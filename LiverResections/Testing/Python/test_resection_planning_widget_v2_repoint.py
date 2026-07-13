# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 4 -- re-point the Stage-4 ResectionPlanningWidget to the v2 node graph.

Until slice 4 the ResectionPlanningWidget selected a v1
``vtkMRMLMarkupsBezierSurfaceNode`` and read the distance map off THAT node
(``GetDistanceMapVolumeNode``).  Slice 4 re-points the widget onto the v2
resection-plan node graph (ADR-0014 §"Fourth layer" wrapper/carrier split):

  * the active-resection combo box selects the ``vtkMRMLResectionPlanNode``
    WRAPPER (not the v1 markups surface);
  * "resectogram available" reads the distance map off the WRAPPER
    (``plan.GetDistanceMapVolumeNode()`` -- ADR-0031: the distance map lives on
    the wrapper, not the carrier);
  * the ``vtkMRMLResectogramDisplayNode`` is ensured on the CARRIER
    (``plan.GetGeometryNode()``, a ``vtkMRMLBezierSurfaceNode``), not the
    wrapper;
  * a "Place resection" affordance mints a fresh plan via the logic create-API
    (``vtkSlicerLiverResectionsLogic::CreateResectionPlan``, #501 slice 1) and
    selects it in the combo.

This pins the re-point in three invariants, all MRML/widget-state and GPU-free
(they run under the ``--no-main-window`` launched harness -- no realized GL
context needed; the embed itself self-gates on a main window):

  1. COMBO RE-POINT.  After ``setMRMLScene``, a scene holding a
     ``vtkMRMLResectionPlanNode`` OFFERS it as selectable; a scene holding a v1
     ``vtkMRMLMarkupsBezierSurfaceNode`` does NOT offer it (the v1 surface is no
     longer directly selectable -- the combo ``nodeTypes`` is
     ``["vtkMRMLResectionPlanNode"]``).

  2. AUTO-POPULATE PREDICATE RE-POINTED.  "resectogram available" iff a plan is
     selected AND ``plan.GetDistanceMapVolumeNode() is not None`` (ADR-0031,
     read off the WRAPPER).  Three hint states: (a) none selected -> "select"
     hint; (b) plan without distance map -> "compute the distance map" hint;
     (c) plan WITH distance map -> hint hidden AND exactly one
     ``vtkMRMLResectogramDisplayNode`` ensured on the CARRIER
     (``plan.GetGeometryNode()``), idempotent across repeated refreshes.

  3. PLACE BUTTON.  The widget exposes a "Place resection" affordance
     (``placeResectionButton()`` accessor + an ``onPlaceResection()`` slot);
     invoking the slot calls ``logic.CreateResectionPlan(...)``, adds the plan
     to the scene, and selects it in the combo -- afterwards the combo's current
     node ``IsA vtkMRMLResectionPlanNode`` and the scene gained a plan + a
     ``vtkMRMLBezierSurfaceNode`` carrier.

-- WHY LAUNCHED-SLICER + SKIP-PENDING --

The widget imports ``LiverResectionsLib.ResectionPlanningWidget`` (ADR-0004
Python GUI) and needs the wrapped ``vtkMRMLResectionPlanNode`` /
``vtkMRMLBezierSurfaceNode`` + the logic create-API, all reachable only inside a
launched Slicer with the module loaded.  A bare ``PythonSlicer -m pytest`` has
``slicer.mrmlScene is None`` / no ``qt.QWidget`` / no create-API, so every test
here SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards -- it never
errors.

Each invariant is additionally GUARDED on the NEW state's PRESENCE
(``nodeTypes`` inspection / ``hasattr`` on the place-button accessor + the
create-API), so this lands RED-as-skip on the current (still-v1) build and
turns GREEN once slice 4 re-points the widget -- the ADR-0027 §Conformance
"the skip lifts at the implementation commit" shape.  Verify run-vs-skip in the
CI log; never trust overall green (the launched harness is green-but-skipping
prone).

-- NOT PINNED HERE (interactive :0 eyeball follow-ups) --

The GL-coupled reactivity / render path is deliberately NOT committed here.  In
v1 the storm-free strip-repaint hooked the markups ``PointModifiedEvent`` (a
signal a render does not raise); the v2 carrier fires only generic
``Modified()`` on control-point edits, so a control-point edit repainting the
embedded strip WITHOUT a feedback-storm is a GL-coupled invariant that belongs
on the interactive ``:0`` eyeball probe (ADR-0032 §Conformance), not a committed
headless test.

-- IMPLEMENTER CONTRACT (assumed accessors + entry points) --

  * ``LiverResectionsLib.ResectionPlanningWidget`` -- the Python Stage-4 widget
    (ADR-0004); composed by ``Liver/Liver.py`` for stage 3.
  * combo box objectName ``"ResectionSurfaceComboBox"`` with
    ``nodeTypes == ["vtkMRMLResectionPlanNode"]`` (the re-point).
  * ``widget.placeResectionButton()`` -> the "Place resection" affordance
    (a ``QPushButton`` / ``QAbstractButton``); ``widget.onPlaceResection()`` ->
    the slot that mints + selects a fresh plan.
  * ``widget.resectogramHintLabel()`` -- the drawer hint (ADR-0009 §explainable
    state), non-empty text, VISIBLE iff the drawer is not populated.

See also:
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"  (wrapper/carrier)
  * Docs/adr/0031-distance-map-on-resection-plan-wrapper.md  (distance map on
    the WRAPPER; the auto-populate predicate reads it there)
  * Docs/adr/0019-resection-state-machine.md  (plan state; predicate is
    state-orthogonal)
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4  (the GUI surface)
  * Docs/adr/0004-python-cpp-boundary.md  (the widget is Python)
  * Docs/adr/0027-invariant-test-first-v2-implementation.md  (RED / skip-pending)
  * LiverResections/LiverResectionsLib/ResectionPlanningWidget.py  (the widget)
  * LiverResections/Testing/Python/test_resectogram_open_view_action.py  (the
    v1-surface auto-populate invariants this re-points from)
  * LiverResections/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liverresections"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"
BEZIER_CARRIER_CLASS = "vtkMRMLBezierSurfaceNode"
V1_MARKUPS_SURFACE_CLASS = "vtkMRMLMarkupsBezierSurfaceNode"
RESECTOGRAM_DISPLAY_CLASS = "vtkMRMLResectogramDisplayNode"

COMBO_BOX_OBJECT_NAME = "ResectionSurfaceComboBox"
HINT_LABEL_OBJECT_NAME = "ResectogramHintLabel"
VIEW_NODE_CLASS = "vtkMRMLViewNode"


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each test.
# --------------------------------------------------------------------------- #


def _purge_resectogram_singleton_view():
    """Remove the resectogram singleton view node AND its auto-created camera.

    The positive auto-populate branch runs ``ResectogramViewManager`` which
    mints a ``vtkMRMLViewNode`` carrying a MRML ``SingletonTag`` (and, via the
    cameras logic, a paired ``vtkMRMLCameraNode``).  Both SURVIVE
    ``vtkMRMLScene.Clear(0)`` by design, so they trip this directory's
    ``_launched_scene_cleanup`` leak-check (``remaining <= baseline``) unless
    reclaimed here.  Reclaim the paired camera BEFORE the view it points at, so
    the cameras logic does not re-pair an orphan camera with the surviving
    singleton.  No-op under bare pytest / before the manager is importable.
    Mirrors ``test_resectogram_open_view_action._purge_resectogram_singleton_view``.
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
    for index in range(scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if node is not None and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            stale_views.append(node)
            stale_view_ids.add(node.GetID())

    stale_cameras = []
    for index in range(scene.GetNumberOfNodesByClass("vtkMRMLCameraNode")):
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

    Function-scoped + module-local so it brackets each test INSIDE the broader
    conftest cleanup: purge BOTH before (defend the precondition against a
    sibling-file leak) and after (so this file never leaks onward).  No-op under
    bare pytest.
    """
    _purge_resectogram_singleton_view()
    yield
    _purge_resectogram_singleton_view()


# --------------------------------------------------------------------------- #
# Skip-guards -- every path prints an explicit, greppable reason (#460 lesson).
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    """Resolve a launched ``slicer`` with a scene, or skip cleanly.

    Imports the guards from ``slicer_pytest_support`` directly (NOT
    ``from conftest import``): the launched harness passes several test roots,
    so ``conftest`` resolves to whichever sibling is first on the path.  The
    sibling LiverResections tests import the canonical bodies the same way.
    """
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _module_or_skip(slicer):
    """Skip unless the LiverResections loadable module is registered."""
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- the Stage-4 widget "
            "(ADR-0023 §Stage-4) is unreachable in this environment."
        )
    return module


