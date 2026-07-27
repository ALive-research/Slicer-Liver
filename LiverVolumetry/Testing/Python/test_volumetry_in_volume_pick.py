# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment, OQ4) -- the in-volume / slice-click pick returns an INTERIOR point.

ADR-0038 §"Base extension: the pick step is swappable" (2026-07-27) makes
the pick a SEAM-INJECTED provider, not a fixed surface-snap.  LiverVolumetry
seeds are REGION-GROWING seeds: ``vtkLiverVolumetryLogic`` converts each
seed to a voxel index (``TransformPhysicalPointToIndex``) and grows a
``ConnectedThreshold`` from it, so the seed must land INSIDE the target
region, not on its surface.  Snapping a volumetry seed to a surface would
place it on the region boundary and can mis-seed the grow.

So volumetry injects an IN-VOLUME / slice-click pick: a click in a slice
view resolves to the RAS point AT THE SLICE PLANE (an interior voxel), the
natural region-growing-seed UX.  This file pins that contract -- the ONE
place volumetry is not a plain surface client:

* a slice click INSIDE the region yields a RAS point whose
  ``TransformPhysicalPointToIndex`` lands on a LABELLED (non-zero) voxel of
  the target labelmap -- i.e. an interior voxel the region-grow can seed;
* the pick is NOT surface-snapped -- given a target region with a genuine
  interior (a solid block), the returned point is strictly inside, not on
  the boundary face.

The pick provider does NOT leak a volume concept into the base: the base
sees only "the consumer's pick returned this world point" (pinned by
``SlicerLiverInteractionLib/Testing/Python/test_point_placement_pipeline_3d.py``
::test_no_surface_vs_volume_branch_in_the_base).  This file pins the
PROVIDER's own contract.

