# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 3b -- DistanceSpheroid Init-mode placement on the Pipeline.

ADR-0032 routes v2 resection interaction through the LayerDM Pipeline's
interaction seam on ``LiverBezierSurfacePipeline`` -- not a standalone
``vtkAbstractWidget`` (the ADR-0014 §3 widget decision is superseded).  Slice 2
landed the Planning-state per-control-point EDIT path; slice 3a landed the
**Init-state SlicingPlane PLACEMENT** branch
(``_place_slicing_plane_init_point`` + the ``ProcessInteractionEvent``
Init+SlicingPlane dispatch).  Slice 3b is the exact same shape for the OTHER
init mode: the **Init-state DistanceSpheroid PLACEMENT** branch.  The
``DistanceSpheroidInitRepresentation`` already RENDERS the spheroid init
geometry, but clicking to PLACE the distance-spheroid init points is not wired.

This pins the placement path in two halves:

  * The **GL-free kernel** ``_place_distance_spheroid_init_point((x, y, z))`` --
    takes a RAS world point directly (no renderer / picking).  When the carrier
    is in **Init + DistanceSpheroid** mode, it places the NEXT distance-spheroid
    init point (index 0, 1, ...) at the world point via
    ``vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidInitPoint`` and
    returns that index.  It is a no-op returning ``None`` when the carrier is
    not Init, not DistanceSpheroid mode, has no carrier, or all points are
    already placed.

    Unlike SlicingPlane's FIXED 2-slot array, the DistanceSpheroid init-point
    array is DYNAMICALLY sized: ``GetNumberOfDistanceSpheroidInitPoints()`` /
    ``SetNumberOfDistanceSpheroidInitPoints(n)`` (default ``0``, Init-guarded on
    the Bezier subclass).  So the "full" boundary is capacity-relative, NOT a
    hard-coded count -- these tests configure a known capacity ``N`` on the
    carrier and pin fill-in-order-up-to-``N``-then-refuse against that ``N``
    (they do NOT assume a magic count).  The node holds no on-node placed-count,
    so -- mirroring slice 3a's ``_slicing_plane_points_placed`` discipline --
    the Pipeline tracks placement progress in an instance counter reset on
    ``SetDisplayNode``.  Tests 1--4.

  * The **routing override** ``ProcessInteractionEvent(eventData)`` -- extends
    the slice-2/3a dispatch: Init+DistanceSpheroid -> placement (display->world
    -> the placement kernel), distinct from Init+SlicingPlane placement and from
    the Planning per-point edit.  It needs a live view, so it is pinned
    skip-pending behind a realized main-window view; the full routing (and the
    spheroid centre/radii derivation from the placed points, which is
    camera-coupled) is verified on the interactive ``:0`` pass
    (ADR-0032 §Conformance).  Test 5.

-- GL-FREE VS SKIP-PENDING-LAUNCHED --

Tests 1--4 are GL-free: the kernel takes a world point directly, so they RUN
under a launched Slicer once the kernel lands and never touch a renderer.  Test
5 (the ``ProcessInteractionEvent`` routing) needs a GL-backed view and stays
skip-pending behind a realized main-window view.  The spheroid centre/radii
derivation from the placed points needs the camera/view direction, so it is
GL-coupled and is NOT pinned GL-free here -- it belongs on the :0 pass.

-- WHY LAUNCHED-SLICER --

The kernel tests need the wrapped ``vtkMRMLBezierSurfaceNode`` carrier + the
logic create-API (``vtkSlicerLiverResectionsLogic::CreateResectionPlan``) +
the importable ``LiverBezierSurfacePipeline`` (LayerDMLib reachable only inside
a launched Slicer with the module loaded).  A bare ``PythonSlicer -m pytest``
has ``slicer.mrmlScene is None`` and the create-API / LayerDMLib off the path,
so every test here SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards -- it never errors.

-- RUN-VS-SKIP DISCIPLINE --

Under a launched Slicer the kernel tests (1--4) must actually RUN (not silently
skip) once slice 3b lands ``_place_distance_spheroid_init_point``; verify
run-vs-skip in the CI log, never trust overall green (the launched harness is
green-but-skipping prone).  Pre-implementation they are skip-pending on the
missing seam (``hasattr`` guard) per ADR-0027 -- the skip lifts at the
implementation commit.  Test 5 stays skip-pending behind a realized view even
after the kernel lands; it lifts when a GL-backed view is available.

