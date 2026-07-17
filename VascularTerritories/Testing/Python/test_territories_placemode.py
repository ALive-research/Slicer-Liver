# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 4 — per-territory Place mode + module-active gate + table-UX polish.

ADR-0037 §Decision 2 (placement/edit via the Pipeline seam) + §Decision 3
(the table UI) — sharpened by the slice-4 amendment recording the place-mode
UX.  Slice 4 makes placement an EXPLICIT, per-territory, exclusive arm toggle
driven from the table (not an implicit "Add Territory arms it and never
disarms"), gates arming on the module being active, and polishes the table to
the Slicer-idiomatic eye-icon visibility toggle.

The confirmed slice-4 design (maintainer-LOCKED this session), each pinned
below:

1.  PER-TERRITORY EXCLUSIVE PLACE TOGGLE.  Each territory HEADER row gets a
    checkable "Place" button in a NEW leftmost column.  The 5-column layout
    becomes ``Place | Visibility | Colour | Label | Status``.  Toggling ON
    arms placement into THAT territory (``set_active_territory`` +
    ``set_armed(True)`` + the highlight visible via ``TerritoryInteractionState``)
    and un-checks EVERY other row's toggle (EXCLUSIVE — one territory armed at
    a time); toggling OFF disarms.  The armed row's checked state is
    RE-DERIVED from the display node on each rebuild
    (``checked = is_armed(dn) and get_active_territory(dn) == territoryId``),
    NOT stored in a Python field, so it survives the carrier-Modified rebuild.

2.  MODULE-ACTIVE GATE.  ``exit()`` disarms placement (clears the display
    node's armed/active, hides the highlight, un-checks the active toggle) so
    no view claims an add-on-click when VascularTerritories is inactive.
    ``enter()`` auto-arms NOTHING.  Edits (grab/drag/delete of existing seeds)
    stay INDEPENDENT of arm state — intended, not gated.

3.  EYE-ICON VISIBILITY.  The visibility column is a Slicer-idiomatic
    eye-on / eye-off toggle (the segmentation convention): a checkable
    ``qt.QToolButton`` (NOT a ``QCheckBox``) toggling
    ``carrier.SetTerritoryVisibility``.

4.  HIERARCHICAL CHILD ROWS ON PLACEMENT.  Placing a seed into the armed
    territory (carrier ``AddAnnotationPoint`` / a click through the
    display-node-wired pipeline) adds EXACTLY ONE child row under that
    territory's header on the next rebuild, in the right columns of the
    5-column layout.

5.  PANEL BUTTONS.  ``Add Territory`` mints a new empty territory row AND arms
    it (its Place toggle reads checked after rebuild).  ``Add seeds`` + ``Done``
    panel buttons are RETIRED (absent).  The ``done()`` disarm logic survives
    as the shared body reused by ``exit()`` + toggle-OFF.

6.  COLOUR CELL guard.  The colour cell is a ``ctkColorPickerButton``
    (committed in slice 2/3); a light guard that the 5-column shift does not
    regress it (``colorChanged`` -> ``setTerritoryColor``).

-- BARE vs LAUNCHED --

The Place-toggle EXCLUSIVITY / re-derivation logic can be driven purely
through the table + a display node (no GL, no pipeline event dispatch), so
those RUN launched where the wrapped display node is reachable, and SKIP
cleanly bare (no Qt, no wrapped node).  The exit()-disarms-a-click and
click-adds-a-child-row invariants need a REAL pipeline bound to the SAME
display node the table writes (the detached-instance contract), so they are
LAUNCHED, pipeline wired via the display node.  Every test SKIPS cleanly bare
via the shared ``conftest`` guards.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the Place column / eye-icon toggle / exit-disarm /
child-row-on-placement do not exist, so the ``hasattr`` / column-shape guards
skip-pend; the skips lift at the slice-4 implementation commit.  Under a
launched Slicer, verify run-vs-skip in the CI log once the seam lands — never
trust overall green (the launched harness is green-but-skipping prone).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 2 / §3)
  * Docs/adr/0034-stage2-segments-table.md  (the table paradigm)
  * Docs/adr/0033-control-polygon-display-aspect.md  (hover-decline)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/Testing/Python/test_territories_table.py  (shared idiom)
  * VascularTerritories/Testing/Python/test_territories_widget_panel.py
  * VascularTerritories/VascularTerritoriesLib/TerritoryInteractionState.py
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
TERRITORY_A = "SegmentVII"
TERRITORY_B = "SegmentVIII"

