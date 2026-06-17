# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stack-4 ring-extraction wiring -- on-commit-not-per-drag + weakref consumption.

Two pinned invariants for the LayerDM Pipeline + Init Representations that
consume the ring extractors (``vtkLiverPlaneRingExtractor`` /
``vtkLiverSpheroidRingExtractor``):

  Constraint 3 -- the extractor runs ONCE on the
  ``Init -> Planning`` commit transition (ADR-0019: irreversible 2-state
  automaton; the init data freezes to read-only audit data at the
  transition), NOT on every per-drag ``Modified`` tick.  Per-drag visual
  feedback is the shader's job; the discrete ring extraction is one-shot per
  resection and must be debounced behind an explicit commit boundary
  (``LiverBezierSurfacePipeline.commit()`` + a ``_pending_extraction``
  request flag), not inherited per-drag by accident from the legacy
  Markups workflow.

  Weakref consumption (ADR-0014 §1) -- the Init Representation reaches the
  target mesh through the now-merged ``vtkMRMLBezierSurfaceNode`` weak
  ``target`` reference (``GetTargetReferenceRole()`` == "target" /
  ``GetTargetModelNode()`` / ``SetAndObserveTargetModelNode()``), i.e.
  extraction feeds on the weakref'd mesh -- not a hard-coded path and not a
  silent ``None`` no-op.  This pins that the ``TODO(T2-target-mesh-weakref)``
  sites in ``SlicingPlaneInitRepresentation`` /
  ``DistanceSpheroidInitRepresentation`` are wired.

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

The commit boundary lives in the Python Pipeline / Representations, but
exercising it end-to-end needs the wrapped ``vtkMRMLBezierSurfaceNode``
(for ``SetAndObserveTargetModelNode`` + the state enum) and a real
``vtkMRMLModelNode`` target mesh -- both wrapped-C++-from-Python, only
reachable under a launched Slicer.  Under bare ``PythonSlicer -m pytest``
this SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards (no
``slicer.mrmlScene``); the ``_launched_scene_cleanup`` fixture in this
module's conftest tears down every minted node so the launched harness
does not trip ``vtkDebugLeaks`` (launched-Slicer leak discipline -- NO in-process
``sys.modules['slicer']`` stubbing).

-- WHY THIS IS RED NOW --

The Pipeline has no ``commit()`` / ``_pending_extraction`` boundary and the
Representations' ``TODO(T2-target-mesh-weakref)`` sites do not yet construct
an extractor.  Each test SKIPS pre-implementation (the commit seam / wired
extractor is absent) rather than failing noisily, and goes GREEN once the
implementer lands the boundary -- per ADR-0027 §Conformance "for skipped
tests, the skip lifts at the implementation commit".

See also:
  * Docs/adr/0019-resection-state-machine.md  (Init -> Planning transition)
  * Docs/adr/0014-*.md §1  (vtkMRMLBezierSurfaceNode weak target reference)
  * Docs/adr/0008-testing-strategy.md §1, §6  (dual-harness strategy)
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
  * LiverResections/Testing/Python/conftest.py  (the cleanup fixture)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
MODEL_NODE_CLASS = "vtkMRMLModelNode"
TARGET_REFERENCE_ROLE = "target"  # vtkMRMLBezierSurfaceNode::GetTargetReferenceRole()

# Mirrors the C++ resection-state enum (ADR-0019; STATE_INIT/STATE_PLANNING
# in LiverBezierSurfacePipeline).  Pinned locally so a bare-pytest collect
# does not import the Pipeline module before the skip-guards fire.
STATE_INIT = 0
STATE_PLANNING = 1

# Number of simulated per-drag updates the per-drag-debounce test issues.
N_DRAG_TICKS = 12


def _slicer_or_skip():
    """Resolve a launched ``slicer`` module or skip cleanly under bare pytest."""
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_pipeline_or_skip():
    """Construct a ``LiverBezierSurfacePipeline`` or skip if unimportable.

    The Pipeline imports cleanly only inside a Slicer process with LayerDMLib
    reachable; a bare-pytest run skips before reaching here via
    ``_slicer_or_skip``.
    """
    try:
        from LiverResectionsLib.LiverBezierSurfacePipeline import (
            LiverBezierSurfacePipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "LiverBezierSurfacePipeline not importable "
            f"({exc!r}) -- the Stack-4 Pipeline is not reachable in this "
            "environment; the commit boundary cannot be exercised."
        )
    return LiverBezierSurfacePipeline()


def _bezier_node_or_skip(slicer):
    """Add a wrapped ``vtkMRMLBezierSurfaceNode`` or skip if not registered."""
    node = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    if node is None:
        pytest.skip(
            f"{BEZIER_NODE_CLASS} not registered in this build -- cannot "
            "exercise the weak target reference (ADR-0014 §1)."
        )
    return node


def _require_commit_seam_or_skip(pipeline):
    """Skip unless the Pipeline exposes the explicit commit boundary.

    Constraint 3 names the seam: a ``commit()`` method plus a
    ``_pending_extraction`` request flag.  RED == this seam is absent now;
    the skip lifts when the implementer introduces it.
    """
    if not hasattr(pipeline, "commit"):
        pytest.skip(
            "LiverBezierSurfacePipeline has no commit() method -- Constraint 3 "
            "requires the extractor to run on the Init->Planning "
            "commit boundary, not per drag.  Skip lifts when the commit() "
            "seam + _pending_extraction flag land (ADR-0019; ADR-0027 "
            "§Conformance)."
        )


