# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the SYSTEMATIC case matrix for Generate-segments + Compute.

An analytic overlapping-layer phantom (built in-fixture, no external data)
drives every seeding/visibility/volume-grouping case through BOTH products:

* ``LiverVolumetryLogic.computeVolumePerVolume`` (one results row per VOLUME =
  the union of its seeds' carved regions, ``VisibilityCarve`` +
  ``VolumeSegmentAggregation``), and
* ``LiverVolumetryLogic.generateSegments`` ->
  ``vtkLiverVolumetryLogic::GenerateSegmentsLabelMap`` (materialise the seeded
  regions as a new Segmentation + the "Unassigned" leftover).

THE PHANTOM (100^3 @ 1 mm, so 1 voxel == 0.001 mL; every expectation is an
EXACT voxel count computed from the same numpy masks the segments are built
from):

* Parenchyma box 60^3 = 216.000 mL (layer 0).
* Segment_1..4: four z-slabs of the box, 54.000 mL each (layers 1..4).
* Tumor sphere r=12 centred on the Segment_2|Segment_3 boundary = 7.153 mL
  (top layer); tumor∩Segment_2 = 3.356 mL; tumor∩Segment_3 = 3.797 mL.
* Derived: Parenchyma∖Segment_1 = 162.000; Segment_2∖Tumor = 50.644;
  Segment_3∖Tumor = 50.203; Parenchyma∖(four slabs) = 0 (the slabs tile it).

THE CONTRACT UNDER TEST (as the code documents it):

* Compute (per-volume path): each seed's effective region is its BOUND owner
  segment minus the snapshot segments stacked above it (the
  visibility-composed carve rule); a volume's row is the UNION of its seeds'
  effective regions; an empty snapshot means the whole owner (legacy); rows
  are per-volume INDEPENDENT; unbound/ungrouped seeds are skipped; the run
  ends with an explicit "Total volume (<segmentation>)" denominator row (the
  whole segmentation's rasterized region).
* Generate: materialise each seed's claimed region under the SEED's label and
  everything unclaimed as "Unassigned", on the ticked-segments export grid
  (empty tick == all segments).

DESIGN QUESTIONS the matrix surfaced (contract ambiguities for the
maintainer -- each is flagged at its case below, none is silently resolved):

* OQ-A (case 4/6): Generate emits one segment per SEED (distinct flat label)
  while Compute emits one row per VOLUME -- which granularity should the
  materialised segmentation follow, and should names come from seed labels or
  volume labels?
* OQ-B (case 7): two volumes may CLAIM overlapping regions; Compute's
  independent rows then double-count the overlap (sum of rows > organ union)
  while Generate's flat export resolves ownership top-layer-wins.  Which
  semantics is the contract?
* OQ-C (case 2): the "Unassigned" leftover's scope -- everything in the
  ticked export not claimed by any seed's EFFECTIVE region (the reading this
  matrix asserts), vs the current flat-label complement.
* OQ-D (case 3): a seed whose carve is EMPTY (owner fully covered by its
  snapshot) -- Compute emits an explicit 0-row today (pinned as PASS; a
  skip-the-row alternative is a design decision).
* OQ-E (case 10): an ungrouped (legacy) seed is SKIPPED by per-volume Compute
  but INCLUDED by Generate -- the two products disagree on the seed set.
* OQ-F: generated segments carry import-assigned colours; the per-seed /
  per-volume carrier colours are not propagated (no spec anchor yet -- noted,
  not asserted).

PINNED DEFECTS (xfail strict=True keeps the CORRECT expectation while CI
stays green, ADR-0027 red->green; never weakened to match wrong output):

* G1 -- generated-segment NAME SHIFT: ``generateSegments`` names index 0
  "Unassigned" and 1..N from the seeds, but on the no-resection path
  ``GenerateSegmentsLabelMap`` keeps seeded voxels at their ORIGINAL export
  label values (< 99) and marks the leftover 99, and the labelmap import
  orders segments by ASCENDING label value -- so the leftover imports LAST and
  every name lands one region off (the seeded region reads "Unassigned").
* G2 -- two seeds resolving to the SAME flat label (e.g. two seeds in one
  segment) CRASH Generate: the naming loop indexes one segment per seed but
  the labelmap only carries one segment per DISTINCT label, so
  ``GetNthSegment`` returns None; the exception also leaks the scratch
  generated labelmap node into the scene.
