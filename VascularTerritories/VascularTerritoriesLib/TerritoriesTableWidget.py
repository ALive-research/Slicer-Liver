# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0037 Stage-2 — the VascularTerritories annotation tree widget.

ADR-0037 §Decision 3 replaces the legacy markups-selector / place-widget
panel with a Python-composed CUSTOM ``qt.QTreeWidget`` (ADR-0004): the
surface-snap + territory-grouping contract has no stock point-list fit (the
same call ADR-0034 made against ``qMRMLSegmentsTableView``).

Unlike the flat ADR-0034 segments table, territories have a genuine
parent/child structure — seed points nest under their territory — so the
panel composes a two-level ``qt.QTreeWidget`` (territories as TOP-LEVEL
items, seed points as CHILD items with a disclosure triangle + indentation)
rather than a flat ``qt.QTableWidget`` (§Decision 2 slice-4 amendment).

The tree is a VIEW over the Stage-1 annotation carrier
(``vtkMRMLCustomTerritoriesNode``): it OBSERVES the carrier's
``vtkCommand::ModifiedEvent`` and rebuilds, and its edits write BACK to the
carrier (geometry via the point carrier + the placement Pipeline's shared
removal path, display via the per-territory display slot).  The arm state
lives on the shared highlight DISPLAY NODE (``TerritoryInteractionState``,
not a Slicer mouse mode); "Add Territory" mints an empty territory + arms
into it, and a surface click through the pipeline seam appends one seed to
the ACTIVE territory.

The panel is a SINGLE-COLUMN, HEADER-LESS tree of composite row widgets
(ADR-0037 §Decision 2 slice-4 amendment): the column grid + header row are
dropped.  ``columnCount == 1`` and ``header().isHidden()``; each item —
territory top-level AND seed child — carries ONE composite ``QWidget`` on
column 0 (``tree.itemWidget(item, 0)``) whose ``QHBoxLayout`` holds the row's
controls as a horizontal STRIP, addressed by NAME (never by column index):

* TERRITORY (top-level) row widget, in order: a per-territory Place toggle
  (``qt.QToolButton``, checkable), an eye-icon visibility toggle
  (``qt.QToolButton``, checkable), a colour button (``ctk.ctkColorPickerButton``),
  an editable label (``qt.QLineEdit``, stretch), and a completeness status
  label (``qt.QLabel``) rendered as GLYPH + TEXT (ADR-0010, never colour
  alone) — display-only in Stage 2 (extraction gating is Stage 3).
* SEED (child) row widget: an on-surface status label (``qt.QLabel``,
  stretch) + a delete button (``qt.QToolButton``), nested under its
  territory's top-level item (the tree indentation conveys the hierarchy).

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

#: The single column the composite row widget lives on (ADR-0037 §Decision 2
#: slice-4 amendment): the column grid + header row are dropped, so every item
#: carries ONE composite ``QWidget`` on column 0.
_COMPOSITE_COLUMN = 0
_COLUMN_COUNT = 1

#: A territory needs at least this many seeds to be complete (a centerline
#: needs a start + an end); fewer reads incomplete (display-only, Stage 2).
_MIN_SEEDS_FOR_COMPLETE = 2

#: The incomplete indicator, rendered as GLYPH + TEXT (ADR-0010): the glyph
#: is a leading warning sign, the text spells the state out.
_INCOMPLETE_GLYPH = "⚠"  # WARNING SIGN
_INCOMPLETE_TEXT = "Incomplete — needs at least two seeds"
_COMPLETE_TEXT = "Ready"


