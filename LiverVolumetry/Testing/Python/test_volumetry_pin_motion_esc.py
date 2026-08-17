# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- bounded pin motion, on-slice identity text, ESC.

Three view-side finishing contracts:

* CONTINUOUS MARCH -- the pin's stripes march for as long as the pin is
  up: a frozen stripe texture reads as a rendering fault and cannot be
  told apart from a stuck view, so the motion IS the "this overlay is
  live" signal.  What bounds it is module ``exit()`` (nothing of ours
  ticks in the background), not a timeout.
* ON-SLICE TEXT -- while pinned, the slice pipeline's corner annotation
  names the pinned seed + volume in TEXT (identity is never colour-alone
  in the view, ADR-0010); a hover preview shows no annotation; unpinning
  clears it.
* ESC -- while placement is armed, Escape (a panel-scoped shortcut on the
  seeds table) cancels the arm: disarm + the Place toggle unchecks.  ESC
  does NOT clear the pin.

HARNESS: launched Slicer (Qt + wrapped carrier + display node; the
annotation contract also needs the LayerDM slice base).  SKIPS CLEANLY
bare via the shared guards; RUNS launched (ADR-0027).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "SlicerLiverInteractionLib",
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

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
    carrier = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "PinMotionCarrier")
    if carrier is None or not hasattr(carrier, "GetNthSeedID"):
        pytest.skip("stable-ID seed carrier unavailable (launched build; ADR-0027).")
    display = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "PinMotionDisplay")
    if display is None or not hasattr(display, "GetHighlightSeedID"):
        pytest.skip("HighlightSeedID display member unavailable (ADR-0027).")
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
    qt_widgets.append(table)
    return carrier, display, table


# --------------------------------------------------------------------------- #
# Idle-static (bounded motion)
# --------------------------------------------------------------------------- #