# Carrier point API (pinned by test_territories_annotation_carrier.py).
ADD_POINT_METHOD = "AddAnnotationPoint"
COUNT_METHOD = "GetNumberOfAnnotationPoints"
GET_NTH_METHOD = "GetNthAnnotationPoint"

# Carrier display-attribute slot (Stage-2).
DISPLAY_METHODS = (
    "SetTerritoryColor",
    "GetTerritoryColor",
    "SetTerritoryLabel",
    "GetTerritoryLabel",
    "SetTerritoryVisibility",
    "GetTerritoryVisibility",
)

# ---------------------------------------------------------------------------
# THE 5-COLUMN CONTRACT the implementer MUST honour (slice 4).
#
# The Place column is inserted LEFTMOST; every downstream column shifts right
# by one.  The old 4-column layout was:
#     [Visibility=0 | Colour=1 | Label=2 | Status=3]  (_COLUMN_COUNT == 4)
# The slice-4 layout is:
#     [Place=0 | Visibility=1 | Colour=2 | Label=3 | Status=4]  (== 5)
#
# ``_appendChildRow`` must move with the shift: the child-row STATUS TEXT
# (formerly in _COL_LABEL == 2) moves to the new label column (3), and the
# child-row DELETE affordance (formerly in _COL_STATUS == 3) moves to the new
# status column (4).  The Place + Visibility + Colour cells stay blank on a
# child row.  These offsets are asserted below so the implementer's
# ``_COL_*`` constants + ``_appendHeaderRow`` / ``_appendChildRow`` matches.
# ---------------------------------------------------------------------------
EXPECTED_COLUMN_COUNT = 5
EXPECTED_COL_PLACE = 0
EXPECTED_COL_VISIBILITY = 1
EXPECTED_COL_COLOUR = 2
EXPECTED_COL_LABEL = 3
EXPECTED_COL_STATUS = 4


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py + the
# shared idiom in test_territories_table.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _qt_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_carrier_or_skip(slicer, name="PlaceModeCarrierTest"):
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


def _make_display_node_or_skip(slicer, name="PlaceModeHighlightTest"):
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


