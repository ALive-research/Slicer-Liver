# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 3a -- SlicingPlane Init-mode placement on the Pipeline.

ADR-0032 routes v2 resection interaction through the LayerDM Pipeline's
interaction seam on ``LiverBezierSurfacePipeline`` -- not a standalone
``vtkAbstractWidget`` (the ADR-0014 §3 widget decision is superseded).  Slice 2
landed the Planning-state per-control-point EDIT path
(``_apply_world_point_to_nearest_control_point`` +
``ProcessInteractionEvent`` dispatch).  Slice 3a adds the **Init-state
SlicingPlane PLACEMENT** branch: the ``SlicingPlaneInitRepresentation`` already
RENDERS the init geometry, but clicking to PLACE the two slicing-plane init
points is not wired.

This pins the placement path in two halves:

  * The **GL-free kernel** ``_place_slicing_plane_init_point((x, y, z))`` --
    takes a RAS world point directly (no renderer / picking).  When the carrier
    is in **Init + SlicingPlane** mode, it places the NEXT slicing-plane init
    point (index 0 then 1) at the world point via
    ``vtkMRMLAbstractParametricSurfaceNode::SetSlicingPlaneInitPoint`` and
    returns that index.  It is a no-op returning ``None`` when the carrier is
    not Init, not SlicingPlane mode, has no carrier, or both slots are already
    filled (the node holds a FIXED 2-slot array
    ``SlicingPlaneInitPoints[2][3]`` -- there is no on-node placed-count, so the
    Pipeline tracks placement progress in an instance counter reset on
    ``SetDisplayNode``).  Tests 1--4.

  * The **routing override** ``ProcessInteractionEvent(eventData)`` -- extends
    slice 2's dispatch by state: Init+SlicingPlane -> placement (display->world
    -> the placement kernel); Planning -> the existing per-point edit.  It needs
    a live view, so it is pinned skip-pending behind a realized main-window
    view; the full routing (and the plane origin/normal derivation, which is
    camera-coupled) is verified on the interactive ``:0`` pass
    (ADR-0032 §Conformance).  Test 5.

-- GL-FREE VS SKIP-PENDING-LAUNCHED --

Tests 1--4 are GL-free: the kernel takes a world point directly, so they RUN
under a launched Slicer once the kernel lands and never touch a renderer.  Test
5 (the ``ProcessInteractionEvent`` routing) needs a GL-backed view and stays
skip-pending behind a realized main-window view.  The plane origin/normal
derivation from the two placed points needs the camera/view direction, so it is
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
skip) once slice 3a lands ``_place_slicing_plane_init_point``; verify run-vs-skip
in the CI log, never trust overall green (the launched harness is
green-but-skipping prone).  Pre-implementation they are skip-pending on the
missing seam (``hasattr`` guard) per ADR-0027 -- the skip lifts at the
implementation commit.  Test 5 stays skip-pending behind a realized view even
after the kernel lands; it lifts when a GL-backed view is available.

-- SEAM NAMES THIS PINS (so the implementation matches) --

  * ``LiverBezierSurfacePipeline._place_slicing_plane_init_point(self, world)
    -> int | None`` -- ``world = (x, y, z)`` RAS; in Init+SlicingPlane places the
    next init point (0 then 1) via ``SetSlicingPlaneInitPoint`` and returns its
    index; returns ``None`` when not Init, not SlicingPlane, no carrier, or both
    slots already placed.  Placement fills slot 0 then slot 1 (this is
    placement, NOT nearest-selection).
  * The placement counter resets on ``SetDisplayNode`` -- a fresh carrier
    restarts placement at index 0.
  * ``LiverBezierSurfacePipeline.ProcessInteractionEvent(self, eventData) ->
    bool`` -- the routing override, extended to dispatch Init+SlicingPlane ->
    placement / Planning -> edit.
  * Carrier state read through ``_safe_get_state`` (``GetState``; enum
    ``Init = 0``, ``Planning = 1``, ``Confirmed = 2`` on
    ``vtkMRMLBezierSurfaceNode``); init mode through ``_safe_get_init_mode``
    (``GetInitMode``; enum ``SlicingPlane = 0``, ``DistanceSpheroid = 1`` on
    ``vtkMRMLAbstractParametricSurfaceNode``).  The init-mode setter on the
    node is ``SetInitMode(int)`` (vtkSetMacro on ``InitMode``).

See also:
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the decision)
  * Docs/adr/0019-resection-state-machine.md  (state-gated init/placement)
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"  (wrapper/carrier)
  * Docs/adr/0004-python-cpp-boundary.md  (interaction math in Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
  * LiverResections/MRML/vtkMRMLAbstractParametricSurfaceNode.h  (init-point API)
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

# The placement kernel seam slice 3a lands.  Tests skip-pending on its absence.
PLACE_KERNEL_METHOD = "_place_slicing_plane_init_point"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_pipeline_control_point_edit.py)
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


