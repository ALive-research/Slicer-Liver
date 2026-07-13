# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Transition-table pins for ``ResectionStateMachine`` (ADR-0035).

The Init interior (Seeded / Adjusting / Candidate) + the single-writer
transition discipline: pipelines raise domain events through
``request(carrier, event, ...)``; illegal transitions are refused and
mutate nothing; the drop's re-fit action runs inside ONE ``Modified``
batch; a stale in-flight phase normalizes back to its encoded origin on
carrier adoption (the scene-saved-mid-drag case).

Pure Python over a node-shaped stub — runs in the bare-VTK unit layer
(no Slicer, no wrapped MRML).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

import ResectionStateMachine as rsm  # noqa: E402 - after the path insert


class _StubCarrier:
    """vtkMRMLBezierSurfaceNode-shaped stub: attributes + state + batching."""

    def __init__(self, state=0):
        self._attributes = {}
        self._state = state
        self._modify_depth = 0
        self.modified_events = 0

    # -- attribute API -------------------------------------------------- #
    def GetAttribute(self, name):  # noqa: N802 - VTK verb
        return self._attributes.get(name)

    def SetAttribute(self, name, value):  # noqa: N802 - VTK verb
        self._attributes[name] = value
        self.Modified()

    # -- state API (ADR-0019) ------------------------------------------- #
    def GetState(self):  # noqa: N802 - VTK verb
        return self._state

    def SetState(self, state):  # noqa: N802 - VTK verb
        self._state = int(state)
        self.Modified()

    # -- Modified batching ---------------------------------------------- #
    def StartModify(self):  # noqa: N802 - VTK verb
        was = self._modify_depth > 0
        self._modify_depth += 1
        return was

    def EndModify(self, was):  # noqa: N802 - VTK verb
        self._modify_depth -= 1
        if not was:
            self.modified_events += 1

    def Modified(self):  # noqa: N802 - VTK verb
        if self._modify_depth == 0:
            self.modified_events += 1


def test_unset_phase_reads_as_seeded():
    carrier = _StubCarrier()
    assert rsm.resting_phase(carrier) == rsm.PHASE_SEEDED
    assert rsm.in_flight(carrier) is False
    assert rsm.candidate_active(carrier) is False


def test_grab_then_successful_drop_raises_the_candidate():
    carrier = _StubCarrier(state=rsm.STATE_INIT)

    assert rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED) is True
    assert rsm.in_flight(carrier) is True
    assert rsm.resting_phase(carrier) == rsm.PHASE_SEEDED
    assert rsm.candidate_active(carrier) is False, (
        "mid-drag the candidate must read inactive (the surface hides)."
    )

    assert (
        rsm.request(
            carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True
        )
        is True
    )
    assert rsm.in_flight(carrier) is False
    assert rsm.candidate_active(carrier) is True, (
        "dropping the handle GENERATES the candidate (v1)."
    )


def test_failed_refit_restores_the_origin_phase():
    carrier = _StubCarrier(state=rsm.STATE_INIT)

    # From Seeded: a failed re-fit falls back to Seeded.
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: False)
    assert rsm.resting_phase(carrier) == rsm.PHASE_SEEDED
    assert rsm.candidate_active(carrier) is False

    # Raise a candidate, then drag again with a failing re-fit: the
    # PREVIOUS fitted grid still exists -- the origin (Candidate) must
    # be restored, not Seeded.
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    assert rsm.resting_phase(carrier) == rsm.PHASE_CANDIDATE
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: False)
    assert rsm.candidate_active(carrier) is True, (
        "a failed re-fit from Candidate keeps the previous candidate."
    )


def test_surface_grab_commits_only_from_candidate():
    carrier = _StubCarrier(state=rsm.STATE_INIT)

    # No candidate yet: the commit is refused, nothing mutates.
    before = carrier.modified_events
    assert rsm.request(carrier, rsm.EVENT_SURFACE_GRABBED) is False
    assert carrier.GetState() == rsm.STATE_INIT
    assert carrier.modified_events == before, "a refused event mutates nothing"

    # Mid-drag: still refused.
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    assert rsm.request(carrier, rsm.EVENT_SURFACE_GRABBED) is False
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)

    # Candidate up: the first surface grab IS the Init -> Planning commit.
    assert rsm.request(carrier, rsm.EVENT_SURFACE_GRABBED) is True
    assert carrier.GetState() == rsm.STATE_PLANNING

    # Irreversible (ADR-0019): a second commit request is a refused no-op.
    assert rsm.request(carrier, rsm.EVENT_SURFACE_GRABBED) is False
    assert carrier.GetState() == rsm.STATE_PLANNING


def test_events_are_refused_outside_init():
    carrier = _StubCarrier(state=rsm.STATE_PLANNING)
    assert rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED) is False
    assert (
        rsm.request(
            carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True
        )
        is False
    )
    assert rsm.resting_phase(carrier) == rsm.PHASE_SEEDED


def test_double_grab_and_bare_drop_are_refused():
    carrier = _StubCarrier(state=rsm.STATE_INIT)
    assert (
        rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)
        is False
    ), "a drop without a grab in flight is refused"
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    assert rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED) is False, (
        "a second grab while one is in flight is refused"
    )


def test_drop_is_one_modified_batch():
    carrier = _StubCarrier(state=rsm.STATE_INIT)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    carrier.modified_events = 0

    def _refit():
        # The real re-fit writes the 16 grid points on the carrier; the
        # machine's batch must absorb those writes too.
        carrier.Modified()
        carrier.Modified()
        return True

    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=_refit)
    assert carrier.modified_events == 1, (
        "the drop (re-fit + phase write) must land as EXACTLY ONE "
        "Modified -- the composite reveal is a single reconcile."
    )


def test_normalize_collapses_a_stale_in_flight_phase():
    """The scene-saved-mid-drag case: on carrier adoption a stale
    ``Adjusting+<origin>`` collapses back to its origin."""
    carrier = _StubCarrier(state=rsm.STATE_INIT)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    assert rsm.in_flight(carrier) is True

    rsm.normalize(carrier)
    assert rsm.in_flight(carrier) is False
    assert rsm.candidate_active(carrier) is True, (
        "the stale drag collapses to its Candidate origin."
    )

    # Normalizing a resting phase is a no-op.
    before = carrier.modified_events
    rsm.normalize(carrier)
    assert carrier.modified_events == before


def test_unknown_event_is_refused():
    carrier = _StubCarrier(state=rsm.STATE_INIT)
    assert rsm.request(carrier, "NoSuchEvent") is False


def test_raising_refit_counts_as_a_failed_fit():
    """A drop whose re-fit RAISES still lands a resting phase (the
    origin) -- an exception must not strand the node in-flight with the
    caller's gesture cleanup skipped."""
    carrier = _StubCarrier(state=rsm.STATE_INIT)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)

    def _exploding_refit():
        raise RuntimeError("degenerate ring")

    assert (
        rsm.request(
            carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=_exploding_refit
        )
        is True
    ), "the drop still fires -- the raise reads as a failed fit"
    assert rsm.in_flight(carrier) is False
    assert rsm.resting_phase(carrier) == rsm.PHASE_SEEDED
    assert rsm.phase_token(carrier) == rsm.PHASE_SEEDED, (
        "the render-key token reads the landed resting phase"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
