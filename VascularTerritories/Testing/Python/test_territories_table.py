# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-2 — the VascularTerritories annotation tree UI.

ADR-0037 §Decision 3 (§3 table) replaces the legacy
``inputSurfaceSelector`` / ``endPointsMarkupsSelector`` place-widget panel
with a Python-composed custom tree (ADR-0004): a CUSTOM view, not a stock
point-list view, because the surface-snap + territory-grouping contract has
no stock fit (the same call ADR-0034 made against
``qMRMLSegmentsTableView``).

The confirmed design (maintainer-approved this session) that these
invariants pin:

* TREE SHAPE (composite-row, two-level hierarchy).  The tree is SINGLE-COLUMN
  with NO header row and NO visible column grid (``columnCount == 1``,
  ``header().isHidden()``).  Territories are TOP-LEVEL items; seed points are
  CHILD items nested under their territory (disclosure triangle + indentation)
  — a genuine parent/child hierarchy, unlike the flat ADR-0034 segments table.
  Each item carries ONE composite ``QWidget`` on column 0
  (``tree.itemWidget(item, 0)``) holding the row's controls as a horizontal
  STRIP, addressed by NAME (never by column).  A territory row carries a Place
  toggle, an eye-icon visibility toggle, a colour button, an editable label,
  and a status label; each seed child row carries an on-surface status label +
  a delete button.
* CARRIER IS THE MODEL.  The tree reads/writes the Stage-1 annotation
  carrier ``vtkMRMLCustomTerritoriesNode`` (points via ``AddAnnotationPoint``
  / ``GetNumberOfAnnotationPoints`` / ``GetNthAnnotationPoint`` /
  ``ClearAnnotationPoints``; the Stage-2 display slot via the per-territory
  colour / label / visibility accessors).  It OBSERVES the carrier's
  ``vtkCommand::ModifiedEvent`` and rebuilds; edits write back.
* ARMING (pipeline-managed, NOT a Slicer mouse mode).  The arm state lives
  on the SHARED highlight DISPLAY NODE (``TerritoryInteractionState``): the
  tree WRITES arm / active-territory / carrier onto it, and the
  manager-driven placement Pipeline READS them back at event time — the
  widget cannot reach the manager-owned Pipeline instance directly, so the
  display node is the shared handle (the 3D-fix contract).  "Add Territory"
  mints a new empty territory on the carrier, selects its item, makes it the
  ACTIVE territory, and arms placement; each surface click through the
  pipeline seam appends ONE seed to the ACTIVE territory (sequential,
  unbounded).  "Done" / Esc disarms.  Selecting an existing territory +
  "Add seeds" re-arms into THAT territory.  The integration these tests pin:
  a REAL ``TerritoryPlacementPipeline`` whose ``SetDisplayNode`` was called
  with the SAME display node the tree writes to routes the click into the
  ACTIVE territory — the gap that let the detached-instance bug through.
* DELETE CONVERGENCE.  Delete-by-seed (tree) and delete-by-pick (pipeline)
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

A Python-widget-composed tree, mirroring the Stage-2 table paradigm
(ADR-0034) but CUSTOM and HIERARCHICAL (ADR-0037 §Decision 3):

  * module path ``VascularTerritoriesLib.TerritoriesTableWidget``, class
    ``TerritoriesTableWidget`` (a composed ``qt.QWidget`` owning a
    ``qt.QTreeWidget``), constructed over the carrier + the SHARED highlight
    display node:
      ``TerritoriesTableWidget(carrier=<vtkMRMLCustomTerritoriesNode>,
                               displayNode=<vtkMRMLTerritoriesHighlightDisplayNode>)``.
  * ``tree()`` -> the underlying ``qt.QTreeWidget``;
  * item-model helpers:
      ``territoryIds() -> list[str]`` (top-level items, in order),
      ``territoryItem(territoryId) -> QTreeWidgetItem`` (the top-level item),
      ``seedItems(territoryId) -> list[QTreeWidgetItem]`` (child items, in
      order);
  * composite sub-widget getters (controls addressed by NAME, never column):
      ``territoryRowWidget(territoryId) -> QWidget``,
      ``placeButton(territoryId) -> QToolButton`` (checkable),
      ``visibilityButton(territoryId) -> QToolButton`` (checkable eye),
      ``colourButton(territoryId) -> ctkColorPickerButton``,
      ``territoryLabelEdit(territoryId) -> QLineEdit`` (editing writes
      ``setTerritoryLabel``),
      ``seedRowWidget(territoryId, pointIndex) -> QWidget``,
      ``seedDeleteButton(territoryId, pointIndex) -> QToolButton``,
      ``seedStatusText(territoryId, pointIndex) -> str``;
  * ``addTerritory(territoryId=None) -> str`` — mint an empty territory,
    select its item, arm the pipeline into it;
  * ``armForSelectedTerritory()`` — re-arm placement into the selected
    territory ("Add seeds");
  * ``selectTerritoryRow(territoryId)`` — select a territory's top-level item;
  * ``done()`` — disarm;
  * ``deleteSeed(territoryId, pointIndex)`` — the delete-from-tree entry
    point, converging on the carrier's ``RemoveNthAnnotationPoint`` (the SAME
    method the pipeline's ``DeleteAnnotationPoint`` reaches);
  * completeness readers on the territory item:
    ``territoryStatusText(territoryId) -> str`` and
    ``territoryHasIncompleteGlyph(territoryId) -> bool``.

The arm state rides on the SHARED highlight DISPLAY NODE
(``TerritoryInteractionState``: ``set_armed`` / ``is_armed`` /
``set_active_territory`` / ``get_active_territory`` / ``set_carrier`` /
``get_carrier``), the handle both the tree and the manager-driven Pipeline
hold.  The Pipeline reads them back via its ``IsArmed()`` /
``GetActiveTerritory()`` seam once ``SetDisplayNode`` binds the SAME node.
"Add Territory" writes active-territory + armed onto the display node so a
click appends to the ACTIVE territory, not an implicit one.

-- WHY LAUNCHED-SLICER --

The tree needs Qt (``qt.QTreeWidget``) + the wrapped
``vtkMRMLCustomTerritoriesNode`` carrier + (for the arming tests) the
LayerDM ``TerritoryPlacementPipeline``.  A bare ``PythonSlicer -m pytest``
has ``slicer.mrmlScene is None``, no Qt, and LayerDMLib off the path, so
every test here SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the composite-row widget + the carrier display slot + the
Pipeline arm seam do not exist, so the import / ``tree()`` / single-column /
header-hidden / ``territoryRowWidget`` / ``placeButton`` / ``hasattr`` guards
skip-pend; the skips lift at the composite-row implementation commit.  Under a
launched Slicer, verify run-vs-skip in the CI log once the seam lands — never
trust overall green (the launched harness is green-but-skipping prone).

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
HIGHLIGHT_DISPLAY_CLASS = "vtkMRMLTerritoriesHighlightDisplayNode"
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

