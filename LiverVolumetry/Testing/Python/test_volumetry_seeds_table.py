# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the LiverVolumetry seeds table widget.

Pins the carrier-backed seeds table's per-SEED contract (the volumetry sibling
of the VascularTerritories ``TerritoriesTableWidget``).  The table now nests
seeds under their VOLUME (territory-usability grouped-volumes,
``test_volumetry_volumes_table.py``); this file pins the per-seed row controls,
which stay keyed by the seed's GLOBAL placement index on top of the grouping:

* ROW-PER-SEED -- ``rowCount`` counts one SEED row per carrier seed, in
  placement order, matching ``GetNumberOfSeeds`` (the carrier is the model).
* CARRIER MODIFIED REBUILD -- adding a seed to the carrier (outside the table)
  grows the row count without an explicit refresh (the table observes the
  carrier's ``ModifiedEvent``).
* LABEL EDIT -- committing the row's ``QLineEdit`` writes ``SetNthSeedLabel``
  on the carrier (the label becomes the generated segment name, ADR-0038
  §Conformance) without touching the seed coordinate.
* COLOUR EDIT -- the row's colour picker writes ``SetNthSeedColor`` without
  touching the coordinate.
* DELETE -- the row's overflow "Delete seed" action calls ``RemoveNthSeed``,
  dropping exactly that seed (one-click when snapshotless; the confirm names
  a snapshot-bearing seed); the ``deleteSeed`` entry point converges on the
  same carrier method.
* OBSERVER TEARDOWN -- ``cleanup`` detaches the carrier observer so a
  parentless widget does not survive to app shutdown holding a MRML observer
  (feedback_launched_widget_teardown_crash).

HARNESS: launched Slicer.  The table needs Qt (``qt.QTableWidget`` +
``ctk.ctkColorPickerButton``) + the wrapped ``vtkMRMLVolumetrySeedsNode``
carrier, so a bare ``PythonSlicer -m pytest`` (``slicer.mrmlScene is None``,
no Qt) SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards; the CTest
row collects + skips bare and RUNS launched (ADR-0027).

References
----------
* ADR-0038 -- §"Consumers ledger" + §Conformance (per-seed labels become
  generated segment names).
* ADR-0014 -- the four-layer split (a display edit must not touch geometry).
* ADR-0010 -- glyph/text pairing (icon controls carry text + tooltip).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/Testing/Python/test_territories_table.py -- the
  carrier-backed table idiom this mirrors (hierarchical variant).
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _qt_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_carrier_or_skip(slicer, name="SeedsTableCarrierTest"):
    """Mint a seed carrier exposing the flat seed API, or skip-pend (ADR-0027)."""
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(
            f"{SEEDS_NODE_CLASS} not registered -- the ADR-0038-amendment "
            "volumetry seed carrier has not landed (launched build; ADR-0027)."
        )
    for method in ("AddSeed", "GetNumberOfSeeds", "GetNthSeed"):
        if not hasattr(node, method):
            pytest.skip(
                f"{SEEDS_NODE_CLASS} has no {method} -- the seed carrier API "
                "has not landed (ADR-0027)."
            )
    return node


def _import_table_or_skip():
    """Import the seeds table widget class, or skip-pend (ADR-0027)."""
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VolumetrySeedsTableWidget not importable ({exc!r}) -- the ADR-0038 "
            "seeds table has not landed OR Qt/ctk is not reachable here.  The "
            "skip lifts at the implementation commit (ADR-0027)."
        )
    return VolumetrySeedsTableWidget


def _make_table_or_skip(slicer, carrier):
    """Construct the table over the carrier, or skip-pend the seam (ADR-0027)."""
    VolumetrySeedsTableWidget = _import_table_or_skip()
    try:
        table = VolumetrySeedsTableWidget(carrier=carrier)
    except TypeError as exc:
        pytest.skip(
            f"VolumetrySeedsTableWidget(carrier=) seam absent ({exc!r}) -- the "
            "ADR-0038 widget constructor has not landed (ADR-0027)."
        )
    for method in ("table", "rowCount"):
        if not hasattr(table, method):
            pytest.skip(
                f"VolumetrySeedsTableWidget has no {method} seam (ADR-0027)."
            )
    return table


