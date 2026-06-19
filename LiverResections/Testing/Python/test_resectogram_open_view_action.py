# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T3-g3 -- gated "Open resectogram view" action on the LiverResections widget.

LiverResections is a loadable (C++) module that, until T3-g3, ships NO widget
representation (``qSlicerLiverResectionsModule::createWidgetRepresentation()``
returns ``nullptr``).  T3-g3 adds the module's FIRST GUI -- the ADR-0023
§Stage-4 "Resection Planning" surface that ``Liver/Liver.py`` composes via
``LiverResections.widgetRepresentation()`` -- carrying:

  * a ``qMRMLNodeComboBox`` of ``vtkMRMLMarkupsBezierSurfaceNode`` (the node
    the merged resectogram render stack reads -- NOT the
    ``vtkMRMLBezierSurfaceNode`` carrier) that selects the *active* resection,
    and
  * an [Open resectogram view] action/button.

Three pinned invariants (all MRML/widget-state -- GPU-free, runnable in a
minimal ``qSlicerApplication`` without a GL view; the strip RENDERING is out
of g3 scope and is the orchestrator's eyeball pass, not asserted here):

  1. PREDICATE GATING (the load-bearing invariant).  The action is enabled
     iff a Bezier surface is selected AND
     ``selectedNode->GetDistanceMapVolumeNode() != nullptr``
     (vtkMRMLMarkupsBezierSurfaceNode.h line 91).  Disabled when no surface is
     selected, and disabled when the selected surface has no distance map.
     STATE-ORTHOGONAL: the gate does NOT read the ADR-0019 ResectionState -- a
     Planning *or* Confirmed surface with a distance map can open.

  2. SINGLE DISPLAY NODE ON TRIGGER.  Triggering the action with the gate
     satisfied ensures EXACTLY ONE ``vtkMRMLResectogramDisplayNode`` on the
     selected surface (``AddAndObserveDisplayNodeID`` when none present);
     re-triggering reuses it (idempotent -- no second display node).  This is
     net-new production behaviour: today only the
     ``Resectogram4x4BlurOff`` scenario builder attaches the display node
     (scenarios/Resectogram4x4BlurOff.py ``_attach_resectogram_display_node``).

  3. VIEW-NODE IDEMPOTENCY.  The action ensures the singleton resectogram view
     node via ``ResectogramViewManager.ensureViewNode()``
     (LiverResectionsLib/ResectogramViewManager.py); re-triggering reuses it
     -- no second ``vtkMRMLViewNode`` carrying RESECTOGRAM_VIEW_SINGLETON_TAG.

The action adds ONLY a display node + a view node + leans on the already-
registered ResectogramPipeline creator: NO custom DisplayableManager
(ADR-0013 §5; the ``feedback_layerdm_no_custom_dm`` lesson).  Binding the
singleton view node into a visible custom LAYOUT slot (the side-panel
qMRMLThreeDWidget placement) is OUT of g3 scope; these tests stop at
"display node ensured + view node ensured".

-- WHY THIS IS A LAUNCHED-SLICER PYTEST (NOT A ctkTest) --

A C++ ctkTest against the widget cannot COMPILE before the widget class
exists, which would break the build during the RED phase.  A Python launched
test instead SKIPS CLEANLY (no widget rep / no accessor / module not
registered) pre-implementation and goes GREEN post -- the ADR-0027
§Conformance "for skipped tests, the skip lifts at the implementation commit"
shape.  A C++ generic widget test may accompany the IMPLEMENTATION later.

Reaching the GUI: ``slicer.modules.liverresections.widgetRepresentation()``.
The combo box + button are located by objectName (see the implementer
contract below); a thin Python-accessible helper API is preferred where
direct child-finding is brittle.

Dual harness (ADR-0008 §1, §6): runs meaningfully under the launched-Slicer
``pytest_launched`` row (Liver/Testing/Python/run_pytest_launched.py; this
dir is already on its test roots) and SKIPS CLEANLY under bare
``PythonSlicer -m pytest`` via the shared guards.  Every skip prints an
explicit, greppable reason -- never silently green (the #460 launched-harness
lesson).  The ``_launched_scene_cleanup`` fixture in this dir's conftest tears
down minted nodes so the launched harness does not trip ``vtkDebugLeaks``.

-- IMPLEMENTER CONTRACT (assumed objectNames + entry points) --

  * ``qSlicerLiverResectionsModuleWidget`` -- the net-new C++ widget returned
    by ``createWidgetRepresentation()``.
  * objectName ``"ResectionSurfaceComboBox"`` -- the
    ``qMRMLNodeComboBox`` of ``vtkMRMLMarkupsBezierSurfaceNode`` selecting the
    active resection.
  * objectName ``"OpenResectogramViewButton"`` -- the [Open resectogram
    view] ``QPushButton`` / ``QToolButton`` carrying the gated action.
  * The button's ``enabled`` state realises the gating predicate, and its
    ``toolTip`` explains the disabled reason (ADR-0009 §"explainable disabled
    state").
  * Triggering = ``button.click()`` (or invoking the wired QAction).
  * The action's display-node-ensure entry point keys on the
    combo-box-selected ``vtkMRMLMarkupsBezierSurfaceNode`` and calls
    ``ResectogramViewManager.ensureViewNode()`` once.

If the implementer cannot expose stable objectNames, a thin Python-accessible
API on the widget (e.g. ``widget.setActiveResectionNode(node)`` /
``widget.isOpenResectogramViewEnabled()`` / ``widget.openResectogramView()``)
satisfies the same invariants -- the helpers below probe both shapes and skip
with explicit guidance if neither is present.

See also:
  * Docs/adr/0027-invariant-test-first-v2-implementation.md (red->green)
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4 (the GUI surface)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5 (no custom DM)
  * Docs/adr/0009-ux-and-design-discipline.md (explainable disabled state)
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
# invariant is the gating behaviour, not the spelling -- if these change, the
# helpers below skip with explicit guidance rather than silently passing.
COMBO_BOX_OBJECT_NAME = "ResectionSurfaceComboBox"
OPEN_BUTTON_OBJECT_NAME = "OpenResectogramViewButton"


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each test.
# --------------------------------------------------------------------------- #


def _purge_resectogram_singleton_view():
    """Remove any view node carrying the resectogram singleton tag.

    No-op under bare pytest (no ``slicer``) or before the manager is
    importable.
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
    stale = []
    total = scene.GetNumberOfNodesByClass(VIEW_NODE_CLASS)
    for index in range(total):
        node = scene.GetNthNodeByClass(index, VIEW_NODE_CLASS)
        if (
            node is not None
            and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG
        ):
            stale.append(node)
    for node in stale:
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
    """Return the module's widget representation, or skip cleanly.

    RED pre-implementation: ``createWidgetRepresentation()`` returns
    ``nullptr`` today, so ``widgetRepresentation()`` is ``None`` and the test
    skips.  The skip lifts when the net-new ``qSlicerLiverResectionsModuleWidget``
    lands (ADR-0027 §Conformance).
    """
    from slicer_pytest_support import require_qt_widget

    require_qt_widget()
    module = _module_or_skip(slicer)
    rep = module.widgetRepresentation()
    if rep is None:
        pytest.skip(
            "LiverResections has no widget representation -- "
            "createWidgetRepresentation() still returns nullptr.  T3-g3 adds "
            "the module's first GUI (qSlicerLiverResectionsModuleWidget, "
            "ADR-0023 §Stage-4); the skip lifts when it lands."
        )
    return rep


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


def _open_button(widget):
    """Return the [Open resectogram view] button by objectName, or ``None``.

    Probes both the direct objectName and a thin Python-accessible getter so
    the implementer has two ways to satisfy the contract.
    """
    import qt  # type: ignore[import-not-found]

    button = widget.findChild(qt.QAbstractButton, OPEN_BUTTON_OBJECT_NAME)
    if button is not None:
        return button
    getter = getattr(widget, "openResectogramViewButton", None)
    if callable(getter):
        return getter()
    return getattr(widget, "OpenResectogramViewButton", None)


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
    """Skip unless both the combo box and the open button are findable.

    The pinned invariant is the gating behaviour; if neither the objectName
    nor a Python-accessible getter resolves the controls, skip with guidance
    rather than failing -- the implementer wires one of the two shapes.
    """
    combo = _combo_box(widget)
    button = _open_button(widget)
    if combo is None or button is None:
        pytest.skip(
            "T3-g3 widget chrome not found: expected a "
            f"qMRMLNodeComboBox objectName={COMBO_BOX_OBJECT_NAME!r} and a "
            f"button objectName={OPEN_BUTTON_OBJECT_NAME!r} (or the "
            "Python-accessible getters resectionSurfaceComboBox / "
            "openResectogramViewButton).  Skip lifts when the implementer "
            "wires the controls (ADR-0023 §Stage-4)."
        )
    return combo, button


def _select_active_resection(widget, combo, node):
    """Select ``node`` as the active resection on the widget.

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


def _trigger_open(widget, button):
    """Trigger the open-resectogram-view action.

    Prefers a thin Python API (``openResectogramView``); falls back to a
    button click.
    """
    action = getattr(widget, "openResectogramView", None)
    if callable(action):
        action()
        return
    button.click()


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
# Invariant 1 -- predicate gating (the load-bearing, GPU-free invariant).
# --------------------------------------------------------------------------- #


def test_open_action_disabled_when_no_surface_selected():
    """No active resection selected => the open action is DISABLED.

    ADR-0023 §Stage-4 gating predicate (enabled-iff): the action requires a
    selected Bezier surface.  With the combo box cleared, the button is
    disabled.  RED until the widget + gate land (skips pre-implementation).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    # Clear any selection: select no node.
    if not _select_active_resection(widget, combo, None):
        pytest.skip(
            "neither setActiveResectionNode(None) nor combo.setCurrentNode "
            "is available to clear the selection (implementer contract)."
        )

    assert not button.enabled, (
        "the [Open resectogram view] action must be DISABLED when no Bezier "
        "surface is selected (ADR-0023 §Stage-4 gating predicate)."
    )


def test_open_action_disabled_when_surface_has_no_distance_map():
    """Surface selected but no distance map => the open action is DISABLED.

    ADR-0023 §Stage-4 gating predicate: enabled-iff a surface is selected AND
    ``GetDistanceMapVolumeNode() != nullptr`` (vtkMRMLMarkupsBezierSurfaceNode.h
    line 91).  A surface without a distance map keeps the action disabled --
    the merged resectogram stack has nothing to sample.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_without_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert bezier.GetDistanceMapVolumeNode() is None  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract: "
            "setActiveResectionNode / combo.setCurrentNode)."
        )

    assert not button.enabled, (
        "the [Open resectogram view] action must be DISABLED when the "
        "selected surface has no distance map "
        "(GetDistanceMapVolumeNode() is None) -- ADR-0023 §Stage-4."
    )


def test_open_action_enabled_when_surface_has_distance_map():
    """Surface with a distance map selected => the open action is ENABLED.

    ADR-0023 §Stage-4 gating predicate: the positive branch.  State-ORTHOGONAL
    -- the gate does NOT read ADR-0019 ResectionState, so a distance-mapped
    surface enables the action regardless of Planning/Confirmed state.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert bezier.GetDistanceMapVolumeNode() is not None  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract: "
            "setActiveResectionNode / combo.setCurrentNode)."
        )

    assert button.enabled, (
        "the [Open resectogram view] action must be ENABLED when a Bezier "
        "surface WITH a distance map is selected (ADR-0023 §Stage-4 gating "
        "predicate, positive branch)."
    )


def test_open_action_disabled_state_is_explainable_via_tooltip():
    """The disabled action carries a non-empty tooltip explaining why.

    ADR-0009 §"explainable disabled state": a disabled affordance must say why
    it is disabled.  Cheap to pin -- the tooltip is non-empty in the
    no-distance-map disabled case.  RED until the implementer wires the
    tooltip alongside the gate.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_without_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )

    assert not button.enabled  # precondition for this assertion
    assert button.toolTip, (
        "a disabled [Open resectogram view] action must carry a non-empty "
        "tooltip explaining the disabled reason (ADR-0009 §explainable "
        "disabled state) -- e.g. 'select a resection with a distance map'."
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
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert _count_resectogram_display_nodes(slicer, bezier) == 0  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) on a distance-mapped "
            "surface -- the gating predicate is not yet wired; covered by "
            "test_open_action_enabled_when_surface_has_distance_map."
        )

    _trigger_open(widget, button)

    assert _count_resectogram_display_nodes(slicer, bezier) == 1, (
        "triggering the open action must ensure EXACTLY ONE "
        f"{RESECTOGRAM_DISPLAY_CLASS} on the selected surface "
        "(AddAndObserveDisplayNodeID when none present) -- ADR-0023 §Stage-4."
    )


