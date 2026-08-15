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

THE CONTRACT UNDER TEST -- ONE region definition, TWO products.  Compute
measures it and Generate materialises it, so a results row's mL and the
segment carrying that row's name are the same voxels by construction:

* THE REGION.  A seed's EFFECTIVE region is its BOUND owner segment minus the
  snapshot segments stacked above it (the visibility-composed carve rule); an
  empty snapshot means the whole owner (legacy).  A VOLUME's region is the
  UNION of its seeds' effective regions.
* Compute emits one row per volume, per-volume INDEPENDENT (so two volumes
  claiming the same voxels each count it -- the rows can sum past the organ),
  and ends with an explicit "Total volume (<segmentation>)" denominator row
  (the whole segmentation's rasterized region).
* Generate emits one SEGMENT per volume on the ticked-segments export grid
  (empty tick == all segments), named with the VOLUME's label and coloured
  with the VOLUME's colour, PLUS one "Unassigned" segment = the ticked export
  minus every claim, omitted entirely when empty.
* OVERLAPS SURVIVE: two volumes claiming the same voxel keep it in BOTH
  segments (Slicer stores overlapping binary labelmaps as separate layers) --
  the materialised counterpart of Compute's independent rows, never a
  top-layer-wins resolution.
* SKIPS AGREE: ungrouped seeds and empty-carve seeds claim nothing in either
  product (Compute still emits the volume's honest 0 mL row -- a visible zero
  -- while Generate omits the empty segment, since an empty region is nothing
  to show).

The matrix drives every seeding/visibility/volume-grouping case through both
products and asserts the SAME regions on both sides, geometrically (a named
region must CONTAIN the voxels that define it) and not by voxel count alone:
counts coincide between the correct region and a wrong one (case 2:
Parenchyma∖Segment_1 and Parenchyma∖Segment_4 are both 162.000 mL).

EXECUTION: every test needs wrapped C++ nodes + a live scene, so the whole
matrix SKIPS bare (``PythonSlicer -m pytest``) and RUNS launched
(ADR-0027).

FUTURE WORK: the resection-refined Generate (Refine-by-resection ON) is out
of scope here -- the phantom carries no resection nodes, and that path stays
on the C++ region-grow partition bounded by the Bezier barriers (ADR-0015),
which is per-SEED (one piece per seed) rather than per-volume.  A phantom
carrying barrier surfaces would be needed to extend the matrix over it.
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
    truth["Segment_2∪Tumor"] = int((slabs[1] | tumor).sum())

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


class _Region:
    """A generated segment: name + colour + voxel count + mask on the phantom grid."""

    def __init__(self, name, colour, count, mask):
        self.name = name
        self.colour = colour
        self.count = count
        self.mask = mask


def _generate(ph, carrier):
    """Run generateSegments on the all-segments export -> the generated regions.

    Voxel COUNTS alone can coincide between the correct region and a wrong one
    (e.g. case 2: Parenchyma∖Segment_1 and Parenchyma∖Segment_4-flat are both
    162.000 mL), so each region also carries its MASK for geometric asserts.
    """
    from slicer import util

    export = _export_all(ph)
    before = {n.GetID() for n in util.getNodesByClass("vtkMRMLSegmentationNode")}
    try:
        ph.logic.generateSegments(None, carrier, export)
    finally:
        ph.slicer.mrmlScene.RemoveNode(export)
    generated = [n for n in util.getNodesByClass("vtkMRMLSegmentationNode")
                 if n.GetID() not in before]
    assert len(generated) == 1, "Generate must add exactly ONE segmentation node."
    seg = generated[0].GetSegmentation()
    entries = []
    for i in range(seg.GetNumberOfSegments()):
        sid = seg.GetNthSegmentID(i)
        array = util.arrayFromSegmentBinaryLabelmap(generated[0], sid, ph.volume)
        entries.append(_Region(
            seg.GetNthSegment(i).GetName(),
            tuple(seg.GetNthSegment(i).GetColor()),
            int(array.sum()) if array is not None else -1,
            array.astype(bool) if array is not None else None))
    return entries


def _counts_by_name(entries):
    return {r.name: r.count for r in entries}


def _contains(region, ijk):
    """True iff the region's mask covers the (i, j, k) voxel (array is [k][j][i])."""
    i, j, k = ijk
    return region.mask is not None and bool(region.mask[k, j, i])


def _names_at(entries, ijk):
    """The names of EVERY generated region covering the (i, j, k) voxel.

    A set, not a single owner: claims may overlap, and the overlap surviving
    in both segments is the contract (never a top-layer-wins resolution).
    """
    return {r.name for r in entries if _contains(r, ijk)}


def _region_at(entries, ijk):
    """The generated region covering the (i, j, k) voxel, where it is unique."""
    hits = [r for r in entries if _contains(r, ijk)]
    assert len(hits) == 1, (
        f"exactly one generated segment must own voxel {ijk}; got "
        f"{[r.name for r in hits]!r}")
    return hits[0]


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


def test_case1_generate_names_bind_to_the_volume_regions(phantom):
    """The claimed region carries the VOLUME's label; the leftover is 'Unassigned'."""
    carrier = _new_carrier(phantom, "c1g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_TUMOR, "Tumor", ALL_NAMES, "SeedTumor")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Tumor"],
        "Unassigned": phantom.truth["Parenchyma"] - phantom.truth["Tumor"],
    }
    assert _region_at(entries, SEED_TUMOR).name == "VolA", (
        "the segment carrying the volume's label must CONTAIN its seed's voxel.")


