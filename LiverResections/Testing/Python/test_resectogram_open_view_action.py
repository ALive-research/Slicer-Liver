# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T3-g3 -- auto-populated resectogram drawer on the LiverResections widget.

LiverResections is a loadable (C++) module that, until T3-g3, shipped NO widget
representation (``qSlicerLiverResectionsModule::createWidgetRepresentation()``
returned ``nullptr``).  T3-g3 adds the module's FIRST GUI -- the ADR-0023
§Stage-4 "Resection Planning" surface that ``Liver/Liver.py`` composes via
``LiverResections.widgetRepresentation()`` -- carrying:

  * a ``qMRMLNodeComboBox`` of ``vtkMRMLMarkupsBezierSurfaceNode`` (the node
    the merged resectogram render stack reads -- NOT the
    ``vtkMRMLBezierSurfaceNode`` carrier) that selects the *active* resection,
    and
  * a collapsible "Resectogram" drawer that AUTO-POPULATES (no click) when the
    selected surface carries a distance map, and shows an explanatory HINT
    otherwise.

The TRIGGER is the SELECTION: setting the combo box to a valid surface (no
explicit [Open] button; the maintainer removed it -- the drawer auto-populates
on selection AND when a distance map appears on the already-selected surface).

Three pinned invariants (all MRML/widget-state -- GPU-free, runnable in a
minimal ``qSlicerApplication`` without a GL view; the strip RENDERING is out
of g3 scope and is the orchestrator's eyeball pass, not asserted here):

  1. AUTO-POPULATE PREDICATE (the load-bearing invariant).  The drawer
     populates iff a Bezier surface is selected AND
     ``selectedNode->GetDistanceMapVolumeNode() != nullptr``
     (vtkMRMLMarkupsBezierSurfaceNode.h line 91).  Otherwise the drawer shows a
     non-empty HINT instead of the view (ADR-0009 §explainable state).
     STATE-ORTHOGONAL: the predicate does NOT read the ADR-0019 ResectionState
     -- a Planning *or* Confirmed surface with a distance map populates.

  2. SINGLE DISPLAY NODE ON SELECTION.  Selecting a valid surface ensures
     EXACTLY ONE ``vtkMRMLResectogramDisplayNode`` on it
     (``AddAndObserveDisplayNodeID`` when none present); re-selecting reuses it
     (idempotent -- no second display node).  This is net-new production
     behaviour: today only the ``Resectogram4x4BlurOff`` scenario builder
     attaches the display node
     (scenarios/Resectogram4x4BlurOff.py ``_attach_resectogram_display_node``).

  3. VIEW-NODE IDEMPOTENCY.  Selecting a valid surface ensures the singleton
     resectogram view node via ``ResectogramViewManager.ensureViewNode()``
     (LiverResectionsLib/ResectogramViewManager.py); re-selecting reuses it
     -- no second ``vtkMRMLViewNode`` carrying RESECTOGRAM_VIEW_SINGLETON_TAG.

The widget adds ONLY a display node + a view node + leans on the already-
registered ResectogramPipeline creator: NO custom DisplayableManager
(ADR-0013 §5; the ``feedback_layerdm_no_custom_dm`` lesson).  Binding the
singleton view node into the drawer's embedded qMRMLThreeDWidget is gated on a
realized GL context; the headless invariants stop at
"display node ensured + view node ensured + hint vs view".

-- WHY THIS IS A LAUNCHED-SLICER PYTEST (NOT A ctkTest) --

A C++ ctkTest against the widget cannot COMPILE before the widget class
exists, which would break the build during the RED phase.  A Python launched
test instead SKIPS CLEANLY (no widget rep / no accessor / module not
registered) pre-implementation and goes GREEN post -- the ADR-0027
§Conformance "for skipped tests, the skip lifts at the implementation commit"
shape.  A C++ generic widget test may accompany the IMPLEMENTATION later.

Reaching the GUI: the Stage-4 panel is a Python widget per ADR-0004 -- the
tests build ``LiverResectionsLib.ResectionPlanningWidget`` directly and call
``setMRMLScene`` (the loadable module's ``createWidgetRepresentation()`` returns
nullptr; ``Liver/Liver.py`` composes the Python widget for stage 3).  The combo
box + drawer + hint are located by objectName (see the implementer contract
below); a thin Python-accessible helper API is preferred where direct
child-finding is brittle.

Dual harness (ADR-0008 §1, §6): runs meaningfully under the launched-Slicer
``pytest_launched`` row (Liver/Testing/Python/run_pytest_launched.py; this
dir is already on its test roots) and SKIPS CLEANLY under bare
``PythonSlicer -m pytest`` via the shared guards.  Every skip prints an
explicit, greppable reason -- never silently green (the #460 launched-harness
lesson).  The ``_launched_scene_cleanup`` fixture in this dir's conftest tears
down minted nodes so the launched harness does not trip ``vtkDebugLeaks``.

-- IMPLEMENTER CONTRACT (assumed objectNames + entry points) --

  * ``LiverResectionsLib.ResectionPlanningWidget`` -- the Python Stage-4 widget
    (ADR-0004); composed by ``Liver/Liver.py`` for stage 3.
  * objectName ``"ResectionSurfaceComboBox"`` -- the
    ``qMRMLNodeComboBox`` of ``vtkMRMLMarkupsBezierSurfaceNode`` selecting the
    active resection.
  * objectName ``"ResectogramDrawer"`` -- the collapsible "Resectogram" drawer
    that auto-populates with the embedded view (or shows the hint).
  * objectName ``"ResectogramHintLabel"`` -- the hint shown in the drawer when
    no valid resectogram is available (ADR-0009 §"explainable state").  Its
    text is non-empty and it is VISIBLE iff the drawer is NOT populated.
  * Selecting a valid surface (combo ``setCurrentNode``) is the TRIGGER: it
    keys the display-node-ensure entry point on the selected
    ``vtkMRMLMarkupsBezierSurfaceNode`` and calls
    ``ResectogramViewManager.ensureViewNode()`` once.

If the implementer cannot expose stable objectNames, a thin Python-accessible
API on the widget (e.g. ``widget.setActiveResectionNode(node)`` /
``widget.resectogramDrawer()`` / ``widget.resectogramHintLabel()``) satisfies
the same invariants -- the helpers below probe both shapes and skip with
explicit guidance if neither is present.

See also:
  * Docs/adr/0027-invariant-test-first-v2-implementation.md (red->green)
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4 (the GUI surface)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5 (no custom DM)
  * Docs/adr/0009-ux-and-design-discipline.md (explainable state)
  * LiverMarkups/MRML/vtkMRMLMarkupsBezierSurfaceNode.h line 91
    (GetDistanceMapVolumeNode)
  * LiverResections/LiverResectionsLib/ResectogramViewManager.py
    (ensureViewNode singleton-by-tag)
  * LiverResections/Testing/Python/scenarios/Resectogram4x4BlurOff.py
    (surface-with-distance-map fixture builders reused below)
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liverresections"
BEZIER_SURFACE_CLASS = "vtkMRMLMarkupsBezierSurfaceNode"
RESECTOGRAM_DISPLAY_CLASS = "vtkMRMLResectogramDisplayNode"
VIEW_NODE_CLASS = "vtkMRMLViewNode"

# Implementer-contract objectNames (see module docstring).  The pinned
# invariant is the auto-populate behaviour, not the spelling -- if these
# change, the helpers below skip with explicit guidance rather than silently
# passing.
COMBO_BOX_OBJECT_NAME = "ResectionSurfaceComboBox"
DRAWER_OBJECT_NAME = "ResectogramDrawer"
HINT_LABEL_OBJECT_NAME = "ResectogramHintLabel"


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each test.
# --------------------------------------------------------------------------- #


def _purge_resectogram_singleton_view():
    """Remove the resectogram singleton view node AND its auto-created camera.

    No-op under bare pytest (no ``slicer``) or before the manager is
    importable.

    Beyond the singleton VIEW node: ``GetViewActiveCameraNode(view)`` (the
    cameras-logic accessor the framing path calls) AUTO-CREATES a
    ``vtkMRMLCameraNode`` whose ``ActiveTag`` is the resectogram view, and that
    camera node SURVIVES ``vtkMRMLScene.Clear(0)`` (the cameras logic re-pairs
    it with the surviving singleton view).  Left behind it trips this
    directory's ``_launched_scene_cleanup`` leak-check and pollutes a
    ``count == 0`` precondition -- so reclaim the paired camera node here too,
    BEFORE the view node it points at, so ``-k presentation`` alone does not
    ERROR on a leaked camera.
    """
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

    stale_views = []
    stale_view_ids = set()
    total = scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)
    for index in range(total):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if (
            node is not None
            and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG
        ):
            stale_views.append(node)
            stale_view_ids.add(node.GetID())

    # Reclaim any camera node paired (ActiveTag) with a resectogram view first,
    # so removing the view does not leave an orphan camera the cameras logic
    # re-pairs with the surviving singleton.
    camera_total = scene.GetNumberOfNodesByClass("vtkMRMLCameraNode")
    stale_cameras = []
    for index in range(camera_total):
        camera = scene.GetNthNodeByClass(index, "vtkMRMLCameraNode")
        if camera is not None and camera.GetActiveTag() in stale_view_ids:
            stale_cameras.append(camera)
    for camera in stale_cameras:
        scene.RemoveNode(camera)

    for node in stale_views:
        scene.RemoveNode(node)