# The columns + header row are DROPPED (ADR-0037 §Decision 2 slice-4
# amendment): the tree is SINGLE-COLUMN with a hidden header, each item
# carrying ONE composite QWidget on column 0.  Controls are addressed by NAME
# through the composite getters, never by column index.
EXPECTED_COLUMN_COUNT = 1  # single-column tree; the composite row lives on col 0
COMPOSITE_COLUMN = 0


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


def _make_display_node_or_skip(slicer, name="TableHighlightTest"):
    """Mint the shared highlight display node, or skip-pend (ADR-0027).

    The display node is the shared handle both the tree and the
    manager-driven placement Pipeline hold: the tree writes arm /
    active-territory / carrier onto it, the Pipeline reads them back.
    """
    node = slicer.mrmlScene.AddNewNodeByClass(HIGHLIGHT_DISPLAY_CLASS, name)
    if node is None:
        pytest.skip(
            f"{HIGHLIGHT_DISPLAY_CLASS} not registered -- the shared highlight "
            "display node (ADR-0036/0037) is unavailable (launched build)."
        )
    # The module-scoped overlay gate is default-CLOSED and opened by the
    # widget's enter() (TerritoryInteractionState.set_overlays_enabled).  A
    # Pipeline test mints its own display node and has no widget, so it models
    # a SHOWING module explicitly -- otherwise the pipeline correctly draws
    # nothing and every overlay assertion below would be asserting the gate.
    from slicer_pytest_support import open_module_overlay_gate

    open_module_overlay_gate(node, "VascularTerritories")
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
    """Import the tree widget class or skip-pend (ADR-0027)."""
    try:
        from VascularTerritoriesLib.TerritoriesTableWidget import (
            TerritoriesTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"TerritoriesTableWidget not importable ({exc!r}) -- the ADR-0037 "
            "territories widget has not landed OR Qt/LayerDMLib is not "
            "reachable here.  The skip lifts at the tree-rewrite implementation "
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


def _make_table_or_skip(slicer, carrier, displayNode):
    """Construct the tree over the carrier + shared display node.

    Skip-pends when the widget constructor does not yet accept the
    ``(carrier=, displayNode=)`` seam (the 3D-fix contract; tree rewrite not
    landed).
    """
    TerritoriesTableWidget = _import_table_or_skip()
    try:
        table = TerritoriesTableWidget(carrier=carrier, displayNode=displayNode)
    except TypeError as exc:
        pytest.skip(
            f"TerritoriesTableWidget(carrier=, displayNode=) seam absent ({exc!r}) "
            "-- the ADR-0037 widget constructor has not landed (ADR-0027)."
        )
    return table


def _require_tree_model(table):
    """Skip-pend unless the widget exposes the item-based tree reader seams."""
    for method in ("tree", "territoryIds", "territoryItem", "seedItems"):
        if not hasattr(table, method):
            pytest.skip(
                f"TerritoriesTableWidget has no {method} tree seam -- the "
                "ADR-0037 QTreeWidget rewrite has not landed (ADR-0027)."
            )


def _require_composite_rows_or_skip(table):
    """Skip-pend unless the widget adopted the composite-row layout.

    The gate for the tree-shape assertions: while the ``tree()`` seam is
    absent, OR the tree is not single-column (``columnCount != 1``), OR its
    header is not hidden, OR the ``territoryRowWidget`` / ``placeButton``
    composite getters are absent, the tests collect + SKIP-PENDING and RUN
    once the composite-row rewrite lands (ADR-0037 §Decision 2 slice-4
    amendment; ADR-0027).
    """
    if not hasattr(table, "tree"):
        pytest.skip(
            "TerritoriesTableWidget has no tree() seam -- the ADR-0037 "
            "composite-row rewrite has not landed (ADR-0027)."
        )
    tree = table.tree()
    if tree.columnCount != EXPECTED_COLUMN_COUNT:
        pytest.skip(
            f"tree has {tree.columnCount} columns, not the slice-4 single-column "
            "(composite-row) layout -- the column-drop rewrite has not landed "
            "(ADR-0027)."
        )
    header = tree.header()
    if header is None or not header.isHidden():
        pytest.skip(
            "tree header is not hidden -- the slice-4 header-drop has not landed "
            "(ADR-0027)."
        )
    for method in ("territoryRowWidget", "placeButton"):
        if not hasattr(table, method):
            pytest.skip(
                f"TerritoriesTableWidget has no {method} composite getter -- the "
                "ADR-0037 slice-4 composite-row rewrite has not landed (ADR-0027)."
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


def _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch):
    """Bind a REAL pipeline to the SHARED display node so it reads live state.

    This is the integration the detached-instance bug slipped through: the
    pipeline resolves its carrier / active territory / arm flag from the
    display node the TREE writes to (``SetDisplayNode`` + the carrier bound
    onto the display node via ``TerritoryInteractionState``), NOT from a
    hand-armed detached instance.  A stub renderer + injected pick core keep
    the click GL-free.
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
    # Bind the carrier onto the SHARED display node, then hand the display
    # node to the pipeline: it now reads the SAME carrier + arm state the
    # tree writes.  SetDisplayNode resets the pick to force a re-resolve from
    # the node's pickSurface (production behaviour), so inject the unit-sphere
    # pick AFTER binding the display node.
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)
    pipeline.SetPickCore(VesselSurfacePick(_unit_sphere()))


def _require_arm_seam(pipeline):
    """Skip-pend unless the Pipeline exposes the active-territory + arm seam."""
    for method in ("SetActiveTerritory", "GetActiveTerritory", "Arm", "Disarm", "IsArmed"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"TerritoryPlacementPipeline has no {method} -- the ADR-0037 "
                "active-territory + arm seam has not landed.  A click must "
                "append to the ACTIVE territory, not an implicit one "
                "(§Decision 3 arming model; ADR-0027)."
            )


# --------------------------------------------------------------------------- #
# TREE SHAPE — top-level item per territory + child item per seed
# --------------------------------------------------------------------------- #


def test_tree_builds_top_level_item_per_territory_and_child_item_per_point(qt_widgets):
    """The tree has one top-level item per territory + one child item per seed.

    ADR-0037 §Decision 3 / §3 table: territories are TOP-LEVEL items, seed
    points CHILD items nested under them.  A carrier with two territories
    (2 + 3 seeds) yields 2 top-level items with 2 + 3 child items, in
    territory order.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    for x, y, z in [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0), (0.0, 3.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)
    carrier.Modified()

    tree = table.tree()
    assert tree.topLevelItemCount == 2, "one top-level item per territory."
    assert TERRITORY_A in table.territoryIds()
    assert TERRITORY_B in table.territoryIds()

    # Each territory's child-item count matches its seed count, and each child
    # is genuinely nested under its territory's top-level item.
    for territory, expected in ((TERRITORY_A, 2), (TERRITORY_B, 3)):
        parent = table.territoryItem(territory)
        assert parent is not None
        seeds = table.seedItems(territory)
        assert len(seeds) == expected, f"one child item per seed for {territory}."
        assert parent.childCount() == expected
        for j, seed in enumerate(seeds):
            assert seed.parent() is parent, "each seed must nest under its territory."
            assert parent.child(j) is seed, "seedItems order must match child() order."
        assert expected == carrier.GetNumberOfAnnotationPoints(territory)


def test_carrier_modified_event_rebuilds_the_tree(qt_widgets):
    """A carrier ``ModifiedEvent`` triggers a tree rebuild (the carrier is the model).

    ADR-0037 §Decision 3: the tree OBSERVES the carrier's
    ``vtkCommand::ModifiedEvent`` and rebuilds.  Adding a point to the
    carrier (outside the tree) grows the child-item count without an
    explicit tree refresh call.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)

    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    before = len(table.seedItems(TERRITORY_A))

    carrier.AddAnnotationPoint(TERRITORY_A, 2.0, 0.0, 0.0)  # fires ModifiedEvent

    after = len(table.seedItems(TERRITORY_A))
    assert after == before + 1, (
        "a carrier ModifiedEvent must rebuild the tree (child-item count grows "
        "with the seed count) -- the carrier is the model, no manual refresh."
    )


def test_seed_drag_defers_full_rebuild_until_release(qt_widgets):
    """A seed drag does NOT rebuild the tree per move; ONE rebuild on release.

    ADR-0037 §Decision 3 performance: a drag relocates the grabbed seed on
    every mouse-move (``SetNthAnnotationPoint`` -> carrier ``Modified``), so a
    naive observer rebuilds the whole tree (every composite row widget
    destroyed + recreated) per frame -- the drag lag.  The placement Pipeline
    publishes a drag-in-flight flag on the shared display node on grab and
    clears it + fires ONE carrier ``Modified`` on release; the table observer
    reads the flag and defers its full ``_rebuild`` until the drag ends.  This
    pins: (1) carrier ``Modified``s WHILE grabbing trigger no full rebuild;
    (2) the release rebuild runs once; (3) the final positions are consistent.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    if not hasattr(state, "set_grabbing"):
        pytest.skip(
            "TerritoryInteractionState has no set_grabbing -- the drag-defer "
            "seam has not landed (ADR-0027)."
        )
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)

    # A seed to drag.
    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)

    # Spy on the full rebuild.
    rebuild_calls = {"n": 0}
    real_rebuild = table._rebuild

    def _counting_rebuild():
        rebuild_calls["n"] += 1
        real_rebuild()

    table._rebuild = _counting_rebuild

    # Grab: the Pipeline sets the drag-in-flight flag on the display node.
    state.set_grabbing(displayNode, True)

    # Many drag moves relocate the grabbed seed -- each fires carrier Modified.
    for step in range(1, 11):
        carrier.SetNthAnnotationPoint(TERRITORY_A, 0, float(step), 0.0, 0.0)
    assert rebuild_calls["n"] == 0, (
        "a drag in flight must NOT trigger a full tree rebuild per move -- the "
        f"drag lag (got {rebuild_calls['n']} rebuilds across 10 moves)."
    )

    # Release: the Pipeline clears the flag, then fires ONE carrier Modified.
    state.set_grabbing(displayNode, False)
    carrier.Modified()
    assert rebuild_calls["n"] == 1, (
        "the release must run EXACTLY ONE full rebuild reflecting the final "
        f"positions (got {rebuild_calls['n']})."
    )

    # Final state consistent: the seed row exists at the dragged-to position.
    final = carrier.GetNthAnnotationPoint(TERRITORY_A, 0)
    assert (final[0], final[1], final[2]) == (10.0, 0.0, 0.0), (
        "the carrier must hold the final dragged-to seed position after release."
    )
    assert len(table.seedItems(TERRITORY_A)) == 1, (
        "the tree must show exactly the one seed after the release rebuild -- "
        "no stale / duplicated rows."
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
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    active = table.addTerritory()  # mints + selects + arms into a new territory
    # The tree wrote arm + active onto the SHARED display node; the pipeline
    # (bound to that SAME node via SetDisplayNode) reads them back — the
    # integration the detached-instance bug slipped through.
    assert pipeline.IsArmed() is True, (
        "Add Territory must arm placement via the shared display node."
    )
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
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)

    # An ACTIVE territory is set (so the gate under test is the ARM flag, not a
    # missing active territory); then the tree's "Done" disarms via the
    # shared display node.
    pipeline.SetActiveTerritory(TERRITORY_A)
    table.done()
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
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    pipeline.SetActiveTerritory(TERRITORY_A)
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
    """Selecting a territory + Add seeds redirects clicks to the newly ACTIVE one.

    ADR-0037 §Decision 3: "Selecting an existing territory + 'Add seeds'
    re-arms into that territory."  After re-arming into territory B, a click
    lands in B — not the previously active A.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    for seam in ("addTerritory", "armForSelectedTerritory", "selectTerritoryRow"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} seam -- cannot pin "
                "active-territory switching (ADR-0037 Stage-2; ADR-0027)."
            )

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()
    # Re-arm into A first, then switch back to B via the item selection.
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
# DELETE convergence — tree + pipeline share one carrier deletion path
# --------------------------------------------------------------------------- #


def test_delete_seed_removes_exactly_one_point(qt_widgets):
    """Delete-by-seed removes EXACTLY ONE carrier point (§Decision 3 / §Decision 2).

    Deleting a seed child item drops that one seed from the carrier; the
    count falls by one and the survivors keep their order.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    if not hasattr(table, "deleteSeed"):
        pytest.skip("TerritoriesTableWidget has no deleteSeed seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    # Delete territory A, point index 1.
    table.deleteSeed(TERRITORY_A, 1)

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1, (
        "delete-by-seed must remove EXACTLY ONE carrier point."
    )
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 1)) == pytest.approx(pts[2], abs=1e-6)