def test_case1_generate_falls_back_to_the_volume_id_when_unlabelled(phantom):
    """An unlabelled volume names its segment with its id -- never blank.

    The same fallback Compute's row name uses (``GetVolumeLabel or volumeId``),
    so a volume the surgeon has not named yet still produces a segment that
    can be told apart in the Data module."""
    carrier = _new_carrier(phantom, "c1gid")
    carrier.AddVolume("V1")  # no SetVolumeLabel
    _add_seed(phantom, carrier, "V1", SEED_TUMOR, "Tumor", ALL_NAMES, "SeedTumor")

    entries = _generate(phantom, carrier)

    assert _region_at(entries, SEED_TUMOR).name == "V1"


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


def test_case2_generate_honours_the_binding_and_the_carve(phantom):
    """Generate materialises the SAME region Compute measures: the seed's
    bound Parenchyma minus its snapshot's Segment_1 (162.000 mL), leaving
    Unassigned = the export's remaining 54.000 mL ('Unassigned' == everything
    not claimed by any volume's effective region)."""
    carrier = _new_carrier(phantom, "c2g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S4, "Parenchyma",
              ["Parenchyma", "Segment_1"], "SeedPar")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Parenchyma∖Segment_1"],
        "Unassigned": phantom.truth["Segment_1"],
    }
    # Geometry, not just counts: the binding/carve-blind flat-export reading
    # ALSO yields a 162.000 leftover (Parenchyma minus the slab under the
    # seed), so the count map alone can pass while the region is wrong-shaped.
    assert _region_at(entries, SEED_S4).name == "VolA", (
        "the claimed region must contain its seed's own voxel.")
    assert _region_at(entries, SEED_S1).name == "Unassigned", (
        "the snapshot's Segment_1 is the only unclaimed region.")


# --------------------------------------------------------------------------- #
# Case 3 -- empty carve: owner Parenchyma under FULL visibility is entirely
# covered by the four slabs + tumor, so the seed's effective region is EMPTY.
# --------------------------------------------------------------------------- #


def test_case3_compute_empty_carve_yields_an_explicit_zero_row(phantom):
    """Compute EMITS the volume's row with 0 mL -- a visible zero.

    The contract's asymmetry, and it is deliberate: a table row can SAY zero
    (the volume was measured and measures nothing), while Generate has no way
    to show an empty segment, so it omits it (case 3's Generate side).
    """
    carrier = _new_carrier(phantom, "c3")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Parenchyma", ALL_NAMES, "SeedEmpty")

    rows = _compute_rows(phantom, carrier)

    assert rows[0][0] == "VolA"
    assert rows[0][1] == pytest.approx(0.0, abs=0.01)


