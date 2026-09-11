# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The group-gesture seam on the shared placement base (ADR-0038).

A GROUP gesture translates a set of control points rigidly -- every
member displaced by the same delta -- as opposed to the per-point drag
the base already arbitrates.  The control polygon needs two of them: a
frame drag moving the whole polygon, and a ring drag moving one ring.

The base carries the ARBITRATION only.  What a group is, and what a
delta does to it, is data-model knowledge that stays with the client
(ADR-0038 §"What is not shared") -- so the base hands a client-defined
id straight back to the client's hooks and never moves a point itself.

The load-bearing property here is that the seam is INERT for clients
that do not opt in.  Three modules sit on this base (resection control
polygon, vascular territories, volumetry seeds); a widening that leaked
into their dispatch would change interaction everywhere at once.  The
default ``_group_pick`` declines every press, so those clients see the
dispatch they always saw.

HARNESS: launched Slicer.  The renderer, scene and GL are all stubbed
out here -- the arbitration under test is pure Python -- but the base
class itself derives from ``vtkMRMLLayerDMPipelineI``, which is
reachable only inside a launched Slicer with LayerDM loaded.  A bare
``PythonSlicer -m pytest`` SKIPS CLEANLY (ADR-0027).
"""

from __future__ import annotations

import importlib
import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

# The lib ships flat into qt-scripted-modules, so its modules are imported
# by bare name; put the source dir on the path the same way the sibling
# base tests do.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


def _base_or_skip():
    try:
        module = importlib.import_module("SurfacePointPlacementPipeline3D")
    except Exception as exc:
        pytest.skip(f"placement base not importable ({exc!r}) -- ADR-0027.")
    if not hasattr(module, "SurfacePointPlacementPipeline3D"):
        pytest.skip("SurfacePointPlacementPipeline3D absent (ADR-0027).")
    return module


class _Event:
    """Minimal eventData stand-in: only the event type is read here."""

    def __init__(self, etype):
        self._etype = etype

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype


def _make_pipeline(base_module, group_claim=None):
    """A pipeline whose renderer/admissibility are stubbed out.

    ``group_claim`` is what ``_group_pick`` returns; ``None`` models a
    client that never opted in.
    """
    cls = base_module.SurfacePointPlacementPipeline3D

    class _Probe(cls):
        def __init__(self):
            super().__init__("test")
            self.grabs = []
            self.drags = []
            self.releases = []

        # Stub the environment the base would otherwise reach for.
        def _safe_get_renderer(self):
            return object()

        def _admissible(self):
            return True

        def _nearest_key_in_display(self, renderer, eventData):
            return None, float("inf")

        def _pick_world(self, renderer, eventData):
            return None

        def _event_world(self, renderer, eventData):
            return (1.0, 2.0, 3.0)

        def RequestRender(self):  # noqa: N802 - VTK verb
            pass

        def _group_pick(self, renderer, eventData, etype):
            return group_claim

        def _on_group_grab(self, group, renderer, eventData):
            self.grabs.append(group)

        def _on_group_drag(self, group, world):
            self.drags.append((group, world))

        def _on_group_release(self, group):
            self.releases.append(group)

    try:
        return _Probe()
    except Exception as exc:  # pragma: no cover - construction needs the C++ base
        pytest.skip(f"placement base not constructible here ({exc!r}) -- ADR-0027.")


def test_default_group_pick_declines_every_press():
    """The seam is inert for a client that does not opt in."""
    base_module = _base_or_skip()
    pipeline = _make_pipeline(base_module, group_claim=None)

    for etype in (
        vtk.vtkCommand.LeftButtonPressEvent,
        vtk.vtkCommand.RightButtonPressEvent,
    ):
        claimed, _distance = pipeline.CanProcessInteractionEvent(_Event(etype))
        assert claimed is False, (
            "A client that never overrides _group_pick must see the "
            "dispatch it always saw; three modules depend on this."
        )


def test_right_press_is_claimed_only_when_a_client_opts_in():
    """A right press reaches the group seam and can be claimed."""
    base_module = _base_or_skip()
    pipeline = _make_pipeline(base_module, group_claim=("ring0", 0.0))

    claimed, _distance = pipeline.CanProcessInteractionEvent(
        _Event(vtk.vtkCommand.RightButtonPressEvent)
    )
    assert claimed is True, (
        "The base filtered to LeftButtonPress only, so a right-drag "
        "gesture could never be routed; the ring gesture needs it."
    )


def test_group_gesture_runs_grab_drag_release_and_ends_on_its_own_button():
    """A right-button group drag ends on the RIGHT release, not the left."""
    base_module = _base_or_skip()
    pipeline = _make_pipeline(base_module, group_claim=("ring0", 0.0))

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.RightButtonPressEvent)
    )
    assert pipeline.grabs == ["ring0"]

    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.MouseMoveEvent))
    assert pipeline.drags == [("ring0", (1.0, 2.0, 3.0))]

    # A LEFT release must not end a RIGHT gesture.
    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonReleaseEvent))
    assert pipeline.releases == [], (
        "A group gesture must end on the release of the button that "
        "started it, or a stray left click would strand the drag."
    )

    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.RightButtonReleaseEvent))
    assert pipeline.releases == ["ring0"]


def test_group_drag_never_moves_a_point_in_the_base():
    """The base holds the gesture's identity, never its meaning."""
    base_module = _base_or_skip()
    pipeline = _make_pipeline(base_module, group_claim=("frame", 0.0))

    moved = []
    pipeline._move_point = lambda key, world: moved.append((key, world))

    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.RightButtonPressEvent))
    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.MouseMoveEvent))

    assert moved == [], (
        "What a delta does to a group is the client's data model "
        "(ADR-0038 §'What is not shared'); the base must not displace "
        "anything itself."
    )