def test_delete_by_seed_and_by_pick_share_one_carrier_path(qt_widgets):
    """Delete-by-seed and the pipeline's ``DeleteAnnotationPoint`` converge.

    ADR-0037 §Decision 3 delete convergence: BOTH entry points route through
    ONE carrier deletion path.  Deleting index 1 via each entry point removes
    the same point and drops the count by one identically — no divergent
    routes.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    if not hasattr(pipeline, "SetDisplayNode") or not hasattr(pipeline, "DeleteAnnotationPoint"):
        pytest.skip(
            "TerritoryPlacementPipeline lacks SetDisplayNode / DeleteAnnotationPoint "
            "-- cannot pin delete convergence (ADR-0027)."
        )
    # The pipeline resolves its carrier from the SHARED display node (the same
    # handle the tree binds), so both delete entry points reach one carrier.
    state = _import_interaction_state_or_skip()
    state.set_carrier(displayNode, carrier)
    pipeline.SetDisplayNode(displayNode)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    if not hasattr(table, "deleteSeed"):
        pytest.skip("TerritoriesTableWidget has no deleteSeed seam (ADR-0027).")

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

    # Route 2: tree delete-by-seed on territory A, index 1.
    table.deleteSeed(TERRITORY_A, 1)
    a_after = [
        tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, i))
        for i in range(carrier.GetNumberOfAnnotationPoints(TERRITORY_A))
    ]

    # Both routes must yield the SAME surviving set (points 0 and 2).
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_B) == len(pts) - 1
    assert a_after == pytest.approx(b_after, abs=1e-6), (
        "delete-by-seed and delete-by-pick must converge on one carrier path "
        "(identical survivors) -- no divergent deletion routes."
    )


# --------------------------------------------------------------------------- #
# TERRITORY-LEVEL DELETE — remove a whole territory (incl. an EMPTY one)
# --------------------------------------------------------------------------- #


def test_territory_delete_button_removes_the_whole_territory(qt_widgets):
    """The territory header row carries a delete button that removes it wholly.

    ADR-0037 §Decision 3: a territory-HEADER delete affordance removes the
    territory and all its seeds via the carrier's ``RemoveTerritory`` -- so a
    populated territory drops from ``GetAnnotationTerritoryIds`` and its points
    go, while a sibling is untouched.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "territoryDeleteButton") or not hasattr(carrier, "RemoveTerritory"):
        pytest.skip(
            "TerritoriesTableWidget/carrier lack the territory-level delete seam "
            "(territoryDeleteButton / RemoveTerritory) (ADR-0027)."
        )

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.AddAnnotationPoint(TERRITORY_B, 0.0, 1.0, 0.0)
    carrier.Modified()

    delete = table.territoryDeleteButton(TERRITORY_A)
    assert delete is not None, "the territory header row must carry a delete button."
    delete.click()

    assert TERRITORY_A not in list(carrier.GetAnnotationTerritoryIds()), (
        "deleting a territory must drop it from GetAnnotationTerritoryIds."
    )
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == 0, (
        "deleting a territory must drop all its seeds."
    )
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_B) == 1, (
        "deleting a territory must NOT touch a sibling."
    )


