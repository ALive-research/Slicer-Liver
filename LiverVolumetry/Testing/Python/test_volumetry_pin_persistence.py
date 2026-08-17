# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- pin persistence on the module parameter node.

The pinned seed's STABLE ID is mirrored into the module parameter node
(``PinnedSeedID``): parameter nodes serialize with the scene and the
carrier-minted ID survives index shifts, so a saved scene resumes the pin
on module enter.  Pins:

* PIN WRITES THE PARAMETER -- checking a seed's Pin toggle lands its stable
  ID on the parameter node; unpinning clears it.
* EXIT KEEPS THE PARAMETER -- ``exit()`` stops the stripes (the timer, the
  live highlight) but must NOT erase the persisted pin.
* ENTER RESUMES THE PIN -- ``enter()`` re-raises the pin from the parameter
  node when the ID still resolves on the carrier.
* A STALE ID CLEARS -- an ID that no longer resolves (seed deleted, carrier
  gone) clears the parameter instead of resurrecting later.

The same enter/exit round trip carries the MODULE-SCOPED OVERLAY rule
(``territory-usability`` display lifecycle): nothing this module draws may
stay visible under another module, so ``exit()`` hides the seeds display node
(retiring the glyph / handle / stripe / annotation family the LayerDM
Pipelines draw off it) and ``enter()`` restores it -- while the surgeon's
SEGMENTATION visibility (their eye-list composition) is identical across the
round trip.  Pinned below.

