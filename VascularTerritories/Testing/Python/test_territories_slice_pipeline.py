# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 §2D — the slice-view territory placement + distance-faded viz.

ADR-0037 §Decision 2 routes vessel-annotation placement through a LayerDM
scripted Pipeline; this file pins the SLICE-VIEW complement
(``TerritorySlicePipeline``), which mirrors
``LiverResectionsLib.SliceControlPolygonPipeline`` (ADR-0033):

* PROJECTION (viz).  Every visible territory's carrier seeds project into
  the slice view's XY space (``inverse(XYToRAS)``), faded by |signed
  distance to the slice plane| over ``FADE_DISTANCE_MM``, with a signed
  above/below SIDE TINT and a HARD presence cutoff at ``PICK_RANGE_MM``
  (2D alpha is unreliable).  These are pure geometry given a slice node
  exposing ``GetXYToRAS`` / ``GetSliceToRAS``, so they run BARE against the
  ``TerritorySliceProjection`` helper module — no LayerDM, no GL, no scene.
* SNAP (placement).  An armed LEFT-BUTTON PRESS resolves the slice pixel to
  RAS on the plane (``XYToRAS``), casts a ray ALONG THE SLICE NORMAL, and
  feeds it to ``VesselSurfacePick`` -> the surface-snapped seed lands in the
  ACTIVE territory.  A bare MOVE is DECLINED (``(False, +inf)``, ADR-0033);
  a disarmed press away from any seed leaves the gesture to the camera.
* SHARED STATE.  Arm / active-territory / carrier live on the SAME shared
  highlight display node the 3D placement uses
  (``TerritoryInteractionState``), so 2D and 3D placement stay in lockstep.

The projection math runs bare; the Pipeline itself needs LayerDMLib
(reachable only inside a launched Slicer with the module loaded), so the
snap / arm-gate / decline invariants SKIP bare and RUN launched, mirroring
the 3D ``test_territories_placement_pipeline.py`` suite.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (the decision)
  * Docs/adr/0033-control-polygon-display-aspect.md  (slice-projection + hover)
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the seam)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * LiverResections/LiverResectionsLib/SliceControlPolygonPipeline.py  (mirror)
  * VascularTerritories/VascularTerritoriesLib/TerritorySliceProjection.py
  * VascularTerritories/VascularTerritoriesLib/TerritorySlicePipeline.py
  * VascularTerritories/Testing/Python/test_territories_placement_pipeline.py
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
TERRITORY_A = "SegmentVII"
TERRITORY_B = "SegmentVIII"

# --------------------------------------------------------------------------- #
# Repo geometry — the pure-math helper lives in the VascularTerritoriesLib
# package alongside the pick core.  The path-insert lets the bare unit layer
# import the projection module before the packaging follow-up lands (the
# test_vessel_surface_pick.py precedent).
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "VascularTerritories" / "VascularTerritoriesLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Fake slice node — pure matrices, no MRML
# --------------------------------------------------------------------------- #


def _identity_scaled(fov_mm_per_px=1.0):
    """A 4x4 mapping XY pixels to RAS with a uniform mm-per-pixel scale."""
    m = vtk.vtkMatrix4x4()
    m.Identity()
    m.SetElement(0, 0, fov_mm_per_px)
    m.SetElement(1, 1, fov_mm_per_px)
    return m


class _FakeSliceNode:
    """An axial slice at ``z = z0``: normal +z, pixels 1 mm apart in x/y.

    ``GetSliceToRAS`` origin is ``(0, 0, z0)`` with the standard axial
    basis; ``GetXYToRAS`` maps pixel ``(ex, ey, 0)`` to RAS
    ``(ex, ey, z0)`` — the in-plane landing point.
    """

    def __init__(self, z0=0.0, fov_mm_per_px=1.0):
        self._slice_to_ras = vtk.vtkMatrix4x4()
        self._slice_to_ras.Identity()
        self._slice_to_ras.SetElement(2, 3, z0)
        self._xy_to_ras = _identity_scaled(fov_mm_per_px)
        self._xy_to_ras.SetElement(2, 3, z0)

    def GetSliceToRAS(self):  # noqa: N802 - VTK verb
        return self._slice_to_ras

    def GetXYToRAS(self):  # noqa: N802 - VTK verb
        return self._xy_to_ras

    def IsA(self, cls):  # noqa: N802 - VTK verb
        return cls == "vtkMRMLSliceNode"