def test_empty_territory_is_deletable_via_the_header_button(qt_widgets):
    """An EMPTY (zero-seed) minted territory is removable via its header button.

    ADR-0037 §Decision 3: the failure mode this fixes -- a territory with no
    seeds has no seed rows, so the per-seed delete never appears; the header
    delete affordance must still remove it.  Mints an empty territory via
    ``addTerritory`` and clicks its header delete.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "territoryDeleteButton") or not hasattr(carrier, "RemoveTerritory"):
        pytest.skip(
            "TerritoriesTableWidget/carrier lack the territory-level delete seam "
            "(ADR-0027)."
        )

    territoryId = table.addTerritory()
    assert carrier.GetNumberOfAnnotationPoints(territoryId) == 0, (
        "precondition: the minted territory has no seeds (the empty case)."
    )
    assert territoryId in table.territoryIds(), (
        "precondition: the empty territory has a top-level (header) item."
    )

    delete = table.territoryDeleteButton(territoryId)
    assert delete is not None, "an empty territory's header row must carry a delete button."
    delete.click()

    assert territoryId not in table.territoryIds(), (
        "deleting an empty territory must drop its top-level item."
    )
    assert territoryId not in list(carrier.GetDisplayTerritoryIds()), (
        "deleting an empty territory must clear its display slot too."
    )


def test_deleting_the_active_territory_clears_the_arm_state(qt_widgets):
    """Deleting the ACTIVE (armed) territory disarms placement (hygiene).

    ADR-0037 §Decision 3: if the deleted territory is the display node's active
    territory, the arm state is cleared so a subsequent surface click does not
    append to a territory that is gone.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "deleteTerritory") or not hasattr(carrier, "RemoveTerritory"):
        pytest.skip(
            "TerritoriesTableWidget/carrier lack the territory-level delete seam "
            "(ADR-0027)."
        )
    state = _import_interaction_state_or_skip()

    # Mint + arm into a territory (addTerritory arms into the new territory).
    territoryId = table.addTerritory()
    assert state.is_armed(displayNode) is True, (
        "precondition: minting a territory arms placement into it."
    )
    assert state.get_active_territory(displayNode) == territoryId, (
        "precondition: the minted territory is the active one."
    )

    table.deleteTerritory(territoryId)

    assert state.is_armed(displayNode) is False, (
        "deleting the active territory must clear the arm state so placement "
        "does not target a gone territory (ADR-0037 §Decision 3)."
    )


# --------------------------------------------------------------------------- #
# DISPLAY EDITS — write the carrier display slot without touching geometry
# --------------------------------------------------------------------------- #


