# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins slice 2 -- margin edits repaint the strip.

The Pipeline memoises ``UpdatePipeline`` on the control-point geometry
digest, so a ``SafetyMargin_mm`` / ``RiskMargin_mm`` write on the plan
wrapper -- or a band-style edit on the parametric-surface display node --
at FIXED geometry never re-threads the mappers and never repaints: the
strip shows stale bands until an unrelated render.  Slice 2 widens the
memo key to ``(geometry digest, band-state digest)`` -- the band digest
being VALUES, never MTimes, so render-induced ``Modified`` churn at fixed
geometry + fixed band state still short-circuits (the maximize render
storm cannot regress; ``test_resectogram_pipeline_memo_key.py`` stays
green UNMODIFIED as the sentinel) -- and observes the resolved plan +
parametric-surface display nodes through the Pipeline's EXISTING Python
observer route, so the edits arrive with no external caller.

The framework's own ``UpdatePipeline`` dispatch fires on ResetDisplay, not
plain ``Modified`` (the LayerDM dispatch caveat) -- which is exactly why
the Pipeline's own observers carry this, as they already do for the
display + data nodes.

-- WHY LAUNCHED-SLICER --

Needs the wrapped plan / carrier / display nodes + a constructible
``ResectogramPipeline``.  Skips cleanly under bare pytest.

-- WHY RED NOW --

The Pipeline has no band-state digest (``_safe_get_band_state_digest``
absent), so every test SKIPS cleanly.  The skip lifts when slice 2 lands
(ADR-0027 §Conformance).

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md (margins cluster)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §4 (observing state nodes)
  * LiverResections/Testing/Python/test_resectogram_pipeline_memo_key.py
    (the render-storm sentinel this must not regress)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
SURFACE_DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"


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


def _require_band_digest_seam_or_skip():
    """Skip unless the band-state digest (slice 2) has landed."""
    import importlib

    # importlib.import_module returns the real submodule from
    # sys.modules; a plain ``import X.Y as module`` resolves through
    # the package ATTRIBUTE, which the package __init__'s
    # ``from .Y import Y`` re-binds to the CLASS -- hasattr on that
    # never sees module-level functions.
    module = importlib.import_module("LiverResectionsLib.ResectogramPipeline")

    if not hasattr(module, "_safe_get_band_state_digest"):
        pytest.skip(
            "ResectogramPipeline has no _safe_get_band_state_digest -- "
            "resectogram-margins slice 2 has not landed (imported from "
            f"{getattr(module, '__file__', '?')})."
        )


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _wire_full_margin_fixture(slicer):
    """plan --geometry--> data <--displayable-- {resectogram, surface} displays."""
    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    data.SetAndObserveDisplayNodeID(display.GetID())
    if display.GetDisplayableNode() is not data:
        pytest.skip(
            "display.GetDisplayableNode() does not resolve the carrier in "
            "this build."
        )
    surface_display = _add_or_skip(slicer, SURFACE_DISPLAY_NODE_CLASS)
    data.AddAndObserveDisplayNodeID(surface_display.GetID())
    plan = _add_or_skip(slicer, PLAN_NODE_CLASS)
    if not hasattr(plan, "SetAndObserveGeometryNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveGeometryNode.")
    plan.SetAndObserveGeometryNode(data)
    if not (hasattr(plan, "SetSafetyMargin_mm") and hasattr(plan, "SetRiskMargin_mm")):
        pytest.skip(f"{PLAN_NODE_CLASS} has no Safety/Risk margin setters.")
    return data, display, surface_display, plan


def test_margin_write_at_fixed_geometry_does_real_work():
    """A margin edit with static geometry re-reconciles -- the slice-2 gap.

    No explicit ``UpdatePipeline`` call after the write: the plan node's
    ``ModifiedEvent`` must reach the Pipeline through its own observer (the
    plan is resolved, so it must be observed) and the widened memo key must
    treat the new margin VALUES as a fresh key.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_band_digest_seam_or_skip()

    data, display, surface_display, plan = _wire_full_margin_fixture(slicer)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()
    settled = pipeline.GetUpdateCount()
    assert settled >= 1, "the first dispatch must do real work."

    plan.SetSafetyMargin_mm(7.0)

    assert pipeline.GetUpdateCount() > settled, (
        "a SafetyMargin_mm write at fixed geometry must re-reconcile through "
        "the Pipeline's own plan observer + the widened memo key; the count "
        "did not advance -- the margin edit was swallowed."
    )


def test_margin_key_is_idempotent_after_the_edit():
    """A second dispatch after the margin write short-circuits.

    The widened key must stay a stable VALUE digest: same margins, same
    geometry -> same key -> no repeated work (the storm guard, extended).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_band_digest_seam_or_skip()

    data, display, surface_display, plan = _wire_full_margin_fixture(slicer)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    plan.SetSafetyMargin_mm(7.0)
    after_edit = pipeline.GetUpdateCount()

    pipeline.UpdatePipeline()
    assert pipeline.GetUpdateCount() == after_edit, (
        "an explicit UpdatePipeline with margins + geometry both unchanged "
        "must short-circuit; the count advanced -- the band digest is not a "
        "stable value digest."
    )


def test_unchanged_state_requests_no_render():
    """``_on_node_modified`` at fixed geometry AND fixed band state is silent.

    Render-induced ``Modified`` churn advances MTimes but not the VALUES the
    widened key digests, so no render may be requested -- the maximize
    render-storm guard extended over the new key components.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_band_digest_seam_or_skip()

    data, display, surface_display, plan = _wire_full_margin_fixture(slicer)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    calls = []
    original = pipeline.RequestRender
    pipeline.RequestRender = lambda: calls.append(1)  # wrap: count only
    try:
        pipeline._on_node_modified(None, None)
    finally:
        pipeline.RequestRender = original

    assert calls == [], (
        "a Modified at fixed geometry + fixed band state must not request a "
        f"render; got {len(calls)} request(s) -- the storm guard regressed."
    )


def test_resolved_state_nodes_are_observed():
    """The resolved plan + surface display node land in the observed set.

    Without observers a margin / style edit only takes effect on the next
    unrelated dispatch -- the edit must reach the Pipeline with NO external
    caller (ADR-0013 §4: the observation set includes state nodes the
    displayed concept depends on).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_band_digest_seam_or_skip()

    data, display, surface_display, plan = _wire_full_margin_fixture(slicer)
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    assert plan in pipeline._observed_node_refs, (
        "the resolved plan wrapper must be observed so margin writes reach "
        "the Pipeline without an external caller."
    )
    assert surface_display in pipeline._observed_node_refs, (
        "the resolved parametric-surface display node must be observed so "
        "band-style edits reach the Pipeline without an external caller."
    )


def test_interpolated_flip_does_real_work():
    """An ``InterpolatedMargins`` flip on the style node re-reconciles."""
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_band_digest_seam_or_skip()

    data, display, surface_display, plan = _wire_full_margin_fixture(slicer)
    if not hasattr(surface_display, "SetInterpolatedMargins"):
        pytest.skip(f"{SURFACE_DISPLAY_NODE_CLASS} has no InterpolatedMargins.")
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()
    settled = pipeline.GetUpdateCount()

    surface_display.SetInterpolatedMargins(True)

    assert pipeline.GetUpdateCount() > settled, (
        "an InterpolatedMargins flip must re-reconcile through the style "
        "node's observer + the widened memo key; the count did not advance."
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
