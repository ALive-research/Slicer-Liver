# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Volumetry placement cues: a slice hover cursor + a 3D view that never places.

Two usability invariants on the volumetry placement pipelines (ADR-0038 /
ADR-0033):

* FIX B -- a declined bare move in the SLICE pipeline REQUESTS A RENDER so the
  placement-preview cursor paints.  The base DECLINES a bare move (camera
  untouched, ADR-0033) and returns WITHOUT a render; a bare hover mutates no
  observed node, so the preview cursor is computed onto the actor but never
  flushed unless the client's ``_on_bare_move_decline`` requests a render
  itself.  This pins the render request -- the reported "no placement
  cursor/highlight when placing volumetry seeds" -- mirroring the territory
  ``test_bare_move_decline_requests_a_render`` idea.

* FIX C -- the 3D pipeline DECLINES add-on-click (in-volume seeds are placed
  from a slice, never on a 3D surface), while the SLICE pipeline still accepts
  it.  The 3D pipeline reports itself disarmed so the base's add branch is dead
  in ``Can/ProcessInteractionEvent`` (grab-drag editing + rendering intact);
  the shared armed flag the slice pipeline reads is untouched.

HARNESS: launched Slicer.  The pipelines import ``LayerDMLib`` (reachable only
inside a launched Slicer with the module loaded), so a bare
``PythonSlicer -m pytest`` SKIPS CLEANLY (ADR-0027 red->skip / lift-launched).

References
----------
* ADR-0038 -- §Decision (the shared base) + §"Base extension" (the in-volume
  pick that makes placement a SLICE gesture).
* ADR-0033 -- the bare-move-decline hover discipline (camera untouched; the
  cue is a render-flushed side effect).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/Testing/Python/test_territories_placement_pipeline.py --
  ``test_bare_move_decline_requests_a_render``, the sibling this mirrors.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "SlicerLiverInteractionLib",
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pipelines_or_skip():
    """Import the volumetry slice + 3D pipelines, or skip-pend (ADR-0027).

    Both import ``LayerDMLib`` (via the shared base), so this skips cleanly on
    a bare ``PythonSlicer`` where LayerDMLib is unreachable.
    """
    try:
        from VolumetrySeedPipeline import (
            VolumetrySeedPipeline3D,
            VolumetrySeedPipelineSlice,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"volumetry pipelines not importable ({exc!r}) -- the shared base / "
            "LayerDMLib is unreachable bare (ADR-0027 skip; lifts launched)."
        )
    return VolumetrySeedPipeline3D, VolumetrySeedPipelineSlice


class _FakeSliceNode:
    """An axial slice at z=0, 1 mm/px, so the preview projection is exercisable."""

    def __init__(self):
        self._m = vtk.vtkMatrix4x4()
        self._m.Identity()

    def GetXYToRAS(self):  # noqa: N802 - VTK verb
        return self._m

    def GetSliceToRAS(self):  # noqa: N802 - VTK verb
        return self._m

    def IsA(self, cls):  # noqa: N802 - VTK verb
        return cls == "vtkMRMLSliceNode"

    def AddObserver(self, *args, **kwargs):  # noqa: N802 - VTK verb
        return 0

    def RemoveObserver(self, *args, **kwargs):  # noqa: N802 - VTK verb
        pass


class _FakePick:
    """An in-volume pick returning a FIXED interior world point on any hover."""

    def __init__(self, world=(3.0, 4.0, 0.0)):
        self._world = world

    def pick_for_event(self, renderer, eventData):
        return self._world

    def pick_for_slice_event(self, slice_node, display_xy):
        return self._world


class _FakeRenderer:
    pass