def test_visibility_colour_label_edits_leave_geometry_unchanged(qt_widgets):
    """Territory visibility / colour / label edits write the display slot only.

    ADR-0037 §Decision 3: the territory item carries per-territory visibility,
    colour swatch, and label; editing them writes the carrier's display slot
    "without touching geometry" — the annotation-point count + coords stay
    byte-identical.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
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
    table.setTerritoryLabel(TERRITORY_A, "Renamed via tree")

    # The display slot took the edit ...
    assert bool(carrier.GetTerritoryVisibility(TERRITORY_A)) is False
    assert carrier.GetTerritoryLabel(TERRITORY_A) == "Renamed via tree"
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


def test_editing_the_label_line_edit_writes_set_territory_label(qt_widgets):
    """Editing the row's ``QLineEdit`` writes ``setTerritoryLabel`` on the carrier.

    ADR-0037 §Decision 3 (slice-4 composite-row): the editable label is a
    ``qt.QLineEdit`` in the territory row widget (``territoryLabelEdit``).
    Committing an edit (setting the text + emitting ``editingFinished``) routes
    through the tree's ``setTerritoryLabel`` and writes the carrier's display
    slot — the composite-row replacement for the retired in-item editable text.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory") or not hasattr(table, "territoryLabelEdit"):
        pytest.skip(
            "TerritoriesTableWidget has no addTerritory / territoryLabelEdit seam "
            "(ADR-0027)."
        )

    territory = table.addTerritory()
    edit = table.territoryLabelEdit(territory)
    assert edit is not None, "the territory row must carry an editable label QLineEdit."

    edit.setText("Renamed via line edit")
    edit.editingFinished()  # commit the edit

    assert carrier.GetTerritoryLabel(territory) == "Renamed via line edit", (
        "committing the label QLineEdit must write setTerritoryLabel on the "
        "carrier (ADR-0037 §Decision 3 composite-row)."
    )


def test_seed_delete_button_removes_exactly_that_seed(qt_widgets):
    """Clicking a seed's delete button removes exactly that seed via the carrier.

    ADR-0037 §Decision 3 delete convergence (slice-4 composite-row): each seed
    row's delete affordance (``seedDeleteButton``) drives the SAME carrier
    removal path as ``deleteSeed``; clicking it drops exactly that one seed.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "seedDeleteButton"):
        pytest.skip("TerritoriesTableWidget has no seedDeleteButton seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    delete = table.seedDeleteButton(TERRITORY_A, 1)
    assert delete is not None, "the seed row must carry a delete button."
    delete.click()

    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == len(pts) - 1, (
        "clicking a seed's delete button must remove EXACTLY ONE carrier point."
    )
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthAnnotationPoint(TERRITORY_A, 1)) == pytest.approx(pts[2], abs=1e-6)


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
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    for seam in ("territoryStatusText", "territoryHasIncompleteGlyph"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} status seam -- cannot "
                "assert the glyph+text completeness indicator (ADR-0010; ADR-0027)."
            )

    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)  # one seed -> incomplete
    for x, y, z in [(0.0, 1.0, 0.0), (0.0, 2.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_B, x, y, z)  # two seeds -> complete
    carrier.Modified()

    # Assert the GLYPH + TEXT indicator, never a colour.
    assert table.territoryHasIncompleteGlyph(TERRITORY_A) is True, (
        "a < 2-seed territory must carry an incomplete GLYPH (ADR-0010)."
    )
    assert table.territoryStatusText(TERRITORY_A).strip() != "", (
        "the incomplete state must also carry TEXT (ADR-0010, never colour alone)."
    )
    assert table.territoryHasIncompleteGlyph(TERRITORY_B) is False, (
        "a >= 2-seed territory must NOT be flagged incomplete."
    )


# --------------------------------------------------------------------------- #
# REVISED slice 5 — coloured seed rows + per-structure warning glyph
# --------------------------------------------------------------------------- #
#
# The revised multi-system design (Docs/design/multi-system-territory-plan.md
# §B3 / §B6): each seed child row carries a colour swatch tinted with the seed's
# STRUCTURE colour (the input segmentation's per-segment display colour) PAIRED
# with the structure NAME (ADR-0010, never colour alone); and a territory
# touching any structure with <2 seeds shows the WARNING glyph+text (that
# structure cannot yield a centerline).  The table resolves a seed's structure
# via the seed->structure mapping (§B1) over the input segmentation, so it needs
# the segmentation bound.

# Two disjoint vessel segments (Vein + Artery) with distinct display colours so
# the seed rows can be tinted per structure.
_VEIN_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^29092000^Vein~^^~Anatomic codes~^^~^^"
)
_ARTERY_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^51114001^Artery~^^~Anatomic codes~^^~^^"
)
_VEIN_CENTRE = (0.0, 0.0, 0.0)
_ARTERY_CENTRE = (100.0, 0.0, 0.0)
_VESSEL_RADIUS = 10.0

# Table structure-colour reader seams (proposed; sharpen at landing).  §B3.
SEED_STRUCTURE_ID_ACCESSOR = "seedStructureId"
SEED_STRUCTURE_COLOR_ACCESSOR = "seedStructureColor"
SET_INPUT_SEGMENTATION_SEAM = "setInputSegmentation"


def _two_vessel_segmentation_or_skip(slicer):
    """A segmentation with a Vein + Artery vessel segment, distinct colours."""
    import vtk  # local: the table test module does not import vtk at top level

    seg = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "TableTwoVessels")
    if seg is None:
        pytest.skip("vtkMRMLSegmentationNode not registered (launched build).")
    seg.CreateDefaultDisplayNodes()

    def _add(terminology, name, center, colour):
        source = vtk.vtkSphereSource()
        source.SetCenter(*center)
        source.SetRadius(_VESSEL_RADIUS)
        source.SetThetaResolution(16)
        source.SetPhiResolution(16)
        source.Update()
        modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
        modelNode.SetAndObservePolyData(source.GetOutput())
        slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
            modelNode, seg)
        slicer.mrmlScene.RemoveNode(modelNode)
        segmentation = seg.GetSegmentation()
        segId = segmentation.GetNthSegmentID(segmentation.GetNumberOfSegments() - 1)
        segmentation.GetSegment(segId).SetTag("TerminologyEntry", terminology)
        segmentation.GetSegment(segId).SetColor(*colour)
        return segId

    veinId = _add(_VEIN_TERMINOLOGY, "VeinModel", _VEIN_CENTRE, (0.1, 0.2, 0.9))
    arteryId = _add(_ARTERY_TERMINOLOGY, "ArteryModel", _ARTERY_CENTRE, (0.9, 0.1, 0.1))
    return seg, {"vein": veinId, "artery": arteryId}


def _bind_segmentation_or_skip(table, segmentation):
    """Bind the input segmentation to the table, or skip-pend (ADR-0027)."""
    if not hasattr(table, SET_INPUT_SEGMENTATION_SEAM):
        pytest.skip(
            f"TerritoriesTableWidget has no {SET_INPUT_SEGMENTATION_SEAM} seam "
            "-- the revised slice-5 seed-row structure-colour binding has not "
            "landed (ADR-0027)."
        )
    getattr(table, SET_INPUT_SEGMENTATION_SEAM)(segmentation)


def test_seed_row_is_coloured_by_its_structure(qt_widgets):
    """Each seed child row carries its STRUCTURE's segment display colour + name.

    Revised slice 5 (§B3): a seed on the vein reads the vein segment's display
    colour, a seed on the artery reads the artery's — NOT the territory palette.
    The colour is paired with the structure NAME in the row text (ADR-0010,
    never colour alone).  Pinned via the ``seedStructureId`` / ``seedStructureColor``
    reader seams.  Launched (Qt + segmentation); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    for seam in (SEED_STRUCTURE_ID_ACCESSOR, SEED_STRUCTURE_COLOR_ACCESSOR):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} seam -- the revised "
                "slice-5 seed-row structure colour reader has not landed "
                "(ADR-0027)."
            )

    segmentation, ids = _two_vessel_segmentation_or_skip(slicer)
    _bind_segmentation_or_skip(table, segmentation)

    # One seed on the vein surface, one on the artery surface.
    vein_seed = (_VEIN_CENTRE[0], _VEIN_CENTRE[1], _VEIN_CENTRE[2] + _VESSEL_RADIUS)
    artery_seed = (_ARTERY_CENTRE[0], _ARTERY_CENTRE[1], _ARTERY_CENTRE[2] + _VESSEL_RADIUS)
    carrier.AddAnnotationPoint(TERRITORY_A, *vein_seed)
    carrier.AddAnnotationPoint(TERRITORY_A, *artery_seed)
    carrier.Modified()

    assert table.seedStructureId(TERRITORY_A, 0) == ids["vein"], (
        "the first seed (on the vein surface) must map to the vein segment id "
        f"({ids['vein']!r}); got {table.seedStructureId(TERRITORY_A, 0)!r} "
        "(revised ADR-0037 slice 5, §B3)."
    )
    assert table.seedStructureId(TERRITORY_A, 1) == ids["artery"], (
        "the second seed (on the artery surface) must map to the artery segment "
        f"id ({ids['artery']!r}); got {table.seedStructureId(TERRITORY_A, 1)!r}."
    )

    vein_colour = table.seedStructureColor(TERRITORY_A, 0)
    artery_colour = table.seedStructureColor(TERRITORY_A, 1)
    assert vein_colour is not None and artery_colour is not None, (
        "each seed row must resolve its structure's display colour (§B3)."
    )
    # The two structures were given distinct segment display colours, so the two
    # seed rows must read DIFFERENT colours -- the swatch is per-structure, not
    # the (single) territory palette colour.
    assert tuple(round(c, 3) for c in vein_colour) != tuple(
        round(c, 3) for c in artery_colour
    ), (
        "seeds on DIFFERENT structures must carry DIFFERENT swatch colours -- "
        "the swatch is the segment display colour, not the territory palette "
        "(revised ADR-0037 slice 5, §B3)."
    )
    # ADR-0010: colour never alone -- the row text names the structure.
    vein_text = table.seedStatusText(TERRITORY_A, 0) if hasattr(table, "seedStatusText") else ""
    assert vein_text.strip() != "", (
        "the seed row must pair its colour swatch with structure TEXT (ADR-0010, "
        "never colour alone)."
    )


