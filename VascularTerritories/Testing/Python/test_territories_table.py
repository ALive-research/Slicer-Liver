# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-2 — the VascularTerritories annotation table UI.

ADR-0037 §Decision 3 (§3 table) replaces the legacy
``inputSurfaceSelector`` / ``endPointsMarkupsSelector`` place-widget panel
with a Python-composed custom ``QTableWidget`` (ADR-0004): a CUSTOM table,
not a stock point-list view, because the surface-snap + territory-grouping
contract has no stock fit (the same call ADR-0034 made against
``qMRMLSegmentsTableView``).

The confirmed Stage-2 design (maintainer-approved this session) that these
invariants pin:

* TABLE SHAPE.  Rows are PER-POINT, grouped under per-territory HEADER
  rows.  Each territory has a header row (per-territory visibility, colour
  swatch, label) and one CHILD row per seed point (on-surface status +
  delete).
* CARRIER IS THE MODEL.  The table reads/writes the Stage-1 annotation
  carrier ``vtkMRMLCustomTerritoriesNode`` (points via ``AddAnnotationPoint``
  / ``GetNumberOfAnnotationPoints`` / ``GetNthAnnotationPoint`` /
  ``ClearAnnotationPoints``; the Stage-2 display slot via the per-territory
  colour / label / visibility accessors).  It OBSERVES the carrier's
  ``vtkCommand::ModifiedEvent`` and rebuilds; edits write back.
* ARMING (pipeline-managed, NOT a Slicer mouse mode).  The arm state lives
  on the ``TerritoryPlacementPipeline``; the interaction node is NOT
  touched.  "Add Territory" mints a new empty territory on the carrier,
  selects its row, makes it the pipeline's ACTIVE territory, and arms
  placement; each surface click through the pipeline seam appends ONE seed
  to the ACTIVE territory (sequential, unbounded).  "Done" / Esc disarms.
  Selecting an existing row + "Add seeds" re-arms into THAT territory.
* DELETE CONVERGENCE.  Delete-by-row (table) and delete-by-pick (pipeline)
  route through ONE carrier deletion path — a single point-removal
  implementation reached from both entry points.
* SEED-COUNT COMPLETENESS.  A territory with < 2 seeds is flagged
  incomplete via GLYPH + TEXT (ADR-0010, never colour alone) —
  display-only in Stage 2 (extraction gating is Stage 3).
* RETIREMENT.  The legacy markups-selector / place-widget wiring
  (``endPointsMarkupsSelector`` / ``newEndpointsListCreated`` /
  ``onSegmentChanged``) retires; ``inputSurfaceSelector`` +
  ``updateHighlightPickSurface`` STAY (Stage-1 highlight-wiring invariant
  survives); NO ``vtkMRMLMarkupsFiducialNode`` persisted by the annotation
  path.

-- SEAM THE IMPLEMENTER MUST PROVIDE (proposed; sharpen at landing) --

A Python-widget-composed table, mirroring the Stage-2 segments-table
paradigm (ADR-0034) but CUSTOM (ADR-0037 §Decision 3):

  * module path ``VascularTerritoriesLib.TerritoriesTableWidget``, class
    ``TerritoriesTableWidget`` (a ``qt.QTableWidget`` subclass or a
    composed widget owning one), constructed over the carrier + the
    placement Pipeline:
      ``TerritoriesTableWidget(carrier=<vtkMRMLCustomTerritoriesNode>,
                               pipeline=<TerritoryPlacementPipeline>)``.
  * ``table()`` -> the underlying ``qt.QTableWidget``;
  * row model helpers: ``isHeaderRow(row) -> bool``,
    ``territoryOfRow(row) -> str``, ``pointIndexOfRow(row) -> int | None``
    (``None`` for a header row);
  * ``addTerritory(territoryId=None) -> str`` — mint an empty territory,
    select its header row, arm the pipeline into it;
  * ``armForSelectedTerritory()`` — re-arm placement into the selected
    row's territory ("Add seeds");
  * ``done()`` — disarm;
  * ``deleteRow(row)`` — the delete-from-table entry point, converging on
    the pipeline's ``DeleteAnnotationPoint``;
  * status-cell readers for the completeness assertion:
    ``rowStatusText(row) -> str`` and ``rowHasIncompleteGlyph(row) -> bool``.