class TerritoriesTableWidget(qt.QWidget):
    """Custom composite-row tree over the annotation carrier (ADR-0037).

    Composes a SINGLE-COLUMN, HEADER-LESS two-level ``qt.QTreeWidget`` —
    territories are TOP-LEVEL items, seed points CHILD items nested under
    them — where each item carries ONE composite ``QWidget`` (a horizontal
    STRIP of controls) on column 0.  Constructed over the Stage-1 carrier and
    the shared highlight display node:

        ``TerritoriesTableWidget(carrier=<vtkMRMLCustomTerritoriesNode>,
                                 displayNode=<vtkMRMLTerritoriesHighlightDisplayNode>)``.

    The carrier is the model.  Arm state / active territory are written onto
    the DISPLAY NODE (``TerritoryInteractionState``) — the shared handle the
    LayerDM-driven placement Pipeline reads at event time, since the widget
    cannot reach the manager-owned Pipeline instance directly.  Delete goes
    straight to the carrier (the same ``RemoveNthAnnotationPoint`` the
    Pipeline's pick-delete uses — one carrier method, ADR-0037 §Decision 3).

    Controls are addressed by NAME through the composite sub-widget getters
    (``placeButton`` / ``visibilityButton`` / ``colourButton`` /
    ``territoryLabelEdit`` / ``seedDeleteButton`` ...), never by column index —
    the columns no longer exist.
    """

    def __init__(self, carrier: Any = None, displayNode: Any = None, parent: Any = None) -> None:
        super().__init__(parent)

        self._carrier = carrier
        self._displayNode = displayNode
        # Bind the carrier onto the shared display node so the LayerDM-driven
        # placement Pipeline (which the widget cannot reach directly) resolves
        # the same carrier the tree edits.
        _state.set_carrier(displayNode, carrier)
        self._carrier_observer_tag: int | None = None
        # Guards against the write-back edits re-triggering a rebuild mid-edit.
        self._rebuilding = False
        # Deterministic territory order: minted / points-bearing / display
        # territories in first-seen order (so an EMPTY minted territory keeps
        # its top-level item).
        self._territory_order: list[str] = []
        # territoryId -> its top-level QTreeWidgetItem; rebuilt every repaint.
        self._territory_items: dict[str, Any] = {}
        # territoryId -> the composite row QWidget on the top-level item, and
        # the named controls parsed out of it (rebuilt every repaint).
        self._territory_rows: dict[str, dict[str, Any]] = {}
        # (territoryId, pointIndex) -> the seed composite row QWidget + its
        # named controls (rebuilt every repaint).
        self._seed_rows: dict[tuple[str, int], dict[str, Any]] = {}
        # Auto-mint counter for "Add Territory".
        self._mint_counter = 0
        # The territory the surgeon last selected (drives "Add seeds"); the
        # explicit selection survives an offscreen selection state.
        self._selected_territory: str = ""

        layout = qt.QVBoxLayout(self)

        # Single-column, header-less tree (ADR-0037 §Decision 2 slice-4
        # amendment): each item carries a composite row widget on column 0, so
        # there is no column grid and no header row.  The disclosure triangle
        # (setRootIsDecorated) stays so seeds expand/collapse under a territory.
        self._tree = qt.QTreeWidget()
        self._tree.setColumnCount(_COLUMN_COUNT)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._tree.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        layout.addWidget(self._tree)

        buttons = qt.QHBoxLayout()
        # ADR-0037 §Decision 2 slice-4: placement is an explicit per-territory
        # Place toggle in each territory row, so the "Add seeds" + "Done" panel
        # buttons retire; the shared disarm body survives as ``done()``.
        self._addTerritoryButton = qt.QPushButton("Add Territory")
        buttons.addWidget(self._addTerritoryButton)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._addTerritoryButton.connect("clicked(bool)", lambda _checked: self.addTerritory())

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
    # Item-model reader seams
    # ------------------------------------------------------------------ #

    def tree(self) -> Any:
        """The underlying ``qt.QTreeWidget``."""
        return self._tree

    def territoryIds(self) -> list[str]:
        """The territory ids of the top-level items, in display order.

        ``_territory_items`` is populated in top-level-item order during
        ``_rebuild`` (an insertion-ordered dict), so its keys are the display
        order.
        """
        return list(self._territory_items.keys())

    def territoryItem(self, territoryId: str) -> Any:
        """The top-level ``QTreeWidgetItem`` for ``territoryId`` (or ``None``)."""
        return self._territory_items.get(territoryId)

    def seedItems(self, territoryId: str) -> list[Any]:
        """The child ``QTreeWidgetItem`` list for ``territoryId``, in order."""
        parent = self._territory_items.get(territoryId)
        if parent is None:
            return []
        return [parent.child(j) for j in range(parent.childCount())]

    def territoryStatusText(self, territoryId: str) -> str:
        """The completeness status TEXT shown on the territory's row widget."""
        status = self._territoryControl(territoryId, "status")
        return status.text if status is not None else ""

    def territoryHasIncompleteGlyph(self, territoryId: str) -> bool:
        """Whether the territory carries the incomplete GLYPH (ADR-0010)."""
        return _INCOMPLETE_GLYPH in self.territoryStatusText(territoryId)

    # ------------------------------------------------------------------ #
    # Composite sub-widget getters (controls addressed by NAME, never column)
    # ------------------------------------------------------------------ #

    def _territoryControl(self, territoryId: str, key: str) -> Any:
        """The named control from a territory's composite row (or ``None``)."""
        row = self._territory_rows.get(territoryId)
        return row[key] if row is not None else None

    def _seedControl(self, territoryId: str, pointIndex: int, key: str) -> Any:
        """The named control from a seed's composite row (or ``None``)."""
        row = self._seed_rows.get((territoryId, int(pointIndex)))
        return row[key] if row is not None else None

    def territoryRowWidget(self, territoryId: str) -> Any:
        """The composite ``QWidget`` on the territory's top-level item (col 0)."""
        return self._territoryControl(territoryId, "widget")

    def placeButton(self, territoryId: str) -> Any:
        """The checkable Place ``qt.QToolButton`` on the territory row."""
        return self._territoryControl(territoryId, "place")

    def visibilityButton(self, territoryId: str) -> Any:
        """The checkable eye-icon ``qt.QToolButton`` on the territory row."""
        return self._territoryControl(territoryId, "visibility")

    def colourButton(self, territoryId: str) -> Any:
        """The ``ctk.ctkColorPickerButton`` on the territory row."""
        return self._territoryControl(territoryId, "colour")

    def territoryLabelEdit(self, territoryId: str) -> Any:
        """The editable label ``qt.QLineEdit`` on the territory row."""
        return self._territoryControl(territoryId, "label")

    def seedRowWidget(self, territoryId: str, pointIndex: int) -> Any:
        """The composite ``QWidget`` on the seed child item (col 0)."""
        return self._seedControl(territoryId, pointIndex, "widget")

    def seedDeleteButton(self, territoryId: str, pointIndex: int) -> Any:
        """The delete ``qt.QToolButton`` on the seed row."""
        return self._seedControl(territoryId, pointIndex, "delete")

    def seedStatusText(self, territoryId: str, pointIndex: int) -> str:
        """The on-surface status label text on the seed row."""
        status = self._seedControl(territoryId, pointIndex, "status")
        return status.text if status is not None else ""

    # ------------------------------------------------------------------ #
    # Territory lifecycle (arming)
    # ------------------------------------------------------------------ #

    def addTerritory(self, territoryId: str | None = None) -> str:
        """Mint an empty territory, select its item, arm the pipeline.

        Returns the (possibly auto-generated) territory id.  Auto-generated
        ids avoid colliding with an existing territory.
        """
        if territoryId is None:
            territoryId = self._mintTerritoryId()
        newTerritory = territoryId not in self._territory_order
        if newTerritory:
            self._territory_order.append(territoryId)
        # Give the territory a display slot so its top-level item survives
        # before any seed lands (an empty minted territory is enumerable), and
        # a distinct palette colour so it reads apart in the swatch + 3D seeds.
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

    def armForSelectedTerritory(self) -> None:
        """Re-arm placement into the selected territory (the "Add seeds" seam)."""
        if not self._selected_territory:
            return
        self._armInto(self._selected_territory)
        self._rebuild()

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
        """Select the top-level item of ``territoryId`` (a no-op if absent)."""
        self._selected_territory = territoryId
        item = self._territory_items.get(territoryId)
        if item is not None:
            self._tree.setCurrentItem(item)

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
        display node, so the other items un-check themselves.  Ignored while a
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

    def _onLabelEdited(self, territoryId: str, edit: Any) -> None:
        """Write an edited label ``QLineEdit`` back to the carrier's display slot.

        The composite-row replacement for the retired in-item editable text
        (ADR-0037 §Decision 3 slice-4): the ``QLineEdit``'s ``editingFinished``
        routes through ``setTerritoryLabel``.
        """
        if self._rebuilding:
            return
        self.setTerritoryLabel(territoryId, edit.text)

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

    def deleteSeed(self, territoryId: str, pointIndex: int) -> None:
        """Delete-from-tree entry point — converges on the shared removal path.

        Routes through ``_removePoint`` to the carrier's
        ``RemoveNthAnnotationPoint`` — the SAME carrier method the placement
        Pipeline's pick-delete (``DeleteAnnotationPoint``) reaches, so
        delete-by-seed and delete-by-pick converge on one deletion path
        (ADR-0037 §Decision 3).
        """
        if not territoryId or pointIndex is None:
            return
        self._removePoint(territoryId, int(pointIndex))

    # ------------------------------------------------------------------ #
    # Repaint
    # ------------------------------------------------------------------ #

    def _territories(self) -> list[str]:
        """The territories to render, in a stable order.

        Union of the first-seen minted order, the carrier's points-bearing
        territories, and its display-slot territories — so a points-bearing
        territory added outside the tree (a pipeline click) still gets a
        top-level item, and an empty minted territory keeps its top-level item.
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
            self._tree.clear()
            self._territory_items = {}
            self._territory_rows = {}
            self._seed_rows = {}
            for territory in self._territories():
                self._appendTerritoryItem(territory)
            self._tree.expandAll()
        finally:
            self._rebuilding = False

    def _appendTerritoryItem(self, territoryId: str) -> None:
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
        label = territoryId
        color = (1.0, 1.0, 1.0)
        if self._carrier is not None:
            label = self._carrier.GetTerritoryLabel(territoryId) or territoryId
            rgb = self._carrier.GetTerritoryColor(territoryId)
            color = (rgb[0], rgb[1], rgb[2])

        item = qt.QTreeWidgetItem(self._tree)
        self._territory_items[territoryId] = item

        rowWidget = self._buildTerritoryRow(territoryId, label, color, visible, seedCount)
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, rowWidget)

        for pointIndex in range(seedCount):
            self._appendSeedItem(item, territoryId, pointIndex)

    def _buildTerritoryRow(
        self,
        territoryId: str,
        label: str,
        color: tuple[float, float, float],
        visible: bool,
        seedCount: int,
    ) -> Any:
        """Compose a territory row's horizontal control STRIP (ADR-0037 slice-4).

        Order: Place toggle -> eye-icon visibility toggle -> colour button ->
        label QLineEdit (stretch) -> completeness status label.  Controls are
        registered by NAME in ``_territory_rows`` so the getters resolve them
        without any column index.
        """
        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        # Place toggle: a checkable button that arms placement into THIS
        # territory, exclusively.  Its checked state is RE-DERIVED from the
        # shared display node on every rebuild, never stored in a Python field,
        # so it survives the carrier-Modified rebuild.
        placeButton = qt.QToolButton()
        placeButton.setAutoRaise(True)
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
        rowLayout.addWidget(placeButton)

        # Visibility: a Slicer-idiomatic eye-on / eye-off ``QToolButton`` (the
        # segmentation convention, ADR-0037 §Decision 3 slice-4 UX polish), NOT
        # a bare QCheckBox.  Checked state is derived from the carrier.
        visibilityButton = qt.QToolButton()
        visibilityButton.setAutoRaise(True)
        visibilityButton.setCheckable(True)
        visibilityButton.setChecked(visible)
        self._applyEyeIcon(visibilityButton, visible)
        visibilityButton.connect(
            "toggled(bool)",
            lambda checked, t=territoryId, b=visibilityButton: self._onVisibilityToggled(t, b, checked),
        )
        rowLayout.addWidget(visibilityButton)

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
        rowLayout.addWidget(colourButton)

        # Editable label: a ``QLineEdit`` (the composite-row replacement for the
        # retired in-item editable text); ``editingFinished`` writes the
        # carrier's display slot.  It takes the row's slack (stretch=1).
        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.connect(
            "editingFinished()",
            lambda t=territoryId, e=labelEdit: self._onLabelEdited(t, e),
        )
        rowLayout.addWidget(labelEdit, 1)

        # Completeness indicator: GLYPH + TEXT (ADR-0010, never colour alone).
        incomplete = seedCount < _MIN_SEEDS_FOR_COMPLETE
        statusText = f"{_INCOMPLETE_GLYPH} {_INCOMPLETE_TEXT}" if incomplete else _COMPLETE_TEXT
        statusLabel = qt.QLabel(statusText)
        rowLayout.addWidget(statusLabel)

        self._territory_rows[territoryId] = {
            "widget": rowWidget,
            "place": placeButton,
            "visibility": visibilityButton,
            "colour": colourButton,
            "label": labelEdit,
            "status": statusLabel,
        }
        return rowWidget

    def _appendSeedItem(self, parentItem: Any, territoryId: str, pointIndex: int) -> None:
        child = qt.QTreeWidgetItem(parentItem)
        rowWidget = self._buildSeedRow(territoryId, pointIndex)
        self._tree.setItemWidget(child, _COMPOSITE_COLUMN, rowWidget)

    def _buildSeedRow(self, territoryId: str, pointIndex: int) -> Any:
        """Compose a seed row's horizontal control STRIP (ADR-0037 slice-4).

        Order: on-surface status label (stretch) -> delete ``QToolButton``.
        The tree indentation under the territory item conveys the hierarchy.
        """
        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        # On-surface status text (surface-snapped on placement).
        statusLabel = qt.QLabel(f"Seed {pointIndex + 1} — on surface")
        rowLayout.addWidget(statusLabel, 1)

        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Delete")
        deleteButton.setToolTip("Remove this seed")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, t=territoryId, i=pointIndex: self._removePoint(t, i),
        )
        rowLayout.addWidget(deleteButton)

        self._seed_rows[(territoryId, pointIndex)] = {
            "widget": rowWidget,
            "status": statusLabel,
            "delete": deleteButton,
        }
        return rowWidget

    def _removePoint(self, territoryId: str, pointIndex: int) -> None:
        """The ONE point-removal path shared by delete-by-seed + delete-by-pick.

        Calls the carrier's ``RemoveNthAnnotationPoint`` directly — the SAME
        carrier method the placement Pipeline's pick-delete
        (``DeleteAnnotationPoint``) reaches, so delete-by-seed and
        delete-by-pick converge on one deletion path (ADR-0037 §Decision 3).
        """
        if self._carrier is not None:
            self._carrier.RemoveNthAnnotationPoint(territoryId, pointIndex)
