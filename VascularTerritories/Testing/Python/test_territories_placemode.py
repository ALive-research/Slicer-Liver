# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 slice 4 — per-territory Place mode + module-active gate + tree-UX polish.

ADR-0037 §Decision 2 (placement/edit via the Pipeline seam) + §Decision 3
(the table UI) — sharpened by the slice-4 amendment recording the place-mode
UX.  Slice 4 makes placement an EXPLICIT, per-territory, exclusive arm toggle
driven from the tree (not an implicit "Add Territory arms it and never
disarms"), gates arming on the module being active, and polishes the panel to
the Slicer-idiomatic eye-icon visibility toggle.

The confirmed slice-4 design (maintainer-LOCKED this session), each pinned
below:

1.  PER-TERRITORY EXCLUSIVE PLACE TOGGLE.  Each territory row is ONE composite
    ``QWidget`` (a horizontal STRIP of controls, not a column grid) carrying a
    checkable "Place" ``qt.QToolButton``.  Toggling ON arms placement into THAT
    territory (``set_active_territory`` + ``set_armed(True)`` + the highlight
    visible via ``TerritoryInteractionState``) and un-checks EVERY other
    territory's toggle (EXCLUSIVE — one territory armed at a time); toggling OFF
    disarms.  The armed item's checked state is RE-DERIVED from the display node
    on each rebuild
    (``checked = is_armed(dn) and get_active_territory(dn) == territoryId``),
    NOT stored in a Python field, so it survives the carrier-Modified rebuild.

2.  MODULE-ACTIVE GATE.  ``exit()`` disarms placement (clears the display
    node's armed/active, hides the highlight, un-checks the active toggle) so
    no view claims an add-on-click when VascularTerritories is inactive.
    ``enter()`` auto-arms NOTHING.  Edits (grab/drag/delete of existing seeds)
    stay INDEPENDENT of arm state — intended, not gated.

3.  EYE-ICON VISIBILITY.  The visibility control is a Slicer-idiomatic
    eye-on / eye-off toggle (the segmentation convention): a checkable
    ``qt.QToolButton`` (NOT a ``QCheckBox``) toggling
    ``carrier.SetTerritoryVisibility``.

4.  HIERARCHICAL CHILD ITEMS ON PLACEMENT.  Placing a seed into the armed
    territory (carrier ``AddAnnotationPoint`` / a click through the
    display-node-wired pipeline) adds EXACTLY ONE child item — thus one seed
    composite-row ``QWidget`` — under that territory's top-level item on the
    next rebuild.

5.  PANEL BUTTONS.  ``Add Territory`` mints a new empty territory item AND arms
    it (its Place toggle reads checked after rebuild).  ``Add seeds`` + ``Done``
    panel buttons are RETIRED (absent).  The ``done()`` disarm logic survives
    as the shared body reused by ``exit()`` + toggle-OFF.

6.  COLOUR CONTROL guard.  The colour control is a ``ctkColorPickerButton``
    (committed in slice 2/3); a light guard that the tree rewrite does not
    regress it (``colorChanged`` -> ``setTerritoryColor``).

-- THE TREE (composite-row, two-level hierarchy) --

The panel composes a SINGLE-COLUMN ``qt.QTreeWidget`` with NO header row and
NO visible column grid (``columnCount == 1``, ``header().isHidden()``):
territories are TOP-LEVEL items, seed points are CHILD items nested under
their territory (disclosure triangle + indentation, a genuine two-level
hierarchy — unlike the flat ADR-0034 segments table).  Each item carries a
COMPOSITE ``QWidget`` on column 0 (``tree.itemWidget(item, 0)``) whose layout
holds the row's controls as a horizontal STRIP.  Controls are addressed by
NAME through the composite sub-widget getters, never by column index — the
columns no longer exist.

* TERRITORY (top-level) row widget: in order — the Place toggle
  (``qt.QToolButton``, checkable), the eye-icon visibility toggle
  (``qt.QToolButton``, checkable), the colour button (``ctk.ctkColorPickerButton``),
  an editable label (``qt.QLineEdit``), and a status label (``qt.QLabel``,
  glyph+text).  Reached via ``territoryRowWidget`` / ``placeButton`` /
  ``visibilityButton`` / ``colourButton`` / ``territoryLabelEdit`` /
  ``territoryStatusText``.
* SEED (child) row widget: a status label (``qt.QLabel``, e.g.
  "Seed N — on surface") and a delete button (``qt.QToolButton``), nested under
  its territory's top-level item.  Reached via ``seedRowWidget`` /
  ``seedStatusText`` / ``seedDeleteButton``.

-- BARE vs LAUNCHED --

The Place-toggle EXCLUSIVITY / re-derivation logic can be driven purely
through the tree + a display node (no GL, no pipeline event dispatch), so
those RUN launched where the wrapped display node is reachable, and SKIP
cleanly bare (no Qt, no wrapped node).  The exit()-disarms-a-click and
click-adds-a-child-item invariants need a REAL pipeline bound to the SAME
display node the tree writes (the detached-instance contract), so they are
LAUNCHED, pipeline wired via the display node.  Every test SKIPS cleanly bare
via the shared ``conftest`` guards.

-- RUN-VS-SKIP DISCIPLINE (ADR-0027) --

Pre-implementation the composite-row seam / Place toggle / eye-icon toggle /
exit-disarm / child-item-on-placement do not exist, so the ``tree()`` /
single-column-shape / ``territoryRowWidget`` / ``placeButton`` /  ``hasattr``
guards skip-pend; the skips lift at the slice-4 composite-row rewrite commit.
Under a launched Slicer, verify run-vs-skip in the CI log once the seam lands
— never trust overall green (the launched harness is green-but-skipping
prone).

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
# THE COMPOSITE-ROW CONTRACT the implementer MUST honour (slice 4).
#
# The columns + header row are DROPPED.  The tree is SINGLE-COLUMN
# (``columnCount == 1``) with a hidden header (``header().isHidden()``) and no
# visible column grid.  Each item — territory top-level AND seed child —
# carries ONE composite ``QWidget`` on column 0 (``tree.itemWidget(item, 0)``)
# whose layout holds the row's controls as a horizontal STRIP.  Controls are
# addressed by NAME through the composite sub-widget getters below, NEVER by
# column index.
#
# TERRITORY row widget, in order: Place toggle (checkable QToolButton),
# eye-icon visibility toggle (checkable QToolButton), colour button
# (ctkColorPickerButton), editable label (QLineEdit), status label (QLabel).
# SEED row widget: status label (QLabel) + delete button (QToolButton).
# ---------------------------------------------------------------------------
EXPECTED_COLUMN_COUNT = 1  # single-column tree; the composite row lives on col 0
COMPOSITE_COLUMN = 0


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
            "territories widget has not landed OR Qt/LayerDMLib is not reachable "
            "here (ADR-0027)."
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
    """Construct the widget over the carrier + shared display node, or skip-pend."""
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
                "ADR-0037 slice-4 QTreeWidget rewrite has not landed (ADR-0027)."
            )


def _require_composite_rows_or_skip(table):
    """Skip-pend unless the widget adopted the slice-4 composite-row layout.

    The gate for every slice-4 assertion: while the ``tree()`` seam is absent,
    OR the tree is not single-column (``columnCount != 1``), OR its header is
    not hidden, OR the ``territoryRowWidget`` / ``placeButton`` composite
    getters are absent, the tests collect + SKIP-PENDING and RUN once the
    composite-row rewrite lands (ADR-0037 §Decision 2 slice-4 amendment;
    ADR-0027).
    """
    if not hasattr(table, "tree"):
        pytest.skip(
            "TerritoriesTableWidget has no tree() seam -- the ADR-0037 slice-4 "
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


def _place_button_or_skip(table, territoryId):
    """Return the territory row's Place toggle button, or skip-pend.

    Skips while the composite Place toggle is absent so the toggle-behaviour
    tests remain collectible pre-implementation.
    """
    button = table.placeButton(territoryId)
    if button is None:
        pytest.skip(
            "no Place-toggle button on the territory row widget -- the ADR-0037 "
            "slice-4 per-territory Place toggle has not landed (ADR-0027)."
        )
    return button


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
    territory / arm flag from the display node the TREE writes to, NOT from a
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
# Invariant 1 — single-column, header-hidden tree; per-item composite row.
# ===========================================================================


def test_tree_is_single_column_with_header_hidden(qt_widgets):
    """The tree drops columns + header: single-column with a hidden header.

    ADR-0037 §Decision 2 (slice-4 amendment): the column grid + header row are
    retired.  The ``QTreeWidget`` is single-column (``columnCount == 1``) with
    its header hidden (``header().isHidden()``); each row's controls live in a
    composite ``QWidget`` on column 0, not in per-column cells.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)

    tree = table.tree()
    assert tree.columnCount == EXPECTED_COLUMN_COUNT, (
        "the tree must be single-column (columns dropped) after the slice-4 "
        "composite-row rewrite."
    )
    assert tree.header().isHidden(), (
        "the tree header row must be hidden (no visible column grid)."
    )


def test_territory_row_widget_holds_the_named_controls_strip(qt_widgets):
    """A territory row is ONE composite QWidget holding the named controls strip.

    ADR-0037 §Decision 2 (slice-4): each territory item carries a composite
    ``QWidget`` via ``tree.itemWidget(item, 0)`` whose layout holds — in order —
    the Place toggle (checkable ``QToolButton``), the eye-icon visibility toggle
    (checkable ``QToolButton``), the colour button (``ctkColorPickerButton``),
    an editable label (``QLineEdit``), and a status label (``QLabel``).  The
    controls are reached by NAME through the composite getters, never by column.
    """
    import ctk
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")
    for getter in (
        "colourButton",
        "visibilityButton",
        "territoryLabelEdit",
    ):
        if not hasattr(table, getter):
            pytest.skip(
                f"TerritoriesTableWidget has no {getter} composite getter -- the "
                "ADR-0037 slice-4 composite-row rewrite has not landed (ADR-0027)."
            )

    territory = table.addTerritory()

    # The composite row widget lives on column 0 of the top-level item.
    item = table.territoryItem(territory)
    assert item is not None, "the minted territory must have a top-level tree item."
    row = table.territoryRowWidget(territory)
    assert row is not None, "the territory item must carry a composite row widget."
    assert row is table.tree().itemWidget(item, COMPOSITE_COLUMN), (
        "territoryRowWidget must be the composite widget on column 0."
    )

    # The named controls resolve to their expected widget types.
    assert isinstance(table.placeButton(territory), qt.QToolButton)
    assert isinstance(table.visibilityButton(territory), qt.QToolButton)
    assert isinstance(table.colourButton(territory), ctk.ctkColorPickerButton)
    assert isinstance(table.territoryLabelEdit(territory), qt.QLineEdit)


def test_seed_row_widget_holds_status_label_and_delete_button(qt_widgets):
    """A seed CHILD item is ONE composite QWidget: status label + delete button.

    ADR-0037 §Decision 2 (slice-4): a seed is a CHILD item nested under its
    territory's top-level item.  Its composite row widget (on column 0) holds a
    status label (``QLabel``, non-empty text, e.g. "Seed N — on surface") and a
    delete button (``QToolButton``).  Reached via ``seedRowWidget`` /
    ``seedStatusText`` / ``seedDeleteButton`` — never by column index.
    """
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    for getter in ("seedRowWidget", "seedStatusText", "seedDeleteButton"):
        if not hasattr(table, getter):
            pytest.skip(
                f"TerritoriesTableWidget has no {getter} composite getter -- the "
                "ADR-0037 slice-4 composite-row rewrite has not landed (ADR-0027)."
            )

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]:
        carrier.AddAnnotationPoint(TERRITORY_A, x, y, z)
    carrier.Modified()

    tree = table.tree()
    seeds = table.seedItems(TERRITORY_A)
    assert len(seeds) >= 1, "the armed territory must carry at least one seed child item."
    seed = seeds[0]

    # The seed is genuinely a CHILD of its territory's top-level item.
    territory_item = table.territoryItem(TERRITORY_A)
    assert territory_item is not None
    assert seed.parent() is territory_item, (
        "a seed must be a CHILD item nested under its territory's top-level item."
    )

    # The seed's composite row widget lives on column 0.
    row = table.seedRowWidget(TERRITORY_A, 0)
    assert row is not None, "the seed item must carry a composite row widget."
    assert row is tree.itemWidget(seed, COMPOSITE_COLUMN), (
        "seedRowWidget must be the composite widget on column 0."
    )

    # Status TEXT is non-empty (glyph+text status label).
    assert table.seedStatusText(TERRITORY_A, 0).strip() != "", (
        "the seed row's status label must carry non-empty text."
    )
    # The delete affordance is a QToolButton on the seed row.
    delete = table.seedDeleteButton(TERRITORY_A, 0)
    assert isinstance(delete, qt.QToolButton), (
        "the seed row's delete affordance must be a QToolButton."
    )


# ===========================================================================
# Invariant 1 — per-territory EXCLUSIVE Place toggle.
# ===========================================================================


def test_place_toggle_arms_its_territory_on_the_display_node(qt_widgets):
    """Toggling a Place button ON arms THAT territory on the display node.

    ADR-0037 §Decision 2 (slice-4): the territory item's Place toggle writes
    ``set_active_territory`` + ``set_armed(True)`` onto the SHARED display node
    (``TerritoryInteractionState``) and makes the highlight visible.  [launched
    where the wrapped display node is reachable; the toggle logic is driven via
    the tree + display node, no pipeline dispatch needed.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    place = _place_button_or_skip(table, territory)

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
    every other territory's toggle and re-points the display node's ACTIVE
    territory at B.  [launched; toggle logic driven via the tree + display node.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()

    place_a = _place_button_or_skip(table, territory_a)
    place_a.setChecked(True)
    assert state.get_active_territory(displayNode) == territory_a

    place_b = _place_button_or_skip(table, territory_b)
    place_b.setChecked(True)

    assert state.get_active_territory(displayNode) == territory_b, (
        "arming B must re-point the ACTIVE territory at B."
    )
    # A's toggle must have been un-checked (exclusivity) — re-read from the
    # rebuilt item (the checked state is display-node-derived, not stored).
    place_a_after = _place_button_or_skip(table, territory_a)
    assert place_a_after.isChecked() is False, (
        "arming B must un-check A's Place toggle (EXCLUSIVE arming)."
    )


def test_place_toggle_off_disarms(qt_widgets):
    """Toggling the armed Place button OFF disarms placement.

    ADR-0037 §Decision 2 (slice-4): toggling OFF clears the display node's
    armed flag (reusing the shared ``done()`` disarm body).  [launched; toggle
    logic driven via the tree + display node.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    place = _place_button_or_skip(table, territory)
    place.setChecked(True)
    assert state.is_armed(displayNode) is True

    place_after = _place_button_or_skip(table, territory)
    place_after.setChecked(False)

    assert state.is_armed(displayNode) is False, (
        "toggling the Place button OFF must disarm placement."
    )


def test_checked_state_rederived_from_display_node_on_rebuild(qt_widgets):
    """The armed item's checked state survives a carrier-Modified rebuild.

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
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory_a = table.addTerritory()
    territory_b = table.addTerritory()
    place_a = _place_button_or_skip(table, territory_a)
    place_a.setChecked(True)

    # Force a full rebuild by adding a seed to the OTHER territory.
    carrier.AddAnnotationPoint(territory_b, 1.0, 0.0, 0.0)
    carrier.Modified()

    place_a_after = _place_button_or_skip(table, territory_a)
    place_b_after = _place_button_or_skip(table, territory_b)
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


def test_visibility_control_is_eye_icon_tool_button_not_checkbox(qt_widgets):
    """The visibility control is a Slicer-idiomatic eye-icon ``QToolButton``.

    ADR-0037 §Decision 3 (slice-4 UX polish): the visibility control is a
    checkable ``qt.QToolButton`` (eye-on / eye-off, the segmentation
    convention), NOT a ``QCheckBox``.  Toggling it flips
    ``carrier.SetTerritoryVisibility``.  Reached via ``visibilityButton``.
    [launched.]
    """
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory") or not hasattr(table, "visibilityButton"):
        pytest.skip(
            "TerritoriesTableWidget has no addTerritory / visibilityButton seam "
            "(ADR-0027)."
        )

    territory = table.addTerritory()
    cell = table.visibilityButton(territory)
    assert cell is not None, "the territory row must carry a visibility control."

    assert isinstance(cell, qt.QToolButton), (
        "the visibility control must be an eye-icon QToolButton (segmentation "
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
# Invariant 6 — colour control stays a ctkColorPickerButton (regression guard).
# ===========================================================================


def test_colour_control_stays_ctk_color_picker_button(qt_widgets):
    """The colour control survives the rewrite as a ``ctkColorPickerButton``.

    ADR-0037 §Decision 3 (already committed): the colour swatch is a
    ``ctkColorPickerButton`` emitting ``colorChanged`` -> ``setTerritoryColor``.
    A light regression guard that the flat-table -> composite-row rewrite does
    not turn it back into a bare swatch.  Reached via ``colourButton``.
    [launched.]
    """
    import ctk

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory") or not hasattr(table, "colourButton"):
        pytest.skip(
            "TerritoriesTableWidget has no addTerritory / colourButton seam "
            "(ADR-0027)."
        )

    territory = table.addTerritory()
    cell = table.colourButton(territory)
    assert cell is not None, "the territory row must carry a colour control."
    assert isinstance(cell, ctk.ctkColorPickerButton), (
        "the colour control must stay a ctkColorPickerButton after the "
        "composite-row rewrite (ADR-0037 §Decision 3)."
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
    top-level item and arms it — after the rebuild that follows, that item's
    Place toggle reads checked (the checked state re-derived from the display
    node).  [launched or bare where the display node is reachable.]
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    displayNode = _make_display_node_or_skip(slicer)
    state = _import_interaction_state_or_skip()
    table = _make_table_or_skip(slicer, carrier, displayNode)
    qt_widgets.append(table)
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()

    assert state.is_armed(displayNode) is True, "Add Territory must arm placement."
    assert state.get_active_territory(displayNode) == territory
    place = _place_button_or_skip(table, territory)
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
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)

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
# item.  [launched, pipeline wired via the display node.]
# ===========================================================================


def test_click_while_armed_places_into_territory_and_adds_one_child_item(qt_widgets, monkeypatch):
    """An armed click appends one seed AND yields exactly one new child item.

    ADR-0037 §Decision 2/3 (slice-4 invariant 4): with a territory armed via
    its Place toggle, a click through the display-node-wired pipeline adds one
    surface-snapped point to the carrier AND — on the carrier-Modified rebuild
    — exactly one CHILD ITEM appears under that territory's top-level item (the
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
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")

    territory = table.addTerritory()
    place = _place_button_or_skip(table, territory)
    place.setChecked(True)  # arm via the Place toggle (writes the display node)

    before_children = len(table.seedItems(territory))
    before_points = carrier.GetNumberOfAnnotationPoints(territory)

    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent)) is True

    assert carrier.GetNumberOfAnnotationPoints(territory) == before_points + 1, (
        "an armed click must append EXACTLY ONE seed to the ACTIVE territory."
    )
    after_children = table.seedItems(territory)
    assert len(after_children) == before_children + 1, (
        "an armed click must add EXACTLY ONE child item under the armed "
        "territory's top-level item (ADR-0037 slice-4 invariant 4)."
    )
    # The new child item carries a composite seed-row widget (col 0).
    seed = after_children[-1]
    new_index = len(after_children) - 1
    assert seed.parent() is table.territoryItem(territory), (
        "the new seed must be a child of the armed territory's top-level item."
    )
    if hasattr(table, "seedRowWidget"):
        assert table.seedRowWidget(territory, new_index) is not None, (
            "the new seed must carry a composite row widget on column 0 "
            "(ADR-0037 slice-4)."
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

    The same closed gate carries the MODULE-SCOPED OVERLAY rule
    (``territory-usability`` display lifecycle): nothing this module draws may
    stay visible under another module, so the seed glyphs retire on ``exit()``
    and come back on ``enter()``.
    [launched, pipeline wired via the display node.]
    """
    _slicer_or_skip()
    _qt_or_skip()
    import slicer as _slicer  # noqa: F811 — the widget lives on the launched module

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
    _require_tree_model(table)
    _require_composite_rows_or_skip(table)
    displayNode = getattr(widget, "_highlightDisplayNode", None)
    carrier = getattr(widget, "_annotationCarrier", None)
    if displayNode is None or carrier is None:
        pytest.skip(
            "widget did not expose the shared display node + carrier handles "
            "(ADR-0027)."
        )
    state = _import_interaction_state_or_skip()

    # Arm via the tree's Place toggle, then bind a REAL pipeline to the SAME
    # display node the widget/tree write.
    if not hasattr(table, "addTerritory"):
        pytest.skip("TerritoriesTableWidget has no addTerritory seam (ADR-0027).")
    territory = table.addTerritory()
    place = _place_button_or_skip(table, territory)
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

    # The module-scoped OVERLAY rule (territory-usability display lifecycle):
    # the closed gate must also retire everything this module DRAWS -- here the
    # seed glyphs -- and re-entering must bring them back.  A seed added while
    # inactive still renders no glyph; the restore rides the pipeline's own
    # display-node observer (LayerDM does not call UpdatePipeline on a
    # display-node Modified).
    carrier.AddAnnotationPoint(territory, 5.0, 0.0, 0.0)
    pipeline.UpdatePipeline()
    assert not pipeline._seed_actor.GetVisibility(), (  # noqa: SLF001 - actor seam
        "an inactive module must draw no seed glyphs."
    )
    assert not pipeline._admissible(), (  # noqa: SLF001 - gate seam
        "a retired glyph must not be grabbable either."
    )

    widget.enter()

    assert pipeline._seed_actor.GetVisibility(), (  # noqa: SLF001 - actor seam
        "enter() must bring our overlays back (the workflow resumes as left)."
    )
    assert pipeline._admissible()  # noqa: SLF001 - gate seam

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
    _require_composite_rows_or_skip(table)
    state = _import_interaction_state_or_skip()

    widget.enter()

    assert state.is_armed(displayNode) is False, (
        "enter() must auto-arm nothing (ADR-0037 slice-4 module-active gate)."
    )

    widget.cleanup()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