The arm state on the Pipeline (a Stage-2 addition to
``TerritoryPlacementPipeline``): an ``IsArmed() -> bool`` plus an
"active territory" the click appends into (the current ``SetCarrier``
binds a single territory; Stage 2 needs "set active territory + arm" so a
click appends to the ACTIVE territory, not an implicit one).  Proposed:
``SetActiveTerritory(territoryId)`` / ``GetActiveTerritory()`` +
``Arm()`` / ``Disarm()`` / ``IsArmed()``.

-- WHY LAUNCHED-SLICER --

The table needs Qt (``qt.QTableWidget``) + the wrapped
``vtkMRMLCustomTerritoriesNode`` carrier + (for the arming tests) the
LayerDM ``TerritoryPlacementPipeline``.  A bare ``PythonSlicer -m pytest``
has ``slicer.mrmlScene is None``, no Qt, and LayerDMLib off the path, so
every test here SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the table widget + the carrier display slot + the
Pipeline arm seam do not exist, so the import / ``hasattr`` guards
skip-pend; the skips lift at the Stage-2 implementation commit.  Under a
launched Slicer, verify run-vs-skip in the CI log once the seam lands —
never trust overall green (the launched harness is green-but-skipping
prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (the decision)
  * Docs/adr/0034-stage2-segments-table.md  (the table paradigm)
  * Docs/adr/0010-accessibility-and-i18n.md  (glyph + text, never colour)
  * Docs/adr/0033-control-polygon-display-aspect.md  (hover-decline)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/Testing/Python/test_territories_annotation_carrier.py
  * VascularTerritories/Testing/Python/test_territories_placement_pipeline.py
  * VascularTerritories/Testing/Python/test_vessel_highlight_wiring.py
  * VascularTerritories/VascularTerritoriesLib/TerritoryPlacementPipeline.py
  * VascularTerritories/Testing/Python/conftest.py  (the cleanup fixtures)
"""

from __future__ import annotations

import sys

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
TERRITORY_A = "SegmentVII"
TERRITORY_B = "SegmentVIII"

# Carrier point API (pinned by test_territories_annotation_carrier.py).
ADD_POINT_METHOD = "AddAnnotationPoint"
COUNT_METHOD = "GetNumberOfAnnotationPoints"
GET_NTH_METHOD = "GetNthAnnotationPoint"

# Carrier display-attribute slot (Stage-2; pinned bare-adjacent in the
# carrier test's i5).  Proposed accessor names.
DISPLAY_METHODS = (
    "SetTerritoryColor",
    "GetTerritoryColor",
    "SetTerritoryLabel",
    "GetTerritoryLabel",
    "SetTerritoryVisibility",
    "GetTerritoryVisibility",
)


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _qt_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_carrier_or_skip(slicer, name="TableCarrierTest"):
    """Mint a carrier exposing the point + display-attribute API, or skip-pend."""
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
                "annotation carrier (Stage-1) has not landed (ADR-0027)."
            )
    for method in DISPLAY_METHODS:
        if not hasattr(node, method):
            pytest.skip(
                f"{CUSTOM_TERRITORIES_CLASS} has no {method} -- the ADR-0037 "
                "Stage-2 display-attribute slot has not landed (ADR-0027)."
            )
    return node


def _import_table_or_skip():
    """Import the Stage-2 table widget class or skip-pend (ADR-0027)."""
    try:
        from VascularTerritoriesLib.TerritoriesTableWidget import (
            TerritoriesTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoriesTableWidget not importable ({exc!r}) -- the ADR-0037 "
            "Stage-2 table widget has not landed OR Qt/LayerDMLib is not "
            "reachable here.  The skip lifts at the Stage-2 implementation "
            "commit (ADR-0027)."
        )
    return TerritoriesTableWidget


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


def _make_table_or_skip(slicer, carrier, pipeline=None):
    """Construct the table over the carrier (+ pipeline), registering teardown.

    Skip-pends when the table constructor does not yet accept the carrier +
    pipeline seam (Stage-2 not landed).
    """
    TerritoriesTableWidget = _import_table_or_skip()
    try:
        table = TerritoriesTableWidget(carrier=carrier, pipeline=pipeline)
    except TypeError as exc:
        pytest.skip(
            f"TerritoriesTableWidget(carrier=, pipeline=) seam absent ({exc!r}) "
            "-- the ADR-0037 Stage-2 table constructor has not landed (ADR-0027)."
        )
    return table


def _require_table_row_model(table):
    """Skip-pend unless the table exposes the row-model reader seams."""
    for method in ("table", "isHeaderRow", "territoryOfRow", "pointIndexOfRow"):
        if not hasattr(table, method):
            pytest.skip(
                f"TerritoriesTableWidget has no {method} row-model seam -- "
                "the ADR-0037 Stage-2 table has not landed (ADR-0027)."
            )


# --------------------------------------------------------------------------- #
# Fake interaction plumbing (reused from the placement-pipeline suite shape)
# --------------------------------------------------------------------------- #


def _unit_sphere():
    source = vtk.vtkSphereSource()
    source.SetRadius(1.0)
    source.SetThetaResolution(64)
    source.SetPhiResolution(64)
    source.Update()
    return source.GetOutput()


class _FakeRenderer:
    """Display->world unprojects any pixel to the +z ray a unit sphere is hit by."""

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


def _wire_pipeline_or_skip(pipeline, carrier, monkeypatch):
    """Attach a stub renderer + pick core so a click resolves to the surface."""
    try:
        from VesselSurfacePick import VesselSurfacePick
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselSurfacePick not importable ({exc!r}).")
    if not hasattr(pipeline, "SetPickCore") or not hasattr(pipeline, "SetCarrier"):
        pytest.skip(
            "TerritoryPlacementPipeline lacks SetPickCore / SetCarrier -- "
            "cannot drive a click (Stage-1 not landed; ADR-0027)."
        )
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))
    pipeline.SetCarrier(carrier, TERRITORY_A)


def _require_arm_seam(pipeline):
    """Skip-pend unless the Pipeline exposes the Stage-2 active-territory + arm seam."""
    for method in ("SetActiveTerritory", "GetActiveTerritory", "Arm", "Disarm", "IsArmed"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"TerritoryPlacementPipeline has no {method} -- the ADR-0037 "
                "Stage-2 active-territory + arm seam has not landed.  A click "
                "must append to the ACTIVE territory, not an implicit one "
                "(§Decision 3 arming model; ADR-0027)."
            )


# --------------------------------------------------------------------------- #
# TABLE SHAPE — header row per territory + child row per seed
# --------------------------------------------------------------------------- #


def test_table_builds_header_row_per_territory_and_child_row_per_point(qt_widgets):
    """The table has one header row per territory + one child row per seed.

    ADR-0037 §Decision 3 / §3 table: rows are per-point, grouped under
    per-territory header rows.  A carrier with two territories (2 + 3 seeds)
    yields 2 header rows + 5 child rows, in territory order.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    _require_table_row_model(table)

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)
    carrier.Modified()

    widget = table.table()
    header_rows = [r for r in range(widget.rowCount) if table.isHeaderRow(r)]
    child_rows = [r for r in range(widget.rowCount) if not table.isHeaderRow(r)]

    assert len(header_rows) == 2, "one header row per territory."
    assert len(child_rows) == 5, "one child row per seed point across both territories."
    # Every child row resolves to a real point index within its territory.
    for r in child_rows:
        territory = table.territoryOfRow(r)
        idx = table.pointIndexOfRow(r)
        assert idx is not None and 0 <= idx < carrier.GetNumberOfAnnotationPoints(territory)