@pytest.fixture(autouse=True)
def _drop_resectogram_singleton_view():
    """Reclaim the resectogram singleton view node around each test.

    ``ResectogramViewManager.ensureViewNode()`` mints a ``vtkMRMLViewNode``
    carrying a MRML ``SingletonTag``, which by design SURVIVES
    ``vtkMRMLScene.Clear(0)``.  Left in place it (a) trips this directory's
    ``_launched_scene_cleanup`` leak-check (``remaining <= baseline``) and
    (b) pollutes a ``count == 0`` precondition.  Worse, a sibling test FILE
    (the ``Testing/Python`` arena, which has no leak-check) can leak the same
    singleton into the FIRST test here.  So purge it BOTH before the test (to
    defend the precondition against an upstream leak) AND after (so this file
    never leaks onward).  Module-local + function-scoped, so it brackets the
    test inside the broader conftest cleanup.  No-op under bare pytest.
    """
    _purge_resectogram_singleton_view()
    yield
    _purge_resectogram_singleton_view()


# --------------------------------------------------------------------------- #
# Skip-guards -- every path prints an explicit, greppable reason (#460 lesson).
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    """Resolve a launched ``slicer`` with a scene, or skip cleanly.

    Import the guards from ``slicer_pytest_support`` directly, NOT
    ``from conftest import``: when the launched harness passes several test
    roots, ``conftest`` resolves to whichever sibling conftest is first on the
    path (the cross-module ``Testing/Python`` one, which exports the unprefixed
    names), not this directory's.  The sibling LiverResections tests import the
    canonical bodies the same way for this reason.
    """
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _module_or_skip(slicer):
    """Skip unless the LiverResections loadable module is registered."""
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- the T3-g3 widget "
            "surface (ADR-0023 §Stage-4) is unreachable in this environment."
        )
    return module


