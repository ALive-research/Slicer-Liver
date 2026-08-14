# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- "Restore placement view": explicit, symmetric, depth one.

The visibility restore is DECOUPLED from the Pin toggle (the P1 trap: a
"highlight" toggle that silently rewrote the surgeon's eye-list composition).
Restoring a seed's placement-time visibility snapshot is its own explicit
affordance with symmetric, depth-ONE semantics:

* ENTER captures "my view" -- restoring a seed first captures the CURRENT
  visibility (one widget-side slot), then shows exactly the snapshot.
* RETURN is symmetric -- "Return to my view" puts the captured composition
  back and ends the context.
* SWITCH reuses the capture -- restoring a DIFFERENT seed while restored
  does NOT re-capture; returning afterwards lands on the ORIGINAL "my view".
* TAKEOVER ends the context -- a MANUAL eye-list change while restored ends
  the restored context; the widget never re-asserts visibility against the
  user, and the capture is dropped (the user's new composition wins).
* STALE HARD-GUARD -- a snapshot sharing NO segment with the segmentation's
  current segment IDs REFUSES the restore (named in the banner slot); the
  view is never blanked.
* PLACEMENT GUARD -- arming placement while restored first returns to "my
  view", so new snapshots are always minted from the surgeon's own
  composition.
* BANNER -- while restored, a text line names the restored seed (+ volume)
  with the inline return button (ADR-0010); it clears on return / switch
  target change / takeover / module exit (``stopHighlight``).

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


def _make_carrier_or_skip(slicer, name="PinRestoreCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    if not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} has no SetNthSeedVisibilityContext (ADR-0027)."
        )
    return node


def _make_display_or_skip(slicer, name="PinRestoreDisplayTest"):
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
    if not hasattr(table, "restorePlacementView"):
        pytest.skip(
            "VolumetrySeedsTableWidget has no restorePlacementView seam (ADR-0027)."
        )
    return table


def _make_segmentation(slicer, name="PinRestoreSegSrc"):
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


def _visible_ids(segmentation):
    display = segmentation.GetDisplayNode()
    ids = []
    for n in range(segmentation.GetSegmentation().GetNumberOfSegments()):
        segmentID = segmentation.GetSegmentation().GetNthSegmentID(n)
        if display.GetSegmentVisibility(segmentID):
            ids.append(segmentID)
    return set(ids)


def _set_visible(segmentation, visible):
    display = segmentation.GetDisplayNode()
    for n in range(segmentation.GetSegmentation().GetNumberOfSegments()):
        segmentID = segmentation.GetSegmentation().GetNthSegmentID(n)
        display.SetSegmentVisibility(segmentID, segmentID in visible)


def _shown(widget):
    """True iff ``widget`` is explicitly shown (setVisible(True)).

    ``isVisible()`` is False for any child of a never-shown parentless test
    widget, so the assertions read ``isHidden()`` -- which tracks the
    explicit setVisible state regardless of ancestor show state.
    """
    hidden = widget.isHidden
    hidden = hidden() if callable(hidden) else hidden
    return not hidden


def _restore_fixture(slicer, qt_widgets, contexts):
    """Carrier + display + segmentation + table with one seed per context."""
    carrier = _make_carrier_or_skip(slicer)
    display = _make_display_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    for i, context in enumerate(contexts):
        carrier.AddSeed(float(i), 0.0, 0.0)
        _set_context(carrier, i, context)
    table = _make_table_or_skip(slicer, carrier, display)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)
    return carrier, display, segmentation, table


# --------------------------------------------------------------------------- #
# Enter + symmetric return
# --------------------------------------------------------------------------- #


def test_restore_shows_snapshot_and_return_puts_my_view_back(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})  # the surgeon's own composition

    assert table.restorePlacementView(carrier.GetNthSeedID(0)) is True

    assert _visible_ids(segmentation) == {"Segment_1", "Parenchyma"}, (
        "the restore must show exactly the snapshot's segments."
    )
    assert table.restoredSeedID() == carrier.GetNthSeedID(0)

    table.returnToMyView()

    assert _visible_ids(segmentation) == {"Tumor"}, (
        "Return to my view must put the pre-restore composition back."
    )
    assert table.restoredSeedID() == "", "returning ends the restored context."