def _state_machine_or_skip():
    """Import ``ResectionStateMachine`` or skip cleanly.

    Bare pytest has ``LiverResectionsLib`` off ``sys.path`` (the built
    ``qt-scripted-modules`` only) -- an unguarded module-scope import
    would ERROR the bare CTest row instead of skipping.
    """
    try:
        from LiverResectionsLib import ResectionStateMachine
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"ResectionStateMachine not importable ({exc!r}) -- "
            "LiverResectionsLib not reachable in this environment."
        )
    return ResectionStateMachine


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
    mode they need for the invariant under test.
    """
    pipeline = _make_pipeline_or_skip()

    plan = logic.CreateResectionPlan(plan_name)
    if plan is None:
        pytest.skip("CreateResectionPlan returned None -- triad not minted.")
    carrier = plan.GetGeometryNode()
    if carrier is None or carrier.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip(
            "plan geometry node is not a vtkMRMLBezierSurfaceNode carrier -- "
            "cannot exercise slicing-plane init placement."
        )
    for method in ("SetSlicingPlaneInitPoint", "GetSlicingPlaneInitPoint"):
        if not hasattr(carrier, method):
            pytest.skip(
                f"carrier has no {method} -- the SlicingPlane init-point API "
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


def _make_init_slicing_plane_carrier_or_skip(slicer, plan_name="SlicingPlaneInitTest"):
    """Build an Init + SlicingPlane carrier wired onto a fresh Pipeline.

    Placement is admitted only in ``Init`` state with ``InitMode ==
    SlicingPlane`` (ADR-0019 / ADR-0032).  Returns ``(pipeline, carrier)``.
    """
    logic = _resection_logic_or_skip(slicer)
    pipeline, carrier = _mint_carrier_pipeline_or_skip(slicer, logic, plan_name)

    carrier.SetState(STATE_INIT)
    carrier.SetInitMode(INIT_MODE_SLICING_PLANE)
    if carrier.GetState() != STATE_INIT:
        pytest.skip("carrier is not in Init -- cannot exercise placement.")
    if carrier.GetInitMode() != INIT_MODE_SLICING_PLANE:
        pytest.skip(
            "carrier is not in SlicingPlane init mode -- cannot exercise "
            "slicing-plane placement."
        )
    return pipeline, carrier


def _require_place_kernel_or_skip(pipeline):
    """Skip-pending unless the placement kernel seam has landed (ADR-0027).

    RED == ``LiverBezierSurfacePipeline`` has no
    ``_place_slicing_plane_init_point``; the skip lifts at the slice-3a
    implementation commit.
    """
    if not hasattr(pipeline, PLACE_KERNEL_METHOD):
        pytest.skip(
            f"LiverBezierSurfacePipeline has no {PLACE_KERNEL_METHOD} -- the "
            "ADR-0032 SlicingPlane init-placement kernel (#501 slice 3a) has "
            "not landed.  Skip lifts at the implementation commit (ADR-0027)."
        )


# --------------------------------------------------------------------------- #
# Init-point helpers
# --------------------------------------------------------------------------- #


def _init_point(carrier, index):
    """Return the (x, y, z) of slicing-plane init point ``index`` as a tuple."""
    p = carrier.GetSlicingPlaneInitPoint(index)
    return (p[0], p[1], p[2])


# --------------------------------------------------------------------------- #
# 1--4: GL-free placement kernel + state/mode gating + reset
# --------------------------------------------------------------------------- #


def test_place_fills_slot0_then_slot1_then_refuses_third():
    """Invariant 1: fills index 0, then 1, then refuses (2-slot array is full).

    In Init+SlicingPlane the first call places index 0 (returns 0), the second
    with a distinct point places index 1 (returns 1), and a THIRD call returns
    ``None`` and leaves BOTH points unchanged -- the node holds a fixed 2-slot
    array ``SlicingPlaneInitPoints[2][3]`` (no on-node placed-count).  GL-free:
    the kernel takes the RAS world point directly (ADR-0032: placement math is
    Python-testable via SetSlicingPlaneInitPoint).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    w0 = (10.0, 20.0, 30.0)
    w1 = (-5.0, 40.0, 15.0)

    idx0 = pipeline._place_slicing_plane_init_point(w0)
    assert idx0 == 0, (
        "the first placement must fill slot 0 and return index 0; got "
        f"{idx0!r}."
    )
    assert _init_point(carrier, 0) == pytest.approx(w0, abs=1e-6), (
        f"slot 0 must hold {w0} after the first placement; got "
        f"{_init_point(carrier, 0)}."
    )

    idx1 = pipeline._place_slicing_plane_init_point(w1)
    assert idx1 == 1, (
        "the second placement must fill slot 1 and return index 1; got "
        f"{idx1!r}."
    )
    assert _init_point(carrier, 1) == pytest.approx(w1, abs=1e-6), (
        f"slot 1 must hold {w1} after the second placement; got "
        f"{_init_point(carrier, 1)}."
    )

    before0 = _init_point(carrier, 0)
    before1 = _init_point(carrier, 1)
    idx2 = pipeline._place_slicing_plane_init_point((99.0, 99.0, 99.0))
    assert idx2 is None, (
        "a third placement must be a no-op returning None -- the 2-slot init "
        f"array is full; got {idx2!r}."
    )
    assert _init_point(carrier, 0) == pytest.approx(before0, abs=1e-9), (
        "slot 0 must be unchanged by the refused third placement."
    )
    assert _init_point(carrier, 1) == pytest.approx(before1, abs=1e-9), (
        "slot 1 must be unchanged by the refused third placement."
    )


