# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the per-VOLUME LiverVolumetry seeds table.

A carrier-backed table over the grouped ``vtkMRMLVolumetrySeedsNode`` seed
carrier, the volumetry sibling of the VascularTerritories
``TerritoriesTableWidget``.  Where the territory table nests seed points under
their surgeon-named TERRITORY, this table nests region-growing seeds under their
surgeon-named VOLUME: the surgeon adds a named volume, arms placement into the
ACTIVE volume (a per-volume Place toggle publishing the active volume onto the
shared display node), and placed seeds nest under that volume.

It is a Python-composed ``qt.QWidget`` (ADR-0004) that OWNS a two-level
``qt.QTreeWidget`` (VOLUMES top-level, seeds child rows), mirroring the
territory tree.  The prior FLAT per-seed table (ADR-0038) is subsumed: seed rows
keep every per-seed control, and the per-SEED getters stay keyed by the seed's
GLOBAL placement INDEX (``labelEdit`` / ``colourButton`` / ``targetCombo`` /
``deleteButton`` / ``setSeedColor`` / ``setSeedLabel`` / ``deleteSeed`` /
``retargetSeed``), so the existing seed→segment binding + Target-combo contract
is preserved on top of the grouping.

Each VOLUME (top-level) row carries a horizontal strip, addressed by NAME:

* a per-volume Place toggle (``qt.QToolButton``, checkable) that arms placement
  into THIS volume exclusively (publishes the active volume + armed flag onto
  the shared display node via the base ``PointPlacementState``);
* a COLOUR swatch (``ctk.ctkColorPickerButton``) writing ``SetVolumeColor``;
* an editable LABEL (``qt.QLineEdit``) writing ``SetVolumeLabel``;
* a DELETE (``qt.QToolButton``) removing the whole volume via ``RemoveVolume``.