def test_restore_never_touches_the_pin(qt_widgets):
    """The restore raises no stripes and the pin raises no restore."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Parenchyma"]]
    )
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    assert get_highlight_seed_id(display) == "", (
        "Restore placement view must not publish a stripe highlight."
    )


# --------------------------------------------------------------------------- #
# Switch reuses the ONE capture (depth one)
# --------------------------------------------------------------------------- #


def test_switching_restored_seed_reuses_the_original_capture(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer,
        qt_widgets,
        [["Segment_1", "Parenchyma"], ["Tumor", "Parenchyma"]],
    )

    _set_visible(segmentation, {"Tumor"})  # "my view"

    table.restorePlacementView(carrier.GetNthSeedID(0))
    table.restorePlacementView(carrier.GetNthSeedID(1))  # the switch

    assert _visible_ids(segmentation) == {"Tumor", "Parenchyma"}, (
        "the switch must show the SECOND seed's snapshot."
    )
    assert table.restoredSeedID() == carrier.GetNthSeedID(1)

    table.returnToMyView()

    assert _visible_ids(segmentation) == {"Tumor"}, (
        "return after a switch must land on the ORIGINAL capture (depth one, "
        "never the first seed's snapshot)."
    )


# --------------------------------------------------------------------------- #
# User takeover ends the context (never fight the eye list)
# --------------------------------------------------------------------------- #


def test_manual_visibility_change_ends_the_restored_context(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    # The user flips an eye by hand (the takeover).
    segmentation.GetDisplayNode().SetSegmentVisibility("Tumor", True)

    assert table.restoredSeedID() == "", (
        "a manual eye-list change while restored must END the restored "
        "context -- the user took over."
    )
    assert not _shown(table.restoreBanner()), "the banner clears on takeover."
    assert _visible_ids(segmentation) == {"Segment_1", "Parenchyma", "Tumor"}, (
        "the widget must NEVER re-assert visibility against the user."
    )


def test_unrelated_display_edit_keeps_the_restored_context(qt_widgets):
    """A display-node edit that does not change the visible set (colour,
    opacity) is not a takeover."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    segmentation.GetDisplayNode().SetSegmentOpacity3D("Parenchyma", 0.5)

    assert table.restoredSeedID() == carrier.GetNthSeedID(0), (
        "an edit that leaves the visible set unchanged must not end the "
        "restored context."
    )


# --------------------------------------------------------------------------- #
# Stale-snapshot hard-guard
# --------------------------------------------------------------------------- #


def test_stale_snapshot_refuses_the_restore(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.VolumetrySeedsTableWidget import STALE_SNAPSHOT_MESSAGE

    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["GoneA", "GoneB"]]  # no overlap with the source
    )

    _set_visible(segmentation, {"Tumor"})

    assert table.restorePlacementView(carrier.GetNthSeedID(0)) is False, (
        "a snapshot with no surviving segment must REFUSE the restore."
    )
    assert _visible_ids(segmentation) == {"Tumor"}, (
        "the refused restore must not blank or change the view."
    )
    assert table.restoredSeedID() == ""
    label = table.restoreBannerLabel()
    text = label.text
    text = text() if callable(text) else text
    assert text == STALE_SNAPSHOT_MESSAGE, (
        "the refusal must be NAMED in the banner slot (ADR-0010)."
    )


def test_empty_snapshot_counts_as_stale(qt_widgets):
    """A legacy snapshotless seed has nothing to restore -- refused, view kept."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [[]]
    )

    _set_visible(segmentation, {"Tumor"})

    assert table.restorePlacementView(carrier.GetNthSeedID(0)) is False
    assert _visible_ids(segmentation) == {"Tumor"}


# --------------------------------------------------------------------------- #
# Placement guard
# --------------------------------------------------------------------------- #


def test_arming_placement_returns_to_my_view_first(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )
    if not hasattr(table, "addVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no addVolume seam (ADR-0027).")

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    table.addVolume()  # arms placement into the new volume

    assert table.restoredSeedID() == "", (
        "arming placement while restored must first end the restored context."
    )
    assert _visible_ids(segmentation) == {"Tumor"}, (
        "the placement guard returns to MY view so new snapshots are minted "
        "from the surgeon's own composition."
    )


# --------------------------------------------------------------------------- #
# Banner
# --------------------------------------------------------------------------- #


def test_banner_names_the_restored_seed_and_volume(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.VolumetrySeedsTableWidget import RESTORE_BANNER_PREFIX

    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Parenchyma"]]
    )
    carrier.SetNthSeedLabel(0, "Wedge seed")
    if hasattr(carrier, "AddVolume"):
        carrier.AddVolume("V1")
        carrier.SetVolumeLabel("V1", "Left lobe")
        carrier.SetNthSeedVolume(0, "V1")

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    assert _shown(table.restoreBanner()), "the banner must show while a restored context is active."
    label = table.restoreBannerLabel()
    text = label.text
    text = text() if callable(text) else text
    assert text.startswith(RESTORE_BANNER_PREFIX)
    assert "Wedge seed" in text, "the banner names the seed in text (ADR-0010)."
    if hasattr(carrier, "AddVolume"):
        assert "Left lobe" in text, "the banner names the volume in text."
    assert _shown(table.returnToMyViewButton()), "the inline return button rides the banner."


def test_return_button_returns_and_clears_the_banner(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    table.returnToMyViewButton().click()

    assert _visible_ids(segmentation) == {"Tumor"}
    assert not _shown(table.restoreBanner()), "the banner clears on return."


def test_module_exit_ends_the_restored_context_without_touching_the_view(qt_widgets):
    """``stopHighlight`` (the module-exit hook) clears the banner + context
    but leaves the visibility exactly as the surgeon sees it."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    table.stopHighlight()

    assert table.restoredSeedID() == ""
    assert not _shown(table.restoreBanner()), "the banner clears on module exit."
    assert _visible_ids(segmentation) == {"Segment_1", "Parenchyma"}, (
        "module exit must not flip the visibility under the surgeon."
    )


