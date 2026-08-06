# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the LiverVolumetry seeds table widget.

A thin, carrier-backed table over the FLAT ``vtkMRMLVolumetrySeedsNode`` seed
carrier (ADR-0038 §"Consumers ledger"), the volumetry sibling of the
VascularTerritories ``TerritoriesTableWidget``.  It is a Python-composed
``qt.QWidget`` (ADR-0004: Slicer-Liver panels are Python, not C++
``qSlicer*ModuleWidget``) that OWNS a ``qt.QTableWidget``, one ROW per seed.

Unlike the territories tree (a two-level territory/seed hierarchy), the
volumetry seed carrier is a FLAT ORDERED list with no grouping and no edges,
so this is a plain flat table, not a ``QTreeWidget``.

Each row carries a horizontal strip of controls addressed by NAME through the
per-row getters (never by column index):

* COLOUR swatch -- a ``ctk.ctkColorPickerButton`` that renders the seed's
  display colour and opens the picker on click, writing ``SetNthSeedColor``.
* LABEL -- an editable ``qt.QLineEdit`` whose committed text writes
  ``SetNthSeedLabel``.  This label becomes the generated segment name that
  ``GenerateSegmentsLabelMap`` reads (ADR-0038 §Conformance), so it is the
  load-bearing per-seed field.
* TARGET -- a ``qt.QComboBox`` naming the structure the seed was caught by
  (the seed→label capture, ``territory-usability`` §"Seed→label capture") and
  offering the OTHER touched candidates so the surgeon can RETARGET the
  binding.  The bound segment's NAME is the a11y text -- the caught structure
  is always named, never signalled by the fade animation alone (ADR-0010).
* DELETE -- a ``qt.QToolButton`` that removes the seed via ``RemoveNthSeed``.

FADE HIGHLIGHT.  There is no named Slicer fade API, so a small ``qt.QTimer``
pulses the BOUND segment's 2D fill opacity in and out a few cycles when a seed
is placed or its row is selected -- a non-blocking "this is what was caught"
confirmation.  The fade is a CONFIRMATION on top of the text, never the sole
signal (ADR-0010): the target combo already names the segment.

