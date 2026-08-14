# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Gating truth-table for the seeds-first-class volumetry panel.

The corrected model (``Docs/design/volumetry-data-first-redesign.md`` §1/§3):
segment volumes are computed in two PEER ways -- tick segments OR place seeds
to pick regions -- and resections are an OPTIONAL refinement, never the
framing.  The seeds-without-resections path (logic B2: a seed measures the
whole segment/region it sits in) is a valid, first-class workflow.

The gates the panel enforces:

* COMPUTE VOLUMES is enabled iff a segmentation is selected AND (>= 1 segment
  is ticked OR >= 1 seed is placed).  The requirements line otherwise reads
  "Select a segmentation, then tick segments or place seeds."
* PLACE SEEDS has NO standalone button (territory-usability): placement is the
  per-volume Place toggle on a volume row.  ``placeUnmet`` still reports what
  placement needs -- a segmentation (the in-volume pick's target labelmap) and
  a volume to place into ("Add a volume to place seeds") -- feeding the
  requirements line + the tooltips, not a global button.
* REFINE BY RESECTION is purely optional: when ON it wants >= 1 resection
  checked to have effect ("Check a resection to bound the seed regions"), but
  it NEVER blocks the plain seed path.  There is NO gate that requires a
  resection to compute.
* GENERATE SEGMENTS is enabled iff >= 1 seed is placed (resections optional).

The existing ``_actionRequirements`` / ``_updateActionEnablement`` /
``_updateRequirementsMessage`` trio stays the single source of truth; only the
predicate set changes.

This file pins (mirroring the VascularTerritories requirements-surface idiom):

* i1 (launched, widget) -- with no segmentation Compute is disabled and the
  requirements line names the segmentation, and ``placeUnmet`` names the
  segmentation too; selecting a segmentation and TICKING a segment ENABLES
  Compute; selecting a segmentation alone (nothing ticked, no seed) does NOT
  enable Compute, and ``placeUnmet`` then asks for a volume to place into.
* i2 (launched, widget) -- the seeds-only (B2) path: a placed seed with NO
  resection enables Compute AND Generate.  Resections are not required.
* i3 (launched, widget) -- Refine-by-resection is optional: turning it ON with
  no resection checked names the refine requirement but does NOT disable
  Compute (the plain seed path still runs).
* i4 (launched, widget) -- Clear-all empties the carrier and re-disables.

Both need the wrapped carrier + a live scene + Qt, so they SKIP cleanly bare
and RUN launched (ADR-0027).

See also:
  * Docs/design/volumetry-data-first-redesign.md  (§1/§3 seeds-first-class)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"

_NEEDS_INPUT = "Select a segmentation, then tick segments or place seeds."
_NEEDS_SEGMENTATION = "Select a segmentation."
_NEEDS_VOLUME = "Add a volume to place seeds."
_NEEDS_RESECTION = "Check a resection to bound the seed regions."


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


def _tick_all_segments(widget, seg):
    """Tick every segment of ``seg`` on the input selector (the B1 path)."""
    segmentation = seg.GetSegmentation()
    ids = [segmentation.GetNthSegmentID(i)
           for i in range(segmentation.GetNumberOfSegments())]
    widget.ui.InputSegmentSelectorWidget.setSelectedSegmentIDs(ids)


# =========================================================================== #
# i1 -- Compute gates on a segmentation AND (a ticked segment OR a seed);
#       Place gates on a segmentation only (§3.4)
# =========================================================================== #


def test_compute_gates_on_segmentation_plus_ticked_or_seed(qt_widgets):
    """§3.4: Compute needs a segmentation AND (a ticked segment OR a seed).

    With no segmentation Compute is disabled and every action lists
    "Select a segmentation...".  There is NO standalone Place button
    (territory-usability): placement is a per-volume row control, so
    ``placeUnmet`` (feeding the requirements line, not a global button) asks
    for a segmentation first, then a volume.  Selecting a segmentation does NOT
    enable Compute (nothing ticked, no seed yet); ticking a segment then
    enables Compute.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    # The standalone Place-seeds button is retired (territory-usability):
    # placement arms per-volume from a table row, never a global toggle.
    assert not hasattr(widget.ui, "AddSeedsButton"), (
        "the standalone Place-seeds button must be removed (territory-usability)."
    )

    widget.ui.InputSegmentSelectorWidget.setCurrentNode(None)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is False, (
        "Compute must be DISABLED with no segmentation (§3.4)."
    )
    placeUnmet, computeUnmet, _generateUnmet, _refineUnmet = widget._actionRequirements()
    assert computeUnmet == [_NEEDS_INPUT], (
        "with no segmentation Compute must list ONLY the combined input "
        "requirement (tick segments or place seeds)."
    )
    assert placeUnmet == [_NEEDS_SEGMENTATION], (
        "with no segmentation placement asks for a segmentation first."
    )

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.ui.InputSegmentSelectorWidget.setSelectedSegmentIDs([])
    widget._updateActionEnablement()
    placeUnmet2, _c, _g, _r = widget._actionRequirements()
    assert placeUnmet2 == [_NEEDS_VOLUME], (
        "with a segmentation but no volume, placement asks to add a volume "
        "(no global Place button; territory-usability)."
    )
    assert widget.ui.ComputeVolumePushButton.enabled is False, (
        "Compute must stay DISABLED with a segmentation but nothing ticked "
        "and no seed placed (§3.4)."
    )

    _tick_all_segments(widget, seg)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is True, (
        "Compute must ENABLE once a segment is ticked (§3.4)."
    )
    _p2, computeUnmet2, _g2, _r2 = widget._actionRequirements()
    assert computeUnmet2 == [], (
        "with a segmentation selected and a segment ticked Compute has no "
        "unmet preconditions."
    )


# =========================================================================== #
# i2 -- the seeds-only (B2) path: a seed with NO resection enables Compute +
#       Generate (§1/§3 -- seeds are first-class, resections optional)
# =========================================================================== #


def test_seed_without_resection_enables_compute_and_generate(qt_widgets):
    """§1/§3: a placed seed alone (no resection) enables Compute AND Generate.

    Seeds are a first-class way to pick regions to measure; a seed measures
    the whole region it sits in (logic B2).  A seed with NO checked resection
    must enable BOTH Compute and Generate -- there is no resection-required
    gate.  Launched (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.ui.InputSegmentSelectorWidget.setSelectedSegmentIDs([])
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )

    # No seed yet, nothing ticked -> Compute + Generate disabled.
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is False
    assert widget.ui.GenerateSegmentsPushButton.enabled is False, (
        "Generate must be DISABLED with no seed placed (§3.4)."
    )

    # A seed alone (no checked resection) -> Compute AND Generate ENABLED.
    carrier.AddSeed(0.0, 0.0, 0.0)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is True, (
        "a seed alone (no resection) must ENABLE Compute -- the B2 seeds-only "
        "path is first-class (§1/§3)."
    )
    assert widget.ui.GenerateSegmentsPushButton.enabled is True, (
        "a seed alone (no resection) must ENABLE Generate -- resections are "
        "an optional refinement, not a precondition (§1/§3)."
    )
    _p, computeUnmet, generateUnmet, _r = widget._actionRequirements()
    assert computeUnmet == [], "a placed seed satisfies Compute's input gate."
    assert generateUnmet == [], "a placed seed satisfies Generate's gate."


# =========================================================================== #
# i3 -- Refine-by-resection is OPTIONAL: never blocks the plain seed path
# =========================================================================== #


def test_refine_by_resection_is_optional(qt_widgets):
    """§1/§3: Refine-by-resection is optional and never blocks Compute.

    Turning refine ON with NO resection checked names the refine requirement
    (so the surgeon knows a resection is wanted to have effect) but does NOT
    disable Compute -- the plain seed path still runs (logic B2).  Launched
    (widget); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)
    _require_requirements_seam_or_skip(widget)

    if not hasattr(widget.ui, "RefineByResectionCheckBox"):
        pytest.skip(
            "widget has no RefineByResectionCheckBox -- the refine sub-control "
            "has not landed (ADR-0027)."
        )

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    widget.ui.InputSegmentSelectorWidget.setSelectedSegmentIDs([])
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip(
            "seed carrier unavailable -- the ADR-0038 carrier has not landed "
            "(launched build; ADR-0027)."
        )
    carrier.AddSeed(0.0, 0.0, 0.0)

    # Refine OFF (default): no refine requirement, Compute enabled.
    widget.ui.RefineByResectionCheckBox.setChecked(False)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is True
    _p, _c, _g, refineUnmet = widget._actionRequirements()
    assert refineUnmet == [], (
        "with refine OFF there is no refine requirement (§3.4)."
    )

    # Refine ON but no resection checked: names the requirement, Compute STILL
    # enabled (the plain seed path is never blocked).
    widget.ui.RefineByResectionCheckBox.setChecked(True)
    widget._updateActionEnablement()
    assert widget.ui.ComputeVolumePushButton.enabled is True, (
        "Refine-by-resection must NEVER block the plain seed path -- Compute "
        "stays enabled with a seed placed (§1/§3)."
    )
    _p2, _c2, _g2, refineUnmet2 = widget._actionRequirements()
    assert refineUnmet2 == [_NEEDS_RESECTION], (
        "refine ON with no resection checked must name the resection "
        "requirement (§3.4)."
    )


# =========================================================================== #
# i4 -- Clear all seeds
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

    # >1 seed clears only through the confirm (destructive out of the
    # misclick path); the seam is stubbed so no modal blocks the harness.
    confirms = []

    def _fake_confirm(text):
        confirms.append(text)
        return _fake_confirm.answer

    _fake_confirm.answer = False
    widget._confirmDestructive = _fake_confirm

    widget.onClearAllSeeds()
    assert carrier.GetNumberOfSeeds() == 2, (
        "a DECLINED confirm must leave every seed in place."
    )
    assert confirms and "2" in confirms[0], (
        "the confirm must name HOW MANY seeds are about to go."
    )

    _fake_confirm.answer = True
    widget.onClearAllSeeds()
    assert carrier.GetNumberOfSeeds() == 0, (
        "Clear all seeds must remove every seed from the carrier."
    )
    assert widget.ui.ClearAllSeedsButton.enabled is False, (
        "Clear all seeds must re-disable once the carrier is empty."
    )


def test_clear_all_single_seed_stays_one_click(qt_widgets):
    """One seed clears WITHOUT a confirm (re-placement is the recovery)."""
    slicer = _slicer_or_skip()
    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not hasattr(widget, "_confirmDestructive"):
        pytest.skip("widget has no confirm seam -- has not landed (ADR-0027).")

    seg = _single_segment_segmentation(slicer)
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(seg)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None:
        pytest.skip("seed carrier unavailable (launched build; ADR-0027).")

    carrier.AddSeed(0.0, 0.0, 0.0)

    def _never_confirm(text):
        raise AssertionError("a single-seed clear must not confirm")

    widget._confirmDestructive = _never_confirm
    widget.onClearAllSeeds()

    assert carrier.GetNumberOfSeeds() == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
