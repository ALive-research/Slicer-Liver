# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins slice 1 -- the Pipeline resolves the style display node.

The band STYLE (margin colours + InterpolatedMargins) lives on the shared
``vtkMRMLParametricSurfaceDisplayNode`` that hangs off the carrier as a
SIBLING of the resectogram display node (one carrier, two display aspects --
Docs/architecture/current-mrml-node-hierarchy.md).  For the strip to show
user-chosen colours, the ``ResectogramPipeline`` must resolve that sibling
and hand it to the ``FlattenedSurfaceRepresentation`` via
``SetSurfaceDisplayNode`` -- mirroring how it already reverse-resolves the
plan wrapper (``test_resectogram_pipeline_resolves_resection_plan.py``).

-- WHY LAUNCHED-SLICER --

Needs the wrapped display nodes + the ``ResectogramPipeline`` whose base
``vtkMRMLLayerDMScriptedPipeline`` is constructible only inside a Slicer
process with SlicerLayerDM loaded.  Skips cleanly under bare pytest.

-- WHY RED NOW --

The Pipeline has no surface-display resolution seam and the Representation
has no ``SetSurfaceDisplayNode``, so the tests SKIP cleanly.  The skip lifts
when resectogram-margins slice 1 lands (ADR-0027 §Conformance).

See also:
  * Docs/architecture/target-mrml-node-hierarchy.md (colour placement)
  * LiverResections/LiverResectionsLib/ResectogramPipeline.py
  * LiverResections/Testing/Python/test_resectogram_pipeline_resolves_resection_plan.py
    (the plan-wrapper resolution precedent this mirrors)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
SURFACE_DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    pytest.importorskip(
        "LayerDMLib",
        reason="ResectogramPipeline's base vtkMRMLLayerDMScriptedPipeline is "
        "only constructible inside a Slicer process with SlicerLayerDM loaded "
        "(the launched pytest_launched row); skipping under bare pytest.",
    )
    try:
        from LiverResectionsLib.ResectogramPipeline import ResectogramPipeline
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"ResectogramPipeline not importable ({exc!r}).")
    return ResectogramPipeline()


def _require_style_seam_or_skip(pipeline):
    """Skip unless the surface-display resolution seam (slice 1) landed."""
    try:
        from LiverResectionsLib.Representations.FlattenedSurfaceRepresentation import (
            FlattenedSurfaceRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"FlattenedSurfaceRepresentation not importable ({exc!r}).")
    if not hasattr(FlattenedSurfaceRepresentation, "SetSurfaceDisplayNode"):
        pytest.skip(
            "FlattenedSurfaceRepresentation has no SetSurfaceDisplayNode -- "
            "resectogram-margins slice 1 has not landed."
        )
    if not hasattr(pipeline, "_resolve_surface_display_node"):
        pytest.skip(
            "ResectogramPipeline has no _resolve_surface_display_node -- "
            "resectogram-margins slice 1 has not landed."
        )


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


class _RecordingRepresentation:
    """Spy standing in for the FlattenedSurfaceRepresentation.

    Records the display node handed through ``SetSurfaceDisplayNode`` --
    "never called" (sentinel) is distinct from an explicit ``None``.
    """

    def __init__(self):
        self.surface_display_node = "sentinel"

    def SetSurfaceDisplayNode(self, node):  # noqa: N802 - VTK verb
        self.surface_display_node = node

    def SetResectionPlanNode(self, node):  # noqa: N802 - VTK verb
        pass

    def SetLocatorNode(self, node):  # noqa: N802 - VTK verb
        pass

    def update(self, display_node, data_node):
        pass


def _wire_carrier(slicer):
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    data.SetAndObserveDisplayNodeID(display.GetID())
    if display.GetDisplayableNode() is not data:
        pytest.skip(
            "display.GetDisplayableNode() does not resolve the carrier in "
            "this build -- cannot exercise the Pipeline's data-node derivation."
        )
    return data, display


def _spy_flattened_representation(pipeline):
    """Dispatch once so the Representations exist, then swap in the spy."""
    pipeline.UpdatePipeline()
    spy = _RecordingRepresentation()
    pipeline._flattened_surface = spy
    # Invalidate the memo so the next dispatch re-threads into the spy.
    pipeline._last_update_key = None
    return spy


def test_pipeline_threads_sibling_surface_display_node():
    """Carrier with BOTH display aspects -> the parametric one is threaded.

    Wire ``data <--displayable-- {resectogram-display, surface-display}``;
    after a dispatch the flattened Representation must have received the
    PARAMETRIC display node (the style source) via ``SetSurfaceDisplayNode``.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_style_seam_or_skip(pipeline)

    data, display = _wire_carrier(slicer)
    surface_display = _add_or_skip(slicer, SURFACE_DISPLAY_NODE_CLASS)
    data.AddAndObserveDisplayNodeID(surface_display.GetID())

    pipeline.SetDisplayNode(display)
    spy = _spy_flattened_representation(pipeline)
    pipeline.UpdatePipeline()

    assert spy.surface_display_node is surface_display, (
        "the Pipeline must resolve the carrier's sibling "
        "vtkMRMLParametricSurfaceDisplayNode and thread it via "
        "SetSurfaceDisplayNode (the band-style source); got "
        f"{spy.surface_display_node!r}."
    )


def test_pipeline_threads_none_without_sibling_display_node():
    """Resectogram-only carrier -> explicit ``SetSurfaceDisplayNode(None)``.

    Pins the graceful default: no parametric sibling means the Representation
    is told so (not left stale), and the mapper's compiled-in colours stand.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_style_seam_or_skip(pipeline)

    data, display = _wire_carrier(slicer)

    pipeline.SetDisplayNode(display)
    spy = _spy_flattened_representation(pipeline)
    pipeline.UpdatePipeline()

    assert spy.surface_display_node is None, (
        "a carrier with no parametric-surface display node must thread an "
        "explicit None (never leave the spy untouched at the sentinel); got "
        f"{spy.surface_display_node!r}."
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