def _widget_or_skip(slicer):
    """Construct the Python ResectionPlanningWidget, or skip cleanly.

    Per ADR-0004 the Stage-4 GUI is Python: the widget is built directly
    (``ResectionPlanningWidget(); setMRMLScene(slicer.mrmlScene)``) rather than
    reached via the loadable module's ``widgetRepresentation()`` (which now
    returns ``nullptr`` again).  Skips cleanly when the lib is not importable
    (e.g. a build without the LiverResectionsLib scripted package).
    """
    from slicer_pytest_support import require_qt_widget

    require_qt_widget()
    # The C++ loadable module still hosts the logic + MRML nodes; require it so
    # the gate-satisfied fixture builders (which call
    # ``slicer.modules.liverresections.logic()``) work.
    _module_or_skip(slicer)
    try:
        from LiverResectionsLib.ResectionPlanningWidget import (  # type: ignore[import-not-found]
            ResectionPlanningWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "LiverResectionsLib.ResectionPlanningWidget not importable "
            f"({exc!r}) -- the ADR-0004 Python Stage-4 widget is unreachable in "
            "this environment; the skip lifts when the lib is on the path."
        )
    widget = ResectionPlanningWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    return widget


def _accessor_or_skip(bezier):
    """Skip unless the Bezier surface exposes ``GetDistanceMapVolumeNode``.

    The gate reads this accessor (vtkMRMLMarkupsBezierSurfaceNode.h line 91);
    if the Python wrapping does not surface it, the gate cannot be exercised.
    """
    if not hasattr(bezier, "GetDistanceMapVolumeNode"):
        pytest.skip(
            f"{BEZIER_SURFACE_CLASS} exposes no GetDistanceMapVolumeNode() in "
            "this build -- the T3-g3 gating predicate (ADR-0023 §Stage-4) "
            "cannot be evaluated."
        )


