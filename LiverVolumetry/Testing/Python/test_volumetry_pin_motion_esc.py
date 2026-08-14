# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- bounded pin motion, on-slice identity text, ESC.

Three view-side finishing contracts:

* IDLE-STATIC -- the pin's stripe march is BOUNDED: after
  ``STRIPE_IDLE_STATIC_MS`` of marching the widget's timer stops and the
  stripes freeze in place; the pin (and its published ID) stays.  Any pin
  change refills the countdown and restarts the march.  This doubles as
  the reduced-motion story: motion is never indefinite.
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


def test_march_goes_idle_static_and_keeps_the_pin(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    from LiverVolumetryLib.CarvedRegionStripes import get_highlight_seed_id

    carrier, display, table = _make_fixture(slicer, qt_widgets)
    if not hasattr(table, "_stripeTicksRemaining"):
        pytest.skip("idle-static countdown seam absent (ADR-0027).")

    table.highlightButton(0).setChecked(True)
    assert table._stripeTimer.isActive()  # noqa: SLF001 - timer seam

    # Fast-forward the countdown to its last two ticks (10 s of wall-clock
    # marching is not a unit test's business).
    table._stripeTicksRemaining = 2  # noqa: SLF001 - countdown seam
    table._onStripeTick()  # noqa: SLF001
    assert table._stripeTimer.isActive(), "one tick left -- still marching."  # noqa: SLF001
    table._onStripeTick()  # noqa: SLF001

    assert not table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "after the idle-static interval the march timer must STOP."
    )
    assert get_highlight_seed_id(display) == carrier.GetNthSeedID(0), (
        "idle-static freezes the MOTION only -- the pin and its stripes stay."
    )
    assert table.pinnedSeedID() == carrier.GetNthSeedID(0)


def test_a_pin_change_restarts_the_march(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier, _display, table = _make_fixture(slicer, qt_widgets)
    if not hasattr(table, "_stripeTicksRemaining"):
        pytest.skip("idle-static countdown seam absent (ADR-0027).")

    table.highlightButton(0).setChecked(True)
    table._stripeTicksRemaining = 1  # noqa: SLF001
    table._onStripeTick()  # noqa: SLF001
    assert not table._stripeTimer.isActive()  # noqa: SLF001

    table.highlightButton(1).setChecked(True)  # the pin change

    assert table._stripeTimer.isActive(), (  # noqa: SLF001 - timer seam
        "any pin change must restart the march."
    )
    assert table._stripeTicksRemaining > 1, (  # noqa: SLF001 - countdown seam
        "the pin change must refill the idle-static countdown."
    )


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

    key = shortcut.key()
    key = key.toString() if hasattr(key, "toString") else str(key)
    assert str(key) == "Esc"
    context = shortcut.context()
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

    slice_node = slicer.util.getNode("vtkMRMLSliceNodeRed")
    if slice_node is None:
        pytest.skip("no Red slice node available in this launched Slicer.")
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
    from LiverVolumetryLib.CarvedRegionStripes import (
        set_highlight_seed_id,
        set_preview_seed_id,
    )

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

    # A hover preview shows no identity text (transient by design).
    set_preview_seed_id(display, carrier.GetNthSeedID(0))
    pipeline.UpdatePipeline()
    assert not (pipeline.GetPinAnnotation().GetText(1) or ""), (
        "a preview must not annotate."
    )

    # Unpinning clears the annotation.
    set_highlight_seed_id(display, "")
    pipeline.UpdatePipeline()
    assert not (pipeline.GetPinAnnotation().GetText(1) or "")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