def test_the_march_never_stops_while_the_pin_is_up(qt_widgets):
    """Many ticks in, the timer is STILL running and the pin still published.

    The march used to stop after a fixed idle interval, leaving a frozen
    texture that reads as a rendering fault.  Motion now lasts exactly as
    long as the pin.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    carrier, display, table = _make_fixture(slicer, qt_widgets)

    table.highlightButton(0).setChecked(True)
    assert table._stripeTimer.isActive()  # noqa: SLF001 - timer seam

    # Far more ticks than the retired 10 s bound would have allowed.
    for _ in range(500):
        table._onStripeTick()  # noqa: SLF001

    assert table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "the march must not time out: a frozen texture reads as a fault."
    )
    assert get_highlight_seed_id(display) == carrier.GetNthSeedID(0)
    assert table.pinnedSeedID() == carrier.GetNthSeedID(0)


def test_a_pin_change_keeps_the_march_running(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, table = _make_fixture(slicer, qt_widgets)

    table.highlightButton(0).setChecked(True)
    for _ in range(50):
        table._onStripeTick()  # noqa: SLF001

    table.highlightButton(1).setChecked(True)  # the pin change

    assert table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "a pin change keeps the march running for the new pin."
    )
    assert table.pinnedSeedID() == carrier.GetNthSeedID(1)


# --------------------------------------------------------------------------- #
# ESC cancels an armed placement (and nothing else)
# --------------------------------------------------------------------------- #


def test_escape_disarms_and_unchecks_the_place_toggle(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from PointPlacementState import PointPlacementState

    carrier, display, table = _make_fixture(slicer, qt_widgets)
    if not hasattr(table, "cancelArmedPlacement"):
        pytest.skip("cancelArmedPlacement seam absent (ADR-0027).")

    volumeId = table.addVolume()  # arms into the new volume
    state = PointPlacementState("LiverVolumetry")
    assert state.is_armed(display)
    assert table.placeButton(volumeId).isChecked()

    table.highlightButton(0).setChecked(True)  # a live pin ESC must not touch

    table.cancelArmedPlacement()  # the ESC shortcut's slot

    assert not state.is_armed(display), "ESC must disarm placement."
    assert not table.placeButton(volumeId).isChecked(), (
        "ESC must uncheck the armed volume's Place toggle."
    )
    assert table.pinnedSeedID() == carrier.GetNthSeedID(0), (
        "ESC cancels the ARM only -- never the pin."
    )


def test_escape_is_a_noop_when_nothing_is_armed(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, display, table = _make_fixture(slicer, qt_widgets)
    if not hasattr(table, "cancelArmedPlacement"):
        pytest.skip("cancelArmedPlacement seam absent (ADR-0027).")

    table.highlightButton(0).setChecked(True)
    table.cancelArmedPlacement()

    assert table.pinnedSeedID() == carrier.GetNthSeedID(0), (
        "a disarmed ESC changes nothing."
    )


def test_escape_shortcut_is_panel_scoped(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    import qt

    _carrier, _display, table = _make_fixture(slicer, qt_widgets)
    shortcut = getattr(table, "_escapeShortcut", None)
    if shortcut is None:
        pytest.skip("ESC shortcut seam absent (ADR-0027).")

    # PythonQt exposes QShortcut.key / .context as properties (not callables).
    key = shortcut.key
    key = key() if callable(key) else key
    key = key.toString() if hasattr(key, "toString") else str(key)
    assert str(key) == "Esc"
    context = shortcut.context
    context = context() if callable(context) else context
    assert context == qt.Qt.WidgetWithChildrenShortcut, (
        "the ESC shortcut is scoped to the panel's widget tree, never global."
    )


# --------------------------------------------------------------------------- #
# On-slice corner annotation (the slice pipeline names the pin in text)
# --------------------------------------------------------------------------- #


def _pipeline_fixture(slicer):
    try:
        from VolumetrySeedPipeline import (
            VolumetrySeedPipelineSlice,
            VOLUMETRY_NAMESPACE,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VolumetrySeedPipelineSlice not importable ({exc!r}) -- the "
            "LayerDMLib base is not reachable here."
        )
    from PointPlacementState import PointPlacementState

    # The launched harness runs without slice widgets, so no vtkMRMLSliceNode
    # pre-exists (and the conftest clears the scene between tests): create the
    # slice node the pipeline projects against (the in-volume-pick precedent).
    slice_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSliceNode")
    if slice_node is None:
        slice_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSliceNode", "Red")
    if slice_node is None:
        pytest.skip("no vtkMRMLSliceNode available in this launched Slicer.")
    carrier = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "PinAnnotSeeds")
    display = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "PinAnnotDisplay")
    if carrier is None or display is None or not hasattr(carrier, "GetNthSeedID"):
        pytest.skip(f"{SEEDS_NODE_CLASS}/{DISPLAY_NODE_CLASS} not registered.")
    PointPlacementState(VOLUMETRY_NAMESPACE).set_carrier(display, carrier)

    pipeline = VolumetrySeedPipelineSlice()
    pipeline.SetViewNode(slice_node)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()
    if not hasattr(pipeline, "GetPinAnnotation"):
        pytest.skip("pipeline has no GetPinAnnotation seam (ADR-0027).")
    return pipeline, carrier, display


def test_slice_annotation_names_the_pinned_seed_and_volume():
    slicer = _slicer_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import set_highlight_seed_id

    pipeline, carrier, display = _pipeline_fixture(slicer)
    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.SetNthSeedLabel(0, "Wedge seed")
    if hasattr(carrier, "AddVolume"):
        carrier.AddVolume("V1")
        carrier.SetVolumeLabel("V1", "Left lobe")
        carrier.SetNthSeedVolume(0, "V1")

    set_highlight_seed_id(display, carrier.GetNthSeedID(0))
    pipeline.UpdatePipeline()

    text = pipeline.GetPinAnnotation().GetText(1) or ""
    assert "Wedge seed" in text, (
        "the slice corner annotation must NAME the pinned seed in text."
    )
    if hasattr(carrier, "AddVolume"):
        assert "Left lobe" in text, "the annotation names the volume too."

    # Unpinning clears the annotation.
    set_highlight_seed_id(display, "")
    pipeline.UpdatePipeline()
    assert not (pipeline.GetPinAnnotation().GetText(1) or "")


# --------------------------------------------------------------------------- #
# Module-scoped overlays (the display node's visibility IS the gate)
# --------------------------------------------------------------------------- #


def test_hiding_the_display_node_retires_every_slice_overlay():
    """An invisible seeds display node draws NOTHING; re-showing repaints.

    ``territory-usability`` display lifecycle: the module widget's ``exit()``
    hides the shared seeds display node, so every overlay this slice pipeline
    owns -- the projected handles, the hover ring, the placement-preview
    cursor and the pinned-seed stripes -- must retire, however the highlight
    member reads.  ``enter()`` re-shows the node and the next reconcile
    repaints from the carrier (no shadow state to restore).
    """
    slicer = _slicer_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import set_highlight_seed_id

    pipeline, carrier, display = _pipeline_fixture(slicer)
    carrier.AddSeed(1.0, 2.0, 0.0)  # in-plane, so the handle projects present
    carrier.SetNthSeedLabel(0, "Scoped seed")
    set_highlight_seed_id(display, carrier.GetNthSeedID(0))
    pipeline.UpdatePipeline()
    assert pipeline._handles_actor.GetVisibility(), (  # noqa: SLF001 - actor seam
        "precondition: the visible display node projects the seed handle."
    )
    assert "Scoped seed" in (pipeline.GetPinAnnotation().GetText(1) or ""), (
        "precondition: the pin names itself in the slice corner."
    )

    display.SetVisibility(False)
    pipeline.UpdatePipeline()

    assert not (pipeline.GetPinAnnotation().GetText(1) or ""), (
        "the pinned-seed identity TEXT must be blanked, not just hidden -- a "
        "vtkCornerAnnotation keeps its text and would outlive the module."
    )
    assert not pipeline.GetPinAnnotation().GetVisibility()

    assert not pipeline._handles_actor.GetVisibility(), (  # noqa: SLF001 - actor seam
        "a hidden display node must retire the projected seed handles."
    )
    assert not pipeline._ring_actor.GetVisibility()  # noqa: SLF001 - actor seam
    assert not pipeline._preview_actor.GetVisibility()  # noqa: SLF001 - actor seam
    assert not pipeline._stripes_actor.GetVisibility()  # noqa: SLF001 - actor seam
    # A retired overlay is not grabbable either (one gate for cue + gesture).
    assert not pipeline._slice_admissible()  # noqa: SLF001 - gate seam

    display.SetVisibility(True)
    pipeline.UpdatePipeline()

    assert pipeline._slice_admissible()  # noqa: SLF001 - gate seam
    assert pipeline._handles_actor.GetVisibility(), (  # noqa: SLF001 - actor seam
        "re-showing the display node must repaint the seed handles."
    )


def test_renderer_teardown_blanks_the_pin_annotation():
    """``cleanup`` (renderer churn / removal) blanks the identity text.

    The other retire route named by the display lifecycle: a pipeline whose
    renderer goes away must leave no "Pinned: ..." text behind for a re-added
    actor to resurrect.
    """
    slicer = _slicer_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import set_highlight_seed_id

    pipeline, carrier, display = _pipeline_fixture(slicer)
    carrier.AddSeed(1.0, 2.0, 0.0)
    carrier.SetNthSeedLabel(0, "Teardown seed")
    set_highlight_seed_id(display, carrier.GetNthSeedID(0))
    pipeline.UpdatePipeline()
    assert pipeline.GetPinAnnotation().GetText(1)

    pipeline.cleanup()

    assert not (pipeline.GetPinAnnotation().GetText(1) or ""), (
        "a renderer teardown must blank the pinned-seed identity text."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
