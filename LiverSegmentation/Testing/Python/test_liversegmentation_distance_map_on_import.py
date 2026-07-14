# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stage-2 canonical import triggers the distance-map computation.

The distance-map volume is consumed throughout Stage 4 (the resection plan's
distance-map reference, the resectogram, the resection mappers) but nothing in
the v2 workflow produced it -- Planning opened with no map.  The explicit
human action growing the canonical node is the toolbar **Import…** gesture
(the unified ``importSegmentation`` path, ADR-0034 §Decision 2), so that hook
(the same one that creates the 3D surface representations) also computes the
composed distance map via the ``ensureDistanceMap`` logic seam:

  * reference volume resolved from the Stage-1 ``LiverRole='PortalVenous'``
    tag (``selectInputVolume``);
  * output is a resolve-or-create ``vtkMRMLVectorVolumeNode`` tagged
    ``DistanceMap='True'`` / ``Computed='True'`` (the v1 selector contract);
  * no reference volume -> the import still succeeds and no map is minted
    (graceful degradation, mirroring the surface-representation seam).

Scene-needing (segmentation converter + SimpleITK compute), so this runs under
the launched ``pytest_launched`` row and skips cleanly under bare pytest.
Skips-pending until ``ensureDistanceMap`` lands (RED before impl, ADR-0027).
"""

from __future__ import annotations

import pytest

SCT_LIVER_CODE = "10200004"
SEAM = "ensureDistanceMap"
IMPORT_SEAM = "importSegmentation"


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    slicer = _import_slicer_or_skip()
    _require_mrml_scene()
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _require_seam(logic):
    if not hasattr(logic, SEAM):
        pytest.skip(
            f"LiverSegmentationLogic.{SEAM}() not implemented -- "
            "skip-pending until the distance-map trigger seam lands."
        )
    assert hasattr(logic, IMPORT_SEAM), (
        f"LiverSegmentationLogic.{IMPORT_SEAM}() is missing -- the "
        "distance-map trigger must ride the unified import path "
        "(ADR-0034 §Decision 2)."
    )


def _require_segmentations_module(slicer):
    if not hasattr(slicer.modules, "segmentations"):
        pytest.skip(
            "Segmentations module not loaded; the distance-map trigger "
            "invariant runs in a fully loaded Slicer."
        )


def _source_segmentation_with_geometry(slicer):
    """A source segmentation with one real-geometry segment (cube labelmap).

    The segment is named ``liver`` so the unified import path name-matches
    it against the ``Resources/Terminology/LabelToSCT/`` bridges (ADR-0011)
    and lands it as the liver structure.
    """
    import numpy as np

    labelmap = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLabelMapVolumeNode", "LoadedLM"
    )
    arr = np.zeros((24, 24, 24), dtype=np.int16)
    arr[6:18, 6:18, 6:18] = 1
    slicer.util.updateVolumeFromArray(labelmap, arr)

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Loaded")
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(
        labelmap, node
    )
    slicer.mrmlScene.RemoveNode(labelmap)
    segmentation = node.GetSegmentation()
    assert segmentation.GetNumberOfSegments() >= 1
    segment_id = segmentation.GetNthSegmentID(0)
    segmentation.GetSegment(segment_id).SetName("liver")
    return node, segment_id


def _reference_volume(slicer):
    """A Stage-1 role-tagged scalar reference volume."""
    import numpy as np

    from LiverSegmentationLib.roles import LIVER_ROLE_PORTAL_VENOUS, set_volume_role

    volume = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLScalarVolumeNode", "ReferenceCT"
    )
    slicer.util.updateVolumeFromArray(volume, np.zeros((24, 24, 24), dtype=np.int16))
    assert set_volume_role(volume, LIVER_ROLE_PORTAL_VENOUS)
    return volume


def _distance_map_volumes(slicer):
    return [
        node
        for node in slicer.util.getNodesByClass("vtkMRMLVectorVolumeNode")
        if node.GetAttribute("DistanceMap") == "True"
    ]


def test_import_computes_tagged_distance_map():
    """Importing into the canonical segmentation mints a computed distance map."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)
    _require_segmentations_module(slicer)

    _reference_volume(slicer)
    source, _segId = _source_segmentation_with_geometry(slicer)

    canonical = logic.importSegmentation(source)
    assert canonical is not None

    maps = _distance_map_volumes(slicer)
    assert len(maps) == 1, (
        "import-as-canonical must produce exactly one DistanceMap-tagged "
        f"vector volume (#538); found {len(maps)}."
    )
    dmap = maps[0]
    assert dmap.GetAttribute("Computed") == "True"
    assert dmap.GetImageData() is not None, "distance map must carry image data"
    assert dmap.GetImageData().GetNumberOfScalarComponents() == 1, (
        "only the PRESENT (non-empty) liver channel may compose -- the "
        "pre-seeded empty checklist segments (ADR-0034 §Amendments) must "
        "not become distance-map channels; the components stay dense over "
        "the present channels (the v1 contract the resection shader reads)."
    )