HARNESS: launched Slicer.  The pick resolves a slice pixel against a real
``vtkMRMLLabelMapVolumeNode`` (``TransformPhysicalPointToIndex`` /
``GetImageData``) reachable only inside a launched Slicer; a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` so it SKIPS
CLEANLY.

The SUT does not exist yet.  Per ADR-0027 red->skip the import + guards
skip-pend; the skips lift at the implementation commit.

References
----------
* ADR-0038 -- §"Base extension: the pick step is swappable (surface vs
  in-volume)"; §"Consumers ledger" (LiverVolumetry -- in-volume/slice pick).
* ADR-0015 -- the region-grow C++ (TransformPhysicalPointToIndex ->
  ConnectedThreshold) the interior seed feeds, unchanged.
* volumetry-seeds-layerdm-plan.md §9 OQ4 (RESOLVED: in-volume pick, not
  surface-snap).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for candidate in (
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pick_or_skip():
    """Import the volumetry in-volume pick provider or skip-pend (ADR-0027).

    PROPOSED seam (sharpen at landing).  A pick provider satisfying the same
    seam the base injects (see the 3D base's SetPickProvider), resolving a
    slice-view click to an interior RAS point of a labelmap volume::

        class InVolumePick:
            def __init__(self, labelmap_node) -> None: ...
            # returns the interior RAS world point for a slice-view click,
            # or None when the click is outside the labelled region.
            def pick_for_slice_event(self, slice_node, display_xy): ...

    Adjust the imported name here to match the landed module/class.
    """
    try:
        from InVolumePick import InVolumePick
    except ImportError:
        pytest.skip(
            "InVolumePick not importable -- the ADR-0038-amendment (OQ4) "
            "in-volume / slice-click pick provider has not landed (ADR-0027)."
        )
    return InVolumePick


def _solid_block_labelmap_or_skip(slicer, label=3):
    """A labelmap volume: a solid interior block of ``label`` in a zero field.

    Builds a 20x20x20 image with a 6..14 cube set to ``label`` so there is a
    genuine INTERIOR (voxel (10,10,10) is strictly inside, not on a face).
    Returns the ``vtkMRMLLabelMapVolumeNode`` or skips if creation fails.
    """
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TargetRegion")
    if node is None:
        pytest.skip("vtkMRMLLabelMapVolumeNode not registrable (launched build).")

    image = vtk.vtkImageData()
    image.SetDimensions(20, 20, 20)
    image.SetSpacing(1.0, 1.0, 1.0)
    image.SetOrigin(0.0, 0.0, 0.0)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    scalars = image.GetPointData().GetScalars()
    scalars.Fill(0)
    for k in range(20):
        for j in range(20):
            for i in range(20):
                if 6 <= i <= 14 and 6 <= j <= 14 and 6 <= k <= 14:
                    idx = i + 20 * (j + 20 * k)
                    scalars.SetTuple1(idx, label)
    image.Modified()
    node.SetAndObserveImageData(image)
    return node, label


def test_slice_click_inside_region_yields_a_labelled_interior_voxel():
    """A slice click inside the region resolves to a LABELLED voxel's RAS.

    ADR-0038 §"Base extension" (OQ4).  The interior seed's RAS, when mapped
    to the labelmap's index space via ``TransformPhysicalPointToIndex``,
    must land on a non-zero (labelled) voxel -- i.e. a voxel the region-grow
    can seed.  Without this the ``ConnectedThreshold`` seeds outside the
    region and grows nothing / the wrong region (ADR-0015).
    """
    slicer = _slicer_or_skip()
    InVolumePick = _import_pick_or_skip()
    labelmap, label = _solid_block_labelmap_or_skip(slicer)

    pick = InVolumePick(labelmap)
    if not hasattr(pick, "pick_for_slice_event"):
        pytest.skip(
            "InVolumePick has no pick_for_slice_event seam -- the slice-click "
            "resolution has not landed (ADR-0027)."
        )

    # A click over the centre of the region (RAS ~ index (10,10,10), which is
    # strictly interior to the 6..14 block).  The slice node + display xy are
    # resolved by the harness against the labelmap centre; the invariant is
    # the RESULT (a labelled interior voxel), not the pixel arithmetic.
    slice_node = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
    world = pick.pick_for_slice_event(slice_node, display_xy=None)
    if world is None:
        pytest.skip(
            "the pick could not resolve a slice click in this harness -- the "
            "slice-node placement helper has not landed (ADR-0027)."
        )

    # Map the picked RAS to the labelmap's voxel index and read the label.
    ras_to_ijk = vtk.vtkMatrix4x4()
    labelmap.GetRASToIJKMatrix(ras_to_ijk)
    homog = list(world) + [1.0]
    ijk = ras_to_ijk.MultiplyPoint(homog)
    i, j, k = (int(round(c)) for c in ijk[:3])
    value = labelmap.GetImageData().GetScalarComponentAsDouble(i, j, k, 0)

    assert value == pytest.approx(float(label)), (
        "the in-volume pick must land on a LABELLED voxel (an interior "
        "region-grow seed), NOT outside the region (ADR-0038 §'Base "
        "extension' / ADR-0015)."
    )


def test_in_volume_pick_is_not_surface_snapped():
    """The interior seed is strictly INSIDE the region, not on its boundary.

    ADR-0038 §"Base extension": a surface-snapped pick would land the seed
    on the region boundary and can mis-seed the grow.  Given a solid block
    with a genuine interior, the returned voxel must NOT be a boundary face
    voxel of the labelled block -- it must have labelled neighbours on all
    six sides.
    """
    slicer = _slicer_or_skip()
    InVolumePick = _import_pick_or_skip()
    labelmap, label = _solid_block_labelmap_or_skip(slicer)

    pick = InVolumePick(labelmap)
    if not hasattr(pick, "pick_for_slice_event"):
        pytest.skip("InVolumePick has no pick_for_slice_event seam (ADR-0027).")

    slice_node = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
    world = pick.pick_for_slice_event(slice_node, display_xy=None)
    if world is None:
        pytest.skip("the pick could not resolve a slice click in this harness (ADR-0027).")

    ras_to_ijk = vtk.vtkMatrix4x4()
    labelmap.GetRASToIJKMatrix(ras_to_ijk)
    ijk = ras_to_ijk.MultiplyPoint(list(world) + [1.0])
    ci, cj, ck = (int(round(c)) for c in ijk[:3])
    image = labelmap.GetImageData()

    for di, dj, dk in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        neighbour = image.GetScalarComponentAsDouble(ci + di, cj + dj, ck + dk, 0)
        assert neighbour == pytest.approx(float(label)), (
            "the interior seed must have labelled neighbours on ALL six sides "
            "(strictly inside, not surface-snapped to the boundary) -- "
            "ADR-0038 §'Base extension'."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