Each SEED (child) row carries the strip the flat table used: a COLOUR swatch, an
editable LABEL (the generated segment name, ADR-0038 §Conformance), a TARGET
combo (the seed→segment binding + retarget, ``territory-usability`` §"Seed→label
capture"), and a DELETE button.  A small ``qt.QTimer`` fades the bound segment's
2D fill on placement / row-selection as a confirmation ON TOP of the named
target (ADR-0010, never colour/animation alone).

CARRIER IS THE MODEL.  The table reads/writes the carrier and OBSERVES its
``vtkCommand::ModifiedEvent`` to rebuild.  ``cleanup()`` detaches the observer +
stops the fade so a parentless widget does not survive to app shutdown holding a
MRML observer (``feedback_launched_widget_teardown_crash``).

The arm state / active volume ride the shared ``vtkMRMLVolumetrySeedsDisplayNode``
(not a Python pipeline instance LayerDM does not drive,
``feedback_layerdm_state_on_display_node``) via the base ``PointPlacementState``
``LiverVolumetry.*`` channel -- the SAME channel the slice pipeline reads at
placement time (``_assign_active_volume``).

See also:
  * VascularTerritories/VascularTerritoriesLib/TerritoriesTableWidget.py -- the
    two-level tree idiom this mirrors.
  * Docs/adr/0038 -- the seeds-off-markups migration + §Conformance.
  * Docs/adr/0014-*.md §"Fourth layer" -- a display edit must not touch geometry.
  * Docs/adr/0010-accessibility-and-i18n.md -- glyph/text pairing.
  * Docs/adr/0004-*.md -- panels are Python.
"""

from __future__ import annotations

from typing import Any

import ctk
import qt
import vtk

try:  # pragma: no cover - exercised once per import path
    from .SeedTargetResolution import (
        gather_touched_candidates,
        resolve_touched_candidates,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from SeedTargetResolution import (  # type: ignore[no-redef]
        gather_touched_candidates,
        resolve_touched_candidates,
    )

# The arm / active-volume state rides the shared display node via the base's
# PointPlacementState (the LiverVolumetry.* channel the slice pipeline reads at
# placement time).  Import the same dual-path idiom the placement module uses.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

#: The base namespace for the volumetry arm/active-volume state on the shared
#: display node (matches the placement pipeline's ``VOLUMETRY_NAMESPACE``).
VOLUMETRY_NAMESPACE = "LiverVolumetry"

#: The seed / volume default display colour (opaque white), mirroring the
#: carrier's own out-of-range default.
_DEFAULT_SEED_COLOR = (1.0, 1.0, 1.0)

#: A small distinct palette so minted volumes read apart in the swatch (RGB in
#: 0..1).  Cycled by mint order, mirroring the territory palette.
_VOLUME_PALETTE = (
    (0.90, 0.30, 0.24),  # red
    (0.20, 0.60, 0.86),  # blue
    (0.18, 0.80, 0.44),  # green
    (0.95, 0.77, 0.06),  # amber
    (0.61, 0.35, 0.71),  # purple
    (0.90, 0.49, 0.13),  # orange
)

#: The fade pulse: how many in/out cycles, and the per-step timer interval (ms).
_FADE_STEPS = 12
_FADE_INTERVAL_MS = 60
_FADE_MIN_OPACITY = 0.15
_FADE_MAX_OPACITY = 1.0

#: The single column the composite row widget lives on (mirrors the territory
#: tree slice-4 amendment): a header-less tree, one composite QWidget per item.
_COMPOSITE_COLUMN = 0
_COLUMN_COUNT = 1


class VolumetrySeedsTableWidget(qt.QWidget):
    """Per-volume carrier-backed tree over ``vtkMRMLVolumetrySeedsNode``.

    Constructed over the seed carrier + (optionally) the shared display node::

        VolumetrySeedsTableWidget(carrier=<vtkMRMLVolumetrySeedsNode>,
                                  displayNode=<vtkMRMLVolumetrySeedsDisplayNode>)

    Volumes are top-level rows; seeds nest under their volume.  Per-seed getters
    stay keyed by the seed's global placement index; volume-level getters take
    the volume id.
    """

    def __init__(self, carrier: Any = None, displayNode: Any = None, parent: Any = None) -> None:
        super().__init__(parent)

        self._carrier = carrier
        self._displayNode = displayNode
        self._carrier_observer_tag: int | None = None
        # Guards against the write-back edits re-triggering a rebuild mid-edit.
        self._rebuilding = False
        # The structure-source segmentation the retarget menu recomputes touched
        # candidates against; bound by the module widget via setStructureSource.
        self._structureSource: Any = None
        # The index of the last seed we fired a placement-fade for.
        self._lastFadedSeed = -1
        # Deterministic volume order: minted / seed-bearing / display volumes in
        # first-seen order (so an EMPTY minted volume keeps its top-level row).
        self._volume_order: list[str] = []
        # volumeId -> its top-level QTreeWidgetItem + named controls; rebuilt.
        self._volume_items: dict[str, Any] = {}
        self._volume_rows: dict[str, dict[str, Any]] = {}
        # global seed index -> the seed composite row's named controls; rebuilt.
        self._seed_rows: dict[int, dict[str, Any]] = {}
        # Auto-mint counter for "Add volume".
        self._mint_counter = 0

        # The fade-pulse machinery (as in the flat table).
        self._fadeTimer = qt.QTimer(self)
        self._fadeTimer.setInterval(_FADE_INTERVAL_MS)
        self._fadeTimer.connect("timeout()", self._onFadeStep)
        self._fadeStep = 0
        self._fadeDisplayNode: Any = None
        self._fadeSegmentID: str = ""
        self._fadeRestoreOpacity = 1.0

        layout = qt.QVBoxLayout(self)

        # Single-column, header-less two-level tree (volumes -> seeds).
        self._tree = qt.QTreeWidget()
        self._tree.setColumnCount(_COLUMN_COUNT)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._tree.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self._tree.connect("itemSelectionChanged()", self._onRowSelectionChanged)
        layout.addWidget(self._tree)

        buttons = qt.QHBoxLayout()
        self._addVolumeButton = qt.QPushButton("Add volume")
        self._addVolumeButton.setToolTip("Add a named volume, then place seeds into it")
        buttons.addWidget(self._addVolumeButton)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._addVolumeButton.connect("clicked(bool)", lambda _checked: self.addVolume())

        self._attachCarrierObserver()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Drop the carrier observer + stop the fade timer (test teardown fixture)."""
        self._stopFade(restore=True)
        self._detachCarrierObserver()

    def setStructureSource(self, segmentationNode: Any) -> None:
        """Bind the structure-source segmentation the retarget menu scans."""
        self._structureSource = segmentationNode
        self._rebuild()

    def setCarrier(self, carrier: Any) -> None:
        """Rebind the table to ``carrier`` (drops the prior observer, rebuilds)."""
        if carrier is self._carrier:
            return
        self._detachCarrierObserver()
        self._carrier = carrier
        self._attachCarrierObserver()
        self._rebuild()

    def setDisplayNode(self, displayNode: Any) -> None:
        """Bind the shared display node the arm / active-volume state rides.

        The per-volume Place toggle publishes the active volume + armed flag onto
        THIS node via the base ``PointPlacementState``; the LayerDM-created slice
        pipeline reads them at placement time (``_assign_active_volume``).
        """
        self._displayNode = displayNode
        self._rebuild()

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
        newest = self._seedCount() - 1
        newlyBound = newest >= 0 and bool(self._seedBindingSegmentID(newest)) and newest != self._lastFadedSeed
        self._rebuild()
        if newlyBound:
            self._lastFadedSeed = newest
            self._fadeSeedBinding(newest)

    # ------------------------------------------------------------------ #
    # Item-model reader seams
    # ------------------------------------------------------------------ #

    def tree(self) -> Any:
        """The underlying ``qt.QTreeWidget``."""
        return self._tree

    def table(self) -> Any:
        """Back-compat alias for the underlying tree (the flat table's seam)."""
        return self._tree

    def rowCount(self) -> int:
        """The number of SEED rows currently rendered (one per carrier seed)."""
        return self._seedCount()

    def volumeIds(self) -> list[str]:
        """The volume ids of the top-level items, in display order."""
        return list(self._volume_items.keys())

    def volumeItem(self, volumeId: str) -> Any:
        """The top-level ``QTreeWidgetItem`` for ``volumeId`` (or ``None``)."""
        return self._volume_items.get(volumeId)

    def seedIndicesForVolume(self, volumeId: str) -> list[int]:
        """The GLOBAL seed indices assigned to ``volumeId``, in placement order."""
        if self._carrier is None:
            return []
        return [
            i
            for i in range(self._carrier.GetNumberOfSeeds())
            if self._carrier.GetNthSeedVolume(i) == volumeId
        ]

    # -- per-volume control getters (by volume id) --------------------- #

    def _volumeControl(self, volumeId: str, key: str) -> Any:
        row = self._volume_rows.get(volumeId)
        return row[key] if row is not None else None

    def placeButton(self, volumeId: str) -> Any:
        """The checkable Place ``qt.QToolButton`` on the volume row."""
        return self._volumeControl(volumeId, "place")

    def volumeColourButton(self, volumeId: str) -> Any:
        """The ``ctk.ctkColorPickerButton`` on the volume row."""
        return self._volumeControl(volumeId, "colour")

    def volumeLabelEdit(self, volumeId: str) -> Any:
        """The editable label ``qt.QLineEdit`` on the volume row."""
        return self._volumeControl(volumeId, "label")

    def volumeDeleteButton(self, volumeId: str) -> Any:
        """The delete ``qt.QToolButton`` on the volume row."""
        return self._volumeControl(volumeId, "delete")

    # -- per-seed control getters (by GLOBAL index; flat-table contract) - #

    def _seedControl(self, seedIndex: int, key: str) -> Any:
        row = self._seed_rows.get(int(seedIndex))
        return row[key] if row is not None else None

    def colourButton(self, seedIndex: int) -> Any:
        """The seed row's ``ctk.ctkColorPickerButton`` (keyed by global index)."""
        return self._seedControl(seedIndex, "colour")

    def labelEdit(self, seedIndex: int) -> Any:
        """The seed row's editable label ``qt.QLineEdit`` (keyed by global index)."""
        return self._seedControl(seedIndex, "label")

    def targetCombo(self, seedIndex: int) -> Any:
        """The seed row's retarget ``qt.QComboBox`` (keyed by global index)."""
        return self._seedControl(seedIndex, "target")

    def deleteButton(self, seedIndex: int) -> Any:
        """The seed row's delete ``qt.QToolButton`` (keyed by global index)."""
        return self._seedControl(seedIndex, "delete")

    # ------------------------------------------------------------------ #
    # Volume lifecycle (add / arm / delete)
    # ------------------------------------------------------------------ #

    def addVolume(self, volumeId: str | None = None) -> str:
        """Mint a volume and arm placement into it (the active-volume seam).

        Returns the (possibly auto-generated) volume id.  Registers a carrier
        display slot so the empty volume's top-level row survives before a seed
        lands, gives it a distinct palette colour, and arms placement into it via
        the shared display node.
        """
        if volumeId is None:
            volumeId = self._mintVolumeId()
        newVolume = volumeId not in self._volume_order
        if newVolume:
            self._volume_order.append(volumeId)
        if self._carrier is not None:
            self._carrier.AddVolume(volumeId)
            if newVolume:
                r, g, b = _VOLUME_PALETTE[
                    (len(self._volume_order) - 1) % len(_VOLUME_PALETTE)
                ]
                self._carrier.SetVolumeColor(volumeId, r, g, b)
        self._armInto(volumeId)
        self._rebuild()
        return volumeId

    def deleteVolume(self, volumeId: str) -> None:
        """Remove a whole volume (its seeds + display slot) via the carrier.

        If the removed volume was the display node's ACTIVE (armed) volume, the
        arm state is cleared first so placement does not target a gone volume.
        """
        if not volumeId or self._carrier is None:
            return
        if self._activeVolume() == volumeId:
            self._disarm()
        self._volume_order = [v for v in self._volume_order if v != volumeId]
        self._carrier.RemoveVolume(volumeId)

    def _mintVolumeId(self) -> str:
        while True:
            self._mint_counter += 1
            candidate = f"Volume {self._mint_counter}"
            if candidate not in self._volume_order and (
                self._carrier is None or candidate not in list(self._carrier.GetVolumeIds())
            ):
                return candidate

    # -- arm state on the shared display node -------------------------- #

    def _state(self) -> Any:
        return PointPlacementState(VOLUMETRY_NAMESPACE)

    def _activeVolume(self) -> str:
        if self._displayNode is None:
            return ""
        return self._state().get_active(self._displayNode) or ""

    def _isArmedInto(self, volumeId: str) -> bool:
        state = self._state()
        return (
            self._displayNode is not None
            and state.is_armed(self._displayNode)
            and state.get_active(self._displayNode) == volumeId
        )

    def _armInto(self, volumeId: str) -> None:
        """Arm placement into ``volumeId`` via the shared display node."""
        if self._displayNode is None:
            return
        state = self._state()
        state.set_active(self._displayNode, volumeId)
        state.set_armed(self._displayNode, True)

    def _disarm(self) -> None:
        if self._displayNode is None:
            return
        self._state().set_armed(self._displayNode, False)

    def _onPlaceToggled(self, volumeId: str, checked: bool) -> None:
        """Arm into ``volumeId`` exclusively on ON; disarm on OFF."""
        if self._rebuilding:
            return
        if checked:
            self._armInto(volumeId)
        else:
            self._disarm()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Edits (write back to the carrier)
    # ------------------------------------------------------------------ #

    def setVolumeColor(self, volumeId: str, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetVolumeColor(volumeId, float(r), float(g), float(b))

    def setVolumeLabel(self, volumeId: str, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetVolumeLabel(volumeId, str(label))

    def setSeedColor(self, seedIndex: int, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedColor(int(seedIndex), float(r), float(g), float(b))

    def setSeedLabel(self, seedIndex: int, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedLabel(int(seedIndex), str(label))

    def deleteSeed(self, seedIndex: int) -> None:
        """Remove the seed at ``seedIndex`` via the carrier's ``RemoveNthSeed``."""
        if self._carrier is not None:
            self._carrier.RemoveNthSeed(int(seedIndex))

    def retargetSeed(self, seedIndex: int, segmentID: str) -> None:
        """Rebind the seed at ``seedIndex`` to ``segmentID`` + re-fade + re-name."""
        if self._carrier is None or not segmentID:
            return
        source = self._structureSource
        if source is None:
            return
        self._carrier.SetNthSeedBinding(seedIndex, source.GetID(), segmentID)
        segment = source.GetSegmentation().GetSegment(segmentID)
        if segment is not None:
            self.setSeedLabel(seedIndex, segment.GetName())
        self._fadeSeedBinding(seedIndex)

    def _onVolumeLabelEdited(self, volumeId: str, edit: Any) -> None:
        if self._rebuilding:
            return
        self.setVolumeLabel(volumeId, edit.text)

    def _onVolumeColourChanged(self, volumeId: str, colour: Any) -> None:
        if self._rebuilding:
            return
        self.setVolumeColor(volumeId, colour.redF(), colour.greenF(), colour.blueF())

    def _onLabelEdited(self, seedIndex: int, edit: Any) -> None:
        if self._rebuilding:
            return
        self.setSeedLabel(seedIndex, edit.text)

    def _onColourChanged(self, seedIndex: int, colour: Any) -> None:
        if self._rebuilding:
            return
        self.setSeedColor(seedIndex, colour.redF(), colour.greenF(), colour.blueF())

    def _onTargetChanged(self, seedIndex: int, combo: Any) -> None:
        if self._rebuilding:
            return
        segmentID = combo.itemData(combo.currentIndex)
        if segmentID:
            self.retargetSeed(seedIndex, str(segmentID))

    def _onRowSelectionChanged(self) -> None:
        """Re-fade the selected seed's bound segment (confirmation on demand)."""
        if self._rebuilding:
            return
        items = self._tree.selectedItems()
        if not items:
            return
        seedIndex = items[0].data(0, qt.Qt.UserRole)
        if seedIndex is not None:
            self._fadeSeedBinding(int(seedIndex))

    # ------------------------------------------------------------------ #
    # Repaint
    # ------------------------------------------------------------------ #

    def _seedCount(self) -> int:
        if self._carrier is None:
            return 0
        return self._carrier.GetNumberOfSeeds()

    def _volumes(self) -> list[str]:
        """The volumes to render, in a stable first-seen order.

        Union of the local minted order and the carrier's enumerated volumes
        (seed-bearing + display-slot), so a volume added outside the table (a
        pipeline click into a fresh volume) still gets a top-level row and an
        empty minted volume keeps its row.
        """
        order = list(self._volume_order)
        seen = set(order)
        if self._carrier is not None:
            for volumeId in self._carrier.GetVolumeIds():
                if volumeId not in seen:
                    seen.add(volumeId)
                    order.append(volumeId)
        self._volume_order = order
        return order

    def _rebuild(self) -> None:
        self._rebuilding = True
        try:
            self._tree.clear()
            self._volume_items = {}
            self._volume_rows = {}
            self._seed_rows = {}
            # Seeds grouped by volume; ungrouped seeds ride a synthetic
            # "Ungrouped" bucket so a legacy / pre-volume seed still shows.
            grouped: dict[str, list[int]] = {}
            ungrouped: list[int] = []
            for i in range(self._seedCount()):
                volumeId = self._carrier.GetNthSeedVolume(i)
                if volumeId:
                    grouped.setdefault(volumeId, []).append(i)
                else:
                    ungrouped.append(i)
            for volumeId in self._volumes():
                self._appendVolumeItem(volumeId, grouped.get(volumeId, []))
            if ungrouped:
                self._appendUngroupedSeeds(ungrouped)
            self._tree.expandAll()
            if self._lastFadedSeed >= self._seedCount():
                self._lastFadedSeed = -1
        finally:
            self._rebuilding = False

    def _appendVolumeItem(self, volumeId: str, seedIndices: list[int]) -> None:
        item = qt.QTreeWidgetItem(self._tree)
        self._volume_items[volumeId] = item
        rowWidget = self._buildVolumeRow(volumeId)
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, rowWidget)
        for seedIndex in seedIndices:
            self._appendSeedItem(item, seedIndex)

    def _appendUngroupedSeeds(self, seedIndices: list[int]) -> None:
        item = qt.QTreeWidgetItem(self._tree)
        label = qt.QLabel("Ungrouped seeds")
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, label)
        for seedIndex in seedIndices:
            self._appendSeedItem(item, seedIndex)

    def _buildVolumeRow(self, volumeId: str) -> Any:
        """Compose a volume row's horizontal control strip: Place / colour /
        label / delete (ADR-0010 glyph + text)."""
        color = _DEFAULT_SEED_COLOR
        label = volumeId
        if self._carrier is not None:
            rgb = self._carrier.GetVolumeColor(volumeId)
            color = (rgb[0], rgb[1], rgb[2])
            label = self._carrier.GetVolumeLabel(volumeId) or volumeId

        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        placeButton = qt.QToolButton()
        placeButton.setAutoRaise(True)
        placeButton.setCheckable(True)
        placeButton.setText("Place")
        placeButton.setToolTip("Arm placement into this volume (exclusive)")
        placeButton.setChecked(self._isArmedInto(volumeId))
        placeButton.connect(
            "toggled(bool)",
            lambda checked, v=volumeId: self._onPlaceToggled(v, checked),
        )
        rowLayout.addWidget(placeButton)

        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.setToolTip(f"{label} colour")
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, v=volumeId: self._onVolumeColourChanged(v, c),
        )
        rowLayout.addWidget(colourButton)

        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.setPlaceholderText(volumeId)
        labelEdit.setToolTip("Label for this volume")
        labelEdit.connect(
            "editingFinished()",
            lambda v=volumeId, e=labelEdit: self._onVolumeLabelEdited(v, e),
        )
        rowLayout.addWidget(labelEdit, 1)

        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Remove")
        deleteButton.setToolTip("Remove this volume and its seeds")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, v=volumeId: self.deleteVolume(v),
        )
        rowLayout.addWidget(deleteButton)

        self._volume_rows[volumeId] = {
            "widget": rowWidget,
            "place": placeButton,
            "colour": colourButton,
            "label": labelEdit,
            "delete": deleteButton,
        }
        return rowWidget

    def _appendSeedItem(self, parentItem: Any, seedIndex: int) -> None:
        child = qt.QTreeWidgetItem(parentItem)
        # Carry the global seed index on the item so row-selection can re-fade.
        child.setData(0, qt.Qt.UserRole, seedIndex)
        rowWidget = self._buildSeedRow(seedIndex)
        self._tree.setItemWidget(child, _COMPOSITE_COLUMN, rowWidget)

    def _seedColor(self, seedIndex: int) -> tuple[float, float, float]:
        if self._carrier is None:
            return _DEFAULT_SEED_COLOR
        rgb = self._carrier.GetNthSeedColor(seedIndex)
        return (rgb[0], rgb[1], rgb[2])

    def _seedLabel(self, seedIndex: int) -> str:
        if self._carrier is None:
            return ""
        return self._carrier.GetNthSeedLabel(seedIndex)

    def _buildSeedRow(self, seedIndex: int) -> Any:
        """Compose one seed row: colour swatch, label, target combo, delete."""
        color = self._seedColor(seedIndex)
        label = self._seedLabel(seedIndex)

        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.setToolTip(f"Seed {seedIndex + 1} colour")
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, i=seedIndex: self._onColourChanged(i, c),
        )
        rowLayout.addWidget(colourButton)

        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.setPlaceholderText(f"Seed {seedIndex + 1} label")
        labelEdit.setToolTip("Label for this seed (becomes the generated segment name)")
        labelEdit.connect(
            "editingFinished()",
            lambda i=seedIndex, e=labelEdit: self._onLabelEdited(i, e),
        )
        rowLayout.addWidget(labelEdit, 1)

        targetCombo = self._buildTargetCombo(seedIndex)
        rowLayout.addWidget(targetCombo)

        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Delete")
        deleteButton.setToolTip("Remove this seed")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, i=seedIndex: self.deleteSeed(i),
        )
        rowLayout.addWidget(deleteButton)

        self._seed_rows[seedIndex] = {
            "widget": rowWidget,
            "colour": colourButton,
            "label": labelEdit,
            "target": targetCombo,
            "delete": deleteButton,
        }
        return rowWidget

    def _buildTargetCombo(self, seedIndex: int) -> Any:
        """Compose the row's retarget combo: the touched candidates, top-first."""
        combo = qt.QComboBox()
        combo.setToolTip("The structure this seed is bound to (pick another to retarget)")
        boundSegmentID = self._seedBindingSegmentID(seedIndex)
        candidates = self._touchedCandidates(seedIndex)
        if boundSegmentID and boundSegmentID not in candidates:
            candidates = [boundSegmentID] + candidates
        selected = 0
        for i, segmentID in enumerate(candidates):
            combo.addItem(self._segmentName(segmentID) or segmentID, segmentID)
            if segmentID == boundSegmentID:
                selected = i
        if candidates:
            combo.setCurrentIndex(selected)
        else:
            combo.addItem("Unbound", "")
            combo.setEnabled(False)
        combo.connect(
            "activated(int)",
            lambda _idx, i=seedIndex, c=combo: self._onTargetChanged(i, c),
        )
        return combo

    # ------------------------------------------------------------------ #
    # Binding + candidate readers (the target column's model)
    # ------------------------------------------------------------------ #

    def _seedBindingSegmentID(self, seedIndex: int) -> str:
        if self._carrier is None or not hasattr(self._carrier, "GetNthSeedBindingSegmentID"):
            return ""
        return self._carrier.GetNthSeedBindingSegmentID(seedIndex)

    def _touchedCandidates(self, seedIndex: int) -> list[str]:
        source = self._structureSource
        if source is None or self._carrier is None:
            return []
        coord = self._carrier.GetNthSeed(seedIndex)
        ras = (float(coord[0]), float(coord[1]), float(coord[2]))
        touched = gather_touched_candidates(source, source.GetDisplayNode(), ras)
        ordered, _top = resolve_touched_candidates(touched)
        return ordered

    def _segmentName(self, segmentID: str) -> str:
        source = self._structureSource
        if source is None or not segmentID:
            return ""
        segment = source.GetSegmentation().GetSegment(segmentID)
        return segment.GetName() if segment is not None else ""

    # ------------------------------------------------------------------ #
    # Fade pulse (the caught-structure confirmation; no named Slicer fade API)
    # ------------------------------------------------------------------ #

    def _fadeSeedBinding(self, seedIndex: int) -> None:
        self._stopFade(restore=True)
        source = self._structureSource
        segmentID = self._seedBindingSegmentID(seedIndex)
        if source is None or not segmentID:
            return
        displayNode = source.GetDisplayNode()
        if displayNode is None or not hasattr(displayNode, "GetSegmentOpacity2DFill"):
            return
        self._fadeDisplayNode = displayNode
        self._fadeSegmentID = segmentID
        self._fadeRestoreOpacity = displayNode.GetSegmentOpacity2DFill(segmentID)
        self._fadeStep = 0
        self._fadeTimer.start()

    def _onFadeStep(self) -> None:
        import math

        if self._fadeStep >= _FADE_STEPS or self._fadeDisplayNode is None:
            self._stopFade(restore=True)
            return
        phase = (self._fadeStep / _FADE_STEPS) * 2.0 * math.pi * 2.0
        blend = (1.0 - math.cos(phase)) * 0.5  # 0..1
        opacity = _FADE_MIN_OPACITY + blend * (_FADE_MAX_OPACITY - _FADE_MIN_OPACITY)
        try:
            self._fadeDisplayNode.SetSegmentOpacity2DFill(self._fadeSegmentID, opacity)
        except Exception:  # noqa: BLE001 - a segment removed mid-pulse just ends the fade
            self._stopFade(restore=False)
            return
        self._fadeStep += 1

    def _stopFade(self, restore: bool) -> None:
        if self._fadeTimer.isActive():
            self._fadeTimer.stop()
        if restore and self._fadeDisplayNode is not None and self._fadeSegmentID:
            try:
                self._fadeDisplayNode.SetSegmentOpacity2DFill(
                    self._fadeSegmentID, self._fadeRestoreOpacity
                )
            except Exception:  # noqa: BLE001 - best-effort restore
                pass
        self._fadeDisplayNode = None
        self._fadeSegmentID = ""
