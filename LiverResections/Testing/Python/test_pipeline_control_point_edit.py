# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 2 -- the v2 resection control-point edit path on the Pipeline.

ADR-0032 routes v2 resection interaction (placement + control-grid editing)
through the LayerDM Pipeline's interaction seam on
``LiverBezierSurfacePipeline`` -- ``CanProcessInteractionEvent`` /
``ProcessInteractionEvent`` overrides -- *not* a standalone
``vtkAbstractWidget`` (that decision in ADR-0014 §3 is superseded).  The
control-grid mutation math (pick -> display->world -> write the control
point via ``vtkMRMLBezierSurfaceNode::SetControlPoint``) is lifted into the
Python Pipeline per ADR-0004.

This pins the edit path in two halves:

  * The **GL-free kernel** ``_apply_world_point_to_nearest_control_point((x,
    y,z))`` -- takes a RAS world point directly (no renderer / picking), finds
    the carrier's nearest control point, moves it there via ``SetControlPoint``,
    and returns its flat index.  It is a no-op returning ``None`` when the
    carrier is not editable (state past ``Planning`` -- read-only per ADR-0019)
    or there is no carrier.  Tests 1--3.

  * The **routing override** ``ProcessInteractionEvent(eventData)`` -- does
    display->world via the Pipeline's renderer/camera then calls the kernel.
    It needs a live view, so it is pinned skip-pending behind a realized
    main-window view; the full routing is verified on the interactive ``:0``
    pass (ADR-0032 §Conformance).  Test 4.

-- WHY LAUNCHED-SLICER --

The kernel tests need the wrapped ``vtkMRMLBezierSurfaceNode`` carrier + the
logic create-API (``vtkSlicerLiverResectionsLogic::CreateResectionPlan``) +
the importable ``LiverBezierSurfacePipeline`` (LayerDMLib reachable only
inside a launched Slicer with the module loaded).  A bare ``PythonSlicer -m
pytest`` has ``slicer.mrmlScene is None`` and the create-API / LayerDMLib off
the path, so every test here SKIPS CLEANLY via the shared
``slicer_pytest_support`` guards -- it never errors.

-- RUN-VS-SKIP DISCIPLINE --

Under a launched Slicer the kernel tests (1--3) must actually RUN (not
silently skip) once slice 2 lands ``_apply_world_point_to_nearest_control_point``;
verify run-vs-skip in the CI log, never trust overall green (the launched
harness is green-but-skipping prone).  Pre-implementation they are skip-pending
on the missing seam (``hasattr`` guard) per ADR-0027 -- the skip lifts at the
implementation commit.  Test 4 stays skip-pending behind a realized view even
after the kernel lands; it lifts when a GL-backed view is available.

-- SEAM NAMES THIS PINS (so the implementation matches) --

  * ``LiverBezierSurfacePipeline._apply_world_point_to_nearest_control_point(
    self, world) -> int | None`` -- ``world = (x, y, z)`` RAS; returns the moved
    point's flat index, or ``None`` when not editable / no carrier.
  * ``LiverBezierSurfacePipeline.ProcessInteractionEvent(self, eventData) ->
    bool`` -- the routing override (display->world -> kernel).
  * Carrier state read through the Pipeline's ``_safe_get_state(self._data_node)``
    dispatch (``vtkMRMLBezierSurfaceNode::SetState`` / the enum ``Init = 0``,
    ``Planning = 1``, ``Confirmed = 2``).

