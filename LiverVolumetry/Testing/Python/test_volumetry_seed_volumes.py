# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- grouped VOLUMES on the volumetry seed carrier.

The volumetry seed carrier gains a named-VOLUME grouping mirroring the
VascularTerritories carrier's per-group model (``vtkMRMLCustomTerritoriesNode``
per-territory annotation points + per-territory display slots): the surgeon
adds a named ``volume``, then placed seeds go into the ACTIVE volume.  Each
seed still carries its per-seed LABEL, colour, and ``(segmentationNodeID,
segmentID)`` Target binding (the just-added seed→segment capture) -- grouping
only decides which volume it lands in.

This file pins the grouped-carrier increment (mirroring
``test_territories_annotation_carrier.py`` per-group maps + the existing flat
``test_volumetry_seed_carrier.py`` per-seed fields):

* PER-SEED VOLUME id -- each seed carries a volume-group id, independent of its
  coordinate + label + binding; a delete shifts it in lockstep with the tail.
* ADD-SEED-TO-VOLUME -- ``AddSeedToVolume`` appends a seed already assigned to a
  volume, preserving the flat placement order + the per-seed fields.
* VOLUME ENUMERATION -- ``GetVolumeIds`` lists volumes deterministically;
  ``AddVolume`` registers an empty (zero-seed) volume that still enumerates.
* PER-VOLUME DISPLAY -- per-volume colour + label ride OWN slots (a display
  write never touches seed geometry), mirroring ``SetTerritoryColor`` /
  ``SetTerritoryLabel``.
* DELETE VOLUME -- ``RemoveVolume`` drops the volume's seeds AND its display
  slot, leaving siblings intact.
* STORAGE ROUND-TRIP -- the per-seed volume ids + the per-volume display slots
  survive a write/read cycle alongside the existing seeds/labels/colours.

HARNESS: launched Slicer.  ``vtkMRMLVolumetrySeedsNode`` is a WRAPPED C++ node
(the wrapped-class-namespace rule); a bare ``PythonSlicer -m pytest`` has
``slicer.mrmlScene is None`` and the wrapped class off the path, so every test
SKIPS CLEANLY.  Per ADR-0027 red->skip the guards skip-pend; the skips lift at
the implementation commit.

References
----------
* territory-usability -- the grouped-volumes plan (this file's SUT).
* ADR-0037 -- the per-group territory carrier this mirrors.
* ADR-0014 -- the four-layer split (a display edit must not touch geometry).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
SEEDS_STORAGE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"

# PROPOSED grouped-carrier API (mirror the territory carrier's std::string-keyed
# per-group idiom).  Tests skip-pending on absence (ADR-0027).
ADD_TO_VOLUME_METHOD = "AddSeedToVolume"        # AddSeedToVolume(volumeId, x, y, z) -> int
GET_SEED_VOLUME_METHOD = "GetNthSeedVolume"
SET_SEED_VOLUME_METHOD = "SetNthSeedVolume"
ADD_VOLUME_METHOD = "AddVolume"
GET_VOLUME_IDS_METHOD = "GetVolumeIds"
REMOVE_VOLUME_METHOD = "RemoveVolume"
SET_VOLUME_COLOR_METHOD = "SetVolumeColor"
GET_VOLUME_COLOR_METHOD = "GetVolumeColor"
SET_VOLUME_LABEL_METHOD = "SetVolumeLabel"
GET_VOLUME_LABEL_METHOD = "GetVolumeLabel"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_carrier_or_skip(slicer, name="VolumetryVolumesTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(
            f"{SEEDS_NODE_CLASS} not registered -- launched build required "
            "(ADR-0027)."
        )
    for method in (ADD_TO_VOLUME_METHOD, GET_VOLUME_IDS_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{SEEDS_NODE_CLASS} has no {method} -- the grouped-volumes "
                "carrier API (territory-usability) has not landed (ADR-0027)."
            )
    return node


# --------------------------------------------------------------------------- #
# Per-seed volume id + add-to-volume
# --------------------------------------------------------------------------- #


def test_add_seed_to_volume_assigns_volume_and_keeps_order():
    """AddSeedToVolume appends a seed assigned to the named volume, in order."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    i0 = carrier.AddSeedToVolume("Volume A", 1.0, 2.0, 3.0)
    i1 = carrier.AddSeedToVolume("Volume B", 4.0, 5.0, 6.0)
    i2 = carrier.AddSeedToVolume("Volume A", 7.0, 8.0, 9.0)

    assert (i0, i1, i2) == (0, 1, 2)
    assert carrier.GetNumberOfSeeds() == 3
    assert carrier.GetNthSeedVolume(0) == "Volume A"
    assert carrier.GetNthSeedVolume(1) == "Volume B"
    assert carrier.GetNthSeedVolume(2) == "Volume A"
    # The flat coordinate order is preserved.
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx((4.0, 5.0, 6.0), abs=1e-9)


def test_seed_volume_is_independent_of_other_per_seed_fields():
    """A volume assignment does not disturb the coordinate / label / binding."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.SetNthSeedLabel(0, "Segment_2")
    carrier.SetNthSeedBinding(0, "segNode", "Segment_2")
    carrier.SetNthSeedVolume(0, "Left lobe")

    assert carrier.GetNthSeedVolume(0) == "Left lobe"
    assert carrier.GetNthSeedLabel(0) == "Segment_2"
    assert carrier.GetNthSeedBindingSegmentID(0) == "Segment_2"
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9)