def _widget_or_skip(slicer):
    """Construct the Python ResectionPlanningWidget, or skip cleanly.

    Per ADR-0004 the Stage-4 GUI is Python: build the widget directly and call
    ``setMRMLScene(slicer.mrmlScene)``.  Registers it for deterministic teardown
    (parentless widgets crash the launched harness at shutdown; the conftest
    autouse fixture drains + cleans them while the scene is still alive).
    """
    from slicer_pytest_support import require_qt_widget, register_widget_for_teardown

    require_qt_widget()
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
    return register_widget_for_teardown(widget)


def _combo_box(widget):
    """Return the active-resection combo box by objectName or getter, or None."""
    import qt  # type: ignore[import-not-found]

    combo = widget.findChild(qt.QWidget, COMBO_BOX_OBJECT_NAME)
    if combo is not None:
        return combo
    getter = getattr(widget, "resectionSurfaceComboBox", None)
    if callable(getter):
        return getter()
    return getattr(widget, "ResectionSurfaceComboBox", None)


def _hint_label(widget):
    """Return the resectogram drawer's hint label by objectName or getter."""
    import qt  # type: ignore[import-not-found]

    label = widget.findChild(qt.QLabel, HINT_LABEL_OBJECT_NAME)
    if label is not None:
        return label
    getter = getattr(widget, "resectogramHintLabel", None)
    if callable(getter):
        return getter()
    return getattr(widget, "ResectogramHintLabel", None)