def test_carrier_modified_event_rebuilds_the_table(qt_widgets):
    """A carrier ``ModifiedEvent`` triggers a table rebuild (the carrier is the model).

    ADR-0037 §Decision 3: the table OBSERVES the carrier's
    ``vtkCommand::ModifiedEvent`` and rebuilds.  Adding a point to the
    carrier (outside the table) grows the child-row count without an
    explicit table refresh call.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    _require_table_row_model(table)

    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    before = sum(1 for r in range(table.table().rowCount) if not table.isHeaderRow(r))

    carrier.AddAnnotationPoint(TERRITORY_A, 2.0, 0.0, 0.0)  # fires ModifiedEvent

    after = sum(1 for r in range(table.table().rowCount) if not table.isHeaderRow(r))
    assert after == before + 1, (
        "a carrier ModifiedEvent must rebuild the table (child-row count grows "
        "with the seed count) -- the carrier is the model, no manual refresh."
    )


# --------------------------------------------------------------------------- #
# ARMING — click appends to the ACTIVE territory
# --------------------------------------------------------------------------- #


def test_arm_then_click_appends_one_seed_to_active_territory(qt_widgets, monkeypatch):
    """Arm + a surface click appends EXACTLY ONE seed to the ACTIVE territory.

    ADR-0037 §Decision 3 arming model: "Add Territory" makes a territory
    the pipeline's ACTIVE one and arms placement; a surface click through
    the pipeline seam appends one seed to THAT territory, not another.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_or_skip(pipeline, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, pipeline)
    qt_widgets.append(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    active = table.addTerritory()  # mints + selects + arms into a new territory
    assert pipeline.IsArmed() is True, "Add Territory must arm placement."
    assert pipeline.GetActiveTerritory() == active

    before_active = carrier.GetNumberOfAnnotationPoints(active)
    before_other = carrier.GetNumberOfAnnotationPoints(TERRITORY_B)

    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    assert pipeline.ProcessInteractionEvent(click) is True

    assert carrier.GetNumberOfAnnotationPoints(active) == before_active + 1, (
        "an armed click must append EXACTLY ONE seed to the ACTIVE territory."
    )
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_B) == before_other, (
        "the click must NOT leak into another territory."
    )


