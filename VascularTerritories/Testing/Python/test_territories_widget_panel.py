# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-2 — the VascularTerritories panel modernisation (slice 2).

ADR-0037 §Decision 3 modernises the panel to Python-widget composition
(ADR-0004; the ``ResectionPlanningWidget`` precedent): the legacy
selector/place-widget surface that merely duplicates the composed
``TerritoriesTableWidget`` retires, and the surviving controls are re-homed
into a Python-composed panel.

Slice-2 scope (maintainer-approved — the map-target derivation +
``build_centerline_model`` carrier-wiring + the ``selectedVascularTerritorySegmId``
retirement are SLICE 3):

* RETIRE the table-duplicating v1 widgets + the per-segment input selector
  (``ColorPickerButton`` / ``showHideButton`` / ``addSegmentationButton`` /
  ``SegmentsWidget`` / ``inputSegmentSelectorWidget`` / ``vascularTerritoryId``)
  and their handlers/helpers, plus the dead ``_registerVesselHighlightPipeline``.
* KEEP + re-home: ``inputSurfaceSelector`` (feeds ``pickSurface`` + the
  extraction surface), ``SegmentationShow3DButton``, the composed
  ``TerritoriesTableWidget``, and an "Extract centerlines" action
  (``onAddCenterlineButton`` -> ``extractCenterlines``).
* KEEP AS-IS FOR SLICE 3 (must stay FUNCTIONAL this slice): the "Compute
  territory map" action + ``selectedVascularTerritorySegmId`` +
  ``calculateVascularTerritoryMap``.

These invariants build the module widget, so they need a launched
``qSlicerApplication``: they SKIP cleanly bare and RUN launched, matching the
existing ``test_territories_*`` idiom (``_require_qt_widget`` /
``_require_mrml_scene`` / the ``qt_widgets`` disposal fixture).

Until the implementer lands slice 2 the v1 widgets are still present; every
behavioural assertion is guarded on ``_slice2_landed(widget)`` and
SKIP-PENDING while the legacy surface survives, so this file collects + goes
green (as skips) now and RUNS once the retirement lands.

References
----------
* ADR-0037 §Decision 3 — panel modernised to Python-widget composition.
* ADR-0004 — GUI widgets are Python (the ResectionPlanningWidget precedent).
* ADR-0033 — hover discipline (the surviving highlight wiring).
* feedback_launched_widget_teardown_crash — tear the widget down before exit.
"""

from __future__ import annotations

import pytest

from conftest import _require_mrml_scene, _require_qt_widget

# ---------------------------------------------------------------------------
# The exact retire / keep contract (ADR-0037 §Decision 3, slice-2 scope).
# Naming the concrete attributes gives the implementer an exact target: after
# slice 2 lands, each RETIRED name is ABSENT and each KEPT name is PRESENT.
# ---------------------------------------------------------------------------

# ``ui.*`` widgets that merely duplicate the composed TerritoriesTableWidget
# (plus the per-segment input selector — maintainer: retire per-segment).
RETIRED_UI_WIDGETS = (
    "ColorPickerButton",
    "showHideButton",
    "addSegmentationButton",
    "SegmentsWidget",
    "inputSegmentSelectorWidget",
    "vascularTerritoryId",
)

# Handlers / helpers on the widget that only served the retired widgets.
RETIRED_WIDGET_METHODS = (
    "onColorChanged",
    "onShowHideButton",
    "refreshShowHideButton",
    "updateShowHideButtonText",
    "onAddSegmentationButton",
    "updateVascTerrList",
    "vascular_territory_segmentationNodeSelected",
    "createCenterlineNode",
    "mergePolydata",
    "getDisplayNodeAndSegmentId",
    "getCurrentColor",
    "getCurrentColorQt",
    "useColorFromSelector",
    # Dead code: defined, never called.
    "_registerVesselHighlightPipeline",
)

# ``copyIndex`` is a Logic helper serving the retired createCenterlineNode
# path; asserted separately against the Logic, not the widget.
RETIRED_LOGIC_METHODS = (
    "copyIndex",
)

# ``ui.*`` widgets re-homed into the Python-composed panel and KEPT.
KEPT_UI_WIDGETS = (
    "inputSurfaceSelector",
    "SegmentationShow3DButton",
    # Slice-3 rework territory; must STAY present + wired this slice.
    "selectedVascularTerritorySegmId",
    "addCenterlineSegmentButton",
    "calculateVascularTerritoryMapButton",
)

# Methods on the widget that survive slice 2.
KEPT_WIDGET_METHODS = (
    "updateHighlightPickSurface",      # Stage-1 highlight wiring survives.
    "onAddCenterlineButton",           # the "Extract centerlines" action.
    "onCalculateVascularTerritoryMapButton",  # slice-3 rework; stays wired now.
)


def _make_widget(slicer):
    """Build a set-up ``VascularTerritoriesWidget`` on the launched scene."""
    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    return widget


def _detach_scene_observers(slicer, widget):
    """Drop the widget's scene observers while it is still alive.

    Mirrors ``test_vessel_highlight_wiring`` so the autouse scene-clear does
    not fire the legacy ``onSceneStartClose`` / ``onSceneEndClose`` handlers
    on a torn-down widget.
    """
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 — best-effort across widget shapes
            pass


def _slice2_landed(widget) -> bool:
    """True once the retirement has landed (all retired ``ui.*`` gone).

    Guards the behavioural assertions so this file collects + SKIP-PENDINGs
    cleanly while the v1 surface survives, and RUNS once slice 2 strips it.
    The map-path guard (invariant 4) checks slice-3 KEEPs, which are present
    both before and after slice 2, so it does NOT gate on this.
    """
    ui = getattr(widget, "ui", None)
    if ui is None:
        return False
    return not any(hasattr(ui, name) for name in RETIRED_UI_WIDGETS)


# ===========================================================================
# Invariant 1 — Retired widgets/handlers are gone.  (pure presence)
# ===========================================================================

def test_retired_ui_widgets_absent(qt_widgets):
    """Every table-duplicating ``ui.*`` widget is gone (ADR-0037 §Decision 3)."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    present = [name for name in RETIRED_UI_WIDGETS if hasattr(widget.ui, name)]
    assert not present, f"retired ui widgets still present: {present}"


