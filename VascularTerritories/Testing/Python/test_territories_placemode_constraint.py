# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 (PR-B) — active-tree seed constraint + highlight + module gate.

PR-A landed the compute core (the vessels-only surface resolver
``vascular_surface_polydata`` / the C++ ``GetVascularSegmentIds`` / the pure-VTK
``VesselConnectivity.connected_component_at`` / the per-extraction
single-component surface, and made the pick surface vessels-only).  PR-B adds
the INTERACTION layer on top: the placement pipelines constrain a territory's
seed set to ONE connected vessel tree, highlight that tree while armed, and
decline add-on-clicks while the owning module is inactive.

The invariants pinned here (ADR-0037 §"Amendment — connected-tree-constrained
centerline seeding (slice 5)" + §Conformance (slice 5)):

* C4a FIRST-SEED-DEFINES-TREE.  The first seed placed into an armed territory
  is accepted at its snapped surface point and DEFINES the territory's active
  vessel tree = the connected component of that point (recovered via
  ``VesselConnectivity.connected_component_at`` over the vessels-only surface).
* C4b LATER-SEED-SNAPS-TO-ACTIVE.  A later seed whose raw snap lands on a
  DIFFERENT connected component is re-snapped to the nearest point on the
  ACTIVE component — never placed off-tree.
* C4c NET SINGLE-COMPONENT.  After ANY sequence of clicks, every one of a
  territory's seeds lies on ONE connected component — the component of
  ``AnnotationPoints[territory][0]``.
* C5 ACTIVE-TREE HIGHLIGHT.  While a territory is armed, a pipeline-owned actor
  (no new displayable manager, ADR-0013) renders the active connected tree; its
  INPUT polydata is the seed[0] component (styling deferred — the input
  IDENTITY is pinned, not the appearance).
* #1a MODULE-INACTIVE-DECLINES.  With the owning module NOT active, an
  add-on-click places nothing (belt-and-suspenders beyond the armed flag).
* #1b ARMED-FLAG STILL GATES.  A dis-armed display node -> a click places
  nothing; ``enter()`` auto-arms nothing / ``exit()`` disarms (slice-4
  regression pins, re-verified under the slice-5 surface).

-- SEAMS THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

On BOTH ``TerritoryPlacementPipeline`` (3D) and ``TerritorySlicePipeline`` (2D),
extending the existing add-on-click path (``ProcessInteractionEvent`` ->
``_add_point``):

  * the LATER-seed constraint gate: after the raw surface snap and before the
    carrier write, when the active territory already carries >=1 seed, recover
    the active component (``connected_component_at`` seeded at index-0 over the
    vessels-only pick surface) and re-snap the click to the nearest point on
    THAT component when the raw snap lands on a different component;
  * ``activeTreePolyData() -> vtkPolyData | None`` — the recovered active tree
    for the active territory (the seed[0] component), or ``None`` when the
    active territory has no seed.  Used to assert C4/C5 without reaching into
    private caches;
  * ``highlightActor() -> vtkActor | None`` — the pipeline-owned active-tree
    highlight actor whose input polydata IS ``activeTreePolyData()`` while
    armed (C5); a THIRD actor alongside ``_seed_actor`` / ``_marker_actor``,
    not a new pipeline on the same display-node type (ADR-0013 §1);
  * ``SetModuleActive(bool)`` / ``IsModuleActive() -> bool`` — the module-active
    gate flag (concern #1); an add-on-click is declined when the module is not
    active, independent of the armed flag.

If the implementer names these differently, update the constants below — the
invariants are the SINGLE-COMPONENT seed set + the highlight-input identity +
the module-active decline, not the specific spelling.

-- WHY LAUNCHED-SLICER --

The pipelines need LayerDMLib (reachable only inside a launched Slicer with the
module loaded) + the wrapped ``vtkMRMLCustomTerritoriesNode`` carrier + the
shared ``vtkMRMLTerritoriesHighlightDisplayNode``.  A bare ``PythonSlicer -m
pytest`` has ``slicer.mrmlScene is None`` and LayerDMLib off the path, so every
test here SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards.  The
connectivity recovery itself is pure-VTK (covered bare by
``test_territories_connectivity.py``); here it runs on a REAL multi-component
vessel surface (two disjoint spheres) wired as the pick surface + the injected
pick core, so the CONSTRAINT is exercised end-to-end through the click path.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the PR-B seams (the later-seed constraint, the
``activeTreePolyData`` / ``highlightActor`` accessors, the module-active flag)
do not exist, so the ``hasattr`` guards skip-pend; the skips lift at the PR-B
implementation commit.  Under a launched Slicer, verify run-vs-skip in the CI
log once the seam lands — never trust overall green (the launched harness is
green-but-skipping prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0013-no-custom-displayable-manager.md  (pipeline-owned actor)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * Docs/design/connected-tree-seeding-plan.md  (C4 / C5 / concern #1)
  * VascularTerritories/VascularTerritoriesLib/VesselConnectivity.py
  * VascularTerritories/Testing/Python/test_territories_connectivity.py  (bare)
  * VascularTerritories/Testing/Python/test_territories_placement_pipeline.py
  * VascularTerritories/Testing/Python/test_territories_slice_pipeline.py
"""

from __future__ import annotations

import importlib

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
TERRITORY_A = "SegmentVII"

# The pure-VTK connectivity seam (PR-A; used to compute the EXPECTED active tree
# independently of the pipeline's own recovery).
CONNECTIVITY_MODULE = "VascularTerritoriesLib.VesselConnectivity"
CONNECTED_COMPONENT_FUNC = "connected_component_at"

# PR-B pipeline accessors (proposed; sharpen at landing).
ACTIVE_TREE_ACCESSOR = "activeTreePolyData"
HIGHLIGHT_ACTOR_ACCESSOR = "highlightActor"
MODULE_ACTIVE_SETTER = "SetModuleActive"

# Two well-separated sphere centres so their meshes never share a point and
# connectivity keeps them as two disjoint regions (the connectivity-test idiom).
CENTER_A = (0.0, 0.0, 0.0)
CENTER_B = (100.0, 0.0, 0.0)
RADIUS = 10.0


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in the sibling suites)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pipeline_or_skip():
    try:
        from VascularTerritoriesLib.TerritoryPlacementPipeline import (
            TerritoryPlacementPipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoryPlacementPipeline not importable ({exc!r}) -- ADR-0037 "
            "placement Pipeline / LayerDMLib not reachable (ADR-0027)."
        )
    return TerritoryPlacementPipeline


def _import_slice_pipeline_or_skip():
    try:
        from VascularTerritoriesLib.TerritorySlicePipeline import (
            TerritorySlicePipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritorySlicePipeline not importable ({exc!r}) -- ADR-0037 §2D "
            "slice Pipeline / LayerDMLib not reachable (ADR-0027)."
        )
    return TerritorySlicePipeline


def _import_pick_or_skip():
    try:
        from VesselSurfacePick import VesselSurfacePick
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselSurfacePick not importable ({exc!r}).")
    return VesselSurfacePick


def _import_interaction_state_or_skip():
    try:
        import TerritoryInteractionState as state
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoryInteractionState not importable ({exc!r}) -- the ADR-0037 "
            "shared display-node state module has not landed (ADR-0027)."
        )
    return state


def _connected_component_at_or_skip():
    """The PR-A pure-VTK connectivity helper, used to compute the EXPECTED tree."""
    try:
        module = importlib.import_module(CONNECTIVITY_MODULE)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{CONNECTIVITY_MODULE} not importable ({exc!r}) -- PR-A connectivity "
            "helper absent (ADR-0027)."
        )
    func = getattr(module, CONNECTED_COMPONENT_FUNC, None)
    if func is None:
        pytest.skip(
            f"{CONNECTIVITY_MODULE} has no {CONNECTED_COMPONENT_FUNC} -- PR-A "
            "connectivity helper absent (ADR-0027)."
        )
    return func


def _make_carrier_or_skip(slicer, name="ConstraintCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    for method in ("AddAnnotationPoint", "GetNumberOfAnnotationPoints", "GetNthAnnotationPoint"):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "annotation carrier has not landed (ADR-0027)."
            )
    return node


def _make_display_node_or_skip(slicer, name="ConstraintHighlightTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(HIGHLIGHT_DISPLAY_CLASS, name)
    if node is None:
        pytest.skip(
            f"{HIGHLIGHT_DISPLAY_CLASS} not registered -- the shared highlight "
            "display node (ADR-0036/0037) is unavailable (launched build)."
        )
    return node


def _require_constraint_seam_or_skip(pipeline):
    """Skip-pend unless the PR-B active-tree constraint accessor has landed.

    ``activeTreePolyData`` is the accessor the C4/C5 assertions read; its
    absence means the PR-B seam has not landed, so every constraint test
    collects + SKIP-PENDINGs cleanly and RUNS once PR-B lands (ADR-0027).
    """
    if not hasattr(pipeline, ACTIVE_TREE_ACCESSOR):
        pytest.skip(
            f"{type(pipeline).__name__} has no {ACTIVE_TREE_ACCESSOR}() accessor "
            "-- the ADR-0037 slice-5 (PR-B) active-tree seed constraint has not "
            "landed (ADR-0027)."
        )


# --------------------------------------------------------------------------- #
# Multi-component vessel surface: TWO disjoint spheres (A at origin, B at +x)
# --------------------------------------------------------------------------- #


def _sphere(center, radius=RADIUS):
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(16)
    source.SetPhiResolution(16)
    source.Update()
    return source.GetOutput()


def _two_disjoint_spheres():
    """A single polydata holding two DISJOINT sphere components (A then B)."""
    sphere_a = _sphere(CENTER_A)
    sphere_b = _sphere(CENTER_B)
    append = vtk.vtkAppendPolyData()
    append.AddInputData(sphere_a)
    append.AddInputData(sphere_b)
    append.Update()
    return append.GetOutput(), sphere_a, sphere_b


def _points_inside_sphere(polydata, center, radius, tolerance=1.0e-3):
    """Count ``polydata`` points on/inside the sphere ``(center, radius)``."""
    count = 0
    cx, cy, cz = center
    r2 = (radius + tolerance) ** 2
    for i in range(polydata.GetNumberOfPoints()):
        px, py, pz = polydata.GetPoint(i)
        if (px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2 <= r2:
            count += 1
    return count


def _bounds_center(polydata):
    b = polydata.GetBounds()
    return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)


class _FakeRenderer:
    """Display->world unprojects any pixel to a chosen +something ray.

    The ray hits whichever sphere the test selects: the fake pick core resolves
    the click to a fixed world point on sphere A or sphere B (see
    ``_StubPickToPoint``), so the renderer only needs to hand back a stable ray.
    """

    def SetDisplayPoint(self, x, y, z):  # noqa: N802 - VTK verb
        pass

    def DisplayToWorld(self):  # noqa: N802 - VTK verb
        pass

    def GetWorldPoint(self):  # noqa: N802 - VTK verb
        return (0.0, 0.0, 5.0, 1.0)

    def SetWorldPoint(self, *a):  # noqa: N802 - VTK verb
        pass

    def WorldToDisplay(self):  # noqa: N802 - VTK verb
        pass

    def GetDisplayPoint(self):  # noqa: N802 - VTK verb
        # Return a display point far from any seed so the click is an
        # add-on-click, never a grab.
        return (1.0e6, 1.0e6, 0.0)


class _Event:
    """A minimal interaction event at a fixed display pixel + type."""

    def __init__(self, etype, display_position=(100, 100)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def _surface_point_on(sphere_polydata):
    """A genuine surface point on ``sphere_polydata`` (its first mesh point)."""
    return tuple(sphere_polydata.GetPoint(0))


def _wire_pipeline_on_two_spheres_or_skip(
    slicer, pipeline, carrier, displayNode, monkeypatch, snap_targets
):
    """Wire the pipeline over the two-sphere surface with a scripted snap.

    ``snap_targets`` is a list of world points the RAW surface snap yields on
    successive clicks (the injected ``_event_world_on_surface`` return values).
    Each is a genuine point on sphere A or sphere B, so the constraint gate is
    what re-snaps an off-tree later click.  The pick surface is set to the two
    disjoint spheres so the pipeline's own ``connected_component_at`` recovery
    (over the vessels-only surface) has a real multi-component mesh to work on.
    """
    VesselSurfacePick = _import_pick_or_skip()
    for method in ("SetPickCore", "SetDisplayNode"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"{type(pipeline).__name__} has no {method} seam (ADR-0027)."
            )
    state = _import_interaction_state_or_skip()
    two_spheres, _sphere_a, _sphere_b = _two_disjoint_spheres()

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)
    # Inject the pick core over the REAL two-component surface (the vessels-only
    # pick surface PR-A resolves in production).  SetDisplayNode resets the pick,
    # so inject AFTER binding it.
    pipeline.SetPickCore(VesselSurfacePick(two_spheres))

    # Script the RAW snap so we choose which component each click lands on.  The
    # 3D and 2D pipelines both funnel the snapped world point through
    # ``_add_point`` after the constraint gate, so injecting the raw snap here
    # exercises the gate deterministically without a GL context.
    calls = {"i": 0}

    def _fake_snap(*_args, **_kwargs):
        i = calls["i"]
        calls["i"] = i + 1
        if i < len(snap_targets):
            return snap_targets[i]
        return snap_targets[-1]

    if hasattr(pipeline, "_event_world_on_surface"):
        monkeypatch.setattr(pipeline, "_event_world_on_surface", _fake_snap)
    elif hasattr(pipeline, "_snap_event_to_surface"):
        monkeypatch.setattr(pipeline, "_snap_event_to_surface", _fake_snap)
    else:
        pytest.skip(
            f"{type(pipeline).__name__} has no raw-snap seam to inject "
            "(_event_world_on_surface / _snap_event_to_surface) (ADR-0027)."
        )
    return two_spheres


def _click(pipeline):
    return pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent))


def _all_points(carrier, territory):
    n = carrier.GetNumberOfAnnotationPoints(territory)
    return [tuple(carrier.GetNthAnnotationPoint(territory, i)) for i in range(n)]


# =========================================================================== #
# C4a — the first seed defines the territory's active tree
# =========================================================================== #


def test_first_seed_defines_the_active_tree(monkeypatch):
    """C4a: the first click accepts the surface point + defines the active tree.

    Arming an EMPTY territory and clicking on sphere A places exactly one seed
    at A's surface point; the territory's active vessel tree is A's connected
    component (asserted via ``activeTreePolyData()`` matching the independent
    ``connected_component_at(surface, seedA)`` point-count + carrying zero B
    points).  ADR-0037 slice-5 "First seed defines the active vessel tree".
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_constraint_seam_or_skip(pipeline)
    connected_component_at = _connected_component_at_or_skip()

    seed_a = _surface_point_on(_sphere(CENTER_A))
    two_spheres = _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert _click(pipeline) is True
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "the first armed click must add EXACTLY ONE seed (C4a)."
    )

    active_tree = getattr(pipeline, ACTIVE_TREE_ACCESSOR)()
    assert active_tree is not None and active_tree.GetNumberOfPoints() > 0, (
        "after the first seed the pipeline must expose a non-empty active tree."
    )
    expected = connected_component_at(two_spheres, seed_a)
    assert active_tree.GetNumberOfPoints() == expected.GetNumberOfPoints(), (
        "the active tree must be sphere A's connected component "
        f"({active_tree.GetNumberOfPoints()} != {expected.GetNumberOfPoints()}) "
        "-- the first seed DEFINES the tree (ADR-0037 slice 5)."
    )
    assert _points_inside_sphere(active_tree, CENTER_B, RADIUS) == 0, (
        "the active tree must carry ZERO points from the disjoint B system."
    )


# =========================================================================== #
# C4b — a later seed on a different component snaps onto the active tree
# =========================================================================== #


def test_later_seed_on_other_component_snaps_to_active_tree(monkeypatch):
    """C4b: a later click on sphere B lands ON sphere A's component, not B.

    With a seed already on A (the active tree), a click whose RAW snap lands on
    sphere B is re-snapped to the nearest point on the ACTIVE component: the
    placed point lies within A's component (containment check) and NOT on B.
    Exactly one new seed; all seeds still lie on A.  ADR-0037 slice-5 "Seeds
    constrained to the active tree".
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_constraint_seam_or_skip(pipeline)

    seed_a = _surface_point_on(_sphere(CENTER_A))
    seed_b = _surface_point_on(_sphere(CENTER_B))
    _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a, seed_b]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()

    assert _click(pipeline) is True  # first seed on A defines the tree
    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert _click(pipeline) is True  # raw snap on B -> must be re-snapped to A

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "the constrained later click must add EXACTLY ONE seed (never two, "
        "never zero)."
    )
    points = _all_points(carrier, TERRITORY_A)
    for i, p in enumerate(points):
        dist_a2 = sum((p[k] - CENTER_A[k]) ** 2 for k in range(3))
        dist_b2 = sum((p[k] - CENTER_B[k]) ** 2 for k in range(3))
        assert dist_a2 <= (RADIUS + 1.0e-2) ** 2, (
            f"seed {i} at {p} must lie on sphere A's component (the active tree)."
        )
        assert dist_b2 > (RADIUS + 1.0) ** 2, (
            f"seed {i} at {p} must NOT lie on the disjoint sphere B -- an "
            "off-tree click is re-snapped to the active tree (ADR-0037 slice 5)."
        )


# =========================================================================== #
# C4c — net single-component after A -> B -> A
# =========================================================================== #


def test_net_single_component_after_a_b_a_clicks(monkeypatch):
    """C4c: after clicks targeting A, B, then A, every seed lies on A's component.

    The net invariant: no matter the raw-snap sequence, all of a territory's
    seeds lie on ONE connected component -- the component of
    ``AnnotationPoints[territory][0]`` (ADR-0037 slice-5 Conformance [test]
    "never straddles two trees").
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_constraint_seam_or_skip(pipeline)
    connected_component_at = _connected_component_at_or_skip()

    seed_a0 = _surface_point_on(_sphere(CENTER_A))
    seed_b = _surface_point_on(_sphere(CENTER_B))
    # A second genuine point on A (opposite pole) so the A-targeting clicks are
    # distinct surface points, not a repeat of index-0.
    seed_a1 = (CENTER_A[0], CENTER_A[1], CENTER_A[2] + RADIUS)
    two_spheres = _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a0, seed_b, seed_a1]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()

    assert _click(pipeline) is True  # A (defines tree)
    assert _click(pipeline) is True  # raw B (must re-snap to A)
    assert _click(pipeline) is True  # A

    points = _all_points(carrier, TERRITORY_A)
    assert len(points) == 3, "each of the three clicks must add exactly one seed."

    # Every seed lies on the component of index-0.
    index0_component = connected_component_at(two_spheres, points[0])
    assert _points_inside_sphere(index0_component, CENTER_B, RADIUS) == 0, (
        "the index-0 component (the active tree) must be A-only."
    )
    for i, p in enumerate(points):
        dist_b2 = sum((p[k] - CENTER_B[k]) ** 2 for k in range(3))
        assert dist_b2 > (RADIUS + 1.0) ** 2, (
            f"seed {i} at {p} must not lie on the disjoint B system -- every "
            "seed lies on the index-0 component (ADR-0037 slice 5 C4c)."
        )


# =========================================================================== #
# C5 — the active-tree highlight actor's input is the seed[0] component
# =========================================================================== #


def test_active_tree_highlight_actor_input_is_seed_zero_component(monkeypatch):
    """C5: the highlight actor's input polydata == the seed[0] component.

    While a territory is armed, a pipeline-owned actor (no new DM, ADR-0013)
    renders the active connected tree; its INPUT polydata is the seed[0]
    component (same point count / bounds as ``connected_component_at(surface,
    seed0)``).  Styling is deferred -- only the input IDENTITY is pinned.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_constraint_seam_or_skip(pipeline)
    connected_component_at = _connected_component_at_or_skip()
    if not hasattr(pipeline, HIGHLIGHT_ACTOR_ACCESSOR):
        pytest.skip(
            f"TerritoryPlacementPipeline has no {HIGHLIGHT_ACTOR_ACCESSOR}() "
            "accessor -- the ADR-0037 slice-5 (PR-B) active-tree highlight has "
            "not landed (ADR-0027)."
        )

    seed_a = _surface_point_on(_sphere(CENTER_A))
    two_spheres = _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()
    assert _click(pipeline) is True  # define the active tree

    actor = getattr(pipeline, HIGHLIGHT_ACTOR_ACCESSOR)()
    assert actor is not None, (
        "the pipeline must own an active-tree highlight actor while armed (C5)."
    )
    mapper = actor.GetMapper()
    assert mapper is not None, "the highlight actor must carry a mapper."
    actor_input = mapper.GetInput()
    assert actor_input is not None and actor_input.GetNumberOfPoints() > 0, (
        "the highlight actor's input must be the non-empty active tree."
    )

    expected = connected_component_at(two_spheres, seed_a)
    assert actor_input.GetNumberOfPoints() == expected.GetNumberOfPoints(), (
        "the highlight actor's INPUT must be the seed[0] component "
        f"({actor_input.GetNumberOfPoints()} != {expected.GetNumberOfPoints()}) "
        "-- the input identity is pinned, styling deferred (ADR-0037 slice 5)."
    )
    assert _points_inside_sphere(actor_input, CENTER_B, RADIUS) == 0, (
        "the highlight tree must carry ZERO points from the disjoint B system."
    )
    # The highlight input tracks the pipeline's own active-tree accessor.
    active_tree = getattr(pipeline, ACTIVE_TREE_ACCESSOR)()
    assert actor_input.GetNumberOfPoints() == active_tree.GetNumberOfPoints(), (
        "the highlight actor input must be the SAME component the pipeline "
        "exposes as its active tree (C5)."
    )


# =========================================================================== #
# #1a — the module-active gate declines an add-on-click while inactive
# =========================================================================== #


def test_module_inactive_declines_add_on_click(monkeypatch):
    """#1a: an add-on-click places nothing while the module is NOT active.

    Belt-and-suspenders beyond the armed flag (concern #1): even ARMED, an
    add-on-click is declined while the owning module is inactive, so no view
    lands a seed while VascularTerritories is not the active module.  Modelled
    via the ``SetModuleActive`` gate the seam exposes.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    if not hasattr(pipeline, MODULE_ACTIVE_SETTER):
        pytest.skip(
            f"TerritoryPlacementPipeline has no {MODULE_ACTIVE_SETTER}() gate -- "
            "the ADR-0037 slice-5 (PR-B) module-active gate (concern #1) has not "
            "landed (ADR-0027)."
        )

    seed_a = _surface_point_on(_sphere(CENTER_A))
    _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()

    # Armed, but the module is inactive: the add-on-click must place nothing.
    getattr(pipeline, MODULE_ACTIVE_SETTER)(False)
    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    _click(pipeline)
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "an add-on-click must place NOTHING while the module is inactive -- the "
        "module-active gate (concern #1) is belt-and-suspenders beyond the "
        "armed flag (ADR-0037 slice 5)."
    )

    # Re-activating the module lets the same armed click land a seed.
    getattr(pipeline, MODULE_ACTIVE_SETTER)(True)
    assert _click(pipeline) is True
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "with the module active + armed, the add-on-click must land ONE seed."
    )


# =========================================================================== #
# #1b — the armed flag still gates (slice-4 regression re-pin under slice 5)
# =========================================================================== #


def test_disarmed_display_node_click_places_nothing(monkeypatch):
    """#1b: a dis-armed display node -> an add-on-click places nothing.

    Re-pins the slice-4 arm gate at the pipeline level under the slice-5
    surface: with the shared display node dis-armed, an add-on-click adds no
    seed (ADR-0037 §Decision 3; a regression guard for the PR-B changes).
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()

    seed_a = _surface_point_on(_sphere(CENTER_A))
    _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    # Explicitly dis-armed on the shared display node.
    state.set_armed(displayNode, False)
    if hasattr(pipeline, MODULE_ACTIVE_SETTER):
        getattr(pipeline, MODULE_ACTIVE_SETTER)(True)  # isolate the arm gate

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    _click(pipeline)
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a dis-armed add-on-click must place nothing (ADR-0037 §Decision 3)."
    )


def test_enter_auto_arms_nothing_exit_disarms():
    """#1b: enter() auto-arms nothing; exit() disarms (module-active gate).

    Re-pins the slice-4 module-active gate at the widget level under slice 5:
    ``enter()`` leaves the shared display node dis-armed, and ``exit()`` clears
    an armed state (ADR-0037 slice-4 amendment §Module-active gate).  Launched;
    needs the composed widget.
    """
    _slicer_or_skip()
    import slicer as _slicer  # noqa: F811 — the widget lives on the launched module

    try:
        from VascularTerritories import VascularTerritoriesWidget
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VascularTerritoriesWidget not importable ({exc!r}) (ADR-0027).")

    widget = VascularTerritoriesWidget()
    widget.setup()
    # Drop the widget's scene observers before the autouse scene-clear fires.
    for event, handler in (
        (_slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (_slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(_slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 — best-effort across widget shapes
            pass

    displayNode = getattr(widget, "_highlightDisplayNode", None)
    if displayNode is None:
        widget.cleanup()
        pytest.skip(
            "widget did not expose the shared display node handle (ADR-0027)."
        )
    state = _import_interaction_state_or_skip()

    widget.enter()
    assert state.is_armed(displayNode) is False, (
        "enter() must auto-arm nothing (ADR-0037 slice-4 module-active gate)."
    )

    state.set_armed(displayNode, True)
    widget.exit()
    assert state.is_armed(displayNode) is False, (
        "exit() must disarm placement (ADR-0037 slice-4 module-active gate)."
    )

    widget.cleanup()


# =========================================================================== #
# C4 twin — the SLICE pipeline enforces the same net single-component invariant
# =========================================================================== #


def test_slice_pipeline_later_seed_snaps_to_active_tree(monkeypatch):
    """C4b (2D twin): the slice pipeline re-snaps an off-tree later seed to A.

    The 2D ``TerritorySlicePipeline`` shares the commit-time constraint gate
    (the snap runs in world space, so the slice-normal ray result feeds the
    SAME gate).  With a seed on A, a slice click whose raw snap lands on B is
    re-snapped onto A's component -- exactly one new seed, all seeds on A.
    """
    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_slice_pipeline_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_constraint_seam_or_skip(pipeline)

    seed_a = _surface_point_on(_sphere(CENTER_A))
    seed_b = _surface_point_on(_sphere(CENTER_B))
    _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a, seed_b]
    )
    if hasattr(pipeline, "SetActiveTerritory"):
        pipeline.SetActiveTerritory(TERRITORY_A)
    else:
        state = _import_interaction_state_or_skip()
        state.set_active_territory(displayNode, TERRITORY_A)
    state = _import_interaction_state_or_skip()
    state.set_armed(displayNode, True)
    if hasattr(pipeline, MODULE_ACTIVE_SETTER):
        getattr(pipeline, MODULE_ACTIVE_SETTER)(True)

    assert _click(pipeline) is True  # first seed on A defines the tree
    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert _click(pipeline) is True  # raw snap on B -> re-snapped to A

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "the 2D constrained later click must add EXACTLY ONE seed."
    )
    for i, p in enumerate(_all_points(carrier, TERRITORY_A)):
        dist_b2 = sum((p[k] - CENTER_B[k]) ** 2 for k in range(3))
        assert dist_b2 > (RADIUS + 1.0) ** 2, (
            f"slice seed {i} at {p} must not lie on the disjoint B system -- the "
            "2D pipeline shares the active-tree constraint (ADR-0037 slice 5)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