HARNESS: launched Slicer (module widget + wrapped carrier).  SKIPS CLEANLY
bare via the shared guards; RUNS launched (ADR-0027).
"""

from __future__ import annotations

import pytest


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_widget_or_skip(slicer):
    from conftest import _require_qt_widget

    _require_qt_widget()
    from LiverVolumetry import LiverVolumetryWidget

    # Explicit parent: with parent=None, ScriptedLoadableModuleWidget's
    # __init__ auto-runs setup() (and show()), so the explicit setup()
    # below would run TWICE -- stacking two panels and registering
    # duplicate scene observers that outlive cleanup() (the destroyed-ui
    # 'enabled' storm, feedback_launched_widget_teardown_crash).
    import qt

    widgetParent = qt.QWidget()
    qt.QVBoxLayout(widgetParent)
    widget = LiverVolumetryWidget(widgetParent)
    widget.setup()
    return widget


def _pin_fixture(slicer, qt_widgets, seeds=2):
    """Module widget + carrier with ``seeds`` placed seeds + the seeds table."""
    from LiverVolumetry import PINNED_SEED_PARAMETER  # noqa: F401 - seam probe

    widget = _make_widget_or_skip(slicer)
    qt_widgets.append(widget)
    carrier = widget._ensureSeedsCarrier()
    if carrier is None or not hasattr(carrier, "GetNthSeedID"):
        pytest.skip("stable-ID seed carrier unavailable (launched build; ADR-0027).")
    # The stripes ride the shared display node; without it a pin cannot
    # raise, so the fixture ensures it like a real session does.
    if widget._ensureSeedsDisplayNode() is None:
        pytest.skip("seed display node unavailable (launched build; ADR-0027).")
    for i in range(seeds):
        carrier.AddSeed(float(i), 0.0, 0.0)
    table = widget._seedsTable
    if table is None or not hasattr(table, "pinnedSeedID"):
        pytest.skip("seeds table / pin seams unavailable (ADR-0027).")
    return widget, carrier, table


def _parameter(widget):
    from LiverVolumetry import PINNED_SEED_PARAMETER

    return widget._parameterNode.GetParameter(PINNED_SEED_PARAMETER)


def test_pinning_writes_the_parameter_and_unpinning_clears(qt_widgets):
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets)

    # Placement auto-pinned the LAST seed; the explicit toggle re-points.
    table.highlightButton(0).setChecked(True)
    assert _parameter(widget) == carrier.GetNthSeedID(0), (
        "pinning must mirror the seed's STABLE ID into the parameter node."
    )

    table.highlightButton(0).setChecked(False)
    assert _parameter(widget) == "", "unpinning must clear the parameter."


def test_placement_auto_pin_persists_too(qt_widgets):
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets, seeds=1)

    carrier.AddSeed(9.0, 0.0, 0.0)  # a placement (one-seed append)

    assert _parameter(widget) == carrier.GetNthSeedID(1), (
        "the placement auto-pin must persist like the toggle."
    )


def test_exit_keeps_the_parameter_and_enter_resumes(qt_widgets):
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets)
    pinnedID = carrier.GetNthSeedID(0)

    table.highlightButton(0).setChecked(True)
    widget.exit()

    assert table.pinnedSeedID() == "", "exit stops the live stripes."
    assert not table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "exit must stop the march timer."
    )
    assert _parameter(widget) == pinnedID, (
        "exit must KEEP the persisted pin -- only the live stripes stop."
    )

    widget.enter()

    assert table.pinnedSeedID() == pinnedID, (
        "enter must re-raise the pin from the parameter node."
    )
    assert table.highlightButton(0).isChecked(), (
        "the resumed pin re-checks its seed's toggle."
    )
    assert table._stripeTimer.isActive()  # noqa: SLF001 - timer seam


def test_a_stale_persisted_id_clears_on_enter(qt_widgets):
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets)
    from LiverVolumetry import PINNED_SEED_PARAMETER

    widget._parameterNode.SetParameter(PINNED_SEED_PARAMETER, "seed:gone")

    widget.enter()

    assert table.pinnedSeedID() == "", "a stale ID must not raise a pin."
    assert _parameter(widget) == "", (
        "a stale persisted ID must be CLEARED, never left to resurrect."
    )


def test_exit_hides_our_overlays_and_enter_restores_them(qt_widgets):
    """``exit()`` retires the overlay family; ``enter()`` brings it back.

    The seed glyphs (3D), slice handles, placement preview and pinned-seed
    stripes/annotation are all drawn by the LayerDM Pipelines bound to the
    seeds display node, and they honour its visibility -- so the display
    node's visibility IS the module-scoped overlay gate.
    """
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets)
    display = widget._seedsDisplayNode  # noqa: SLF001 - display-node seam

    table.highlightButton(0).setChecked(True)
    widget.exit()

    assert not bool(display.GetVisibility()), (
        "exit() must hide the seeds display node -- our overlays are "
        "module-scoped and may not survive a module switch."
    )
    assert table.pinnedSeedID() == "", "exit() also clears the live highlight."

    widget.enter()

    assert bool(display.GetVisibility()), (
        "enter() must restore our overlays so the workflow resumes as left."
    )
    assert table.pinnedSeedID() == carrier.GetNthSeedID(0), (
        "the persisted pin resumes with the restored overlays."
    )


def test_exit_enter_is_idempotent_and_survives_a_missing_display_node(qt_widgets):
    """Repeated / node-less enter-exit must never raise (crash-safe guards)."""
    slicer = _slicer_or_skip()
    widget, _carrier, _table = _pin_fixture(slicer, qt_widgets)
    display = widget._seedsDisplayNode  # noqa: SLF001 - display-node seam

    widget.exit()
    widget.exit()
    assert not bool(display.GetVisibility())
    widget.enter()
    widget.enter()
    assert bool(display.GetVisibility())

    # No display node at all (a session that never placed a seed): the
    # visibility writes must degrade to a no-op, not raise.
    widget._seedsDisplayNode = None  # noqa: SLF001 - simulate the pre-placement state
    widget.exit()
    widget.enter()


def test_our_overlay_scoping_leaves_segment_visibility_untouched(qt_widgets):
    """The surgeon's eye-list composition is IDENTICAL across exit/enter.

    Only OUR overlays move on a module switch; per-segment visibility on the
    input segmentation belongs to the surgeon (the visibility-composed carve
    reads it), so an exit/enter round trip must not rewrite a single segment.
    """
    slicer = _slicer_or_skip()
    widget, _carrier, _table = _pin_fixture(slicer, qt_widgets)

    segmentation = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "OverlayScopeSegmentation")
    if segmentation is None:
        pytest.skip("vtkMRMLSegmentationNode unavailable (ADR-0027).")
    segmentation.CreateDefaultDisplayNodes()
    for name in ("A", "B", "C"):
        segmentation.GetSegmentation().AddEmptySegment(name, name)
    segmentationDisplay = segmentation.GetDisplayNode()
    if segmentationDisplay is None:
        pytest.skip("segmentation display node unavailable (ADR-0027).")
    segmentIDs = list(segmentation.GetSegmentation().GetSegmentIDs())
    # A deliberately MIXED composition -- the thing that must survive.
    for index, segmentID in enumerate(segmentIDs):
        segmentationDisplay.SetSegmentVisibility(segmentID, index % 2 == 0)
    before = {
        segmentID: bool(segmentationDisplay.GetSegmentVisibility(segmentID))
        for segmentID in segmentIDs
    }

    widget.exit()
    widget.enter()

    after = {
        segmentID: bool(segmentationDisplay.GetSegmentVisibility(segmentID))
        for segmentID in segmentIDs
    }
    assert after == before, (
        "an exit/enter round trip must not touch the surgeon's per-segment "
        "visibility -- only OUR overlays are module-scoped."
    )


def test_deleting_the_pinned_seed_clears_the_parameter(qt_widgets):
    slicer = _slicer_or_skip()
    widget, carrier, table = _pin_fixture(slicer, qt_widgets)
    pinnedID = carrier.GetNthSeedID(1)

    table.highlightButton(1).setChecked(True)
    assert _parameter(widget) == pinnedID

    carrier.RemoveNthSeed(1)

    assert _parameter(widget) == "", (
        "retiring the pin (its seed was deleted) must clear the parameter."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