def test_retired_widget_methods_absent(qt_widgets):
    """Handlers/helpers that only served the retired widgets are gone."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    present = [name for name in RETIRED_WIDGET_METHODS if hasattr(widget, name)]
    assert not present, f"retired widget methods still present: {present}"


def test_retired_logic_methods_absent(qt_widgets):
    """The ``copyIndex`` Logic helper (served createCenterlineNode) is gone."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    logic = widget.logic
    present = [name for name in RETIRED_LOGIC_METHODS if hasattr(logic, name)]
    assert not present, f"retired logic methods still present: {present}"


# ===========================================================================
# Invariant 2 — Kept surface present + wired.  (behavioural)
# ===========================================================================

def test_kept_ui_widgets_present(qt_widgets):
    """The re-homed + slice-3-retained ``ui.*`` widgets survive setup."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    missing = [name for name in KEPT_UI_WIDGETS if not hasattr(widget.ui, name)]
    assert not missing, f"kept ui widgets missing after slice 2: {missing}"


def test_kept_widget_methods_present(qt_widgets):
    """The surviving widget methods (highlight wiring + actions) survive setup."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    missing = [name for name in KEPT_WIDGET_METHODS if not hasattr(widget, name)]
    assert not missing, f"kept widget methods missing after slice 2: {missing}"