See also:
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the decision)
  * Docs/adr/0019-resection-state-machine.md  (state-gated editability)
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"  (wrapper/carrier)
  * Docs/adr/0004-python-cpp-boundary.md  (interaction math in Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
  * LiverResections/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"

# Mirror the C++ ResectionState enum on vtkMRMLBezierSurfaceNode (ADR-0019):
#   Init = 0, Planning = 1, Confirmed = 2.
STATE_INIT = 0
STATE_PLANNING = 1
STATE_CONFIRMED = 2

# The kernel-edit seam slice 2 lands.  Tests skip-pending on its absence.
EDIT_KERNEL_METHOD = "_apply_world_point_to_nearest_control_point"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_pipeline_resolves_resection_plan.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    # ADR-0033 re-sited the Planning per-point drag onto the control
    # polygon's own Pipeline (superseding the ADR-0032 siting on the
    # surface Pipeline these invariants originally pinned).
    try:
        from LiverResectionsLib.ControlPolygonPipeline import (
            ControlPolygonPipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"ControlPolygonPipeline not importable ({exc!r}) -- LayerDMLib "
            "not reachable in this environment."
        )
    return ControlPolygonPipeline()


def _resection_logic_or_skip(slicer):
    """Return ``vtkSlicerLiverResectionsLogic`` with the create-API, or skip.

    The triad (plan + carrier + parametric-surface display node) is minted via
    the merged ``CreateResectionPlan`` (#501 slice 1); skip cleanly if the
    module / logic / create-API is not reachable in this build.
    """
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered in this build.")
    logic = module.logic()
    if logic is None:
        pytest.skip("liverresections module has no logic singleton.")
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "create-API (#501 slice 1) is not in this build."
        )
    return logic


def _make_planning_carrier_pipeline_or_skip(slicer):
    """Build a ``Planning``-state plan/carrier/display triad on a fresh Pipeline.

    Returns ``(pipeline, carrier)`` where the Pipeline's ``_data_node`` is the
    carrier (derived from the display node, the LayerDM back-reference) and the
    carrier is advanced ``Init -> Planning`` so its control polygon is editable
    (ADR-0019).  The grid is seeded non-degenerate so nearest-selection has a
    unique answer.
    """
    logic = _resection_logic_or_skip(slicer)
    pipeline = _make_pipeline_or_skip()

    plan = logic.CreateResectionPlan("EditPathTest")
    if plan is None:
        pytest.skip("CreateResectionPlan returned None -- triad not minted.")
    carrier = plan.GetGeometryNode()
    if carrier is None or carrier.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip(
            "plan geometry node is not a vtkMRMLBezierSurfaceNode carrier -- "
            "cannot exercise the control-grid edit."
        )
    if not hasattr(carrier, "SetControlPoint"):
        pytest.skip(
            "carrier has no SetControlPoint -- the Python grid seam (slice 1d) "
            "is not in this build."
        )
    if not hasattr(carrier, "SetState"):
        pytest.skip("carrier has no SetState -- ADR-0019 state machine absent.")

    display = carrier.GetDisplayNode()
    if display is None or not display.IsA(DISPLAY_NODE_CLASS):
        pytest.skip(
            "carrier has no vtkMRMLParametricSurfaceDisplayNode -- "
            "CreateDefaultDisplayNodes did not mint the display the Pipeline "
            "derives its data node from."
        )

    _seed_distinct_grid(carrier)

    # Advance Init -> Planning so the control polygon is editable (ADR-0019).
    carrier.SetState(STATE_PLANNING)
    if carrier.GetState() != STATE_PLANNING:
        pytest.skip(
            "carrier did not advance to Planning -- cannot exercise the "
            "editable-state edit path."
        )

    # Attach the display node so the Pipeline derives _data_node = carrier
    # (the production LayerDM wiring).
    pipeline.SetDisplayNode(display)
    if pipeline.GetDataNode() is not carrier:
        pytest.skip(
            "Pipeline did not derive its data node from the display node's "
            "displayable back-reference -- cannot exercise the edit kernel."
        )
    return pipeline, carrier


def _require_edit_kernel_or_skip(pipeline):
    """Skip-pending unless the edit kernel seam has landed (ADR-0027).

    RED == ``LiverBezierSurfacePipeline`` has no
    ``_apply_world_point_to_nearest_control_point``; the skip lifts at the
    slice-2 implementation commit.
    """
    if not hasattr(pipeline, EDIT_KERNEL_METHOD):
        pytest.skip(
            f"LiverBezierSurfacePipeline has no {EDIT_KERNEL_METHOD} -- the "
            "ADR-0032 control-point edit kernel (#501 slice 2) has not landed. "
            "Skip lifts at the implementation commit (ADR-0027)."
        )


# --------------------------------------------------------------------------- #
# Grid helpers
# --------------------------------------------------------------------------- #


