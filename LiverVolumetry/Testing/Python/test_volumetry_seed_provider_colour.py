# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the volumetry provider yields each seed's VOLUME colour.

Volumetry seeds must render in their VOLUME's colour (the colour shown on the
volume's table row), so differently-coloured volumes read apart in both the 2D
slice handles and the 3D sphere glyphs.  Mirroring
``TerritoryPointProvider``'s per-group colour lookup, ``VolumetrySeedProvider``
resolves each seed's base colour from the carrier's per-volume
``GetVolumeColor`` when the seed is grouped, falling back to the seed's own
``GetNthSeedColor`` when it is ungrouped (a legacy / pre-volume seed still
renders).

This file pins that fan-out PURELY over a fake carrier, so it RUNS BARE
(ADR-0027 no-skip for the pure-Python provider seam).  The rendered-glyph end
of the same contract (the 3D actor's direct-scalars point colours) is pinned
launched by ``test_volumetry_seed_glyph_3d.py``.

References
----------
* territory-usability -- the per-volume seed-colour plan (this seam).
* VascularTerritoriesLib/TerritoryPointProvider.py -- the per-group colour
  lookup this mirrors.
* ADR-0038 -- the PointProvider seam (``iter_points`` yields ``(world, base_rgb)``).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


class _FakeCarrier:
    """A minimal seed carrier with per-seed colour + per-volume colour slots."""

    _DEFAULT = (1.0, 1.0, 1.0)

    def __init__(self):
        self._coords: list[tuple[float, float, float]] = []
        self._seed_colors: list[tuple[float, float, float]] = []
        self._seed_volumes: list[str] = []
        self._volume_colors: dict[str, tuple[float, float, float]] = {}

    def AddSeed(self, x, y, z):  # noqa: N802 - carrier verb
        self._coords.append((x, y, z))
        self._seed_colors.append(self._DEFAULT)
        self._seed_volumes.append("")
        return len(self._coords) - 1

    def GetNumberOfSeeds(self):  # noqa: N802 - carrier verb
        return len(self._coords)

    def GetNthSeed(self, i):  # noqa: N802 - carrier verb
        return self._coords[i]

    def SetNthSeedColor(self, i, r, g, b):  # noqa: N802 - carrier verb
        self._seed_colors[i] = (r, g, b)

    def GetNthSeedColor(self, i):  # noqa: N802 - carrier verb
        return self._seed_colors[i]

    def SetNthSeedVolume(self, i, volumeId):  # noqa: N802 - carrier verb
        self._seed_volumes[i] = volumeId

    def GetNthSeedVolume(self, i):  # noqa: N802 - carrier verb
        return self._seed_volumes[i]

    def SetVolumeColor(self, volumeId, r, g, b):  # noqa: N802 - carrier verb
        self._volume_colors[volumeId] = (r, g, b)

    def GetVolumeColor(self, volumeId):  # noqa: N802 - carrier verb
        return self._volume_colors.get(volumeId, self._DEFAULT)


def _provider(carrier):
    from VolumetrySeedProvider import VolumetrySeedProvider

    return VolumetrySeedProvider(carrier)


def test_grouped_seed_yields_its_volume_colour():
    """A seed grouped into a named volume yields THAT volume's colour."""
    carrier = _FakeCarrier()
    idx = carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.SetNthSeedColor(idx, 0.0, 1.0, 0.0)  # green per-seed colour
    carrier.SetNthSeedVolume(idx, "Left")
    carrier.SetVolumeColor("Left", 1.0, 0.0, 0.0)  # red volume colour

    (world, base_rgb), = list(_provider(carrier).iter_points())
    assert world == pytest.approx((1.0, 2.0, 3.0))
    assert base_rgb == pytest.approx((1.0, 0.0, 0.0)), (
        "a grouped seed's base colour must be its VOLUME colour, not the "
        "per-seed colour."
    )


def test_ungrouped_seed_falls_back_to_its_per_seed_colour():
    """An ungrouped seed keeps its own per-seed colour (the fallback path)."""
    carrier = _FakeCarrier()
    idx = carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedColor(idx, 0.0, 0.0, 1.0)  # blue

    (_world, base_rgb), = list(_provider(carrier).iter_points())
    assert base_rgb == pytest.approx((0.0, 0.0, 1.0)), (
        "an ungrouped seed's base colour falls back to its per-seed colour."
    )


def test_two_volumes_read_apart():
    """Seeds in two differently-coloured volumes yield distinct base colours."""
    carrier = _FakeCarrier()
    a = carrier.AddSeed(0.0, 0.0, 0.0)
    b = carrier.AddSeed(1.0, 1.0, 1.0)
    carrier.SetNthSeedVolume(a, "A")
    carrier.SetNthSeedVolume(b, "B")
    carrier.SetVolumeColor("A", 0.90, 0.30, 0.24)
    carrier.SetVolumeColor("B", 0.20, 0.60, 0.86)

    colours = [rgb for _world, rgb in _provider(carrier).iter_points()]
    assert colours[0] == pytest.approx((0.90, 0.30, 0.24))
    assert colours[1] == pytest.approx((0.20, 0.60, 0.86))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