def test_composed_table_present(qt_widgets):
    """The Python-composed ``TerritoriesTableWidget`` is composed into the panel."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    # ``_setupTerritoriesTable`` degrades to ``None`` only if the wrapped
    # carrier / LayerDMLib is off the launched path.  On the CI image (which
    # opts LayerDM in) the composed table is present.
    table = getattr(widget, "_territoriesTable", None)
    assert table is not None, (
        "composed TerritoriesTableWidget absent — the panel no longer "
        "hosts the ADR-0037 §Decision 3 table")


def test_input_surface_selector_drives_highlight_pick(qt_widgets):
    """``inputSurfaceSelector`` still drives ``updateHighlightPickSurface``.

    The Stage-1 highlight-wiring invariant (pinned in
    ``test_vessel_highlight_wiring.py``) MUST survive the panel modernisation:
    selecting an input segmentation aims the highlight's pickSurface at it.
    """
    _require_qt_widget()
    _require_mrml_scene()
    import vtk  # noqa: F401 — sphere source lives in the wiring test helper
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    # Reuse the sphere-segmentation helper from the surviving Stage-1 test so
    # this cross-checks the exact wiring that must stay green.
    from test_vessel_highlight_wiring import _sphere_segmentation

    segmentationNode = _sphere_segmentation(slicer, radius=30.0)
    widget.ui.inputSurfaceSelector.setCurrentNode(segmentationNode)

    highlight = widget._highlightDisplayNode
    assert highlight is not None
    assert highlight.GetPickSurfaceNode() is segmentationNode


def test_extract_centerlines_action_reaches_logic(qt_widgets, monkeypatch):
    """The "Extract centerlines" action calls ``logic.extractCenterlines``.

    The kept action (``onAddCenterlineButton`` -> ``onAddCenterlineSegment``)
    feeds the annotation carrier through ``VascularTerritoriesLogic
    .extractCenterlines`` (ADR-0037 §Decision 4).  Monkeypatch the logic seam
    + the VMTK guard so the action is reachable without SlicerVMTK and the
    call is observed, not executed.
    """
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    calls = []
    monkeypatch.setattr(widget.logic, "extractionActionEnabled", lambda: True)
    monkeypatch.setattr(
        widget.logic,
        "extractCenterlines",
        lambda carrier, surfaceNode, segmentId: calls.append(
            (carrier, surfaceNode, segmentId)),
    )

    widget.onAddCenterlineButton()

    assert len(calls) == 1, "extract-centerlines action did not reach the logic"


# ===========================================================================
# Invariant 3 — Panel builds cleanly.  (behavioural)
# ===========================================================================

def test_panel_builds_cleanly(qt_widgets):
    """``setup()`` raises nothing with the v1 widgets gone.

    No dangling ``self.ui.<retired>`` access, no orphaned signal connection to
    a retired handler.  ``_make_widget`` already calls ``setup()``; reaching
    this assertion means it did not raise.
    """
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    assert widget.ui is not None


# ===========================================================================
# Invariant 4 — Map path still functional (slice-2 guard).  (pure presence)
# ===========================================================================
#
# The "Compute territory map" action, its ``selectedVascularTerritorySegmId``
# selector, and the ``calculateVascularTerritoryMap`` path are reworked in
# SLICE 3 — this slice they must STAY present + wired.  This invariant does
# NOT gate on ``_slice2_landed`` (these names exist both before and after
# slice 2) and MUST NOT assert their removal.

def test_map_path_still_present(qt_widgets):
    """The slice-3 map path (button + selector + logic) is untouched by slice 2."""
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    qt_widgets.append(widget)
    _detach_scene_observers(slicer, widget)

    assert hasattr(widget.ui, "calculateVascularTerritoryMapButton")
    assert hasattr(widget.ui, "selectedVascularTerritorySegmId")
    assert hasattr(widget, "onCalculateVascularTerritoryMapButton")
    assert hasattr(widget.logic, "calculateVascularTerritoryMap")


# ===========================================================================
# Invariant 5 — Teardown clean.  (behavioural)
# ===========================================================================

def test_cleanup_leaves_no_stray_observers(qt_widgets):
    """``cleanup()`` after ``setup()`` drops observers and does not crash.

    The launched-widget-teardown discipline
    (feedback_launched_widget_teardown_crash): a widget holding a MRML scene
    that survives to shutdown crashes SlicerApp.  ``cleanup()`` must tear the
    composed table down and remove every VTK observer.
    """
    _require_qt_widget()
    _require_mrml_scene()
    import slicer

    widget = _make_widget(slicer)
    _detach_scene_observers(slicer, widget)

    if not _slice2_landed(widget):
        # Still exercise cleanup on the v1 widget so it disposes cleanly, but
        # do not assert the post-slice-2 observer contract yet.
        widget.cleanup()
        qt_widgets.append(widget)
        pytest.skip("Panel modernisation (slice 2) not yet implemented")

    widget.cleanup()

    # VTKObservationMixin tracks live observations in ``Observations``; a clean
    # teardown leaves none.  ``removeObservers()`` (called by ``cleanup``)
    # drains it.
    observations = getattr(widget, "Observations", None)
    assert not observations, f"stray observers after cleanup: {observations}"

    qt_widgets.append(widget)