# --------------------------------------------------------------------------- #
# ROW-PER-SEED + carrier-modified rebuild
# --------------------------------------------------------------------------- #


def test_table_has_one_row_per_seed(qt_widgets):
    """The table renders one row per carrier seed, matching the seed count."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    assert table.rowCount() == carrier.GetNumberOfSeeds() == 3, (
        "the table must render one SEED row per carrier seed (per-volume tree, "
        "territory-usability)."
    )


def test_carrier_modified_event_rebuilds_the_table(qt_widgets):
    """A carrier ``ModifiedEvent`` rebuilds the table (the carrier is the model).

    Adding a seed to the carrier (outside the table) grows the row count with
    no explicit refresh -- the table observes the carrier.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    carrier.AddSeed(1.0, 0.0, 0.0)
    before = table.rowCount()

    carrier.AddSeed(2.0, 0.0, 0.0)  # fires ModifiedEvent

    after = table.rowCount()
    assert after == before + 1, (
        "a carrier ModifiedEvent must rebuild the table (row count grows with "
        "the seed count) -- the carrier is the model, no manual refresh."
    )


# --------------------------------------------------------------------------- #
# LABEL edit -- writes SetNthSeedLabel without touching geometry
# --------------------------------------------------------------------------- #


def test_editing_the_label_line_edit_writes_set_nth_seed_label(qt_widgets):
    """Committing the row's ``QLineEdit`` writes ``SetNthSeedLabel`` on the carrier.

    ADR-0038 §Conformance: the per-seed label becomes the generated segment
    name.  Committing an edit (setting the text + emitting ``editingFinished``)
    routes through ``setSeedLabel`` and writes the carrier -- without moving the
    seed coordinate.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedLabel"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedLabel (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "labelEdit"):
        pytest.skip("VolumetrySeedsTableWidget has no labelEdit seam (ADR-0027).")

    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.Modified()

    edit = table.labelEdit(0)
    assert edit is not None, "the seed row must carry an editable label QLineEdit."

    edit.setText("SegmentV")
    edit.editingFinished()  # commit the edit

    assert carrier.GetNthSeedLabel(0) == "SegmentV", (
        "committing the label QLineEdit must write SetNthSeedLabel on the "
        "carrier (the generated segment name; ADR-0038 §Conformance)."
    )
    # The display edit must not move the seed.
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9), (
        "a label edit must NOT move the seed coordinate (ADR-0014 four-layer)."
    )


def test_set_seed_color_writes_carrier_without_touching_geometry(qt_widgets):
    """``setSeedColor`` writes ``SetNthSeedColor`` without moving the seed.

    ADR-0014 §"Fourth layer": a display edit writes the display slot only; the
    seed coordinate stays byte-identical.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedColor"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedColor (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "setSeedColor"):
        pytest.skip("VolumetrySeedsTableWidget has no setSeedColor seam (ADR-0027).")

    carrier.AddSeed(4.0, 5.0, 6.0)
    carrier.Modified()

    table.setSeedColor(0, 0.3, 0.6, 0.9)

    color = carrier.GetNthSeedColor(0)
    assert (color[0], color[1], color[2]) == pytest.approx((0.3, 0.6, 0.9), abs=1e-6)
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((4.0, 5.0, 6.0), abs=1e-9), (
        "a colour edit must NOT move the seed coordinate (ADR-0014 four-layer)."
    )


# --------------------------------------------------------------------------- #
# DELETE -- drops exactly that seed via RemoveNthSeed
# --------------------------------------------------------------------------- #


