# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0037 Stage-2 — the VascularTerritories annotation table widget.

ADR-0037 §Decision 3 replaces the legacy markups-selector / place-widget
panel with a Python-composed CUSTOM ``qt.QTableWidget`` (ADR-0004): the
surface-snap + territory-grouping contract has no stock point-list fit (the
same call ADR-0034 made against ``qMRMLSegmentsTableView``).

The table is a VIEW over the Stage-1 annotation carrier
(``vtkMRMLCustomTerritoriesNode``): it OBSERVES the carrier's
``vtkCommand::ModifiedEvent`` and rebuilds, and its edits write BACK to the
carrier (geometry via the point carrier + the placement Pipeline's shared
removal path, display via the per-territory display slot).  The arm state
lives on the ``TerritoryPlacementPipeline`` (pipeline-managed, not a Slicer
mouse mode); "Add Territory" mints an empty territory + arms into it, and a
surface click through the pipeline seam appends one seed to the ACTIVE
territory.

Rows are PER-POINT, grouped under per-territory HEADER rows:

* HEADER row (one per territory): per-territory visibility toggle, colour
  swatch, editable label, and a completeness indicator rendered as GLYPH +
  TEXT (ADR-0010, never colour alone) — display-only in Stage 2 (extraction
  gating is Stage 3).
* CHILD row (one per seed point): on-surface status + a delete affordance.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (the decision)
  * Docs/adr/0034-stage2-segments-table.md  (the table paradigm)
  * Docs/adr/0010-accessibility-and-i18n.md  (glyph + text, never colour)