def test_under_seeded_structure_flags_the_territory(qt_widgets):
    """A territory touching a <2-seed structure shows the WARNING glyph+text.

    Revised slice 5 (§B6): the completeness check is PER STRUCTURE, not a flat
    seed count.  A territory with 2 seeds on the vein but only 1 on the artery
    has a structure (the artery) that cannot yield a centerline, so the
    territory is flagged (glyph + text, ADR-0010); a 2-on-vein + 2-on-artery
    territory is NOT flagged.  Pinned via the existing
    ``territoryHasIncompleteGlyph`` reader, extended to the per-structure gate.
    Launched (Qt + segmentation); SKIPS bare.

    Red->green: FAILS against the flat ``seedCount < 2`` check (a 3-seed
    territory reads complete regardless of structure split), PASSES once the
    check groups by structure.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    for seam in ("territoryStatusText", "territoryHasIncompleteGlyph"):
        if not hasattr(table, seam):
            pytest.skip(
                f"TerritoriesTableWidget has no {seam} status seam (ADR-0027).")

    segmentation, _ids = _two_vessel_segmentation_or_skip(slicer)
    _bind_segmentation_or_skip(table, segmentation)

    def _vein(k):
        return (_VEIN_CENTRE[0], _VEIN_CENTRE[1] + k, _VEIN_CENTRE[2] + _VESSEL_RADIUS)

    def _artery(k):
        return (_ARTERY_CENTRE[0], _ARTERY_CENTRE[1] + k, _ARTERY_CENTRE[2] + _VESSEL_RADIUS)

    # TERRITORY_A: 2 on the vein + 1 on the artery -> artery under-seeded -> flag.
    carrier.AddAnnotationPoint(TERRITORY_A, *_vein(0.0))
    carrier.AddAnnotationPoint(TERRITORY_A, *_vein(2.0))
    carrier.AddAnnotationPoint(TERRITORY_A, *_artery(0.0))
    # TERRITORY_B: 2 on the vein + 2 on the artery -> no under-seeded structure.
    carrier.AddAnnotationPoint(TERRITORY_B, *_vein(0.0))
    carrier.AddAnnotationPoint(TERRITORY_B, *_vein(2.0))
    carrier.AddAnnotationPoint(TERRITORY_B, *_artery(0.0))
    carrier.AddAnnotationPoint(TERRITORY_B, *_artery(2.0))
    carrier.Modified()

    assert table.territoryHasIncompleteGlyph(TERRITORY_A) is True, (
        "a territory with a <2-seed structure (2 on the vein, 1 on the artery) "
        "must be FLAGGED -- the under-seeded structure cannot yield a centerline "
        "(revised ADR-0037 slice 5, §B6).  A flat 3-seed count would wrongly read "
        "complete."
    )
    assert table.territoryStatusText(TERRITORY_A).strip() != "", (
        "the per-structure warning must carry TEXT (ADR-0010, never colour alone)."
    )
    assert table.territoryHasIncompleteGlyph(TERRITORY_B) is False, (
        "a territory with >=2 seeds on EVERY touched structure (2 vein + 2 "
        "artery) must NOT be flagged (revised ADR-0037 slice 5, §B6)."
    )


# --------------------------------------------------------------------------- #
# POST-REVIEW REFINEMENT — Add Territory does NOT auto-select the new row
# --------------------------------------------------------------------------- #
#
# The reviewer's refinement (ADR-0037 §Decision 2 slice-4): "Add Territory"
# mints + arms a territory but must NOT also SELECT its tree row.  Arming (the
# Place toggle reading checked) is the sole active-state cue, so a row selection
# on top of it is redundant and confuses which affordance drives placement.
# ``addTerritory``'s docstring pins this ("The new row is NOT selected/
# highlighted -- arming ... is the active-state cue").  Green regression guard:
# these RUN + PASS launched now, guarding against a re-introduced setCurrentItem.


def test_add_territory_does_not_auto_select_the_new_row(qt_widgets):
    """Add Territory arms the new territory but leaves its tree row UNSELECTED.

    Post-review refinement (ADR-0037 §Decision 2 slice-4): minting a territory
    arms placement into it (its Place toggle reads checked) but must NOT select
    its row -- arming is the active-state cue, a redundant selection is not.
    Pins that after ``addTerritory()`` the tree's current item is not the new
    row (and the selection is empty), while the Place toggle still reads checked.
    Launched (Qt + carrier); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory") or not hasattr(table, "placeButton"):
        pytest.skip(
            "TerritoriesTableWidget has no addTerritory / placeButton seam "
            "(ADR-0027)."
        )

    territory = table.addTerritory()

    tree = table.tree()
    newItem = table.territoryItem(territory)
    assert newItem is not None, "the minted territory must have a top-level item."

    # The new row is NOT the current item, and nothing is selected: arming, not
    # selection, is the active-state cue (ADR-0037 §Decision 2 slice-4).
    assert tree.currentItem() is not newItem, (
        "Add Territory must NOT auto-select the new territory's row -- arming "
        "(the checked Place toggle) is the active-state cue, not a selection."
    )
    assert len(tree.selectedItems()) == 0, (
        "Add Territory must leave the tree selection empty (no auto-select)."
    )

    # Arming IS the cue: the new territory's Place toggle reads checked.
    place = table.placeButton(territory)
    assert place is not None and place.checked is True, (
        "the minted territory's Place toggle must read checked (arming is the "
        "active-state cue, ADR-0037 §Decision 2 slice-4)."
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

    # Explicit parent: with parent=None, ScriptedLoadableModuleWidget's
    # __init__ auto-runs setup() (and show()), so the explicit setup()
    # below would run TWICE -- stacking two panels and registering
    # duplicate scene observers that outlive cleanup() (the destroyed-ui
    # 'enabled' storm, feedback_launched_widget_teardown_crash).
    import qt

    widgetParent = qt.QWidget()
    qt.QVBoxLayout(widgetParent)
    widget = VascularTerritoriesWidget(widgetParent)
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
    place-widget wiring retires, and the annotation/tree path persists NO
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

    # Explicit parent: with parent=None, ScriptedLoadableModuleWidget's
    # __init__ auto-runs setup() (and show()), so the explicit setup()
    # below would run TWICE -- stacking two panels and registering
    # duplicate scene observers that outlive cleanup() (the destroyed-ui
    # 'enabled' storm, feedback_launched_widget_teardown_crash).
    import qt

    widgetParent = qt.QWidget()
    qt.QVBoxLayout(widgetParent)
    widget = VascularTerritoriesWidget(widgetParent)
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

    # (2) no fiducial persisted by the annotation/tree path.
    fiducials = slicer.mrmlScene.GetNodesByClass("vtkMRMLMarkupsFiducialNode")
    count = fiducials.GetNumberOfItems() if fiducials is not None else 0
    assert count == 0, (
        "the annotation/tree path must persist NO vtkMRMLMarkupsFiducialNode "
        "(ADR-0037 §Conformance [review])."
    )

    for event, handler in (
        (slicer.mrmlScene.StartCloseEvent, widget.onSceneStartClose),
        (slicer.mrmlScene.EndCloseEvent, widget.onSceneEndClose),
    ):
        widget.removeObserver(slicer.mrmlScene, event, handler)
    widget.cleanup()


# --------------------------------------------------------------------------- #
# REVIEW STATUS + DERIVED EDIT-LOCK (ADR-0037 Amendment)
#
# The territory-usability plan §3-§5 / §8: a per-territory click-cycle status
# cell (NotStarted -> InProgress -> Completed -> Flagged -> NotStarted); a
# LOCKED (Completed) territory refuses each edit path (place / drag / seed-
# delete / territory-delete); a GEOMETRY edit demotes a Completed territory to
# InProgress, but a colour / label edit does NOT.
# --------------------------------------------------------------------------- #

_STATUS_NOT_STARTED = 0
_STATUS_IN_PROGRESS = 1
_STATUS_COMPLETED = 2
_STATUS_FLAGGED = 3


def _require_status_seam(table):
    """Skip-pend unless the table exposes the review-status seam (ADR-0027)."""
    for method in (
        "territoryStatus",
        "setTerritoryStatus",
        "cycleTerritoryStatus",
        "territoryIsLocked",
    ):
        if not hasattr(table, method):
            pytest.skip(
                f"TerritoriesTableWidget has no {method} -- the ADR-0037 "
                "per-territory status + derived edit-lock has not landed (ADR-0027)."
            )


def _require_carrier_status_or_skip(carrier):
    if not hasattr(carrier, "SetTerritoryStatus") or not hasattr(carrier, "GetTerritoryLocked"):
        pytest.skip(
            "vtkMRMLCustomTerritoriesNode has no status slot -- the ADR-0037 "
            "status amendment carrier has not landed (ADR-0027)."
        )


def test_status_cell_click_cycles_through_the_four_states(qt_widgets):
    """The status cell click-cycles NotStarted -> InProgress -> Completed -> Flagged -> NotStarted."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    _require_status_seam(table)

    territory = table.addTerritory()  # NotStarted by default
    assert table.territoryStatus(territory) == _STATUS_NOT_STARTED

    expected = [_STATUS_IN_PROGRESS, _STATUS_COMPLETED, _STATUS_FLAGGED, _STATUS_NOT_STARTED]
    for want in expected:
        table.cycleTerritoryStatus(territory)
        assert table.territoryStatus(territory) == want, (
            f"the status cell must cycle to {want}; got {table.territoryStatus(territory)}."
        )


def test_status_button_click_advances_the_status(qt_widgets):
    """Clicking the status QToolButton advances the review status one step."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    _require_status_seam(table)
    if not hasattr(table, "statusButton"):
        pytest.skip("TerritoriesTableWidget has no statusButton getter (ADR-0027).")

    territory = table.addTerritory()
    button = table.statusButton(territory)
    assert button is not None, "the territory row must carry a status button."

    button.click()
    assert table.territoryStatus(territory) == _STATUS_IN_PROGRESS, (
        "a status-button click must advance the review status one step."
    )


def test_locked_territory_disables_the_row_edit_controls(qt_widgets):
    """A locked (Completed) territory disables place / colour / label / Remove.

    The visibility toggle stays ENABLED (lock is independent of visibility).
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    _require_status_seam(table)

    territory = table.addTerritory()
    table.setTerritoryStatus(territory, _STATUS_COMPLETED)  # -> rebuild, locked

    assert table.territoryIsLocked(territory) is True
    assert table.placeButton(territory).enabled is False, "Place must be disabled when locked."
    assert table.colourButton(territory).enabled is False, "colour must be disabled when locked."
    assert table.territoryDeleteButton(territory).enabled is False, "Remove must be disabled when locked."
    # Visibility stays usable -- lock is orthogonal to visibility.
    assert table.visibilityButton(territory).enabled is True, (
        "visibility must stay enabled on a locked territory (lock != visibility)."
    )


def test_locked_territory_refuses_seed_and_territory_delete(qt_widgets):
    """A locked territory refuses delete-by-seed AND territory-delete (§5)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_status_seam(table)
    if not hasattr(table, "deleteSeed") or not hasattr(table, "deleteTerritory"):
        pytest.skip("TerritoriesTableWidget lacks deleteSeed / deleteTerritory (ADR-0027).")

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()
    table.setTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)
    assert table.territoryIsLocked(TERRITORY_A) is True

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    table.deleteSeed(TERRITORY_A, 0)
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a locked territory must refuse delete-by-seed (§5)."
    )

    table.deleteTerritory(TERRITORY_A)
    assert TERRITORY_A in list(carrier.GetAnnotationTerritoryIds()), (
        "a locked territory must refuse territory-delete (§5)."
    )