def _combo_or_skip(widget):
    """Return the combo box, or skip with implementer guidance."""
    combo = _combo_box(widget)
    if combo is None:
        pytest.skip(
            "active-resection combo box not found: expected a qMRMLNodeComboBox "
            f"objectName={COMBO_BOX_OBJECT_NAME!r} (or the "
            "resectionSurfaceComboBox() getter).  Skip lifts when the "
            "implementer wires the control (ADR-0023 §Stage-4)."
        )
    return combo


def _combo_node_types(combo):
    """Return the combo's nodeTypes as a Python list of str (or None)."""
    node_types = getattr(combo, "nodeTypes", None)
    if node_types is None:
        return None
    return [str(t) for t in node_types]


def _require_combo_repointed_or_skip(combo):
    """Skip-pending unless the combo has been re-pointed to the plan wrapper.

    RED == the combo still lists the v1 ``vtkMRMLMarkupsBezierSurfaceNode``; the
    skip lifts at the slice-4 implementation commit (ADR-0027).  Guarded on the
    NEW state's presence (``nodeTypes`` inspection) rather than a bare assert, so
    the test skips (not errors) on the still-v1 build.
    """
    node_types = _combo_node_types(combo)
    if node_types is None:
        pytest.skip(
            "combo box exposes no inspectable nodeTypes -- cannot verify the "
            "#501 slice-4 re-point to vtkMRMLResectionPlanNode."
        )
    if PLAN_NODE_CLASS not in node_types:
        pytest.skip(
            f"combo box nodeTypes {node_types} does not list {PLAN_NODE_CLASS!r} "
            "-- the #501 slice-4 re-point to the v2 resection-plan wrapper "
            "(ADR-0014 §'Fourth layer') has not landed.  Skip lifts at the "
            "implementation commit (ADR-0027)."
        )


def _resection_logic_or_skip(slicer):
    """Return the resection logic with the create-API, or skip cleanly.

    The plan/carrier/display triad is minted via the merged
    ``CreateResectionPlan`` (#501 slice 1); skip cleanly if the module / logic /
    create-API is not reachable in this build.
    """
    module = _module_or_skip(slicer)
    logic = module.logic()
    if logic is None:
        pytest.skip("liverresections module has no logic singleton.")
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "create-API (#501 slice 1) is not in this build."
        )
    return logic