def test_delete_seed_removes_exactly_one_point(qt_widgets):
    """``deleteSeed`` removes EXACTLY ONE carrier seed; survivors keep order."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "RemoveNthSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no RemoveNthSeed (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteSeed"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteSeed seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    table.deleteSeed(1)

    assert carrier.GetNumberOfSeeds() == len(pts) - 1, (
        "delete-by-row must remove EXACTLY ONE carrier seed."
    )
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx(pts[2], abs=1e-6)


def test_delete_action_removes_exactly_that_seed(qt_widgets):
    """Triggering a row's overflow "Delete seed" removes exactly that seed.

    The row diet moved the destructive delete behind the "..." overflow
    menu; a SNAPSHOTLESS seed still deletes one-click (no confirm).
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "RemoveNthSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no RemoveNthSeed (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteAction"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteAction seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    def _never_confirm(text):
        raise AssertionError("a snapshotless delete must not confirm")

    table._confirmDestructive = _never_confirm  # noqa: SLF001 - confirm seam

    delete = table.deleteAction(1)
    assert delete is not None, "the seed overflow must carry a Delete seed action."
    delete.trigger()

    assert carrier.GetNumberOfSeeds() == len(pts) - 1, (
        "the overflow Delete seed must remove EXACTLY ONE carrier seed."
    )
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx(pts[2], abs=1e-6)


def test_deleting_a_snapshot_bearing_seed_confirms_by_name(qt_widgets):
    """Deleting a seed WITH a visibility snapshot goes through the confirm,
    which names the seed; declining keeps it."""
    import vtk

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedVisibilityContext"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no visibility-context slot (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteAction"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteAction seam (ADR-0027).")

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedLabel(0, "Wedge seed")
    ids = vtk.vtkStringArray()
    ids.InsertNextValue("Parenchyma")
    carrier.SetNthSeedVisibilityContext(0, ids)
    carrier.Modified()

    confirms = []

    def _fake_confirm(text):
        confirms.append(text)
        return _fake_confirm.answer

    _fake_confirm.answer = False
    table._confirmDestructive = _fake_confirm  # noqa: SLF001 - confirm seam

    table.deleteAction(0).trigger()
    assert carrier.GetNumberOfSeeds() == 1, (
        "a DECLINED confirm must keep the snapshot-bearing seed."
    )
    assert confirms and "Wedge seed" in confirms[0], (
        "the confirm must NAME the seed it is about to delete."
    )

    _fake_confirm.answer = True
    table.deleteAction(0).trigger()
    assert carrier.GetNumberOfSeeds() == 0


# --------------------------------------------------------------------------- #
# TARGET column + retarget (the seed→label capture surface)
# --------------------------------------------------------------------------- #


def _checked_action_texts(menu):
    """The texts of the CHECKED actions on a retarget submenu."""
    texts = []
    for action in menu.actions():
        checked = action.isChecked
        checked = checked() if callable(checked) else checked
        if checked:
            text = action.text
            texts.append(text() if callable(text) else text)
    return texts


def test_retarget_menu_names_the_bound_segment(qt_widgets):
    """The overflow Retarget submenu CHECKS the seed's bound segment.

    ``territory-usability`` §"Seed→label capture" / ADR-0010: the caught
    structure is named in text.  The row diet moved the Target combo into
    the overflow menu; the bound candidate reads checked.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedBinding"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedBinding (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "targetCombo") or not hasattr(table, "setStructureSource"):
        pytest.skip("VolumetrySeedsTableWidget has no target/retarget seam (ADR-0027).")

    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SegSrc")
    segmentation.CreateDefaultDisplayNodes()
    segmentation.GetSegmentation().AddEmptySegment("segA", "Alpha")
    segmentation.GetSegmentation().AddEmptySegment("segB", "Beta")
    table.setStructureSource(segmentation)

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "segB")
    carrier.Modified()

    menu = table.targetCombo(0)
    assert menu is not None, "the seed overflow must carry a Retarget submenu."
    assert _checked_action_texts(menu) == ["Beta"], (
        "the Retarget submenu must CHECK the seed's bound segment "
        "(ADR-0010 text)."
    )


def test_retarget_rebinds_the_seed_and_renames_label(qt_widgets):
    """``retargetSeed`` rebinds the seed and renames its label to follow.

    Picking another candidate writes the carrier binding + relabels the seed to
    the new segment's name so the a11y text tracks the binding.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedBinding"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedBinding (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "retargetSeed") or not hasattr(table, "setStructureSource"):
        pytest.skip("VolumetrySeedsTableWidget has no retarget seam (ADR-0027).")

    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SegSrc")
    segmentation.CreateDefaultDisplayNodes()
    segmentation.GetSegmentation().AddEmptySegment("segA", "Alpha")
    segmentation.GetSegmentation().AddEmptySegment("segB", "Beta")
    table.setStructureSource(segmentation)

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "segB")
    carrier.Modified()

    table.retargetSeed(0, "segA")

    assert carrier.GetNthSeedBindingSegmentID(0) == "segA", (
        "retarget must rebind the seed to the chosen segment."
    )
    assert carrier.GetNthSeedLabel(0) == "Alpha", (
        "retarget must rename the seed label to follow the new binding."
    )