-- NODE API THIS PINS (confirmed from the headers) --

  * ``vtkMRMLAbstractParametricSurfaceNode::SetDistanceSpheroidInitPoint(int
    index, const double point[3]) -> bool`` -- bounds-guarded
    (``0 <= index < GetNumberOfDistanceSpheroidInitPoints()``); the
    ``vtkMRMLBezierSurfaceNode`` override ADDS an Init-only guard (returns
    ``False`` past the Init->Planning transition, ADR-0014 §4 / ADR-0019).
  * ``GetDistanceSpheroidInitPoint(int index)`` -> 3-tuple (``VTK_SIZEHINT(3)``;
    out-of-range yields a zero vector, not nullptr).
  * ``SetNumberOfDistanceSpheroidInitPoints(int n)`` / ``GetNumberOf...`` --
    DYNAMIC capacity, default ``0``, Init-only-guarded on the Bezier subclass.
  * Carrier state via ``GetState`` (``Init = 0``, ``Planning = 1``,
    ``Confirmed = 2`` on ``vtkMRMLBezierSurfaceNode``); init mode via
    ``GetInitMode`` (``SlicingPlane = 0``, ``DistanceSpheroid = 1`` on
    ``vtkMRMLAbstractParametricSurfaceNode``); ``SetInitMode(int)`` is the
    vtkSetMacro on ``InitMode``.

-- SEAM NAMES THIS PINS (so the implementation matches) --

  * ``LiverBezierSurfacePipeline._place_distance_spheroid_init_point(self,
    world) -> int | None`` -- ``world = (x, y, z)`` RAS; in Init+DistanceSpheroid
    places the next init point (0, 1, ... up to capacity) via
    ``SetDistanceSpheroidInitPoint`` and returns its index; returns ``None``
    when not Init, not DistanceSpheroid, no carrier, or the array is full.
    Placement fills in order (this is placement, NOT nearest-selection).
  * The placement counter resets on ``SetDisplayNode`` -- a fresh carrier
    restarts placement at index 0.
  * ``LiverBezierSurfacePipeline.ProcessInteractionEvent(self, eventData) ->
    bool`` -- the routing override, extended to dispatch Init+DistanceSpheroid
    -> placement.

