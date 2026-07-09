# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Logic-side locator SINGLETON invariant -- ``EnsureLocatorNode`` (ADR-0025 §Consumer).

Pins a NEW C++ method on ``vtkSlicerLiverResectionsLogic`` (to be implemented
later; ADR-0014 the wrapper/carrier + logic layer, ADR-0004 the C++/Python
boundary) --

    vtkMRMLLocatorNode* EnsureLocatorNode();

It resolve-or-creates the ONE cross-view ``vtkMRMLLocatorNode`` the v2.0
architecture allows (ADR-0025 §Consumer: "v2.0 has exactly one"), so every
consumer that reverse-resolves via ``GetFirstNodeByClass("vtkMRMLLocatorNode")``
sees a single, deterministic node.  The method is idempotent -- resolve via
``GetFirstNodeByClass`` else mint via ``AddNewNodeByClass`` -- mints + wires a
``vtkMRMLLocatorDisplayNode`` (default ``Radius`` = 2.0) through
``CreateDefaultDisplayNodes()``, sets ``LocatorActive`` = true, and returns the
node (``nullptr`` when the logic has no scene).  ``CreateResectionPlan`` calls it
too, so opening a plan guarantees the locator exists.

Three invariants:

  1. ``EnsureLocatorNode`` creates EXACTLY ONE locator: after the call the scene
     has a single ``vtkMRMLLocatorNode``, it carries a
     ``vtkMRMLLocatorDisplayNode`` with ``Radius`` > 0, and ``LocatorActive`` is
     true (ADR-0025 §Consumer, §"The node").
  2. Idempotent: a SECOND call returns the SAME node (same ``GetID()``) and mints
     no second node -- the singleton invariant holds under repeat calls
     (ADR-0025 §Consumer).
  3. ``CreateResectionPlan`` ensures the locator: opening a plan from a
     locator-free state leaves >= 1 locator; a second plan does not add another
     (still exactly one).

-- WHY LAUNCHED-SLICER --
Needs the registered ``liverresections`` module + its logic singleton (bound to
``slicer.mrmlScene``) and the wrapped ``vtkMRMLLocatorNode`` /
``vtkMRMLLocatorDisplayNode``, reachable only inside a launched Slicer with the
module loaded.  Skips cleanly under bare ``PythonSlicer -m pytest`` via the
shared ``slicer_pytest_support`` guards.  GL-free: no view / render window is
realised -- only node + display-node state is asserted.

-- WHY RED NOW --
``EnsureLocatorNode`` is not yet on the logic, so every test skips-pending on
``hasattr(logic, "EnsureLocatorNode")``.  The skip lifts at the implementation
commit, at which point the tests ASSERT (ADR-0027 §Conformance).

-- SHARED-SCENE DETERMINISM --
All launched tests share ONE process + scene, so the scene does NOT start empty.
Each test removes any pre-existing ``vtkMRMLLocatorNode`` (+ its display node) up
front so "exactly one" is deterministic, tracks the nodes it caused to be
created, and tears them down at the end so the launched leak discipline holds
(``conftest._launched_scene_cleanup``) and later tests are unaffected.

See also:
  * Docs/adr/0025-locator-architecture.md §Consumer, §"The node"
  * Docs/adr/0027-invariant-test-first-v2-implementation.md  (RED / skip-pending)
  * Docs/adr/0014-mrml-node-architecture.md
  * Docs/adr/0004-python-cpp-boundary.md
  * LiverResections/MRML/vtkMRMLLocatorNode.h
  * LiverResections/MRML/vtkMRMLLocatorDisplayNode.h
  * LiverResections/Logic/vtkSlicerLiverResectionsLogic.h
  * LiverResections/Testing/Python/test_pipeline_resolves_locator.py
  * LiverResections/Testing/Python/test_resectogram_locator_pipeline_seam.py