def _hint_label(widget):
    """Return the resectogram drawer's hint label by objectName, or ``None``.

    Probes both the direct objectName and a thin Python-accessible getter so
    the implementer has two ways to satisfy the contract.
    """
    import qt  # type: ignore[import-not-found]

    label = widget.findChild(qt.QLabel, HINT_LABEL_OBJECT_NAME)
    if label is not None:
        return label
    getter = getattr(widget, "resectogramHintLabel", None)
    if callable(getter):
        return getter()
    return getattr(widget, "ResectogramHintLabel", None)


def _drawer(widget):
    """Return the resectogram drawer by objectName, or ``None``."""
    import qt  # type: ignore[import-not-found]

    drawer = widget.findChild(qt.QWidget, DRAWER_OBJECT_NAME)
    if drawer is not None:
        return drawer
    getter = getattr(widget, "resectogramDrawer", None)
    if callable(getter):
        return getter()
    return getattr(widget, "ResectogramDrawer", None)


def _combo_box(widget):
    """Return the active-resection combo box by objectName, or ``None``."""
    import qt  # type: ignore[import-not-found]

    combo = widget.findChild(qt.QWidget, COMBO_BOX_OBJECT_NAME)
    if combo is not None:
        return combo
    getter = getattr(widget, "resectionSurfaceComboBox", None)
    if callable(getter):
        return getter()
    return getattr(widget, "ResectionSurfaceComboBox", None)


def _require_widget_chrome_or_skip(widget):
    """Skip unless both the combo box and the drawer hint are findable.

    The pinned invariant is the auto-populate behaviour; if neither the
    objectName nor a Python-accessible getter resolves the controls, skip with
    guidance rather than failing -- the implementer wires one of the two
    shapes.  Returns ``(combo, hint)``.
    """
    combo = _combo_box(widget)
    hint = _hint_label(widget)
    if combo is None or hint is None:
        pytest.skip(
            "T3-g3 widget chrome not found: expected a "
            f"qMRMLNodeComboBox objectName={COMBO_BOX_OBJECT_NAME!r} and a "
            f"QLabel objectName={HINT_LABEL_OBJECT_NAME!r} (or the "
            "Python-accessible getters resectionSurfaceComboBox / "
            "resectogramHintLabel).  Skip lifts when the implementer wires the "
            "controls (ADR-0023 §Stage-4)."
        )
    return combo, hint


def _select_active_resection(widget, combo, node):
    """Select ``node`` as the active resection on the widget.

    Selecting is the TRIGGER in the auto-populate model (no [Open] button).
    Prefers a thin Python API (``setActiveResectionNode``); falls back to the
    qMRMLNodeComboBox ``setCurrentNode``.  Returns ``True`` on success.
    """
    setter = getattr(widget, "setActiveResectionNode", None)
    if callable(setter):
        setter(node)
        return True
    if hasattr(combo, "setCurrentNode"):
        combo.setCurrentNode(node)
        return True
    return False


def _require_populated_or_skip(hint):
    """Skip unless the drawer populated (the hint is hidden).

    In the auto-populate model, selecting a distance-mapped surface should hide
    the hint and run the ensure path.  If the hint is NOT hidden the
    auto-populate predicate is not yet wired -- skip with an explicit reason
    (covered by the Invariant 1 hint tests) rather than asserting a downstream
    ensure invariant against an un-fired trigger (#460 explicit-skip lesson).
    Checked via ``isHidden()`` not ``visible``: under --no-main-window the
    unshown widget tree reports ``visible==False`` regardless.
    """
    if not hint.isHidden():
        pytest.skip(
            "drawer did not auto-populate on a distance-mapped surface (hint "
            "not hidden) -- the auto-populate predicate is not yet wired; "
            "covered by test_hint_hidden_when_surface_has_distance_map."
        )