def test_retrigger_reuses_display_node_no_duplicate():
    """Re-triggering does NOT create a second resectogram display node.

    ADR-0023 §Stage-4: the ensure step is idempotent -- a surface that already
    carries a ``vtkMRMLResectogramDisplayNode`` is reused, not duplicated.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) -- covered by the gating "
            "tests; idempotency cannot be exercised until the gate is wired."
        )

    _trigger_open(widget, button)
    first_count = _count_resectogram_display_nodes(slicer, bezier)
    _trigger_open(widget, button)
    second_count = _count_resectogram_display_nodes(slicer, bezier)

    assert first_count == 1, (
        "first trigger must leave exactly one resectogram display node "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-triggering must REUSE the existing resectogram display node, not "
        f"create a second ({second_count} present after the 2nd trigger) -- "
        "ADR-0023 §Stage-4 idempotent ensure."
    )


# --------------------------------------------------------------------------- #
# Invariant 3 -- view-node idempotency (singleton-by-tag).
# --------------------------------------------------------------------------- #


def test_trigger_ensures_singleton_resectogram_view_node():
    """Triggering ensures the singleton resectogram view node exists.

    ADR-0023 §Stage-4: the action calls
    ``ResectogramViewManager.ensureViewNode()`` -- after one trigger exactly
    one ``vtkMRMLViewNode`` carries RESECTOGRAM_VIEW_SINGLETON_TAG.
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    assert _count_singleton_view_nodes(slicer) == 0  # fixture sanity

    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) -- the gating predicate is "
            "not yet wired; covered by the Invariant 1 tests."
        )

    _trigger_open(widget, button)

    assert _count_singleton_view_nodes(slicer) == 1, (
        "triggering the open action must ensure exactly one "
        "resectogram-tagged vtkMRMLViewNode via "
        "ResectogramViewManager.ensureViewNode() -- ADR-0023 §Stage-4."
    )