def _make_plan_or_skip(slicer, name, with_distance_map):
    """Mint a v2 resection plan via the logic create-API.

    Returns the ``vtkMRMLResectionPlanNode`` wrapper.  When
    ``with_distance_map`` is True, attaches a scalar volume as the distance map
    on the WRAPPER (ADR-0031); otherwise leaves ``GetDistanceMapVolumeNode()``
    null so the negative branch of the auto-populate predicate is exercised.
    """
    logic = _resection_logic_or_skip(slicer)
    plan = logic.CreateResectionPlan(name)
    if plan is None or not plan.IsA(PLAN_NODE_CLASS):
        pytest.skip(
            "CreateResectionPlan did not return a vtkMRMLResectionPlanNode -- "
            "cannot exercise the slice-4 re-point."
        )
    for method in ("GetGeometryNode", "GetDistanceMapVolumeNode"):
        if not hasattr(plan, method):
            pytest.skip(
                f"{PLAN_NODE_CLASS} exposes no {method}() in this build -- the "
                "ADR-0031 distance-map-on-wrapper API is not wrapped."
            )
    if with_distance_map:
        if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode"):
            pytest.skip(
                f"{PLAN_NODE_CLASS} has no SetAndObserveDistanceMapVolumeNode -- "
                "cannot attach the distance map on the wrapper (ADR-0031)."
            )
        volume = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode", f"{name}DistanceMap"
        )
        if volume is None:
            pytest.skip(
                "vtkMRMLScalarVolumeNode not registered -- cannot attach a "
                "distance map on the wrapper."
            )
        plan.SetAndObserveDistanceMapVolumeNode(volume)
        if plan.GetDistanceMapVolumeNode() is None:
            pytest.skip(
                "distance map did not attach to the wrapper -- cannot exercise "
                "the positive auto-populate branch (ADR-0031)."
            )
    return plan


def _select(widget, combo, node):
    """Select ``node`` as the active resection; returns True on success."""
    setter = getattr(widget, "setActiveResectionNode", None)
    if callable(setter):
        setter(node)
        return True
    if hasattr(combo, "setCurrentNode"):
        combo.setCurrentNode(node)
        return True
    return False


def _count_carrier_resectogram_display_nodes(plan):
    """Count ``vtkMRMLResectogramDisplayNode``s on the plan's CARRIER.

    Slice 4 attaches the resectogram display node to the carrier
    (``plan.GetGeometryNode()``), NOT the wrapper (ADR-0014 §'Fourth layer').
    """
    carrier = plan.GetGeometryNode()
    if carrier is None:
        return 0
    count = 0
    for index in range(carrier.GetNumberOfDisplayNodes()):
        display = carrier.GetNthDisplayNode(index)
        if display is not None and display.IsA(RESECTOGRAM_DISPLAY_CLASS):
            count += 1
    return count


def _refresh(widget):
    """Re-run the drawer's auto-populate predicate (idempotency probe)."""
    refresh = getattr(widget, "refreshResectogramDrawer", None)
    if callable(refresh):
        refresh()


# --------------------------------------------------------------------------- #
# Invariant 1 -- combo re-point (offers plan wrapper, not the v1 surface).
# --------------------------------------------------------------------------- #


def test_combo_offers_resection_plan_node():
    """The combo lists (and offers) a ``vtkMRMLResectionPlanNode``.

    #501 slice 4 re-points the active-resection combo to the v2 wrapper
    (ADR-0014 §'Fourth layer').  A scene holding a plan node makes it the
    combo's current node after selection.  Skip-pending on the still-v1 combo
    (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    plan = _make_plan_or_skip(slicer, "RepointComboTest", with_distance_map=False)
    if not _select(widget, combo, plan):
        pytest.skip("cannot select the active resection (implementer contract).")

    current = combo.currentNode()
    assert current is not None and current.IsA(PLAN_NODE_CLASS), (
        "the active-resection combo must offer + select a "
        f"{PLAN_NODE_CLASS} (ADR-0014 §'Fourth layer'); its current node is "
        f"{current.GetClassName() if current is not None else None!r}."
    )


def test_combo_does_not_offer_v1_markups_surface():
    """The combo does NOT list the retired ``vtkMRMLMarkupsBezierSurfaceNode``.

    The Stage-4 combo selects the plan wrapper (ADR-0014 §"Fourth layer"),
    never a surface node.  The v1 markups Bezier surface is fully retired
    (ADR-0014 §"Dissolution"; ADR-0032 §"Consequences") -- the class no
    longer exists, so it cannot be instantiated; this pins that the
    re-pointed combo's advertised node types never name it.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    # The retired class is not registered, so a scene can never hold one;
    # assert the combo's advertised node types do not name it (it selects
    # the plan wrapper).
    node_types = _combo_node_types(combo)
    assert V1_MARKUPS_SURFACE_CLASS not in node_types, (
        "the re-pointed combo must NOT list the retired "
        f"{V1_MARKUPS_SURFACE_CLASS} (it selects the "
        f"{PLAN_NODE_CLASS} wrapper); nodeTypes is {node_types}."
    )