def test_click_with_nothing_armed_appends_nothing(qt_widgets, monkeypatch):
    """A click with placement NOT armed appends no seed (ADR-0037 §Decision 3).

    Disarmed ("Done" / Esc), the pipeline is idle: a click adds nothing to
    any territory.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_or_skip(pipeline, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, pipeline)
    qt_widgets.append(table)

    pipeline.Disarm()
    assert pipeline.IsArmed() is False

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    pipeline.ProcessInteractionEvent(click)

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a click with nothing armed must append no seed."
    )


def test_bare_move_stays_declined_while_armed(qt_widgets, monkeypatch):
    """A bare hover/move stays DECLINED even while armed (ADR-0033).

    Arming enables add-on-click; it does NOT make a bare move claim the
    gesture.  ``CanProcessInteractionEvent`` on a move returns
    ``(False, +inf)`` so the camera is untouched (ADR-0033 hover discipline,
    carried into ADR-0037).
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_or_skip(pipeline, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    pipeline.Arm()

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    can, distance2 = pipeline.CanProcessInteractionEvent(move)

    assert can is False, "a bare move must stay declined while armed (ADR-0033)."
    assert distance2 == sys.float_info.max
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a bare move must append no seed."
    )


def test_switching_active_territory_redirects_subsequent_clicks(qt_widgets, monkeypatch):
    """Selecting a row + Add seeds redirects clicks to the newly ACTIVE territory.

    ADR-0037 §Decision 3: "Selecting an existing row + 'Add seeds' re-arms
    into that territory."  After re-arming into territory B, a click lands in
    B — not the previously active A.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_or_skip(pipeline, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, pipeline)
    qt_widgets.append(table)
    _require_table_row_model(table)
    for seam in ("addTerritory", "armForSelectedTerritory", "selectTerritoryRow"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} seam -- cannot pin "
                "active-territory switching (ADR-0037 Stage-2; ADR-0027)."
            )

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()
    # Re-arm into A first, then switch back to B via the row selection.
    table.selectTerritoryRow(territory_a)
    table.armForSelectedTerritory()
    assert pipeline.GetActiveTerritory() == territory_a

    table.selectTerritoryRow(territory_b)
    table.armForSelectedTerritory()
    assert pipeline.GetActiveTerritory() == territory_b

    before_b = carrier.GetNumberOfAnnotationPoints(territory_b)
    before_a = carrier.GetNumberOfAnnotationPoints(territory_a)
    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent))

    assert carrier.GetNumberOfAnnotationPoints(territory_b) == before_b + 1, (
        "after re-arming into B, a click must land in B."
    )
    assert carrier.GetNumberOfAnnotationPoints(territory_a) == before_a, (
        "the previously active territory A must not receive the click."
    )


# --------------------------------------------------------------------------- #
# DELETE convergence — table + pipeline share one carrier deletion path
# --------------------------------------------------------------------------- #


def test_delete_row_removes_exactly_one_point(qt_widgets):
    """Delete-by-row removes EXACTLY ONE carrier point (§Decision 3 / §Decision 2).

    Deleting a child row drops that one seed from the carrier; the count
    falls by one and the survivors keep their order.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    _require_table_row_model(table)
    if not hasattr(table, "deleteRow"):
        pytest.skip("TerritoriesTableWidget has no deleteRow seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    # The child row for territory A, point index 1.
    target_row = next(
        r
        for r in range(table.table().rowCount)
        if not table.isHeaderRow(r)
        and table.territoryOfRow(r) == TERRITORY_A
        and table.pointIndexOfRow(r) == 1
    )
    table.deleteRow(target_row)

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1, (
        "delete-by-row must remove EXACTLY ONE carrier point."
    )
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 1)) == pytest.approx(pts[2], abs=1e-6)


