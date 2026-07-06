# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T3-g3 -- custom-enlarge toggle for the embedded resectogram widget.

The resectogram is presented in a single ``qMRMLThreeDWidget`` embedded in the
"Resectogram" drawer (ADR-0023 §Stage-4).  Slicer's built-in double-click
maximize is NOT usable here: it realises a SECOND layout-managed widget on the
same singleton view node whose LayerDM pipeline never populates the strip (a
decisive topology probe showed the strip actors live only in the embedded
widget's renderer -- the layout-managed widget comes up blank).  So "maximize"
is implemented as a CUSTOM ENLARGE of the one working widget: a double-click
reparents that same widget into the central layout area, and a second
double-click restores it to the drawer.  Reparenting WITHIN the main window
preserves the GL context + distance-map texture (verified on :0), so no second
pipeline is created and the strip is never blank.

Pinned invariant (widget-tree state -- the GL render is the eyeball pass):

  ENLARGE/RESTORE REPARENTS THE ONE WIDGET.  ``enlargeResectogram()`` reparents
  the embedded ``qMRMLThreeDWidget`` to the layout manager's central viewport;
  ``restoreResectogram()`` reparents it back under the drawer.  Idempotent and
  toggle-symmetric: there is never a SECOND ``qMRMLThreeDWidget`` (the
  built-in-maximize failure mode this design exists to avoid), and the enlarged
  flag tracks the state.

Main-window-gated: the embedded widget only exists with a realized GL context
(the embed binds the singleton view node + uploads the distance-map texture),
so this skips cleanly under the ``--no-main-window`` launched harness and is
exercised on the interactive ``:0`` eyeball pass (#460 explicit-skip lesson).

See also:
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer" (wrapper/carrier)
  * Docs/adr/0031-distance-map-on-resection-plan-wrapper.md (distance map on the
    WRAPPER; the fixture attaches it there)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5 (no custom DM)
  * test_resectogram_open_view_action.py (the auto-populate invariants reused
    here via the shared v2-plan fixture builder)
  * test_resection_planning_widget_v2_repoint.py (the v2 re-point idioms)
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liverresections"
# #501 slice 4: the enlarge/restore invariants are node-model-agnostic (they
# assert on the embedded qMRMLThreeDWidget reparenting); only the fixture the
# combo selects changes -- the v2 plan WRAPPER (ADR-0014 §"Fourth layer").
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"
VIEW_NODE_CLASS = "vtkMRMLViewNode"
COMBO_BOX_OBJECT_NAME = "ResectionSurfaceComboBox"


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each test
# (shared shape with test_resectogram_open_view_action.py).
# --------------------------------------------------------------------------- #


def _purge_resectogram_singleton_view():
    try:
        import slicer  # type: ignore[import-not-found]
        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            RESECTOGRAM_VIEW_SINGLETON_TAG,
        )
    except Exception:  # pragma: no cover - bare-pytest / import-env dependent
        return
    scene = getattr(slicer, "mrmlScene", None)
    if scene is None:
        return

    stale_view_ids = set()
    stale_views = []
    for index in range(scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if node is not None and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            stale_views.append(node)
            stale_view_ids.add(node.GetID())
    for index in range(scene.GetNumberOfNodesByClass("vtkMRMLCameraNode")):
        camera = scene.GetNthNodeByClass(index, "vtkMRMLCameraNode")
        if camera is not None and camera.GetActiveTag() in stale_view_ids:
            scene.RemoveNode(camera)
    for node in stale_views:
        scene.RemoveNode(node)


@pytest.fixture(autouse=True)
def _drop_resectogram_singleton_view():
    _purge_resectogram_singleton_view()
    yield
    _purge_resectogram_singleton_view()


# --------------------------------------------------------------------------- #
# Skip-guards -- explicit, greppable reasons (#460 lesson).
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _require_main_window_or_skip(slicer):
    from slicer_pytest_support import require_qt_widget

    require_qt_widget()
    if slicer.util.mainWindow() is None:
        pytest.skip(
            "no main window (--no-main-window harness): the embedded "
            "qMRMLThreeDWidget (and thus the enlarge toggle) only exists with a "
            "realized GL context.  Exercised on the interactive :0 eyeball pass "
            "(ADR-0023 §Stage-4)."
        )


def _widget_or_skip(slicer):
    # Per ADR-0004 the Stage-4 GUI is Python: build the widget directly rather
    # than reaching it via the loadable module's widgetRepresentation().  The
    # C++ module is still required for the logic + MRML nodes the fixture uses.
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(f"'{MODULE_NAME}' module not registered.")
    try:
        from LiverResectionsLib.ResectionPlanningWidget import (  # type: ignore[import-not-found]
            ResectionPlanningWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "LiverResectionsLib.ResectionPlanningWidget not importable "
            f"({exc!r}) -- the ADR-0004 Python Stage-4 widget is unreachable."
        )
    widget = ResectionPlanningWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    # Parentless widget -> register for deterministic teardown so it does not
    # survive to app shutdown and crash the launched harness (see the conftest
    # autouse fixture + slicer_pytest_support.register_widget_for_teardown).
    from slicer_pytest_support import register_widget_for_teardown

    return register_widget_for_teardown(widget)


def _enlarge_api_or_skip(widget):
    """Skip unless the widget exposes the enlarge-toggle API.

    The implementer wires Q_INVOKABLE enlargeResectogram() /
    restoreResectogram() / isResectogramEnlarged() so the toggle is drivable
    without synthesising a double-click.  Skip with guidance pre-implementation.
    """
    needed = ("enlargeResectogram", "restoreResectogram", "isResectogramEnlarged")
    if not all(callable(getattr(widget, name, None)) for name in needed):
        pytest.skip(
            "enlarge-toggle API not found on the widget: expected Q_INVOKABLE "
            f"{needed} (ADR-0023 §Stage-4 custom-enlarge).  Skip lifts when the "
            "implementer wires them."
        )


def _select(widget, slicer, plan):
    setter = getattr(widget, "setActiveResectionNode", None)
    if callable(setter):
        setter(plan)
        return True
    import qt  # type: ignore[import-not-found]

    combo = widget.findChild(qt.QWidget, COMBO_BOX_OBJECT_NAME)
    if combo is not None and hasattr(combo, "setCurrentNode"):
        combo.setCurrentNode(plan)
        return True
    return False


def _make_surface_with_distance_map(slicer):
    """Mint a v2 resection plan WITH a distance map on the WRAPPER (ADR-0031).

    #501 slice 4: builds the wrapper via the logic create-API
    (``CreateResectionPlan``, #501 slice 1) and attaches the distance map on the
    WRAPPER; skips cleanly (never fails) when the create-API / node API is
    absent, mirroring ``test_resection_planning_widget_v2_repoint._make_plan_or_skip``.
    Returns the ``vtkMRMLResectionPlanNode`` wrapper.
    """
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(f"'{MODULE_NAME}' module not registered.")
    logic = module.logic()
    if logic is None or not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "create-API (#501 slice 1) is not in this build."
        )
    plan = logic.CreateResectionPlan("EnlargeTogglePlan")
    if plan is None or not plan.IsA(PLAN_NODE_CLASS):
        pytest.skip(
            "CreateResectionPlan did not return a vtkMRMLResectionPlanNode -- "
            "cannot exercise the #501 slice-4 re-point."
        )
    if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode") or not hasattr(
        plan, "GetDistanceMapVolumeNode"
    ):
        pytest.skip(
            f"{PLAN_NODE_CLASS} has no distance-map-on-wrapper API (ADR-0031) -- "
            "cannot make the plan populate-ready."
        )
    volume = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "EnlargeTogglePlanDistanceMap"
    )
    if volume is None:
        pytest.skip(
            "vtkMRMLScalarVolumeNode not registered -- cannot attach a distance "
            "map on the wrapper."
        )
    plan.SetAndObserveDistanceMapVolumeNode(volume)
    if plan.GetDistanceMapVolumeNode() is None:
        pytest.skip(
            "distance map did not attach to the wrapper -- cannot exercise the "
            "positive auto-populate branch (ADR-0031)."
        )
    return plan