def test_case3_generate_empty_carve_contributes_nothing(phantom):
    """A volume whose effective region is empty generates NO segment: the
    output is the 'Unassigned' leftover alone.

    The Generate side of Compute's 0 mL row -- the two agree on the region
    (nothing), and differ only in how "nothing" is best shown: Compute states
    the zero in words, Generate omits a segment that would carry no voxels."""
    carrier = _new_carrier(phantom, "c3g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Parenchyma", ALL_NAMES, "SeedEmpty")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {"Unassigned": phantom.truth["Parenchyma"]}


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


def test_case4_generate_materialises_the_snapshot_regions(phantom):
    """ONE segment per VOLUME, not per seed: the volume's two seeds union into
    a single 108.000 mL segment carrying the volume's label -- the exact
    region Compute's single row for that volume measured."""
    carrier = _new_carrier(phantom, "c4g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    context = ["Segment_2", "Segment_3"]
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", context, "SeedS2")
    _add_seed(phantom, carrier, "V1", SEED_S3, "Segment_3", context, "SeedS3")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_2"] + phantom.truth["Segment_3"],
        "Unassigned": phantom.truth["Parenchyma"]
        - phantom.truth["Segment_2"] - phantom.truth["Segment_3"],
    }
    assert _region_at(entries, SEED_S2).name == "VolA"
    assert _region_at(entries, SEED_S3).name == "VolA"
    # The snapshots HIDE the tumor, so the tumor-covered slab voxels belong to
    # the volume's claim, never to 'Unassigned'.
    assert _region_at(entries, TUMOR_IN_S2).name == "VolA"
    assert _region_at(entries, TUMOR_IN_S3).name == "VolA"


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


def test_case5_generate_two_seeds_same_segment_must_not_raise(phantom):
    """Two seeds in one segment generate that segment ONCE + the leftover.

    Never a crash: the per-volume fold keeps DISTINCT (owner, snapshot) pairs,
    so two seeds sharing both collapse to one region instead of indexing a
    segment that was never created."""
    carrier = _new_carrier(phantom, "c5g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ["Segment_2"], "SeedA")
    _add_seed(phantom, carrier, "V1", SEED_S2_B, "Segment_2", ["Segment_2"], "SeedB")

    entries = _generate(phantom, carrier)  # must not raise

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_2"],
        "Unassigned": phantom.truth["Parenchyma"] - phantom.truth["Segment_2"],
    }
    claimed = _region_at(entries, SEED_S2)
    assert _contains(claimed, SEED_S2_B), (
        "ONE region claims both seeds' voxels (they share the segment).")
    assert claimed.count == phantom.truth["Segment_2"]


def test_case5_generate_leaves_no_scratch_node_behind(phantom):
    """Generate adds the segmentation and NOTHING else: no scratch labelmap
    survives the run (the crash path used to leak one into the scene)."""
    from slicer import util

    carrier = _new_carrier(phantom, "c5leak")
    carrier.AddVolume("V1")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ["Segment_2"], "SeedA")
    _add_seed(phantom, carrier, "V1", SEED_S2_B, "Segment_2", ["Segment_2"], "SeedB")

    before = {n.GetID() for n in util.getNodesByClass("vtkMRMLLabelMapVolumeNode")}
    _generate(phantom, carrier)
    after = {n.GetID() for n in util.getNodesByClass("vtkMRMLLabelMapVolumeNode")}

    assert after == before, "Generate leaked a scratch labelmap into the scene."


# --------------------------------------------------------------------------- #
# Case 6 -- two volumes on disjoint segments: two rows, two volume segments.
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


