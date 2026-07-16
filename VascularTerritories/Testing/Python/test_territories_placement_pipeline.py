# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-1 — the annotation placement/edit Pipeline seam.

ADR-0037 §Decision 2 routes vessel-annotation placement + edit through a
LayerDM scripted Pipeline's interaction seam (ADR-0032 /ADR-0033), reusing
the already-built ``VesselSurfacePick`` (ray-onto-surface) + the adhering
highlight.  There is NO markup place mode and NO annotation state machine
(ADR-0037 §Decision 2 + §Alternatives) — add-on-click / drag-to-edit /
delete-from-table is the whole lifecycle:

  * a CLICK claims the gesture and adds EXACTLY ONE surface-snapped point
    to the carrier (on the mesh, distance ~= 0);
  * a DRAG edits the NEAREST existing point;
  * a BARE MOVE is DECLINED (``CanProcessInteractionEvent`` returns
    ``(False, +inf)``) so the camera is untouched (ADR-0033) — beyond
    raising the adhering highlight as a side effect;
  * DELETE removes exactly one point;
  * an unrelated ``Modified`` causes no drift.

This file pins the Stage-1 increments + the Stage-2 shared-display-node
routing on the placement Pipeline:

* i3 — PLACEMENT click->add + bare-move decline.
* i4 — EDIT (drag) + DELETE, and no-drift-on-unrelated-Modified.
* i5 — SHARED DISPLAY-NODE routing (Stage 2 / the 3D-fix contract): with a
  display node present, ``Arm()`` / ``SetActiveTerritory()`` publish onto it
  and read back via ``IsArmed()`` / ``GetActiveTerritory()``, and a click
  routes into the display-node-resolved carrier + ACTIVE territory.  The
  bare-unit i3/i4 path (``SetPickCore`` + ``SetCarrier``, no display node)
  keeps working via the instance-field fallback.

The point storage lives on ``vtkMRMLCustomTerritoriesNode`` (the carrier
pinned by ``test_territories_annotation_carrier.py``); this file pins the
Pipeline that WRITES to it via the interaction seam.

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

The placement Pipeline mirrors ``LiverBezierSurfacePipeline`` /
``ControlPolygonPipeline`` (the resection interaction-test seams):

  * module path ``VascularTerritoriesLib.TerritoryPlacementPipeline``,
    class ``TerritoryPlacementPipeline`` (a LayerDM scripted Pipeline);
  * ``CanProcessInteractionEvent(eventData) -> (bool, float)`` —
    arbitration; a bare move returns ``(False, sys.float_info.max)`` and
    only raises the highlight as a side effect (ADR-0033);
  * ``ProcessInteractionEvent(eventData) -> bool`` — a left-button PRESS
    (click) adds one surface-snapped point; a grabbed MOVE (drag) edits
    the nearest point; DELETE removes one;
  * injection seams reused from the highlight/resection suites:
    ``_safe_get_renderer`` (monkeypatched to a stub), ``SetPickCore`` (the
    ``VesselSurfacePick`` over a known surface), and a
    display-node/carrier back-reference (``SetDisplayNode`` deriving the
    ``vtkMRMLCustomTerritoriesNode`` carrier + its active territory id).

-- WHY LAUNCHED-SLICER --

The Pipeline needs LayerDMLib (reachable only inside a launched Slicer
with the module loaded) + the wrapped ``vtkMRMLCustomTerritoriesNode``
carrier.  A bare ``PythonSlicer -m pytest`` has ``slicer.mrmlScene is
None`` and LayerDMLib off the path, so every test here SKIPS CLEANLY via
the shared ``slicer_pytest_support`` guards.  The pick geometry itself is
pure-VTK and covered bare by ``test_vessel_surface_pick.py``.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the Pipeline + carrier API do not exist, so the import
/ ``hasattr`` guards skip-pend; the skips lift at the implementation
commit.  Under a launched Slicer, verify run-vs-skip in the CI log once
the seam lands — never trust overall green.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (the decision)
  * Docs/adr/0032-v2-interaction-via-layerdm-pipeline-seam.md  (the seam)
  * Docs/adr/0033-control-polygon-display-aspect.md  (hover-decline)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/Testing/Python/test_vessel_surface_pick.py  (pick core)
  * VascularTerritories/Testing/Python/test_vessel_highlight_pipeline.py
  * LiverResections/Testing/Python/test_pipeline_slicing_plane_init_placement.py
  * VascularTerritories/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import sys

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
TERRITORY_A = "SegmentVII"
TERRITORY_B = "SegmentVIII"