The table has NO per-seed VISIBILITY column: the flat seed carrier and the
data-only ``vtkMRMLVolumetrySeedsDisplayNode`` expose only a single shared
``Visibility`` (inherited from ``vtkMRMLDisplayNode``), not a per-seed toggle,
so a per-row eye toggle would be a fake affordance -- the column is OMITTED
rather than faked (the segmentation-table precedent + the "no colour of the
sky" discipline).  The visibility column can be added later if the carrier
grows a per-seed visibility slot.

CARRIER IS THE MODEL.  The table reads/writes the carrier
(``GetNumberOfSeeds`` / ``GetNthSeedColor`` / ``GetNthSeedLabel`` for the
read; ``SetNthSeedColor`` / ``SetNthSeedLabel`` / ``RemoveNthSeed`` for the
edits) and OBSERVES its ``vtkCommand::ModifiedEvent`` to rebuild.  It detaches
the observer on ``cleanup()``: a parentless Qt widget holding a MRML observer
must tear down cleanly (cleanup + deleteLater) so it does not survive to
app shutdown (``feedback_launched_widget_teardown_crash``).

Kept THIN and re-parentable so the future unified planning table -- the one
that composes seeds, resections, and territories into a single panel -- can
absorb the same carrier binding without a rewrite.

a11y: every icon-only control also carries text + a tooltip (ADR-0010: never
an icon / colour alone).  The colour swatch is paired with the label text.

See also:
  * Docs/adr/0038 -- the seeds-off-markups migration + §Conformance (labels
    become generated segment names).
  * Docs/adr/0014-*.md §"Fourth layer" -- the wrapper/carrier/display/storage
    split (a display edit must not touch geometry).
  * Docs/adr/0010-accessibility-and-i18n.md -- glyph/text pairing.
  * Docs/adr/0004-*.md -- panels are Python.
  * VascularTerritories/VascularTerritoriesLib/TerritoriesTableWidget.py
    -- the carrier-backed table idiom this mirrors (hierarchical variant).
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

#: The seed default display colour (opaque white), mirroring the carrier's
#: ``SeedColorScratch`` default so an unedited row reads the same swatch the
#: carrier reports for an out-of-range index.
_DEFAULT_SEED_COLOR = (1.0, 1.0, 1.0)

#: The fade pulse: how many in/out cycles, and the per-step timer interval
#: (ms).  A handful of gentle cycles reads as "look here" without becoming a
#: distraction; the fade is confirmation on top of the named target, never the
#: sole signal (ADR-0010).
_FADE_STEPS = 12
_FADE_INTERVAL_MS = 60
#: The 2D fill opacity the pulse swings between (the bound segment's own
#: display node); restored to its pre-fade value when the pulse ends.
_FADE_MIN_OPACITY = 0.15
_FADE_MAX_OPACITY = 1.0


class VolumetrySeedsTableWidget(qt.QWidget):
    """Flat carrier-backed table over ``vtkMRMLVolumetrySeedsNode`` (ADR-0038).

    Constructed over the seed carrier::

        VolumetrySeedsTableWidget(carrier=<vtkMRMLVolumetrySeedsNode>)

    The carrier is the model: the table renders one row per seed, edits write
    back to the carrier, and a carrier ``ModifiedEvent`` rebuilds the rows.
    Controls are addressed by NAME through the per-row getters
    (``colourButton`` / ``labelEdit`` / ``deleteButton``), never by column
    index.
    """

    def __init__(self, carrier: Any = None, parent: Any = None) -> None:
        super().__init__(parent)

        self._carrier = carrier
        self._carrier_observer_tag: int | None = None
        # Guards against the write-back edits re-triggering a rebuild mid-edit.
        self._rebuilding = False
        # rowIndex -> the named controls parsed out of the row (rebuilt every
        # repaint).
        self._rows: dict[int, dict[str, Any]] = {}
        # The structure-source segmentation the retarget menu recomputes touched
        # candidates against (the seed→label capture source); bound by the module
        # widget via ``setStructureSource``.  ``None`` -> the target column reads
        # only the stored binding, no retarget choices.
        self._structureSource: Any = None
        # The index of the last seed we fired a placement-fade for, so a stream
        # of edit-Modifieds on an already-bound newest seed does not re-pulse.
        self._lastFadedSeed = -1

        # The fade-pulse machinery: a QTimer steps the bound segment's 2D fill
        # opacity in/out, restoring the pre-fade value when the pulse ends.  One
        # timer at a time (a new pulse cancels the prior one).
        self._fadeTimer = qt.QTimer(self)
        self._fadeTimer.setInterval(_FADE_INTERVAL_MS)
        self._fadeTimer.connect("timeout()", self._onFadeStep)
        self._fadeStep = 0
        self._fadeDisplayNode: Any = None
        self._fadeSegmentID: str = ""
        self._fadeRestoreOpacity = 1.0

        layout = qt.QVBoxLayout(self)

        self._table = qt.QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Colour", "Label", "Target", ""])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(False)
        # The label column takes the row's slack; the colour + target + delete
        # cells stay tight to their controls.
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, qt.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, qt.QHeaderView.Stretch)
        header.setSectionResizeMode(2, qt.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, qt.QHeaderView.ResizeToContents)
        # Selecting a row re-fades the bound segment (the "which structure is
        # this seed on?" confirmation on demand).
        self._table.connect("itemSelectionChanged()", self._onRowSelectionChanged)
        layout.addWidget(self._table)

        self._attachCarrierObserver()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Drop the carrier observer + stop the fade timer (test teardown fixture).

        A parentless Qt widget holding a MRML observer must tear down cleanly
        so it does not survive to app shutdown
        (``feedback_launched_widget_teardown_crash``).  The fade timer is
        stopped and its restore applied so a pulse in flight does not leave a
        segment mid-fade.
        """
        self._stopFade(restore=True)
        self._detachCarrierObserver()

    def setStructureSource(self, segmentationNode: Any) -> None:
        """Bind the structure-source segmentation the retarget menu scans.

        The seed→label capture (``territory-usability`` §"Seed→label capture")
        binds a seed to the top touched segment; the retarget menu recomputes
        the touched-candidate set at the seed's coordinate against THIS
        segmentation so the surgeon can pick a different structure.  ``None``
        leaves each row showing only its stored binding, no retarget choices.
        """
        self._structureSource = segmentationNode
        self._rebuild()

    def setCarrier(self, carrier: Any) -> None:
        """Rebind the table to ``carrier`` (drops the prior observer, rebuilds).

        The rebind seam the module widget uses once the scene-resident carrier
        is created (or re-created after a scene close); the same seam the future
        unified planning table can adopt to adopt this carrier.
        """
        if carrier is self._carrier:
            return
        self._detachCarrierObserver()
        self._carrier = carrier
        self._attachCarrierObserver()
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
        # A placement fires AddSeed (unbound) THEN SetNthSeedBinding, each its
        # own Modified: fade on the transition where the newest seed GAINS a
        # binding it did not have at the last rebuild, so the pulse lands on the
        # capture, not the bare add (the "this is what was caught" confirmation).
        newest = self._seedCount() - 1
        newlyBound = newest >= 0 and bool(self._seedBindingSegmentID(newest)) and newest != self._lastFadedSeed
        self._rebuild()
        if newlyBound:
            self._lastFadedSeed = newest
            self._fadeSeedBinding(newest)

    # ------------------------------------------------------------------ #
    # Item-model reader seams
    # ------------------------------------------------------------------ #

    def table(self) -> Any:
        """The underlying ``qt.QTableWidget``."""
        return self._table

    def rowCount(self) -> int:
        """The number of rows currently rendered (one per seed)."""
        return self._table.rowCount

    def _control(self, rowIndex: int, key: str) -> Any:
        """The named control from a row (or ``None`` for an out-of-range row)."""
        row = self._rows.get(int(rowIndex))
        return row[key] if row is not None else None

    def colourButton(self, rowIndex: int) -> Any:
        """The ``ctk.ctkColorPickerButton`` on the row."""
        return self._control(rowIndex, "colour")

    def labelEdit(self, rowIndex: int) -> Any:
        """The editable label ``qt.QLineEdit`` on the row."""
        return self._control(rowIndex, "label")

    def targetCombo(self, rowIndex: int) -> Any:
        """The retarget ``qt.QComboBox`` on the row (the touched candidates)."""
        return self._control(rowIndex, "target")

    def deleteButton(self, rowIndex: int) -> Any:
        """The delete ``qt.QToolButton`` on the row."""
        return self._control(rowIndex, "delete")

    # ------------------------------------------------------------------ #
    # Edits (write back to the carrier)
    # ------------------------------------------------------------------ #

    def setSeedColor(self, rowIndex: int, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedColor(int(rowIndex), float(r), float(g), float(b))

    def setSeedLabel(self, rowIndex: int, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedLabel(int(rowIndex), str(label))

    def deleteSeed(self, rowIndex: int) -> None:
        """Remove the seed at ``rowIndex`` via the carrier's ``RemoveNthSeed``.

        The single seed-removal path both the delete button and any external
        caller reach -- the same carrier method the placement pipeline's
        pick-delete uses, so delete-by-row and delete-by-pick converge.
        """
        if self._carrier is not None:
            self._carrier.RemoveNthSeed(int(rowIndex))

    def retargetSeed(self, rowIndex: int, segmentID: str) -> None:
        """Rebind the seed at ``rowIndex`` to ``segmentID`` + re-fade + re-name.

        The retarget path the target combo drives (``territory-usability``
        §"Seed→label capture"): rebinds the seed to the chosen touched
        candidate, renames its label to that segment's name so the a11y text
        follows the binding, and re-fades the newly-bound segment.  A no-op with
        no carrier / no structure source / an empty segmentID.
        """
        if self._carrier is None or not segmentID:
            return
        source = self._structureSource
        if source is None:
            return
        self._carrier.SetNthSeedBinding(rowIndex, source.GetID(), segmentID)
        segment = source.GetSegmentation().GetSegment(segmentID)
        if segment is not None:
            self.setSeedLabel(rowIndex, segment.GetName())
        self._fadeSeedBinding(rowIndex)

    def _onLabelEdited(self, rowIndex: int, edit: Any) -> None:
        if self._rebuilding:
            return
        self.setSeedLabel(rowIndex, edit.text)

    def _onTargetChanged(self, rowIndex: int, combo: Any) -> None:
        if self._rebuilding:
            return
        segmentID = combo.itemData(combo.currentIndex)
        if segmentID:
            self.retargetSeed(rowIndex, str(segmentID))

    def _onRowSelectionChanged(self) -> None:
        """Re-fade the selected seed's bound segment (confirmation on demand)."""
        if self._rebuilding:
            return
        rows = self._table.selectionModel().selectedRows()
        if rows:
            self._fadeSeedBinding(rows[0].row())

    def _onColourChanged(self, rowIndex: int, colour: Any) -> None:
        if self._rebuilding:
            return
        self.setSeedColor(rowIndex, colour.redF(), colour.greenF(), colour.blueF())

    # ------------------------------------------------------------------ #
    # Repaint
    # ------------------------------------------------------------------ #

    def _seedCount(self) -> int:
        if self._carrier is None:
            return 0
        return self._carrier.GetNumberOfSeeds()

    def _rebuild(self) -> None:
        self._rebuilding = True
        try:
            self._rows = {}
            count = self._seedCount()
            self._table.setRowCount(count)
            for rowIndex in range(count):
                self._buildRow(rowIndex)
            # A shrink (delete / clear) invalidates the last-faded index.
            if self._lastFadedSeed >= count:
                self._lastFadedSeed = -1
        finally:
            self._rebuilding = False

    def _seedColor(self, rowIndex: int) -> tuple[float, float, float]:
        if self._carrier is None:
            return _DEFAULT_SEED_COLOR
        rgb = self._carrier.GetNthSeedColor(rowIndex)
        return (rgb[0], rgb[1], rgb[2])

    def _seedLabel(self, rowIndex: int) -> str:
        if self._carrier is None:
            return ""
        return self._carrier.GetNthSeedLabel(rowIndex)

    def _buildRow(self, rowIndex: int) -> None:
        """Compose one seed row's controls: colour swatch, label, delete.

        Controls are registered by NAME in ``_rows`` so the getters resolve
        them without any column index.
        """
        color = self._seedColor(rowIndex)
        label = self._seedLabel(rowIndex)

        # Colour swatch: the Slicer-idiomatic ``ctkColorPickerButton`` (the
        # segmentation / resection convention) -- it renders its own colour
        # square, opens the picker on click, and emits ``colorChanged``.
        # ``setColor`` BEFORE ``connect`` so seeding the initial colour does
        # not fire the write-back.  The button text names the seed so the
        # colour is never the only cue (ADR-0010, colour never alone).
        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.setToolTip(f"Seed {rowIndex + 1} colour")
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, i=rowIndex: self._onColourChanged(i, c),
        )
        self._table.setCellWidget(rowIndex, 0, colourButton)

        # Editable label: a ``QLineEdit`` whose committed text becomes the
        # generated segment name (ADR-0038 §Conformance).  ``editingFinished``
        # writes ``SetNthSeedLabel``.
        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.setPlaceholderText(f"Seed {rowIndex + 1} label")
        labelEdit.setToolTip("Label for this seed (becomes the generated segment name)")
        labelEdit.connect(
            "editingFinished()",
            lambda i=rowIndex, e=labelEdit: self._onLabelEdited(i, e),
        )
        self._table.setCellWidget(rowIndex, 1, labelEdit)

        # Target: a combo naming the caught structure + the OTHER touched
        # candidates (the retarget affordance).  The current binding's segment
        # NAME is the selected entry -- the a11y text that names the caught
        # structure so the fade animation is never the sole cue (ADR-0010).
        targetCombo = self._buildTargetCombo(rowIndex)
        self._table.setCellWidget(rowIndex, 2, targetCombo)

        # Delete: an icon-only button paired with text + a tooltip (ADR-0010).
        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Delete")
        deleteButton.setToolTip("Remove this seed")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, i=rowIndex: self.deleteSeed(i),
        )
        self._table.setCellWidget(rowIndex, 3, deleteButton)

        self._rows[rowIndex] = {
            "colour": colourButton,
            "label": labelEdit,
            "target": targetCombo,
            "delete": deleteButton,
        }

    def _buildTargetCombo(self, rowIndex: int) -> Any:
        """Compose the row's retarget combo: the touched candidates, top-first.

        Lists the segments the seed touched (recomputed at the seed's coordinate
        against the structure source) with the currently-bound segment
        pre-selected; picking another entry retargets the binding.  Falls back
        to naming only the stored binding when the structure source is absent or
        the coordinate touches nothing (a placement before a target resolved).
        """
        combo = qt.QComboBox()
        combo.setToolTip("The structure this seed is bound to (pick another to retarget)")
        boundSegmentID = self._seedBindingSegmentID(rowIndex)
        candidates = self._touchedCandidates(rowIndex)
        # Always include the stored binding even if it is no longer touched, so
        # the row never loses its named target.
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
            lambda _idx, i=rowIndex, c=combo: self._onTargetChanged(i, c),
        )
        return combo

    # ------------------------------------------------------------------ #
    # Binding + candidate readers (the target column's model)
    # ------------------------------------------------------------------ #

    def _seedBindingSegmentID(self, rowIndex: int) -> str:
        """The segment ID the seed is bound to (empty when unbound)."""
        if self._carrier is None or not hasattr(self._carrier, "GetNthSeedBindingSegmentID"):
            return ""
        return self._carrier.GetNthSeedBindingSegmentID(rowIndex)

    def _touchedCandidates(self, rowIndex: int) -> list[str]:
        """The segments the seed's coordinate touches, ordered top-first.

        Recomputes the touched-candidate set (one voxel per visible segment)
        against the structure source, so the retarget menu offers exactly the
        structures the seed sits in.  Empty when there is no structure source or
        the carrier lacks the coordinate.
        """
        source = self._structureSource
        if source is None or self._carrier is None:
            return []
        coord = self._carrier.GetNthSeed(rowIndex)
        ras = (float(coord[0]), float(coord[1]), float(coord[2]))
        touched = gather_touched_candidates(source, source.GetDisplayNode(), ras)
        ordered, _top = resolve_touched_candidates(touched)
        return ordered

    def _segmentName(self, segmentID: str) -> str:
        """The human name of ``segmentID`` on the structure source (or empty)."""
        source = self._structureSource
        if source is None or not segmentID:
            return ""
        segment = source.GetSegmentation().GetSegment(segmentID)
        return segment.GetName() if segment is not None else ""

    # ------------------------------------------------------------------ #
    # Fade pulse (the caught-structure confirmation; no named Slicer fade API)
    # ------------------------------------------------------------------ #

    def _fadeSeedBinding(self, rowIndex: int) -> None:
        """Pulse the bound segment's 2D fill opacity as a caught confirmation.

        Reads the seed's binding, resolves the segmentation's display node, and
        starts the fade timer against that segment.  A no-op (and a clean stop
        of any prior pulse) when the seed is unbound or the segmentation is not
        in the scene -- the named target combo remains the a11y cue.
        """
        self._stopFade(restore=True)
        source = self._structureSource
        segmentID = self._seedBindingSegmentID(rowIndex)
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
        """One fade step: swing the opacity along a raised-cosine, then restore.

        Steps a smooth in/out pulse so the bound segment breathes a few cycles;
        when the steps run out the pre-fade opacity is restored and the timer
        stops (the pulse is a transient confirmation, not a persistent change).
        """
        import math

        if self._fadeStep >= _FADE_STEPS or self._fadeDisplayNode is None:
            self._stopFade(restore=True)
            return
        # A raised-cosine over the step count gives smooth breathing between the
        # min/max opacity; two full cycles across the steps.
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
        """Stop the pulse; optionally restore the segment's pre-fade opacity."""
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