def test_case6_generate_tiles_the_disjoint_regions(phantom):
    """Two volumes on disjoint claims tile the export: each slab once, named +
    coloured from ITS volume, plus the 108.000 mL leftover."""
    carrier = _new_carrier(phantom, "c6g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.SetVolumeColor("V1", 1.0, 0.0, 0.0)
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    carrier.SetVolumeColor("V2", 0.0, 0.0, 1.0)
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "V2", SEED_S4, "Segment_4", ["Segment_4"], "SeedS4")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_1"],
        "VolB": phantom.truth["Segment_4"],
        "Unassigned": phantom.truth["Parenchyma"]
        - phantom.truth["Segment_1"] - phantom.truth["Segment_4"],
    }
    assert _region_at(entries, SEED_S1).name == "VolA"
    assert _region_at(entries, SEED_S4).name == "VolB"
    assert _region_at(entries, SEED_TUMOR).name == "Unassigned", (
        "the unclaimed middle (Segment_2+Segment_3) is the leftover region.")
    # The surgeon's own volume colours carry into the generated segments, so
    # the materialised segmentation reads like the seeds table it came from.
    by_name = {r.name: r for r in entries}
    assert by_name["VolA"].colour == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)
    assert by_name["VolB"].colour == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)


# --------------------------------------------------------------------------- #
# Case 7 -- two volumes with OVERLAPPING claims (V1: whole Segment_2 -- its
# snapshot shows only Segment_2; V2: the tumor, which overlaps Segment_2).
# --------------------------------------------------------------------------- #


def test_case7_compute_rows_are_independent_and_double_count_overlap(phantom):
    """Per-volume rows are INDEPENDENT unions -- V1 measures the whole
    Segment_2 (54.000, tumor overlap included) and V2 the whole tumor (7.153),
    so the rows sum to 61.153 while the organ union of the two claims is only
    57.797: the tumor∩Segment_2 overlap (3.356) is counted TWICE, by design.
    Each row answers "how big is THIS volume", not "how is the organ divided";
    the Generate side keeps the same overlap in both segments."""
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


def test_case7_generate_preserves_the_overlap_in_both_volumes(phantom):
    """Overlapping claims survive as overlapping SEGMENTS -- the materialised
    counterpart of Compute's independent rows.

    V1 claims the whole Segment_2 (54.000) and V2 the whole tumor (7.153);
    their 3.356 mL intersection stays in BOTH segments (separate binary
    labelmap layers), so each volume's segment reads exactly the mL its
    Compute row reported -- neither is silently carved by the other, and
    "Unassigned" is the export minus their UNION (counted once)."""
    carrier = _new_carrier(phantom, "c7g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ["Segment_2"], "SeedS2")
    _add_seed(phantom, carrier, "V2", SEED_TUMOR, "Tumor", ["Tumor"], "SeedT")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_2"],
        "VolB": phantom.truth["Tumor"],
        "Unassigned": phantom.truth["Parenchyma"] - phantom.truth["Segment_2∪Tumor"],
    }
    # THE overlap pin: a tumor∩Segment_2 voxel is in BOTH volumes' segments.
    assert _names_at(entries, TUMOR_IN_S2) == {"VolA", "VolB"}, (
        "the overlap must survive in both segments, not be resolved to one.")
    # ... and the layers really are distinct (a collapsed representation would
    # have silently dropped one of the two claims above).
    by_name = {r.name: r for r in entries}
    overlap = int((by_name["VolA"].mask & by_name["VolB"].mask).sum())
    assert overlap == phantom.truth["Tumor∩Segment_2"]


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


def test_case8_generate_tiles_without_overlap(phantom):
    """Carve-disjoint claims tile: 50.644 + 7.153 + 158.203, no overlap.

    V1's snapshot SHOWS the tumor, so its own carve already excludes
    tumor∩Segment_2 -- the exclusion comes from the seed's visibility, not
    from a resolution between the two volumes (case 7 keeps the overlap when
    the snapshot does not carve it)."""
    carrier = _new_carrier(phantom, "c8g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    carrier.AddVolume("V2")
    carrier.SetVolumeLabel("V2", "VolB")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ALL_NAMES, "SeedS2")
    _add_seed(phantom, carrier, "V2", SEED_TUMOR, "Tumor", ALL_NAMES, "SeedT")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_2∖Tumor"],
        "VolB": phantom.truth["Tumor"],
        "Unassigned": phantom.truth["Parenchyma"]
        - phantom.truth["Segment_2∖Tumor"] - phantom.truth["Tumor"],
    }
    assert _region_at(entries, SEED_S2).name == "VolA"
    assert _names_at(entries, TUMOR_IN_S2) == {"VolB"}
    assert _region_at(entries, SEED_S1).name == "Unassigned"


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