# Carrier API seam (also pinned by test_territories_annotation_carrier.py).
ADD_POINT_METHOD = "AddAnnotationPoint"
COUNT_METHOD = "GetNumberOfAnnotationPoints"
GET_NTH_METHOD = "GetNthAnnotationPoint"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pipeline_or_skip():
    """Import the placement Pipeline class or skip-pend (ADR-0027)."""
    try:
        from VascularTerritoriesLib.TerritoryPlacementPipeline import (
            TerritoryPlacementPipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoryPlacementPipeline not importable ({exc!r}) -- the "
            "ADR-0037 placement Pipeline (Stage-1 i3/i4) has not landed OR "
            "LayerDMLib is not reachable in this environment.  The skip lifts "
            "at the implementation commit (ADR-0027)."
        )
    return TerritoryPlacementPipeline


def _import_pick_or_skip():
    try:
        from VesselSurfacePick import VesselSurfacePick
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselSurfacePick not importable ({exc!r}).")
    return VesselSurfacePick


def _make_carrier_or_skip(slicer, name="PlacementCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- module Logic "
            "RegisterNodes() must wire this up (launched build)."
        )
    for method in (ADD_POINT_METHOD, COUNT_METHOD, GET_NTH_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "annotation carrier (Stage-1 i1) has not landed.  The skip "
                "lifts at the implementation commit (ADR-0027)."
            )
    return node


def _make_display_node_or_skip(slicer, name="PlacementHighlightTest"):
    """Mint the shared highlight display node, or skip-pend (ADR-0027)."""
    node = slicer.mrmlScene.AddNewNodeByClass(HIGHLIGHT_DISPLAY_CLASS, name)
    if node is None:
        pytest.skip(
            f"{HIGHLIGHT_DISPLAY_CLASS} not registered -- the shared highlight "
            "display node (ADR-0036/0037) is unavailable (launched build)."
        )
    return node


def _import_interaction_state_or_skip():
    """Import the shared interaction-state accessors, or skip-pend (ADR-0027)."""
    try:
        import TerritoryInteractionState as state
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoryInteractionState not importable ({exc!r}) -- the ADR-0037 "
            "shared display-node state module has not landed (ADR-0027)."
        )
    return state


def _unit_sphere():
    source = vtk.vtkSphereSource()
    source.SetRadius(1.0)
    source.SetThetaResolution(64)
    source.SetPhiResolution(64)
    source.Update()
    return source.GetOutput()


def _distance_to_surface(polydata, point) -> float:
    locator = vtk.vtkCellLocator()
    locator.SetDataSet(polydata)
    locator.BuildLocator()
    closest = [0.0, 0.0, 0.0]
    cell_id = vtk.reference(0)
    sub_id = vtk.reference(0)
    dist2 = vtk.reference(0.0)
    locator.FindClosestPoint(list(point), closest, cell_id, sub_id, dist2)
    return float(dist2) ** 0.5


class _FakeRenderer:
    """A renderer whose display->world unprojects to a fixed +z ray.

    Any display pixel maps to the ``(0, 0, 5)``->``(0, 0, -5)`` ray a unit
    sphere at the origin is hit by at the north pole ``(0, 0, 1)`` — the
    same double the highlight-Pipeline suite uses.
    """

    def __init__(self):
        self._display = [0.0, 0.0, 0.0]

    def SetDisplayPoint(self, x, y, z):  # noqa: N802 - VTK verb
        self._display = [x, y, z]

    def DisplayToWorld(self):  # noqa: N802 - VTK verb
        pass

    def GetWorldPoint(self):  # noqa: N802 - VTK verb
        if self._display[2] <= 0.0:
            return (0.0, 0.0, 5.0, 1.0)
        return (0.0, 0.0, -5.0, 1.0)


class _Event:
    """A minimal interaction event at a fixed display pixel + type."""

    def __init__(self, etype, display_position=(100, 100)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch):
    """Attach the doubles + carrier onto the Pipeline via its unit seams.

    Skips if the Pipeline does not expose the reused injection seams
    (``SetPickCore`` + a display-node/carrier back-reference) — the skip
    lifts when the ADR-0037 placement Pipeline lands them.
    """
    VesselSurfacePick = _import_pick_or_skip()
    if not hasattr(pipeline, "SetPickCore"):
        pytest.skip(
            "TerritoryPlacementPipeline has no SetPickCore injection seam -- "
            "cannot inject the VesselSurfacePick (Stage-1 i3/i4 not landed)."
        )
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))
    if not hasattr(pipeline, "SetCarrier"):
        pytest.skip(
            "TerritoryPlacementPipeline has no SetCarrier seam -- cannot bind "
            "the vtkMRMLCustomTerritoriesNode carrier + active territory "
            "(Stage-1 i3/i4 not landed)."
        )
    pipeline.SetCarrier(carrier, TERRITORY_A)


# --------------------------------------------------------------------------- #
# i3 — placement: click adds exactly one; bare move is declined
# --------------------------------------------------------------------------- #


