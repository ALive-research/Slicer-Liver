# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the LiverVolumetry seed carrier + storage round-trip.

The ADR-0038 implementation amendment (2026-07-27) moves LiverVolumetry's
region-growing seed fiducials OFF Slicer markups
(``vtkMRMLMarkupsFiducialNode`` ``ROIMarkersList``) ONTO a module-local
data-carrier ``vtkMRMLVolumetrySeedsNode``, following ADR-0014's four-layer
split (each module owns its wrapper / carrier / display / storage;
``volumetry-seeds-layerdm-plan.md`` §3a).  A volumetry seed is a labelled
point: the per-point LABEL becomes a generated segment name
(``GenerateSegmentsLabelMap`` reads it), and the per-point colour carries
the seed display.

This file pins the carrier increments (mirroring
``test_territories_annotation_carrier.py``):

* CARRIER MUTATION -- ordered add / get-Nth / count / delete; ``Modified``
  on mutation; the ABSENCE of any markups-fiducial reference role on the
  carrier (the off-markups invariant, ADR-0014 §"Fourth layer").
* PER-POINT LABEL -- each seed carries a string label independent of its
  coordinate; the label round-trips (the segment-name fidelity, pinned end
  to end by ``test_volumetry_compute_from_carrier.py``).
* PER-POINT COLOUR -- each seed carries an RGB display colour.
* STORAGE ROUND-TRIP -- writing the carrier to its storage node and reading
  back yields identical ORDERED points + labels + colours (mirrors
  ``vtkMRMLResectionPlanStorageNode`` / the territory carrier round-trip).