def test_case9_generate_respects_per_seed_snapshots(phantom):
    """One volume, two DIFFERENT snapshots: the segment is their union.

    Seed A shows the tumor (its carve drops tumor∩Segment_2), seed B hides it
    (its carve keeps tumor∩Segment_3) -- each seed's own snapshot is honoured
    inside the single per-volume segment, which reads Compute's 104.644 mL."""
    carrier = _new_carrier(phantom, "c9g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S2, "Segment_2", ALL_NAMES, "SeedA")
    no_tumor = ["Parenchyma", "Segment_1", "Segment_2", "Segment_3", "Segment_4"]
    _add_seed(phantom, carrier, "V1", SEED_S3, "Segment_3", no_tumor, "SeedB")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_2∖Tumor"] + phantom.truth["Segment_3"],
        "Unassigned": phantom.truth["Parenchyma"]
        - phantom.truth["Segment_2∖Tumor"] - phantom.truth["Segment_3"],
    }
    assert _region_at(entries, SEED_S2).name == "VolA"
    assert _region_at(entries, SEED_S3).name == "VolA"
    # Per-seed snapshots inside the one volume: A shows the tumor
    # (tumor∩Segment_2 stays unclaimed); B hides it (tumor∩Segment_3 is
    # claimed).
    assert _region_at(entries, TUMOR_IN_S2).name == "Unassigned"
    assert _region_at(entries, TUMOR_IN_S3).name == "VolA"


# --------------------------------------------------------------------------- #
# Case 10 -- an ungrouped (legacy) seed alongside a grouped one.
# --------------------------------------------------------------------------- #


def test_case10_compute_skips_the_ungrouped_seed(phantom):
    """The per-volume path runs (a grouped seed exists) and, per its documented
    contract, the ungrouped seed yields NO row -- only V1's.  Generate below
    skips the same seed: the two products agree on the seed set."""
    carrier = _new_carrier(phantom, "c10")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "", SEED_S4, "Segment_4", ["Segment_4"], "SeedLegacy")

    rows = _compute_rows(phantom, carrier)

    assert [r[0] for r in rows] == ["VolA", "Total volume (GenerationMatrixPhantom)"]
    assert rows[0][1] == pytest.approx(_ml(phantom.truth["Segment_1"]), abs=0.01)


def test_case10_generate_skips_the_ungrouped_seed(phantom):
    """Generate materialises VOLUMES, so an ungrouped (legacy) seed claims
    nothing -- exactly the seed Compute skipped.  Its region falls to
    'Unassigned', where the surgeon can see it is unclaimed and group it."""
    carrier = _new_carrier(phantom, "c10g")
    carrier.AddVolume("V1")
    carrier.SetVolumeLabel("V1", "VolA")
    _add_seed(phantom, carrier, "V1", SEED_S1, "Segment_1", ["Segment_1"], "SeedS1")
    _add_seed(phantom, carrier, "", SEED_S4, "Segment_4", ["Segment_4"], "SeedLegacy")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {
        "VolA": phantom.truth["Segment_1"],
        "Unassigned": phantom.truth["Parenchyma∖Segment_1"],
    }
    assert _region_at(entries, SEED_S4).name == "Unassigned", (
        "the ungrouped seed's region is NOT claimed (Compute skips it too).")


# --------------------------------------------------------------------------- #
# Case 11 -- zero seeds: Generate is widget-gated ("Place at least one seed.",
# pinned in test_volumetry_action_enablement); at LOGIC level it degrades to a
# single whole-export 'Unassigned' segmentation.  Compute takes the classic
# ticked-segments path (B1): one TRUE per-segment row each + the explicit
# ticked-total row.
# --------------------------------------------------------------------------- #


def test_case11_generate_zero_seeds_yields_the_unassigned_whole(phantom):
    carrier = _new_carrier(phantom, "c11")

    entries = _generate(phantom, carrier)

    assert _counts_by_name(entries) == {"Unassigned": phantom.truth["Parenchyma"]}


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