def test_click_adds_exactly_one_surface_snapped_point(monkeypatch):
    """i3: a click adds EXACTLY ONE point, snapped ON the mesh.

    The stub renderer unprojects to a +z ray through a unit sphere at the
    origin; the injected ``VesselSurfacePick`` snaps the click to the north
    pole ``(0, 0, 1)``.  The click adds exactly one point to the carrier's
    active territory, on the mesh (distance ~= 0).  ADR-0037 §Decision 2 +
    §Conformance [test] "a click ... adds exactly one surface-snapped
    point".
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch)
    # ADR-0037 §Decision 3 arming model: add-on-click requires an armed
    # pipeline (Stage-2 addition).  Arm into the wired territory before the
    # click; the invariant pinned here (one surface-snapped point) is
    # unchanged.
    if hasattr(pipeline, "Arm"):
        pipeline.Arm()

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    assert pipeline.CanProcessInteractionEvent(click)[0] is True, (
        "a click over the surface must be CLAIMED (add-on-click)."
    )
    assert pipeline.ProcessInteractionEvent(click) is True

    after = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    assert after == before + 1, (
        f"a click must add EXACTLY ONE point (before={before}, after={after})."
    )
    placed = carrier.GetNthAnnotationPoint(TERRITORY_A, after - 1)
    sphere = _unit_sphere()
    assert _distance_to_surface(sphere, (placed[0], placed[1], placed[2])) == pytest.approx(
        0.0, abs=1e-3
    ), "the placed point must be surface-snapped (on the mesh)."


def test_bare_move_is_declined_and_adds_nothing(monkeypatch):
    """i3: a bare move is DECLINED and adds NO point (ADR-0033).

    ``CanProcessInteractionEvent`` on a bare mouse move returns
    ``(False, +inf)`` so LayerDM leaves the move to the camera; its only
    side effect is raising the adhering highlight — never a carrier
    mutation.  ADR-0037 §Decision 2 "a bare hover is declined (camera
    untouched)" + §Conformance [test].
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch)

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    can, distance2 = pipeline.CanProcessInteractionEvent(move)

    assert can is False, "a bare move must be DECLINED (camera untouched, ADR-0033)."
    assert distance2 == sys.float_info.max
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a bare move must add NO annotation point."
    )


# --------------------------------------------------------------------------- #
# i4 — edit (drag) + delete + no drift on unrelated Modified
# --------------------------------------------------------------------------- #


def test_drag_edits_exactly_the_nearest_point(monkeypatch):
    """i4: a drag mutates EXACTLY ONE point — the nearest to the grab.

    With two points placed, a press grabs the nearest one and the drag
    relocates only THAT point; the sibling is unchanged and the count is
    unchanged (ADR-0037 §Decision 2 "a drag edits the nearest point").
    The relocation target is injected so the test stays GL-free on the
    edit math; the nearest-selection is what is pinned.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch)

    # Two placed points; index 1 is the one the grab resolves to.
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, 1.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    if not hasattr(pipeline, "_nearest_point_in_display"):
        pytest.skip(
            "TerritoryPlacementPipeline has no _nearest_point_in_display seam "
            "-- cannot pin nearest-selection (Stage-1 i4 not landed)."
        )
    if not hasattr(pipeline, "_event_world_on_surface"):
        pytest.skip(
            "TerritoryPlacementPipeline has no _event_world_on_surface seam "
            "-- cannot inject the drag target (Stage-1 i4 not landed)."
        )
    # Grab resolves to (territory A, point index 1) at a real squared distance;
    # the drag relocates it to a fixed surface point.
    monkeypatch.setattr(
        pipeline, "_nearest_point_in_display", lambda r, e: (TERRITORY_A, 1, 9.0)
    )
    monkeypatch.setattr(
        pipeline, "_event_world_on_surface", lambda r, e: (0.0, 1.0, 0.0)
    )

    before0 = tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0))
    before_count = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)

    press = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    can, d2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True and d2 == pytest.approx(9.0), (
        "a press near a point must be claimed with the REAL squared display "
        "distance (LayerDM arbitration)."
    )
    assert pipeline.ProcessInteractionEvent(press) is True
    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    assert pipeline.ProcessInteractionEvent(move) is True

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before_count, (
        "a drag edits in place -- it must NOT add or remove points."
    )
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 1)) == pytest.approx(
        (0.0, 1.0, 0.0), abs=1e-6
    ), "the drag must relocate the GRABBED (nearest) point."
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0)) == pytest.approx(
        before0, abs=1e-9
    ), "the drag must NOT move the un-grabbed sibling point."


def test_delete_removes_exactly_one_point(monkeypatch):
    """i4: a delete removes EXACTLY ONE point (the targeted one).

    ADR-0037 §Decision 2 "delete removes one point" (delete-from-table is
    the whole lifecycle end).  With three points, deleting the middle one
    leaves two, and the surviving order is the remaining points minus the
    deleted index.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch)

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)

    if not hasattr(pipeline, "DeleteAnnotationPoint"):
        pytest.skip(
            "TerritoryPlacementPipeline has no DeleteAnnotationPoint seam -- "
            "delete-from-table (Stage-1 i4) has not landed.  The skip lifts "
            "at the implementation commit (ADR-0027)."
        )

    assert pipeline.DeleteAnnotationPoint(TERRITORY_A, 1) is True

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1, (
        "delete must remove EXACTLY ONE point."
    )
    # The survivors are points 0 and 2 in their original order.
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0)) == pytest.approx(
        pts[0], abs=1e-6
    )
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 1)) == pytest.approx(
        pts[2], abs=1e-6
    ), "after deleting the middle point, the tail must shift up in order."