def test_place_fills_in_order_not_nearest_selection():
    """Invariant 2: ordering/identity -- placement fills 0 then 1.

    After placing both points, slot 0 holds the FIRST world point and slot 1 the
    SECOND, regardless of the second point being nearer to slot 0.  This pins
    that placement is fill-in-order, NOT nearest-selection (that is the slice-2
    edit path, a different branch).
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    w0 = (100.0, 0.0, 0.0)
    # w1 is closer to w0 than to the origin -- a nearest-based scheme could be
    # tempted to overwrite slot 0; fill-in-order must not.
    w1 = (105.0, 0.0, 0.0)

    pipeline._place_slicing_plane_init_point(w0)
    pipeline._place_slicing_plane_init_point(w1)

    assert _init_point(carrier, 0) == pytest.approx(w0, abs=1e-6), (
        "slot 0 must hold the FIRST placed point (fill-in-order, not nearest); "
        f"got {_init_point(carrier, 0)} for expected {w0}."
    )
    assert _init_point(carrier, 1) == pytest.approx(w1, abs=1e-6), (
        "slot 1 must hold the SECOND placed point; got "
        f"{_init_point(carrier, 1)} for expected {w1}."
    )


def test_place_is_no_op_in_wrong_state_or_mode():
    """Invariant 3: state/mode gating -- placement is Init+SlicingPlane only.

    The kernel is a no-op returning ``None`` (a) when the carrier is in Planning
    (not Init) and (b) when in Init but DistanceSpheroid mode (wrong init mode).
    Placement is admitted only in Init + SlicingPlane (ADR-0019 / ADR-0032).
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)

    # (a) Planning state (not Init) -- SlicingPlane mode is irrelevant.
    pipeline_p, carrier_p = _mint_carrier_pipeline_or_skip(
        slicer, logic, "PlacementWrongStateTest"
    )
    _require_place_kernel_or_skip(pipeline_p)
    carrier_p.SetInitMode(INIT_MODE_SLICING_PLANE)
    carrier_p.SetState(STATE_PLANNING)
    if carrier_p.GetState() != STATE_PLANNING:
        pytest.skip("carrier did not advance to Planning -- cannot gate on state.")
    idx = pipeline_p._place_slicing_plane_init_point((1.0, 2.0, 3.0))
    assert idx is None, (
        "placement must be a no-op returning None outside Init state "
        f"(carrier in Planning); got {idx!r}."
    )

    # (b) Init state but DistanceSpheroid mode (wrong init mode).
    pipeline_m, carrier_m = _mint_carrier_pipeline_or_skip(
        slicer, logic, "PlacementWrongModeTest"
    )
    carrier_m.SetState(STATE_INIT)
    carrier_m.SetInitMode(INIT_MODE_DISTANCE_SPHEROID)
    if carrier_m.GetInitMode() != INIT_MODE_DISTANCE_SPHEROID:
        pytest.skip(
            "carrier did not enter DistanceSpheroid mode -- cannot gate on mode."
        )
    idx = pipeline_m._place_slicing_plane_init_point((1.0, 2.0, 3.0))
    assert idx is None, (
        "placement must be a no-op returning None in the wrong init mode "
        f"(DistanceSpheroid); got {idx!r}."
    )