* G3 -- Generate is BINDING- and CARVE-BLIND: it re-derives each seed's
  region from the flat ticked-segments export value at the seed coordinate
  (``GetROIPointsLabelValue``), ignoring the carrier's bound owner and
  visibility snapshot -- so a seed Compute measures as 162.000 mL
  materialises as a different 54.000 mL region, and regions Compute includes
  (an un-snapshotted overlap) fall into "Unassigned".

EXECUTION: every test needs wrapped C++ nodes + a live scene, so the whole
matrix SKIPS bare (``PythonSlicer -m pytest``) and RUNS launched
(ADR-0027).  Resection-refined cases are out of scope (the phantom carries no
resection nodes) -- future work.
"""

from __future__ import annotations

import pytest


VOXEL_ML = 0.001
D = 100

ALL_NAMES = ["Parenchyma", "Segment_1", "Segment_2", "Segment_3", "Segment_4", "Tumor"]


# --------------------------------------------------------------------------- #
# Launched-only scaffolding (skips bare, ADR-0027)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_logic_or_skip():
    try:
        from LiverVolumetry import LiverVolumetryLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"LiverVolumetryLogic not importable ({exc!r}).")
    return LiverVolumetryLogic()


class _Phantom:
    """The analytic phantom + its exact voxel-count ground truths."""

    def __init__(self, slicer, logic, volume, segmentation_node, ids, truth):
        self.slicer = slicer
        self.logic = logic
        self.volume = volume
        self.segmentation_node = segmentation_node
        self.ids = ids  # name -> segmentID
        self.truth = truth  # name -> exact voxel count


@pytest.fixture
def phantom():
    """Build the overlapping-layer phantom in-scene (launched only)."""
    slicer = _slicer_or_skip()
    logic = _make_logic_or_skip()

    import numpy as np
    from slicer import util

    probe = slicer.mrmlScene.CreateNodeByClass("vtkMRMLVolumetrySeedsNode")
    if probe is None:
        pytest.skip("vtkMRMLVolumetrySeedsNode not registered (launched build; ADR-0027).")
    probe.UnRegister(None)

    bg = np.zeros((D, D, D), dtype=np.int16)
    bg[20:80, 20:80, 20:80] = 100
    volume = util.addVolumeFromArray(bg, name="GenerationMatrixCT")

    z, y, x = np.mgrid[0:D, 0:D, 0:D]
    parench = (z >= 20) & (z < 80) & (y >= 20) & (y < 80) & (x >= 20) & (x < 80)
    bounds = [(20, 35), (35, 50), (50, 65), (65, 80)]
    slabs = [parench & (z >= lo) & (z < hi) for (lo, hi) in bounds]
    tumor = (((z - 50) ** 2 + (y - 50) ** 2 + (x - 50) ** 2) <= 12 * 12) & parench

    masks = {
        "Parenchyma": parench,
        "Segment_1": slabs[0],
        "Segment_2": slabs[1],
        "Segment_3": slabs[2],
        "Segment_4": slabs[3],
        "Tumor": tumor,
    }

    segmentation_node = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "GenerationMatrixPhantom")
    segmentation_node.CreateDefaultDisplayNodes()
    segmentation_node.SetReferenceImageGeometryParameterFromVolumeNode(volume)
    segmentation = segmentation_node.GetSegmentation()
    ids = {}
    for name in ALL_NAMES:
        sid = segmentation.AddEmptySegment("", name, [0.5, 0.5, 0.5])
        util.updateSegmentBinaryLabelmapFromArray(
            masks[name].astype(np.uint8), segmentation_node, sid, volume)
        ids[name] = sid

    truth = {name: int(mask.sum()) for name, mask in masks.items()}
    truth["Tumor∩Segment_2"] = int((tumor & slabs[1]).sum())
    truth["Tumor∩Segment_3"] = int((tumor & slabs[2]).sum())
    truth["Segment_2∖Tumor"] = int((slabs[1] & ~tumor).sum())
    truth["Segment_3∖Tumor"] = int((slabs[2] & ~tumor).sum())
    truth["Parenchyma∖Segment_1"] = int((parench & ~slabs[0]).sum())

    return _Phantom(slicer, logic, volume, segmentation_node, ids, truth)


# --------------------------------------------------------------------------- #
# Case-construction helpers (carrier API + the write_seed_context seam)
# --------------------------------------------------------------------------- #


def _ras_of(volume, i, j, k):
    import vtk

    m = vtk.vtkMatrix4x4()
    volume.GetIJKToRASMatrix(m)
    p = m.MultiplyPoint([float(i), float(j), float(k), 1.0])
    return p[0], p[1], p[2]


# Seed positions as (i, j, k) on the phantom grid (the array is [k][j][i]).
SEED_TUMOR = (50, 50, 50)  # tumor centre
SEED_S1 = (50, 50, 25)  # inside Segment_1's slab
SEED_S2 = (25, 25, 40)  # Segment_2, outside the tumor
SEED_S2_B = (70, 70, 45)  # another Segment_2 point, outside the tumor
SEED_S3 = (25, 25, 55)  # Segment_3, outside the tumor
SEED_S4 = (50, 50, 70)  # inside Segment_4's slab

# Overlap probe voxels (not seeds): inside the tumor AND the named slab.
TUMOR_IN_S2 = (50, 50, 45)
TUMOR_IN_S3 = (50, 50, 55)


def _top_first(ph, names):
    """The given segments ordered top-first by layer index (the snapshot order)."""
    seg = ph.segmentation_node.GetSegmentation()
    pairs = sorted(((ph.ids[n], seg.GetLayerIndex(ph.ids[n])) for n in names),
                   key=lambda t: -t[1])
    return [sid for sid, _ in pairs]


def _new_carrier(ph, name):
    node = ph.slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumetrySeedsNode", name)
    if node is None or not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip("vtkMRMLVolumetrySeedsNode lacks the context slot (ADR-0027).")
    return node


def _add_seed(ph, carrier, volume_id, ijk, owner_name, context_names, label):
    """One programmatic seed: coordinate + binding + snapshot + label."""
    from LiverVolumetryLib.VisibilityCarve import write_seed_context

    ras = _ras_of(ph.volume, *ijk)
    if volume_id:
        index = carrier.AddSeedToVolume(volume_id, *ras)
    else:
        index = carrier.AddSeed(*ras)
    carrier.SetNthSeedBinding(index, ph.segmentation_node.GetID(), ph.ids[owner_name])
    write_seed_context(carrier, index, _top_first(ph, context_names))
    carrier.SetNthSeedLabel(index, label)
    return index


def _export_all(ph, name="matrixExport"):
    """The ticked-segments export (empty tick == ALL), as the widget builds it."""
    import vtk

    all_ids = vtk.vtkStringArray()
    seg = ph.segmentation_node.GetSegmentation()
    for i in range(seg.GetNumberOfSegments()):
        all_ids.InsertNextValue(seg.GetNthSegmentID(i))
    node = ph.slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", name)
    ph.slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
        ph.segmentation_node, all_ids, node, None)
    return node


def _compute_rows(ph, carrier):
    """Run computeVolumePerVolume into a fresh table -> [(region, mL, pct%), ...]."""
    table = ph.slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "matrixTable")
    ph.logic.computeVolumePerVolume(ph.segmentation_node, carrier, table)
    rows = []
    for r in range(table.GetNumberOfRows()):
        rows.append((table.GetCellText(r, 0),
                     float(table.GetCellText(r, 1)),
                     table.GetCellText(r, 2)))
    return rows


def _ml(voxels):
    return voxels * VOXEL_ML


def _pct(text):
    assert text.endswith("%"), f"percent cell must end with '%': {text!r}"
    return float(text[:-1])


# --------------------------------------------------------------------------- #
# Case 1 -- single seed in the tumor, all segments visible
# --------------------------------------------------------------------------- #


def test_case1_compute_single_seed_measures_the_tumor(phantom):
    """A seed bound to the top layer (nothing above it) measures the whole tumor."""
    carrier = _new_carrier(phantom, "c1")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_TUMOR, "Tumor", ALL_NAMES, "SeedTumor")

    rows = _compute_rows(phantom, carrier)

    assert len(rows) == 2
    region, ml, pct = rows[0]
    assert region == "VolA"
    assert ml == pytest.approx(_ml(phantom.truth["Tumor"]), abs=0.01)
    total_region, total_ml, total_pct = rows[-1]
    assert total_region == "Total volume (GenerationMatrixPhantom)"
    assert total_ml == pytest.approx(_ml(phantom.truth["Parenchyma"]), abs=0.01)
    assert _pct(total_pct) == pytest.approx(100.0, abs=0.01)


# --------------------------------------------------------------------------- #
# Case 2 -- carve context: only Parenchyma + Segment_1 visible, seed outside
# Segment_1.  The seed's effective region is Parenchyma∖Segment_1 = 162.000.
# --------------------------------------------------------------------------- #


def test_case2_compute_measures_the_carved_parenchyma(phantom):
    carrier = _new_carrier(phantom, "c2")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S4, "Parenchyma",
              ["Parenchyma", "Segment_1"], "SeedPar")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Parenchyma∖Segment_1"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 3 -- empty carve: owner Parenchyma under FULL visibility is entirely
# covered by the four slabs + tumor, so the seed's effective region is EMPTY.
# --------------------------------------------------------------------------- #


def test_case3_compute_empty_carve_yields_an_explicit_zero_row(phantom):
    """The current contract EMITS the volume's row with 0 mL (a visible zero).

    OQ-D: skipping the row instead is a design alternative for the maintainer;
    this pins the current, self-consistent behaviour.
    """
    carrier = _new_carrier(phantom, "c3")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Parenchyma", ALL_NAMES, "SeedEmpty")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][0] == "VolA"
    assert rows[0][1] == pytest.approx(0.0, abs=0.01)


# --------------------------------------------------------------------------- #
# Case 4 -- one volume, two seeds on DISJOINT segments (only Segment_2 +
# Segment_3 visible in both snapshots): the row is their union, 108.000.
# --------------------------------------------------------------------------- #


def test_case4_compute_unions_disjoint_seed_regions(phantom):
    carrier = _new_carrier(phantom, "c4")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    context = ["Segment_2", "Segment_3"]
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", context, "SeedS2")
    _add_seed(phantom, carrier, "V1", SEED_S3, "Segment_3", context, "SeedS3")

    rows = _compute_rows(phantom, carrier)

    assert len(rows) == 2, "ONE row per volume (not per seed) + the Total row."
    assert rows[0][1] == pytest.approx(
        _ml(phantom.truth["Segment_2"] + phantom.truth["Segment_3"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 5 -- one volume, two seeds in the SAME segment: no double-count.
# --------------------------------------------------------------------------- #


def test_case5_compute_same_segment_counts_once(phantom):
    carrier = _new_carrier(phantom, "c5")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ["Segment_2"], "SeedA")
    _add_seed(phantom, carrier, "V1", SEED_S2_B, "Segment_2", ["Segment_2"], "SeedB")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_2"]), abs=0.01), (
        "two seeds on the same (owner, snapshot) measure the segment ONCE -- "
        "54.000, never 108.")


# --------------------------------------------------------------------------- #
# Case 6 -- two volumes on disjoint segments: two rows, two seed segments.
# --------------------------------------------------------------------------- #


def test_case6_compute_two_disjoint_volumes(phantom):
    carrier = _new_carrier(phantom, "c6")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "V2", SEED_S4, "Segment_4", ["Segment_4"], "SeedS4")

    rows = _compute_rows(phantom, carrier)

    assert [r[0] for r in rows] == ["VolA", "VolB", "Total volume (GenerationMatrixPhantom)"]
    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_1"]), abs=0.01)
    assert rows[1][1] == pytest.approx(_ml(phantom.truth["Segment_4"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 7 -- two volumes with OVERLAPPING claims (V1: whole Segment_2 -- its
# snapshot shows only Segment_2; V2: the tumor, which overlaps Segment_2).
# --------------------------------------------------------------------------- #


def test_case7_compute_rows_are_independent_and_double_count_overlap(phantom):
    """OQ-B pinned: per-volume rows are INDEPENDENT unions -- V1 measures the
    whole Segment_2 (54.000, tumor overlap included) and V2 the whole tumor
    (7.153), so the rows sum to 61.153 while the organ union of the two claims
    is only 57.797: the tumor∩Segment_2 overlap (3.356) is counted TWICE.
    Whether conflicting claims should be resolved (and how) is a maintainer
    decision; this pins today's arithmetic honestly."""
    carrier = _new_carrier(phantom, "c7")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ["Segment_2"], "SeedS2")
    _add_seed(phantom, carrier, "V2", SEED_TUMOR, "Tumor", ["Tumor"], "SeedT")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_2"]), abs=0.01)
    assert rows[1][1] == pytest.approx(_ml(phantom.truth["Tumor"]), abs=0.01)
    overlap = phantom.truth["Tumor∩Segment_2"]
    assert rows[0][1] + rows[1][1] == pytest.approx(
        _ml(phantom.truth["Segment_2"] + phantom.truth["Tumor"]), abs=0.01), (
        f"the {_ml(overlap):.3f} mL overlap is double-counted across rows (OQ-B).")