def _count_resectogram_display_nodes(slicer, bezier):
    """Count ``vtkMRMLResectogramDisplayNode``s referenced by ``bezier``."""
    count = 0
    for index in range(bezier.GetNumberOfDisplayNodes()):
        display = bezier.GetNthDisplayNode(index)
        if display is not None and display.IsA(RESECTOGRAM_DISPLAY_CLASS):
            count += 1
    return count


def _count_singleton_view_nodes(slicer):
    """Count view nodes carrying the resectogram singleton tag."""
    try:
        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            RESECTOGRAM_VIEW_SINGLETON_TAG,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "ResectogramViewManager not importable "
            f"({exc!r}) -- cannot resolve RESECTOGRAM_VIEW_SINGLETON_TAG to "
            "count the singleton view node (ADR-0023 §Stage-4)."
        )
    scene = slicer.mrmlScene
    count = 0
    total = scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)
    for index in range(total):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if node is not None and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            count += 1
    return count


# --------------------------------------------------------------------------- #
# Fixture builders -- reuse the Resectogram4x4BlurOff scenario, plus a
# no-distance-map variant for the disabled-gate case.
# --------------------------------------------------------------------------- #


def _make_surface_with_distance_map(slicer):
    """Build a Bezier surface WITH a distance map (gate-satisfied fixture).

    Reuses the ``Resectogram4x4BlurOff`` scenario builders so the fixture
    matches the production render inputs.  Returns the markups Bezier node;
    the distance map is attached via ``SetDistanceMapVolumeNode`` inside the
    builder so ``GetDistanceMapVolumeNode()`` is non-null.
    """
    from scenarios import Resectogram4x4BlurOff as scn  # type: ignore[import-not-found]

    slicer.modules.liverresections.logic()
    distance_map = scn._make_parenchyma_distance_map(
        sphere_center=scn.SPHERE_CENTER,
        sphere_radius=scn.SPHERE_RADIUS,
    )
    bezier = scn._build_resectogram_bezier(
        half_extent_u=scn.PATCH_HALF_EXTENT_U,
        half_extent_v=scn.PATCH_HALF_EXTENT_V,
        enable_flexible_boundary=scn.ENABLE_FLEXIBLE_BOUNDARY,
        distance_map=distance_map,
    )
    return bezier


def _make_surface_without_distance_map(slicer):
    """Build a Bezier surface with NO distance map (gate-disabled fixture).

    Same control-point footprint as the gate-satisfied fixture but
    ``SetDistanceMapVolumeNode`` is never called, so
    ``GetDistanceMapVolumeNode()`` is null and the gate must DISABLE the
    action (ADR-0023 §Stage-4 gating predicate).
    """
    import vtk  # type: ignore[import-not-found]

    slicer.modules.liverresections.logic()
    bezier = slicer.mrmlScene.AddNewNodeByClass(
        BEZIER_SURFACE_CLASS, "GateTestBezierNoDistanceMap"
    )
    if bezier is None:
        pytest.skip(
            f"{BEZIER_SURFACE_CLASS} not registered in this build -- "
            "cannot exercise the T3-g3 gate."
        )
    for _ in range(16):
        bezier.AddControlPoint(vtk.vtkVector3d(0.0, 0.0, 0.0))
    bezier.CreateDefaultDisplayNodes()
    return bezier


# --------------------------------------------------------------------------- #
# Invariant 1 -- auto-populate predicate (the load-bearing, GPU-free invariant).
# The drawer shows the HINT when the predicate is unsatisfied, and hides it
# (populating the view in its place) when satisfied.
# --------------------------------------------------------------------------- #