def test_place_progress_resets_on_new_display_node():
    """Invariant 4: a fresh carrier / SetDisplayNode resets placement progress.

    After filling both slots on one carrier, wiring a SECOND carrier's display
    node (via ``SetDisplayNode``) restarts placement at index 0 on the new
    carrier -- the Pipeline's placement counter is reset on ``SetDisplayNode``,
    not carried across carriers.
    """
    slicer = _slicer_or_skip()
    logic = _resection_logic_or_skip(slicer)

    # First carrier: fill both slots.
    pipeline, carrier_a = _mint_carrier_pipeline_or_skip(
        slicer, logic, "PlacementResetTestA"
    )
    _require_place_kernel_or_skip(pipeline)
    carrier_a.SetState(STATE_INIT)
    carrier_a.SetInitMode(INIT_MODE_SLICING_PLANE)
    if carrier_a.GetState() != STATE_INIT or (
        carrier_a.GetInitMode() != INIT_MODE_SLICING_PLANE
    ):
        pytest.skip("first carrier not Init+SlicingPlane -- cannot fill slots.")
    assert pipeline._place_slicing_plane_init_point((1.0, 1.0, 1.0)) == 0
    assert pipeline._place_slicing_plane_init_point((2.0, 2.0, 2.0)) == 1
    # Sanity: the first carrier is now full.
    assert pipeline._place_slicing_plane_init_point((3.0, 3.0, 3.0)) is None

    # Second carrier: a fresh triad wired onto the SAME pipeline.
    plan_b = logic.CreateResectionPlan("PlacementResetTestB")
    if plan_b is None:
        pytest.skip("second CreateResectionPlan returned None -- cannot reset-test.")
    carrier_b = plan_b.GetGeometryNode()
    if carrier_b is None or carrier_b.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip("second plan geometry node is not a Bezier carrier.")
    display_b = carrier_b.GetDisplayNode()
    if display_b is None or not display_b.IsA(DISPLAY_NODE_CLASS):
        pytest.skip("second carrier has no parametric-surface display node.")
    carrier_b.SetState(STATE_INIT)
    carrier_b.SetInitMode(INIT_MODE_SLICING_PLANE)

    pipeline.SetDisplayNode(display_b)
    if pipeline.GetDataNode() is not carrier_b:
        pytest.skip("Pipeline did not re-derive its data node from carrier B.")

    idx = pipeline._place_slicing_plane_init_point((7.0, 8.0, 9.0))
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
    ``--testing``.  The full routing (and the camera-coupled plane origin/normal
    derivation from the two placed points) is verified on the interactive ``:0``
    pass (ADR-0032 §Conformance).
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
    Init+SlicingPlane must place a slicing-plane init point end-to-end through
    the display->world override (ADR-0032), dispatching to the placement branch
    rather than the slice-2 edit branch.  This needs a realized renderer/camera,
    so it is gated behind a main-window view and otherwise skips; the full
    routing is confirmed on the interactive :0 eyeball pass.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)

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
    # plane origin/normal derivation is camera-coupled.  That end-to-end wiring
    # is exercised on the interactive :0 pass; gate here so the routing invariant
    # is REGISTERED (lifts when the headless synthesis path is built out).
    pytest.skip(
        "ProcessInteractionEvent Init+SlicingPlane placement routing "
        "(synthesized vtkMRMLInteractionEventData through the live LayerDM "
        "manager, plus the camera-coupled origin/normal derivation) is verified "
        "on the interactive :0 pass (ADR-0032 §Conformance); headless synthesis "
        "is deferred."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_second_placement_derives_the_slicing_plane():
    """Placing both points writes origin=midpoint, normal=unit(p2-p1).

    v1 parity (the NorMIT-Plan bisector): the slicing plane is the
    perpendicular bisector of the two init points -- origin at their
    midpoint, normal along their difference (normalized here so
    downstream consumers -- the shader band, the ring extractor -- get a
    unit normal).  The camera does NOT enter the plane math (the v1
    study correction); it only orients the auto-seed placement.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    first = pipeline._place_slicing_plane_init_point((10.0, 0.0, 0.0))
    assert first == 0
    second = pipeline._place_slicing_plane_init_point((40.0, 40.0, 0.0))
    assert second == 1

    origin = tuple(carrier.GetSlicingPlaneOrigin())
    assert origin == pytest.approx((25.0, 20.0, 0.0)), (
        "the slicing-plane origin must be the MIDPOINT of the two init "
        "points (the v1 bisector plane)."
    )
    normal = tuple(carrier.GetSlicingPlaneNormal())
    assert normal == pytest.approx((0.6, 0.8, 0.0)), (
        "the slicing-plane normal must be the UNIT vector along p2 - p1."
    )


def test_rederive_follows_a_moved_init_point():
    """Re-running the derivation after a point moves updates the plane."""
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    pipeline._place_slicing_plane_init_point((0.0, 0.0, 0.0))
    pipeline._place_slicing_plane_init_point((10.0, 0.0, 0.0))

    carrier.SetSlicingPlaneInitPoint(1, [0.0, 0.0, 8.0])
    pipeline._derive_slicing_plane()

    assert tuple(carrier.GetSlicingPlaneOrigin()) == pytest.approx(
        (0.0, 0.0, 4.0)
    )
    assert tuple(carrier.GetSlicingPlaneNormal()) == pytest.approx(
        (0.0, 0.0, 1.0)
    )


def test_derivation_is_a_noop_before_both_points():
    """One placed point must not fabricate a plane (degenerate normal)."""
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    _require_place_kernel_or_skip(pipeline)

    before_origin = tuple(carrier.GetSlicingPlaneOrigin())
    before_normal = tuple(carrier.GetSlicingPlaneNormal())
    pipeline._place_slicing_plane_init_point((10.0, 20.0, 30.0))

    assert tuple(carrier.GetSlicingPlaneOrigin()) == before_origin
    assert tuple(carrier.GetSlicingPlaneNormal()) == before_normal


# --------------------------------------------------------------------------- #
# Slice 3 — auto-seed + drag-only handles
# --------------------------------------------------------------------------- #


def _target_model_with_bounds(slicer, xmax=40.0, ymax=20.0, zmax=10.0):
    """A box target model spanning [0, max] on each axis."""
    import vtk

    cube = vtk.vtkCubeSource()
    cube.SetBounds(0.0, xmax, 0.0, ymax, 0.0, zmax)
    cube.Update()
    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode")
    model.SetAndObservePolyData(cube.GetOutput())
    return model


def test_auto_seed_places_handles_across_the_target(monkeypatch):
    """Auto-seed straddles the target's centre along the view-right axis.

    v1 parity, camera-aware: v1 pre-seeded the two points across the
    liver bounds (nobody clicks to place); v2 orients the seed axis
    along the CAMERA's right vector so the initial bisector plane cuts
    vertically through the surgeon's view and the handles sit
    left/right on screen -- maximally draggable.  Headless fallback
    (no camera): the world x axis, v1's exact default.
    """
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    if not hasattr(pipeline, "_auto_seed_slicing_plane"):
        pytest.fail("pipeline must expose the _auto_seed_slicing_plane kernel")

    target = _target_model_with_bounds(slicer)  # centre (20, 10, 5)
    carrier.SetAndObserveTargetModelNode(target)

    # Attaching the target fires the carrier's ModifiedEvent, whose
    # observer reconciles the pipeline -- the dispatch hook auto-seeds
    # (the production path; headless fallback axis = world x = the
    # injected view_right here, so the expectations match either route).
    if pipeline._slicing_plane_points_placed < 2:
        assert pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    p0 = tuple(carrier.GetSlicingPlaneInitPoint(0))
    p1 = tuple(carrier.GetSlicingPlaneInitPoint(1))
    assert p0 == pytest.approx((0.0, 10.0, 5.0)), (
        "handle 0 must sit at centre - half-extent along the seed axis"
    )
    assert p1 == pytest.approx((40.0, 10.0, 5.0)), (
        "handle 1 must sit at centre + half-extent along the seed axis"
    )
    assert tuple(carrier.GetSlicingPlaneOrigin()) == pytest.approx((20.0, 10.0, 5.0)), (
        "the auto-seed must run the plane derivation (origin = midpoint)"
    )
    assert tuple(carrier.GetSlicingPlaneNormal()) == pytest.approx((1.0, 0.0, 0.0))

    # Idempotent: a second reconcile-driven call must not re-seed.
    carrier.SetSlicingPlaneInitPoint(0, [5.0, 10.0, 5.0])
    assert pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0)) is False
    assert tuple(carrier.GetSlicingPlaneInitPoint(0)) == pytest.approx((5.0, 10.0, 5.0))


def test_auto_seed_without_target_is_a_noop():
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    if not hasattr(pipeline, "_auto_seed_slicing_plane"):
        pytest.fail("pipeline must expose the _auto_seed_slicing_plane kernel")
    assert pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0)) is False


def test_press_grabs_a_handle_and_drag_rederives_the_plane(monkeypatch):
    """The Init handles are drag-editable with the control-point grammar.

    Press within the pick radius grabs the nearest handle (real squared
    distance for LayerDM arbitration); moves while grabbed relocate the
    handle on the camera focal plane and re-derive the bisector plane;
    release drops the grab.  Mirrors the ADR-0033 grab pattern.
    """
    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    if not hasattr(pipeline, "_nearest_init_handle_in_display"):
        pytest.fail("pipeline must expose _nearest_init_handle_in_display")

    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        assert pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (1, 9.0)
    )
    monkeypatch.setattr(
        pipeline,
        "_event_world_at_init_point",
        lambda r, e, i: (40.0, 10.0, 25.0),
    )

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    press = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    can, d2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True and d2 == pytest.approx(9.0), (
        "a press within the pick radius must be claimed with the REAL "
        "squared display distance (LayerDM arbitration)."
    )
    assert pipeline.ProcessInteractionEvent(press) is True

    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    can, d2 = pipeline.CanProcessInteractionEvent(move)
    assert can is True and d2 == 0.0, "a grabbed gesture owns the moves"
    assert pipeline.ProcessInteractionEvent(move) is True
    assert tuple(carrier.GetSlicingPlaneInitPoint(1)) == pytest.approx(
        (40.0, 10.0, 25.0)
    ), "the drag must relocate the grabbed handle"
    assert tuple(carrier.GetSlicingPlaneOrigin()) == pytest.approx(
        (20.0, 10.0, 15.0)
    ), "the drag must re-derive the bisector plane live"

    release = _Event(vtk.vtkCommand.LeftButtonReleaseEvent)
    can, _ = pipeline.CanProcessInteractionEvent(release)
    assert can is True
    assert pipeline.ProcessInteractionEvent(release) is False, "grab ends"
    can, _ = pipeline.CanProcessInteractionEvent(move)
    assert can is False, "no grab -> bare moves stay unclaimed (camera intact)"


def test_handle_interaction_declines_outside_init(monkeypatch):
    """Planning must not steal the control-polygon interaction (ADR-0033)."""

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (0, 1.0)
    )
    carrier.SetState(1)  # Planning

    class _Event:
        def GetType(self):  # noqa: N802 - VTK verb
            import vtk as _vtk

            return _vtk.vtkCommand.LeftButtonPressEvent

    can, _ = pipeline.CanProcessInteractionEvent(_Event())
    assert can is False, (
        "outside Init the surface pipeline must keep declining -- the "
        "Planning drag belongs to ControlPolygonPipeline (ADR-0033)."
    )


def test_drag_move_fires_exactly_one_modified(monkeypatch):
    """A drag move batches point + plane writes under ONE ModifiedEvent.

    The point write and the origin/normal re-derivation previously fired
    three ModifiedEvents per mouse move -- and the Stage-4 widget force-
    renders the resectogram strip on every carrier Modified, so each move
    cost three reconciles + three strip renders (the "cutting and
    rendering later" lag).  The control-point drag's cost profile is one
    Modified per move; the handle drag must match it.
    """
    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (0, 1.0)
    )
    monkeypatch.setattr(
        pipeline, "_event_world_at_init_point", lambda r, e, i: (5.0, 6.0, 7.0)
    )

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonPressEvent)
    )

    events = []
    tag = carrier.AddObserver(
        vtk.vtkCommand.ModifiedEvent, lambda c, e: events.append(1)
    )
    try:
        assert pipeline.ProcessInteractionEvent(
            _Event(vtk.vtkCommand.MouseMoveEvent)
        )
    finally:
        carrier.RemoveObserver(tag)

    assert len(events) == 1, (
        f"a drag move must fire exactly ONE ModifiedEvent (got {len(events)}) "
        "-- the point + origin + normal writes batch under StartModify."
    )
    assert tuple(carrier.GetSlicingPlaneInitPoint(0)) == (5.0, 6.0, 7.0)
    assert tuple(carrier.GetSlicingPlaneOrigin())[2] != 5.0  # plane re-derived


# --------------------------------------------------------------------------- #
# R2 — the v1 iterate loop: re-fit on release, contour-only Init
# --------------------------------------------------------------------------- #


def _flat_ring(radius=20.0, z=5.0, count=36):
    """A planar circle ring polydata (a synthetic plane/liver cut)."""
    import math

    import vtk

    points = vtk.vtkPoints()
    for k in range(count):
        angle = 2.0 * math.pi * k / count
        points.InsertNextPoint(
            radius * math.cos(angle), radius * math.sin(angle), z
        )
    ring = vtk.vtkPolyData()
    ring.SetPoints(points)
    return ring


def test_seed_grid_from_ring_builds_the_pca_rectangle():
    """The ring's PCA rectangle becomes a non-degenerate planar 4x4 grid.

    v1 parity (NorMIT-Plan): the rectangle spans 4*sqrt(eigenvalue)
    along the two dominant in-plane eigenvectors, centred on the ring's
    centre of mass; a 4x4 lattice over it seeds the control grid --
    in ONE ModifiedEvent (the drag-latency lesson).
    """
    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)

    events = []
    tag = carrier.AddObserver(
        vtk.vtkCommand.ModifiedEvent, lambda c, e: events.append(1)
    )
    try:
        assert pipeline._seed_grid_from_ring(_flat_ring()) is True
    finally:
        carrier.RemoveObserver(tag)

    assert len(events) == 1, (
        f"the 16 grid writes must batch under ONE Modified (got {len(events)})"
    )
    grid = carrier.GetControlGridVector()
    xs = [grid[i] for i in range(0, 48, 3)]
    ys = [grid[i] for i in range(1, 48, 3)]
    zs = [grid[i] for i in range(2, 48, 3)]
    assert max(xs) - min(xs) > 10.0 and max(ys) - min(ys) > 10.0, (
        "the grid must span the ring's PCA rectangle, not collapse"
    )
    assert all(abs(z - 5.0) < 1e-6 for z in zs), (
        "a planar ring must seed a PLANAR grid at the ring's plane"
    )
    centre_x = sum(xs) / 16.0
    centre_y = sum(ys) / 16.0
    assert abs(centre_x) < 1.0 and abs(centre_y) < 1.0, (
        "the grid must be centred on the ring's centre of mass"
    )


def test_release_refits_and_restores_the_handle_colour(monkeypatch):
    """A drag release runs the grid re-fit and hands ``None`` back to the
    grab cue — press colours the grabbed handle (the control-point
    grammar), release restores the white base."""
    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (0, 1.0)
    )
    monkeypatch.setattr(
        pipeline, "_event_world_at_init_point", lambda r, e, i: (5.0, 6.0, 7.0)
    )
    refits = []
    monkeypatch.setattr(
        pipeline, "_refit_grid_from_plane", lambda: refits.append(1) or True
    )
    grabs = []
    monkeypatch.setattr(
        pipeline, "_set_grabbed_handle", lambda i: grabs.append(i)
    )

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonPressEvent)
    )
    assert grabs == [0], (
        "a grab must colour the grabbed handle (the control-point cue)"
    )
    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonReleaseEvent)
    ) is False
    assert refits == [1], "the release must run the grid re-fit (v1 loop)"
    assert grabs == [0, None], "the release must restore the handle colour"


def test_drag_requests_a_render_per_plane_change(monkeypatch):
    """Moving a slicing-plane init point must request a render — the
    contour follows the handle DURING the drag, not only at the release
    re-fit.  A geometry-preserving ``Modified`` must not re-request (the
    render feedback-loop guard)."""
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    renders = []
    monkeypatch.setattr(pipeline, "RequestRender", lambda: renders.append(1))

    # Baseline: settle the render key at the current geometry.
    pipeline._on_node_modified(None, None)
    baseline = len(renders)

    # A geometry-preserving Modified must NOT re-request.
    pipeline._on_node_modified(None, None)
    assert len(renders) == baseline, (
        "a Modified at unchanged plane geometry must not re-request a "
        "render (the feedback-loop guard)."
    )

    # Moving a handle changes the plane digest -> render requested.
    carrier.SetSlicingPlaneInitPoint(0, (1.0, 2.0, 3.0))
    pipeline._on_node_modified(None, None)
    assert len(renders) == baseline + 1, (
        "a slicing-plane change must request a render -- the contour "
        "follows the handle DURING the drag."
    )


def test_bare_hover_raises_the_halo_and_declines(monkeypatch):
    """A bare mouse move near a handle raises the hover cue (the glow
    halo, the control-point grammar) as a SIDE EFFECT of the declined
    arbitration call -- camera interaction stays unclaimed."""
    import sys

    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    hovers = []
    monkeypatch.setattr(
        pipeline, "_set_hovered_handle", lambda i: hovers.append(i)
    )

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    # Near a handle: hover raised, event still declined.
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (1, 4.0)
    )
    can, distance2 = pipeline.CanProcessInteractionEvent(
        _Event(vtk.vtkCommand.MouseMoveEvent)
    )
    assert can is False and distance2 == sys.float_info.max
    assert hovers == [1], "a near hover must raise the halo on handle 1"

    # Far from every handle: hover cleared, still declined.
    monkeypatch.setattr(
        pipeline,
        "_nearest_init_handle_in_display",
        lambda r, e: (0, 1.0e9),
    )
    can, _ = pipeline.CanProcessInteractionEvent(
        _Event(vtk.vtkCommand.MouseMoveEvent)
    )
    assert can is False
    assert hovers == [1, None], "a far move must clear the hover"


def test_press_repaints_before_any_drag_move(monkeypatch):
    """The grab green must appear ON THE CLICK, not at the first drag
    move: the press itself requests a render even when the handle was
    already hovered (the approach raises the hover first, so the hover
    setter's change-gated request never fires on the press)."""
    import vtk

    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (0, 1.0)
    )
    renders = []
    monkeypatch.setattr(pipeline, "RequestRender", lambda: renders.append(1))

    # The approach: hover already raised on handle 0 (the real-world
    # sequence -- you hover a handle before you can click it).
    pipeline._set_hovered_handle(0)
    renders.clear()

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonPressEvent)
    )
    assert len(renders) >= 1, (
        "the press must request a render -- the grab green appears on "
        "the CLICK, not at the first drag move."
    )