# --------------------------------------------------------------------------- #
# Case 8 -- carve + overlap combined: V1 in Segment_2 under FULL visibility
# (carved to Segment_2∖Tumor), V2 in the tumor -- disjoint by construction.
# --------------------------------------------------------------------------- #


def test_case8_compute_carved_claims_are_disjoint(phantom):
    carrier = _new_carrier(phantom, "c8")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ALL_NAMES, "SeedS2")
    _add_seed(phantom, carrier, "V2", SEED_TUMOR, "Tumor", ALL_NAMES, "SeedT")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_2∖Tumor"]), abs=0.01)
    assert rows[1][1] == pytest.approx(_ml(phantom.truth["Tumor"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 9 -- mixed snapshots in ONE volume: seed A in Segment_2 under FULL
# visibility (50.644); seed B in Segment_3 with the tumor HIDDEN (whole
# Segment_3, 54.000).  Union = 104.644 (disjoint slabs).
# --------------------------------------------------------------------------- #


def test_case9_compute_unions_regions_from_different_snapshots(phantom):
    carrier = _new_carrier(phantom, "c9")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ALL_NAMES, "SeedA")
    no_tumor = ["Parenchyma", "Segment_1", "Segment_2", "Segment_3", "Segment_4"]
    _add_seed(phantom, carrier, "V1", SEED_S3, "Segment_3", no_tumor, "SeedB")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][1] == pytest.approx(
        _ml(phantom.truth["Segment_2∖Tumor"] + phantom.truth["Segment_3"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 10 -- an ungrouped (legacy) seed alongside a grouped one.
# --------------------------------------------------------------------------- #


def test_case10_compute_skips_the_ungrouped_seed(phantom):
    """The per-volume path runs (a grouped seed exists) and, per its documented
    contract, the ungrouped seed yields NO row -- only V1's.  OQ-E: Generate
    below INCLUDES the same seed, so the two products disagree on the seed
    set; a maintainer decision is needed."""
    carrier = _new_carrier(phantom, "c10")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "", SEED_S4, "Segment_4", ["Segment_4"], "SeedLegacy")

    rows = _compute_rows(phantom, carrier)

    assert [r[0] for r in rows] == ["VolA", "Total volume (GenerationMatrixPhantom)"]
    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_1"]), abs=0.01)


# --------------------------------------------------------------------------- #
# Case 11 -- zero seeds: Generate is widget-gated ("Place at least one seed.",
# pinned in test_volumetry_action_enablement); at LOGIC level it degrades to a
# single whole-export 'Unassigned' segmentation.  Compute takes the classic
# ticked-segments path (B1): one TRUE per-segment row each + the explicit
# ticked-total row.
# --------------------------------------------------------------------------- #


def test_case11_compute_zero_seeds_reports_per_segment_rows(phantom):
    """The B1 path reports each segment's TRUE (layer-aware) volume -- the
    overlapping tumor still reads 7.153, not its flat-export remainder --
    and ends with the explicit ticked-segments Total row."""
    carrier = _new_carrier(phantom, "c11c")
    export = _export_all(phantom)
    table = phantom.slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "matrixTableB1")
    try:
        phantom.logic.computeVolume(
            export, export, phantom.segmentation_node, table, carrier, None)
    finally:
        phantom.slicer.mrmlScene.RemoveNode(export)

    rows = [(table.GetCellText(r, 0), float(table.GetCellText(r, 1)),
             table.GetCellText(r, 2)) for r in range(table.GetNumberOfRows())]
    by_region = {region: ml for region, ml, _pct_text in rows}

    for name in ALL_NAMES:
        assert by_region[name] == pytest.approx(_ml(phantom.truth[name]), abs=0.01)
    assert rows[-1][0] == "Total volume (ticked segments)"
    assert rows[-1][1] == pytest.approx(_ml(phantom.truth["Parenchyma"]), abs=0.01)
    assert _pct(rows[-1][2]) == pytest.approx(100.0, abs=0.01)


# --------------------------------------------------------------------------- #
# Case 12 -- the % denominator: every per-volume row reads against the whole
# segmentation's region (216.000), and the Total row reads 100%.
# --------------------------------------------------------------------------- #


def test_case12_percent_reads_against_the_named_total_row(phantom):
    carrier = _new_carrier(phantom, "c12")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "V2", SEED_S4, "Segment_4", ["Segment_4"], "SeedS4")

    rows = _compute_rows(phantom, carrier)

    total = _ml(phantom.truth["Parenchyma"])
    assert _pct(rows[0][2]) == pytest.approx(100.0 * rows[0][1] / total, abs=0.01)
    assert _pct(rows[1][2]) == pytest.approx(100.0 * rows[1][1] / total, abs=0.01)
    assert _pct(rows[-1][2]) == pytest.approx(100.0, abs=0.01)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
