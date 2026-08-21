# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins slice 2 -- the 3D view repaints on margin edits.

The 3D twin of ``test_resectogram_pipeline_margin_repaint.py``.  The
``LiverBezierSurfacePipeline`` already OBSERVES the plan wrapper and its
display node, and its reconcile key already folds their MTimes -- so a
margin write re-threads the mapper uniforms.  What it does NOT do is
request a render: ``_on_node_modified``'s ``render_key`` digests only the
visible dispatch inputs (state / geometry / slicing plane / phase /
locator) and has no margin or band-style component, so the surface shows
stale bands until an unrelated repaint (a camera orbit).  Slice 2 extends
the render key with the margin + band-style VALUES -- values, never
MTimes, keeping the documented render feedback-loop guard intact.

-- WHY LAUNCHED-SLICER --

Needs the wrapped plan / carrier / display nodes + a constructible
``LiverBezierSurfacePipeline``.  Skips cleanly under bare pytest.

-- WHY RED NOW --

The pipeline module has no ``_safe_get_plan_margins`` accessor, so the
tests SKIP cleanly.  The skip lifts when slice 2 lands
(ADR-0027 §Conformance).

See also:
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
    (_on_node_modified -- the render_key this extends)
  * LiverResections/Testing/Python/test_pipeline_resolves_resection_plan.py
    (the construction idiom this clones)
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


def _require_margin_render_seam_or_skip():
    """Skip unless the margin render-key extension (slice 2) has landed."""
    import importlib

    # importlib.import_module returns the real submodule from
    # sys.modules; a plain ``import X.Y as module`` resolves through
    # the package ATTRIBUTE, which the package __init__'s
    # ``from .Y import Y`` re-binds to the CLASS -- hasattr on that
    # never sees module-level functions.
    module = importlib.import_module("LiverResectionsLib.LiverBezierSurfacePipeline")

    if not hasattr(module, "_safe_get_plan_margins"):
        pytest.skip(
            "LiverBezierSurfacePipeline has no _safe_get_plan_margins -- "
            "resectogram-margins slice 2 has not landed (imported from "
            f"{getattr(module, '__file__', '?')})."
        )


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _wire_pipeline(slicer, pipeline):
    """plan --geometry--> data <--displayable-- display; dispatched once."""
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, DISPLAY_NODE_CLASS)
    data.SetAndObserveDisplayNodeID(display.GetID())
    if display.GetDisplayableNode() is not data:
        pytest.skip(
            "display.GetDisplayableNode() does not resolve the carrier in "
            "this build."
        )
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(data)
    if not hasattr(plan, "SetSafetyMargin_mm"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetSafetyMargin_mm.")

    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()
    # Settle the render key: drive the observer once so _last_render_key
    # holds the current state before the margin edit under test.
    pipeline._on_node_modified(None, None)
    return data, display, plan


def _count_renders(pipeline, action):
    calls = []
    original = pipeline.RequestRender
    pipeline.RequestRender = lambda: calls.append(1)  # wrap: count only
    try:
        action()
    finally:
        pipeline.RequestRender = original
    return len(calls)


def test_margin_write_requests_exactly_one_render():
    """A margin edit at fixed geometry repaints the 3D surface -- once.

    The plan observer routes the write into ``_on_node_modified``; the
    extended render key sees new margin VALUES -> exactly one coalesced
    ``RequestRender``.  Without the extension the bands stay stale until a
    camera orbit.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_margin_render_seam_or_skip()

    data, display, plan = _wire_pipeline(slicer, pipeline)

    renders = _count_renders(pipeline, lambda: plan.SetSafetyMargin_mm(9.0))

    assert renders == 1, (
        "a SafetyMargin_mm write at fixed geometry must request exactly one "
        f"render through the extended render key; got {renders}."
    )


def test_noop_modified_requests_no_render():
    """A ``Modified`` with nothing changed stays silent.

    Values-not-MTimes: firing the plan's ``Modified`` without changing any
    digested value must not re-request -- the render feedback-loop guard the
    key extension must not weaken.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_margin_render_seam_or_skip()

    data, display, plan = _wire_pipeline(slicer, pipeline)
    plan.SetSafetyMargin_mm(9.0)  # settle a non-default value first

    renders = _count_renders(pipeline, plan.Modified)

    assert renders == 0, (
        "a no-op Modified (no digested value changed) must not request a "
        f"render; got {renders} -- the feedback-loop guard regressed."
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