# --------------------------------------------------------------------------- #
# Skip-guards for the launched-only Pipeline invariants
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_projection_or_skip():
    """Import the pure-math projection helper, or skip-pend (ADR-0027)."""
    try:
        import TerritorySliceProjection as proj
    except ImportError:
        pytest.skip(
            "TerritorySliceProjection not importable -- the ADR-0037 §2D slice "
            "projection helper has not landed (ADR-0027 red->skip)."
        )
    return proj


def _import_pipeline_or_skip():
    try:
        from VascularTerritoriesLib.TerritorySlicePipeline import (
            TerritorySlicePipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritorySlicePipeline not importable ({exc!r}) -- the ADR-0037 "
            "§2D slice Pipeline has not landed OR LayerDMLib is not reachable "
            "here.  The skip lifts at the implementation commit (ADR-0027)."
        )
    return TerritorySlicePipeline


def _import_pick_or_skip():
    try:
        from VesselSurfacePick import VesselSurfacePick
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselSurfacePick not importable ({exc!r}).")
    return VesselSurfacePick


def _import_interaction_state_or_skip():
    try:
        import TerritoryInteractionState as state
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"TerritoryInteractionState not importable ({exc!r}).")
    return state


def _make_carrier_or_skip(slicer, name="SliceCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- the ADR-0037 "
            "annotation carrier has not landed (launched build)."
        )
    if not hasattr(node, "AddAnnotationPoint"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no AddAnnotationPoint -- the "
            "annotation carrier API has not landed (ADR-0027)."
        )
    return node