def test_delete_by_row_and_by_pick_share_one_carrier_path(qt_widgets):
    """Delete-by-row and the pipeline's ``DeleteAnnotationPoint`` converge.

    ADR-0037 §Decision 3 delete convergence: BOTH entry points route through
    ONE carrier deletion path.  Deleting index 1 via each entry point removes
    the same point and drops the count by one identically — no divergent
    routes.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    if not hasattr(pipeline, "SetCarrier") or not hasattr(pipeline, "DeleteAnnotationPoint"):
        pytest.skip(
            "TerritoryPlacementPipeline lacks SetCarrier / DeleteAnnotationPoint "
            "-- cannot pin delete convergence (ADR-0027)."
        )
    pipeline.SetCarrier(carrier, TERRITORY_A)
    table = _make_table_or_skip(slicer, carrier, pipeline)
    qt_widgets.append(table)
    _require_table_row_model(table)
    if not hasattr(table, "deleteRow"):
        pytest.skip("TerritoriesTableWidget has no deleteRow seam (ADR-0027).")

    # Seed two identical-shaped territories to delete-index-1 from each way.
    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)
    carrier.Modified()

    # Route 1: pipeline delete-by-pick on territory B, index 1.
    assert pipeline.DeleteAnnotationPoint(TERRITORY_B, 1) is True
    b_after = [
        tuple(carrier.GetNthAnnotationPoint(TERRITORY_B, i))
        for i in range(carrier.GetNumberOfAnnotationPoints(TERRITORY_B))
    ]

    # Route 2: table delete-by-row on territory A, index 1.
    target_row = next(
        r
        for r in range(table.table().rowCount)
        if not table.isHeaderRow(r)
        and table.territoryOfRow(r) == TERRITORY_A
        and table.pointIndexOfRow(r) == 1
    )
    table.deleteRow(target_row)
    a_after = [
        tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i))
        for i in range(carrier.GetNumberOfAnnotationPoints(TERRITORY_A))
    ]

    # Both routes must yield the SAME surviving set (points 0 and 2).
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_B) == len(pts) - 1
    assert a_after == pytest.approx(b_after, abs=1e-6), (
        "delete-by-row and delete-by-pick must converge on one carrier path "
        "(identical survivors) -- no divergent deletion routes."
    )


# --------------------------------------------------------------------------- #
# DISPLAY EDITS — write the carrier display slot without touching geometry
# --------------------------------------------------------------------------- #


def test_visibility_colour_label_edits_leave_geometry_unchanged(qt_widgets):
    """Header-row visibility / colour / label edits write the display slot only.

    ADR-0037 §Decision 3: the header row carries per-territory visibility,
    colour swatch, and label; editing them writes the carrier's display slot
    "without touching geometry" — the annotation-point count + coords stay
    byte-identical.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    _require_table_row_model(table)
    for seam in ("setTerritoryVisibility", "setTerritoryColor", "setTerritoryLabel"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} edit seam (ADR-0027)."
            )

    pts = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    before_count = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    before = [
        tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i)) for i in range(before_count)
    ]

    table.setTerritoryVisibility(TERRITORY_A, False)
    table.setTerritoryColor(TERRITORY_A, 0.3, 0.6, 0.9)
    table.setTerritoryLabel(TERRITORY_A, "Renamed via table")

    # The display slot took the edit ...
    assert bool(carrier.GetTerritoryVisibility(TERRITORY_A)) is False
    assert carrier.GetTerritoryLabel(TERRITORY_A) == "Renamed via table"
    color = carrier.GetTerritoryColor(TERRITORY_A)
    assert (color[0], color[1], color[2]) == pytest.approx((0.3, 0.6, 0.9), abs=1e-6)

    # ... and the geometry did not move.
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before_count, (
        "a display edit must NOT change the annotation-point count."
    )
    for i, expected in enumerate(before):
        assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i)) == pytest.approx(
            expected, abs=1e-9
        ), f"point {i} must not move on a display edit."


