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
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5 (no custom DM)
  * test_resectogram_open_view_action.py (the auto-populate invariants reused
    here via the shared scenario builder)
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liverresections"
BEZIER_SURFACE_CLASS = "vtkMRMLMarkupsBezierSurfaceNode"
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


def _select(widget, slicer, bezier):
    setter = getattr(widget, "setActiveResectionNode", None)
    if callable(setter):
        setter(bezier)
        return True
    import qt  # type: ignore[import-not-found]

    combo = widget.findChild(qt.QWidget, COMBO_BOX_OBJECT_NAME)
    if combo is not None and hasattr(combo, "setCurrentNode"):
        combo.setCurrentNode(bezier)
        return True
    return False


def _make_surface_with_distance_map(slicer):
    from scenarios import Resectogram4x4BlurOff as scn  # type: ignore[import-not-found]

    slicer.modules.liverresections.logic()
    distance_map = scn._make_parenchyma_distance_map(
        sphere_center=scn.SPHERE_CENTER,
        sphere_radius=scn.SPHERE_RADIUS,
    )
    return scn._build_resectogram_bezier(
        half_extent_u=scn.PATCH_HALF_EXTENT_U,
        half_extent_v=scn.PATCH_HALF_EXTENT_V,
        enable_flexible_boundary=scn.ENABLE_FLEXIBLE_BOUNDARY,
        distance_map=distance_map,
    )


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
    bezier = _make_surface_with_distance_map(slicer)
    if not _select(self, slicer, bezier):
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