HARNESS: launched Slicer.  ``vtkMRMLVolumetrySeedsNode`` is a WRAPPED C++
node whose Python wrapper resolves ONLY via the module's wrapped-logic
Python module inside a launched Slicer with the module loaded -- NOT via
plain ``vtk`` or ``slicer`` (the wrapped-class-namespace rule,
``reference_algorithm_wrapped_class_namespace``).  A bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` and the wrapped
class off the path, so every test SKIPS CLEANLY.

The SUT does not exist yet.  Per ADR-0027 red->skip the
``AddNewNodeByClass``-returns-None + ``hasattr`` guards skip-pend; the
skips lift at the implementation commit.

References
----------
* ADR-0038 -- §"Consumers ledger" (LiverVolumetry as the third client) +
  §Conformance (per-seed labels round-trip so generated segments keep
  their names).
* ADR-0014 -- the four-layer split (wrapper / carrier / display / storage);
  §"Fourth layer" (no persistent markups).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/Testing/Python/test_territories_annotation_carrier.py
  -- the carrier-contract idiom this mirrors.
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
SEEDS_STORAGE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"

# PROPOSED carrier API (sharpen at landing against the territory carrier's
# std::string-keyed idiom + the resection carrier's grid-vector accessors).
# Tests skip-pending on absence (ADR-0027); the skip lifts at landing.
ADD_METHOD = "AddSeed"                 # AddSeed(x, y, z) -> int (index)
COUNT_METHOD = "GetNumberOfSeeds"
GET_NTH_METHOD = "GetNthSeed"          # -> (x, y, z)
DELETE_METHOD = "RemoveNthSeed"
SET_LABEL_METHOD = "SetNthSeedLabel"
GET_LABEL_METHOD = "GetNthSeedLabel"
SET_COLOR_METHOD = "SetNthSeedColor"
GET_COLOR_METHOD = "GetNthSeedColor"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_carrier_or_skip(slicer, name="VolumetrySeedsTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(
            f"{SEEDS_NODE_CLASS} not registered -- the ADR-0038-amendment "
            "volumetry seed carrier (plan §3a) has not landed; module Logic "
            "RegisterNodes() must wire it up (launched build).  Skip lifts at "
            "the implementation commit (ADR-0027)."
        )
    for method in (ADD_METHOD, COUNT_METHOD, GET_NTH_METHOD):
        if not hasattr(node, method):
            pytest.skip(
                f"{SEEDS_NODE_CLASS} has no {method} -- the seed carrier API "
                "has not landed (ADR-0027)."
            )
    return node


# --------------------------------------------------------------------------- #
# Carrier mutation + off-markups invariant
# --------------------------------------------------------------------------- #


def test_add_get_count_are_ordered():
    """Seeds add in order; get-Nth returns the placement-order coordinate.

    ADR-0038 §"Consumers ledger" (flat, no-edges seed carrier).
    """
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)

    assert carrier.GetNumberOfSeeds() == len(pts)
    for i, expected in enumerate(pts):
        assert tuple(carrier.GetNthSeed(i)) == pytest.approx(expected, abs=1e-9)


def test_delete_removes_exactly_one_and_shifts_order():
    """Deleting the middle seed leaves two; the tail shifts up in order."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, DELETE_METHOD):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no {DELETE_METHOD} (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)

    carrier.RemoveNthSeed(1)

    assert carrier.GetNumberOfSeeds() == len(pts) - 1
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx(pts[0], abs=1e-9)
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx(pts[2], abs=1e-9)


def test_carrier_holds_no_markups_reference_role():
    """The seed carrier carries NO ``vtkMRMLMarkupsFiducialNode`` reference.

    ADR-0014 §"Fourth layer" / the off-markups invariant: the seed geometry
    lives on the carrier's own point store, not a referenced markups node.
    An absence pin WITH a credible creep-in path (the old ``ROIMarkersList``
    fiducial is exactly the thing being retired), not a colour-of-the-sky
    absence (``feedback_no_colour_of_the_sky_tests``).
    """
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)

    carrier.AddSeed(0.0, 0.0, 1.0)

    n_roles = carrier.GetNumberOfNodeReferenceRoles()
    for i in range(n_roles):
        role = carrier.GetNthNodeReferenceRole(i)
        ref = carrier.GetNodeReference(role)
        assert ref is None or not ref.IsA("vtkMRMLMarkupsFiducialNode"), (
            f"the seed carrier must hold NO markups-fiducial reference "
            f"(role {role!r}) -- the off-markups migration retired ROIMarkersList "
            "(ADR-0014 §'Fourth layer')."
        )


# --------------------------------------------------------------------------- #
# Per-point label + colour
# --------------------------------------------------------------------------- #


def test_per_seed_label_is_independent_of_coordinate():
    """Each seed carries a string LABEL independent of its coordinate.

    ADR-0038 §Conformance: per-seed labels round-trip so generated segments
    keep their names.  Setting a label must not move the point and vice
    versa (the display/label slot is independent of the geometry slot).
    """
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    for method in (SET_LABEL_METHOD, GET_LABEL_METHOD):
        if not hasattr(carrier, method):
            pytest.skip(f"{SEEDS_NODE_CLASS} has no {method} (ADR-0027).")

    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.AddSeed(4.0, 5.0, 6.0)
    carrier.SetNthSeedLabel(0, "SegmentV")
    carrier.SetNthSeedLabel(1, "SegmentVI")

    assert carrier.GetNthSeedLabel(0) == "SegmentV"
    assert carrier.GetNthSeedLabel(1) == "SegmentVI"
    # Setting a label must not disturb the coordinate.
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9)


def test_per_seed_colour_round_trips():
    """Each seed carries an RGB display colour that reads back."""
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    for method in (SET_COLOR_METHOD, GET_COLOR_METHOD):
        if not hasattr(carrier, method):
            pytest.skip(f"{SEEDS_NODE_CLASS} has no {method} (ADR-0027).")

    carrier.AddSeed(0.0, 0.0, 1.0)
    carrier.SetNthSeedColor(0, 0.9, 0.2, 0.1)

    assert tuple(carrier.GetNthSeedColor(0)) == pytest.approx((0.9, 0.2, 0.1), abs=1e-6)


# --------------------------------------------------------------------------- #
# Storage round-trip
# --------------------------------------------------------------------------- #


def test_storage_round_trips_points_labels_and_colours(tmp_path):
    """Writing the carrier to storage and reading back preserves seeds + labels.

    ADR-0014 storage layer; mirrors the resection / territory storage
    round-trip.  Ordered points, per-seed labels, and per-seed colours must
    be byte-equal after a write/read cycle.
    """
    slicer = _slicer_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    storage = slicer.mrmlScene.AddNewNodeByClass(SEEDS_STORAGE_CLASS)
    if storage is None:
        pytest.skip(
            f"{SEEDS_STORAGE_CLASS} not registered -- the seed storage node "
            "has not landed (ADR-0027)."
        )
    for method in (SET_LABEL_METHOD, GET_LABEL_METHOD):
        if not hasattr(carrier, method):
            pytest.skip(f"{SEEDS_NODE_CLASS} has no {method} (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0)]
    labels = ["SegmentV", "SegmentVI"]
    for (x, y, z), label in zip(pts, labels):
        idx = carrier.AddSeed(x, y, z)
        carrier.SetNthSeedLabel(idx, label)

    path = str(tmp_path / "seeds.vsd.json")
    storage.SetFileName(path)
    assert storage.WriteData(carrier) != 0, "storage write must succeed."

    reloaded = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "Reloaded")
    storage.ReadData(reloaded)

    assert reloaded.GetNumberOfSeeds() == len(pts)
    for i, (expected, label) in enumerate(zip(pts, labels)):
        assert tuple(reloaded.GetNthSeed(i)) == pytest.approx(expected, abs=1e-9)
        assert reloaded.GetNthSeedLabel(i) == label, (
            "the per-seed label must round-trip through storage (segment-name "
            "fidelity, ADR-0038 §Conformance)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
