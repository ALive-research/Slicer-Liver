# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the per-VOLUME volumetry seeds table.

The volumetry seeds table restructures from a FLAT per-seed table into a
two-level tree mirroring the VascularTerritories ``TerritoriesTableWidget``:
VOLUMES are TOP-LEVEL rows, seeds nest as CHILD rows under their volume.  The
surgeon adds a named VOLUME (Add volume), arms placement into the ACTIVE volume
(a per-volume Place toggle publishing the active volume onto the shared display
node), and placed seeds nest under that volume.  Each volume row carries a
colour swatch, an editable label, and an overflow "..." menu carrying Remove
volume (confirming when seeds would go with it); each seed row keeps its
retarget + delete behind its own overflow (the seed→segment binding is
untouched).

The per-SEED getters stay keyed by the seed's GLOBAL placement INDEX
(``labelEdit`` / ``targetCombo`` / ``deleteAction`` / ``setSeedColor`` /
``deleteSeed`` / ``retargetSeed``), so the existing seed-row + Target-combo
contract (``test_volumetry_seeds_table.py``) is preserved on top of the
grouping.

HARNESS: launched Slicer (Qt + wrapped carrier).  Bare SKIPS CLEANLY via the
shared ``conftest`` guards; the CTest row collects + skips bare and RUNS
launched (ADR-0027).

References
----------
* territory-usability -- the per-volume table plan (this SUT).
* VascularTerritories/Testing/Python/test_territories_table.py -- the
  two-level tree idiom this mirrors.
* ADR-0038 -- the carrier-backed table.
* ADR-0010 -- glyph/text pairing.
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


