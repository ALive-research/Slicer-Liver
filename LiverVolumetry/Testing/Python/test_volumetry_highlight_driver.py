# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the carved-region highlight's TWO drivers.

The stripes highlight is DECOUPLED from row selection: the seed rows are dense
with actionable controls, so a selection-driven highlight fired on every stray
click and a real placement did not reliably select a row at all.  The two
drivers are:

* PLACEMENT -- a one-seed carrier append publishes ``highlightSeed`` for the
  new seed directly (no row selection, no visibility restore: the seed's
  snapshot equals the live visibility at placement).
* the per-seed HIGHLIGHT toggle -- checking it RESTORES the seed's visibility
  snapshot (``VisibilityCarve``) and publishes its highlight; the toggles are
  exclusive; unchecking clears the highlight.

Pins on the table widget:

* TOGGLE RESTORES + PUBLISHES -- checking a seed's Highlight button flips the
  structure-source visibility to exactly the seed's snapshot and publishes
  ``highlightSeed`` on the shared display node.
* EMPTY SNAPSHOT IS A NO-OP -- a legacy seed with no context must not blank
  the view.
* EXCLUSIVITY -- checking another seed's toggle moves the highlight and
  unchecks the first.
* UNTOGGLE CLEARS -- unchecking clears ``highlightSeed`` back to -1.
* PLACEMENT AUTO-HIGHLIGHTS -- a carrier append publishes the new seed's
  highlight WITHOUT selecting its row and WITHOUT touching visibility.
* SELECTION IS INERT -- selecting a seed row changes neither the highlight
  nor the visibility (selection is plain row UX).
* A11Y TEXT -- the seed row names its owning segment + context in text
  (tooltip), never colour/animation alone (ADR-0010).

HARNESS: launched Slicer (Qt + wrapped carrier + display node).  SKIPS
CLEANLY bare via the shared guards; RUNS launched (ADR-0027).
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _qt_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_carrier_or_skip(slicer, name="HighlightDriverCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    if not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} has no SetNthSeedVisibilityContext (ADR-0027)."
        )
    return node


def _make_display_or_skip(slicer, name="HighlightDriverDisplayTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{DISPLAY_NODE_CLASS} not registered (launched build; ADR-0027).")
    return node


def _make_table_or_skip(slicer, carrier, display=None):
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VolumetrySeedsTableWidget not importable ({exc!r}).")
    table = VolumetrySeedsTableWidget(carrier=carrier, displayNode=display)
    if not hasattr(table, "highlightButton"):
        pytest.skip("VolumetrySeedsTableWidget has no highlightButton seam (ADR-0027).")
    return table


def _highlight_seed(display):
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed

    return get_highlight_seed(display)


def _make_segmentation(slicer, name="HighlightDriverSegSrc"):
    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", name)
    segmentation.CreateDefaultDisplayNodes()
    for segmentID, segmentName in (
        ("Parenchyma", "Parenchyma"),
        ("Segment_1", "Segment 1"),
        ("Tumor", "Tumor"),
    ):
        segmentation.GetSegmentation().AddEmptySegment(segmentID, segmentName)
    return segmentation


def _set_context(carrier, index, context):
    import vtk

    ids = vtk.vtkStringArray()
    for segmentID in context:
        ids.InsertNextValue(segmentID)
    carrier.SetNthSeedVisibilityContext(index, ids)


def _select_seed_row(table, seedIndex):
    """Select the tree item carrying ``seedIndex`` (manual walk; the item
    iterator is not wrapped into Slicer's ``qt`` namespace)."""
    import qt

    tree = table.tree()
    for t in range(tree.topLevelItemCount):
        top = tree.topLevelItem(t)
        for c in range(top.childCount()):
            child = top.child(c)
            if child.data(0, qt.Qt.UserRole) == seedIndex:
                tree.setCurrentItem(child)
                return True
    return False


# --------------------------------------------------------------------------- #
# The Highlight toggle -- restore + publish, exclusivity, clear
# --------------------------------------------------------------------------- #