def test_retrigger_reuses_view_node_no_duplicate():
    """Re-triggering reuses the singleton view node -- no second view node.

    ADR-0023 §Stage-4 + ResectogramViewManager singleton-by-tag: a second
    trigger re-targets the existing tagged view node rather than minting a
    duplicate (the singleton-tag mechanism the Slicer view machinery
    enforces).
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip(
            "cannot select the active resection (implementer contract)."
        )
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) -- covered by the Invariant "
            "1 tests; view-node idempotency cannot be exercised until the "
            "gate is wired."
        )

    _trigger_open(widget, button)
    first_count = _count_singleton_view_nodes(slicer)
    _trigger_open(widget, button)
    second_count = _count_singleton_view_nodes(slicer)

    assert first_count == 1, (
        "first trigger must leave exactly one resectogram-tagged view node "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-triggering must REUSE the singleton resectogram view node, not "
        f"create a second ({second_count} present after the 2nd trigger) -- "
        "ResectogramViewManager.ensureViewNode() is singleton-by-tag "
        "(ADR-0023 §Stage-4)."
    )


# --------------------------------------------------------------------------- #
# Invariant 4 -- the open action embeds ONE qMRMLThreeDWidget bound to the
# singleton resectogram view node into the module panel (T3-g3b).
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
    """Return the module panel's ``qMRMLThreeDWidget`` children.

    The embedded resectogram view widget is a ``qMRMLThreeDWidget`` (a C++
    class); the open action adds exactly one to the module panel (ADR-0023
    §Stage-4, the SlicerHyperProbe ``create_three_d_widget`` precedent).
    """
    import qt  # type: ignore[import-not-found]

    return [
        child
        for child in widget.findChildren(slicer.qMRMLThreeDWidget)
        if isinstance(child, qt.QWidget)
    ]


def test_trigger_embeds_three_d_widget_bound_to_singleton_view_node():
    """Triggering embeds one qMRMLThreeDWidget bound to the singleton view.

    ADR-0023 §Stage-4: with the gate satisfied, the open action places a single
    ``qMRMLThreeDWidget`` in the module panel whose ``mrmlViewNode()`` IS the
    resectogram singleton view node (identity by node ID).  GPU-free -- pins the
    widget tree + node identity, not the GL render (the orchestrator's eyeball).
    """
    slicer = _slicer_or_skip()
    _require_main_window_or_skip(slicer)
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip("cannot select the active resection (implementer contract).")
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) -- covered by the Invariant "
            "1 tests; the embedded view widget cannot be exercised until the "
            "gate is wired."
        )

    _trigger_open(widget, button)

    embedded = _resectogram_three_d_widgets(slicer, widget)
    assert len(embedded) == 1, (
        "triggering the open action must embed EXACTLY ONE qMRMLThreeDWidget "
        f"in the module panel (got {len(embedded)}) -- ADR-0023 §Stage-4."
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


def test_retrigger_reuses_three_d_widget_no_duplicate():
    """Re-triggering does NOT add a second qMRMLThreeDWidget.

    ADR-0023 §Stage-4: the embed step is idempotent -- a re-open shows/raises
    the existing panel widget rather than minting a second one (mirroring the
    singleton view-node + display-node idempotency).
    """
    slicer = _slicer_or_skip()
    _require_main_window_or_skip(slicer)
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, button = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip("cannot select the active resection (implementer contract).")
    if not button.enabled:
        pytest.skip(
            "gate not satisfied (button disabled) -- covered by the Invariant "
            "1 tests; embed idempotency cannot be exercised until the gate is "
            "wired."
        )

    _trigger_open(widget, button)
    first_count = len(_resectogram_three_d_widgets(slicer, widget))
    _trigger_open(widget, button)
    second_count = len(_resectogram_three_d_widgets(slicer, widget))

    assert first_count == 1, (
        "first trigger must embed exactly one qMRMLThreeDWidget "
        "(ADR-0023 §Stage-4)."
    )
    assert second_count == 1, (
        "re-triggering must REUSE the embedded qMRMLThreeDWidget, not add a "
        f"second ({second_count} present after the 2nd trigger) -- "
        "ADR-0023 §Stage-4 idempotent embed."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
