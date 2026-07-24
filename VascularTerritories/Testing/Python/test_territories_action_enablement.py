# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 — the Extract + Compute actions gate on real preconditions.

The panel's Extract-centerlines and Compute-territory-map actions no longer
enable on ANY input selection: each reads LIVE state so a surgeon cannot click
an action that cannot yet run (ADR-0037 §Decision 4):

* Extract centerlines: enabled iff an input segmentation is selected AND
  SlicerVMTK is present AND at least one territory has a STRUCTURE with >=2
  seeds -- i.e. something is actually extractable (the SAME per-structure
  grouping the extraction path runs on).
* Compute territory map: enabled iff an input segmentation is selected AND a
  reference volume exists AND at least one centerline has been extracted (the
  carrier's ``CenterlineRefs`` is non-empty).

This file pins:

* i1 (launched, widget) — with an input selected but no >=2-seed structure,
  Extract is DISABLED; after >=2 seeds land on a structure it ENABLES.  Compute
  is DISABLED until ``CenterlineRefs`` is non-empty (+ a reference volume);
  populated via the stub-centerline idiom from ``test_territories_map_compute``
  so no SlicerVMTK is needed.
* i2 (launched) — the shared ``territoryStructureSeedCounts`` query returns the
  per-structure counts the extraction groups on, so the enablement, the
  extractor's >=2-per-structure gate, and the table warning cannot diverge.

Both need the wrapped carrier + a live scene (and i1 also Qt), so they SKIP
cleanly bare and RUN launched (ADR-0027).  The extractable-structure check is
SlicerVMTK-independent (it is pure grouping), so i1 exercises the Extract gate
even off the VMTK image by driving ``_hasExtractableStructure`` directly for
the seed-count half while asserting the button's disabled state stands in for
"nothing extractable".

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * VascularTerritories/Testing/Python/test_territories_map_compute.py  (the
    stub-centerline CenterlineRefs idiom this file reuses)
  * VascularTerritories/Testing/Python/test_territories_seed_structure.py  (the
    per-structure grouping this query shares)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"

_VEIN_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^29092000^Vein~^^~Anatomic codes~^^~^^"
)


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


def _logic_or_skip(slicer):
    try:
        from VascularTerritories import VascularTerritoriesLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VascularTerritoriesLogic not importable ({exc!r}).")
    return VascularTerritoriesLogic()


def _make_carrier_or_skip(slicer, name="ActionEnablementCarrier"):
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


def _vessel_segmentation(slicer, center=(0.0, 0.0, 0.0), radius=20.0, name="EnablementVessel"):
    """A one-segment vascular-tagged segmentation (the extractable structure)."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(24)
    source.SetPhiResolution(24)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name + "Model")
    modelNode.SetAndObservePolyData(source.GetOutput())
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, name)
    seg.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, seg)
    slicer.mrmlScene.RemoveNode(modelNode)
    obj = seg.GetSegmentation()
    segId = obj.GetNthSegmentID(0)
    obj.GetSegment(segId).SetTag("TerminologyEntry", _VEIN_TERMINOLOGY)
    return seg, segId


# =========================================================================== #
# i2 — the shared per-structure seed-count query
# =========================================================================== #


def test_territory_structure_seed_counts_matches_grouping():
    """i2: ``territoryStructureSeedCounts`` returns the per-structure counts.

    The query groups a territory's seeds by their nearest structure exactly as
    the extraction path does, so the enablement, the extractor's
    >=2-per-structure gate, and the table warning agree (ADR-0037 slice 5).
    Two seeds on the vessel yield ``{vesselSegId: 2}``.  Launched-only; SKIPS
    bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    if not hasattr(logic, "territoryStructureSeedCounts"):
        pytest.skip(
            "VascularTerritoriesLogic has no territoryStructureSeedCounts -- "
            "the ADR-0037 slice-5 shared per-structure count query has not "
            "landed (ADR-0027)."
        )
    carrier = _make_carrier_or_skip(slicer)
    seg, segId = _vessel_segmentation(slicer)

    # Two seeds near the vessel centre so both map to the vessel structure.
    carrier.AddAnnotationPoint("T1", 0.0, 0.0, 5.0)
    carrier.AddAnnotationPoint("T1", 0.0, 0.0, -5.0)

    counts = logic.territoryStructureSeedCounts(carrier, seg, "T1")

    assert counts, "the query must return the per-structure counts, not empty."
    assert counts.get(segId) == 2, (
        f"both seeds must group onto the vessel structure {segId!r}; "
        f"got {counts!r}."
    )
    # An empty carrier / territory yields no counts.
    assert logic.territoryStructureSeedCounts(carrier, seg, "Empty") == {}, (
        "a territory with no seeds must return an empty count map."
    )