def test_toggling_highlight_restores_snapshot_and_publishes(qt_widgets):
    """Checking a seed's Highlight button restores its snapshot and publishes
    ``highlightSeed`` on the shared display node."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    segDisplay = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "Parenchyma")
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    # Start from a DIFFERENT live visibility so the restore is observable.
    segDisplay.SetSegmentVisibility("Parenchyma", False)
    segDisplay.SetSegmentVisibility("Segment_1", False)
    segDisplay.SetSegmentVisibility("Tumor", True)

    button = table.highlightButton(0)
    assert button is not None, "the seed row must carry a Highlight toggle."
    button.setChecked(True)

    assert segDisplay.GetSegmentVisibility("Parenchyma"), (
        "the Highlight toggle must SHOW the snapshot's segments."
    )
    assert segDisplay.GetSegmentVisibility("Segment_1")
    assert not segDisplay.GetSegmentVisibility("Tumor"), (
        "the Highlight toggle must HIDE segments outside the snapshot."
    )
    assert _highlight_seed(display) == 0, (
        "the Highlight toggle must publish highlightSeed for its seed."
    )


def test_toggling_a_snapshotless_seed_keeps_the_view(qt_widgets):
    """A legacy seed (empty context) must not blank the live visibility."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    segDisplay = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)  # no context snapshot

    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    segDisplay.SetSegmentVisibility("Tumor", True)

    table.highlightButton(0).setChecked(True)

    assert segDisplay.GetSegmentVisibility("Tumor"), (
        "an empty snapshot is a NO-OP -- the live view stays."
    )
    assert _highlight_seed(display) == 0, (
        "the highlight still publishes for a snapshotless seed."
    )


def test_highlight_toggles_are_exclusive(qt_widgets):
    """Checking another seed's toggle moves the highlight + unchecks the first."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    carrier.AddSeed(1.0, 0.0, 0.0)
    carrier.AddSeed(2.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)

    table.highlightButton(0).setChecked(True)
    assert _highlight_seed(display) == 0

    table.highlightButton(1).setChecked(True)

    assert _highlight_seed(display) == 1, (
        "checking another seed's toggle must move the highlight."
    )
    assert not table.highlightButton(0).isChecked(), (
        "the toggles are exclusive: checking one unchecks the others."
    )
    assert table.highlightButton(1).isChecked()


def test_unchecking_the_toggle_clears_the_highlight(qt_widgets):
    """Unchecking clears ``highlightSeed`` (back to -1) + stops the march."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    carrier.AddSeed(1.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)

    button = table.highlightButton(0)
    button.setChecked(True)
    assert _highlight_seed(display) == 0

    button.setChecked(False)

    assert _highlight_seed(display) == -1, (
        "unchecking the Highlight toggle must clear the published highlight."
    )
    assert not table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "clearing the highlight must stop the stripe phase timer."
    )


# --------------------------------------------------------------------------- #
# Placement -- publishes the highlight directly, no selection, no restore
# --------------------------------------------------------------------------- #


def test_placement_publishes_the_highlight_without_selection(qt_widgets):
    """A one-seed carrier append (a placement) publishes the new seed's
    highlight directly -- no row is selected, and the toggle states follow."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    carrier.AddSeed(1.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)

    carrier.AddSeed(2.0, 0.0, 0.0)  # the placement (fires ModifiedEvent)

    assert _highlight_seed(display) == 1, (
        "placing a seed must publish its highlight IMMEDIATELY (the surgeon "
        "sees the just-measured region striped with no row interaction)."
    )
    assert not table.tree().selectedItems(), (
        "placement must NOT select the row -- the highlight is decoupled "
        "from selection."
    )
    assert table.highlightButton(1).isChecked(), (
        "the new seed's Highlight toggle must read on after placement."
    )
    assert table._stripeTimer.isActive()  # noqa: SLF001 - timer seam


def test_placement_repoints_an_existing_highlight(qt_widgets):
    """A new placement re-points the highlight + updates the checked states."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    carrier.AddSeed(1.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)

    table.highlightButton(0).setChecked(True)
    carrier.AddSeed(2.0, 0.0, 0.0)  # the placement

    assert _highlight_seed(display) == 1
    assert not table.highlightButton(0).isChecked(), (
        "a placement re-points the highlight: the old toggle unchecks."
    )
    assert table.highlightButton(1).isChecked()