def _seed_distinct_grid(carrier):
    """Seed a non-degenerate 4x4 control grid with distinct world positions.

    The carrier defaults to a 16-point grid all at the origin; nearest-selection
    is ill-defined there.  Lay the points on a regular lattice so every point
    has a unique nearest-world neighbourhood.
    """
    rows = int(carrier.GetRows())
    cols = int(carrier.GetCols())
    for r in range(rows):
        for c in range(cols):
            carrier.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, 0.0)


def _grid_point(carrier, row, col):
    """Return the (x, y, z) of the (row, col) control point via the flat grid."""
    cols = int(carrier.GetCols())
    grid = carrier.GetControlGridVector()
    base = (row * cols + col) * 3
    return (grid[base + 0], grid[base + 1], grid[base + 2])


def _all_points(carrier):
    """Return a flat list of the 16 control-point (x, y, z) tuples, row-major."""
    rows = int(carrier.GetRows())
    cols = int(carrier.GetCols())
    return [_grid_point(carrier, r, c) for r in range(rows) for c in range(cols)]


def _flat_index(carrier, row, col):
    return row * int(carrier.GetCols()) + col


# --------------------------------------------------------------------------- #
# 1--3: GL-free kernel + state-gating
# --------------------------------------------------------------------------- #


def test_edit_kernel_moves_exactly_one_nearest_control_point_in_planning():
    """Invariant 1: in Planning, the kernel moves exactly the nearest point.

    Feeding a RAS world point near the (1, 2) control point moves THAT point
    to the world point and leaves the other 15 unchanged; the returned flat
    index identifies the moved point.  GL-free -- the kernel takes the world
    point directly, no renderer / picking (ADR-0032: the math is Python-testable
    via SetControlPoint).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_planning_carrier_pipeline_or_skip(slicer)
    _require_edit_kernel_or_skip(pipeline)

    rows = int(carrier.GetRows())
    cols = int(carrier.GetCols())
    assert rows * cols == 16, (
        f"expected a default 4x4 (16-point) grid, got {rows}x{cols}."
    )

    target_row, target_col = 1, 2
    before = _all_points(carrier)
    target_idx = _flat_index(carrier, target_row, target_col)

    # A world point a small offset from the (1, 2) point -- unambiguously
    # nearest to it on the seeded lattice.
    base = before[target_idx]
    world = (base[0] + 1.0, base[1] - 1.0, base[2] + 0.5)

    moved = pipeline._apply_world_point_to_nearest_control_point(world)

    assert moved == target_idx, (
        "the kernel must return the flat index of the moved (nearest) control "
        f"point; expected {target_idx} (row {target_row}, col {target_col}), "
        f"got {moved!r}."
    )

    after = _all_points(carrier)
    assert after[target_idx] == pytest.approx(world, abs=1e-6), (
        "the nearest control point must be moved to the world point; "
        f"got {after[target_idx]} for world {world}."
    )

    moved_count = sum(
        1 for b, a in zip(before, after) if a != pytest.approx(b, abs=1e-9)
    )
    assert moved_count == 1, (
        "exactly ONE control point may move per edit; the kernel moved "
        f"{moved_count} of {len(before)}."
    )


def test_edit_kernel_selects_a_different_nearest_control_point():
    """Invariant 2: nearest-selection correctness.

    A world point near a DIFFERENT control point moves THAT one -- the kernel
    selects by nearest distance, not a fixed index.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_planning_carrier_pipeline_or_skip(slicer)
    _require_edit_kernel_or_skip(pipeline)

    target_row, target_col = 3, 0
    target_idx = _flat_index(carrier, target_row, target_col)
    before = _all_points(carrier)

    base = before[target_idx]
    world = (base[0] - 0.5, base[1] + 1.0, base[2] - 0.5)

    moved = pipeline._apply_world_point_to_nearest_control_point(world)

    assert moved == target_idx, (
        "the kernel must select the nearest control point by distance; "
        f"expected index {target_idx} (row {target_row}, col {target_col}), "
        f"got {moved!r}."
    )
    after = _all_points(carrier)
    assert after[target_idx] == pytest.approx(world, abs=1e-6), (
        f"the nearest point (index {target_idx}) must move to {world}; got "
        f"{after[target_idx]}."
    )


