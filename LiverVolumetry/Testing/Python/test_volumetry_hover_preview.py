# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- hovering the seed rows changes NOTHING.

A hover is an accident of moving the cursor, so it must never disturb
committed render state.  An earlier revision previewed a hovered seed's
stripes; with a pin available that made the two indistinguishable -- the
surgeon could not tell whether the stripes on screen were the pinned
region or whatever the cursor happened to be passing over.  The Pin
toggle (and placement) are now the ONLY drivers of the highlight.

Pins on the table widget:

* HOVER OVER AN UNPINNED SEED'S PIN BUTTON LEAVES THE PUBLISHED HIGHLIGHT
  UNTOUCHED -- with a pin up, and with nothing pinned.
* THE MARCH KEEPS RUNNING ACROSS A HOVER -- no static/dimmed interlude.
* SEGMENT VISIBILITY IS UNTOUCHED BY HOVER (as it always was).

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
    # The overlay gate is default-CLOSED and opened by the module's enter()
    # (PointPlacementState.set_overlays_visible).  A Pipeline test mints its own
    # display node and has no widget, so it models a SHOWING module explicitly.
    from slicer_pytest_support import open_module_overlay_gate

    open_module_overlay_gate(display, "LiverVolumetry")
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


def test_hover_does_not_change_the_published_highlight(qt_widgets):
    """A pinned seed stays published while the cursor crosses other rows."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    carrier, display, table = _make_fixture(slicer, qt_widgets)
    pinnedID = carrier.GetNthSeedID(0)
    table.highlightButton(0).setChecked(True)
    assert get_highlight_seed_id(display) == pinnedID

    # Simulate the cursor crossing another seed's Pin button: the shared
    # event filter must ignore Enter/Leave entirely.
    other = table.highlightButton(1)
    qt = __import__("qt")
    table.eventFilter(other, qt.QEvent(qt.QEvent.Enter))
    assert get_highlight_seed_id(display) == pinnedID, (
        "hover must not steal the highlight from the pinned seed."
    )
    table.eventFilter(other, qt.QEvent(qt.QEvent.Leave))
    assert get_highlight_seed_id(display) == pinnedID


def test_hover_publishes_nothing_when_no_seed_is_pinned(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    _carrier, display, table = _make_fixture(slicer, qt_widgets)
    qt = __import__("qt")

    table.eventFilter(table.highlightButton(1), qt.QEvent(qt.QEvent.Enter))

    assert get_highlight_seed_id(display) == "", (
        "with nothing pinned, a hover must leave the highlight empty."
    )


def test_the_march_keeps_running_across_a_hover(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    _carrier, _display, table = _make_fixture(slicer, qt_widgets)
    qt = __import__("qt")

    table.highlightButton(0).setChecked(True)
    assert table._stripeTimer.isActive()  # noqa: SLF001 - timer seam

    table.eventFilter(table.highlightButton(1), qt.QEvent(qt.QEvent.Enter))

    assert table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "a hover introduces no static interlude: the march continues."
    )
