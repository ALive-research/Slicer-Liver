# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T3 -- ResectogramPipeline memo-key invariant (the render-storm fix).

``ResectogramPipeline.UpdatePipeline`` memoises on the data node's
control-point GEOMETRY digest ALONE -- it deliberately does NOT fold in the
data/display node ``GetMTime`` (ADR-0013 §3 idempotency).  That single choice
is the render-storm fix: a maximize/enlarge binds the resectogram view to a
live ``qMRMLThreeDView`` whose every frame re-``Modified()``s the surface +
display node WITHOUT changing geometry; keying on those MTimes would make every
render-churned MTime a fresh key -> re-feed + RequestRender on every render ->
a continuous render loop (~47 renders/s observed).  Keying on the geometry
digest instead means render-induced ``Modified()`` at fixed geometry
short-circuits (no work, no render) while a real control-point DRAG changes the
digest and stays reactive.

This pins that invariant so the storm cannot silently regress (e.g. if a future
change re-introduces an MTime component into the key):

  1. A second ``UpdatePipeline()`` at unchanged geometry does NOT advance
     ``GetUpdateCount()`` (the short-circuit -- a render-induced Modified is a
     no-op).
  2. A control-point position change DOES advance it (edit reactivity).
  3. ``_on_node_modified`` (the observer callback a render-induced Modified
     fires) does NOT advance the count at fixed geometry, and requests no
     render -- the loop is broken at the observer.

The Pipeline base class is ``vtkMRMLLayerDMScriptedPipeline`` (LayerDMLib),
constructible only inside a Slicer process with that extension loaded, so this
``importorskip``s LayerDMLib and runs under the launched-Slicer
``pytest_launched`` row, skipping cleanly under bare pytest (ADR-0008
dual-harness; the #460 explicit-skip lesson).  It is GPU-free: the two
Representations are stubbed out (``_representations_initialised = True`` with
both set to ``None``) so ``UpdatePipeline`` exercises ONLY the digest memo +
update-count logic, no VTK actor / GL context needed.

See also:
  * Docs/adr/0013-layerdm-pipeline-pattern.md §3 (idempotency contract)
  * Docs/adr/0027-invariant-test-first-v2-implementation.md
  * LiverResections/LiverResectionsLib/ResectogramPipeline.py
    (UpdatePipeline / _on_node_modified / _safe_get_control_points_digest)
"""

from __future__ import annotations

import pytest


class _StubDataNode:
    """Minimal carrier-like node exposing only the accessor the digest reads.

    The v2 ``vtkMRMLBezierSurfaceNode`` carrier surfaces its control polygon
    as a flat row-major grid via ``GetControlGridVector`` (a tuple of ``3 * N``
    floats; ADR-0014 §"Fourth layer").  The v1 markups control-point API is
    retired (ADR-0014 §"Dissolution"; ADR-0032 §"Consequences").
    """

    def __init__(self, points):
        self._points = [list(p) for p in points]

    def GetControlGridVector(self):  # noqa: N802 - mirrors the VTK accessor
        return tuple(coord for point in self._points for coord in point)

    def move(self, index, position):
        self._points[index] = list(position)


def _make_pipeline_or_skip(data_node):
    """Construct a ResectogramPipeline with Representations stubbed out.

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

    pipeline = ResectogramPipeline()
    # Stub the Representations OUT so UpdatePipeline exercises only the digest
    # memo + update-count logic (no VTK actor / GL context).  _ensure_representations
    # early-returns on this flag; the update() calls are guarded by `is not None`.
    pipeline._representations_initialised = True
    pipeline._flattened_surface = None
    pipeline._vascular_contour = None
    pipeline._data_node = data_node
    return pipeline


def test_unchanged_geometry_short_circuits_update():
    """A second UpdatePipeline at fixed geometry does NOT advance the count.

    This is the render-storm short-circuit: a render-induced Modified() drives
    UpdatePipeline, but with the geometry digest unchanged the memo key matches
    and the reconciliation is skipped (ADR-0013 §3).
    """
    data = _StubDataNode([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    pipeline = _make_pipeline_or_skip(data)

    assert pipeline.GetUpdateCount() == 0  # nothing reconciled yet
    pipeline.UpdatePipeline()
    assert pipeline.GetUpdateCount() == 1, "first feed must do real work"
    pipeline.UpdatePipeline()
    assert pipeline.GetUpdateCount() == 1, (
        "a second UpdatePipeline at UNCHANGED control-point geometry must "
        "short-circuit (the memo key is the geometry digest alone) -- this is "
        "the render-storm fix: render-induced Modified() at fixed geometry "
        "must not re-feed (ADR-0013 §3)."
    )


def test_control_point_change_advances_update():
    """Moving a control point DOES advance the count (edit reactivity).

    The digest changes when geometry changes, so a real drag is picked up even
    though render-induced MTime churn is not.
    """
    data = _StubDataNode([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    pipeline = _make_pipeline_or_skip(data)

    pipeline.UpdatePipeline()
    assert pipeline.GetUpdateCount() == 1
    data.move(0, (5.0, 5.0, 5.0))
    pipeline.UpdatePipeline()
    assert pipeline.GetUpdateCount() == 2, (
        "a control-point position change must advance the update count -- the "
        "geometry digest changed, so edit reactivity is preserved while the "
        "render-induced churn is not (ADR-0013 §3)."
    )


def test_render_induced_modified_requests_no_render():
    """``_on_node_modified`` at fixed geometry advances nothing and renders not.

    The observer callback a render-induced Modified() fires must short-circuit:
    no update-count advance, and (because the count did not advance) no
    RequestRender -- breaking the feedback loop at the observer.  A render at
    changed geometry is the reactive path and is exercised by the
    control-point-change test above.
    """
    data = _StubDataNode([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    pipeline = _make_pipeline_or_skip(data)

    # Count RequestRender calls by wrapping the base-class method.
    renders = {"n": 0}
    original = pipeline.RequestRender

    def _counting_request_render(*args, **kwargs):
        renders["n"] += 1
        try:
            return original(*args, **kwargs)
        except Exception:  # pragma: no cover - base stub may not be live
            return None

    pipeline.RequestRender = _counting_request_render

    pipeline.UpdatePipeline()  # initial feed
    baseline_count = pipeline.GetUpdateCount()
    renders["n"] = 0

    # Simulate a render-induced Modified() at fixed geometry.
    pipeline._on_node_modified(data, "ModifiedEvent")

    assert pipeline.GetUpdateCount() == baseline_count, (
        "a render-induced Modified() at fixed geometry must not advance the "
        "update count (the digest is unchanged) -- the render-storm fix."
    )
    assert renders["n"] == 0, (
        "_on_node_modified must request NO render when UpdatePipeline "
        "short-circuited (the count did not advance) -- this is what breaks the "
        "maximize/enlarge render loop at the observer."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