# =========================================================================== #
# i1 — the Extract / Compute enablement gates (launched, widget)
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


def _attach_stub_centerline(slicer, logic, carrier, territoryId, name="EnablementCenterline"):
    """Wire a small line model into the carrier's CenterlineRefs (no VMTK)."""
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
    role = getattr(logic, "CENTERLINE_REFERENCE_ROLE", "CenterlineRefs")
    carrier.AddNodeReferenceID(role, model.GetID())
    if hasattr(carrier, "SetGrouping"):
        carrier.SetGrouping(model.GetID(), territoryId)
    return model


def test_extract_gated_on_extractable_structure(qt_widgets):
    """i1: Extract is DISABLED without a >=2-seed structure, ENABLES with one.

    ADR-0037 §Decision 4: Extract needs SlicerVMTK AND an extractable
    >=2-seed structure.  Off the VMTK image the button stays disabled by the
    VMTK gate, so the extractable-structure half is asserted through
    ``_hasExtractableStructure`` directly (SlicerVMTK-independent -- it is pure
    grouping); the button-enabled state is asserted only when VMTK is present.
    Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "_updateActionEnablement") or not hasattr(
        widget, "_hasExtractableStructure"
    ):
        pytest.skip(
            "the ADR-0037 slice-5 action-enablement seam "
            "(_updateActionEnablement / _hasExtractableStructure) has not "
            "landed (ADR-0027)."
        )

    seg, _segId = _vessel_segmentation(slicer)
    widget.ui.inputSurfaceSelector.setCurrentNode(seg)
    carrier = widget._ensureAnnotationCarrier()

    # No seeds yet: nothing extractable, and (regardless of VMTK) the button is
    # disabled.
    widget._updateActionEnablement()
    assert widget._hasExtractableStructure(seg) is False, (
        "with no seeds there is no extractable >=2-seed structure."
    )
    assert widget.ui.addCenterlineSegmentButton.enabled is False, (
        "Extract must be DISABLED with nothing extractable (ADR-0037 §Decision 4)."
    )

    # Two seeds on the vessel -> a >=2-seed structure exists.
    carrier.AddAnnotationPoint("T1", 0.0, 0.0, 5.0)
    carrier.AddAnnotationPoint("T1", 0.0, 0.0, -5.0)
    widget._updateActionEnablement()
    assert widget._hasExtractableStructure(seg) is True, (
        "two seeds on the vessel must expose an extractable >=2-seed structure."
    )
    # The button ENABLES only when SlicerVMTK is also present; assert the
    # VMTK-independent extractable half above, and the button state under VMTK.
    if widget.logic.extractionActionEnabled():
        assert widget.ui.addCenterlineSegmentButton.enabled is True, (
            "Extract must ENABLE once something is extractable AND SlicerVMTK "
            "is present (ADR-0037 §Decision 4)."
        )


def test_compute_gated_on_centerline_and_reference_volume(qt_widgets):
    """i1: Compute is DISABLED until CenterlineRefs is non-empty (+ ref volume).

    ADR-0037 §Decision 4: Compute needs an input segmentation, a reference
    volume, and at least one extracted centerline.  The centerline is populated
    via the stub-centerline idiom (no SlicerVMTK).  Launched-only; SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "_updateActionEnablement"):
        pytest.skip(
            "the ADR-0037 slice-5 action-enablement seam has not landed "
            "(ADR-0027)."
        )

    seg, _segId = _vessel_segmentation(slicer)
    widget.ui.inputSurfaceSelector.setCurrentNode(seg)
    carrier = widget._ensureAnnotationCarrier()

    # A reference volume, but no centerline yet: Compute stays disabled.
    ref_volume = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "EnablementRefVolume")
    image = vtk.vtkImageData()
    image.SetDimensions(4, 4, 4)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    ref_volume.SetAndObserveImageData(image)

    widget._updateActionEnablement()
    assert widget.ui.calculateVascularTerritoryMapButton.enabled is False, (
        "Compute must be DISABLED with no extracted centerline (ADR-0037 "
        "§Decision 4)."
    )

    # A centerline in CenterlineRefs flips Compute on (input + volume present).
    _attach_stub_centerline(slicer, widget.logic, carrier, "T1")
    widget._updateActionEnablement()
    assert widget.ui.calculateVascularTerritoryMapButton.enabled is True, (
        "Compute must ENABLE once a centerline is extracted (CenterlineRefs "
        "non-empty), an input is selected, and a reference volume exists."
    )


