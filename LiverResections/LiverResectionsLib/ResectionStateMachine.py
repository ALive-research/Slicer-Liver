# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The resection init state machine (ADR-0035).

Single writer for the ADR-0019 state field's ``Init`` interior and the
``Init -> Planning`` commit.  Pipelines translate raw VTK gestures into
the domain events below and call :func:`request`; they never write the
phase attribute or call ``SetState`` for these transitions themselves.
Illegal transitions are refused (``False``) and mutate nothing.

The interior (the v1 composite-widget choreography):

* ``Seeded`` — auto-seeded handles + shader contour only.
* ``Adjusting`` — a plane-handle drag is in flight; the candidate (if
  any) hides while the contour follows.  Transient — persisted only as
  ``Adjusting+<origin>`` so a scene saved mid-drag self-heals
  (:func:`normalize`).
* ``Candidate`` — a re-fitted grid is up as a manipulable candidate
  surface; its first grab (``SurfaceGrabbed``) is the irreversible
  commit to ``Planning``.

The module is pure Python over a node-shaped object (``GetAttribute`` /
``SetAttribute`` / ``GetState`` / ``SetState`` / ``StartModify`` /
``EndModify``) so the transition table is pinned in the bare-VTK unit
layer with stubs.  It never touches actors or renderers: state reaches
pixels only through the existing ``Modified -> reconcile`` flow.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Callable

#: The carrier attribute holding the Init phase.  Values: PHASE_SEEDED,
#: PHASE_CANDIDATE, or the transient ``Adjusting+<origin>``.  Unset reads
#: as Seeded (pre-machine carriers).
PHASE_ATTRIBUTE = "LiverResections.InitPhase"

PHASE_SEEDED = "Seeded"
PHASE_CANDIDATE = "Candidate"
_ADJUSTING_PREFIX = "Adjusting+"

#: Domain events (raised by pipelines from raw VTK gestures).
EVENT_PLANE_HANDLE_GRABBED = "PlaneHandleGrabbed"
EVENT_PLANE_HANDLE_DROPPED = "PlaneHandleDropped"
EVENT_SURFACE_GRABBED = "SurfaceGrabbed"

#: ADR-0019 state integers (mirror the C++ enum on
#: ``vtkMRMLBezierSurfaceNode``; kept numeric so stub nodes work).
STATE_INIT = 0
STATE_PLANNING = 1
STATE_CONFIRMED = 2


# --------------------------------------------------------------------------- #
# Reads (the phase predicate exists ONCE — pipelines import these)
# --------------------------------------------------------------------------- #


def _raw_phase(node: Any) -> str | None:
    if node is None:
        return None
    get = getattr(node, "GetAttribute", None)
    if get is None:
        return None
    return get(PHASE_ATTRIBUTE)


def resting_phase(node: Any) -> str:
    """The resting phase — a transient ``Adjusting+<origin>`` reads as
    its origin; unset/unknown reads as ``Seeded``."""
    raw = _raw_phase(node)
    if raw is None:
        return PHASE_SEEDED
    if raw.startswith(_ADJUSTING_PREFIX):
        raw = raw[len(_ADJUSTING_PREFIX) :]
    return raw if raw in (PHASE_SEEDED, PHASE_CANDIDATE) else PHASE_SEEDED


def in_flight(node: Any) -> bool:
    """True while a plane-handle drag is in flight (``Adjusting``)."""
    raw = _raw_phase(node)
    return raw is not None and raw.startswith(_ADJUSTING_PREFIX)


def candidate_active(node: Any) -> bool:
    """True when the candidate surface should show / accept gestures:
    resting in ``Candidate`` with no drag in flight."""
    return _raw_phase(node) == PHASE_CANDIDATE


def phase_token(node: Any) -> str | None:
    """The raw phase value, for render-key digests.

    A phase flip must repaint the views even when no local gesture
    requested a render (a failed re-fit, undo/redo, a programmatic
    :func:`request`) — pipelines include this token in their
    digest-gated render keys.
    """
    return _raw_phase(node)


# --------------------------------------------------------------------------- #
# Writes — request() and normalize() are the ONLY mutators
# --------------------------------------------------------------------------- #


def request(
    node: Any,
    event: str,
    *,
    refit: Callable[[], bool] | None = None,
) -> bool:
    """Raise a domain event; apply the transition if legal.

    Returns ``True`` iff the transition fired.  A refused event mutates
    nothing.  ``refit`` is the drop's injected grid re-fit action — it
    runs inside the machine's ``StartModify`` batch so the re-fit + the
    phase write land as ONE ``Modified`` (one reconcile), and its return
    value decides ``Candidate`` (success) vs the origin (failure).
    """
    if node is None:
        return False
    state = _safe_state(node)

    if event == EVENT_PLANE_HANDLE_GRABBED:
        if state != STATE_INIT or in_flight(node):
            return False
        node.SetAttribute(
            PHASE_ATTRIBUTE, _ADJUSTING_PREFIX + resting_phase(node)
        )
        return True

    if event == EVENT_PLANE_HANDLE_DROPPED:
        if state != STATE_INIT or not in_flight(node):
            return False
        was_modifying = node.StartModify()
        try:
            # A raising re-fit counts as a FAILED fit -- the phase write
            # below must still land (the "a fired event always leaves a
            # resting phase" contract; an exception here would strand the
            # node in-flight with the gesture cleanup skipped).
            try:
                fitted = bool(refit()) if refit is not None else False
            except Exception:
                fitted = False
            node.SetAttribute(
                PHASE_ATTRIBUTE,
                PHASE_CANDIDATE if fitted else resting_phase(node),
            )
        finally:
            node.EndModify(was_modifying)
        return True

    if event == EVENT_SURFACE_GRABBED:
        if state != STATE_INIT or not candidate_active(node):
            return False
        # The ADR-0019 irreversible commit — the ONLY SetState call for
        # this transition in the codebase (single-writer discipline).
        node.SetState(STATE_PLANNING)
        return True

    return False


def normalize(node: Any) -> None:
    """Collapse a stale in-flight phase back to its encoded origin.

    The scene-saved-mid-drag case: ``Adjusting+<origin>`` persisted into
    a scene reloads with no drag actually in flight.  Pipelines call
    this once on carrier adoption (``SetDisplayNode``), which cannot
    race a live drag — a drag never spans adoption.  A resting phase is
    a no-op (no ``Modified``).
    """
    if node is None or not in_flight(node):
        return
    node.SetAttribute(PHASE_ATTRIBUTE, resting_phase(node))


def _safe_state(node: Any) -> int | None:
    getter = getattr(node, "GetState", None)
    if getter is None:
        return None
    return int(getter())