# --------------------------------------------------------------------------- #
# ROW DIET -- at most four visible controls; occasional actions overflow
# --------------------------------------------------------------------------- #


def test_seed_row_carries_no_inline_combo_or_delete(qt_widgets):
    """The seed row shows Pin / colour / label / cue-chip text only; the
    retarget combo and delete moved behind the "..." overflow menu."""
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "overflowButton"):
        pytest.skip("VolumetrySeedsTableWidget has no overflow seam (ADR-0027).")

    carrier.AddSeed(0.0, 0.0, 0.0)

    row = table._seed_rows[carrier.GetNthSeedID(0)]["widget"]  # noqa: SLF001
    stack, combos = [row], []
    while stack:
        widget = stack.pop()
        if isinstance(widget, qt.QComboBox):
            combos.append(widget)
        stack.extend(widget.children())
    assert combos == [], (
        "no inline QComboBox on the seed row -- the retarget moved into the "
        "overflow menu (the row diet)."
    )
    assert table.overflowButton(0) is not None
    assert table.deleteAction(0) is not None, (
        "delete lives on the overflow menu, not the row strip."
    )
    assert table.restoreAction(0) is not None, (
        "Restore placement view lives on the overflow menu."
    )


def _overlapping_two_segment_segmentation(slicer, name="SegSrc"):
    """Two LAYERED block segments overlapping at (2, 2, 2): Alpha under Beta.

    The retarget submenu offers the TOUCHED candidates (the seed→label
    capture contract, SeedTargetResolution), so a retarget test needs REAL
    overlapping labelmap geometry at the seed position -- empty segments
    touch nothing and would offer only the bound segment.  The touched
    membership read (``arrayFromSegmentBinaryLabelmap``) needs the
    segmentation's reference image geometry, so the first source labelmap
    stays in the scene as that reference.
    """
    import numpy as np

    seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", name)
    seg.CreateDefaultDisplayNodes()

    def _add_segment_from_array(array, label, keepAsReference=False):
        labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
        slicer.util.updateVolumeFromArray(labelmap, array.astype(np.uint8))
        ok = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
            labelmap, seg)
        assert ok
        if keepAsReference:
            seg.SetReferenceImageGeometryParameterFromVolumeNode(labelmap)
        else:
            slicer.mrmlScene.RemoveNode(labelmap)
        segmentation = seg.GetSegmentation()
        segmentID = segmentation.GetNthSegmentID(segmentation.GetNumberOfSegments() - 1)
        segmentation.GetSegment(segmentID).SetName(label)
        return segmentID

    outer = np.zeros((8, 8, 8), dtype=np.uint8)
    outer[1:7, 1:7, 1:7] = 1
    inner = np.zeros((8, 8, 8), dtype=np.uint8)
    inner[1:4, 1:4, 1:4] = 1
    alphaID = _add_segment_from_array(outer, "Alpha", keepAsReference=True)
    betaID = _add_segment_from_array(inner, "Beta")
    return seg, (alphaID, betaID)