def _make_display_node_or_skip(slicer, name="SliceHighlightTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(HIGHLIGHT_DISPLAY_CLASS, name)
    if node is None:
        pytest.skip(
            f"{HIGHLIGHT_DISPLAY_CLASS} not registered -- the shared highlight "
            "display node is unavailable (launched build)."
        )
    return node


def _unit_sphere():
    source = vtk.vtkSphereSource()
    source.SetRadius(1.0)
    source.SetThetaResolution(64)
    source.SetPhiResolution(64)
    source.Update()
    return source.GetOutput()


class _Event:
    """A minimal interaction event at a fixed display pixel + type."""

    def __init__(self, etype, display_position=(0, 0)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


# --------------------------------------------------------------------------- #
# PURE MATH — projection / signed distance / presence cutoff (BARE)
# --------------------------------------------------------------------------- #


def test_project_ras_to_xy_round_trips_in_plane_point():
    """A point ON the slice plane projects to its pixel via inverse(XYToRAS).

    With a 1 mm/px axial slice at z=0, RAS ``(3, 4, 0)`` projects to XY
    ``(3, 4)`` — the slice-view display coordinates coincide with this XY
    space (the SliceControlPolygonPipeline convention).
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0, fov_mm_per_px=1.0)

    xy = proj.project_ras_to_xy(slice_node, (3.0, 4.0, 0.0))

    assert xy is not None
    assert xy == pytest.approx((3.0, 4.0), abs=1e-6)


def test_signed_distance_is_positive_above_negative_below():
    """Signed distance is + above the plane (along +normal), - below.

    An axial slice at z=0 has normal +z; RAS ``(0, 0, 5)`` is 5 mm above,
    ``(0, 0, -5)`` is 5 mm below.
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0)

    assert proj.signed_distance_to_slice(slice_node, (0.0, 0.0, 5.0)) == pytest.approx(5.0)
    assert proj.signed_distance_to_slice(slice_node, (0.0, 0.0, -5.0)) == pytest.approx(-5.0)
    assert proj.signed_distance_to_slice(slice_node, (2.0, 9.0, 0.0)) == pytest.approx(0.0)


def test_presence_cutoff_is_hard_at_pick_range():
    """Presence is a HARD cutoff at ``PICK_RANGE_MM`` (2D alpha unreliable).

    A seed just inside the range is present; one at / beyond it is absent —
    not merely faded to zero alpha (the ADR-0033 slice-polygon rule).
    """
    proj = _import_projection_or_skip()

    assert proj.is_present(proj.PICK_RANGE_MM - 0.01) is True
    assert proj.is_present(proj.PICK_RANGE_MM) is False
    assert proj.is_present(proj.PICK_RANGE_MM + 5.0) is False
    # The fade is monotone: nearer the plane => more opaque.
    assert proj.fade_alpha(0.0) == pytest.approx(1.0)
    assert proj.fade_alpha(proj.FADE_DISTANCE_MM) == pytest.approx(0.0)
    assert 0.0 < proj.fade_alpha(proj.FADE_DISTANCE_MM / 2.0) < 1.0


def test_side_tint_lightens_above_and_darkens_below():
    """The signed side tint pulls a mid-grey toward white above / black below."""
    proj = _import_projection_or_skip()
    base = [128, 128, 128]

    above = proj.side_tint(base, +proj.FADE_DISTANCE_MM)
    below = proj.side_tint(base, -proj.FADE_DISTANCE_MM)

    assert above[0] > base[0], "above the plane must lighten toward white."
    assert below[0] < base[0], "below the plane must darken toward black."


def test_normal_ray_runs_along_the_slice_normal_through_the_point():
    """The snap ray straddles the RAS point ALONG the slice normal.

    An axial slice's normal is +z, so the ray through ``(1, 2, 0)`` runs
    from ``(1, 2, +extent)`` to ``(1, 2, -extent)`` — the x/y stay fixed.
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0)

    ray = proj.normal_ray(slice_node, (1.0, 2.0, 0.0), extent_mm=50.0)

    assert ray is not None
    p1, p2 = ray
    assert p1 == pytest.approx((1.0, 2.0, 50.0), abs=1e-6)
    assert p2 == pytest.approx((1.0, 2.0, -50.0), abs=1e-6)


# --------------------------------------------------------------------------- #
# PIPELINE — snap / arm-gate / decline (LAUNCHED; SKIP bare)
# --------------------------------------------------------------------------- #


def _wire_slice_pipeline_or_skip(slicer, pipeline, displayNode, carrier, monkeypatch):
    """Bind the pipeline to the shared display node + a slice view + pick core."""
    VesselSurfacePick = _import_pick_or_skip()
    state = _import_interaction_state_or_skip()
    for method in ("SetPickCore", "SetDisplayNode", "SetViewNode"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"TerritorySlicePipeline has no {method} seam (ADR-0027)."
            )
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    # The C++ base SetViewNode type-checks for a real vtkMRMLAbstractViewNode;
    # the deterministic _FakeSliceNode drives the pure-Python projection/snap
    # math, so set the internal slice-node field directly (avoids the C++
    # marshalling that rejects a duck-typed node).
    pipeline._slice_node = _FakeSliceNode(z0=0.0)
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)
    # SetDisplayNode resets the pick to force a re-resolve from the node's
    # pickSurface (production behaviour), so inject the pick AFTER binding it.
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))


def test_armed_slice_press_adds_one_surface_snapped_seed(monkeypatch):
    """An armed slice press snaps ONE seed onto the surface in the ACTIVE territory.

    The pixel resolves to RAS on the plane, the normal ray hits the unit
    sphere the injected pick core wraps, and the snapped seed lands in the
    display-node ACTIVE territory (ADR-0037 §2D snap; the 2D/3D lockstep).
    """
    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_pipeline_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    _wire_slice_pipeline_or_skip(slicer, pipeline, displayNode, carrier, monkeypatch)

    state.set_active_territory(displayNode, TERRITORY_A)
    state.set_armed(displayNode, True)

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    # A pixel over the plane origin: the normal ray straddles the sphere.
    press = _Event(vtk.vtkCommand.LeftButtonPressEvent, display_position=(0, 0))
    assert pipeline.CanProcessInteractionEvent(press)[0] is True, (
        "an armed press over the surface must be CLAIMED (add-on-click)."
    )
    assert pipeline.ProcessInteractionEvent(press) is True

    after = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert after == before + 1, "an armed slice press must add EXACTLY ONE seed."


def test_disarmed_slice_press_adds_nothing(monkeypatch):
    """A disarmed slice press away from any seed adds no seed (ADR-0037 §Decision 3)."""
    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_pipeline_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    _wire_slice_pipeline_or_skip(slicer, pipeline, displayNode, carrier, monkeypatch)

    state.set_active_territory(displayNode, TERRITORY_A)
    state.set_armed(displayNode, False)

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    press = _Event(vtk.vtkCommand.LeftButtonPressEvent, display_position=(0, 0))
    can, _distance2 = pipeline.CanProcessInteractionEvent(press)

    assert can is False, "a disarmed press away from any seed must be DECLINED."
    pipeline.ProcessInteractionEvent(press)
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a disarmed slice press must add no seed."
    )


def test_bare_slice_move_is_declined(monkeypatch):
    """A bare slice move is DECLINED even while armed (ADR-0033 hover discipline)."""
    import sys as _sys

    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_pipeline_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    _wire_slice_pipeline_or_skip(slicer, pipeline, displayNode, carrier, monkeypatch)

    state.set_active_territory(displayNode, TERRITORY_A)
    state.set_armed(displayNode, True)

    move = _Event(vtk.vtkCommand.MouseMoveEvent, display_position=(0, 0))
    can, distance2 = pipeline.CanProcessInteractionEvent(move)

    assert can is False, "a bare move must stay declined while armed (ADR-0033)."
    assert distance2 == _sys.float_info.max


def test_reproject_projects_only_present_visible_seeds(monkeypatch):
    """The reproject drops seeds beyond the presence cutoff + invisible territories.

    A seed on the plane is present; one far off the plane (beyond
    ``PICK_RANGE_MM``) is dropped; an invisible territory contributes none.
    The projected-key bookkeeping reflects exactly the surviving seeds.
    """
    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_pipeline_or_skip()
    proj = _import_projection_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    if not hasattr(pipeline, "GetProjectedKeys") or not hasattr(pipeline, "SetViewNode"):
        pytest.skip("TerritorySlicePipeline lacks GetProjectedKeys / SetViewNode (ADR-0027).")

    carrier.SetTerritoryVisibility(TERRITORY_A, True)
    carrier.SetTerritoryColor(TERRITORY_A, 0.9, 0.2, 0.2)
    carrier.AddAnnotationPoint(TERRITORY_A, 3.0, 4.0, 0.0)  # on plane -> present
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, proj.PICK_RANGE_MM + 10.0)  # far -> absent
    carrier.SetTerritoryVisibility(TERRITORY_B, False)
    carrier.SetTerritoryColor(TERRITORY_B, 0.2, 0.2, 0.9)
    carrier.AddAnnotationPoint(TERRITORY_B, 1.0, 1.0, 0.0)  # invisible -> absent

    state.set_carrier(displayNode, carrier)
    # Set the internal slice-node field directly: the C++ base SetViewNode
    # type-checks for a real view node, while the deterministic _FakeSliceNode
    # drives the pure-Python projection math under test.
    pipeline._slice_node = _FakeSliceNode(z0=0.0)
    pipeline.SetDisplayNode(displayNode)
    pipeline._reproject()

    keys = pipeline.GetProjectedKeys()
    assert keys == [(TERRITORY_A, 0)], (
        "only the present, visible seed survives the projection (HARD presence "
        "cutoff + territory visibility)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
