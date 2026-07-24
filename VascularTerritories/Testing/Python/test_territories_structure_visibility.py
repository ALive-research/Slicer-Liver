# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 — centerlines + seeds follow the anatomical-structure show/hide.

Hiding a structure (input segment) via the structures table hides everything
derived from it:

* SEEDS — the 3D ``TerritoryPlacementPipeline`` seed glyphs and the 2D
  ``TerritorySlicePipeline`` projected seeds drop the points whose nearest
  STRUCTURE is hidden, and restore them when the structure is shown.  The seed
  is mapped to its structure exactly as extraction groups it
  (``SeedStructureMapping.nearest_structure`` over the per-segment vessel closed
  surfaces).
* CENTERLINES — each extracted centerline model is tagged with its structure
  segment id (``VascularTerritories.StructureSegmentId``) at creation; the
  widget observes the input segmentation's display node and sets each
  ``CenterlineRefs`` model's display visibility to its structure's visibility.

This file pins:

* i1 (launched) — SEED visibility: with seeds on two structures, hiding one
  omits its seeds from the 3D seed-glyph polydata (and the 2D projection);
  showing restores them.
* i2 (launched) — CENTERLINE visibility: a centerline tagged with a structure
  segment id hides when that segment is hidden (and reappears when shown), via
  the widget's segmentation-display-node observer.

All need the wrapped carrier + highlight display node + a live multi-segment
segmentation, so they SKIP cleanly bare and RUN launched (ADR-0027).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4 + slice 5)
  * Docs/adr/0013-layerdm-migration.md  (§5 — no custom displayable manager;
    the centerline follow is a widget-level Python observer)
  * VascularTerritories/Testing/Python/test_territories_placement_pipeline.py
    (the display-node + pickSurface routing this file reuses)
  * VascularTerritories/Testing/Python/test_territories_surface_resolution.py
    (the multi-segment vascular segmentation fixtures)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"
TERRITORY = "T1"

_VEIN_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^29092000^Vein~^^~Anatomic codes~^^~^^"
)
_ARTERY_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^51114001^Artery~^^~Anatomic codes~^^~^^"
)

# The two structures sit far apart so a seed at each centre maps unambiguously
# to its own structure (nearest-closed-surface).
_A_CENTER = (0.0, 0.0, 0.0)
_B_CENTER = (100.0, 0.0, 0.0)
_RADIUS = 15.0


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_carrier_or_skip(slicer, name="StructureVisibilityCarrier"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    if not hasattr(node, "AddAnnotationPoint"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no AddAnnotationPoint -- the "
            "ADR-0037 annotation carrier has not landed (ADR-0027)."
        )
    return node


def _make_display_node_or_skip(slicer, name="StructureVisibilityHighlight"):
    node = slicer.mrmlScene.AddNewNodeByClass(HIGHLIGHT_DISPLAY_CLASS, name)
    if node is None:
        pytest.skip(
            f"{HIGHLIGHT_DISPLAY_CLASS} not registered -- the shared highlight "
            "display node (ADR-0036/0037) is unavailable (launched build)."
        )
    return node


def _add_tagged_sphere(slicer, segmentation, terminology, name, center):
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(_RADIUS)
    source.SetThetaResolution(20)
    source.SetPhiResolution(20)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    modelNode.SetAndObservePolyData(source.GetOutput())
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentation)
    slicer.mrmlScene.RemoveNode(modelNode)
    obj = segmentation.GetSegmentation()
    segId = obj.GetNthSegmentID(obj.GetNumberOfSegments() - 1)
    obj.GetSegment(segId).SetTag("TerminologyEntry", terminology)
    return segId


def _two_structure_segmentation(slicer):
    """A segmentation with two disjoint vascular structures (vein + artery)."""
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, "TwoStructureVessel")
    seg.CreateDefaultDisplayNodes()
    seg.CreateClosedSurfaceRepresentation()
    segA = _add_tagged_sphere(slicer, seg, _VEIN_TERMINOLOGY, "StructureA", _A_CENTER)
    segB = _add_tagged_sphere(slicer, seg, _ARTERY_TERMINOLOGY, "StructureB", _B_CENTER)
    seg.CreateClosedSurfaceRepresentation()
    return seg, segA, segB


def _import_pipeline_or_skip(module_name, class_name):
    try:
        import importlib

        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - LayerDMLib off the bare path
        pytest.skip(
            f"{module_name} not importable ({exc!r}) -- LayerDMLib is reachable "
            "only from a launched Slicer (ADR-0027)."
        )
    cls = getattr(module, class_name, None)
    if cls is None:
        pytest.skip(f"{module_name} has no {class_name} (ADR-0027).")
    return cls


def _seed_point_count(polydata) -> int:
    pts = polydata.GetPoints()
    return pts.GetNumberOfPoints() if pts is not None else 0


