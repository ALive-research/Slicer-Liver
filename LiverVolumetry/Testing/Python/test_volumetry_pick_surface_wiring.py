# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment, OQ4) -- the WIRED pickSurface is readable by InVolumePick.

The in-volume pick (``InVolumePick``) resolves interior voxels by reading the
pickSurface node's ``GetImageData`` + RAS<->IJK matrices -- the
``vtkMRMLLabelMapVolumeNode`` API.  The widget's ``_aimPickSurface`` is the
seam that binds a pickSurface onto the shared display node from the user's
INPUT SEGMENTATION selection.  A ``vtkMRMLSegmentationNode`` has NO
``GetImageData`` / IJK API, so if ``_aimPickSurface`` aimed the pick at the
segmentation node directly, EVERY armed click would make the pick raise and
the base would decline -- no seed lands (the interaction was dead in the GUI).

This file pins the WIRING contract the pick-math + placement tests both
missed: they fed a real labelmap or a fixed-world fake pick DIRECTLY, so
neither exercised what ``_aimPickSurface`` actually binds.  Here we drive the
widget's own ``_aimPickSurface`` with a real segmentation input and assert:

* the wired pickSurface is a node ``InVolumePick`` can READ -- ``GetImageData``
  returns a non-``None`` image (a segmentation node fails this);
* a real pick against that wired surface lands on a LABELLED interior voxel,
  i.e. a click through the live path would place a seed.

HARNESS: launched Slicer.  Needs the seed display node, the segmentation
logic's ``ExportSegmentsToLabelmapNode``, and the module widget -- all
reachable only inside a launched Slicer with the module loaded (and a main
window, so the widget's ``.ui`` selectors exist).  A bare ``PythonSlicer -m
pytest`` (no scene / no main window) SKIPS CLEANLY.

References
----------
* ADR-0038 -- §"Base extension: the pick step is swappable (surface vs
  in-volume)"; §"Consumers ledger" (LiverVolumetry -- in-volume/slice pick).
* ADR-0015 -- the region-grow C++ the interior seed feeds, unchanged.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
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
    try:
        from InVolumePick import InVolumePick
    except ImportError:
        pytest.skip(
            "InVolumePick not importable -- the in-volume pick provider has "
            "not landed (ADR-0027)."
        )
    return InVolumePick


def _widget_or_skip(slicer):
    """The LiverVolumetry widget (its ``.ui`` selectors drive ``_aimPickSurface``).

    Needs a main window: the widget's ``_aimPickSurface`` reads the input
    segmentation + segment selection + reference volume off ``self.ui``.  A
    ``--no-main-window`` launch has no widget representation, so skip cleanly.
    """
    module = getattr(slicer.modules, "livervolumetry", None)
    if module is None:
        pytest.skip("livervolumetry module not loaded (ADR-0027).")
    try:
        rep = module.widgetRepresentation()
        widget = rep.self() if rep is not None else None
    except Exception:  # pragma: no cover - no-main-window launch
        widget = None
    if widget is None or not hasattr(widget, "_aimPickSurface"):
        pytest.skip(
            "LiverVolumetry widget / _aimPickSurface unavailable (no main "
            "window, or the pick-surface seam has not landed) -- ADR-0027."
        )
    return widget


def _segmentation_with_solid_block_or_skip(slicer):
    """A segmentation with one segment covering a solid interior block.

    Built from a labelmap so the exported segment has a genuine strictly-
    interior voxel (the region-grow seed target).
    """
    dims = (20, 20, 20)
    image = vtk.vtkImageData()
    image.SetDimensions(*dims)
    image.AllocateScalars(vtk.VTK_SHORT, 1)
    image.GetPointData().GetScalars().Fill(0)
    for k in range(20):
        for j in range(20):
            for i in range(20):
                if 6 <= i <= 14 and 6 <= j <= 14 and 6 <= k <= 14:
                    image.SetScalarComponentFromDouble(i, j, k, 0, 1)
    image.Modified()

    lm = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "SeedBlock")
    if lm is None:
        pytest.skip("vtkMRMLLabelMapVolumeNode not registrable (ADR-0027).")
    lm.SetAndObserveImageData(image)
    seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SeedSeg")
    if seg is None:
        pytest.skip("vtkMRMLSegmentationNode not registrable (ADR-0027).")
    seg.CreateDefaultDisplayNodes()
    imported = slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(lm, seg)
    if not imported:
        pytest.skip("ImportLabelmapToSegmentationNode failed in this harness (ADR-0027).")
    return seg