def test_resectogram_drawer_exists():
    """The widget carries the collapsible "Resectogram" drawer.

    ADR-0023 §Stage-4: the drawer is the container the view auto-populates into
    (replacing the removed [Open] button).  Cheap structural pin -- the drawer
    is findable by objectName (or the Python-accessible getter).
    """
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    _require_widget_chrome_or_skip(widget)

    assert _drawer(widget) is not None, (
        "the LiverResections widget must carry the collapsible resectogram "
        f"drawer (objectName {DRAWER_OBJECT_NAME!r} or the resectogramDrawer() "
        "getter) -- ADR-0023 §Stage-4."
    )


def test_hint_shown_when_no_surface_selected():
    """No active resection selected => the drawer shows the hint.

    ADR-0023 §Stage-4 auto-populate predicate (the negative branch): with no
    surface selected the drawer cannot populate, so it shows a non-empty,
    visible hint instead of an edge-on / blank view (ADR-0009 §explainable
    state).  RED until the widget + drawer land (skips pre-implementation).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    # Clear any selection: select no node.
    if not _select_active_resection(widget, combo, None):
        pytest.skip(
            "neither setActiveResectionNode(None) nor combo.setCurrentNode "
            "is available to clear the selection (implementer contract)."
        )

    assert not hint.isHidden(), (
        "the resectogram drawer hint must be SHOWN when no Bezier surface is "
        "selected (ADR-0023 §Stage-4 auto-populate predicate; ADR-0009 "
        "§explainable state).  Checked via isHidden() not visible: under "
        "--no-main-window the unshown widget tree reports visible==False "
        "regardless, but isHidden() reflects the explicit show/hide state."
    )
    assert hint.text, (
        "the resectogram drawer hint must carry non-empty text explaining what "
        "to select (ADR-0009 §explainable state) -- e.g. 'select a resection "
        "with a computed distance map'."
    )


def test_hint_shown_when_surface_has_no_distance_map():
    """Surface selected but no distance map => the drawer shows the hint.

    ADR-0023 §Stage-4 auto-populate predicate: populates iff a surface is
    selected AND ``GetDistanceMapVolumeNode() != nullptr``
    (vtkMRMLMarkupsBezierSurfaceNode.h line 91).  A surface without a distance
    map keeps the hint up -- the merged resectogram stack has nothing to
    sample.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_without_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert bezier.GetDistanceMapVolumeNode() is None  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract: "
            "setActiveResectionNode / combo.setCurrentNode)."
        )

    assert not hint.isHidden(), (
        "the resectogram drawer hint must be SHOWN when the selected surface "
        "has no distance map (GetDistanceMapVolumeNode() is None) -- "
        "ADR-0023 §Stage-4, ADR-0009 §explainable state.  Checked via "
        "isHidden() not visible (see test_hint_shown_when_no_surface_selected)."
    )
    assert hint.text, (
        "the resectogram drawer hint must carry non-empty text explaining the "
        "unpopulated reason (ADR-0009 §explainable state)."
    )


def test_hint_hidden_when_surface_has_distance_map():
    """Surface with a distance map selected => the drawer hint is HIDDEN.

    ADR-0023 §Stage-4 auto-populate predicate: the positive branch -- the
    drawer populates (shows the view), so the hint is hidden.  State-ORTHOGONAL
    -- the predicate does NOT read ADR-0019 ResectionState, so a distance-mapped
    surface populates regardless of Planning/Confirmed state.  GPU-free: pins
    the hint visibility, not the GL render.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert bezier.GetDistanceMapVolumeNode() is not None  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract: "
            "setActiveResectionNode / combo.setCurrentNode)."
        )

    assert hint.isHidden(), (
        "the resectogram drawer hint must be HIDDEN when a Bezier surface WITH "
        "a distance map is selected -- the drawer auto-populates the view in "
        "its place (ADR-0023 §Stage-4 auto-populate predicate, positive "
        "branch).  Checked via isHidden(): the ensure + hint-hide run headless; "
        "the GL embed itself is gated to the main-window eyeball pass."
    )


# --------------------------------------------------------------------------- #
# Invariant 2 -- single display node on trigger (idempotent reuse).
# --------------------------------------------------------------------------- #


def test_trigger_ensures_exactly_one_resectogram_display_node():
    """Triggering ensures EXACTLY ONE resectogram display node on the surface.

    ADR-0023 §Stage-4 click action: ensure a ``vtkMRMLResectogramDisplayNode``
    on the selected surface (``AddAndObserveDisplayNodeID`` if none present).
    The surface starts with no resectogram display node; one trigger creates
    exactly one.  Net-new production behaviour (today only the
    Resectogram4x4BlurOff scenario attaches it).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert _count_resectogram_display_nodes(slicer, bezier) == 0  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    _require_populated_or_skip(hint)

    assert _count_resectogram_display_nodes(slicer, bezier) == 1, (
        "selecting a distance-mapped surface must ensure EXACTLY ONE "
        f"{RESECTOGRAM_DISPLAY_CLASS} on it "
        "(AddAndObserveDisplayNodeID when none present) -- ADR-0023 §Stage-4."
    )