def _import_table_or_skip():
    """Import the Stage-2 table widget class or skip-pend (ADR-0027)."""
    try:
        from VascularTerritoriesLib.TerritoriesTableWidget import (
            TerritoriesTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoriesTableWidget not importable ({exc!r}) -- the ADR-0037 "
            "table widget has not landed OR Qt/LayerDMLib is not reachable here "
            "(ADR-0027)."
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


def _make_table_or_skip(slicer, carrier, displayNode):
    """Construct the table over the carrier + shared display node, or skip-pend."""
    TerritoriesTableWidget = _import_table_or_skip()
    try:
        table = TerritoriesTableWidget(carrier=carrier, displayNode=displayNode)
    except TypeError as exc:
        pytest.skip(
            f"TerritoriesTableWidget(carrier=, displayNode=) seam absent ({exc!r}) "
            "-- the ADR-0037 table constructor has not landed (ADR-0027)."
        )
    return table


def _require_table_row_model(table):
    """Skip-pend unless the table exposes the row-model reader seams."""
    for method in ("table", "isHeaderRow", "territoryOfRow", "pointIndexOfRow"):
        if not hasattr(table, method):
            pytest.skip(
                f"TerritoriesTableWidget has no {method} row-model seam -- "
                "the ADR-0037 table has not landed (ADR-0027)."
            )


def _require_five_column_layout_or_skip(table):
    """Skip-pend unless the table adopted the slice-4 5-column Place layout.

    The gate for every slice-4-shape assertion: while the pre-slice-4
    4-column layout survives, the table has no Place column, so the tests
    collect + SKIP-PENDING and RUN once the leftmost Place column lands
    (ADR-0037 §Decision 2 slice-4 amendment; ADR-0027).
    """
    widget = table.table()
    if widget.columnCount != EXPECTED_COLUMN_COUNT:
        pytest.skip(
            f"table has {widget.columnCount} columns, not the slice-4 "
            f"{EXPECTED_COLUMN_COUNT} (Place | Visibility | Colour | Label | "
            "Status) -- the per-territory Place column has not landed (ADR-0027)."
        )


def _place_cell_or_skip(table, row):
    """Return the header row's Place toggle widget, or skip-pend.

    Skips while the Place column is absent so the toggle-behaviour tests
    remain collectible pre-implementation.
    """
    widget = table.table()
    cell = widget.cellWidget(row, EXPECTED_COL_PLACE)
    if cell is None:
        pytest.skip(
            "no Place-toggle cell widget on the header row -- the ADR-0037 "
            "slice-4 per-territory Place toggle has not landed (ADR-0027)."
        )
    return cell


def _header_row_for(table, territoryId):
    """The header-row index for ``territoryId`` (raises if absent)."""
    return next(
        r
        for r in range(table.table().rowCount)
        if table.isHeaderRow(r) and table.territoryOfRow(r) == territoryId
    )


# --------------------------------------------------------------------------- #
# Fake interaction plumbing (reused from the placement-pipeline / table suites)
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


def _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch):
    """Bind a REAL pipeline to the SHARED display node so it reads live state.

    The detached-instance contract: the pipeline resolves its carrier / active
    territory / arm flag from the display node the TABLE writes to, NOT from a
    hand-armed detached instance.  A stub renderer + injected pick core keep
    the click GL-free.  (Same helper shape as test_territories_table.py.)
    """
    try:
        from VesselSurfacePick import VesselSurfacePick
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselSurfacePick not importable ({exc!r}).")
    if not hasattr(pipeline, "SetPickCore") or not hasattr(pipeline, "SetDisplayNode"):
        pytest.skip(
            "TerritoryPlacementPipeline lacks SetPickCore / SetDisplayNode -- "
            "cannot bind the shared display-node state (Stage-1 not landed; "
            "ADR-0027)."
        )
    state = _import_interaction_state_or_skip()
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))


# ===========================================================================
# Invariant 1 — the 5-column layout with the leftmost Place column.
# ===========================================================================


def test_table_has_five_columns_with_place_leftmost(qt_widgets):
    """The table adopts the slice-4 5-column layout, Place leftmost.

    ADR-0037 §Decision 2 (slice-4 amendment): the columns become
    ``Place | Visibility | Colour | Label | Status``.  The Place column is
    inserted LEFTMOST (index 0); the downstream columns shift right by one.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)

    # TODO(slice-4 implementer): the invariant body below is authoritative once
    # the Place column lands; it is unreachable while the guard skip-pends.
    assert table.table().columnCount == EXPECTED_COLUMN_COUNT


def test_child_row_status_and_delete_shift_into_the_five_column_offsets(qt_widgets):
    """Child rows render in the shifted 5-column offsets (the column contract).

    ADR-0037 §Decision 2 (slice-4): with the leftmost Place column inserted,
    ``_appendChildRow`` must move — the seed STATUS TEXT into the label column
    (index ``EXPECTED_COL_LABEL == 3``) and the DELETE affordance into the
    status column (index ``EXPECTED_COL_STATUS == 4``); Place / Visibility /
    Colour stay blank on a child row.  This pins the exact offsets the
    implementer's ``_appendChildRow`` must honour.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    widget = table.table()
    child_row = next(r for r in range(widget.rowCount) if not table.isHeaderRow(r))

    # Status TEXT lives in the label column (index 3) — a QTableWidgetItem.
    label_item = widget.item(child_row, EXPECTED_COL_LABEL)
    assert label_item is not None and label_item.text().strip() != "", (
        "child-row status text must live in the shifted label column "
        f"(index {EXPECTED_COL_LABEL})."
    )
    # Delete affordance lives in the status column (index 4) — a cell widget.
    delete_cell = widget.cellWidget(child_row, EXPECTED_COL_STATUS)
    assert delete_cell is not None, (
        "child-row delete affordance must live in the shifted status column "
        f"(index {EXPECTED_COL_STATUS})."
    )
    # Place / Visibility / Colour stay blank on a child row.
    for col in (EXPECTED_COL_PLACE, EXPECTED_COL_VISIBILITY, EXPECTED_COL_COLOUR):
        assert widget.cellWidget(child_row, col) is None and widget.item(child_row, col) is None, (
            f"child-row column {col} must be blank in the 5-column layout."
        )


