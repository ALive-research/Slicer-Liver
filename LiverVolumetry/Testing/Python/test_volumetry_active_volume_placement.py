# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- a placed volumetry seed lands in the ACTIVE volume.

Mirroring the VascularTerritories active-territory routing (a surface click
appends one seed to the ACTIVE territory read off the shared display node), the
volumetry slice pipeline assigns each placed seed to the ACTIVE VOLUME.  The
active-volume id rides the shared ``vtkMRMLVolumetrySeedsDisplayNode`` via the
base's ``PointPlacementState`` active slot (the same channel the territory
client uses for its active territory), NOT the Python pipeline instance LayerDM
does not drive (``feedback_layerdm_state_on_display_node``).

This file pins the routing seam PURELY (bare-runnable): the slice pipeline's
``_assign_active_volume`` reads the active-volume id from the display node and
writes it onto the just-placed seed's ``SetNthSeedVolume``.  The full LayerDM
placement lifecycle (armed click -> interior pick -> add) is pinned launched by
``test_volumetry_seed_placement.py``; this unit test isolates the volume
routing over a fake carrier + display node so it RUNS BARE (ADR-0027 no-skip
for the pure-Python seam).

References
----------
* territory-usability -- the active-volume placement plan (this seam).
* VascularTerritoriesLib/TerritoryPlacementPipeline.py -- the active-group
  routing this mirrors.
* ADR-0038 -- the shared base + PointPlacementState the state rides.
* feedback_layerdm_state_on_display_node -- state on the display node, not the
  pipeline instance.
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

VOLUMETRY_NAMESPACE = "LiverVolumetry"


class _FakeCarrier:
    """A minimal flat seed carrier with the volume-group slot under test."""

    def __init__(self):
        self._volumes = []

    def AddSeed(self, x, y, z):  # noqa: N802 - carrier verb
        self._volumes.append("")
        return len(self._volumes) - 1

    def GetNumberOfSeeds(self):  # noqa: N802 - carrier verb
        return len(self._volumes)

    def SetNthSeedVolume(self, i, volumeId):  # noqa: N802 - carrier verb
        self._volumes[i] = volumeId

    def GetNthSeedVolume(self, i):  # noqa: N802 - carrier verb
        return self._volumes[i]


class _FakeDisplayNode:
    """A GetAttribute/SetAttribute channel like a MRML display node."""

    def __init__(self):
        self._attrs = {}

    def SetAttribute(self, key, value):  # noqa: N802 - MRML verb
        if value is None:
            self._attrs.pop(key, None)
        else:
            self._attrs[key] = value

    def GetAttribute(self, key):  # noqa: N802 - MRML verb
        return self._attrs.get(key)


def _state():
    from PointPlacementState import PointPlacementState

    return PointPlacementState(VOLUMETRY_NAMESPACE)


def _pipeline_assign_seam():
    """The slice pipeline's ``_assign_active_volume`` bound onto a bare instance.

    Constructs the slice pipeline without touching Slicer/LayerDM by pulling the
    unbound method off the class and driving it against fakes; skip-pends if the
    seam has not landed (ADR-0027).
    """
    try:
        from VolumetrySeedPipeline import VolumetrySeedPipelineSlice
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VolumetrySeedPipelineSlice not importable bare ({exc!r}).")
    if not hasattr(VolumetrySeedPipelineSlice, "_assign_active_volume"):
        pytest.skip(
            "VolumetrySeedPipelineSlice has no _assign_active_volume -- the "
            "active-volume routing seam (territory-usability) has not landed "
            "(ADR-0027)."
        )
    return VolumetrySeedPipelineSlice


class _StubProvider:
    def __init__(self, carrier):
        self._carrier = carrier

    def carrier(self):
        return self._carrier


def _drive_assign(cls, carrier, displayNode, index):
    """Call ``_assign_active_volume`` with the pipeline's fields stubbed in."""
    inst = cls.__new__(cls)
    inst._provider = _StubProvider(carrier)  # noqa: SLF001 - test wiring
    inst._display_node = displayNode  # noqa: SLF001 - test wiring
    cls._assign_active_volume(inst, index)


def test_placed_seed_gets_the_active_volume():
    """A placed seed is assigned the active-volume id from the display node."""
    cls = _pipeline_assign_seam()
    carrier = _FakeCarrier()
    display = _FakeDisplayNode()
    _state().set_active(display, "Left lobe")

    index = carrier.AddSeed(1.0, 2.0, 3.0)
    _drive_assign(cls, carrier, display, index)

    assert carrier.GetNthSeedVolume(index) == "Left lobe"


def test_no_active_volume_leaves_seed_ungrouped():
    """With no active volume the seed stays ungrouped (empty volume id)."""
    cls = _pipeline_assign_seam()
    carrier = _FakeCarrier()
    display = _FakeDisplayNode()  # no active set

    index = carrier.AddSeed(0.0, 0.0, 0.0)
    _drive_assign(cls, carrier, display, index)

    assert carrier.GetNthSeedVolume(index) == ""


def test_two_seeds_route_to_the_active_volume_at_placement_time():
    """Switching the active volume between placements routes each seed correctly.

    Mirrors add-territory -> place seeds -> add-territory -> place seeds: the
    active volume at PLACEMENT time decides the group.
    """
    cls = _pipeline_assign_seam()
    carrier = _FakeCarrier()
    display = _FakeDisplayNode()

    _state().set_active(display, "A")
    i0 = carrier.AddSeed(0.0, 0.0, 0.0)
    _drive_assign(cls, carrier, display, i0)

    _state().set_active(display, "B")
    i1 = carrier.AddSeed(1.0, 1.0, 1.0)
    _drive_assign(cls, carrier, display, i1)

    assert carrier.GetNthSeedVolume(i0) == "A"
    assert carrier.GetNthSeedVolume(i1) == "B"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