def _require_two_mapped_structures(pipeline, segA, segB):
    """Skip unless both structures resolve AND the two seeds map to distinct ones.

    Reads the pipeline's own ``_visible_structures`` (the display-node
    pickSurface resolution the seed filter uses) and the shared
    ``nearest_structure`` mapping, so a launch where the closed-surface reps did
    not build (empty structures, or both seeds collapsing to one) SKIPS -- the
    show/hide follow has nothing to gate on -- rather than FAILING on a fixture
    gap.  When the mapping resolves, the follow is genuinely exercised.
    """
    if not hasattr(pipeline, "_visible_structures"):
        pytest.skip(
            "TerritoryPlacementPipeline has no _visible_structures seam "
            "(ADR-0027)."
        )
    structures = pipeline._visible_structures()
    keys = {segId for segId, _surface, _visible in structures}
    if segA not in keys or segB not in keys:
        pytest.skip(
            "the two vessel structures did not resolve from the pickSurface "
            f"(closed-surface reps unbuilt in this launch); resolved {keys!r}."
        )
    from VascularTerritoriesLib.SeedStructureMapping import nearest_structure

    keyed = [(segId, surface) for segId, surface, _visible in structures]
    if nearest_structure(keyed, _A_CENTER) != segA or nearest_structure(keyed, _B_CENTER) != segB:
        pytest.skip(
            "the seeds did not map to distinct structures in this launch -- "
            "cannot exercise the per-structure show/hide follow."
        )


# =========================================================================== #
# i1 — SEED visibility follows the structure show/hide (3D + 2D)
# =========================================================================== #


def test_hiding_a_structure_omits_its_3d_seed_glyphs(monkeypatch):
    """i1: hiding a structure drops its seeds from the 3D seed-glyph polydata.

    With one seed on structure A and one on structure B (each mapping to its own
    vessel), the 3D pipeline renders two seed glyphs.  Hiding structure B via the
    segmentation display node drops B's seed (one glyph); showing it restores
    both.  ADR-0037 slice 5.  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    Pipeline = _import_pipeline_or_skip(
        "TerritoryPlacementPipeline", "TerritoryPlacementPipeline")
    pipeline = Pipeline()
    if not hasattr(pipeline, "SetDisplayNode"):
        pytest.skip("TerritoryPlacementPipeline has no SetDisplayNode (ADR-0027).")

    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_node_or_skip(slicer)
    seg, segA, segB = _two_structure_segmentation(slicer)
    segDisplay = seg.GetDisplayNode()

    import TerritoryInteractionState as state

    state.set_carrier(display, carrier)
    display.SetAndObservePickSurfaceNodeID(seg.GetID())
    pipeline.SetDisplayNode(display)

    # A seed at each structure's centre -> each maps to its own structure.
    carrier.AddAnnotationPoint(TERRITORY, *_A_CENTER)
    carrier.AddAnnotationPoint(TERRITORY, *_B_CENTER)

    # Precondition: the pipeline must resolve BOTH structures from the display
    # node's pickSurface, and the two seeds must map to DISTINCT structures --
    # otherwise the closed-surface reps did not build in this launch and the
    # follow has nothing to gate on (skip, don't fail on a fixture gap).
    _require_two_mapped_structures(pipeline, segA, segB)

    pipeline._rebuild_seed_actor()
    both = _seed_point_count(pipeline._seed_polydata)
    assert both == 2, (
        f"both seeds must render before hiding (got {both}); the precondition "
        "guard above ensures the structures + mapping resolved."
    )

    segDisplay.SetSegmentVisibility(segB, False)
    pipeline._rebuild_seed_actor()
    assert _seed_point_count(pipeline._seed_polydata) == 1, (
        "hiding structure B must omit its seed from the 3D seed glyphs "
        "(ADR-0037 slice 5)."
    )

    segDisplay.SetSegmentVisibility(segB, True)
    pipeline._rebuild_seed_actor()
    assert _seed_point_count(pipeline._seed_polydata) == 2, (
        "showing structure B must restore its seed to the 3D seed glyphs."
    )


def test_hiding_a_structure_omits_its_2d_projected_seeds():
    """i1: hiding a structure drops its seeds from the 2D projection.

    The slice pipeline projects only the seeds whose structure is visible.
    Hiding structure B drops B's projected seed; showing it restores both.
    ADR-0037 slice 5.  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    Pipeline = _import_pipeline_or_skip(
        "TerritorySlicePipeline", "TerritorySlicePipeline")
    pipeline = Pipeline()
    if not hasattr(pipeline, "SetDisplayNode") or not hasattr(pipeline, "GetProjectedKeys"):
        pytest.skip(
            "TerritorySlicePipeline lacks SetDisplayNode / GetProjectedKeys "
            "(ADR-0027)."
        )

    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_node_or_skip(slicer)
    seg, segA, segB = _two_structure_segmentation(slicer)
    segDisplay = seg.GetDisplayNode()

    import TerritoryInteractionState as state

    # A slice node the projection reslices against (Red).
    sliceNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSliceNode")
    if sliceNode is None:
        pytest.skip("no vtkMRMLSliceNode available for the 2D projection.")

    state.set_carrier(display, carrier)
    display.SetAndObservePickSurfaceNodeID(seg.GetID())
    pipeline.SetDisplayNode(display)
    if hasattr(pipeline, "SetViewNode"):
        pipeline.SetViewNode(sliceNode)
    else:
        pipeline._slice_node = sliceNode

    # Seeds at each structure centre, both in the axial (z=0) plane so the
    # presence cutoff keeps them in the Red slice's projection.
    carrier.AddAnnotationPoint(TERRITORY, *_A_CENTER)
    carrier.AddAnnotationPoint(TERRITORY, *_B_CENTER)

    pipeline._reproject()
    both = len(pipeline.GetProjectedKeys())
    if both != 2:
        pytest.skip(
            "the two seeds did not both project (slice frame / structure "
            f"mapping unavailable in this launch); got {both} -- cannot "
            "exercise the follow."
        )

    segDisplay.SetSegmentVisibility(segB, False)
    pipeline._reproject()
    assert len(pipeline.GetProjectedKeys()) == 1, (
        "hiding structure B must omit its seed from the 2D projection "
        "(ADR-0037 slice 5)."
    )

    segDisplay.SetSegmentVisibility(segB, True)
    pipeline._reproject()
    assert len(pipeline.GetProjectedKeys()) == 2, (
        "showing structure B must restore its projected seed."
    )