def test_unrelated_modified_causes_no_point_drift(monkeypatch):
    """i4: an unrelated ``Modified`` does not add / move / drop any point.

    A carrier ``Modified`` raised for a reason OTHER than a placement
    gesture (a table repaint, a colour change, another view) must leave
    the annotation-point set byte-identical — no drift.  Pins the
    reconcile is idempotent on non-geometry Modifieds.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    _wire_pipeline_or_skip(slicer, pipeline, carrier, monkeypatch)

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)

    if not hasattr(pipeline, "_on_node_modified"):
        pytest.skip(
            "TerritoryPlacementPipeline has no _on_node_modified reconcile "
            "hook -- cannot pin no-drift (Stage-1 i4 not landed)."
        )

    before_count = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    before = [tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i)) for i in range(before_count)]

    # A reconcile driven by an unrelated Modified.
    pipeline._on_node_modified(None, None)
    carrier.Modified()
    pipeline._on_node_modified(None, None)

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before_count, (
        "an unrelated Modified must NOT change the point count."
    )
    for i, expected in enumerate(before):
        assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i)) == pytest.approx(
            expected, abs=1e-9
        ), f"point {i} must not drift on an unrelated Modified."


# --------------------------------------------------------------------------- #
# i5 — shared display-node routing (Stage 2 / the 3D-fix contract)
# --------------------------------------------------------------------------- #


def test_display_node_routes_arm_active_and_click(monkeypatch):
    """i5: with a display node present, arm/active read back + a click routes there.

    The 3D-fix contract: the widget/table cannot reach the manager-created
    Pipeline instance, so arm state / active territory / carrier ride on the
    SHARED highlight display node.  A Pipeline whose ``SetDisplayNode`` bound
    that node must (a) publish ``Arm()`` / ``SetActiveTerritory()`` onto it
    and read them back via ``IsArmed()`` / ``GetActiveTerritory()``, and (b)
    route a click into the display-node-resolved carrier + ACTIVE territory —
    NOT an instance-field carrier.  This is the integration the
    detached-instance bug slipped through.
    """
    slicer = _slicer_or_skip()
    TerritoryPlacementPipeline = _import_pipeline_or_skip()
    pipeline = TerritoryPlacementPipeline()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()

    VesselSurfacePick = _import_pick_or_skip()
    if not hasattr(pipeline, "SetPickCore") or not hasattr(pipeline, "SetDisplayNode"):
        pytest.skip(
            "TerritoryPlacementPipeline lacks SetPickCore / SetDisplayNode -- "
            "cannot bind the shared display-node state (Stage-2 not landed)."
        )
    for method in ("SetActiveTerritory", "GetActiveTerritory", "Arm", "IsArmed"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"TerritoryPlacementPipeline has no {method} -- the shared "
                "display-node arm seam has not landed (ADR-0027)."
            )
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))

    # Bind the carrier onto the SHARED display node (NOT via SetCarrier), then
    # hand the display node to the pipeline: everything resolves from the node.
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)

    # (a) arm + active publish onto the node and read back through the seam.
    pipeline.SetActiveTerritory(TERRITORY_B)
    pipeline.Arm()
    assert pipeline.IsArmed() is True
    assert pipeline.GetActiveTerritory() == TERRITORY_B
    assert state.is_armed(displayNode) is True
    assert state.get_active_territory(displayNode) == TERRITORY_B

    # (b) a click routes into the display-node-resolved carrier + ACTIVE
    # territory (B), not the other one.
    before_b = carrier.GetNumberOfAnnotationPoints(TERRITORY_B)
    before_a = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    assert pipeline.ProcessInteractionEvent(click) is True

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_B) == before_b + 1, (
        "an armed click must append ONE seed to the display-node ACTIVE territory."
    )
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before_a, (
        "the click must not leak into another territory."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