class _Event:
    def __init__(self, etype, display_position=(100, 100)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def test_slice_bare_move_decline_requests_a_render(monkeypatch):
    """FIX B: a declined bare move in the SLICE pipeline REQUESTS A RENDER.

    Without it the placement-preview cursor is computed onto the actor but
    never flushed -- the reported "no placement cursor/highlight" (the
    ADR-0033 hover cue is a render-flushed side effect of the declined move).
    """
    _slicer_or_skip()
    _Pipeline3D, PipelineSlice = _import_pipelines_or_skip()
    pipeline = PipelineSlice()
    if not hasattr(pipeline, "_on_bare_move_decline"):
        pytest.skip("slice pipeline has no _on_bare_move_decline hook (ADR-0027).")

    pipeline._slice_node = _FakeSliceNode()
    pipeline.SetPickProvider(_FakePick())
    pipeline._armed = True
    pipeline._module_active = True

    renders = []
    monkeypatch.setattr(pipeline, "RequestRender", lambda: renders.append(1))

    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    can, distance2 = pipeline.CanProcessInteractionEvent(move)

    assert can is False, "a bare move must still be DECLINED (camera untouched)."
    assert distance2 == sys.float_info.max
    assert renders, (
        "a declined bare move must REQUEST A RENDER so the placement-preview "
        "cursor actually paints -- without it the hover cue is computed but "
        "never flushed (the reported 'no cursor' regression)."
    )


def test_slice_hover_shows_a_preview_cursor_when_armed(monkeypatch):
    """FIX B: an ARMED slice hover over a seedable voxel shows the preview cursor.

    The preview ring tracks the cursor over the interior voxel a click would
    seed; hidden when disarmed (edit-only) or off any region (pick declines).
    """
    _slicer_or_skip()
    _Pipeline3D, PipelineSlice = _import_pipelines_or_skip()
    pipeline = PipelineSlice()
    if not hasattr(pipeline, "_preview_actor"):
        pytest.skip("slice pipeline has no _preview_actor (FIX B not landed; ADR-0027).")

    pipeline._slice_node = _FakeSliceNode()
    pipeline.SetPickProvider(_FakePick())
    monkeypatch.setattr(pipeline, "RequestRender", lambda: None)

    # Disarmed: no placement preview (the base's ring cues grab targets instead).
    pipeline._armed = False
    pipeline._module_active = True
    pipeline._on_bare_move_decline(_Event(vtk.vtkCommand.MouseMoveEvent))
    assert pipeline._preview_actor.GetVisibility() == 0, (
        "a DISARMED hover must not show a placement preview."
    )

    # Armed over a seedable voxel: the preview cursor appears.
    pipeline._armed = True
    pipeline._on_bare_move_decline(_Event(vtk.vtkCommand.MouseMoveEvent))
    assert pipeline._preview_actor.GetVisibility() == 1, (
        "an ARMED hover over a seedable interior voxel must show the preview cursor."
    )
    assert pipeline._preview_polydata.GetPoints().GetNumberOfPoints() == 1


def test_slice_hover_hides_preview_when_pick_declines(monkeypatch):
    """FIX B: the preview cursor hides where a click would NOT place a seed.

    The pick declines (``None``) off any labelled region / beyond the local
    search radius, so the cursor cue truthfully tracks placeability.
    """
    _slicer_or_skip()
    _Pipeline3D, PipelineSlice = _import_pipelines_or_skip()
    pipeline = PipelineSlice()
    if not hasattr(pipeline, "_preview_actor"):
        pytest.skip("slice pipeline has no _preview_actor (FIX B not landed; ADR-0027).")

    pipeline._slice_node = _FakeSliceNode()
    pipeline.SetPickProvider(_FakePick(world=None))
    pipeline._armed = True
    pipeline._module_active = True
    monkeypatch.setattr(pipeline, "RequestRender", lambda: None)

    pipeline._on_bare_move_decline(_Event(vtk.vtkCommand.MouseMoveEvent))
    assert pipeline._preview_actor.GetVisibility() == 0, (
        "the preview cursor must hide where the pick declines (no seedable voxel)."
    )


def test_3d_pipeline_declines_placement_while_slice_accepts(monkeypatch):
    """FIX C: the 3D pipeline DECLINES add-on-click; the slice pipeline accepts.

    Volumetry seeds are in-volume: placing one on a 3D surface is invalid, so
    the 3D pipeline reports itself disarmed (add branch dead) while the slice
    pipeline reads the real armed flag and places.
    """
    _slicer_or_skip()
    Pipeline3D, PipelineSlice = _import_pipelines_or_skip()

    p3d = Pipeline3D()
    p3d._armed = True
    p3d._module_active = True
    assert p3d.IsArmed() is False, (
        "the 3D pipeline must report itself DISARMED so the base's add-on-click "
        "branch is dead -- in-volume seeds are placed from a slice, not on a 3D "
        "surface (FIX C)."
    )

    pslice = PipelineSlice()
    pslice._armed = True
    pslice._module_active = True
    assert pslice.IsArmed() is True, (
        "the SLICE pipeline must still arm for placement (the in-volume pick "
        "resolves a slice click to an interior voxel)."
    )


def test_3d_pipeline_still_renders_and_grabs(monkeypatch):
    """FIX C: disabling 3D PLACEMENT leaves grab-drag editing + rendering intact.

    The grab hit-test is gated BEFORE the arm check in the base, so an existing
    seed near the press is still claimed for a drag in a 3D view -- only the
    add-on-click branch is disabled.
    """
    _slicer_or_skip()
    Pipeline3D, _PipelineSlice = _import_pipelines_or_skip()

    pipeline = Pipeline3D()
    for seam in ("_nearest_key_in_display", "_safe_get_renderer"):
        if not hasattr(pipeline, seam):
            pytest.skip(f"base has no {seam} seam (ADR-0027).")

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    monkeypatch.setattr(pipeline, "_nearest_key_in_display", lambda r, e: (0, 4.0))

    press = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    can, distance2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True, "a press near an existing seed must still be claimed for a drag in 3D."
    assert distance2 == pytest.approx(4.0), "the grab claims the REAL squared display distance."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
