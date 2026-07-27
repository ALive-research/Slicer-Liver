# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the pure carrier->transient-fiducial mapping.

``volumetry-seeds-layerdm-plan.md`` §3c keeps the C++
``vtkLiverVolumetryLogic`` SIGNATURES unchanged (they take a
``vtkMRMLMarkupsFiducialNode*``); the seeds-off-markups migration feeds
them a TRANSIENT fiducial built INSIDE the call from the seed carrier,
mirroring ADR-0037 §Decision 4 / ``TransientVmtkSeeds.py``.  The per-seed
LABEL must round-trip into the transient fiducial's control-point label so
``GenerateSegmentsLabelMap`` still names segments correctly.

The pure mapping (carrier points + labels -> a fiducial-shaped payload) is
a dependency-free function -- no live scene, no wrapped C++ node -- so it
is BARE-UNIT-TESTABLE (ADR-0004: keep the mapping pure Python; the actual
``vtkMRMLMarkupsFiducialNode`` creation is a thin Logic wrapper over the
core, pinned end to end by ``test_volumetry_compute_from_carrier.py``).

This file pins:

* POSITION preserved -- each payload entry's coordinate equals its carrier
  seed's coordinate;
* LABEL preserved -- each payload entry's label equals its carrier seed's
  label (the segment-name fidelity);
* ORDER preserved -- payload order == carrier placement order (label i
  drives generated segment i, per ``LiverVolumetry.generateSegments``).

HARNESS: bare ``PythonSlicer -m pytest``.  The mapping is pure Python over
plain tuples -- no scene, no markups, no wrapped node -- so it RUNS bare
AND launched.

The SUT does not exist yet.  Per ADR-0027 red->skip the import is guarded
and every test SKIP-PENDINGs on ``ImportError``; the skips lift when the
implementer lands the pure builder core.

References
----------
* ADR-0038 -- §Conformance ([review] "fed a transient fiducial built from
  the seed carrier, and per-seed labels round-trip so generated segments
  keep their names").
* ADR-0004 -- Python/C++ boundary; keep the mapping pure Python.
* ADR-0015 -- the C++ region-grow logic is unchanged (the transient
  adapter, not a signature rewrite).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/VascularTerritoriesLib/TransientVmtkSeeds.py -- the
  transient-builder idiom this mirrors.
* LiverVolumetry/LiverVolumetry.py -- generateSegments() reads
  GetNthFiducialLabel(i) to name segment i (the order/label dependency).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
# The pure builder core lives in the module's Lib (proposed
# ``LiverVolumetryLib`` following the VascularTerritoriesLib precedent); the
# path-insert lets the bare layer import it before the Lib packaging lands.
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

_PENDING = (
    "the pure carrier->transient-fiducial builder core has not landed "
    "(ADR-0038-amendment / plan §3c) (ADR-0027 red->skip)."
)


def _import_builder():
    """Import the pure builder core or SKIP-PENDING when it is absent.

    PROPOSED seam (sharpen at landing).  A pure function that maps ordered
    ``(x, y, z, label)`` seeds to a fiducial-shaped payload preserving
    coordinate + label + order::

        def build_fiducial_payload(
            seeds: list[tuple[float, float, float, str]],
        ) -> list[tuple[tuple[float, float, float], str]]: ...

    IMPLEMENTER SEAM PREFERENCE (mirrors TransientVmtkSeeds): keep this a
    pure function so this test stays bare; the vtkMRMLMarkupsFiducialNode
    creation (add-to-scene -> set positions + labels -> feed -> RemoveNode)
    is a THIN Logic wrapper over the core, NOT the tested unit for the
    mapping invariant.  Adjust the imported name here to match the landed
    module/function.
    """
    try:
        from TransientVolumetrySeeds import build_fiducial_payload
    except ImportError:
        pytest.skip(_PENDING)
    return build_fiducial_payload


def test_mapping_preserves_position():
    """Each payload entry's coordinate equals its source seed's coordinate."""
    build = _import_builder()
    seeds = [
        (1.0, 2.0, 3.0, "A"),
        (4.0, 5.0, 6.0, "B"),
        (-7.0, 8.0, -9.0, "C"),
    ]

    payload = build(seeds)

    assert len(payload) == len(seeds)
    for (world, _label), src in zip(payload, seeds):
        assert tuple(world) == pytest.approx(src[:3], abs=1e-9)


def test_mapping_preserves_label():
    """Each payload entry's label equals its source seed's label.

    ADR-0038 §Conformance: per-seed labels round-trip so
    ``GenerateSegmentsLabelMap`` names segments correctly.
    """
    build = _import_builder()
    seeds = [
        (1.0, 2.0, 3.0, "SegmentV"),
        (4.0, 5.0, 6.0, "SegmentVI"),
    ]

    payload = build(seeds)

    assert [label for _world, label in payload] == ["SegmentV", "SegmentVI"]


def test_mapping_preserves_order():
    """Payload order == carrier placement order.

    ``LiverVolumetry.generateSegments`` names generated segment ``i`` from
    the fiducial's ``GetNthFiducialLabel(i)``, so payload index i MUST be
    carrier seed i -- a reorder would mis-name every segment.
    """
    build = _import_builder()
    seeds = [(float(i), 0.0, 0.0, f"L{i}") for i in range(5)]

    payload = build(seeds)

    assert [label for _world, label in payload] == [f"L{i}" for i in range(5)]
    for i, (world, _label) in enumerate(payload):
        assert world[0] == pytest.approx(float(i), abs=1e-9), (
            f"payload index {i} must be carrier seed {i} (order preserved)."
        )


def test_empty_carrier_maps_to_empty_payload():
    """An empty seed list maps to an empty payload (no phantom point)."""
    build = _import_builder()
    assert list(build([])) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