def test_reselect_reuses_display_node_no_duplicate():
    """Re-selecting does NOT create a second resectogram display node.

    ADR-0023 §Stage-4: the ensure step is idempotent -- a surface that already
    carries a ``vtkMRMLResectogramDisplayNode`` is reused, not duplicated.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    _require_populated_or_skip(hint)
    first_count = _count_resectogram_display_nodes(slicer, bezier)

    # Re-select the SAME surface (clear then re-select) to re-run the ensure
    # path and prove idempotency.
    _select_active_resection(widget, combo, None)
    _select_active_resection(widget, combo, bezier)
    second_count = _count_resectogram_display_nodes(slicer, bezier)

    assert first_count == 1, (
        "first selection must leave exactly one resectogram display node "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-selecting must REUSE the existing resectogram display node, not "
        f"create a second ({second_count} present after the 2nd selection) -- "
        "ADR-0023 §Stage-4 idempotent ensure."
    )


# --------------------------------------------------------------------------- #
# Invariant 3 -- view-node idempotency (singleton-by-tag).
# --------------------------------------------------------------------------- #


def test_selection_ensures_singleton_resectogram_view_node():
    """Selecting a valid surface ensures the singleton resectogram view node.

    ADR-0023 §Stage-4: the widget calls
    ``ResectogramViewManager.ensureViewNode()`` -- after selecting a valid
    surface exactly one ``vtkMRMLViewNode`` carries
    RESECTOGRAM_VIEW_SINGLETON_TAG.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert _count_singleton_view_nodes(slicer) == 0  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    _require_populated_or_skip(hint)

    assert _count_singleton_view_nodes(slicer) == 1, (
        "selecting a distance-mapped surface must ensure exactly one "
        "resectogram-tagged vtkMRMLViewNode via "
        "ResectogramViewManager.ensureViewNode() -- ADR-0023 §Stage-4."
    )


