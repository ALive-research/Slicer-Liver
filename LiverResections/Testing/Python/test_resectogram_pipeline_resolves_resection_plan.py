# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 5 -- the ResectogramPipeline reverse-resolves its plan wrapper.

The resectogram's flattened strip shades from the SAME distance field the 3D
Bezier path uses.  ADR-0031 clusters the three wrapper-owned inputs the band
needs on the ``vtkMRMLResectionPlanNode`` wrapper: the distance-map volume, the
safety margin, and the risk (uncertainty) margin.  Slice 5 ports the 3D path's
wrapper-threading (already landed on ``LiverBezierSurfacePipeline`` +
``BezierPlanningRepresentation``) into the resectogram path.

The gap this pins: ``ResectogramPipeline`` derives its data node (the carrier)
from the resectogram display node's ``GetDisplayableNode()`` back-reference, but
never resolves the orchestrating wrapper -- so the flattened strip renders with
NO margin shading and reads the distance map off the wrong (carrier) layer.  The
fix mirrors ``LiverBezierSurfacePipeline._resolve_resection_node`` /
``GetResectionNode``: reverse-walk the ``geometry`` back-reference (the plan whose
``GetGeometryNode()`` is our data node is our wrapper) and hand it to the
``FlattenedSurfaceRepresentation`` via ``SetResectionPlanNode`` before / within
``UpdatePipeline`` -- no external caller required.

-- WHY LAUNCHED-SLICER --

Needs the wrapped ``vtkMRMLResectionPlanNode`` / ``vtkMRMLBezierSurfaceNode`` /
``vtkMRMLResectogramDisplayNode`` + the importable ``ResectogramPipeline`` whose
base ``vtkMRMLLayerDMScriptedPipeline`` is constructible only inside a Slicer
process with SlicerLayerDM loaded.  Skips cleanly under bare
``PythonSlicer -m pytest``.

-- WHY RED NOW --

The ResectogramPipeline has no reverse-resolution seam yet
(``GetResectionNode`` / ``_resolve_resection_node`` absent, or the
``FlattenedSurfaceRepresentation`` has no ``SetResectionPlanNode``), so the
tests SKIP cleanly.  The skip lifts when slice 5 lands (ADR-0027 §Conformance).

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md
  * Docs/adr/0013-layerdm-pipeline-pattern.md §3, §5, §6
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer" (wrapper/carrier)
  * Docs/adr/0027-invariant-test-first-v2-implementation.md
  * LiverResections/LiverResectionsLib/ResectogramPipeline.py
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
    (_resolve_resection_node -- the 3D-path precedent this ports)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    """Construct a ``ResectogramPipeline`` or skip if unimportable.

    Skips cleanly when LayerDMLib (the Pipeline base class) is not importable
    -- i.e. outside a launched Slicer with the SlicerLayerDM extension.
    """
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


def _require_resolve_seam_or_skip(pipeline):
    """Skip unless the wrapper reverse-resolution seam (slice 5) has landed.

    RED == the ``ResectogramPipeline`` has no ``GetResectionNode`` /
    ``_resolve_resection_node`` and / or the ``FlattenedSurfaceRepresentation``
    has no ``SetResectionPlanNode``.  The skip lifts when slice 5 ports the
    3D path's wrapper-threading (ADR-0027 §Conformance).
    """
    try:
        from LiverResectionsLib.Representations.FlattenedSurfaceRepresentation import (
            FlattenedSurfaceRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"FlattenedSurfaceRepresentation not importable ({exc!r}).")
    if not hasattr(FlattenedSurfaceRepresentation, "SetResectionPlanNode"):
        pytest.skip(
            "FlattenedSurfaceRepresentation has no SetResectionPlanNode -- "
            "#501 slice 5 (the wrapper-threading seam) has not landed."
        )
    if not hasattr(pipeline, "GetResectionNode"):
        pytest.skip(
            "ResectogramPipeline has no GetResectionNode -- #501 slice 5 "
            "(the wrapper reverse-resolution) has not landed."
        )


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _wire_surface_with_resectogram_display(slicer):
    """Create a Bezier carrier + its resectogram display node, wired so
    ``display.GetDisplayableNode()`` resolves the carrier (the back-reference
    the Pipeline derives its data node from)."""
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    data.SetAndObserveDisplayNodeID(display.GetID())
    if display.GetDisplayableNode() is not data:
        pytest.skip(
            "display.GetDisplayableNode() does not resolve the carrier in this "
            "build -- cannot exercise the Pipeline's data-node derivation."
        )
    return data, display