def _embedded_three_d_widgets(slicer, widget):
    """Every embedded qMRMLThreeDWidget owned by the module widget subtree.

    Once enlarged the widget reparents OUT of the module-panel subtree, so also
    look it up by objectName across the app to catch the enlarged case.
    """
    import qt  # type: ignore[import-not-found]

    found = {
        id(c): c
        for c in widget.findChildren(slicer.qMRMLThreeDWidget)
        if isinstance(c, qt.QWidget)
    }
    # Also any app-wide qMRMLThreeDWidget named like the embedded one (enlarged).
    for top in slicer.app.topLevelWidgets():
        for c in top.findChildren(slicer.qMRMLThreeDWidget):
            if c.objectName == "ResectogramThreeDWidget":
                found[id(c)] = c
    return list(found.values())


def _setup_populated(slicer):
    _require_main_window_or_skip(slicer)
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    rep = widget
    self = rep.self() if hasattr(rep, "self") else rep
    _enlarge_api_or_skip(self)
    plan = _make_surface_with_distance_map(slicer)
    if not _select(self, slicer, plan):
        pytest.skip("cannot select the active resection (implementer contract).")
    # Drawer must have populated the embedded widget.
    embedded = _embedded_three_d_widgets(slicer, rep)
    if len(embedded) != 1:
        pytest.skip(
            f"expected exactly one embedded qMRMLThreeDWidget after populate, "
            f"got {len(embedded)} -- auto-populate not wired (covered elsewhere)."
        )
    return self, rep, embedded[0]


