# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stage-2 canonical segments get a visible 3D surface representation (#539).

A loaded segmentation arrives with only a binary-labelmap representation, so
the main 3D view is empty entering Stage 4 (Planning).  Promoting it to
canonical (``importSegmentationAsCanonical``) must also generate the
**closed-surface representation** and turn on 3D visibility, via the
``ensureSurfaceRepresentation`` logic seam.

Scene-needing (builds a real segmentation with geometry + runs the segmentation
converter), so this runs under the launched-Slicer ``pytest_launched`` row and
skips cleanly under bare ``PythonSlicer -m pytest``.  Skips-pending until
``ensureSurfaceRepresentation`` lands (RED before impl, green after).
"""

from __future__ import annotations

import pytest

CLOSED_SURFACE = "Closed surface"
SCT_LIVER_CODE = "10200004"
SURFACE_SEAM = "ensureSurfaceRepresentation"


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
    if not hasattr(logic, SURFACE_SEAM):
        pytest.skip(
            f"LiverSegmentationLogic.{SURFACE_SEAM}() not implemented -- #539 "
            "skip-pending until the surface-representation seam lands."
        )


def _source_segmentation_with_geometry(slicer):
    """A source segmentation carrying one segment with real labelmap geometry.

    Built by importing a small cube labelmap so the closed-surface converter
    has something to triangulate.  Returns ``(node, segmentId)``.

    Needs the Segmentations module logic (labelmap import).  The CI launched
    harness does not load it yet (#460 registration gap), so skip cleanly when
    it is absent rather than failing -- the invariant is exercised in a fully
    loaded Slicer.
    """
    import numpy as np

    if not hasattr(slicer.modules, "segmentations"):
        pytest.skip(
            "Segmentations module not loaded (CI launched harness, #460); the "
            "surface-representation invariant runs in a fully loaded Slicer."
        )

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
    assert segmentation.GetNumberOfSegments() >= 1, "import must yield a segment"
    return node, segmentation.GetNthSegmentID(0)


def test_import_as_canonical_creates_visible_surface_representation():
    """Promoting a loaded segmentation to canonical must give it a visible
    closed-surface representation (#539)."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    source, segId = _source_segmentation_with_geometry(slicer)
    canonical = logic.importSegmentationAsCanonical(
        source, {segId: (SCT_LIVER_CODE, "Liver")}
    )
    assert canonical is not None

    segmentation = canonical.GetSegmentation()
    assert segmentation.ContainsRepresentation(CLOSED_SURFACE), (
        "canonical segmentation must carry the closed-surface representation so "
        "the anatomy renders in 3D through Planning (#539)."
    )

    display = canonical.GetDisplayNode()
    assert display is not None, "canonical node must have a display node"
    assert display.GetVisibility3D(), (
        "canonical segmentation must be visible in 3D (else the Planning 3D "
        "view is empty)."
    )


def test_ensure_surface_representation_tolerates_none():
    """The seam is a no-op on a None node (defensive)."""
    _slicer, logic = _logic_or_skip()
    _require_seam(logic)
    logic.ensureSurfaceRepresentation(None)  # must not raise
