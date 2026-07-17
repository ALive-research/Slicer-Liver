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

#: Column layout of the custom table (ADR-0037 §Decision 2 slice-4 amendment).
#: A leftmost per-territory Place toggle drives explicit, exclusive arming.  A
#: HEADER row uses columns as [place | visibility | colour | label | status]; a
#: CHILD row uses [<blank> | <blank> | <blank> | status text | delete].
_COL_PLACE = 0
_COL_VISIBILITY = 1
_COL_COLOUR = 2
_COL_LABEL = 3
_COL_STATUS = 4
_COLUMN_COUNT = 5

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
        self._table.setHorizontalHeaderLabels(
            ["Place", "Visible", "Colour", "Territory / label", "Status"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        layout.addWidget(self._table)

        buttons = qt.QHBoxLayout()
        # ADR-0037 §Decision 2 slice-4: placement is an explicit per-territory
        # Place toggle in the leftmost column, so the "Add seeds" + "Done" panel
        # buttons retire; the shared disarm body survives as ``done()``.
        self._addTerritoryButton = qt.QPushButton("Add Territory")
        buttons.addWidget(self._addTerritoryButton)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._addTerritoryButton.connect("clicked(bool)", lambda _checked: self.addTerritory())
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
        # Arm BEFORE the rebuild so the minted territory's Place toggle
        # re-derives as checked (the checked state is display-node-derived, not
        # stored — ADR-0037 §Decision 2 slice-4).  Arming is exclusive, so any
        # previously-armed territory's toggle re-derives un-checked.
        self._armInto(territoryId)
        self._rebuild()
        self.selectTerritoryRow(territoryId)
        return territoryId

    def done(self) -> None:
        """The shared disarm body: clear the arm state + hide the highlight.

        The single disarm path reused by a Place toggle switching OFF and by
        the widget's ``exit()`` module-active gate (ADR-0037 §Decision 2
        slice-4).  Idempotent.
        """
        _state.set_armed(self._displayNode, False)
        if self._displayNode is not None and hasattr(self._displayNode, "SetVisibility"):
            self._displayNode.SetVisibility(False)

    def disarm(self) -> None:
        """Disarm + refresh the toggles (the widget's module-active gate seam).

        The public entry the widget's ``exit()`` calls: the shared ``done()``
        body plus a rebuild so every Place toggle re-derives un-checked
        (ADR-0037 §Decision 2 slice-4).  The toggle-OFF path drives ``done()``
        + its own rebuild directly, so it does not go through here.
        """
        self.done()
        self._rebuild()

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

    def _onPlaceToggled(self, territoryId: str, checked: bool) -> None:
        """Handle a per-territory Place toggle (ADR-0037 §Decision 2 slice-4).

        Toggling ON arms placement into ``territoryId`` EXCLUSIVELY (one armed
        at a time); toggling OFF disarms via the shared ``done()`` body.  The
        follow-up rebuild re-derives every Place toggle's checked state from the
        display node, so the other rows un-check themselves.  Ignored while a
        rebuild is programmatically setting the derived checked state (the
        ``_rebuilding`` guard) so re-deriving does not recursively re-arm.
        """
        if self._rebuilding:
            return
        if checked:
            self._armInto(territoryId)
        else:
            self.done()
        self._rebuild()

    def _onVisibilityToggled(self, territoryId: str, button: Any, checked: bool) -> None:
        """Flip the carrier's per-territory visibility + swap the eye icon."""
        if self._rebuilding:
            return
        self.setTerritoryVisibility(territoryId, checked)
        self._applyEyeIcon(button, checked)

    def _applyEyeIcon(self, button: Any, visible: bool) -> None:
        """Paint the eye-on / eye-off affordance on a visibility toggle.

        Prefers Slicer's stock segmentation eye icons; falls back to a glyph so
        the toggle stays usable when the resource is unavailable.
        """
        iconPath = ":/Icons/Small/SlicerVisible.png" if visible else ":/Icons/Small/SlicerInvisible.png"
        icon = qt.QIcon(iconPath)
        if icon.isNull():
            button.setIcon(qt.QIcon())
            button.setText("👁" if visible else "—")
        else:
            button.setText("")
            button.setIcon(icon)

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

        # Place toggle (ADR-0037 §Decision 2 slice-4): a checkable button that
        # arms placement into THIS territory, exclusively.  Its checked state is
        # RE-DERIVED from the shared display node on every rebuild, never stored
        # in a Python field, so it survives the carrier-Modified rebuild.
        placeButton = qt.QToolButton()
        placeButton.setCheckable(True)
        placeButton.setText("Place")
        placeButton.setToolTip("Arm placement into this territory (exclusive)")
        placeButton.setChecked(
            _state.is_armed(self._displayNode)
            and _state.get_active_territory(self._displayNode) == territoryId
        )
        placeButton.connect(
            "toggled(bool)",
            lambda checked, t=territoryId: self._onPlaceToggled(t, checked),
        )
        self._table.setCellWidget(row, _COL_PLACE, placeButton)

        # Visibility: a Slicer-idiomatic eye-on / eye-off ``QToolButton`` (the
        # segmentation convention, ADR-0037 §Decision 3 slice-4 UX polish), NOT
        # a bare QCheckBox.  Checked state is derived from the carrier.
        visibilityButton = qt.QToolButton()
        visibilityButton.setCheckable(True)
        visibilityButton.setChecked(visible)
        self._applyEyeIcon(visibilityButton, visible)
        visibilityButton.connect(
            "toggled(bool)",
            lambda checked, t=territoryId, b=visibilityButton: self._onVisibilityToggled(t, b, checked),
        )
        self._table.setCellWidget(row, _COL_VISIBILITY, visibilityButton)

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