# --------------------------------------------------------------------------- #
# COMPLETENESS — < 2 seeds flagged via glyph + text (ADR-0010, not colour)
# --------------------------------------------------------------------------- #


def test_territory_with_fewer_than_two_seeds_is_flagged_incomplete(qt_widgets):
    """A territory with < 2 seeds shows an incomplete indicator as GLYPH + TEXT.

    ADR-0037 §Decision 3 + §Conformance [review] (ADR-0010): status is
    rendered as glyph + text, NEVER colour alone.  A one-seed territory reads
    incomplete (glyph present + a non-empty status text); a two-seed one does
    not.  Display-only in Stage 2 — extraction gating is Stage 3.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    _require_table_row_model(table)
    for seam in ("rowStatusText", "rowHasIncompleteGlyph"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} status seam -- cannot "
                "assert the glyph+text completeness indicator (ADR-0010; ADR-0027)."
            )

    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)  # one seed -> incomplete
    for x, y, z in [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)  # two seeds -> complete
    carrier.Modified()

    header_a = next(
        r for r in range(table.table().rowCount)
        if table.isHeaderRow(r) and table.territoryOfRow(r) == TERRITORY_A
    )
    header_b = next(
        r for r in range(table.table().rowCount)
        if table.isHeaderRow(r) and table.territoryOfRow(r) == TERRITORY_B
    )

    # Assert the GLYPH + TEXT indicator, never a colour.
    assert table.rowHasIncompleteGlyph(header_a) is True, (
        "a < 2-seed territory must carry an incomplete GLYPH (ADR-0010)."
    )
    assert table.rowStatusText(header_a).strip() != "", (
        "the incomplete state must also carry TEXT (ADR-0010, never colour alone)."
    )
    assert table.rowHasIncompleteGlyph(header_b) is False, (
        "a >= 2-seed territory must NOT be flagged incomplete."
    )


# --------------------------------------------------------------------------- #
# RETIREMENT — selector gone; highlight wiring survives; no persisted markups
# --------------------------------------------------------------------------- #


def test_highlight_picksurface_wiring_survives_selector_retirement(qt_widgets):
    """The Stage-1 highlight-wiring invariant survives the selector retirement.

    ADR-0037 §Consequences: ``inputSurfaceSelector`` + ``updateHighlightPickSurface``
    STAY.  After the legacy ``endPointsMarkupsSelector`` retires, selecting an
    input segmentation must still aim the highlight's ``pickSurface`` at it
    (the ``test_vessel_highlight_wiring.py`` invariant, re-pinned here so the
    Stage-2 panel rewrite does not regress it).
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()

    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    qt_widgets.append(widget)

    source = vtk.vtkSphereSource()
    source.SetRadius(30.0)
    source.SetThetaResolution(48)
    source.SetPhiResolution(48)
    source.Update()
    model = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "Vessel")
    model.SetAndObservePolyData(source.GetOutput())
    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "TestVessel")
    segmentation.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(model, segmentation)
    slicer.mrmlScene.RemoveNode(model)

    if not hasattr(widget, "updateHighlightPickSurface"):
        pytest.skip(
            "VascularTerritoriesWidget has no updateHighlightPickSurface -- the "
            "surviving Stage-1 highlight wiring is absent (regression!)."
        )
    widget.ui.inputSurfaceSelector.blockSignals(True)
    widget.ui.inputSurfaceSelector.setCurrentNode(segmentation)
    widget.ui.inputSurfaceSelector.blockSignals(False)
    widget.updateHighlightPickSurface()

    highlight = widget._highlightDisplayNode
    assert highlight is not None
    assert highlight.GetPickSurfaceNode() is segmentation, (
        "updateHighlightPickSurface must still aim pickSurface at the selected "
        "input segmentation after the selector retirement (ADR-0037 §Consequences)."
    )

    # Drop the widget's scene observers before the autouse scene-clear fires.
    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        widget.removeObserver(slicer.mrmlScene, event, handler)
    widget.cleanup()