"""

from __future__ import annotations

import pytest

LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"
LOCATOR_DISPLAY_NODE_CLASS = "vtkMRMLLocatorDisplayNode"

# The NEW logic method under test.  Every test skips-pending on its absence.
ENSURE_METHOD = "EnsureLocatorNode"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_resectogram_locator_pipeline_seam.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _resection_logic_or_skip(slicer):
    """Return the ``vtkSlicerLiverResectionsLogic`` singleton, or skip cleanly."""
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered in this build.")
    logic = module.logic()
    if logic is None:
        pytest.skip("liverresections module has no logic singleton.")
    return logic


def _ensure_method_or_skip_pending(logic):
    """Return the bound ``EnsureLocatorNode`` method or SKIP-PENDING (ADR-0027).

    RED == the method is absent (not built yet); the skip lifts at the
    implementation commit, at which point the tests ASSERT.
    """
    method = getattr(logic, ENSURE_METHOD, None)
    if not callable(method):
        pytest.skip(
            f"vtkSlicerLiverResectionsLogic.{ENSURE_METHOD} not present -- the "
            "ADR-0025 §Consumer locator-singleton method has not landed.  Skip "
            "lifts at the implementation commit (ADR-0027)."
        )
    return method


def _clear_existing_locators(slicer):
    """Remove every pre-existing ``vtkMRMLLocatorNode`` (+ its display node).

    The launched harness shares one scene across tests, so a prior test may
    have left a locator; strip them so "exactly one" is deterministic for this
    test.  Display nodes are removed alongside so a leaked display node cannot
    survive to the ``_launched_scene_cleanup`` baseline check either.
    """
    scene = slicer.mrmlScene
    locators = [
        scene.GetNthNodeByClass(i, LOCATOR_NODE_CLASS)
        for i in range(scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS))
    ]
    for locator in locators:
        _remove_locator(scene, locator)


def _remove_locator(scene, locator):
    """Remove a locator node and its display node(s) from the scene."""
    if locator is None:
        return
    for i in range(locator.GetNumberOfDisplayNodes()):
        display = locator.GetNthDisplayNode(i)
        if display is not None:
            scene.RemoveNode(display)
    scene.RemoveNode(locator)


def _remove_plan(scene, plan):
    """Remove a resection-plan wrapper + its Bezier carrier from the scene."""
    if plan is None:
        return
    if hasattr(plan, "GetGeometryNode"):
        carrier = plan.GetGeometryNode()
        if carrier is not None:
            scene.RemoveNode(carrier)
    scene.RemoveNode(plan)


# --------------------------------------------------------------------------- #
# Invariant 1 -- EnsureLocatorNode mints exactly one, wired + active
# --------------------------------------------------------------------------- #


def test_ensure_locator_node_creates_exactly_one_wired_active():
    """Invariant 1: ``EnsureLocatorNode`` yields exactly one wired, active node.

    From a locator-free scene, the call must return a non-None
    ``vtkMRMLLocatorNode``, leave EXACTLY ONE in the scene, give it a
    ``vtkMRMLLocatorDisplayNode`` with ``Radius`` > 0 (default 2.0 via
    ``CreateDefaultDisplayNodes()``), and set ``LocatorActive`` = true
    (ADR-0025 §Consumer, §"The node").
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)
    ensure = _ensure_method_or_skip_pending(logic)
    scene = slicer.mrmlScene

    _clear_existing_locators(slicer)
    locator = None
    try:
        locator = ensure()

        assert locator is not None, (
            "EnsureLocatorNode() must return the locator node, not None, when "
            "the logic has a scene (ADR-0025 §Consumer)."
        )
        count = scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)
        assert count == 1, (
            "EnsureLocatorNode() must leave EXACTLY ONE vtkMRMLLocatorNode in "
            f"the scene (v2.0 has exactly one, ADR-0025 §Consumer); got {count}."
        )
        display = locator.GetDisplayNode()
        assert display is not None, (
            "EnsureLocatorNode() must mint + wire a display node via "
            "CreateDefaultDisplayNodes() (ADR-0025 §'The node')."
        )
        assert display.IsA(LOCATOR_DISPLAY_NODE_CLASS), (
            "the wired display node must be a vtkMRMLLocatorDisplayNode; got "
            f"{display.GetClassName()!r}."
        )
        assert display.GetRadius() > 0.0, (
            "the locator display node must carry a positive Radius (default 2.0, "
            f"ADR-0025 §'The node'); got {display.GetRadius()}."
        )
        assert bool(locator.GetLocatorActive()), (
            "EnsureLocatorNode() must set LocatorActive = true (the persisted "
            "presence flag, ADR-0025 §'The node')."
        )
    finally:
        _remove_locator(scene, locator)