def test_resectogram_pipeline_reverse_resolves_plan_from_geometry_ref():
    """The Pipeline resolves its wrapper from the data node's geometry back-ref.

    Wire ``plan --geometry--> data <--displayable-- resectogram-display``,
    attach the display node to a fresh Pipeline and dispatch; the Pipeline must
    discover the plan (``GetResectionNode()``) without anyone calling a setter
    -- the production wiring the live resectogram render path needs so the
    distance map + margins reach the 2D mapper (ADR-0031).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_resolve_seam_or_skip(pipeline)

    data, display = _wire_surface_with_resectogram_display(slicer)
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(data)
    assert plan.GetGeometryNode() is data

    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    assert pipeline.GetResectionNode() is plan, (
        "the ResectogramPipeline must reverse-resolve its "
        "vtkMRMLResectionPlanNode wrapper from the data node's geometry "
        "back-reference (ADR-0031) so the flattened strip threads the "
        "distance-map + margins without an external caller; got "
        f"{pipeline.GetResectionNode()!r}."
    )


def test_resectogram_pipeline_resection_node_none_for_unowned_surface():
    """A bare surface with no owning plan resolves to no wrapper.

    Pins that the reverse-resolution does not false-positive: a Pipeline over a
    surface that no plan references must leave ``GetResectionNode()`` None (the
    no-distance-map fallback the 2D mapper degrades to gracefully).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_resolve_seam_or_skip(pipeline)

    data, display = _wire_surface_with_resectogram_display(slicer)
    # No plan references ``data``.
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    assert pipeline.GetResectionNode() is None, (
        "a surface no plan owns must resolve to no wrapper; got "
        f"{pipeline.GetResectionNode()!r}."
    )


def test_resectogram_pipeline_sets_plan_on_flattened_representation():
    """The resolved wrapper is threaded to the FlattenedSurfaceRepresentation.

    The Pipeline must not merely resolve the plan -- it must hand it to the
    ``FlattenedSurfaceRepresentation`` (which sources the distance map + margins
    off the wrapper per ADR-0031) before / within ``UpdatePipeline``, mirroring
    ``LiverBezierSurfacePipeline``'s ``active.SetResectionPlanNode(...)`` call.
    Verified by spying the representation's ``SetResectionPlanNode``.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_resolve_seam_or_skip(pipeline)

    data, display = _wire_surface_with_resectogram_display(slicer)
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(data)

    pipeline.SetDisplayNode(display)
    # Force the Representations to exist so we can spy the setter.  A bare
    # pipeline builds them lazily on first dispatch; call once, then spy.
    pipeline.UpdatePipeline()
    rep = pipeline.GetFlattenedSurfaceRepresentation()
    if rep is None:
        pytest.skip(
            "FlattenedSurfaceRepresentation not constructed (no renderer) -- "
            "cannot spy SetResectionPlanNode; exercised on the launched path."
        )

    seen = {"plan": "unset"}
    original = rep.SetResectionPlanNode

    def _spy(plan_node):
        seen["plan"] = plan_node
        return original(plan_node)

    rep.SetResectionPlanNode = _spy

    # Re-dispatch so the Pipeline threads the (already resolved) wrapper.
    pipeline._last_update_key = None  # force a non-short-circuit dispatch
    pipeline.UpdatePipeline()

    assert seen["plan"] is plan, (
        "UpdatePipeline must call SetResectionPlanNode(plan) on the "
        "FlattenedSurfaceRepresentation with the resolved wrapper (ADR-0031) "
        "so the distance-map + margins reach the 2D mapper; got "
        f"{seen['plan']!r}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