def test_extractor_not_invoked_per_drag_only_on_commit(monkeypatch):
    """Ring extraction fires ONCE on Init->Planning commit, zero per drag.

    Constraint 3 + ADR-0019: per-drag ticks must NOT re-run the
    CPU ring extraction (that is the shader's per-frame job); the extractor
    runs exactly once at the commit transition.

    Counting seam: monkeypatch ``vtkLiverSpheroidRingExtractor`` /
    ``vtkLiverPlaneRingExtractor`` ``Update`` (or the Pipeline's extraction
    entry point once named) with a test-scoped counter.  RED until the
    commit boundary debounces per-drag extraction.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_commit_seam_or_skip(pipeline)

    bezier = _bezier_node_or_skip(slicer)

    # Give the Bezier node a target mesh via the weak reference so the
    # extractor has something to consume on commit.
    target = slicer.mrmlScene.AddNewNodeByClass(MODEL_NODE_CLASS, "TargetOrgan")
    assert target is not None
    bezier.SetAndObserveTargetModelNode(target)

    # Install a test-scoped counting seam on the extractor entry point.
    # The implementer's commit boundary calls into the extractor; the exact
    # symbol is pinned once the wiring lands.  We require the Pipeline to
    # expose the extraction call through a patchable attribute so the seam
    # is stable across the implementation.
    count = {"n": 0}

    extract_attr = "_run_ring_extraction"
    if not hasattr(pipeline, extract_attr):
        pytest.skip(
            "LiverBezierSurfacePipeline exposes no patchable ring-extraction "
            f"entry point ({extract_attr!r}) -- the counting seam for "
            "Constraint 3 cannot attach.  Skip lifts when the commit() path "
            "routes extraction through a named, test-observable call."
        )

    def _counting_extract(*args, **kwargs):
        count["n"] += 1

    monkeypatch.setattr(pipeline, extract_attr, _counting_extract, raising=True)

    # Wire the Pipeline against the node and drive Init-mode drags.
    pipeline.SetDisplayNode(getattr(bezier, "GetDisplayNode", lambda: None)())

    # Simulate N per-drag parameter updates while still in Init.
    for _ in range(N_DRAG_TICKS):
        bezier.Modified()
        pipeline.UpdatePipeline()

    assert count["n"] == 0, (
        f"ring extraction ran {count['n']} time(s) during {N_DRAG_TICKS} "
        "per-drag Init ticks; Constraint 3 requires ZERO per-drag "
        "extractions -- per-frame feedback is the shader's job (ADR-0019)."
    )

    # Commit the Init->Planning transition; extraction must fire exactly once.
    pipeline.commit()

    assert count["n"] == 1, (
        f"ring extraction ran {count['n']} time(s) on the Init->Planning "
        "commit; Constraint 3 requires EXACTLY ONE (one-shot per "
        "resection, ADR-0019)."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "T2-target-mesh-weakref not yet implemented: the Init Representation's "
        "TODO(T2-target-mesh-weakref) consume sites do not yet feed the "
        "extractor the weakref'd target mesh (ADR-0014 §1).  Invariant-first "
        "RED pin (ADR-0027); strict=True flips this to a hard failure the moment "
        "the feature lands, forcing removal of this marker."
    ),
)
def test_init_representation_reads_target_via_weakref(monkeypatch):
    """Extraction consumes the weakref'd target mesh, not a None/hard-coded path.

    ADR-0014 §1: the Init Representation reaches the target mesh through
    ``vtkMRMLBezierSurfaceNode``'s weak ``target`` reference
    (``GetTargetModelNode()``).  Pins that the
    ``TODO(T2-target-mesh-weakref)`` consume sites feed the extractor the
    weakref'd mesh.  RED until those sites are wired.
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_commit_seam_or_skip(pipeline)

    bezier = _bezier_node_or_skip(slicer)

    # Sanity: the merged weak target reference is reachable from Python.
    assert bezier.GetTargetReferenceRole() == TARGET_REFERENCE_ROLE
    assert bezier.GetTargetModelNode() is None  # no target yet

    target = slicer.mrmlScene.AddNewNodeByClass(MODEL_NODE_CLASS, "TargetOrgan")
    assert target is not None
    bezier.SetAndObserveTargetModelNode(target)
    assert bezier.GetTargetModelNode() is target

    # Capture the mesh the extractor is fed at commit.  The seam records the
    # vtkPolyData (or the source model node) the Pipeline hands the extractor.
    seen = {"mesh_source": None}

    extract_attr = "_run_ring_extraction"
    if not hasattr(pipeline, extract_attr):
        pytest.skip(
            "LiverBezierSurfacePipeline exposes no patchable ring-extraction "
            f"entry point ({extract_attr!r}) -- cannot observe which mesh the "
            "extractor consumes.  Skip lifts when the commit() path routes "
            "extraction through a named call that takes the target mesh."
        )

    def _capture_extract(target_model=None, *args, **kwargs):
        seen["mesh_source"] = target_model

    monkeypatch.setattr(pipeline, extract_attr, _capture_extract, raising=True)

    pipeline.SetDisplayNode(getattr(bezier, "GetDisplayNode", lambda: None)())
    pipeline.commit()

    assert seen["mesh_source"] is not None, (
        "extraction ran with no target mesh -- ADR-0014 §1 requires the Init "
        "Representation to feed the extractor the weakref'd target "
        "(GetTargetModelNode()), not a None/hard-coded path."
    )
    # The mesh fed in must derive from the weakref'd target model.
    assert seen["mesh_source"] in (target, getattr(target, "GetPolyData", lambda: None)()), (
        "the mesh fed to the extractor must come from the weakref'd "
        "vtkMRMLBezierSurfaceNode target (GetTargetModelNode()), per "
        "ADR-0014 §1 and the TODO(T2-target-mesh-weakref) consume sites."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
