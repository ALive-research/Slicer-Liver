# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The CPU ring-extraction boundary is the handle DROP (ADR-0035).

Supersedes the ``commit()``-boundary pins: the v1 composite loop re-fits
the candidate grid on every plane-handle drop, so the discrete CPU ring
extraction runs exactly once per drop (``_refit_grid_from_plane``) and
NEVER on per-move / per-reconcile Init ticks — per-frame visual feedback
stays the shader's job.  The ``Init -> Planning`` commit itself
(``SurfaceGrabbed``, ADR-0035) is a pure state flip with no extraction.

Needs the wrapped ``vtkMRMLBezierSurfaceNode`` inside a launched Slicer;
skips cleanly under bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
MODEL_NODE_CLASS = "vtkMRMLModelNode"
N_TICKS = 7


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
            f"LiverBezierSurfacePipeline not importable ({exc!r}) -- the "
            "extraction boundary cannot be exercised."
        )
    return LiverBezierSurfacePipeline()


def _init_bezier_with_target_or_skip(slicer):
    """A wrapped carrier in Init+SlicingPlane with a weakref'd target."""
    bezier = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    if bezier is None:
        pytest.skip(f"{BEZIER_NODE_CLASS} not registered in this build.")
    bezier.SetState(0)  # Init
    bezier.SetInitMode(0)  # SlicingPlane
    target = slicer.mrmlScene.AddNewNodeByClass(MODEL_NODE_CLASS, "TargetOrgan")
    assert target is not None
    bezier.SetAndObserveTargetModelNode(target)
    return bezier, target


def test_extractor_never_per_tick_once_per_drop(monkeypatch):
    """Zero extractions across Init reconcile ticks; exactly one per drop."""
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    bezier, _ = _init_bezier_with_target_or_skip(slicer)

    count = {"n": 0}
    monkeypatch.setattr(
        pipeline,
        "_run_ring_extraction",
        lambda *a, **k: count.__setitem__("n", count["n"] + 1),
        raising=True,
    )

    pipeline.SetDisplayNode(getattr(bezier, "GetDisplayNode", lambda: None)())

    for _ in range(N_TICKS):
        bezier.Modified()
        pipeline.UpdatePipeline()
    assert count["n"] == 0, (
        f"ring extraction ran {count['n']} time(s) during {N_TICKS} Init "
        "reconcile ticks; the boundary is the handle DROP -- per-frame "
        "feedback is the shader's job (ADR-0035)."
    )

    # The pipeline's data node is not bound (no display node on the bare
    # carrier); bind it directly the way the drop path sees it.
    pipeline._data_node = bezier
    pipeline._refit_grid_from_plane()
    assert count["n"] == 1, (
        f"ring extraction ran {count['n']} time(s) on the drop re-fit; "
        "exactly ONE per drop (ADR-0035)."
    )

    # The Init -> Planning commit itself (SurfaceGrabbed) is a PURE state
    # flip -- zero extractions across it (the old commit()-boundary's
    # corollary, restated for ADR-0035).
    try:
        from LiverResectionsLib import ResectionStateMachine as rsm
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"ResectionStateMachine not importable ({exc!r}).")
    rsm.request(bezier, rsm.EVENT_PLANE_HANDLE_GRABBED)
    rsm.request(bezier, rsm.EVENT_PLANE_HANDLE_DROPPED, refit=lambda: True)
    before = count["n"]
    assert rsm.request(bezier, rsm.EVENT_SURFACE_GRABBED) is True
    assert bezier.GetState() == rsm.STATE_PLANNING
    assert count["n"] == before, (
        f"the SurfaceGrabbed commit ran {count['n'] - before} "
        "extraction(s); the commit is a pure state flip (ADR-0035 §4)."
    )


def test_drop_refit_reads_target_via_weakref(monkeypatch):
    """The drop's re-fit feeds the extractor the WEAKREF'D target mesh
    (ADR-0014 §1, ``GetTargetModelNode()``), never a None / hard-coded
    path."""
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    bezier, target = _init_bezier_with_target_or_skip(slicer)
    assert bezier.GetTargetModelNode() is target

    seen = {"mesh_source": None}

    def _capture_extract(target_model=None, *args, **kwargs):
        seen["mesh_source"] = target_model

    monkeypatch.setattr(
        pipeline, "_run_ring_extraction", _capture_extract, raising=True
    )

    display = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLParametricSurfaceDisplayNode"
    )
    if display is None:
        pytest.skip("vtkMRMLParametricSurfaceDisplayNode not registered.")
    bezier.AddAndObserveDisplayNodeID(display.GetID())
    pipeline.SetDisplayNode(display)
    pipeline._refit_grid_from_plane()

    assert seen["mesh_source"] is target, (
        "the drop's re-fit must feed the extractor the weakref'd "
        "vtkMRMLBezierSurfaceNode target (GetTargetModelNode()), per "
        "ADR-0014 §1."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