# --------------------------------------------------------------------------- #
# Invariant -- enlarge/restore reparents the ONE widget, never a second.
# --------------------------------------------------------------------------- #


def test_enlarge_reparents_embedded_widget_to_central_viewport():
    """``enlargeResectogram()`` moves the embedded widget into the central area.

    The widget's parent becomes the layout manager's central viewport (the
    region built-in maximize would fill), and it is no longer a child of the
    drawer.  Crucially there is STILL exactly one qMRMLThreeDWidget -- the
    enlarge reuses the working widget rather than realising a blank second one
    (the built-in-maximize failure mode; ADR-0023 §Stage-4).
    """
    slicer = _slicer_or_skip()
    self, rep, embedded = _setup_populated(slicer)

    self.enlargeResectogram()
    slicer.app.processEvents()

    assert self.isResectogramEnlarged(), (
        "isResectogramEnlarged() must report True after enlargeResectogram()."
    )
    viewport = slicer.app.layoutManager().viewport()
    assert embedded.parent() is viewport, (
        "enlargeResectogram() must reparent the embedded qMRMLThreeDWidget to "
        "the layout manager's central viewport (so the one working widget fills "
        "the central area) -- ADR-0023 §Stage-4 custom-enlarge."
    )
    assert len(_embedded_three_d_widgets(slicer, rep)) == 1, (
        "enlarging must NOT create a second qMRMLThreeDWidget -- the whole point "
        "of the custom-enlarge is to reuse the one populated widget rather than "
        "let built-in maximize realise a blank second one (ADR-0023 §Stage-4)."
    )


def test_restore_reparents_embedded_widget_back_to_drawer():
    """``restoreResectogram()`` returns the widget under the drawer.

    Toggle-symmetric with enlarge: after restore the widget is a descendant of
    the resectogram drawer again, the enlarged flag is False, and there is still
    exactly one qMRMLThreeDWidget (ADR-0023 §Stage-4).
    """
    slicer = _slicer_or_skip()
    self, rep, embedded = _setup_populated(slicer)

    self.enlargeResectogram()
    slicer.app.processEvents()
    self.restoreResectogram()
    slicer.app.processEvents()

    assert not self.isResectogramEnlarged(), (
        "isResectogramEnlarged() must report False after restoreResectogram()."
    )
    drawer = self.resectogramDrawer() if hasattr(self, "resectogramDrawer") else None
    if drawer is not None:
        # The widget must be back inside the drawer subtree.
        assert embedded in drawer.findChildren(slicer.qMRMLThreeDWidget), (
            "restoreResectogram() must reparent the embedded qMRMLThreeDWidget "
            "back under the resectogram drawer -- ADR-0023 §Stage-4."
        )
    assert len(_embedded_three_d_widgets(slicer, rep)) == 1, (
        "restoring must keep exactly one qMRMLThreeDWidget (ADR-0023 §Stage-4)."
    )


def test_enlarge_toggle_is_idempotent_and_symmetric():
    """Repeated enlarge/restore never accumulates widgets or desyncs the flag.

    Calling enlarge twice stays enlarged with one widget; calling restore twice
    stays restored with one widget -- the toggle is idempotent at each pole
    (ADR-0023 §Stage-4).
    """
    slicer = _slicer_or_skip()
    self, rep, _embedded = _setup_populated(slicer)

    self.enlargeResectogram()
    self.enlargeResectogram()  # idempotent
    slicer.app.processEvents()
    assert self.isResectogramEnlarged()
    assert len(_embedded_three_d_widgets(slicer, rep)) == 1

    self.restoreResectogram()
    self.restoreResectogram()  # idempotent
    slicer.app.processEvents()
    assert not self.isResectogramEnlarged()
    assert len(_embedded_three_d_widgets(slicer, rep)) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