"""

from __future__ import annotations

from typing import Any

import ctk
import qt
import vtk

try:  # pragma: no cover - exercised once per import path
    from . import TerritoryInteractionState as _state
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    import TerritoryInteractionState as _state  # type: ignore[no-redef]

#: A small distinct palette so minted territories read apart in both the
#: swatch and the 3D seed glyphs (RGB in 0..1).  Cycled by mint order.
_TERRITORY_PALETTE = (
    (0.90, 0.30, 0.24),  # red
    (0.20, 0.60, 0.86),  # blue
    (0.18, 0.80, 0.44),  # green
    (0.95, 0.77, 0.06),  # amber
    (0.61, 0.35, 0.71),  # purple
    (0.90, 0.49, 0.13),  # orange
)

#: Column layout of the custom table.  A HEADER row uses columns as
#: [visibility | colour | label | status]; a CHILD row uses
#: [<blank> | <blank> | status text | delete].
_COL_VISIBILITY = 0
_COL_COLOUR = 1
_COL_LABEL = 2
_COL_STATUS = 3
_COLUMN_COUNT = 4

#: A territory needs at least this many seeds to be complete (a centerline
#: needs a start + an end); fewer reads incomplete (display-only, Stage 2).
_MIN_SEEDS_FOR_COMPLETE = 2

#: The incomplete indicator, rendered as GLYPH + TEXT (ADR-0010): the glyph
#: is a leading warning sign, the text spells the state out.
_INCOMPLETE_GLYPH = "⚠"  # WARNING SIGN
_INCOMPLETE_TEXT = "Incomplete — needs at least two seeds"
_COMPLETE_TEXT = "Ready"

#: The Qt item-data role carrying a header row's territory id / a child row's
#: (territory id, point index).  Used by the row-model reader seams.
_ROLE_TERRITORY = qt.Qt.UserRole + 1
_ROLE_POINT_INDEX = qt.Qt.UserRole + 2
_ROLE_IS_HEADER = qt.Qt.UserRole + 3


class TerritoriesTableWidget(qt.QWidget):
    """Custom table view + editor over the annotation carrier (ADR-0037).

    Constructed over the Stage-1 carrier and the shared highlight display
    node:

        ``TerritoriesTableWidget(carrier=<vtkMRMLCustomTerritoriesNode>,
                                 displayNode=<vtkMRMLTerritoriesHighlightDisplayNode>)``.

    The carrier is the model.  Arm state / active territory are written onto
    the DISPLAY NODE (``TerritoryInteractionState``) — the shared handle the
    LayerDM-driven placement Pipeline reads at event time, since the widget
    cannot reach the manager-owned Pipeline instance directly.  Delete goes
    straight to the carrier (the same ``RemoveNthAnnotationPoint`` the
    Pipeline's pick-delete uses — one carrier method, ADR-0037 §Decision 3).
    """

    def __init__(self, carrier: Any = None, displayNode: Any = None, parent: Any = None) -> None:
        super().__init__(parent)

        self._carrier = carrier
        self._displayNode = displayNode
        # Bind the carrier onto the shared display node so the LayerDM-driven
        # placement Pipeline (which the widget cannot reach directly) resolves
        # the same carrier the table edits.
        _state.set_carrier(displayNode, carrier)
        self._carrier_observer_tag: int | None = None
        # Guards against the write-back edits re-triggering a rebuild mid-edit.
        self._rebuilding = False
        # Deterministic territory order: minted / points-bearing / display
        # territories in first-seen order (so an EMPTY minted territory keeps
        # its header row).
        self._territory_order: list[str] = []
        # Row -> (territoryId, pointIndex | None); rebuilt on every repaint.
        self._row_info: list[tuple[str, int | None]] = []
        # Auto-mint counter for "Add Territory".
        self._mint_counter = 0
        # The territory the surgeon last selected (drives "Add seeds"); the
        # explicit selection survives an offscreen ``currentRow`` of -1.
        self._selected_territory: str = ""

        layout = qt.QVBoxLayout(self)

        self._table = qt.QTableWidget()
        self._table.setColumnCount(_COLUMN_COUNT)
        self._table.setHorizontalHeaderLabels(["Visible", "Colour", "Territory / label", "Status"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        layout.addWidget(self._table)

        buttons = qt.QHBoxLayout()
        self._addTerritoryButton = qt.QPushButton("Add Territory")
        self._addSeedsButton = qt.QPushButton("Add seeds")
        self._doneButton = qt.QPushButton("Done")
        buttons.addWidget(self._addTerritoryButton)
        buttons.addWidget(self._addSeedsButton)
        buttons.addWidget(self._doneButton)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._addTerritoryButton.connect("clicked(bool)", lambda _checked: self.addTerritory())
        self._addSeedsButton.connect("clicked(bool)", lambda _checked: self.armForSelectedTerritory())
        self._doneButton.connect("clicked(bool)", lambda _checked: self.done())
        self._table.connect("itemChanged(QTableWidgetItem*)", self._onItemChanged)

        self._attachCarrierObserver()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Drop the carrier observer (called by the test teardown fixture)."""
        self._detachCarrierObserver()

    def _attachCarrierObserver(self) -> None:
        if self._carrier is None or not hasattr(self._carrier, "AddObserver"):
            return
        self._carrier_observer_tag = self._carrier.AddObserver(
            vtk.vtkCommand.ModifiedEvent, self._onCarrierModified
        )

    def _detachCarrierObserver(self) -> None:
        if self._carrier is None or self._carrier_observer_tag is None:
            return
        try:
            self._carrier.RemoveObserver(self._carrier_observer_tag)
        except Exception:  # noqa: BLE001 - teardown is best-effort
            pass
        self._carrier_observer_tag = None

    def _onCarrierModified(self, caller: Any, event: str) -> None:
        del caller, event
        if self._rebuilding:
            return
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Row-model reader seams
    # ------------------------------------------------------------------ #

    def table(self) -> Any:
        """The underlying ``qt.QTableWidget``."""
        return self._table

    def isHeaderRow(self, row: int) -> bool:
        if row < 0 or row >= len(self._row_info):
            return False
        _territory, pointIndex = self._row_info[row]
        return pointIndex is None

    def territoryOfRow(self, row: int) -> str:
        if row < 0 or row >= len(self._row_info):
            return ""
        return self._row_info[row][0]

    def pointIndexOfRow(self, row: int):
        if row < 0 or row >= len(self._row_info):
            return None
        return self._row_info[row][1]

    def rowStatusText(self, row: int) -> str:
        item = self._table.item(row, _COL_STATUS)
        return item.text() if item is not None else ""

    def rowHasIncompleteGlyph(self, row: int) -> bool:
        return _INCOMPLETE_GLYPH in self.rowStatusText(row)

    # ------------------------------------------------------------------ #
    # Territory lifecycle (arming)
    # ------------------------------------------------------------------ #

    def addTerritory(self, territoryId: str | None = None) -> str:
        """Mint an empty territory, select its header row, arm the pipeline.

        Returns the (possibly auto-generated) territory id.  Auto-generated
        ids avoid colliding with an existing territory.
        """
        if territoryId is None:
            territoryId = self._mintTerritoryId()
        newTerritory = territoryId not in self._territory_order
        if newTerritory:
            self._territory_order.append(territoryId)
        # Give the territory a display slot so its header row survives before
        # any seed lands (an empty minted territory is enumerable), and a
        # distinct palette colour so it reads apart in the swatch + 3D seeds.
        if self._carrier is not None:
            self._carrier.SetTerritoryVisibility(territoryId, True)
            if newTerritory:
                r, g, b = _TERRITORY_PALETTE[
                    (len(self._territory_order) - 1) % len(_TERRITORY_PALETTE)
                ]
                self._carrier.SetTerritoryColor(territoryId, r, g, b)
        self._rebuild()
        self.selectTerritoryRow(territoryId)
        self._armInto(territoryId)
        return territoryId

    def armForSelectedTerritory(self) -> None:
        """Re-arm placement into the selected row's territory ("Add seeds")."""
        territory = self._selectedTerritory()
        if not territory:
            return
        self._armInto(territory)

    def _selectedTerritory(self) -> str:
        """The selected row's territory (explicit selection wins over the row)."""
        if self._selected_territory:
            return self._selected_territory
        return self.territoryOfRow(self._table.currentRow)

    def done(self) -> None:
        """Disarm placement ("Done" / Esc) and hide the adhering highlight."""
        _state.set_armed(self._displayNode, False)
        if self._displayNode is not None and hasattr(self._displayNode, "SetVisibility"):
            self._displayNode.SetVisibility(False)

    def selectTerritoryRow(self, territoryId: str) -> None:
        """Select the header row of ``territoryId`` (a no-op if absent)."""
        self._selected_territory = territoryId
        for row, (territory, pointIndex) in enumerate(self._row_info):
            if pointIndex is None and territory == territoryId:
                self._table.setCurrentCell(row, _COL_LABEL)
                return

    def _armInto(self, territoryId: str) -> None:
        """Arm placement into ``territoryId`` via the shared display node.

        Writes the active territory + armed flag onto the highlight display
        node the LayerDM-driven Pipeline reads, and makes the node visible so
        the adhering highlight is live during placement (the retired place-mode
        visibility gate, re-homed to the arm state — ADR-0037 §Decision 2).
        """
        _state.set_active_territory(self._displayNode, territoryId)
        _state.set_armed(self._displayNode, True)
        if self._displayNode is not None and hasattr(self._displayNode, "SetVisibility"):
            self._displayNode.SetVisibility(True)

    def _mintTerritoryId(self) -> str:
        while True:
            self._mint_counter += 1
            candidate = f"Territory {self._mint_counter}"
            if candidate not in self._territory_order:
                return candidate

    # ------------------------------------------------------------------ #
    # Display + delete edits (write back to the carrier)
    # ------------------------------------------------------------------ #

    def setTerritoryVisibility(self, territoryId: str, visible: bool) -> None:
        if self._carrier is not None:
            self._carrier.SetTerritoryVisibility(territoryId, bool(visible))

    def setTerritoryColor(self, territoryId: str, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetTerritoryColor(territoryId, float(r), float(g), float(b))

    def setTerritoryLabel(self, territoryId: str, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetTerritoryLabel(territoryId, str(label))

    def deleteRow(self, row: int) -> None:
        """Delete-from-table entry point — converges on the shared removal path.

        Routes through ``_removePoint`` to the carrier's
        ``RemoveNthAnnotationPoint`` — the SAME carrier method the placement
        Pipeline's pick-delete reaches, so delete-by-row and delete-by-pick
        converge on one deletion path (ADR-0037 §Decision 3).
        """
        if self.isHeaderRow(row):
            return
        territory = self.territoryOfRow(row)
        pointIndex = self.pointIndexOfRow(row)
        if not territory or pointIndex is None:
            return
        self._removePoint(territory, pointIndex)

    # ------------------------------------------------------------------ #
    # Repaint
    # ------------------------------------------------------------------ #

    def _territories(self) -> list[str]:
        """The territories to render, in a stable order.

        Union of the first-seen minted order, the carrier's points-bearing
        territories, and its display-slot territories — so a points-bearing
        territory added outside the table (a pipeline click) still gets a
        header row, and an empty minted territory keeps its header row.
        """
        order = list(self._territory_order)
        seen = set(order)
        if self._carrier is not None:
            for territory in list(self._carrier.GetAnnotationTerritoryIds()) + list(
                self._carrier.GetDisplayTerritoryIds()
            ):
                if territory not in seen:
                    seen.add(territory)
                    order.append(territory)
        # Keep the local order list in sync so a later addTerritory sees them.
        self._territory_order = order
        return order

    def _rebuild(self) -> None:
        self._rebuilding = True
        try:
            self._table.blockSignals(True)
            self._table.setRowCount(0)
            self._row_info = []
            for territory in self._territories():
                self._appendHeaderRow(territory)
                count = (
                    self._carrier.GetNumberOfAnnotationPoints(territory)
                    if self._carrier is not None
                    else 0
                )
                for pointIndex in range(count):
                    self._appendChildRow(territory, pointIndex)
        finally:
            self._table.blockSignals(False)
            self._rebuilding = False

    def _appendHeaderRow(self, territoryId: str) -> None:
        row = self._table.rowCount
        self._table.insertRow(row)
        self._row_info.append((territoryId, None))

        seedCount = (
            self._carrier.GetNumberOfAnnotationPoints(territoryId)
            if self._carrier is not None
            else 0
        )
        visible = (
            bool(self._carrier.GetTerritoryVisibility(territoryId))
            if self._carrier is not None
            else True
        )
        label = ""
        color = (1.0, 1.0, 1.0)
        if self._carrier is not None:
            label = self._carrier.GetTerritoryLabel(territoryId) or territoryId
            rgb = self._carrier.GetTerritoryColor(territoryId)
            color = (rgb[0], rgb[1], rgb[2])

        # Visibility toggle.
        visibilityBox = qt.QCheckBox()
        visibilityBox.setChecked(visible)
        visibilityBox.connect(
            "toggled(bool)",
            lambda checked, t=territoryId: self.setTerritoryVisibility(t, checked),
        )
        self._table.setCellWidget(row, _COL_VISIBILITY, visibilityBox)

        # Colour swatch: the Slicer-idiomatic ``ctkColorPickerButton`` (the
        # segmentation / resection convention) -- it renders its own colour
        # square, opens the picker on click, and emits ``colorChanged``.
        # ``setColor`` BEFORE ``connect`` so seeding the initial colour does
        # not fire the write-back.
        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, t=territoryId: self.setTerritoryColor(
                t, c.redF(), c.greenF(), c.blueF()
            ),
        )
        self._table.setCellWidget(row, _COL_COLOUR, colourButton)

        # Editable label; header rows carry the territory id / point index on
        # the label item's data roles for the row-model readers.
        labelItem = qt.QTableWidgetItem(label)
        labelItem.setData(_ROLE_TERRITORY, territoryId)
        labelItem.setData(_ROLE_IS_HEADER, True)
        labelItem.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable | qt.Qt.ItemIsEditable)
        self._table.setItem(row, _COL_LABEL, labelItem)

        # Completeness indicator: GLYPH + TEXT (ADR-0010, never colour alone).
        incomplete = seedCount < _MIN_SEEDS_FOR_COMPLETE
        statusText = f"{_INCOMPLETE_GLYPH} {_INCOMPLETE_TEXT}" if incomplete else _COMPLETE_TEXT
        statusItem = qt.QTableWidgetItem(statusText)
        statusItem.setFlags(qt.Qt.ItemIsEnabled)
        self._table.setItem(row, _COL_STATUS, statusItem)

    def _appendChildRow(self, territoryId: str, pointIndex: int) -> None:
        row = self._table.rowCount
        self._table.insertRow(row)
        self._row_info.append((territoryId, pointIndex))

        # On-surface status text for the seed (surface-snapped on placement).
        statusItem = qt.QTableWidgetItem(f"Seed {pointIndex + 1} — on surface")
        statusItem.setData(_ROLE_TERRITORY, territoryId)
        statusItem.setData(_ROLE_POINT_INDEX, pointIndex)
        statusItem.setData(_ROLE_IS_HEADER, False)
        statusItem.setFlags(qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable)
        self._table.setItem(row, _COL_LABEL, statusItem)

        deleteButton = qt.QPushButton("Delete")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, t=territoryId, i=pointIndex: self._removePoint(t, i),
        )
        self._table.setCellWidget(row, _COL_STATUS, deleteButton)

    def _removePoint(self, territoryId: str, pointIndex: int) -> None:
        """The ONE point-removal path shared by delete-by-row + delete-by-cell.

        Calls the carrier's ``RemoveNthAnnotationPoint`` directly — the SAME
        carrier method the placement Pipeline's pick-delete
        (``DeleteAnnotationPoint``) reaches, so delete-by-row and
        delete-by-pick converge on one deletion path (ADR-0037 §Decision 3).
        """
        if self._carrier is not None:
            self._carrier.RemoveNthAnnotationPoint(territoryId, pointIndex)

    def _onItemChanged(self, item: Any) -> None:
        """Write an edited header label back to the carrier's display slot."""
        if item is None or self._rebuilding:
            return
        if not bool(item.data(_ROLE_IS_HEADER)):
            return
        territory = item.data(_ROLE_TERRITORY)
        if territory:
            self.setTerritoryLabel(territory, item.text())
