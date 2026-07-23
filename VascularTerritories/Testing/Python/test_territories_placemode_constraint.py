# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 5 (REVISED) — multi-system territory seeding placement.

The LANDED slice-5 design LOCKED each territory to ONE connected vessel tree:
the first seed defined the active component, later seeds were snapped back onto
it, and the component glowed.  That is clinically wrong — a vascular territory
may legitimately be defined by seeds in MULTIPLE disjoint systems (portal +
hepatic), which are disjoint components whose centerlines are derived
INDEPENDENTLY and BOTH feed the one territory's map region.  The revised design
(Docs/design/multi-system-territory-plan.md, §Part A / §Part D) REMOVES the
single-tree placement lock and the glow halo.

The invariants pinned here (revised ADR-0037 §"Amendment — connected-tree-
constrained centerline seeding (slice 5)" §Conformance):

* NO STRADDLE-SNAP.  With a seed already on structure A, a later add-on-click
  whose surface snap lands on a DIFFERENT visible structure B is placed WHERE
  IT LANDS — on B — never re-snapped back onto A.  A territory MAY straddle
  disjoint systems: two seeds, two structures.  (Inverts the retired C4b/C4c
  active-tree constraint.)
* VISIBILITY-GATED PICK IS THE ONLY PLACEMENT CONSTRAINT.  The pick surface
  stays vessels-only + visibility-gated (hide a system to avoid stray seeds);
  this is the RETAINED gate, exercised by test_territories_surface_resolution
  (T1c) — not re-pinned here.
* #1a MODULE-INACTIVE-DECLINES.  With the owning module NOT active, an
  add-on-click places nothing (belt-and-suspenders beyond the armed flag).
* #1b ARMED-FLAG STILL GATES.  A dis-armed display node -> a click places
  nothing; ``enter()`` auto-arms nothing / ``exit()`` disarms (slice-4
  regression pins, re-verified under the revised surface).

-- WHAT THIS FILE RETIRED (revised design of record) --

The landed slice-5 (PR-B) suite pinned the REMOVED lock + halo:
``test_first_seed_defines_the_active_tree`` (C4a),
``test_later_seed_on_other_component_snaps_to_active_tree`` (C4b),
``test_net_single_component_after_a_b_a_clicks`` (C4c),
``test_active_tree_highlight_actor_input_is_seed_zero_component`` (C5), and the
2D twin ``test_slice_pipeline_later_seed_snaps_to_active_tree``.  Those asserted
``activeTreePolyData`` / ``highlightActor`` / ``_constrain_to_active_tree`` — all
removed.  C4b/C4c/C5 are INVERTED into ``test_later_seed_on_other_structure_stays``
(3D) + ``test_slice_pipeline_later_seed_on_other_structure_stays`` (2D); the C5
highlight actor is retired to ``test_active_tree_highlight_actor_is_gone`` (an
absence pin with a credible creep-in path — the named attribute must be removed,
per the no-colour-of-the-sky rule).

-- SEAMS THIS FILE READS --

On BOTH ``TerritoryPlacementPipeline`` (3D) and ``TerritorySlicePipeline`` (2D):

  * the add-on-click path (``ProcessInteractionEvent`` -> ``_add_point``) with
    NO ``_constrain_to_active_tree`` gate — the raw surface-snapped ``world``
    goes straight to ``_add_point`` (no straddle-snap);
  * ``SetPickCore`` / ``SetDisplayNode`` / the raw-snap seam
    (``_event_world_on_surface`` 3D / ``_snap_event_to_surface`` 2D) — the
    injection surface used to script which structure each click lands on;
  * ``SetModuleActive(bool)`` / ``IsModuleActive()`` — the module-active gate
    (concern #1);
  * the REMOVED ``activeTreePolyData`` / ``highlightActor`` /
    ``_highlight_tree_actor`` — asserted GONE.

If the implementer names these differently, update the constants below — the
invariants are NO straddle-snap + the module-active decline + the retired halo,
not the specific spelling.

-- WHY LAUNCHED-SLICER --

The pipelines need LayerDMLib (reachable only inside a launched Slicer with the
module loaded) + the wrapped ``vtkMRMLCustomTerritoriesNode`` carrier + the
shared ``vtkMRMLTerritoriesHighlightDisplayNode``.  A bare ``PythonSlicer -m
pytest`` has ``slicer.mrmlScene is None`` and LayerDMLib off the path, so every
test here SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards.  The
SUT surface is TWO disjoint spheres (``vtkAppendPolyData`` of two separated
``vtkSphereSource``) wired as the vessels-only pick surface, with the
stub-renderer + injected-pick pattern from test_territories_placement_pipeline,
so clicks map to chosen world points on structure A or structure B.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

The no-straddle-snap invariant RUNS once the lock is removed; before then the
landed lock re-snaps the second seed onto A and the test FAILS (red->green in
reverse — it goes GREEN when the implementer deletes ``_constrain_to_active_tree``).
The retired-halo absence test likewise flips to PASS when the attribute is
removed.  Under a launched Slicer, verify run-vs-skip in the CI log once the
revision lands — never trust overall green (the launched harness is
green-but-skipping prone).

See also:
  * Docs/design/multi-system-territory-plan.md  (§Part A remove; §Part C tests)
  * Docs/adr/0037-vascular-territories-off-markups.md
    (§Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0013-no-custom-displayable-manager.md
  * Docs/adr/0027-invariant-test-first.md
  * VascularTerritories/VascularTerritoriesLib/TerritoryPlacementPipeline.py
  * VascularTerritories/VascularTerritoriesLib/TerritorySlicePipeline.py
  * VascularTerritories/Testing/Python/test_territories_seed_structure.py  (bare)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
TERRITORY_A = "SegmentVII"

MODULE_ACTIVE_SETTER = "SetModuleActive"

# The active-tree lock + halo accessors the revised design REMOVES; the absence
# pin asserts these are gone.
RETIRED_TREE_ACCESSOR = "activeTreePolyData"
RETIRED_HIGHLIGHT_ACCESSOR = "highlightActor"
RETIRED_CONSTRAINT_METHOD = "_constrain_to_active_tree"
RETIRED_HALO_ACTOR_ATTR = "_highlight_tree_actor"

# Two well-separated sphere centres so their meshes never share a point and
# connectivity keeps them as two disjoint structures.
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


def _require_no_straddle_snap_seam_or_skip(pipeline):
    """Skip-pend unless the pipeline's add-on-click path + injection seams exist.

    The revised design REMOVES ``_constrain_to_active_tree`` — the raw
    surface-snapped world goes straight to ``_add_point``.  We can only assert
    "no straddle-snap" once the pipeline exposes the pick + display seams; if
    they are absent the pipeline has not landed at all, so skip-pend (ADR-0027).
    """
    for method in ("SetPickCore", "SetDisplayNode", "SetActiveTerritory", "Arm"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"{type(pipeline).__name__} has no {method} seam -- the ADR-0037 "
                "placement pipeline has not landed (ADR-0027)."
            )


# --------------------------------------------------------------------------- #
# Multi-structure vessel surface: TWO disjoint spheres (A at origin, B at +x)
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
    """A single polydata holding two DISJOINT sphere structures (A then B)."""
    sphere_a = _sphere(CENTER_A)
    sphere_b = _sphere(CENTER_B)
    append = vtk.vtkAppendPolyData()
    append.AddInputData(sphere_a)
    append.AddInputData(sphere_b)
    append.Update()
    return append.GetOutput(), sphere_a, sphere_b


def _bounds_center(polydata):
    b = polydata.GetBounds()
    return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)


class _FakeRenderer:
    """Display->world unprojects any pixel to a chosen ray.

    The fake pick core resolves the click to a fixed world point on sphere A or
    sphere B (see the scripted raw snap), so the renderer only needs to hand
    back a stable ray.
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

    ``snap_targets`` is a list of world points the raw surface snap yields on
    successive clicks (the injected ``_event_world_on_surface`` /
    ``_snap_event_to_surface`` return values).  Each is a genuine point on
    sphere A or sphere B; the revised placement path must place each WHERE IT
    LANDS (no straddle-snap).  The pick surface is the two disjoint spheres so
    the pipeline resolves the same multi-structure mesh production uses.
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
    # Inject the pick core over the REAL two-structure surface (the vessels-only
    # pick surface production resolves).  SetDisplayNode resets the pick, so
    # inject AFTER binding it.
    pipeline.SetPickCore(VesselSurfacePick(two_spheres))

    # Script the raw snap so we choose which structure each click lands on.  The
    # 3D and 2D pipelines both funnel the snapped world point through
    # ``_add_point``; injecting the raw snap exercises the placement path
    # deterministically without a GL context.
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


def _on_structure(point, center, tol=1.0e-2):
    d2 = sum((point[k] - center[k]) ** 2 for k in range(3))
    return d2 <= (RADIUS + tol) ** 2


# =========================================================================== #
# NO STRADDLE-SNAP — a later seed on a DIFFERENT structure STAYS there (3D)
# =========================================================================== #


def test_later_seed_on_other_structure_stays(monkeypatch):
    """A later click on structure B lands ON B — not re-snapped onto A.

    INVERTS the retired C4b/C4c active-tree constraint.  With a seed already on
    structure A, an add-on-click whose surface snap lands on the DISJOINT
    structure B places the seed WHERE IT LANDS (on B): exactly one new seed,
    the territory now STRADDLES the two systems (one seed on A, one on B).  A
    territory may legitimately own seeds across multiple disjoint structures
    (revised ADR-0037 slice-5 Conformance "no straddle-snap"; multi-system plan
    §Part A).
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    _require_no_straddle_snap_seam_or_skip(pipeline)

    seed_a = _surface_point_on(_sphere(CENTER_A))
    seed_b = _surface_point_on(_sphere(CENTER_B))
    _wire_pipeline_on_two_spheres_or_skip(
        slicer, pipeline, carrier, displayNode, monkeypatch, [seed_a, seed_b]
    )
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()
    if hasattr(pipeline, MODULE_ACTIVE_SETTER):
        getattr(pipeline, MODULE_ACTIVE_SETTER)(True)

    assert _click(pipeline) is True  # first seed on A
    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert _click(pipeline) is True  # snap on B -> must STAY on B

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "the second add-on-click must add EXACTLY ONE seed."
    )
    points = _all_points(carrier, TERRITORY_A)
    assert len(points) == 2

    on_a = [p for p in points if _on_structure(p, CENTER_A)]
    on_b = [p for p in points if _on_structure(p, CENTER_B)]
    assert len(on_a) == 1, (
        f"exactly one seed must remain on structure A; got {len(on_a)} of "
        f"{points}."
    )
    assert len(on_b) == 1, (
        "the later seed placed over structure B must STAY on B -- the revised "
        "design does NOT re-snap it back onto A's active tree (revised ADR-0037 "
        f"slice 5, no straddle-snap); got {len(on_b)} B-seeds of {points}."
    )


# =========================================================================== #
# NO STRADDLE-SNAP — the SLICE (2D) pipeline behaves the same
# =========================================================================== #


def test_slice_pipeline_later_seed_on_other_structure_stays(monkeypatch):
    """2D twin: a slice add-on-click on structure B stays on B (no snap).

    INVERTS the retired 2D ``test_slice_pipeline_later_seed_snaps_to_active_tree``.
    The slice pipeline shares the commit-time placement path (the snap runs in
    world space), so a slice click whose raw snap lands on B places its seed on
    B — the territory straddles the two systems (revised ADR-0037 slice 5).
    """
    slicer = _slicer_or_skip()
    TerritorySlicePipeline = _import_slice_pipeline_or_skip()
    pipeline = TerritorySlicePipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    for method in ("SetPickCore", "SetDisplayNode"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"{type(pipeline).__name__} has no {method} seam (ADR-0027)."
            )

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

    assert _click(pipeline) is True  # first seed on A
    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert _click(pipeline) is True  # snap on B -> must STAY on B

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before + 1, (
        "the 2D later click must add EXACTLY ONE seed."
    )
    points = _all_points(carrier, TERRITORY_A)
    on_b = [p for p in points if _on_structure(p, CENTER_B)]
    assert len(on_b) == 1, (
        "the 2D later seed over structure B must STAY on B -- the revised slice "
        "pipeline does NOT re-snap it onto A (revised ADR-0037 slice 5); got "
        f"{on_b} of {points}."
    )


# =========================================================================== #
# RETIRED HALO — the active-tree highlight actor + lock method are GONE
# =========================================================================== #


def test_active_tree_highlight_actor_is_gone(monkeypatch):
    """The active-tree glow halo + single-tree lock accessors are REMOVED.

    The revised design deletes the glow halo (``highlightActor`` /
    ``activeTreePolyData`` / ``_highlight_tree_actor``) and the single-tree lock
    (``_constrain_to_active_tree``).  This is an ABSENCE pin with a credible
    creep-in path (the named attributes exist on the landed branch and must be
    deleted, per the no-colour-of-the-sky rule): assert the pipeline no longer
    exposes any of them.  The SEED-hover halo (``_halo_actor``) is unrelated and
    STAYS — not asserted here.

    Red->green: FAILS while the landed lock+halo attributes survive; PASSES once
    the implementer removes them (revised ADR-0037 slice 5, §Part A).
    """
    _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    # Only meaningful once the pipeline is a real, wired instance; if the core
    # placement seams are absent the pipeline has not landed at all.
    if not hasattr(pipeline, "SetDisplayNode") or not hasattr(pipeline, "Arm"):
        pytest.skip(
            "TerritoryPlacementPipeline core seams absent -- pipeline has not "
            "landed (ADR-0027)."
        )

    for attr in (
        RETIRED_TREE_ACCESSOR,
        RETIRED_HIGHLIGHT_ACCESSOR,
        RETIRED_CONSTRAINT_METHOD,
        RETIRED_HALO_ACTOR_ATTR,
    ):
        assert not hasattr(pipeline, attr), (
            f"the single-tree lock + glow halo attribute {attr!r} must be "
            "REMOVED -- a territory may straddle disjoint systems, so the "
            "active-tree lock+halo are retired (revised ADR-0037 slice 5, "
            "§Part A)."
        )


# =========================================================================== #
# #1a — the module-active gate declines an add-on-click while inactive
# =========================================================================== #


def test_module_inactive_declines_add_on_click(monkeypatch):
    """#1a: an add-on-click places nothing while the module is NOT active.

    RETAINED from the landed suite (unaffected by the lock removal): even ARMED,
    an add-on-click is declined while the owning module is inactive, so no view
    lands a seed while VascularTerritories is not the active module.  Modelled
    via the ``SetModuleActive`` gate.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    if not hasattr(pipeline, MODULE_ACTIVE_SETTER):
        pytest.skip(
            f"TerritoryPlacementPipeline has no {MODULE_ACTIVE_SETTER}() gate -- "
            "the ADR-0037 slice-5 module-active gate (concern #1) has not landed "
            "(ADR-0027)."
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
# #1b — the armed flag still gates (slice-4 regression re-pin)
# =========================================================================== #


def test_disarmed_display_node_click_places_nothing(monkeypatch):
    """#1b: a dis-armed display node -> an add-on-click places nothing.

    Re-pins the slice-4 arm gate at the pipeline level under the revised
    surface: with the shared display node dis-armed, an add-on-click adds no
    seed (ADR-0037 §Decision 3; a regression guard for the revision).
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

    Re-pins the slice-4 module-active gate at the widget level under the
    revision: ``enter()`` leaves the shared display node dis-armed, and
    ``exit()`` clears an armed state (ADR-0037 slice-4 amendment §Module-active
    gate).  Launched; needs the composed widget.
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
