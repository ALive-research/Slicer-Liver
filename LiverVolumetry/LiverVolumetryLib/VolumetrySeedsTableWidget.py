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
capture"), and a DELETE button.  Each composite row widget covers its whole tree
item, so a press anywhere on the row lands on a CHILD control (the stretch line
edit under most of it), which consumes the press -- the tree item itself would
never be selected by a real click.  A row-select event filter on every row
child selects the row FIRST and does not consume the press, so a click on a row
both selects it and still drives the clicked control.  Selecting a seed row
RESTORES its visibility
snapshot (``VisibilityCarve``) and highlights its EFFECTIVE (carved) region in
the 2D slices with slowly MARCHING diagonal stripes: this widget owns the phase
``qt.QTimer`` and publishes ``highlightSeed`` / ``stripePhase`` onto the shared
display node (``CarvedRegionStripes``); the LayerDM slice pipelines render.
The highlight is persistent while selected (no opacity flashing) and is paired
with the row's text naming the owner + context (ADR-0010, never
colour/animation alone).

CARRIER IS THE MODEL.  The table reads/writes the carrier and OBSERVES its
``vtkCommand::ModifiedEvent`` to rebuild.  ``cleanup()`` detaches the observer +
stops the stripe timer so a parentless widget does not survive to app shutdown
holding a MRML observer (``feedback_launched_widget_teardown_crash``).

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
    from .VisibilityCarve import (
        apply_visibility_context,
        carved_mask_for_seed,
        read_seed_context,
    )
    from .CarvedRegionStripes import (
        STRIPE_PERIOD_PX,
        STRIPE_TICK_MS,
        set_highlight_seed,
        set_stripe_phase,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from SeedTargetResolution import (  # type: ignore[no-redef]
        gather_touched_candidates,
        resolve_touched_candidates,
    )
    from VisibilityCarve import (  # type: ignore[no-redef]
        apply_visibility_context,
        carved_mask_for_seed,
        read_seed_context,
    )
    from CarvedRegionStripes import (  # type: ignore[no-redef]
        STRIPE_PERIOD_PX,
        STRIPE_TICK_MS,
        set_highlight_seed,
        set_stripe_phase,
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

#: The single column the composite row widget lives on (mirrors the territory
#: tree slice-4 amendment): a header-less tree, one composite QWidget per item.
_COMPOSITE_COLUMN = 0
_COLUMN_COUNT = 1

#: The empty-carve cue (ADR-0010 legible text -- silent nothing is not a
#: state): shown on the SELECTED seed row when its effective (carved) region
#: is EMPTY -- the owner segment is fully covered by the snapshot segments
#: above it -- so "no stripes" is named, never mute.  An UNKNOWN carve (an
#: unbound seed / unreadable masks) shows no cue: unknown is not empty.
EMPTY_CARVE_MESSAGE = "Region fully covered by segments above"

#: Dynamic Qt properties tagging every widget of a composite row with its row
#: key, so the row-select event filter can resolve WHICH tree item a pressed
#: child control belongs to (a press on a child never reaches the tree
#: viewport, so the tree cannot select the row itself).
_ROW_SEED_PROPERTY = "volumetryRowSeed"
_ROW_VOLUME_PROPERTY = "volumetryRowVolume"


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
        # Deterministic volume order: minted / seed-bearing / display volumes in
        # first-seen order (so an EMPTY minted volume keeps its top-level row).
        self._volume_order: list[str] = []
        # volumeId -> its top-level QTreeWidgetItem + named controls; rebuilt.
        self._volume_items: dict[str, Any] = {}
        self._volume_rows: dict[str, dict[str, Any]] = {}
        # global seed index -> the seed composite row's named controls; rebuilt.
        self._seed_rows: dict[int, dict[str, Any]] = {}
        # global seed index -> the seed child QTreeWidgetItem (the row-select
        # event filter's target); rebuilt with the tree.
        self._seed_items: dict[int, Any] = {}
        # Auto-mint counter for "Add volume".
        self._mint_counter = 0

        # The carved-region stripe highlight: THIS widget owns the phase timer
        # and publishes highlightSeed / stripePhase onto the shared display
        # node (CarvedRegionStripes); the LayerDM slice pipelines render the
        # marching stripes.  Persistent while a seed row is selected -- no
        # opacity flashing (the old fade pulse is retired).
        self._stripeTimer = qt.QTimer(self)
        self._stripeTimer.setInterval(STRIPE_TICK_MS)
        self._stripeTimer.connect("timeout()", self._onStripeTick)
        self._stripePhase = 0
        self._highlightedSeed = -1

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
        """Drop the carrier observer + stop the stripe highlight (teardown)."""
        self._clearHighlight()
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
        pipeline reads them at placement time (``_assign_active_volume``).  The
        stripe highlight rides the same node, so a rebind clears it off the old
        one first.
        """
        if displayNode is not self._displayNode:
            self._clearHighlight()
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
        self._rebuild()

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

    def statusLabel(self, seedIndex: int) -> Any:
        """The seed row's empty-carve cue ``qt.QLabel`` (keyed by global index)."""
        return self._seedControl(seedIndex, "status")

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
        """Rebind the seed at ``seedIndex`` to ``segmentID`` + re-name.

        The Target combo is the FALLBACK retarget of the OWNING segment: the
        carve re-derives within the SAME visibility snapshot (the carrier's
        ModifiedEvent invalidates the pipelines' carve cache), so a highlighted
        seed's stripes follow the new owner without touching the context.
        """
        if self._carrier is None or not segmentID:
            return
        source = self._structureSource
        if source is None:
            return
        self._carrier.SetNthSeedBinding(seedIndex, source.GetID(), segmentID)
        segment = source.GetSegmentation().GetSegment(segmentID)
        if segment is not None:
            self.setSeedLabel(seedIndex, segment.GetName())

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
        """Restore the selected seed's snapshot + raise its carved highlight.

        Selecting a seed row flips the structure-source visibility to EXACTLY
        the seed's placement-time context (the visibility-composed carve rule:
        the snapshot IS the seed's reproducible definition), so the view shows
        the composition that defines the seed, and starts the marching-stripes
        highlight of its carved region.  Deselecting (or selecting a volume
        row) clears the highlight but restores no visibility -- the last
        selected context stays.
        """
        if self._rebuilding:
            return
        items = self._tree.selectedItems()
        seedIndex = items[0].data(0, qt.Qt.UserRole) if items else None
        if seedIndex is None:
            self._clearHighlight()
            self._updateEmptyCarveCue(None)
            return
        self._restoreVisibilityContext(int(seedIndex))
        self._highlightSeed(int(seedIndex))
        self._updateEmptyCarveCue(int(seedIndex))

    # ------------------------------------------------------------------ #
    # Visibility snapshot (restore-on-select, ``VisibilityCarve``)
    # ------------------------------------------------------------------ #

    def _seedVisibilityContext(self, seedIndex: int) -> list[str]:
        """The seed's ordered (top-first) visibility snapshot off the carrier."""
        return read_seed_context(self._carrier, seedIndex)

    def _restoreVisibilityContext(self, seedIndex: int) -> None:
        """Flip the structure-source visibility to the seed's snapshot.

        Shows exactly the context's segments and hides the rest; an empty
        snapshot (a legacy seed) is a NO-OP so the live view is never blanked.
        """
        source = self._structureSource
        if source is None or not hasattr(source, "GetSegmentation"):
            return
        context = self._seedVisibilityContext(seedIndex)
        if not context:
            return
        segmentation = source.GetSegmentation()
        allIDs = [
            segmentation.GetNthSegmentID(n)
            for n in range(segmentation.GetNumberOfSegments())
        ]
        apply_visibility_context(source.GetDisplayNode(), allIDs, context)

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
            self._seed_items = {}
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
        finally:
            self._rebuilding = False
        self._syncHighlightToSelection()

    def _appendVolumeItem(self, volumeId: str, seedIndices: list[int]) -> None:
        item = qt.QTreeWidgetItem(self._tree)
        self._volume_items[volumeId] = item
        rowWidget = self._buildVolumeRow(volumeId)
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, rowWidget)
        self._installRowSelectFilter(rowWidget, _ROW_VOLUME_PROPERTY, volumeId)
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
        # Carry the global seed index on the item so row-selection can restore
        # the seed's snapshot + raise its carved highlight.
        child.setData(0, qt.Qt.UserRole, seedIndex)
        self._seed_items[int(seedIndex)] = child
        rowWidget = self._buildSeedRow(seedIndex)
        self._tree.setItemWidget(child, _COMPOSITE_COLUMN, rowWidget)
        self._installRowSelectFilter(rowWidget, _ROW_SEED_PROPERTY, int(seedIndex))

    # ------------------------------------------------------------------ #
    # Row-select event filter (a press anywhere on a composite row selects
    # the row FIRST, without consuming the press)
    # ------------------------------------------------------------------ #

    def _installRowSelectFilter(self, rowWidget: Any, propertyName: str, key: Any) -> None:
        """Tag the row widget + every descendant and watch their mouse presses.

        The composite row widget covers the whole tree item, so a press on
        "the row" always lands on a child control (mostly the stretch line
        edit) and is CONSUMED there -- the tree viewport never sees it and the
        item is never selected, which made the row-selection features
        (visibility restore + the carved-region stripes) unreachable by a
        real click.  Tagging rides a dynamic Qt property (stable across
        PythonQt wrapper identities); the filter resolves it back to the tree
        item and selects, then lets the press continue into the control.
        """
        # Manual descendant walk: PythonQt does not reliably wrap the template
        # ``findChildren`` (the ``slicer.util.findChildren`` precedent).
        stack = [rowWidget]
        while stack:
            widget = stack.pop()
            widget.setProperty(propertyName, key)
            if hasattr(widget, "installEventFilter"):
                widget.installEventFilter(self)
            stack.extend(widget.children())

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt virtual
        try:
            if event.type() == qt.QEvent.MouseButtonPress:
                self._selectRowForWidget(watched)
        except Exception:  # noqa: BLE001 - an event filter must never raise
            pass
        return False  # never consume: the pressed control still works

    def _selectRowForWidget(self, widget: Any) -> None:
        """Select the tree row the pressed row-child ``widget`` belongs to.

        Resolves the row key off the widget's dynamic property (seed index or
        volume id) and makes that item the current selection -- firing the
        SAME ``itemSelectionChanged`` path a viewport click drives (visibility
        restore + carved-stripes highlight for a seed row; highlight clear for
        a volume row).  A no-op for untagged widgets or during a rebuild.
        """
        if self._rebuilding or widget is None:
            return
        item = None
        seedIndex = widget.property(_ROW_SEED_PROPERTY)
        if seedIndex is not None:
            item = self._seed_items.get(int(seedIndex))
        else:
            volumeId = widget.property(_ROW_VOLUME_PROPERTY)
            if volumeId:
                item = self._volume_items.get(str(volumeId))
        if item is None or item.isSelected():
            return
        self._tree.setCurrentItem(item)

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

        # The empty-carve cue label: hidden until THIS row is selected and its
        # carved region turns out empty (``EMPTY_CARVE_MESSAGE``).  Plain row
        # text (ADR-0010) right where the surgeon clicked -- the stripes'
        # absence is named, never a silent nothing.
        statusLabel = qt.QLabel("")
        statusLabel.setVisible(False)
        rowLayout.addWidget(statusLabel)

        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Delete")
        deleteButton.setToolTip("Remove this seed")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, i=seedIndex: self.deleteSeed(i),
        )
        rowLayout.addWidget(deleteButton)

        # a11y: name the owning segment + the visibility context in TEXT on the
        # row (ADR-0010 -- never colour/animation alone).  Selecting the row
        # restores this snapshot; the tooltip says what that means.
        rowWidget.setToolTip(self._seedContextToolTip(seedIndex))

        self._seed_rows[seedIndex] = {
            "widget": rowWidget,
            "colour": colourButton,
            "label": labelEdit,
            "target": targetCombo,
            "delete": deleteButton,
            "status": statusLabel,
        }
        return rowWidget

    def _seedContextToolTip(self, seedIndex: int) -> str:
        """The seed's owner + snapshot named in text (the a11y companion)."""
        owner = self._seedBindingSegmentID(seedIndex)
        ownerName = self._segmentName(owner) or owner or "unbound"
        context = self._seedVisibilityContext(seedIndex)
        if not context:
            return f"Structure: {ownerName} (no visibility snapshot)"
        contextNames = ", ".join(
            self._segmentName(segmentID) or segmentID for segmentID in context
        )
        return (
            f"Structure: {ownerName}. Visible at placement: {contextNames}. "
            "Selecting this row restores that view."
        )

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
    # Carved-region stripe highlight (CarvedRegionStripes; replaces the old
    # opacity-fade pulse -- persistent while selected, never a blink)
    # ------------------------------------------------------------------ #

    def _highlightSeed(self, seedIndex: int) -> None:
        """Publish the highlight + start the marching-phase timer.

        The highlight state rides the shared display node
        (``feedback_layerdm_state_on_display_node``): this widget writes
        ``highlightSeed`` / ``stripePhase`` and the LayerDM slice pipelines
        render the stripes.  Persistent while the row stays selected.
        """
        if self._displayNode is None:
            return
        self._highlightedSeed = int(seedIndex)
        self._stripePhase = 0
        set_stripe_phase(self._displayNode, 0)
        set_highlight_seed(self._displayNode, seedIndex)
        if not self._stripeTimer.isActive():
            self._stripeTimer.start()

    def _clearHighlight(self) -> None:
        """Stop the march + clear the highlight off the display node."""
        if self._stripeTimer.isActive():
            self._stripeTimer.stop()
        if self._highlightedSeed >= 0:
            set_highlight_seed(self._displayNode, -1)
        self._highlightedSeed = -1

    def _onStripeTick(self) -> None:
        """Advance the stripe phase one pixel (the calm, continuous march).

        Each write fires the display node's ModifiedEvent -- the pipelines'
        render tick; they reuse the cached carved mask and only shift the
        stripe family.
        """
        if self._displayNode is None or self._highlightedSeed < 0:
            self._clearHighlight()
            return
        self._stripePhase = (self._stripePhase + 1) % STRIPE_PERIOD_PX
        set_stripe_phase(self._displayNode, self._stripePhase)

    def _updateEmptyCarveCue(self, seedIndex: int | None) -> None:
        """Name an EMPTY carve on the selected seed row; hide every other cue.

        Runs once per row selection (never per stripe tick).  ``None`` (a
        deselect / a volume row) hides all cues.  Only a PRESENT-but-empty
        carve shows the message: an unknown carve (unbound seed, unreadable
        masks) stays cueless -- unknown is not empty.
        """
        for index, row in self._seed_rows.items():
            status = row.get("status")
            if status is not None and index != seedIndex:
                status.setVisible(False)
        if seedIndex is None:
            return
        status = self._seedControl(seedIndex, "status")
        if status is None:
            return
        empty = self._carvedRegionIsEmpty(seedIndex)
        status.setText(EMPTY_CARVE_MESSAGE if empty else "")
        status.setVisible(bool(empty))

    def _carvedRegionIsEmpty(self, seedIndex: int) -> bool:
        """True iff the seed's carved region is PRESENT and empty.

        Re-derives the owner-minus-above fold (``carved_mask_for_seed``, the
        same fold the stripes pipeline renders) with every mask resampled onto
        the display node's pick-surface labelmap grid.  ``False`` when the
        carve is UNKNOWN -- no structure source / reference / binding -- so the
        cue never claims full coverage it cannot establish.
        """
        source = self._structureSource
        display = self._displayNode
        if source is None or display is None or not hasattr(display, "GetPickSurfaceNode"):
            return False
        reference = display.GetPickSurfaceNode()
        if reference is None:
            return False

        def _segment_mask(segmentID: str) -> Any:
            try:
                import slicer

                return slicer.util.arrayFromSegmentBinaryLabelmap(source, segmentID, reference)
            except Exception:  # noqa: BLE001 - an unreadable mask carves nothing
                return None

        mask = carved_mask_for_seed(self._carrier, seedIndex, _segment_mask)
        return mask is not None and not mask.any()

    def _syncHighlightToSelection(self) -> None:
        """Clear the highlight when its row is gone (rebuild drops selection).

        A rebuild (a seed placed / deleted / cleared) clears the tree
        selection, so a stale highlight would march for a row that is no
        longer selected -- placement-of-another clears the highlight.
        """
        if self._highlightedSeed < 0:
            return
        items = self._tree.selectedItems()
        selected = items[0].data(0, qt.Qt.UserRole) if items else None
        if selected != self._highlightedSeed:
            self._clearHighlight()