# --------------------------------------------------------------------------- #
# R3 -- the v1 composite loop: release raises a manipulable candidate
# surface; grabbing a plane handle hides it while the contour follows.
# --------------------------------------------------------------------------- #


def test_release_marks_the_candidate_and_drag_hides_it(monkeypatch):
    """The v1 composite loop through the state machine (ADR-0035): an
    init-handle press raises the in-flight phase (the candidate surface
    hides while the contour follows); the release drop re-fits and lands
    the carrier in the Candidate phase (the surface [re]appears)."""
    import vtk

    slicer = _slicer_or_skip()
    rsm = _state_machine_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)  # reconcile hook auto-seeds
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    assert rsm.candidate_active(carrier) is False, (
        "before any release there is no candidate -- handles + contour only"
    )

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: object())
    monkeypatch.setattr(
        pipeline, "_nearest_init_handle_in_display", lambda r, e: (0, 1.0)
    )
    monkeypatch.setattr(
        pipeline, "_event_world_at_init_point", lambda r, e, i: (5.0, 6.0, 7.0)
    )

    class _Event:
        def __init__(self, etype):
            self._etype = etype

        def GetType(self):  # noqa: N802 - VTK verb
            return self._etype

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonPressEvent)
    )
    assert rsm.in_flight(carrier) is True, (
        "the press must raise the in-flight phase (the candidate "
        "surface hides while the plane handle is being adjusted)."
    )

    assert pipeline.ProcessInteractionEvent(
        _Event(vtk.vtkCommand.LeftButtonReleaseEvent)
    ) is False
    assert rsm.in_flight(carrier) is False, (
        "the release must clear the in-flight phase."
    )
    assert rsm.candidate_active(carrier) is True, (
        "the release drop must land in the Candidate phase -- dropping "
        "the handle GENERATES the manipulable candidate (v1)."
    )