# ===========================================================================
# Invariant 1 — per-territory EXCLUSIVE Place toggle.
# ===========================================================================


def test_place_toggle_arms_its_territory_on_the_display_node(qt_widgets):
    """Toggling a Place button ON arms THAT territory on the display node.

    ADR-0037 §Decision 2 (slice-4): the header's Place toggle writes
    ``set_active_territory`` + ``set_armed(True)`` onto the SHARED display node
    (``TerritoryInteractionState``) and makes the highlight visible.  [launched
    where the wrapped display node is reachable; the toggle logic is driven via
    the table + display node, no pipeline dispatch needed.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    header = _header_row_for(table, territory)
    place = _place_cell_or_skip(table, header)

    place.setChecked(True)

    assert state.is_armed(displayNode) is True, (
        "a checked Place toggle must arm placement via the shared display node."
    )
    assert state.get_active_territory(displayNode) == territory, (
        "a checked Place toggle must make its territory the ACTIVE one."
    )
    assert bool(displayNode.GetVisibility()) is True, (
        "arming must make the adhering highlight visible (ADR-0037 §Decision 2)."
    )


def test_place_toggle_is_exclusive_arm_b_unchecks_a(qt_widgets):
    """Arming territory B un-arms A (EXCLUSIVE — one territory armed at a time).

    ADR-0037 §Decision 2 (slice-4): toggling one Place button ON un-checks
    every other row's toggle and re-points the display node's ACTIVE territory
    at B.  [launched; toggle logic driven via the table + display node.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()

    place_a = _place_cell_or_skip(table, _header_row_for(table, territory_a))
    place_a.setChecked(True)
    assert state.get_active_territory(displayNode) == territory_a

    place_b = _place_cell_or_skip(table, _header_row_for(table, territory_b))
    place_b.setChecked(True)

    assert state.get_active_territory(displayNode) == territory_b, (
        "arming B must re-point the ACTIVE territory at B."
    )
    # A's toggle must have been un-checked (exclusivity) — re-read from the
    # rebuilt row (the checked state is display-node-derived, not stored).
    place_a_after = _place_cell_or_skip(table, _header_row_for(table, territory_a))
    assert place_a_after.isChecked() is False, (
        "arming B must un-check A's Place toggle (EXCLUSIVE arming)."
    )


def test_place_toggle_off_disarms(qt_widgets):
    """Toggling the armed Place button OFF disarms placement.

    ADR-0037 §Decision 2 (slice-4): toggling OFF clears the display node's
    armed flag (reusing the shared ``done()`` disarm body).  [launched; toggle
    logic driven via the table + display node.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    place = _place_cell_or_skip(table, _header_row_for(table, territory))
    place.setChecked(True)
    assert state.is_armed(displayNode) is True

    place_after = _place_cell_or_skip(table, _header_row_for(table, territory))
    place_after.setChecked(False)

    assert state.is_armed(displayNode) is False, (
        "toggling the Place button OFF must disarm placement."
    )


def test_checked_state_rederived_from_display_node_on_rebuild(qt_widgets):
    """The armed row's checked state survives a carrier-Modified rebuild.

    ADR-0037 §Decision 2 (slice-4): ``checked = is_armed(dn) and
    get_active_territory(dn) == territoryId`` is RE-DERIVED on each rebuild,
    NOT stored in a Python field.  Arming a territory, then forcing a rebuild
    (a carrier ``Modified()``), leaves that territory's Place toggle STILL
    checked and the others un-checked.  [launched or bare where the display
    node is reachable.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()
    place_a = _place_cell_or_skip(table, _header_row_for(table, territory_a))
    place_a.setChecked(True)

    # Force a full rebuild by adding a seed to the OTHER territory.
    carrier.AddAnnotationPoint(territory_b, 1.0, 0.0, 0.0)
    carrier.Modified()

    place_a_after = _place_cell_or_skip(table, _header_row_for(table, territory_a))
    place_b_after = _place_cell_or_skip(table, _header_row_for(table, territory_b))
    assert place_a_after.isChecked() is True, (
        "the armed territory's Place toggle must stay checked across a rebuild "
        "(checked state re-derived from the display node, not stored)."
    )
    assert place_b_after.isChecked() is False, (
        "a non-armed territory's Place toggle must read un-checked after rebuild."
    )


# ===========================================================================
# Invariant 3 — eye-icon visibility toggle (QToolButton, not QCheckBox).
# ===========================================================================


def test_visibility_cell_is_eye_icon_tool_button_not_checkbox(qt_widgets):
    """The visibility cell is a Slicer-idiomatic eye-icon ``QToolButton``.

    ADR-0037 §Decision 3 (slice-4 UX polish): the visibility column becomes a
    checkable ``qt.QToolButton`` (eye-on / eye-off, the segmentation
    convention), NOT a ``QCheckBox``.  Toggling it flips
    ``carrier.SetTerritoryVisibility``.  [launched.]
    """
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    header = _header_row_for(table, territory)
    cell = table.table().cellWidget(header, EXPECTED_COL_VISIBILITY)
    assert cell is not None, "the header row must carry a visibility cell widget."

    assert isinstance(cell, qt.QToolButton), (
        "the visibility cell must be an eye-icon QToolButton (segmentation "
        "convention), not a QCheckBox (ADR-0037 slice-4 UX polish)."
    )
    assert cell.isCheckable(), "the eye-icon toggle must be checkable."

    # Toggling flips the carrier's per-territory visibility.
    carrier.SetTerritoryVisibility(territory, True)
    cell.setChecked(False)
    assert bool(carrier.GetTerritoryVisibility(territory)) is False, (
        "un-checking the eye toggle must hide the territory on the carrier."
    )
    cell.setChecked(True)
    assert bool(carrier.GetTerritoryVisibility(territory)) is True, (
        "checking the eye toggle must show the territory on the carrier."
    )


# ===========================================================================
# Invariant 6 — colour cell stays a ctkColorPickerButton (regression guard).
# ===========================================================================


def test_colour_cell_stays_ctk_color_picker_button(qt_widgets):
    """The colour cell survives the 5-column shift as a ``ctkColorPickerButton``.

    ADR-0037 §Decision 3 (already committed): the colour swatch is a
    ``ctkColorPickerButton`` emitting ``colorChanged`` -> ``setTerritoryColor``.
    A light regression guard that the leftmost-Place-column shift does not turn
    it back into a bare swatch.  [launched.]
    """
    import ctk

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    header = _header_row_for(table, territory)
    cell = table.table().cellWidget(header, EXPECTED_COL_COLOUR)
    assert cell is not None, "the header row must carry a colour cell widget."
    assert isinstance(cell, ctk.ctkColorPickerButton), (
        "the colour cell must stay a ctkColorPickerButton after the 5-column "
        "shift (ADR-0037 §Decision 3)."
    )

    # colorChanged -> setTerritoryColor: the emitted signal writes the carrier.
    import qt

    cell.setColor(qt.QColor(int(0.3 * 255), int(0.6 * 255), int(0.9 * 255)))
    color = carrier.GetTerritoryColor(territory)
    assert (color[0], color[1], color[2]) == pytest.approx((0.3, 0.6, 0.9), abs=2e-3), (
        "the colour picker's colorChanged must write the carrier's territory "
        "colour (setTerritoryColor)."
    )


# ===========================================================================
# Invariant 5 — Add Territory mints + arms; Add seeds / Done buttons retired.
# ===========================================================================


def test_add_territory_mints_and_arms_its_toggle_reads_checked_after_rebuild(qt_widgets):
    """``Add Territory`` mints a territory AND arms it; its Place toggle checks.

    ADR-0037 §Decision 2 (slice-4): "Add Territory" mints a new empty territory
    row and arms it — after the rebuild that follows, that row's Place toggle
    reads checked (the checked state re-derived from the display node).
    [launched or bare where the display node is reachable.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()

    assert state.is_armed(displayNode) is True, "Add Territory must arm placement."
    assert state.get_active_territory(displayNode) == territory
    place = _place_cell_or_skip(table, _header_row_for(table, territory))
    assert place.isChecked() is True, (
        "the minted territory's Place toggle must read checked after rebuild."
    )


def test_add_seeds_and_done_panel_buttons_retired(qt_widgets):
    """The ``Add seeds`` + ``Done`` panel buttons are absent (slice-4 retirement).

    ADR-0037 §Decision 2 (slice-4): with per-territory Place toggles the panel
    ``Add seeds`` + ``Done`` buttons retire; the ``done()`` disarm LOGIC
    survives (reused by ``exit()`` + toggle-OFF), but the panel buttons are
    gone.  Both have a credible creep-in path (a left-in button), so this
    narrow absence stays pinned.  [launched.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)

    # The retired panel buttons must not survive as private attributes ...
    for attr in ("_addSeedsButton", "_doneButton"):
        assert not hasattr(table, attr), (
            f"the retired panel button {attr!r} must be absent (ADR-0037 slice-4)."
        )
    # ... nor as any QPushButton bearing their label text.
    import qt

    labels = {
        b.text
        for b in table.findChildren(qt.QPushButton)
        if b.text
    }
    assert "Add seeds" not in labels, "the 'Add seeds' panel button must be retired."
    assert "Done" not in labels, "the 'Done' panel button must be retired."

    # The shared disarm BODY survives (reused by exit + toggle-OFF).
    assert hasattr(table, "done"), (
        "the done() disarm logic must survive as the shared disarm body "
        "(ADR-0037 slice-4)."
    )


# ===========================================================================
# Invariant 4 — a click while armed places into THAT territory + adds one child
# row.  [launched, pipeline wired via the display node.]
# ===========================================================================


def test_click_while_armed_places_into_territory_and_adds_one_child_row(qt_widgets, monkeypatch):
    """An armed click appends one seed AND yields exactly one new child row.

    ADR-0037 §Decision 2/3 (slice-4 invariant 4): with a territory armed via
    its Place toggle, a click through the display-node-wired pipeline adds one
    surface-snapped point to the carrier AND — on the carrier-Modified rebuild
    — exactly one CHILD ROW appears under that territory's header (the
    maintainer-reported "no child rows" symptom, pinned).  [launched, pipeline
    wired via the display node.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    place = _place_cell_or_skip(table, _header_row_for(table, territory))
    place.setChecked(True)  # arm via the Place toggle (writes the display node)

    def _child_rows_for(territoryId):
        w = table.table()
        return [
            r
            for r in range(w.rowCount)
            if not table.isHeaderRow(r) and table.territoryOfRow(r) == territoryId
        ]

    before_rows = len(_child_rows_for(territory))
    before_points = carrier.GetNumberOfAnnotationPoints(territory)

    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent)) is True

    assert carrier.GetNumberOfAnnotationPoints(territory) == before_points + 1, (
        "an armed click must append EXACTLY ONE seed to the ACTIVE territory."
    )
    after_rows = _child_rows_for(territory)
    assert len(after_rows) == before_rows + 1, (
        "an armed click must add EXACTLY ONE child row under the armed "
        "territory's header (ADR-0037 slice-4 invariant 4)."
    )
    # The new child row renders in the shifted 5-column offsets.
    child_row = after_rows[-1]
    widget = table.table()
    assert widget.item(child_row, EXPECTED_COL_LABEL) is not None, (
        "the new child row's status text must land in the label column (index 3)."
    )
    assert widget.cellWidget(child_row, EXPECTED_COL_STATUS) is not None, (
        "the new child row's delete affordance must land in the status column "
        "(index 4)."
    )


# ===========================================================================
# Invariant 2 — module-active gate: exit() disarms; a later click places nothing.
# ===========================================================================


def test_exit_disarms_and_a_later_click_places_nothing(qt_widgets, monkeypatch):
    """``exit()`` disarms placement so a subsequent click adds no seed.

    ADR-0037 §Decision 2 (slice-4 module-active gate): the widget's ``exit()``
    disarms placement (clears the display node's armed/active + hides the
    highlight) so no view claims an add-on-click while VascularTerritories is
    inactive.  After ``exit()``, a click through the display-node-wired
    pipeline places nothing and the display node reads dis-armed + hidden.
    [launched, pipeline wired via the display node.]
    """
    _slicer_or_skip()
    _qt_or_skip()
    import slicer as _slicer  # noqa: F811 — the widget lives on the launched module

    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    qt_widgets.append(widget)
    # Drop the widget's scene observers before the autouse scene-clear fires.
    for event, handler in (
        (_slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (_slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        try:
            widget.removeObserver(_slicer.mrmlScene, event, handler)
        except Exception:  # noqa: BLE001 — best-effort across widget shapes
            pass

    table = getattr(widget, "_territoriesTable", None)
    if table is None:
        pytest.skip(
            "composed TerritoriesTableWidget absent -- LayerDMLib / the wrapped "
            "carrier is off the launched path (ADR-0027)."
        )
    _require_table_row_model(table)
    _require_five_column_layout_or_skip(table)
    displayNode = getattr(widget, "_highlightDisplayNode", None)
    carrier = getattr(widget, "_annotationCarrier", None)
    if displayNode is None or carrier is None:
        pytest.skip(
            "widget did not expose the shared display node + carrier handles "
            "(ADR-0027)."
        )
    state = _import_interaction_state_or_skip()

    # Arm via the table's Place toggle, then bind a REAL pipeline to the SAME
    # display node the widget/table write.
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")
    territory = table.addTerritory()
    place = _place_cell_or_skip(table, _header_row_for(table, territory))
    place.setChecked(True)
    assert state.is_armed(displayNode) is True

    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)

    # The module-active gate: exit() disarms.
    widget.exit()
    assert state.is_armed(displayNode) is False, (
        "exit() must disarm placement (ADR-0037 slice-4 module-active gate)."
    )
    assert bool(displayNode.GetVisibility()) is False, (
        "exit() must hide the adhering highlight."
    )

    before = carrier.GetNumberOfAnnotationPoints(territory)
    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent))
    assert carrier.GetNumberOfAnnotationPoints(territory) == before, (
        "a click after exit() must place nothing (no view claims an add-on-"
        "click while the module is inactive)."
    )

    widget.cleanup()


def test_enter_auto_arms_nothing(qt_widgets):
    """``enter()`` arms NOTHING (no view claims a click just from entering).

    ADR-0037 §Decision 2 (slice-4): ``enter()`` auto-arms nothing — placement
    is an EXPLICIT per-territory Place toggle.  After ``enter()`` the display
    node reads dis-armed.  [launched.]
    """
    _slicer_or_skip()
    _qt_or_skip()
    import slicer as _slicer  # noqa: F811

    from VascularTerritories import VascularTerritoriesWidget

    widget = VascularTerritoriesWidget()
    widget.setup()
    qt_widgets.append(widget)
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
        pytest.skip(
            "widget did not expose the shared display node handle (ADR-0027)."
        )
    table = getattr(widget, "_territoriesTable", None)
    if table is None:
        pytest.skip("composed TerritoriesTableWidget absent (ADR-0027).")
    _require_five_column_layout_or_skip(table)
    state = _import_interaction_state_or_skip()

    widget.enter()

    assert state.is_armed(displayNode) is False, (
        "enter() must auto-arm nothing (ADR-0037 slice-4 module-active gate)."
    )

    widget.cleanup()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