def test_reselect_reuses_view_node_no_duplicate():
    """Re-selecting reuses the singleton view node -- no second view node.

    ADR-0023 §Stage-4 + ResectogramViewManager singleton-by-tag: re-selecting
    re-targets the existing tagged view node rather than minting a duplicate
    (the singleton-tag mechanism the Slicer view machinery enforces).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    _require_populated_or_skip(hint)
    first_count = _count_singleton_view_nodes(slicer)

    _select_active_resection(widget, combo, None)
    _select_active_resection(widget, combo, bezier)
    second_count = _count_singleton_view_nodes(slicer)

    assert first_count == 1, (
        "first selection must leave exactly one resectogram-tagged view node "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-selecting must REUSE the singleton resectogram view node, not "
        f"create a second ({second_count} present after the 2nd selection) -- "
        "ResectogramViewManager.ensureViewNode() is singleton-by-tag "
        "(ADR-0023 §Stage-4)."
    )


# --------------------------------------------------------------------------- #
# Invariant 4 -- selecting a valid surface embeds ONE qMRMLThreeDWidget bound
# to the singleton resectogram view node inside the drawer (T3-g3b).
# --------------------------------------------------------------------------- #


def _require_main_window_or_skip(slicer):
    """Skip unless a realized main window exists to back a 3D GL context.

    The embed step binds the singleton view node to a ``qMRMLThreeDWidget``
    (``setMRMLViewNode``), which synchronously drives the markups displayable
    manager to upload the distance-map 3D texture for the gate-satisfied
    fixture surface.  That texture upload dereferences live GL entry points,
    so it needs a REALIZED GL context -- i.e. a shown main window.  The
    launched ``pytest_launched`` harness runs ``--no-main-window``
    (``slicer.util.mainWindow()`` is ``None``), where no such context can be
    created and the upload hard-crashes the process; the embed + binding is
    instead exercised on the orchestrator's interactive ``:0`` eyeball pass
    (ADR-0023 §Stage-4).  Skip cleanly here so the GPU-free invariants in this
    file still run under the headless harness (#460 explicit-skip lesson).
    """
    if slicer.util.mainWindow() is None:
        pytest.skip(
            "no main window (--no-main-window harness): binding the embedded "
            "qMRMLThreeDWidget to the singleton view node uploads the "
            "distance-map 3D texture, which needs a realized GL context.  The "
            "embed invariant is exercised on the interactive eyeball pass "
            "(ADR-0023 §Stage-4); the GPU-free invariants in this file run "
            "headlessly."
        )


def _resectogram_three_d_widgets(slicer, widget):
    """Return the drawer's ``qMRMLThreeDWidget`` children.

    The embedded resectogram view widget is a ``qMRMLThreeDWidget`` (a C++
    class); selecting a valid surface adds exactly one inside the drawer
    (ADR-0023 §Stage-4, the SlicerHyperProbe ``create_three_d_widget``
    precedent).
    """
    import qt  # type: ignore[import-not-found]

    return [
        child
        for child in widget.findChildren(slicer.qMRMLThreeDWidget)
        if isinstance(child, qt.QWidget)
    ]


def test_selection_embeds_three_d_widget_bound_to_singleton_view_node():
    """Selecting a valid surface embeds one qMRMLThreeDWidget bound to the view.

    ADR-0023 §Stage-4: with the predicate satisfied, the drawer auto-populates
    a single ``qMRMLThreeDWidget`` whose ``mrmlViewNode()`` IS the resectogram
    singleton view node (identity by node ID).  GPU-free -- pins the widget tree
    + node identity, not the GL render (the orchestrator's eyeball).
    """
    slicer = _slicer_or_skip()
    _require_main_window_or_skip(slicer)
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip("cannot select the active resection (implementer contract).")
    _require_populated_or_skip(hint)

    embedded = _resectogram_three_d_widgets(slicer, widget)
    assert len(embedded) == 1, (
        "selecting a valid surface must embed EXACTLY ONE qMRMLThreeDWidget "
        f"in the drawer (got {len(embedded)}) -- ADR-0023 §Stage-4."
    )

    view_node = embedded[0].mrmlViewNode()
    assert view_node is not None, (
        "the embedded qMRMLThreeDWidget must be bound to a view node "
        "(setMRMLViewNode) -- ADR-0023 §Stage-4."
    )
    from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
        RESECTOGRAM_VIEW_SINGLETON_TAG,
    )

    assert view_node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG, (
        "the embedded qMRMLThreeDWidget must be bound to the resectogram "
        "SINGLETON view node (the one carrying RESECTOGRAM_VIEW_SINGLETON_TAG), "
        "so the LayerDM ResectogramPipeline composites into it -- "
        "ADR-0023 §Stage-4."
    )


def test_reselect_reuses_three_d_widget_no_duplicate():
    """Re-selecting does NOT add a second qMRMLThreeDWidget.

    ADR-0023 §Stage-4: the embed step is idempotent -- re-selecting the surface
    re-targets/shows the existing drawer widget rather than minting a second
    one (mirroring the singleton view-node + display-node idempotency).
    """
    slicer = _slicer_or_skip()
    _require_main_window_or_skip(slicer)
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip("cannot select the active resection (implementer contract).")
    _require_populated_or_skip(hint)
    first_count = len(_resectogram_three_d_widgets(slicer, widget))

    _select_active_resection(widget, combo, None)
    _select_active_resection(widget, combo, bezier)
    second_count = len(_resectogram_three_d_widgets(slicer, widget))

    assert first_count == 1, (
        "first selection must embed exactly one qMRMLThreeDWidget "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-selecting must REUSE the embedded qMRMLThreeDWidget, not add a "
        f"second ({second_count} present after the 2nd selection) -- "
        "ADR-0023 §Stage-4 idempotent embed."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
