# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 -- a placed volumetry seed reprojects into the clicked slice at once.

The shared ``SurfacePointPlacementPipelineSlice`` base observes the SLICE
node + the display node (so a reslice re-projects), but NOT the carrier -- so
a seed placed in a slice fires the carrier's ``Modified`` with nobody
listening, and its handle does not project onto the clicked plane until the
next reslice (the reported "seed does not appear until you scroll").

The volumetry slice client (``VolumetrySeedPipelineSlice``) closes that gap
the way ``TerritorySlicePipeline`` already does: it observes the carrier
itself, so the base's shared ``_on_node_modified`` reprojects (and sets the
handles-actor visibility + requests a render) the moment a seed is placed --
no reslice needed.

This file pins that reproject-on-carrier-Modified contract: with the slice
plane through an in-plane seed, adding the seed makes it appear in the
projected key set WITHOUT any further reslice call.

HARNESS: launched Slicer.  Needs LayerDMLib (the base) + the wrapped
``vtkMRMLVolumetrySeedsNode`` carrier / display node + a real
``vtkMRMLSliceNode`` (its ``GetSliceToRAS`` / ``GetXYToRAS``); a bare
``PythonSlicer -m pytest`` SKIPS CLEANLY.  Verify run-vs-skip in the CI log.

References
----------
* ADR-0038 -- §Decision (the base client seam); the base owns the slice
  projection, the client owns its carrier observation.
* VascularTerritoriesLib/TerritorySlicePipeline.py -- the carrier-observation
  precedent (``_ensure_carrier_observed``).
* SlicerLiverInteractionLib/SlicePointProjection.py -- the presence cutoff a
  just-placed in-plane seed satisfies.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "SlicerLiverInteractionLib",
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pipeline_or_skip():
    try:
        from VolumetrySeedPipeline import (
            VolumetrySeedPipelineSlice,
            VOLUMETRY_NAMESPACE,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VolumetrySeedPipelineSlice not importable ({exc!r}) -- the ADR-0038 "
            "volumetry slice client / LayerDMLib base is not reachable here."
        )
    return VolumetrySeedPipelineSlice, VOLUMETRY_NAMESPACE


def _red_slice_node(slicer):
    # The launched harness runs without slice widgets, so no vtkMRMLSliceNode
    # pre-exists (and the conftest clears the scene between tests): create the
    # slice node the pipeline projects against (the in-volume-pick precedent).
    node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSliceNode")
    if node is None:
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSliceNode", "Red")
    if node is None or not hasattr(node, "GetSliceToRAS"):
        pytest.skip("no vtkMRMLSliceNode available in this launched Slicer.")
    return node


def _wire(slicer, Pipeline, namespace, slice_node):
    """A slice pipeline resolving its carrier from the display node + observing it."""
    from PointPlacementState import PointPlacementState

    carrier = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "SliceSeeds")
    display = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "SliceDisplay")
    if carrier is None or display is None or not hasattr(carrier, "AddSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS}/{DISPLAY_NODE_CLASS} not registered.")
    # The overlay gate is default-CLOSED and opened by the module's enter()
    # (PointPlacementState.set_overlays_visible).  A Pipeline test mints its own
    # display node and has no widget, so it models a SHOWING module explicitly.
    from slicer_pytest_support import open_module_overlay_gate

    open_module_overlay_gate(display, "LiverVolumetry")
    PointPlacementState(namespace).set_carrier(display, carrier)

    pipeline = Pipeline()
    pipeline.SetViewNode(slice_node)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()  # LayerDM's post-carrier-bind hook (observer attach)
    for seam in ("GetProjectedKeys", "GetHandlesActor"):
        if not hasattr(pipeline, seam):
            pytest.skip(f"slice base has no {seam} seam.")
    return pipeline, carrier


def test_placed_seed_projects_without_a_reslice(monkeypatch):
    """Adding an in-plane seed projects it immediately -- no reslice needed.

    The plane runs through ``(20, 20, 10)``; a seed placed there fires the
    carrier ``Modified``, and the client's carrier observer drives the base's
    reproject, so the seed's handle appears in the projected key set + the
    handles actor turns visible with NO further reslice (the reported
    scroll-to-see regression).
    """
    slicer = _slicer_or_skip()
    Pipeline, namespace = _import_pipeline_or_skip()
    slice_node = _red_slice_node(slicer)
    # Aim the plane through the seed BEFORE wiring, so the only event after the
    # add is the carrier Modified (never a reslice).
    slice_node.JumpSliceByOffsetting(20.0, 20.0, 10.0)
    pipeline, carrier = _wire(slicer, Pipeline, namespace, slice_node)

    assert pipeline.GetProjectedKeys() == [], "no seed yet -> nothing projected."

    carrier.AddSeed(20.0, 20.0, 10.0)  # the ONLY event: a carrier Modified

    assert pipeline.GetProjectedKeys() == [0], (
        "a seed placed in the clicked plane must project immediately (its key "
        "in the projected set) WITHOUT a reslice."
    )
    assert bool(pipeline.GetHandlesActor().GetVisibility()) is True, (
        "the handles actor must be visible once a seed projects."
    )


def test_reproject_tracks_multiple_placed_seeds(monkeypatch):
    """Each in-plane seed placed projects immediately; the key set grows."""
    slicer = _slicer_or_skip()
    Pipeline, namespace = _import_pipeline_or_skip()
    slice_node = _red_slice_node(slicer)
    slice_node.JumpSliceByOffsetting(20.0, 20.0, 10.0)
    pipeline, carrier = _wire(slicer, Pipeline, namespace, slice_node)

    carrier.AddSeed(20.0, 20.0, 10.0)
    carrier.AddSeed(25.0, 22.0, 10.0)

    assert pipeline.GetProjectedKeys() == [0, 1], (
        "both in-plane seeds must project immediately, keyed by placement order."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