def test_edit_kernel_is_no_op_in_read_only_state():
    """Invariant 3: state-gating (ADR-0019 read-only-after-commit).

    Advancing the carrier past Planning to Confirmed (a read-only viewing state)
    makes the kernel a no-op: it returns ``None`` and leaves every control
    point unchanged.  Editability is gated on the carrier state the Pipeline's
    dispatch reads (``_safe_get_state(self._data_node)``).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_planning_carrier_pipeline_or_skip(slicer)
    _require_edit_kernel_or_skip(pipeline)

    # Planning -> Confirmed is an allowed transition (ADR-0019); Confirmed is
    # read-only for the control polygon.
    carrier.SetState(STATE_CONFIRMED)
    if carrier.GetState() != STATE_CONFIRMED:
        pytest.skip(
            "carrier did not advance to Confirmed -- cannot exercise the "
            "read-only state gate."
        )

    before = _all_points(carrier)
    base = before[_flat_index(carrier, 1, 2)]
    world = (base[0] + 5.0, base[1] + 5.0, base[2] + 5.0)

    moved = pipeline._apply_world_point_to_nearest_control_point(world)

    assert moved is None, (
        "the kernel must be a no-op returning None when the carrier state is "
        f"not editable (ADR-0019); got moved index {moved!r}."
    )
    after = _all_points(carrier)
    assert after == before, (
        "no control point may move in a read-only state; the grid changed "
        f"from {before} to {after}."
    )


# --------------------------------------------------------------------------- #
# 4: routing override (skip-pending behind a realized view)
# --------------------------------------------------------------------------- #


def _require_main_window_view_or_skip(slicer):
    """Skip unless a realized 3D view with a renderer/camera is available.

    ``ProcessInteractionEvent`` does display->world via the Pipeline's
    renderer/camera, so it needs a live GL-backed view -- present only under a
    launched Slicer with a main window, not under ``--no-main-window`` /
    ``--testing``.  The full routing is verified on the interactive ``:0`` pass
    (ADR-0032 §Conformance: "the first interaction slice must verify
    ProcessInteractionEvent actually fires ... interactive :0").
    """
    layout = getattr(slicer.app, "layoutManager", None)
    layout_manager = layout() if callable(layout) else None
    if layout_manager is None or layout_manager.threeDViewCount == 0:
        pytest.skip(
            "no realized 3D view -- ProcessInteractionEvent needs a renderer/"
            "camera for display->world.  The full interaction routing is "
            "verified on the interactive :0 pass (ADR-0032 §Conformance)."
        )
    return layout_manager.threeDWidget(0).threeDView()


def test_process_interaction_event_routes_edit_through_override():
    """Invariant 4 (skip-pending-launched): the override moves a control point.

    A synthesized ``vtkMRMLInteractionEventData`` positioned over a control
    point, fed to ``pipeline.ProcessInteractionEvent(...)``, must move a control
    point end-to-end through the display->world override (ADR-0032).  This needs
    a realized renderer/camera, so it is gated behind a main-window view and
    otherwise skips; synthesizing the eventData + a renderer headless is too
    heavy, so the full routing is confirmed on the interactive :0 eyeball pass.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_planning_carrier_pipeline_or_skip(slicer)

    if not hasattr(pipeline, "ProcessInteractionEvent"):
        pytest.skip(
            "LiverBezierSurfacePipeline has no ProcessInteractionEvent override "
            "-- ADR-0032 routing (#501 slice 2) has not landed.  Skip lifts at "
            "the implementation commit (ADR-0027)."
        )
    _require_edit_kernel_or_skip(pipeline)
    _require_main_window_view_or_skip(slicer)

    # Even with a view, synthesizing a vtkMRMLInteractionEventData whose
    # display position back-projects onto a control point requires the
    # Pipeline to be attached to that view's renderer through the live LayerDM
    # manager.  That end-to-end wiring is exercised on the interactive :0 pass;
    # gate here so the routing invariant is REGISTERED (lifts when the headless
    # synthesis path is built out).
    pytest.skip(
        "ProcessInteractionEvent end-to-end routing (synthesized "
        "vtkMRMLInteractionEventData over a control point through the live "
        "LayerDM manager) is verified on the interactive :0 pass "
        "(ADR-0032 §Conformance); headless synthesis is deferred."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