# =========================================================================== #
# POST-REVIEW REFINEMENT — Extract + Compute both DISARM placement
# =========================================================================== #
#
# The reviewer's refinement (ADR-0037 §Decision 4): starting an Extract or a
# Compute ENDS the placement gesture -- the widget toggles the active Place
# button OFF via the table's shared ``disarm()`` body (which writes armed=0 onto
# the shared display node) so a stray click after the action does not drop
# another seed.  The extract path early-returns before VMTK is confirmed, so the
# disarm rides the SUCCESS path (VMTK/extractor stubbed here); the compute path
# disarms after the map run (also stubbed).  Green regression guards: RUN +
# PASS launched now.


def _import_interaction_state_or_skip():
    try:
        from VascularTerritoriesLib import TerritoryInteractionState as state
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoryInteractionState not importable ({exc!r}) (ADR-0027).")
    return state


def _arm_widget_placement_or_skip(widget, state):
    """Arm placement on the widget's shared highlight display node, or skip.

    Mirrors the table's ``_armInto``: writes armed=1 onto the shared display
    node -- the handle the placement Pipeline and the table's ``disarm()`` both
    read/write.
    """
    displayNode = getattr(widget, "_highlightDisplayNode", None)
    if displayNode is None:
        pytest.skip(
            "widget has no _highlightDisplayNode -- the shared display node the "
            "disarm writes to is unavailable (launched build; ADR-0027)."
        )
    if getattr(widget, "_territoriesTable", None) is None:
        pytest.skip(
            "widget has no _territoriesTable -- the disarm routes through the "
            "table's shared done() body (ADR-0027)."
        )
    state.set_armed(displayNode, True)
    assert state.is_armed(displayNode) is True, (
        "precondition: placement must read armed before the action disarms it."
    )
    return displayNode