def test_retarget_action_rebinds_through_the_menu(qt_widgets):
    """Triggering a retarget submenu candidate rebinds + renames the seed.

    The seed sits where BOTH segments overlap, so the touched-candidate set
    offers Alpha alongside the bound Beta (SeedTargetResolution).
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedBinding"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedBinding (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "retargetMenu"):
        pytest.skip("VolumetrySeedsTableWidget has no retargetMenu seam (ADR-0027).")

    segmentation, (alphaID, betaID) = _overlapping_two_segment_segmentation(slicer)
    table.setStructureSource(segmentation)

    carrier.AddSeed(2.0, 2.0, 2.0)  # inside BOTH blocks
    carrier.SetNthSeedBinding(0, segmentation.GetID(), betaID)
    carrier.Modified()

    alpha = None
    for action in table.retargetMenu(0).actions():
        text = action.text
        text = text() if callable(text) else text
        if text == "Alpha":
            alpha = action
    assert alpha is not None, "the touched-candidate list must offer Alpha."
    alpha.trigger()

    assert carrier.GetNthSeedBindingSegmentID(0) == alphaID, (
        "a retarget-menu pick must rebind the seed."
    )
    assert carrier.GetNthSeedLabel(0) == "Alpha", (
        "the seed label follows the new binding."
    )


# --------------------------------------------------------------------------- #
# OBSERVER teardown
# --------------------------------------------------------------------------- #


def test_cleanup_detaches_the_carrier_observer(qt_widgets):
    """``cleanup`` detaches the carrier observer so nothing survives shutdown.

    A parentless Qt widget holding a MRML observer crashes SlicerApp on
    shutdown (feedback_launched_widget_teardown_crash).  After ``cleanup``, a
    carrier ``ModifiedEvent`` no longer rebuilds the table.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "cleanup"):
        pytest.skip("VolumetrySeedsTableWidget has no cleanup seam (ADR-0027).")

    carrier.AddSeed(1.0, 0.0, 0.0)
    before = table.rowCount()

    table.cleanup()
    carrier.AddSeed(2.0, 0.0, 0.0)  # fires ModifiedEvent; observer is detached

    assert table.rowCount() == before, (
        "after cleanup, a carrier ModifiedEvent must NOT rebuild the table -- "
        "the observer was detached (feedback_launched_widget_teardown_crash)."
    )


# --------------------------------------------------------------------------- #
# ROW-SELECT event filter -- a press on a row's child control selects the row
# --------------------------------------------------------------------------- #


def test_row_children_carry_the_row_select_tag(qt_widgets):
    """Every seed-row control is tagged with its row's STABLE seed ID.

    The composite row widget covers the whole tree item, so a real click on
    "the row" lands on a child control and is consumed there -- the tree
    viewport never selects the item.  The row-select event filter needs each
    child tagged with its row key (a dynamic Qt property) to resolve the
    press back to the tree item.  The key is the carrier-minted stable ID
    (never the placement index): a deletion reshuffles indices but must not
    re-key surviving rows.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    carrier.AddSeed(1.0, 0.0, 0.0)
    if not hasattr(carrier, "GetNthSeedID"):
        pytest.skip("carrier has no GetNthSeedID -- the stable-ID slot has not landed.")
    seedID = carrier.GetNthSeedID(0)

    for control in (
        table.labelEdit(0),
        table.colourButton(0),
        table.overflowButton(0),
    ):
        assert control is not None
        assert control.property("volumetryRowSeed") == seedID, (
            "each seed-row control must carry the row's STABLE seed ID so the "
            "row-select event filter can select the row on a press."
        )


def test_press_on_a_seed_row_control_selects_the_row(qt_widgets):
    """The row-select seam makes a press on a child control select the row.

    ``_selectRowForWidget`` is the seam ``eventFilter`` delegates every
    mouse press to; selecting through it fires the SAME
    ``itemSelectionChanged`` path a viewport click drives (visibility
    restore + the carved-stripes highlight).  Without it, placing a seed and
    clicking its row showed no highlight at all in the real GUI (the press
    died in the line edit).
    """
    import qt

    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    carrier.AddSeed(1.0, 0.0, 0.0)
    assert not table.tree().selectedItems()

    table._selectRowForWidget(table.labelEdit(0))

    selected = table.tree().selectedItems()
    assert [item.data(0, qt.Qt.UserRole) for item in selected] == [0], (
        "a press on a seed row's child control must select that seed's row "
        "(the row-selection features are otherwise unreachable by a click)."
    )


def test_press_on_a_volume_row_control_selects_the_volume_row(qt_widgets):
    """A press on a VOLUME row's control selects the volume row (which clears
    a running seed highlight via the selection-change path)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "addVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no addVolume seam (ADR-0027).")

    volumeId = table.addVolume()

    table._selectRowForWidget(table.volumeLabelEdit(volumeId))

    selected = table.tree().selectedItems()
    tree = table.tree()
    assert selected and tree.indexOfTopLevelItem(selected[0]) == tree.indexOfTopLevelItem(
        table.volumeItem(volumeId)
    ), "a press on a volume row's child control must select the volume row."