def test_deleting_the_restored_seed_ends_the_context(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Parenchyma"]]
    )

    _set_visible(segmentation, {"Tumor"})
    table.restorePlacementView(carrier.GetNthSeedID(0))

    carrier.RemoveNthSeed(0)

    assert table.restoredSeedID() == "", (
        "deleting the restored seed must end the restored context."
    )
    assert not _shown(table.restoreBanner())


# --------------------------------------------------------------------------- #
# Divergence chip (pinned row, live vs snapshot)
# --------------------------------------------------------------------------- #


def test_chip_appears_when_pinned_view_diverges(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.VolumetrySeedsTableWidget import DIVERGENCE_CHIP_TEXT

    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )
    if not hasattr(table, "divergenceChip"):
        pytest.skip("VolumetrySeedsTableWidget has no divergenceChip seam (ADR-0027).")

    _set_visible(segmentation, {"Segment_1", "Parenchyma"})  # matches snapshot
    table.highlightButton(0).setChecked(True)

    chip = table.divergenceChip(0)
    assert chip is not None
    assert not _shown(chip), "matching live view shows no chip."
    text = chip.text
    text = text() if callable(text) else text
    assert text == DIVERGENCE_CHIP_TEXT, (
        "the chip is plain text naming the divergence (not a tooltip)."
    )

    # The user hides a snapshot segment: the live view now diverges.
    segmentation.GetDisplayNode().SetSegmentVisibility("Segment_1", False)

    assert _shown(table.divergenceChip(0)), (
        "the PINNED row must chip when live visibility != the snapshot."
    )


def test_chip_hides_when_unpinned_or_matching_again(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )
    if not hasattr(table, "divergenceChip"):
        pytest.skip("VolumetrySeedsTableWidget has no divergenceChip seam (ADR-0027).")

    _set_visible(segmentation, {"Tumor"})
    table.highlightButton(0).setChecked(True)
    assert _shown(table.divergenceChip(0))

    # Back to the snapshot composition by hand: the chip clears.
    _set_visible(segmentation, {"Segment_1", "Parenchyma"})
    assert not _shown(table.divergenceChip(0)), (
        "a live view matching the snapshot again must clear the chip."
    )

    # Diverge again, then unpin: the chip clears with the pin.
    _set_visible(segmentation, {"Tumor"})
    assert _shown(table.divergenceChip(0))
    table.highlightButton(0).setChecked(False)
    assert not _shown(table.divergenceChip(0)), "no pin, no chip."


def test_chip_click_restores_the_placement_view(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, segmentation, table = _restore_fixture(
        slicer, qt_widgets, [["Segment_1", "Parenchyma"]]
    )
    if not hasattr(table, "divergenceChip"):
        pytest.skip("VolumetrySeedsTableWidget has no divergenceChip seam (ADR-0027).")

    _set_visible(segmentation, {"Tumor"})
    table.highlightButton(0).setChecked(True)
    assert _shown(table.divergenceChip(0))

    table.divergenceChip(0).click()

    assert _visible_ids(segmentation) == {"Segment_1", "Parenchyma"}, (
        "the chip doubles as the Restore placement view entry point."
    )
    assert table.restoredSeedID() == carrier.GetNthSeedID(0)
    assert not _shown(table.divergenceChip(0)), (
        "after the restore the live view matches -- the chip clears."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
