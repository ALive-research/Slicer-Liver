# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T2 render-cutover slice 1c -- the Pipeline reverse-resolves its plan wrapper.

ADR-0031 puts the distance-map volume (and the resection / uncertainty margins)
on the ``vtkMRMLResectionPlanNode`` *wrapper*, and slice 1b made
``BezierPlanningRepresentation`` thread them onto the mapper -- but only when the
Pipeline's ``_resection_node`` is set.  In the live LayerDM render path the
displayable manager creates the Pipeline for the surface's *display node*
(``registerPipelineCreator`` matches ``vtkMRMLParametricSurfaceDisplayNode``),
so the Pipeline derives its data node but is never handed the wrapper -- nothing
in production calls ``SetResectionNode``.  Without this slice the live v2
surface renders with NO margin shading (the distance map never reaches the
mapper), which would make the render cutover a visible regression.

This pins the fix: the Pipeline reverse-resolves the wrapper from its data node
via the ``geometry`` back-reference (the plan references the surface carrier, so
the plan whose ``GetGeometryNode()`` is our data node is our wrapper) and sets
``_resection_node`` itself -- no external caller required.

-- WHY LAUNCHED-SLICER --
Needs the wrapped ``vtkMRMLResectionPlanNode`` / ``vtkMRMLBezierSurfaceNode`` /
``vtkMRMLParametricSurfaceDisplayNode`` + the importable
``LiverBezierSurfacePipeline`` (LayerDMLib reachable only inside Slicer).  Skips
cleanly under bare ``PythonSlicer -m pytest``.

-- WHY RED NOW --
The Pipeline has no reverse-resolution; ``GetResectionNode()`` stays ``None``
after wiring the graph.  The skip/fail lifts when slice 1c lands (ADR-0027).

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    try:
        from LiverResectionsLib.LiverBezierSurfacePipeline import (
            LiverBezierSurfacePipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"LiverBezierSurfacePipeline not importable ({exc!r}) -- LayerDMLib "
            "not reachable in this environment."
        )
    return LiverBezierSurfacePipeline()


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _wire_surface_with_display(slicer):
    """Create a Bezier carrier + its parametric-surface display node, wired so
    ``display.GetDisplayableNode()`` resolves the carrier (the back-reference
    the Pipeline derives its data node from)."""
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, DISPLAY_NODE_CLASS)
    data.SetAndObserveDisplayNodeID(display.GetID())
    if display.GetDisplayableNode() is not data:
        pytest.skip(
            "display.GetDisplayableNode() does not resolve the carrier in this "
            "build -- cannot exercise the Pipeline's data-node derivation."
        )
    return data, display


def test_pipeline_reverse_resolves_plan_from_geometry_ref():
    """The Pipeline resolves its wrapper from the data node's geometry back-ref.

    Wire ``plan --geometry--> data <--displayable-- display``, attach the
    display node to a fresh Pipeline and dispatch; the Pipeline must discover
    the plan (``GetResectionNode()``) without anyone calling
    ``SetResectionNode`` -- the production wiring the live render path needs.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()

    data, display = _wire_surface_with_display(slicer)
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(data)
    assert plan.GetGeometryNode() is data

    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    assert pipeline.GetResectionNode() is plan, (
        "the Pipeline must reverse-resolve its vtkMRMLResectionPlanNode wrapper "
        "from the data node's geometry back-reference (ADR-0031) so the live "
        "LayerDM render path threads the distance-map + margins without an "
        "external SetResectionNode caller; got "
        f"{pipeline.GetResectionNode()!r}."
    )


def test_pipeline_resection_node_none_for_unowned_surface():
    """A bare surface with no owning plan resolves to no wrapper.

    Pins that the reverse-resolution does not false-positive: a Pipeline over a
    surface that no plan references must leave ``GetResectionNode()`` None
    (the no-distance-map fallback the shader supports).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()

    data, display = _wire_surface_with_display(slicer)
    # No plan references ``data``.
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    assert pipeline.GetResectionNode() is None, (
        "a surface no plan owns must resolve to no wrapper; got "
        f"{pipeline.GetResectionNode()!r}."
    )


def test_pipeline_does_not_rescan_for_plan_every_tick():
    """The reverse-resolution is memoised against scene state, not per-tick.

    For a bare surface with no owning plan, ``_resection_node`` stays None;
    a naive implementation re-scans the scene (``GetNodesByClass``) on every
    ``UpdatePipeline`` -- i.e. every interaction/drag frame.  Pin that the scan
    is gated on the scene's modified time: repeated dispatches with no scene
    change must resolve at most once.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()

    data, display = _wire_surface_with_display(slicer)  # no owning plan
    if not hasattr(pipeline, "_resolve_resection_node"):
        pytest.skip("Pipeline has no _resolve_resection_node -- slice 1c absent.")
    pipeline.SetDisplayNode(display)

    calls = {"n": 0}
    original = pipeline._resolve_resection_node

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    pipeline._resolve_resection_node = _counting

    for _ in range(3):
        pipeline.UpdatePipeline()

    assert calls["n"] <= 1, (
        "the Pipeline re-scanned the scene for an owning plan on every "
        f"UpdatePipeline tick ({calls['n']} scans, no scene change) -- the "
        "reverse-resolution must be memoised against scene state so idle / "
        "per-drag dispatches do not full-scene-scan."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
