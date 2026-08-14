# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the Pin-button hover-preview (static + dimmed).

Hovering an UNPINNED seed's Pin button previews that seed's stripes STATIC
(the widget stops ticking; the slice pipelines freeze the phase and dim) so
the surgeon can glance at what a seed measured without committing the pin.
Hover-out drops the preview and the PINNED seed's stripes (if any) resume.
The preview rides the SAME transient ``HighlightSeedID`` member under the
``preview:`` marker (``CarvedRegionStripes``) -- render state stays on the
shared display node (``feedback_layerdm_state_on_display_node``), never a
widget-local channel the pipelines cannot see.

Pins on the table widget:

* HOVER PUBLISHES THE PREVIEW -- the marked ID lands on the display node;
  the segment visibility is untouched.
* HOVER-OUT RESUMES THE PIN -- the member returns to the pinned seed's bare
  ID (or clears when nothing is pinned).
* THE PINNED SEED'S OWN BUTTON IS NOT A PREVIEW -- its stripes already show.
* TICKS ARE HELD WHILE PREVIEWING -- the march timer fires no
  ``STRIPE_TICK_EVENT`` (the preview is static by contract).
* PIN BUTTONS CARRY THE HOVER TAG -- the shared event filter resolves
  Enter/Leave to the seed through the dynamic property.

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


def _make_fixture(slicer, qt_widgets, seeds=2):
    carrier = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "HoverPreviewCarrier")
    if carrier is None or not hasattr(carrier, "GetNthSeedID"):
        pytest.skip(f"{SEEDS_NODE_CLASS} stable-ID carrier not available (ADR-0027).")
    display = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "HoverPreviewDisplay")
    if display is None or not hasattr(display, "GetHighlightSeedID"):
        pytest.skip(f"{DISPLAY_NODE_CLASS} HighlightSeedID member not available (ADR-0027).")
    for i in range(seeds):
        carrier.AddSeed(float(i), 0.0, 0.0)
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VolumetrySeedsTableWidget not importable ({exc!r}).")
    table = VolumetrySeedsTableWidget(carrier=carrier, displayNode=display)
    if not hasattr(table, "previewSeedID"):
        pytest.skip("VolumetrySeedsTableWidget has no hover-preview seam (ADR-0027).")
    qt_widgets.append(table)
    return carrier, display, table


def _raw_member(display):
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    return get_highlight_seed_id(display)


def test_hover_publishes_a_marked_preview(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import PREVIEW_PREFIX

    carrier, display, table = _make_fixture(slicer, qt_widgets)
    seedID = carrier.GetNthSeedID(1)

    table._startHoverPreview(seedID)  # noqa: SLF001 - the Enter-filter seam

    assert _raw_member(display) == f"{PREVIEW_PREFIX}{seedID}", (
        "the hover must publish the seed under the preview marker."
    )
    assert table.previewSeedID() == seedID


def test_hover_out_resumes_the_pinned_seed(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)
    pinnedID = carrier.GetNthSeedID(0)

    table.highlightButton(0).setChecked(True)
    table._startHoverPreview(carrier.GetNthSeedID(1))  # noqa: SLF001
    table._endHoverPreview()  # noqa: SLF001 - the Leave-filter seam

    assert _raw_member(display) == pinnedID, (
        "hover-out must restore the pinned seed's bare ID (its stripes resume)."
    )
    assert table.previewSeedID() == ""


def test_hover_out_clears_when_nothing_is_pinned(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)

    table._startHoverPreview(carrier.GetNthSeedID(1))  # noqa: SLF001
    table._endHoverPreview()  # noqa: SLF001

    assert _raw_member(display) == "", (
        "with no pin, hover-out clears the member entirely."
    )


def test_hovering_the_pinned_seeds_own_button_is_not_a_preview(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)
    pinnedID = carrier.GetNthSeedID(0)

    table.highlightButton(0).setChecked(True)
    table._startHoverPreview(pinnedID)  # noqa: SLF001

    assert _raw_member(display) == pinnedID, (
        "hovering the pinned seed's own Pin button must not re-publish a "
        "preview -- its stripes already show, marching."
    )
    assert table.previewSeedID() == ""


def test_ticks_are_held_while_previewing(qt_widgets):
    """The march timer fires no STRIPE_TICK_EVENT while a preview is up."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import STRIPE_TICK_EVENT

    carrier, display, table = _make_fixture(slicer, qt_widgets)
    ticks = []
    display.AddObserver(STRIPE_TICK_EVENT, lambda c, e: ticks.append(1))

    table.highlightButton(0).setChecked(True)
    table._onStripeTick()  # noqa: SLF001 - the timer seam
    assert len(ticks) == 1, "the pinned march ticks."

    table._startHoverPreview(carrier.GetNthSeedID(1))  # noqa: SLF001
    table._onStripeTick()  # noqa: SLF001
    assert len(ticks) == 1, (
        "no tick may fire while a preview is up -- the preview is STATIC."
    )

    table._endHoverPreview()  # noqa: SLF001
    table._onStripeTick()  # noqa: SLF001
    assert len(ticks) == 2, "the pinned march resumes after hover-out."


def test_preview_leaves_visibility_untouched(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)

    segmentation = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "HoverPreviewSegSrc"
    )
    segmentation.CreateDefaultDisplayNodes()
    segmentation.GetSegmentation().AddEmptySegment("Parenchyma", "Parenchyma")
    segmentation.GetSegmentation().AddEmptySegment("Tumor", "Tumor")
    table.setStructureSource(segmentation)
    segDisplay = segmentation.GetDisplayNode()
    segDisplay.SetSegmentVisibility("Parenchyma", False)
    segDisplay.SetSegmentVisibility("Tumor", True)

    table._startHoverPreview(carrier.GetNthSeedID(1))  # noqa: SLF001

    assert not segDisplay.GetSegmentVisibility("Parenchyma")
    assert segDisplay.GetSegmentVisibility("Tumor"), (
        "the hover-preview must never change the segment visibility."
    )


def test_pin_buttons_carry_the_hover_tag(qt_widgets):
    """The event-filter wiring: every Pin button is tagged with its seed's
    stable ID so Enter/Leave resolve to the right preview."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, table = _make_fixture(slicer, qt_widgets)

    for i in range(carrier.GetNumberOfSeeds()):
        button = table.highlightButton(i)
        assert button is not None
        assert button.property("volumetryPinSeed") == carrier.GetNthSeedID(i), (
            "each Pin button must carry its seed's stable ID for the "
            "hover-preview event filter."
        )


def test_a_pin_change_supersedes_the_preview(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)

    table._startHoverPreview(carrier.GetNthSeedID(1))  # noqa: SLF001
    table.highlightButton(0).setChecked(True)  # the pin lands mid-hover

    assert _raw_member(display) == carrier.GetNthSeedID(0), (
        "a pin change must supersede the hover preview."
    )
    assert table.previewSeedID() == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