class _FakeCompositeRep:
    """Minimal Representation stand-in for the dispatch pin."""

    def __init__(self):
        self._renderer = None
        self.updates = 0

    def SetRenderer(self, renderer):  # noqa: N802 - VTK verb
        self._renderer = renderer

    def update(self, display_node, data_node):
        self.updates += 1


def test_candidate_attaches_the_planning_surface_alongside_init(monkeypatch):
    """In Init+SlicingPlane with the candidate up, the reconcile keeps
    the BezierPlanning Representation attached ALONGSIDE the init rep
    (the v1 two-widget composite); an in-flight drag detaches it."""

    slicer = _slicer_or_skip()
    rsm = _state_machine_or_skip()
    try:
        from LiverResectionsLib.LiverBezierSurfacePipeline import (
            REPRESENTATION_BEZIER_PLANNING,
            REPRESENTATION_SLICING_PLANE_INIT,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"LiverBezierSurfacePipeline not importable ({exc!r}) -- "
            "LiverResectionsLib not reachable in this environment."
        )
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)

    init_rep = _FakeCompositeRep()
    planning_rep = _FakeCompositeRep()
    pipeline._representations = {
        REPRESENTATION_SLICING_PLANE_INIT: init_rep,
        REPRESENTATION_BEZIER_PLANNING: planning_rep,
    }
    pipeline._representations_initialised = True
    renderer = object()
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: renderer)

    # No candidate yet: only the init rep may sit on the renderer.
    pipeline._last_update_key = None
    pipeline.UpdatePipeline()
    assert init_rep._renderer is renderer
    assert planning_rep._renderer is None, (
        "before the first drop there is no candidate surface."
    )

    # Candidate up (a drop with a successful re-fit): BOTH attach.
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)
    pipeline._last_update_key = None
    pipeline.UpdatePipeline()
    assert init_rep._renderer is renderer, (
        "the init handles + contour stay up while the candidate shows."
    )
    assert planning_rep._renderer is renderer, (
        "the candidate surface must attach alongside the init rep."
    )
    assert planning_rep.updates >= 1, (
        "the composite rep must be updated, not just attached."
    )

    # Drag in flight: the candidate hides, the init rep stays.
    rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    pipeline._last_update_key = None
    pipeline.UpdatePipeline()
    assert planning_rep._renderer is None, (
        "grabbing a plane handle must hide the candidate surface (v1: "
        "the surface hides while the contour follows the drag)."
    )
    assert init_rep._renderer is renderer


