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
* DELETE -- a ``qt.QToolButton`` that removes the seed via ``RemoveNthSeed``.

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

#: The seed default display colour (opaque white), mirroring the carrier's
#: ``SeedColorScratch`` default so an unedited row reads the same swatch the
#: carrier reports for an out-of-range index.
_DEFAULT_SEED_COLOR = (1.0, 1.0, 1.0)


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

        layout = qt.QVBoxLayout(self)

        self._table = qt.QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Colour", "Label", ""])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._table.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(False)
        # The label column takes the row's slack; the colour + delete cells stay
        # tight to their controls.
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, qt.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, qt.QHeaderView.Stretch)
        header.setSectionResizeMode(2, qt.QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        self._attachCarrierObserver()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Drop the carrier observer (called by the test teardown fixture).

        A parentless Qt widget holding a MRML observer must tear down cleanly
        so it does not survive to app shutdown
        (``feedback_launched_widget_teardown_crash``).
        """
        self._detachCarrierObserver()

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
        self._rebuild()

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

    def _onLabelEdited(self, rowIndex: int, edit: Any) -> None:
        if self._rebuilding:
            return
        self.setSeedLabel(rowIndex, edit.text)

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

        # Delete: an icon-only button paired with text + a tooltip (ADR-0010).
        deleteButton = qt.QToolButton()
        deleteButton.setAutoRaise(True)
        deleteButton.setText("Delete")
        deleteButton.setToolTip("Remove this seed")
        deleteButton.connect(
            "clicked(bool)",
            lambda _checked, i=rowIndex: self.deleteSeed(i),
        )
        self._table.setCellWidget(rowIndex, 2, deleteButton)

        self._rows[rowIndex] = {
            "colour": colourButton,
            "label": labelEdit,
            "delete": deleteButton,
        }