def test_extract_centerlines_disarms_placement(qt_widgets, monkeypatch):
    """A successful Extract ENDS the placement gesture (disarms via the table).

    Post-review refinement (ADR-0037 §Decision 4): extracting toggles the active
    Place button off so a stray click after extraction does not drop another
    seed.  The disarm rides the SUCCESS path (the action early-returns when
    SlicerVMTK is absent), so ``extractionActionEnabled`` + ``extractCenterlines``
    + the centerline-visibility sync are stubbed -- no SlicerVMTK needed.  Pins
    the display node reading dis-armed after ``onAddCenterlineSegment()``.
    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "onAddCenterlineSegment") or not hasattr(
        widget, "_disarmPlacement"
    ):
        pytest.skip(
            "widget has no onAddCenterlineSegment / _disarmPlacement -- the "
            "ADR-0037 disarm-on-extract refinement has not landed (ADR-0027)."
        )

    state = _import_interaction_state_or_skip()
    seg, _segId = _vessel_segmentation(slicer)
    widget.ui.inputSurfaceSelector.setCurrentNode(seg)
    displayNode = _arm_widget_placement_or_skip(widget, state)

    # Stub the VMTK gate + the extraction + the visibility sync so the SUCCESS
    # path runs (and reaches the disarm) without SlicerVMTK.
    monkeypatch.setattr(widget.logic, "extractionActionEnabled", lambda: True)
    monkeypatch.setattr(
        widget.logic, "extractCenterlines", lambda carrier, surface, segId: None)
    monkeypatch.setattr(widget, "_syncCenterlineVisibility", lambda: None)

    widget.onAddCenterlineSegment()

    assert state.is_armed(displayNode) is False, (
        "a successful Extract must DISARM placement (toggle the Place button "
        "off) so a stray click adds no seed (ADR-0037 §Decision 4)."
    )


def test_compute_territory_map_disarms_placement(qt_widgets, monkeypatch):
    """A Compute ENDS the placement gesture (disarms via the table).

    Post-review refinement (ADR-0037 §Decision 4): computing the map toggles the
    active Place button off too.  ``build_centerline_model`` /
    ``ensureTerritoryMapOutput`` / ``calculateVascularTerritoryMap`` /
    ``_applyTerritoryNamesAndColors`` are stubbed so the wiring reaches the
    disarm without the real C++ map run (which stays eyeball-gated); a reference
    volume is provided so the button does not early-return.  Pins the display
    node reading dis-armed after ``onCalculateVascularTerritoryMapButton()``.
    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    for method in ("onCalculateVascularTerritoryMapButton", "_disarmPlacement",
                   "build_centerline_model"):
        target = widget if method != "build_centerline_model" else widget.logic
        if not hasattr(target, method):
            pytest.skip(
                f"{method} absent -- the ADR-0037 disarm-on-compute refinement "
                "has not landed (ADR-0027)."
            )

    state = _import_interaction_state_or_skip()
    seg, _segId = _vessel_segmentation(slicer)
    widget.ui.inputSurfaceSelector.setCurrentNode(seg)
    displayNode = _arm_widget_placement_or_skip(widget, state)

    # A reference volume so the button's refVolume guard passes.
    ref_volume = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "DisarmComputeRefVolume")
    image = vtk.vtkImageData()
    image.SetDimensions(4, 4, 4)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    ref_volume.SetAndObserveImageData(image)

    # A centerline model with >= 2 points so the numberOfPoints guard passes.
    def _stub_build(carrier, colormap):
        points = vtk.vtkPoints()
        points.InsertNextPoint(0.0, 0.0, 10.0)
        points.InsertNextPoint(0.0, 0.0, -10.0)
        poly = vtk.vtkPolyData()
        poly.SetPoints(points)
        model = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLModelNode", "DisarmComputeCenterline")
        model.SetAndObserveMesh(poly)
        return model

    monkeypatch.setattr(widget.logic, "build_centerline_model", _stub_build)
    if hasattr(widget.logic, "ensureTerritoryMapOutput"):
        target_seg = slicer.mrmlScene.AddNewNodeByClass(
            SEGMENTATION_CLASS, "DisarmComputeTarget")
        target_seg.SetAttribute("VascularTerritories.SegmentationId", "1")
        monkeypatch.setattr(
            widget.logic, "ensureTerritoryMapOutput", lambda carrier: target_seg)
    monkeypatch.setattr(
        widget.logic, "calculateVascularTerritoryMap",
        lambda target, refVolume, inputSeg, centerline, colormap: None)
    if hasattr(widget, "_applyTerritoryNamesAndColors"):
        monkeypatch.setattr(
            widget, "_applyTerritoryNamesAndColors", lambda carrier, mapSeg: None)

    widget.onCalculateVascularTerritoryMapButton()

    assert state.is_armed(displayNode) is False, (
        "a Compute must DISARM placement (toggle the Place button off) so a "
        "stray click adds no seed (ADR-0037 §Decision 4)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