def test_phase_flip_requests_a_render_without_a_local_gesture(monkeypatch):
    """A phase flip raised OUTSIDE this pipeline's gesture handlers (a
    programmatic request, another view, undo/redo) must still repaint --
    the phase token sits in the digest-gated render key."""
    slicer = _slicer_or_skip()
    rsm = _state_machine_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)

    renders = []
    monkeypatch.setattr(pipeline, "RequestRender", lambda: renders.append(1))

    # Settle the render key, then verify the feedback-loop guard.
    pipeline._on_node_modified(None, None)
    baseline = len(renders)
    pipeline._on_node_modified(None, None)
    assert len(renders) == baseline

    # A machine-raised phase flip with NO local gesture must repaint.
    assert rsm.request(carrier, rsm.EVENT_PLANE_HANDLE_GRABBED) is True
    pipeline._on_node_modified(None, None)
    assert len(renders) == baseline + 1, (
        "a phase flip must enter the render key -- without it the "
        "composite attach/detach reconciles but never repaints."
    )


def test_adoption_keeps_persisted_init_handles(monkeypatch):
    """Re-adopting a carrier that ALREADY carries placed init handles (a
    loaded scene) must not re-seed them -- node-side evidence beats the
    pipeline-local placement counter."""
    slicer = _slicer_or_skip()
    pipeline, carrier = _make_init_slicing_plane_carrier_or_skip(slicer)
    target = _target_model_with_bounds(slicer)
    carrier.SetAndObserveTargetModelNode(target)
    if pipeline._slicing_plane_points_placed < 2:
        pipeline._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))

    # The surgeon adjusted a handle; the scene was saved + reloaded --
    # simulated by a FRESH pipeline adopting the same carrier.
    surgeon_p0 = (12.5, -3.0, 41.0)
    carrier.SetSlicingPlaneInitPoint(0, surgeon_p0)
    fresh = _make_pipeline_or_skip()
    fresh.SetDisplayNode(carrier.GetDisplayNode())
    assert fresh.GetDataNode() is carrier

    fresh._auto_seed_slicing_plane(view_right=(1.0, 0.0, 0.0))
    assert tuple(carrier.GetSlicingPlaneInitPoint(0)) == pytest.approx(
        surgeon_p0
    ), "adoption must ADOPT persisted handles, not re-seed over them."
    assert fresh._slicing_plane_points_placed == 2, (
        "the fresh pipeline adopts the placed count from the node."
    )