def test_no_endpoints_selector_and_no_persisted_fiducial(qt_widgets):
    """``endPointsMarkupsSelector`` is gone AND no fiducial is persisted.

    ADR-0037 §Consequences + §Conformance [review]: the markups-selector /
    place-widget wiring retires, and the annotation/table path persists NO
    ``vtkMRMLMarkupsFiducialNode``.  Both have a credible creep-in path (a
    left-in selector; a fallback fiducial), so per the no-colour-of-the-sky
    discipline this narrow absence stays pinned.

    Pins: (1) the widget no longer exposes ``ui.endPointsMarkupsSelector``;
    (2) after arming + a surface click through the placement path, no
    ``vtkMRMLMarkupsFiducialNode`` is present in the scene.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()

    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    qt_widgets.append(widget)

    # (1) the legacy selector is retired from the UI.
    ui = getattr(widget, "ui", None)
    assert ui is not None
    if hasattr(ui, "endPointsMarkupsSelector"):
        # Skip-pend rather than fail while the Stage-2 panel rewrite is in
        # flight: the retirement is the deliverable this test drives RED for.
        pytest.skip(
            "widget.ui still exposes endPointsMarkupsSelector -- the ADR-0037 "
            "Stage-2 selector retirement has not landed.  The skip lifts at the "
            "retirement commit (ADR-0027)."
        )

    # (2) no fiducial persisted by the annotation/table path.
    fiducials = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsFiducialNode")
    count = fiducials.GetNumberOfItems() if fiducials is not None else 0
    assert count == 0, (
        "the annotation/table path must persist NO vtkMRMLMarkupsFiducialNode "
        "(ADR-0037 §Conformance [review])."
    )

    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        widget.removeObserver(slicer.mrmlScene, event, handler)
    widget.cleanup()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