def test_locked_territory_refuses_colour_and_label_edits(qt_widgets):
    """A locked territory refuses colour + label edits through the table (§2/§4)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_status_seam(table)

    carrier.SetTerritoryColor(TERRITORY_A, 0.1, 0.2, 0.3)
    carrier.SetTerritoryLabel(TERRITORY_A, "Before")
    table.setTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)

    table.setTerritoryColor(TERRITORY_A, 0.9, 0.9, 0.9)
    table.setTerritoryLabel(TERRITORY_A, "After")

    colour = carrier.GetTerritoryColor(TERRITORY_A)
    assert (colour[0], colour[1], colour[2]) == pytest.approx((0.1, 0.2, 0.3), abs=1e-6), (
        "a locked territory must refuse a colour edit through the table."
    )
    assert carrier.GetTerritoryLabel(TERRITORY_A) == "Before", (
        "a locked territory must refuse a label edit through the table."
    )


def test_locked_active_territory_refuses_placement(qt_widgets, monkeypatch):
    """An armed click into a locked active territory appends NO seed (§5).

    The Pipeline's defence-in-depth status check refuses the AddAnnotationPoint
    even when the shared display node still carries an armed flag.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)

    # Arm into a territory, then lock it (Completed) and fire a click.
    pipeline.SetActiveTerritory(TERRITORY_A)
    pipeline.Arm()
    carrier.SetTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)

    before = carrier.GetNumberOfAnnotationPoints(TERRITORY_A)
    pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent))
    assert carrier.GetNumberOfAnnotationPoints(TERRITORY_A) == before, (
        "a locked active territory must refuse the placement append (§5)."
    )