# --------------------------------------------------------------------------- #
# EMPTY-CARVE CUE -- a pinned seed whose carved region is empty names it in
# row text (never a silent nothing; the stripes have nothing to draw)
# --------------------------------------------------------------------------- #


def _shown(widget):
    """True iff ``widget`` is explicitly shown (``isHidden`` tracks the
    setVisible state regardless of the never-shown test parent)."""
    hidden = widget.isHidden
    hidden = hidden() if callable(hidden) else hidden
    return not hidden


def test_pinning_an_empty_carve_seed_shows_the_cue(qt_widgets, monkeypatch):
    """Pinning a seed whose carve is EMPTY shows the explicit text cue on the
    row (``EMPTY_CARVE_MESSAGE``) -- silent nothing must not recur -- and the
    cue names the REMEDY (hide covering segments or retarget)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.VolumetrySeedsTableWidget import EMPTY_CARVE_MESSAGE

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(0.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "statusLabel") or not hasattr(table, "highlightButton"):
        pytest.skip("VolumetrySeedsTableWidget has no cue/pin seam (ADR-0027).")

    monkeypatch.setattr(table, "_carvedRegionIsEmpty", lambda index: True)

    table.highlightButton(0).setChecked(True)

    status = table.statusLabel(0)
    assert status is not None and _shown(status), (
        "an empty carve must surface the row cue, not a silent nothing."
    )
    text = status.text
    text = text() if callable(text) else text
    assert text == EMPTY_CARVE_MESSAGE
    assert "covered by segments above" in text, (
        "the cue must NAME the cause in plain text (ADR-0010)."
    )
    assert "hide covering segments" in text and "retarget" in text, (
        "the cue must NAME the remedy, not just the cause."
    )


def test_non_empty_carve_shows_no_cue_and_unpin_clears(qt_widgets, monkeypatch):
    """A normal (non-empty / unknown) carve keeps the pinned row cueless, and
    unpinning hides a previously shown cue."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(0.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "statusLabel") or not hasattr(table, "highlightButton"):
        pytest.skip("VolumetrySeedsTableWidget has no cue/pin seam (ADR-0027).")

    # Non-empty carve: no cue on pin.
    monkeypatch.setattr(table, "_carvedRegionIsEmpty", lambda index: False)
    button = table.highlightButton(0)
    button.setChecked(True)
    status = table.statusLabel(0)
    assert status is not None and not _shown(status), (
        "a non-empty carve must not show the empty-carve cue."
    )
    button.setChecked(False)

    # Empty carve shown on pin, then unpinning clears it.
    monkeypatch.setattr(table, "_carvedRegionIsEmpty", lambda index: True)
    button.setChecked(True)
    assert _shown(table.statusLabel(0))
    button.setChecked(False)
    assert not _shown(table.statusLabel(0)), (
        "unpinning must clear the seed cue."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