def test_reimport_reuses_the_distance_map_node():
    """A second import recomputes onto the SAME tagged node (no duplicates).

    Two separate sources: a successful import CONSUMES its source node
    (the unified-path contract), so the second import brings its own.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)
    _require_segmentations_module(slicer)

    _reference_volume(slicer)
    first, _segId = _source_segmentation_with_geometry(slicer)
    logic.importSegmentation(first)
    second, _segId = _source_segmentation_with_geometry(slicer)
    logic.importSegmentation(second)

    maps = _distance_map_volumes(slicer)
    assert len(maps) == 1, (
        "re-importing must reuse the existing DistanceMap node, not mint "
        f"another; found {len(maps)}."
    )


def test_import_without_reference_volume_still_succeeds():
    """No Stage-1 reference volume -> import succeeds, no map is minted."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)
    _require_segmentations_module(slicer)

    source, _segId = _source_segmentation_with_geometry(slicer)
    canonical = logic.importSegmentation(source)
    assert canonical is not None, (
        "a missing reference volume must degrade gracefully -- the canonical "
        "import itself succeeds."
    )
    assert _distance_map_volumes(slicer) == [], (
        "without a reference volume no distance map can be computed; none "
        "must be minted."
    )


def test_accept_computes_tagged_distance_map_and_surface_rep():
    """The AI path (Run -> Accept) must produce the map + 3D rep too.

    Every prior end-to-end pass built the canonical node via the import
    path (which computes the distance map and the closed-surface
    representation).  A surgeon going PURE-AI (Run + landing, no import)
    reached Stage 4 with NO distance map and no 3D anatomy -- ``accept()``
    must run the same two post-merge steps.
    """
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)
    _require_segmentations_module(slicer)

    _reference_volume(slicer)

    # A scratch node with one real-geometry, SCT-tagged segment -- the shape
    # a card's Run leaves behind for Accept.
    scratch, segId = _source_segmentation_with_geometry(slicer)
    scratch.SetAttribute("LiverSegmentation.Role", "scratch")
    logic.tagSegmentWithSct(scratch, segId, SCT_LIVER_CODE, "Liver")

    logic.accept(scratch)

    maps = _distance_map_volumes(slicer)
    assert len(maps) == 1, (
        "Accept must compute the DistanceMap-tagged vector volume exactly "
        "like the import path -- the pure-AI Stage-2 path otherwise reaches "
        f"Planning with no map; found {len(maps)}."
    )
    canonical = logic.getOrCreateCanonicalSegmentation()
    assert canonical.GetSegmentation().ContainsRepresentation(
        "Closed surface"
    ), (
        "Accept must ensure the 3D closed-surface representation -- the "
        "main 3D view is otherwise empty entering Stage 4 on the AI path."
    )