def test_delete_shifts_volume_in_lockstep():
    """Deleting a seed shifts the per-seed volume id up with the tail."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    carrier.AddSeedToVolume("A", 0.0, 0.0, 0.0)
    carrier.AddSeedToVolume("B", 1.0, 1.0, 1.0)
    carrier.AddSeedToVolume("C", 2.0, 2.0, 2.0)

    carrier.RemoveNthSeed(1)

    assert carrier.GetNthSeedVolume(0) == "A"
    assert carrier.GetNthSeedVolume(1) == "C"


# --------------------------------------------------------------------------- #
# Volume enumeration + empty volumes
# --------------------------------------------------------------------------- #


def test_get_volume_ids_is_deterministic_and_covers_seeded_volumes():
    """GetVolumeIds lists every seeded volume, deterministically ordered."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    carrier.AddSeedToVolume("Volume B", 0.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Volume A", 1.0, 1.0, 1.0)
    carrier.AddSeedToVolume("Volume B", 2.0, 2.0, 2.0)

    ids = list(carrier.GetVolumeIds())
    assert set(ids) == {"Volume A", "Volume B"}
    # Deterministic order (the storage node enumerates the volumes stably).
    assert ids == sorted(ids)


def test_add_volume_registers_empty_volume_that_enumerates():
    """AddVolume mints a zero-seed volume that still enumerates (an empty group).

    Mirrors the territory carrier's display-slot-only presence: an empty minted
    volume is enumerable so its table row survives before a seed lands.
    """
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, ADD_VOLUME_METHOD):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no {ADD_VOLUME_METHOD} (ADR-0027).")

    carrier.AddVolume("Empty volume")
    assert "Empty volume" in list(carrier.GetVolumeIds())


# --------------------------------------------------------------------------- #
# Per-volume display slots (colour + label)
# --------------------------------------------------------------------------- #


def test_per_volume_colour_and_label_round_trip_in_memory():
    """Per-volume colour + label ride OWN slots; a display write keeps geometry."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    for method in (SET_VOLUME_COLOR_METHOD, GET_VOLUME_COLOR_METHOD,
                   SET_VOLUME_LABEL_METHOD, GET_VOLUME_LABEL_METHOD):
        if not hasattr(carrier, method):
            pytest.skip(f"{SEEDS_NODE_CLASS} has no {method} (ADR-0027).")

    carrier.AddSeedToVolume("V1", 1.0, 2.0, 3.0)
    carrier.SetVolumeColor("V1", 0.2, 0.6, 0.86)
    carrier.SetVolumeLabel("V1", "Left lateral")

    assert tuple(carrier.GetVolumeColor("V1")) == pytest.approx((0.2, 0.6, 0.86), abs=1e-6)
    assert carrier.GetVolumeLabel("V1") == "Left lateral"
    # A display write must not disturb the seed geometry.
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9)


# --------------------------------------------------------------------------- #
# Delete volume
# --------------------------------------------------------------------------- #


def test_remove_volume_drops_its_seeds_and_display_leaving_siblings():
    """RemoveVolume drops the volume's seeds + display slot; siblings survive."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, REMOVE_VOLUME_METHOD):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no {REMOVE_VOLUME_METHOD} (ADR-0027).")

    carrier.AddSeedToVolume("Keep", 0.0, 0.0, 0.0)
    carrier.AddSeedToVolume("Drop", 1.0, 1.0, 1.0)
    carrier.AddSeedToVolume("Drop", 2.0, 2.0, 2.0)
    if hasattr(carrier, SET_VOLUME_LABEL_METHOD):
        carrier.SetVolumeLabel("Drop", "gone")

    removed = carrier.RemoveVolume("Drop")

    assert removed
    assert carrier.GetNumberOfSeeds() == 1
    assert carrier.GetNthSeedVolume(0) == "Keep"
    assert "Drop" not in list(carrier.GetVolumeIds())
    if hasattr(carrier, GET_VOLUME_LABEL_METHOD):
        assert carrier.GetVolumeLabel("Drop") == ""


# --------------------------------------------------------------------------- #
# Storage round-trip
# --------------------------------------------------------------------------- #


def test_storage_round_trips_volume_ids_and_display(tmp_path):
    """Per-seed volume ids + per-volume display slots survive write/read."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    storage = slicer.mrmlScene.AddNewNodeByClass(SEEDS_STORAGE_CLASS)
    if storage is None:
        pytest.skip(f"{SEEDS_STORAGE_CLASS} not registered (ADR-0027).")

    carrier.AddSeedToVolume("Left", 0.0, 0.0, 1.0)
    carrier.AddSeedToVolume("Right", 1.0, 0.0, 0.0)
    if hasattr(carrier, SET_VOLUME_COLOR_METHOD):
        carrier.SetVolumeColor("Left", 0.9, 0.3, 0.24)
    if hasattr(carrier, SET_VOLUME_LABEL_METHOD):
        carrier.SetVolumeLabel("Left", "Left lobe")

    path = str(tmp_path / "seeds.vsd.json")
    storage.SetFileName(path)
    assert storage.WriteData(carrier) != 0

    reloaded = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "Reloaded")
    storage.ReadData(reloaded)

    assert reloaded.GetNumberOfSeeds() == 2
    assert reloaded.GetNthSeedVolume(0) == "Left"
    assert reloaded.GetNthSeedVolume(1) == "Right"
    if hasattr(reloaded, GET_VOLUME_COLOR_METHOD):
        assert tuple(reloaded.GetVolumeColor("Left")) == pytest.approx(
            (0.9, 0.3, 0.24), abs=1e-6)
    if hasattr(reloaded, GET_VOLUME_LABEL_METHOD):
        assert reloaded.GetVolumeLabel("Left") == "Left lobe"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