def test_placement_does_not_restore_visibility(qt_widgets):
    """Placement never restores a context -- the live visibility stays."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    segDisplay = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    segDisplay.SetSegmentVisibility("Parenchyma", False)
    segDisplay.SetSegmentVisibility("Segment_1", False)
    segDisplay.SetSegmentVisibility("Tumor", True)

    carrier.AddSeed(2.0, 0.0, 0.0)  # the placement

    assert not segDisplay.GetSegmentVisibility("Parenchyma"), (
        "placement must NOT restore any seed's visibility context."
    )
    assert segDisplay.GetSegmentVisibility("Tumor")
    assert _highlight_seed(display) == 1


# --------------------------------------------------------------------------- #
# Selection is inert -- plain row UX, no side effects
# --------------------------------------------------------------------------- #


def test_selecting_a_seed_row_has_no_side_effects(qt_widgets):
    """Selecting a seed row changes neither the highlight nor the visibility."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    segDisplay = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    segDisplay.SetSegmentVisibility("Parenchyma", False)
    segDisplay.SetSegmentVisibility("Segment_1", False)
    segDisplay.SetSegmentVisibility("Tumor", True)

    assert _select_seed_row(table, 0), "the seed row must be selectable."

    assert _highlight_seed(display) == -1, (
        "row selection must NOT publish a highlight (decoupled driver)."
    )
    assert not segDisplay.GetSegmentVisibility("Parenchyma"), (
        "row selection must NOT restore the visibility context."
    )
    assert segDisplay.GetSegmentVisibility("Tumor")
    assert not table.highlightButton(0).isChecked()


def test_selection_does_not_clear_an_active_highlight(qt_widgets):
    """Moving the selection (even to a volume row) leaves the toggle-driven
    highlight in place -- only the toggle / a placement / a removal moves it."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    carrier.AddSeed(1.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)

    table.highlightButton(0).setChecked(True)

    volumeId = table.volumeIds()[0]
    table.tree().setCurrentItem(table.volumeItem(volumeId))

    assert _highlight_seed(display) == 0, (
        "selection changes must not clear the toggle-driven highlight."
    )
    assert table.highlightButton(0).isChecked()


# --------------------------------------------------------------------------- #
# A11y -- the row names owner + context in text
# --------------------------------------------------------------------------- #


def test_seed_row_names_owner_and_context_in_text(qt_widgets):
    """The seed row's text (tooltip) names the owning segment + the context
    (ADR-0010: never colour/animation alone)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation = _make_segmentation(slicer)

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "Parenchyma")
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    row = table._seed_rows.get(0)  # noqa: SLF001 - introspection seam
    assert row is not None
    tip = row["widget"].toolTip
    tip = tip() if callable(tip) else tip
    assert "Parenchyma" in tip, "the row text must name the owning segment."
    assert "Segment 1" in tip, "the row text must name the context segments."


def test_highlight_toggle_carries_text_and_tooltip(qt_widgets):
    """The Highlight toggle is named in text + tooltip (ADR-0010)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(0.0, 0.0, 0.0)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    button = table.highlightButton(0)
    assert button is not None
    text = button.text
    text = text() if callable(text) else text
    assert text == "Highlight"
    tip = button.toolTip
    tip = tip() if callable(tip) else tip
    assert "striped overlay" in tip and "restores the visibility" in tip, (
        "the toggle's tooltip must say what it shows AND that it restores "
        "the placement visibility (ADR-0010)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