def test_ensure_locator_node_display_starts_hidden():
    """Invariant 1b: the ensured locator's display starts HIDDEN.

    The marker is gesture-scoped (the strip press flips the display
    Visibility on; release clears it), so ``EnsureLocatorNode`` must leave
    ``Visibility`` false -- an ensured locator must not paint a stray
    marker before the first pick gesture.
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)
    ensure = _ensure_method_or_skip_pending(logic)
    scene = slicer.mrmlScene

    _clear_existing_locators(slicer)
    locator = None
    try:
        locator = ensure()
        assert locator is not None, "EnsureLocatorNode() returned None."
        display = locator.GetDisplayNode()
        assert display is not None, "no display node wired."
        assert not bool(display.GetVisibility()), (
            "EnsureLocatorNode() must leave the locator display HIDDEN "
            "(gesture-scoped marker: visible only between press and release)."
        )
    finally:
        _remove_locator(scene, locator)


# --------------------------------------------------------------------------- #
# Invariant 2 -- idempotent: the second call returns the same singleton
# --------------------------------------------------------------------------- #


def test_ensure_locator_node_is_idempotent():
    """Invariant 2: a second ``EnsureLocatorNode`` returns the SAME node.

    The method resolve-or-creates (``GetFirstNodeByClass`` else
    ``AddNewNodeByClass``), so a second call must return the same node
    (``GetID()`` unchanged) and mint NO second node -- the singleton invariant
    holds under repeat calls (ADR-0025 §Consumer).
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)
    ensure = _ensure_method_or_skip_pending(logic)
    scene = slicer.mrmlScene

    _clear_existing_locators(slicer)
    first = None
    try:
        first = ensure()
        assert first is not None, "first EnsureLocatorNode() returned None."
        count_after_first = scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)
        assert count_after_first == 1, (
            "the first EnsureLocatorNode() must leave exactly one locator; got "
            f"{count_after_first}."
        )

        second = ensure()
        assert second is not None, "second EnsureLocatorNode() returned None."
        assert second.GetID() == first.GetID(), (
            "a second EnsureLocatorNode() must RESOLVE the existing node (same "
            f"GetID()); got {second.GetID()!r} vs {first.GetID()!r}."
        )
        count_after_second = scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)
        assert count_after_second == 1, (
            "a second EnsureLocatorNode() must NOT mint a second locator (the "
            f"singleton invariant, ADR-0025 §Consumer); got {count_after_second}."
        )
    finally:
        _remove_locator(scene, first)


# --------------------------------------------------------------------------- #
# Invariant 3 -- CreateResectionPlan ensures the locator singleton
# --------------------------------------------------------------------------- #


def test_create_resection_plan_ensures_single_locator():
    """Invariant 3: opening a plan ensures the locator singleton.

    ``CreateResectionPlan`` calls ``EnsureLocatorNode`` internally, so opening a
    plan from a locator-free state leaves >= 1 ``vtkMRMLLocatorNode``, and a
    SECOND plan does not increase the locator count (still exactly one) -- the
    singleton invariant survives multiple plans (ADR-0025 §Consumer).
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)
    _ensure_method_or_skip_pending(logic)
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "resection-plan create-API is not in this build."
        )
    scene = slicer.mrmlScene

    _clear_existing_locators(slicer)
    plans = []
    try:
        first_plan = logic.CreateResectionPlan("EnsureViaPlan")
        if first_plan is None:
            pytest.skip("CreateResectionPlan returned None -- plan not minted.")
        plans.append(first_plan)
        count_after_first = scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)
        assert count_after_first >= 1, (
            "CreateResectionPlan must ensure at least one vtkMRMLLocatorNode "
            f"(it calls EnsureLocatorNode); got {count_after_first}."
        )

        second_plan = logic.CreateResectionPlan("EnsureViaPlanTwo")
        if second_plan is not None:
            plans.append(second_plan)
        count_after_second = scene.GetNumberOfNodesByClass(LOCATOR_NODE_CLASS)
        assert count_after_second == count_after_first, (
            "a second CreateResectionPlan must NOT mint another locator (the "
            f"singleton invariant, ADR-0025 §Consumer); count went from "
            f"{count_after_first} to {count_after_second}."
        )
    finally:
        for plan in plans:
            _remove_plan(scene, plan)
        _clear_existing_locators(slicer)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