# --------------------------------------------------------------------------- #
# Invariant 2 -- auto-populate predicate reads the distance map off the WRAPPER
# (ADR-0031); display node ensured on the CARRIER.
# --------------------------------------------------------------------------- #


def test_hint_shown_when_no_plan_selected():
    """No plan selected => the drawer shows the hint.

    ADR-0023 §Stage-4 auto-populate predicate (negative branch): with no plan
    selected the drawer cannot populate, so it shows a non-empty, visible hint
    (ADR-0009 §explainable state).  Checked via ``isHidden()`` not ``visible``:
    under ``--no-main-window`` the unshown tree reports ``visible==False``
    regardless.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    hint = _hint_label(widget)
    if hint is None:
        pytest.skip(
            f"resectogram hint label not found (objectName "
            f"{HINT_LABEL_OBJECT_NAME!r} or resectogramHintLabel())."
        )

    if not _select(widget, combo, None):
        pytest.skip("cannot clear the selection (implementer contract).")

    assert not hint.isHidden(), (
        "the resectogram drawer hint must be SHOWN when no plan is selected "
        "(ADR-0023 §Stage-4 auto-populate predicate; ADR-0009 §explainable "
        "state)."
    )
    assert hint.text, (
        "the hint must carry non-empty text explaining what to select "
        "(ADR-0009 §explainable state)."
    )


def test_hint_shown_when_plan_has_no_distance_map():
    """Plan selected but wrapper has no distance map => the drawer shows the hint.

    ADR-0031: the auto-populate predicate reads
    ``plan.GetDistanceMapVolumeNode()`` off the WRAPPER.  A plan without a
    distance map keeps the hint up (the resectogram stack has nothing to
    sample).  Skip-pending on the still-v1 combo (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    hint = _hint_label(widget)
    if hint is None:
        pytest.skip("resectogram hint label not found (implementer contract).")

    plan = _make_plan_or_skip(slicer, "NoDistanceMapPlan", with_distance_map=False)
    assert plan.GetDistanceMapVolumeNode() is None  # fixture sanity
    if not _select(widget, combo, plan):
        pytest.skip("cannot select the active resection (implementer contract).")

    assert not hint.isHidden(), (
        "the drawer hint must be SHOWN when the selected plan's WRAPPER has no "
        "distance map (plan.GetDistanceMapVolumeNode() is None) -- ADR-0031, "
        "ADR-0023 §Stage-4, ADR-0009 §explainable state."
    )
    assert hint.text, (
        "the hint must carry non-empty text explaining the unpopulated reason "
        "(ADR-0009 §explainable state) -- e.g. 'compute the distance map'."
    )


def test_hint_hidden_and_display_node_on_carrier_when_plan_has_distance_map():
    """Plan WITH a distance map => hint hidden AND one display node on the carrier.

    ADR-0031 (positive branch): the wrapper carries a distance map, so the
    predicate is satisfied -- the hint hides and EXACTLY ONE
    ``vtkMRMLResectogramDisplayNode`` is ensured on the CARRIER
    (``plan.GetGeometryNode()``, ADR-0014 §'Fourth layer'), never on the
    wrapper.  GPU-free: pins hint visibility + carrier display-node presence,
    not the GL render.  Skip-pending on the still-v1 combo (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    hint = _hint_label(widget)
    if hint is None:
        pytest.skip("resectogram hint label not found (implementer contract).")

    plan = _make_plan_or_skip(slicer, "DistanceMapPlan", with_distance_map=True)
    assert plan.GetDistanceMapVolumeNode() is not None  # fixture sanity
    assert _count_carrier_resectogram_display_nodes(plan) == 0  # fixture sanity
    if not _select(widget, combo, plan):
        pytest.skip("cannot select the active resection (implementer contract).")

    assert hint.isHidden(), (
        "the drawer hint must be HIDDEN when the selected plan's WRAPPER carries "
        "a distance map -- the drawer auto-populates (ADR-0031, ADR-0023 "
        "§Stage-4 positive branch).  Checked via isHidden(): the ensure + "
        "hint-hide run headless; the GL embed self-gates on a main window."
    )
    assert _count_carrier_resectogram_display_nodes(plan) == 1, (
        "populating must ensure EXACTLY ONE "
        f"{RESECTOGRAM_DISPLAY_CLASS} on the CARRIER (plan.GetGeometryNode(), a "
        f"{BEZIER_CARRIER_CLASS}), not on the wrapper -- ADR-0014 §'Fourth "
        "layer'."
    )


def test_repeated_refresh_is_idempotent_on_carrier_display_node():
    """Repeated refreshes reuse the carrier's resectogram display node.

    ADR-0023 §Stage-4 idempotent ensure: re-running the auto-populate predicate
    (``refreshResectogramDrawer``) against the same distance-mapped plan REUSES
    the carrier's ``vtkMRMLResectogramDisplayNode`` rather than minting a second
    one.  Skip-pending on the still-v1 combo (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    plan = _make_plan_or_skip(slicer, "IdempotentPlan", with_distance_map=True)
    if not _select(widget, combo, plan):
        pytest.skip("cannot select the active resection (implementer contract).")

    if _count_carrier_resectogram_display_nodes(plan) != 1:
        pytest.skip(
            "drawer did not ensure a carrier display node on selection -- the "
            "positive auto-populate branch is not yet wired (covered by "
            "test_hint_hidden_and_display_node_on_carrier_when_plan_has_"
            "distance_map)."
        )

    # Re-run the predicate several times: re-select + explicit refresh.
    _refresh(widget)
    _select(widget, combo, None)
    _select(widget, combo, plan)
    _refresh(widget)

    assert _count_carrier_resectogram_display_nodes(plan) == 1, (
        "repeated refreshes must REUSE the carrier's resectogram display node, "
        f"not create a second ({_count_carrier_resectogram_display_nodes(plan)} "
        "present) -- ADR-0023 §Stage-4 idempotent ensure, ADR-0014 §'Fourth "
        "layer'."
    )


# --------------------------------------------------------------------------- #
# Invariant 3 -- "Place resection" affordance mints + selects a fresh plan.
# --------------------------------------------------------------------------- #


def _place_button_and_slot_or_skip(widget):
    """Return (button, slot) for the Place-resection affordance, or skip.

    RED == the widget exposes neither the ``placeResectionButton()`` accessor
    nor the ``onPlaceResection()`` slot; the skip lifts at the slice-4
    implementation commit (ADR-0027).
    """
    button_getter = getattr(widget, "placeResectionButton", None)
    slot = getattr(widget, "onPlaceResection", None)
    if not callable(slot):
        pytest.skip(
            "widget has no onPlaceResection() slot -- the #501 slice-4 "
            "'Place resection' affordance (ADR-0023 §Stage-4) has not landed.  "
            "Skip lifts at the implementation commit (ADR-0027)."
        )
    button = button_getter() if callable(button_getter) else None
    return button, slot


def test_place_resection_button_exists():
    """The widget exposes a "Place resection" affordance.

    ADR-0023 §Stage-4: the panel offers an explicit "Place resection" button
    (accessor ``placeResectionButton()``).  Cheap structural pin; skip-pending
    until the affordance lands (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)

    button, _slot = _place_button_and_slot_or_skip(widget)
    assert button is not None, (
        "the widget must expose a 'Place resection' affordance via "
        "placeResectionButton() -- ADR-0023 §Stage-4."
    )


def test_place_resection_mints_and_selects_plan():
    """Invoking the place slot mints a plan (+ carrier) and selects it.

    ADR-0023 §Stage-4 + #501 slice 1: ``onPlaceResection()`` calls
    ``logic.CreateResectionPlan(...)``, adds the plan to the scene, and selects
    it in the combo.  Afterwards the combo's current node ``IsA
    vtkMRMLResectionPlanNode`` and the scene gained a plan + a
    ``vtkMRMLBezierSurfaceNode`` carrier (ADR-0014 §'Fourth layer').
    Skip-pending on the missing slot / create-API (ADR-0027).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    # Require the create-API up front so a build without slice 1 skips cleanly
    # rather than the slot failing.
    _resection_logic_or_skip(slicer)
    widget = _widget_or_skip(slicer)
    combo = _combo_or_skip(widget)
    _require_combo_repointed_or_skip(combo)

    _button, slot = _place_button_and_slot_or_skip(widget)
    _add_canonical_liver(slicer)  # the Place guard requires an Accepted liver

    plans_before = slicer.mrmlScene.GetNumberOfNodesByClass(PLAN_NODE_CLASS)
    carriers_before = slicer.mrmlScene.GetNumberOfNodesByClass(BEZIER_CARRIER_CLASS)

    slot()
    slicer.app.processEvents()

    plans_after = slicer.mrmlScene.GetNumberOfNodesByClass(PLAN_NODE_CLASS)
    carriers_after = slicer.mrmlScene.GetNumberOfNodesByClass(BEZIER_CARRIER_CLASS)

    assert plans_after == plans_before + 1, (
        "onPlaceResection() must add exactly one vtkMRMLResectionPlanNode to "
        f"the scene (before {plans_before}, after {plans_after}) via "
        "logic.CreateResectionPlan(...) -- ADR-0023 §Stage-4, #501 slice 1."
    )
    assert carriers_after == carriers_before + 1, (
        "onPlaceResection() must add exactly one vtkMRMLBezierSurfaceNode "
        f"carrier (before {carriers_before}, after {carriers_after}) -- the "
        "plan's geometry node (ADR-0014 §'Fourth layer')."
    )

    current = combo.currentNode()
    assert current is not None and current.IsA(PLAN_NODE_CLASS), (
        "onPlaceResection() must SELECT the freshly-minted plan in the combo; "
        f"the current node is {current.GetClassName() if current is not None else None!r}."
    )


def test_reshow_kicks_a_resectogram_render():
    """Re-showing the panel must request one embedded-view render.

    Re-entering the module re-shows this panel with the embedded GL
    view's last frame discarded -- without a fresh render request the
    strip reads BLACK until some other interaction repaints it.  The
    kick is deferred one event-loop turn (the show must be processed
    before a forceRender can hit a realized surface), so the pin drains
    the queue before asserting.
    """
    import qt  # type: ignore[import-not-found]
    import slicer  # type: ignore[import-not-found]

    widget = _widget_or_skip(slicer)
    kicks = []
    widget.scheduleResectogramRender = lambda: kicks.append(1)

    widget.show()
    qt.QApplication.processEvents()
    assert kicks, (
        "showEvent must schedule a resectogram render -- re-entering the "
        "module otherwise leaves the strip black until a manual redraw."
    )
    widget.hide()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def _add_canonical_liver(slicer):
    """A canonical-role segmentation with one SCT-tagged liver segment.

    The Place guard requires it: without an Accepted liver there is no
    target mesh and Place refuses (v1 parity -- AddResectionPlane errored
    on a missing target organ model).
    """
    import numpy as np

    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
    array = np.zeros((12, 12, 12), dtype="uint8")
    array[3:9, 3:9, 3:9] = 1
    slicer.util.updateVolumeFromArray(labelmap, array)
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
        labelmap, node
    )
    slicer.mrmlScene.RemoveNode(labelmap)
    node.SetAttribute("LiverSegmentation.Role", "canonical")
    segment_id = node.GetSegmentation().GetNthSegmentID(0)
    node.GetSegmentation().GetSegment(segment_id).SetTag(
        "TerminologyEntry",
        "Segmentation category and type - DICOM master list"
        "~SCT^85756007^Tissue~SCT^10200004^Liver"
        "~^^~Anatomic codes - DICOM master list~^^~^^",
    )
    return node


def test_place_without_canonical_liver_refuses_and_explains():
    """No Accepted liver -> Place mints NOTHING and says why.

    The silent path minted a dead resection (origin grid, no target, no
    seed, no contour) -- exactly the walkthrough failure.  v1 errored on
    a missing target organ; v2 refuses with explainable state
    (ADR-0009): the hint names the missing hand-off.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    _resection_logic_or_skip(slicer)
    widget = _widget_or_skip(slicer)
    _button, slot = _place_button_and_slot_or_skip(widget)

    plans_before = slicer.mrmlScene.GetNumberOfNodesByClass(PLAN_NODE_CLASS)
    slot()
    slicer.app.processEvents()

    assert (
        slicer.mrmlScene.GetNumberOfNodesByClass(PLAN_NODE_CLASS)
        == plans_before
    ), (
        "Place must REFUSE without a canonical liver -- the silent path "
        "minted a dead origin-grid resection."
    )
    hint = widget.resectogramHintLabel()
    assert hint is not None and "liver" in str(hint.text).lower(), (
        "the refusal must explain itself (ADR-0009): the hint names the "
        f"missing Stage-2 hand-off; got {str(hint.text)!r}."
    )
