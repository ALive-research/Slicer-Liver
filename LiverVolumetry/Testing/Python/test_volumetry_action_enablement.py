# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""D1/D2/D3 (volumetry-workflow-consistency critique) -- the action surface.

The LiverVolumetry panel gains the VascularTerritories affirmative
"what's missing" surface + the flat-list Clear-all, so it feels like the
sibling module and Slicer Segmentations (critique §4 "ship now" batch):

* D1 REQUIREMENTS MESSAGE -- an always-visible status line + per-button
  tooltips enumerate the UNMET preconditions.  The list reads the SAME live
  state the enablement gates read, so the messaging and the button state cannot
  diverge (an empty unmet list == the action can run).  With no input the list
  names "Select an input segmentation"; with no seeds Generate names
  "Place at least one seed".
* D2 PLACE-SEEDS GATE -- the Place-seeds arm toggle is DISABLED until an input
  segmentation is selected (the fix for the placement silent-decline: with no
  input the in-volume pick has no labelmap to resolve, so arming would accept
  clicks that never land a seed).
* D3 CLEAR-ALL -- "Clear all seeds" empties the carrier (whole-group delete via
  the carrier's ``RemoveNthSeed``) and is DISABLED when the carrier is empty.

This file pins (mirroring
``VascularTerritories/Testing/Python/test_territories_action_enablement.py``):

* i1 (launched, widget) -- with no input selected both Compute + Generate list
  the input requirement and the Place-seeds toggle is disabled; selecting an
  input enables the toggle; Generate still lists "Place at least one seed".
* i2 (launched, widget) -- Clear-all empties the carrier and re-disables once it
  is empty; the requirements line + Generate track the seed count.

Both need the wrapped carrier + a live scene + Qt, so they SKIP cleanly bare
and RUN launched (ADR-0027).

See also:
  * Docs/design/volumetry-workflow-consistency-critique.md  (D1/D2/D3)
  * VascularTerritories/Testing/Python/test_territories_action_enablement.py
    (the requirements-surface idiom this mirrors)
  * Docs/adr/0038-*.md  (the seeds-off-markups migration + carrier)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_widget_or_skip(slicer):
    from conftest import _require_qt_widget

    _require_qt_widget()
    from LiverVolumetry import LiverVolumetryWidget

    widget = LiverVolumetryWidget()
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


def _require_requirements_seam_or_skip(widget):
    if not hasattr(widget, "_actionRequirements"):
        pytest.skip(
            "widget has no _actionRequirements -- the critique D1 requirements-"
            "message surface has not landed (ADR-0027)."
        )


def _single_segment_segmentation(slicer, name="EnablementLiver"):
    """A one-segment segmentation (the volumetry input region)."""
    source = vtk.vtkSphereSource()
    source.SetRadius(20.0)
    source.SetThetaResolution(16)
    source.SetPhiResolution(16)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name + "Model")
    modelNode.SetAndObservePolyData(source.GetOutput())
    seg = slicer.mrmlScene.AddNewNodeByClass(SEGMENTATION_CLASS, name)
    seg.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, seg)
    slicer.mrmlScene.RemoveNode(modelNode)
    return seg


# =========================================================================== #
# D1/D2 -- the requirements message + the Place-seeds input gate
# =========================================================================== #


def test_place_seeds_disabled_until_input_segmentation(qt_widgets):
    """D2: the Place-seeds toggle is DISABLED until an input segmentation.

    With no input the in-volume pick has no target region, so arming would
    silently decline every click; the toggle stays disabled and the
    requirements line names the input.  Selecting an input enables the toggle.
    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    widget.ui.InputSegmentationSelector.setCurrentNode(None)
    widget._updateActionEnablement()
    assert widget.ui.AddSeedsButton.enabled is False, (
        "Place seeds must be DISABLED with no input segmentation (critique D2)."
    )

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentationSelector.setCurrentNode(seg)
    widget._updateActionEnablement()
    assert widget.ui.AddSeedsButton.enabled is True, (
        "Place seeds must ENABLE once an input segmentation is selected."
    )


def test_requirements_message_lists_missing_input(qt_widgets):
    """D1: with NO input, every action lists "Select an input segmentation".

    The unmet-precondition list drives the messaging: a fresh widget with no
    input, no reference volume, no segment, and no seeds lists the input
    requirement for Place / Compute / Generate.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    widget.ui.InputSegmentationSelector.setCurrentNode(None)
    placeUnmet, computeUnmet, generateUnmet = widget._actionRequirements()

    assert "Select an input segmentation" in placeUnmet, (
        "with no input, Place seeds must list the input requirement."
    )
    assert "Select an input segmentation" in computeUnmet, (
        "with no input, Compute must list the input requirement."
    )
    assert "Select an input segmentation" in generateUnmet, (
        "with no input, Generate must list the input requirement."
    )
    assert "Select a reference volume" in computeUnmet, (
        "with no reference volume, Compute must list the volume requirement."
    )


def test_requirements_message_lists_missing_seeds(qt_widgets):
    """D1: with an input but no seeds, Generate lists "Place at least one seed".

    Generate needs a reference volume + input + segment + >= 1 seed; with a
    carrier holding zero seeds the seed requirement is present and clears once a
    seed lands.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentationSelector.setCurrentNode(seg)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )

    _place, _compute, generateUnmet = widget._actionRequirements()
    assert "Place at least one seed" in generateUnmet, (
        "with no seeds, Generate must list the seed requirement (critique D1)."
    )

    carrier.AddSeed(0.0, 0.0, 0.0)
    _place2, _compute2, generateUnmet2 = widget._actionRequirements()
    assert "Place at least one seed" not in generateUnmet2, (
        "once a seed lands the seed requirement must clear."
    )


# =========================================================================== #
# D3 -- Clear all seeds
# =========================================================================== #


def test_clear_all_seeds_empties_carrier_and_disables(qt_widgets):
    """D3: Clear-all empties the carrier and re-disables once empty.

    ``onClearAllSeeds`` removes every seed through the carrier's ``RemoveNthSeed``
    (the whole-group analogue of the territory Remove), so the table + pipeline
    refresh via the carrier ModifiedEvent; the button is DISABLED with no seeds.
    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "onClearAllSeeds"):
        pytest.skip(
            "widget has no onClearAllSeeds -- the critique D3 clear-all has not "
            "landed (ADR-0027)."
        )

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentationSelector.setCurrentNode(seg)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )

    # Empty carrier: Clear-all is disabled.
    widget._updateActionEnablement()
    assert widget.ui.ClearAllSeedsButton.enabled is False, (
        "Clear all seeds must be DISABLED with no seeds (critique D3)."
    )

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.AddSeed(1.0, 1.0, 1.0)
    widget._updateActionEnablement()
    assert widget.ui.ClearAllSeedsButton.enabled is True, (
        "Clear all seeds must ENABLE once at least one seed is placed."
    )

    widget.onClearAllSeeds()
    assert carrier.GetNumberOfSeeds() == 0, (
        "Clear all seeds must remove every seed from the carrier (critique D3)."
    )
    assert widget.ui.ClearAllSeedsButton.enabled is False, (
        "Clear all seeds must re-disable once the carrier is empty."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