See also:
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the decision)
  * Docs/adr/0019-resection-state-machine.md  (state-gated init/placement)
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"  (wrapper/carrier)
  * Docs/adr/0004-python-cpp-boundary.md  (interaction math in Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
  * LiverResections/MRML/vtkMRMLAbstractParametricSurfaceNode.h  (init-point API)
  * LiverResections/Testing/Python/test_pipeline_slicing_plane_init_placement.py  (slice 3a)
  * LiverResections/Testing/Python/test_pipeline_control_point_edit.py  (slice 2)
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

# Mirror the C++ InitializationMode enum on
# vtkMRMLAbstractParametricSurfaceNode:  SlicingPlane = 0, DistanceSpheroid = 1.
INIT_MODE_SLICING_PLANE = 0
INIT_MODE_DISTANCE_SPHEROID = 1

# The placement kernel seam slice 3b lands.  Tests skip-pending on its absence.
PLACE_KERNEL_METHOD = "_place_distance_spheroid_init_point"

# Capacity the setup helper configures on the carrier.  The DistanceSpheroid
# init-point array is DYNAMICALLY sized (unlike SlicingPlane's fixed 2), so the
# tests pin fill-in-order-up-to-N-then-refuse against a KNOWN N rather than a
# magic on-node constant.  Three is a representative small capacity (a centre +
# two radius-defining points); the invariants hold for any N >= 2.
SPHEROID_CAPACITY = 3


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_pipeline_slicing_plane_init_placement.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    try:
        from LiverResectionsLib.LiverBezierSurfacePipeline import (
            LiverBezierSurfacePipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"LiverBezierSurfacePipeline not importable ({exc!r}) -- LayerDMLib "
            "not reachable in this environment."
        )
    return LiverBezierSurfacePipeline()


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


def _mint_carrier_pipeline_or_skip(slicer, logic, plan_name):
    """Build one plan/carrier/display triad wired onto a fresh Pipeline.

    Returns ``(pipeline, carrier)`` where the Pipeline's ``_data_node`` is the
    carrier (derived from the display node, the LayerDM back-reference).  The
    carrier is left in its freshly-minted state; callers set the state / init
    mode / spheroid capacity they need for the invariant under test.
    """
    pipeline = _make_pipeline_or_skip()

    plan = logic.CreateResectionPlan(plan_name)
    if plan is None:
        pytest.skip("CreateResectionPlan returned None -- triad not minted.")
    carrier = plan.GetGeometryNode()
    if carrier is None or carrier.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip(
            "plan geometry node is not a vtkMRMLBezierSurfaceNode carrier -- "
            "cannot exercise distance-spheroid init placement."
        )
    for method in (
        "SetDistanceSpheroidInitPoint",
        "GetDistanceSpheroidInitPoint",
        "SetNumberOfDistanceSpheroidInitPoints",
        "GetNumberOfDistanceSpheroidInitPoints",
    ):
        if not hasattr(carrier, method):
            pytest.skip(
                f"carrier has no {method} -- the DistanceSpheroid init-point API "
                "(vtkMRMLAbstractParametricSurfaceNode) is not in this build."
            )
    if not hasattr(carrier, "SetState"):
        pytest.skip("carrier has no SetState -- ADR-0019 state machine absent.")
    if not hasattr(carrier, "SetInitMode"):
        pytest.skip(
            "carrier has no SetInitMode -- the InitMode dispatch "
            "(vtkMRMLAbstractParametricSurfaceNode) is not in this build."
        )

    display = carrier.GetDisplayNode()
    if display is None or not display.IsA(DISPLAY_NODE_CLASS):
        pytest.skip(
            "carrier has no vtkMRMLParametricSurfaceDisplayNode -- "
            "CreateDefaultDisplayNodes did not mint the display the Pipeline "
            "derives its data node from."
        )

    pipeline.SetDisplayNode(display)
    if pipeline.GetDataNode() is not carrier:
        pytest.skip(
            "Pipeline did not derive its data node from the display node's "
            "displayable back-reference -- cannot exercise the placement kernel."
        )
    return pipeline, carrier


def _configure_spheroid_capacity_or_skip(carrier, capacity):
    """Size the carrier's DistanceSpheroid init-point array to ``capacity``.

    Init-guarded on the Bezier subclass, so the carrier MUST already be in Init
    when this runs.  Skips if the configured capacity does not stick (e.g. the
    Init guard rejected it), because the fill/refuse invariants are meaningless
    without a known capacity.
    """
    carrier.SetNumberOfDistanceSpheroidInitPoints(capacity)
    if carrier.GetNumberOfDistanceSpheroidInitPoints() != capacity:
        pytest.skip(
            "could not configure the DistanceSpheroid capacity to "
            f"{capacity} (Init guard / dynamic-array API) -- cannot pin "
            "fill-in-order placement against a known capacity."
        )


def _make_init_spheroid_carrier_or_skip(slicer, plan_name="DistanceSpheroidInitTest"):
    """Build an Init + DistanceSpheroid carrier wired onto a fresh Pipeline.

    Placement is admitted only in ``Init`` state with ``InitMode ==
    DistanceSpheroid`` (ADR-0019 / ADR-0032).  The carrier's spheroid init-point
    array is sized to ``SPHEROID_CAPACITY``.  Returns ``(pipeline, carrier)``.
    """
    logic = _resection_logic_or_skip(slicer)
    pipeline, carrier = _mint_carrier_pipeline_or_skip(slicer, logic, plan_name)

    carrier.SetState(STATE_INIT)
    carrier.SetInitMode(INIT_MODE_DISTANCE_SPHEROID)
    if carrier.GetState() != STATE_INIT:
        pytest.skip("carrier is not in Init -- cannot exercise placement.")
    if carrier.GetInitMode() != INIT_MODE_DISTANCE_SPHEROID:
        pytest.skip(
            "carrier is not in DistanceSpheroid init mode -- cannot exercise "
            "distance-spheroid placement."
        )
    _configure_spheroid_capacity_or_skip(carrier, SPHEROID_CAPACITY)
    return pipeline, carrier


def _require_place_kernel_or_skip(pipeline):
    """Skip-pending unless the placement kernel seam has landed (ADR-0027).

    RED == ``LiverBezierSurfacePipeline`` has no
    ``_place_distance_spheroid_init_point``; the skip lifts at the slice-3b
    implementation commit.
    """
    if not hasattr(pipeline, PLACE_KERNEL_METHOD):
        pytest.skip(
            f"LiverBezierSurfacePipeline has no {PLACE_KERNEL_METHOD} -- the "
            "ADR-0032 DistanceSpheroid init-placement kernel (#501 slice 3b) has "
            "not landed.  Skip lifts at the implementation commit (ADR-0027)."
        )


# --------------------------------------------------------------------------- #
# Init-point helpers
# --------------------------------------------------------------------------- #


def _init_point(carrier, index):
    """Return the (x, y, z) of spheroid init point ``index`` as a tuple."""
    p = carrier.GetDistanceSpheroidInitPoint(index)
    return (p[0], p[1], p[2])


# --------------------------------------------------------------------------- #
# 1--4: GL-free placement kernel + state/mode gating + reset
# --------------------------------------------------------------------------- #


def test_place_fills_slots_in_order_then_refuses_past_capacity():
    """Invariant 1: fills index 0..N-1 in order, then refuses (array full).

    In Init+DistanceSpheroid the first ``SPHEROID_CAPACITY`` calls place indices
    ``0, 1, ..., N-1`` (each returning its index) at distinct world points, and
    a further call returns ``None`` and leaves ALL placed points unchanged --
    the dynamically-sized init-point array is full.  GL-free: the kernel takes
    the RAS world point directly (ADR-0032: placement math is Python-testable
    via SetDistanceSpheroidInitPoint).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_spheroid_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    # Distinct world points, one per slot.
    worlds = [(10.0 * (i + 1), 20.0 + i, 30.0 - i) for i in range(SPHEROID_CAPACITY)]

    for i, w in enumerate(worlds):
        idx = pipeline._place_distance_spheroid_init_point(w)
        assert idx == i, (
            f"placement #{i} must fill slot {i} and return index {i}; got {idx!r}."
        )
        assert _init_point(carrier, i) == pytest.approx(w, abs=1e-6), (
            f"slot {i} must hold {w} after placement #{i}; got "
            f"{_init_point(carrier, i)}."
        )

    before = [_init_point(carrier, i) for i in range(SPHEROID_CAPACITY)]
    idx_over = pipeline._place_distance_spheroid_init_point((99.0, 99.0, 99.0))
    assert idx_over is None, (
        "a placement past capacity must be a no-op returning None -- the "
        f"{SPHEROID_CAPACITY}-slot init array is full; got {idx_over!r}."
    )
    for i in range(SPHEROID_CAPACITY):
        assert _init_point(carrier, i) == pytest.approx(before[i], abs=1e-9), (
            f"slot {i} must be unchanged by the refused over-capacity placement."
        )


def test_place_fills_in_order_not_nearest_selection():
    """Invariant 2: ordering/identity -- placement fills 0, 1, ... in order.

    After placing two points, slot 0 holds the FIRST world point and slot 1 the
    SECOND, regardless of the second point being nearer to slot 0.  This pins
    that placement is fill-in-order, NOT nearest-selection (that is the slice-2
    edit path, a different branch).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_spheroid_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    w0 = (100.0, 0.0, 0.0)
    # w1 is closer to w0 than to the origin -- a nearest-based scheme could be
    # tempted to overwrite slot 0; fill-in-order must not.
    w1 = (105.0, 0.0, 0.0)

    pipeline._place_distance_spheroid_init_point(w0)
    pipeline._place_distance_spheroid_init_point(w1)

    assert _init_point(carrier, 0) == pytest.approx(w0, abs=1e-6), (
        "slot 0 must hold the FIRST placed point (fill-in-order, not nearest); "
        f"got {_init_point(carrier, 0)} for expected {w0}."
    )
    assert _init_point(carrier, 1) == pytest.approx(w1, abs=1e-6), (
        "slot 1 must hold the SECOND placed point; got "
        f"{_init_point(carrier, 1)} for expected {w1}."
    )


def test_place_is_no_op_in_wrong_state_or_mode():
    """Invariant 3: state/mode gating -- placement is Init+DistanceSpheroid only.

    The kernel is a no-op returning ``None`` (a) when the carrier is in Planning
    (not Init) and (b) when in Init but SlicingPlane mode (wrong init mode).
    Placement is admitted only in Init + DistanceSpheroid (ADR-0019 / ADR-0032).
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)

    # (a) Planning state (not Init) -- DistanceSpheroid mode is irrelevant.
    pipeline_p, carrier_p = _mint_carrier_pipeline_or_skip(
        slicer, logic, "SpheroidPlacementWrongStateTest"
    )
    _require_place_kernel_or_skip(pipeline_p)
    # Size the array WHILE still in Init (the capacity setter is Init-guarded),
    # then advance to Planning to exercise the state gate.
    carrier_p.SetState(STATE_INIT)
    carrier_p.SetInitMode(INIT_MODE_DISTANCE_SPHEROID)
    _configure_spheroid_capacity_or_skip(carrier_p, SPHEROID_CAPACITY)
    carrier_p.SetState(STATE_PLANNING)
    if carrier_p.GetState() != STATE_PLANNING:
        pytest.skip("carrier did not advance to Planning -- cannot gate on state.")
    idx = pipeline_p._place_distance_spheroid_init_point((1.0, 2.0, 3.0))
    assert idx is None, (
        "placement must be a no-op returning None outside Init state "
        f"(carrier in Planning); got {idx!r}."
    )

    # (b) Init state but SlicingPlane mode (wrong init mode).
    pipeline_m, carrier_m = _mint_carrier_pipeline_or_skip(
        slicer, logic, "SpheroidPlacementWrongModeTest"
    )
    carrier_m.SetState(STATE_INIT)
    carrier_m.SetInitMode(INIT_MODE_SLICING_PLANE)
    if carrier_m.GetInitMode() != INIT_MODE_SLICING_PLANE:
        pytest.skip(
            "carrier did not enter SlicingPlane mode -- cannot gate on mode."
        )
    idx = pipeline_m._place_distance_spheroid_init_point((1.0, 2.0, 3.0))
    assert idx is None, (
        "placement must be a no-op returning None in the wrong init mode "
        f"(SlicingPlane); got {idx!r}."
    )


def test_place_progress_resets_on_new_display_node():
    """Invariant 4: a fresh carrier / SetDisplayNode resets placement progress.

    After placing points on one carrier, wiring a SECOND carrier's display node
    (via ``SetDisplayNode``) restarts placement at index 0 on the new carrier --
    the Pipeline's placement counter is reset on ``SetDisplayNode``, not carried
    across carriers (mirrors slice 3a's counter discipline).
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)

    # First carrier: fill both leading slots.
    pipeline, carrier_a = _mint_carrier_pipeline_or_skip(
        slicer, logic, "SpheroidPlacementResetTestA"
    )
    _require_place_kernel_or_skip(pipeline)
    carrier_a.SetState(STATE_INIT)
    carrier_a.SetInitMode(INIT_MODE_DISTANCE_SPHEROID)
    if carrier_a.GetState() != STATE_INIT or (
        carrier_a.GetInitMode() != INIT_MODE_DISTANCE_SPHEROID
    ):
        pytest.skip("first carrier not Init+DistanceSpheroid -- cannot fill slots.")
    _configure_spheroid_capacity_or_skip(carrier_a, SPHEROID_CAPACITY)
    assert pipeline._place_distance_spheroid_init_point((1.0, 1.0, 1.0)) == 0
    assert pipeline._place_distance_spheroid_init_point((2.0, 2.0, 2.0)) == 1

    # Second carrier: a fresh triad wired onto the SAME pipeline.
    plan_b = logic.CreateResectionPlan("SpheroidPlacementResetTestB")
    if plan_b is None:
        pytest.skip("second CreateResectionPlan returned None -- cannot reset-test.")
    carrier_b = plan_b.GetGeometryNode()
    if carrier_b is None or carrier_b.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip("second plan geometry node is not a Bezier carrier.")
    display_b = carrier_b.GetDisplayNode()
    if display_b is None or not display_b.IsA(DISPLAY_NODE_CLASS):
        pytest.skip("second carrier has no parametric-surface display node.")
    carrier_b.SetState(STATE_INIT)
    carrier_b.SetInitMode(INIT_MODE_DISTANCE_SPHEROID)
    _configure_spheroid_capacity_or_skip(carrier_b, SPHEROID_CAPACITY)

    pipeline.SetDisplayNode(display_b)
    if pipeline.GetDataNode() is not carrier_b:
        pytest.skip("Pipeline did not re-derive its data node from carrier B.")

    idx = pipeline._place_distance_spheroid_init_point((7.0, 8.0, 9.0))
    assert idx == 0, (
        "placement progress must RESET on SetDisplayNode -- the new carrier's "
        f"first placement must return index 0; got {idx!r}."
    )
    assert _init_point(carrier_b, 0) == pytest.approx((7.0, 8.0, 9.0), abs=1e-6), (
        "the new carrier's slot 0 must hold the first placed point after reset; "
        f"got {_init_point(carrier_b, 0)}."
    )


# --------------------------------------------------------------------------- #
# 5: routing override (skip-pending behind a realized view)
# --------------------------------------------------------------------------- #


def _require_main_window_view_or_skip(slicer):
    """Skip unless a realized 3D view with a renderer/camera is available.

    ``ProcessInteractionEvent`` does display->world via the Pipeline's
    renderer/camera, so it needs a live GL-backed view -- present only under a
    launched Slicer with a main window, not under ``--no-main-window`` /
    ``--testing``.  The full routing (and the camera-coupled spheroid
    centre/radii derivation from the placed points) is verified on the
    interactive ``:0`` pass (ADR-0032 §Conformance).
    """
    layout = getattr(slicer.app, "layoutManager", None)
    layout_manager = layout() if callable(layout) else None
    if layout_manager is None or layout_manager.threeDViewCount == 0:
        pytest.skip(
            "no realized 3D view -- ProcessInteractionEvent needs a renderer/"
            "camera for display->world.  The full placement routing is verified "
            "on the interactive :0 pass (ADR-0032 §Conformance)."
        )
    return layout_manager.threeDWidget(0).threeDView()


def test_process_interaction_event_routes_placement_through_override():
    """Invariant 5 (skip-pending-launched): the override places an init point.

    A synthesized ``vtkMRMLInteractionEventData`` fed to
    ``pipeline.ProcessInteractionEvent(...)`` while the carrier is
    Init+DistanceSpheroid must place a distance-spheroid init point end-to-end
    through the display->world override (ADR-0032), dispatching to the
    DistanceSpheroid placement branch rather than the Init+SlicingPlane branch
    or the slice-2 edit branch.  This needs a realized renderer/camera, so it is
    gated behind a main-window view and otherwise skips; the full routing is
    confirmed on the interactive :0 eyeball pass.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_spheroid_carrier_or_skip(slicer)

    if not hasattr(pipeline, "ProcessInteractionEvent"):
        pytest.skip(
            "LiverBezierSurfacePipeline has no ProcessInteractionEvent override "
            "-- ADR-0032 routing has not landed.  Skip lifts at the "
            "implementation commit (ADR-0027)."
        )
    _require_place_kernel_or_skip(pipeline)
    _require_main_window_view_or_skip(slicer)

    # Even with a view, synthesizing a vtkMRMLInteractionEventData whose display
    # position back-projects to a chosen RAS point requires the Pipeline to be
    # attached to that view's renderer through the live LayerDM manager, and the
    # spheroid centre/radii derivation is camera-coupled.  That end-to-end wiring
    # is exercised on the interactive :0 pass; gate here so the routing invariant
    # is REGISTERED (lifts when the headless synthesis path is built out).
    pytest.skip(
        "ProcessInteractionEvent Init+DistanceSpheroid placement routing "
        "(synthesized vtkMRMLInteractionEventData through the live LayerDM "
        "manager, plus the camera-coupled centre/radii derivation) is verified "
        "on the interactive :0 pass (ADR-0032 §Conformance); headless synthesis "
        "is deferred."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