def _make_carrier_or_skip(slicer, name="VolumesTableCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    for method in ("AddSeedToVolume", "GetVolumeIds"):
        if not hasattr(node, method):
            pytest.skip(
                f"{SEEDS_NODE_CLASS} has no {method} -- the grouped-volumes "
                "carrier has not landed (ADR-0027)."
            )
    return node


def _import_table_or_skip():
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VolumetrySeedsTableWidget not importable ({exc!r}) (ADR-0027).")
    return VolumetrySeedsTableWidget


def _make_table_or_skip(slicer, carrier, displayNode=None):
    VolumetrySeedsTableWidget = _import_table_or_skip()
    try:
        table = VolumetrySeedsTableWidget(carrier=carrier, displayNode=displayNode)
    except TypeError as exc:
        pytest.skip(
            f"VolumetrySeedsTableWidget(carrier=, displayNode=) seam absent "
            f"({exc!r}) -- the per-volume table constructor has not landed "
            "(ADR-0027)."
        )
    if not hasattr(table, "volumeIds"):
        pytest.skip("VolumetrySeedsTableWidget has no volumeIds seam (ADR-0027).")
    return table


# --------------------------------------------------------------------------- #
# Volume rows + add volume
# --------------------------------------------------------------------------- #


def test_add_volume_mints_a_top_level_volume_row(qt_widgets):
    """Add volume mints a top-level VOLUME row that enumerates."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "addVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no addVolume seam (ADR-0027).")

    volumeId = table.addVolume()

    assert volumeId in list(table.volumeIds()), (
        "Add volume must mint a top-level volume row that enumerates."
    )


def test_seeds_nest_under_their_volume(qt_widgets):
    """Seeds placed into a volume appear as CHILD rows under that volume."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "seedIndicesForVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no seedIndicesForVolume (ADR-0027).")

    carrier.AddSeedToVolume("Left", 0.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Right", 1.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Left", 2.0, 0.0, 0.0)
    carrier.Modified()

    assert set(table.volumeIds()) >= {"Left", "Right"}
    assert list(table.seedIndicesForVolume("Left")) == [0, 2], (
        "seeds must nest under their volume, keyed by global placement index."
    )
    assert list(table.seedIndicesForVolume("Right")) == [1]


# --------------------------------------------------------------------------- #
# Per-volume display: colour + label + delete
# --------------------------------------------------------------------------- #


def test_volume_label_edit_writes_carrier(qt_widgets):
    """Committing a volume row's label ``QLineEdit`` writes ``SetVolumeLabel``."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "volumeLabelEdit"):
        pytest.skip("VolumetrySeedsTableWidget has no volumeLabelEdit (ADR-0027).")

    carrier.AddSeedToVolume("V1", 0.0, 0.0, 0.0)
    carrier.Modified()

    edit = table.volumeLabelEdit("V1")
    assert edit is not None, "the volume row must carry an editable label."
    edit.setText("Left lobe")
    edit.editingFinished()

    assert carrier.GetVolumeLabel("V1") == "Left lobe"


def test_delete_volume_removes_its_seeds(qt_widgets):
    """A volume row's delete removes the whole volume (its seeds + display)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteVolume seam (ADR-0027).")

    carrier.AddSeedToVolume("Keep", 0.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Drop", 1.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Drop", 2.0, 0.0, 0.0)
    carrier.Modified()

    table.deleteVolume("Drop")

    assert carrier.GetNumberOfSeeds() == 1
    assert carrier.GetNthSeedVolume(0) == "Keep"
    assert "Drop" not in list(table.volumeIds())


# --------------------------------------------------------------------------- #
# Place routes into the active volume (arm on the display node)
# --------------------------------------------------------------------------- #


def test_place_toggle_arms_into_the_active_volume(qt_widgets):
    """A volume row's Place toggle publishes the active volume + arms the node."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumetrySeedsDisplayNode")
    if display is None:
        pytest.skip("vtkMRMLVolumetrySeedsDisplayNode not registered (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier, displayNode=display)
    qt_widgets.append(table)
    if not hasattr(table, "placeButton"):
        pytest.skip("VolumetrySeedsTableWidget has no placeButton seam (ADR-0027).")

    volumeId = table.addVolume() if hasattr(table, "addVolume") else None
    if volumeId is None:
        pytest.skip("addVolume seam absent (ADR-0027).")

    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState

    state = PointPlacementState("LiverVolumetry")
    assert state.get_active(display) == volumeId, (
        "Add volume must arm into the new volume (active volume on the display node)."
    )
    assert state.is_armed(display), "Add volume must arm placement."


# --------------------------------------------------------------------------- #
# Seed-row contract preserved (Target combo keyed by global index)
# --------------------------------------------------------------------------- #


def test_seed_target_combo_keyed_by_global_index(qt_widgets):
    """The per-seed Target combo stays addressable by global placement index."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "targetCombo") or not hasattr(table, "setStructureSource"):
        pytest.skip("VolumetrySeedsTableWidget has no target seam (ADR-0027).")

    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SegSrc")
    segmentation.CreateDefaultDisplayNodes()
    segmentation.GetSegmentation().AddEmptySegment("segA", "Alpha")
    segmentation.GetSegmentation().AddEmptySegment("segB", "Beta")
    table.setStructureSource(segmentation)

    carrier.AddSeedToVolume("V1", 0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "segB")
    carrier.Modified()

    menu = table.targetCombo(0)
    assert menu is not None, (
        "the seed overflow must carry a Retarget submenu keyed by index."
    )
    checked = []
    for action in menu.actions():
        isChecked = action.isChecked
        if isChecked() if callable(isChecked) else isChecked:
            text = action.text
            checked.append(text() if callable(text) else text)
    assert checked == ["Beta"], (
        "the Retarget submenu must CHECK the bound segment (the menu-backed "
        "successor of the Target combo)."
    )


# --------------------------------------------------------------------------- #
# Volume overflow -- Remove confirms when seeds would go with it
# --------------------------------------------------------------------------- #


def test_remove_volume_action_confirms_when_it_carries_seeds(qt_widgets):
    """The overflow "Remove volume..." confirms a seed-bearing volume, naming
    the label + seed count; declining keeps everything."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "volumeRemoveAction"):
        pytest.skip("VolumetrySeedsTableWidget has no volumeRemoveAction (ADR-0027).")

    carrier.AddSeedToVolume("Drop", 1.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Drop", 2.0, 0.0, 0.0)
    carrier.SetVolumeLabel("Drop", "Left lobe")
    carrier.Modified()

    confirms = []

    def _fake_confirm(text):
        confirms.append(text)
        return _fake_confirm.answer

    _fake_confirm.answer = False
    table._confirmDestructive = _fake_confirm  # noqa: SLF001 - confirm seam

    table.volumeRemoveAction("Drop").trigger()
    assert carrier.GetNumberOfSeeds() == 2, (
        "a DECLINED confirm must keep the volume and its seeds."
    )
    assert confirms and "Left lobe" in confirms[0] and "2" in confirms[0], (
        "the confirm must name the volume label AND its seed count."
    )

    _fake_confirm.answer = True
    table.volumeRemoveAction("Drop").trigger()
    assert carrier.GetNumberOfSeeds() == 0
    assert "Drop" not in list(table.volumeIds())


def test_remove_empty_volume_stays_one_click(qt_widgets):
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "volumeRemoveAction") or not hasattr(table, "addVolume"):
        pytest.skip("VolumetrySeedsTableWidget has no volume overflow (ADR-0027).")

    volumeId = table.addVolume()

    def _never_confirm(text):
        raise AssertionError("removing an EMPTY volume must not confirm")

    table._confirmDestructive = _never_confirm  # noqa: SLF001 - confirm seam
    table.volumeRemoveAction(volumeId).trigger()

    assert volumeId not in list(table.volumeIds())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
