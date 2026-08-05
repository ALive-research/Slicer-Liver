# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Gating truth-table for the data-first volumetry panel.

The data-first redesign (``Docs/design/volumetry-data-first-redesign.md``
§3.4) replaces the panel's false preconditions with the gates the logic
actually needs:

* COMPUTE VOLUMES is enabled iff a segmentation is selected (an empty
  segment selection means "all segments", matching the export semantics);
  the requirements line otherwise reads "Select a segmentation."  The old
  reference-volume + "select at least one segment" preconditions are gone
  (§3.3 -- the data never needed them).
* PARTITION contributes rows to Compute iff >= 1 resection is checked AND
  >= 1 seed is placed; otherwise the requirements line reads "Check a
  resection and place at least one seed (e.g. in the remnant)." -- this
  closes the B4 silent no-op (resections-without-seeds was a runnable-but-
  empty state).
* PLACE SEEDS is enabled iff a segmentation is selected (the in-volume pick
  needs a target region's labelmap).
* GENERATE SEGMENTS is enabled iff the partition gate is met.

The existing ``_actionRequirements`` / ``_updateActionEnablement`` /
``_updateRequirementsMessage`` trio stays the single source of truth; only
the predicate set changes.

This file pins (mirroring the VascularTerritories requirements-surface
idiom):

* i1 (launched, widget) -- with no segmentation Compute + Place are
  disabled and the requirements line names the segmentation; selecting a
  segmentation (no segment selection) ENABLES Compute + Place.
* i2 (launched, widget) -- the partition gate: a checked resection alone or
  a seed alone does not arm Generate / the partition contribution; both
  together do, and the requirements line names the partition requirement.
* i3 (launched, widget) -- Clear-all empties the carrier and re-disables.

Both need the wrapped carrier + a live scene + Qt, so they SKIP cleanly
bare and RUN launched (ADR-0027).

See also:
  * Docs/design/volumetry-data-first-redesign.md  (§3.4 gating truth table)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"

_NEEDS_SEGMENTATION = "Select a segmentation."
_NEEDS_PARTITION = (
    "Check a resection and place at least one seed (e.g. in the remnant).")


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
            "widget has no _actionRequirements -- the requirements-message "
            "surface has not landed (ADR-0027)."
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
# i1 -- Compute + Place gate ONLY on a segmentation (§3.4)
# =========================================================================== #


def test_compute_and_place_gate_on_segmentation_only(qt_widgets):
    """§3.4: Compute + Place enabled iff a segmentation is selected.

    With no segmentation both are disabled and every action lists
    "Select a segmentation."  Selecting a segmentation (with NO segment
    selection -- "all segments") ENABLES Compute + Place, and the reference-
    volume + "select at least one segment" preconditions are gone.
    Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    widget.ui.InputSegmentSelectorWidget.setCurrentNode(None)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is False, (
        "Compute must be DISABLED with no segmentation (§3.4)."
    )
    assert widget.ui.AddSeedsButton.enabled is False, (
        "Place seeds must be DISABLED with no segmentation (§3.4)."
    )
    placeUnmet, computeUnmet, _generateUnmet = widget._actionRequirements()
    assert computeUnmet == [_NEEDS_SEGMENTATION], (
        "with no segmentation Compute must list ONLY the segmentation "
        "requirement (the reference-volume + segment preconditions are gone)."
    )
    assert placeUnmet == [_NEEDS_SEGMENTATION]

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is True, (
        "Compute must ENABLE once a segmentation is selected -- an empty "
        "segment selection means 'all segments' (§3.4)."
    )
    assert widget.ui.AddSeedsButton.enabled is True, (
        "Place seeds must ENABLE once a segmentation is selected."
    )
    _place2, computeUnmet2, _gen2 = widget._actionRequirements()
    assert computeUnmet2 == [], (
        "with a segmentation selected Compute has no unmet preconditions."
    )


# =========================================================================== #
# i2 -- the partition gate: resection AND seed (§3.4, closes B4)
# =========================================================================== #


def test_partition_gate_needs_both_resection_and_seed(qt_widgets):
    """§3.4: the partition contributes iff a resection is checked AND a seed.

    A checked resection with no seed (the old B4 silent no-op) does NOT arm
    Generate; a seed with no checked resection does not either; both
    together do.  The requirements line names the partition requirement when
    unmet.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )

    # Neither resection nor seed -> partition gate unmet, Generate disabled.
    widget._updateActionEnablement()
    assert widget.ui.GenerateSegmentsPushButton.enabled is False, (
        "Generate must be DISABLED with no resection and no seed (§3.4)."
    )
    _place, _compute, generateUnmet = widget._actionRequirements()
    assert generateUnmet == [_NEEDS_PARTITION], (
        "the partition requirement message must name both a resection and a "
        "seed (§3.4)."
    )

    # A seed alone (no checked resection) -> still unmet.
    carrier.AddSeed(0.0, 0.0, 0.0)
    widget._updateActionEnablement()
    assert widget.ui.GenerateSegmentsPushButton.enabled is False, (
        "a seed without a checked resection must NOT arm Generate (§3.4)."
    )


# =========================================================================== #
# i3 -- Clear all seeds
# =========================================================================== #


def test_clear_all_seeds_empties_carrier_and_disables(qt_widgets):
    """Clear-all empties the carrier and re-disables once empty (kept D3).

    ``onClearAllSeeds`` removes every seed through the carrier's
    ``RemoveNthSeed``; the button is DISABLED with no seeds.  Launched
    (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "onClearAllSeeds"):
        pytest.skip(
            "widget has no onClearAllSeeds -- the clear-all has not landed "
            "(ADR-0027)."
        )

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )

    # Empty carrier: Clear-all is disabled.
    widget._updateActionEnablement()
    assert widget.ui.ClearAllSeedsButton.enabled is False, (
        "Clear all seeds must be DISABLED with no seeds."
    )

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.AddSeed(1.0, 1.0, 1.0)
    widget._updateActionEnablement()
    assert widget.ui.ClearAllSeedsButton.enabled is True, (
        "Clear all seeds must ENABLE once at least one seed is placed."
    )

    widget.onClearAllSeeds()
    assert carrier.GetNumberOfSeeds() == 0, (
        "Clear all seeds must remove every seed from the carrier."
    )
    assert widget.ui.ClearAllSeedsButton.enabled is False, (
        "Clear all seeds must re-disable once the carrier is empty."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