# =========================================================================== #
# i2 — CENTERLINE visibility follows the structure show/hide (widget observer)
# =========================================================================== #


def _make_widget_or_skip(slicer):
    from slicer_pytest_support import require_qt_widget as _require_qt_widget

    _require_qt_widget()
    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    return widget


def _detach_scene_observers(slicer, widget):
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 - best-effort across widget shapes
            pass


def _attach_stub_centerline(slicer, logic, carrier, territoryId, structureId, name):
    """Wire a line model into CenterlineRefs, tagged with its structure id."""
    points = vtk.vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 10.0)
    points.InsertNextPoint(0.0, 0.0, -10.0)
    lines = vtk.vtkCellArray()
    lines.InsertNextCell(2)
    lines.InsertCellPoint(0)
    lines.InsertCellPoint(1)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetLines(lines)
    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    model.SetAndObserveMesh(poly)
    model.CreateDefaultDisplayNodes()
    attribute = getattr(
        logic, "CENTERLINE_STRUCTURE_ATTRIBUTE",
        "VascularTerritories.StructureSegmentId")
    model.SetAttribute(attribute, structureId)
    role = getattr(logic, "CENTERLINE_REFERENCE_ROLE", "CenterlineRefs")
    carrier.AddNodeReferenceID(role, model.GetID())
    if hasattr(carrier, "SetGrouping"):
        carrier.SetGrouping(model.GetID(), territoryId)
    return model


def test_centerline_hides_when_its_structure_is_hidden(qt_widgets):
    """i2: a centerline hides when its structure segment is hidden, reappears on show.

    ADR-0037 slice 5: the widget observes the input segmentation's display node
    and syncs each ``CenterlineRefs`` model's visibility to its structure's
    visibility, read off the ``VascularTerritories.StructureSegmentId`` tag.
    A widget-level Python observer (ADR-0013 §5 — no displayable manager).
    Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "_syncCenterlineVisibility"):
        pytest.skip(
            "the ADR-0037 slice-5 centerline-visibility follow "
            "(_syncCenterlineVisibility) has not landed (ADR-0027)."
        )
    if not hasattr(widget.logic, "CENTERLINE_STRUCTURE_ATTRIBUTE"):
        pytest.skip(
            "VascularTerritoriesLogic has no CENTERLINE_STRUCTURE_ATTRIBUTE -- "
            "the ADR-0037 slice-5 structure-id tag has not landed (ADR-0027)."
        )

    seg, segA, segB = _two_structure_segmentation(slicer)
    segDisplay = seg.GetDisplayNode()
    widget.ui.inputSurfaceSelector.setCurrentNode(seg)
    carrier = widget._ensureAnnotationCarrier()

    # A centerline tagged with structure B.
    model = _attach_stub_centerline(
        slicer, widget.logic, carrier, TERRITORY, segB, "StructureBCenterline")
    # Re-sync now that the centerline exists (segmentationNodeSelected already
    # aimed the observer; a direct sync stands in for the extract-time sync).
    widget._syncCenterlineVisibility()
    modelDisplay = model.GetDisplayNode()
    assert modelDisplay is not None

    # Hiding structure B hides its centerline.
    segDisplay.SetSegmentVisibility(segB, False)
    assert bool(modelDisplay.GetVisibility()) is False, (
        "hiding structure B must hide its extracted centerline (ADR-0037 "
        "slice 5)."
    )

    # Showing structure B brings the centerline back.
    segDisplay.SetSegmentVisibility(segB, True)
    assert bool(modelDisplay.GetVisibility()) is True, (
        "showing structure B must restore its centerline's visibility."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