def _wired_pick_surface(slicer, widget, segmentation):
    """Drive the widget's ``_aimPickSurface`` and return the wired pickSurface.

    Mirrors the live arm path: select the input segmentation, create the seed
    display node, and let ``_aimPickSurface`` bind whatever pickSurface the
    module aims the in-volume pick at.
    """
    widget.ui.InputSegmentSelectorWidget.setCurrentNode(segmentation)
    displayNode = widget._ensureSeedsDisplayNode()
    if displayNode is None or not hasattr(displayNode, "GetPickSurfaceNode"):
        pytest.skip("seed display node / GetPickSurfaceNode unavailable (ADR-0027).")
    widget._aimPickSurface(displayNode)
    return displayNode.GetPickSurfaceNode()


def test_wired_pick_surface_is_readable_by_in_volume_pick():
    """The wired pickSurface exposes image data ``InVolumePick`` can read.

    ADR-0038 §"Base extension".  ``InVolumePick`` calls ``GetImageData`` /
    RAS<->IJK on the pickSurface, so ``_aimPickSurface`` MUST bind a node that
    answers those -- a ``vtkMRMLLabelMapVolumeNode``, NOT the input
    ``vtkMRMLSegmentationNode`` (which has no image-data API).  Binding the
    segmentation directly made every armed click's pick raise and decline --
    the seed placement was dead in the GUI.
    """
    slicer = _slicer_or_skip()
    widget = _widget_or_skip(slicer)
    segmentation = _segmentation_with_solid_block_or_skip(slicer)

    pickSurface = _wired_pick_surface(slicer, widget, segmentation)
    assert pickSurface is not None, "the arm must bind a pickSurface (ADR-0038)."
    assert hasattr(pickSurface, "GetImageData"), (
        "the wired pickSurface must be an image-data node the in-volume pick "
        "can read -- a segmentation node (no GetImageData) makes every click "
        "decline (ADR-0038 §'Base extension')."
    )
    assert pickSurface.GetImageData() is not None, (
        "the wired pickSurface must carry non-empty image data for the "
        "in-volume pick (ADR-0038 §'Base extension')."
    )


def test_pick_against_wired_surface_lands_on_a_labelled_interior_voxel():
    """A pick against the WIRED pickSurface lands on a labelled interior voxel.

    ADR-0038 §"Base extension" + ADR-0015.  End-to-end over the widget's own
    ``_aimPickSurface`` binding (not a hand-fed labelmap): the pick must
    resolve to a labelled voxel a region-grow can seed -- i.e. a live click
    would place a seed rather than decline.
    """
    slicer = _slicer_or_skip()
    InVolumePick = _import_pick_or_skip()
    widget = _widget_or_skip(slicer)
    segmentation = _segmentation_with_solid_block_or_skip(slicer)

    pickSurface = _wired_pick_surface(slicer, widget, segmentation)
    if pickSurface is None or pickSurface.GetImageData() is None:
        pytest.skip("no readable pickSurface wired in this harness (ADR-0027).")

    pick = InVolumePick(pickSurface)
    # display_xy=None takes the interior-centroid path, which ignores the slice
    # geometry, so no slice node is needed (and creating a duplicate "Red" node
    # would collide with a main-window layout's singleton).  The invariant is
    # that the WIRED surface resolves to a labelled interior voxel at all.
    world = pick.pick_for_slice_event(None, display_xy=None)
    assert world is not None, (
        "the pick against the wired labelmap must resolve an interior seed "
        "(a segmentation-node pickSurface would raise -> None -> declined "
        "click -- the reproduced bug)."
    )

    ras_to_ijk = vtk.vtkMatrix4x4()
    pickSurface.GetRASToIJKMatrix(ras_to_ijk)
    ijk = ras_to_ijk.MultiplyPoint(list(world) + [1.0])
    i, j, k = (int(round(c)) for c in ijk[:3])
    value = pickSurface.GetImageData().GetScalarComponentAsDouble(i, j, k, 0)
    assert value != 0, (
        "the pick must land on a LABELLED voxel of the wired surface (an "
        "interior region-grow seed) -- ADR-0038 §'Base extension' / ADR-0015."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