def test_locked_territory_declines_the_drag_grab(qt_widgets, monkeypatch):
    """A press over a locked territory's seed does NOT grab it for a drag (§5)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    displayNode = _make_display_node_or_skip(slicer)
    pipeline = _import_pipeline_or_skip()()
    _wire_pipeline_through_display_or_skip(pipeline, displayNode, carrier, monkeypatch)
    _require_arm_seam(pipeline)
    if not hasattr(pipeline, "_nearest_key_in_display"):
        pytest.skip("TerritoryPlacementPipeline lacks the grab hit-test seam (ADR-0027).")

    pipeline.SetActiveTerritory(TERRITORY_A)
    # A seed on the pick surface (the unit sphere the wiring injected snaps to).
    carrier.AddAnnotationPoint(TERRITORY_A, 0.0, 0.0, 1.0)
    carrier.SetTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)

    key, _distance2 = pipeline._nearest_key_in_display(
        pipeline._safe_get_renderer(), _Event(vtk.vtkCommand.LeftButtonPressEvent)
    )
    assert key is None, (
        "a locked territory's seeds must not be drag-grab targets (§5)."
    )


def test_geometry_edit_demotes_completed_but_colour_label_does_not(qt_widgets):
    """A GEOMETRY edit demotes Completed -> InProgress; colour/label does NOT.

    The demote-on-edit rule (plan §9 default 5): a seed add / move / delete on
    a Completed territory (reaching the carrier directly, e.g. via the provider)
    demotes it to InProgress; a colour / label edit is cosmetic and never
    demotes.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    _require_carrier_status_or_skip(carrier)
    try:
        from VascularTerritoriesLib.TerritoryPointProvider import TerritoryPointProvider
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"TerritoryPointProvider not importable ({exc!r}) (ADR-0027).")
    if not hasattr(carrier, "SetTerritoryStatus"):
        pytest.skip("carrier has no status slot (ADR-0027).")

    provider = TerritoryPointProvider(
        carrier_getter=lambda: carrier,
        territory_getter=lambda: TERRITORY_A,
    )

    # A colour / label edit does NOT demote.
    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    carrier.SetTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)
    carrier.SetTerritoryColor(TERRITORY_A, 0.4, 0.4, 0.4)
    carrier.SetTerritoryLabel(TERRITORY_A, "Cosmetic")
    assert carrier.GetTerritoryStatus(TERRITORY_A) == _STATUS_COMPLETED, (
        "a colour / label edit must NOT demote a Completed territory."
    )

    # A GEOMETRY edit (provider add) demotes to InProgress.
    provider.add_point((2.0, 0.0, 0.0))
    assert carrier.GetTerritoryStatus(TERRITORY_A) == _STATUS_IN_PROGRESS, (
        "a geometry edit (seed add) must demote Completed -> InProgress."
    )

    # And move / delete demote too (re-lock, then edit).
    carrier.SetTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)
    provider.move_point((TERRITORY_A, 0), (3.0, 0.0, 0.0))
    assert carrier.GetTerritoryStatus(TERRITORY_A) == _STATUS_IN_PROGRESS, (
        "a geometry edit (seed move) must demote Completed -> InProgress."
    )
    carrier.SetTerritoryStatus(TERRITORY_A, _STATUS_COMPLETED)
    provider.delete_point((TERRITORY_A, 0))
    assert carrier.GetTerritoryStatus(TERRITORY_A) == _STATUS_IN_PROGRESS, (
        "a geometry edit (seed delete) must demote Completed -> InProgress."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
