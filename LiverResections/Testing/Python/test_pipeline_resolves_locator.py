# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Locator consumer -- the Pipeline resolves + threads the single locator node.

Pins the Pipeline half of the ADR-0025 locator *consumer* slice (#489 consumer
half): ``LiverBezierSurfacePipeline`` resolves the scene's single
``vtkMRMLLocatorNode`` (``GetFirstNodeByClass("vtkMRMLLocatorNode")`` -- v2.0
has exactly one) and threads it onto the active Representation via
``SetLocatorNode(node)`` before ``update()`` -- mirroring how it already
reverse-resolves + threads the resection-plan wrapper via
``SetResectionPlanNode`` (ADR-0031, ADR-0013 §6).  NO new displayable manager,
NO new pipeline factory (ADR-0025 §"Consumer", ADR-0013 §5).

Two invariants:

  1. Positive -- with a ``vtkMRMLLocatorNode`` in the scene carrying a known
     ``PickedPositionWorld`` + a display ``Radius``, after ``UpdatePipeline``
     the active Representation's real mapper reflects the locator radius uniform
     (the Pipeline resolved the node and threaded it, ADR-0025 §"Consumer").
  2. Negative -- no ``vtkMRMLLocatorNode`` in the scene leaves the consumer in
     its off state (mapper ``GetLocatorRadius()`` == 0): the resolution does not
     false-positive, and the shader's off state holds (ADR-0025 §"Rendering").

SCOPE: this pins node -> consumer (via the Pipeline) only.  The FULL producer ->
``vtkMRMLLocatorNode`` -> consumer chain (issue #489; ADR-0025 §Conformance
[test]) closes when Slice B (the resectogram producer) lands; the producer is
not exercised here.

-- WHY LAUNCHED-SLICER --
Needs the wrapped ``vtkMRMLLocatorNode`` / ``vtkMRMLLocatorDisplayNode`` /
``vtkMRMLBezierSurfaceNode`` / ``vtkMRMLParametricSurfaceDisplayNode`` + the
real ``vtkOpenGLBezierResectionPolyDataMapper`` + the importable
``LiverBezierSurfacePipeline`` (LayerDMLib reachable only inside Slicer).  Skips
cleanly under bare ``PythonSlicer -m pytest``.  GL-free: the mapper's uniform
accessors need no render window.

-- WHY RED NOW --
The Pipeline has no locator resolution / threading, and the Representation has
no ``SetLocatorNode`` seam, so the tests skip on ``_require_locator_seam_or_skip``.
The skip lifts when the ADR-0025 consumer slice lands (ADR-0027 §Conformance --
the skip lifts at the implementation commit).

See also:
  * Docs/adr/0025-locator-architecture.md §"Consumer", §"Rendering", §Conformance
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5, §6
  * Docs/adr/0027-invariant-test-first-v2-implementation.md
  * LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py
  * LiverResections/Testing/Python/test_pipeline_resolves_resection_plan.py
  * LiverResections/Testing/Python/test_bezier_planning_locator_consumer.py
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"
LOCATOR_DISPLAY_NODE_CLASS = "vtkMRMLLocatorDisplayNode"
REAL_MAPPER_CLASS = "vtkOpenGLBezierResectionPolyDataMapper"


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


def _require_locator_seam_or_skip(pipeline):
    """Skip unless the Pipeline threads a locator seam onto its Representations.

    RED == the Pipeline never activates a Representation carrying a
    ``SetLocatorNode`` seam, i.e. the ADR-0025 consumer slice has not landed.
    The skip lifts when the Pipeline resolves + threads the locator node
    (ADR-0027 §Conformance).
    """
    pipeline._ensure_representations()  # noqa: SLF001 - test drives the lazy build
    reps = getattr(pipeline, "_representations", None)
    if not reps or not any(
        r is not None and hasattr(r, "SetLocatorNode") for r in reps.values()
    ):
        pytest.skip(
            "no Representation exposes a SetLocatorNode seam -- the ADR-0025 "
            "locator consumer slice has not landed."
        )


def _active_real_mapper_or_skip(pipeline, slicer):
    """Return the active Planning Representation's real surface mapper, or skip.

    The consumer lives on the Planning-state Bezier surface Representation; its
    mapper must be the real ``vtkOpenGLBezierResectionPolyDataMapper`` the
    locator uniforms live on (ADR-0014 §3).
    """
    name = getattr(pipeline, "_current_representation_name", None)
    reps = getattr(pipeline, "_representations", {}) or {}
    active = reps.get(name) if name else None
    if active is None or not hasattr(active, "GetSurfaceMapper"):
        pytest.skip(
            "active Representation exposes no surface mapper -- the Planning "
            "surface consumer is not the active Representation in this state."
        )
    mapper = active.GetSurfaceMapper()
    if mapper is None or not mapper.IsA(REAL_MAPPER_CLASS):
        actual = type(mapper).__name__ if mapper is not None else "None"
        pytest.skip(
            f"active surface mapper is {actual!r}, not {REAL_MAPPER_CLASS!r} -- "
            "the real mapper the locator uniforms live on is not present."
        )
    if not hasattr(mapper, "GetLocatorRadius"):
        pytest.skip(
            "surface mapper has no GetLocatorRadius accessor -- cannot read "
            "back the threaded uLocatorRadius uniform."
        )
    return mapper


def _attach_locator_display(slicer, locator, radius):
    """Attach a ``vtkMRMLLocatorDisplayNode`` with a known ``Radius``.

    Uses ``CreateDefaultDisplayNodes()`` (ADR-0025 §"The node"), falling back to
    an explicit add + observe if the convenience path is absent.
    """
    display = None
    if hasattr(locator, "CreateDefaultDisplayNodes"):
        locator.CreateDefaultDisplayNodes()
        display = locator.GetDisplayNode()
    if display is None:
        display = _add_or_skip(slicer, LOCATOR_DISPLAY_NODE_CLASS)
        locator.AddAndObserveDisplayNodeID(display.GetID())
    if not display.IsA(LOCATOR_DISPLAY_NODE_CLASS) or not hasattr(display, "SetRadius"):
        pytest.skip(
            f"locator display node is not a {LOCATOR_DISPLAY_NODE_CLASS} with "
            "SetRadius -- cannot exercise the radius uniform."
        )
    display.SetRadius(radius)
    return display


def test_pipeline_resolves_and_threads_single_locator_node():
    """Invariant 3 (positive): the Pipeline resolves + threads the locator node.

    With a single ``vtkMRMLLocatorNode`` in the scene, dispatching the Pipeline
    over the surface must resolve that node
    (``GetFirstNodeByClass("vtkMRMLLocatorNode")``) and thread it onto the
    active Representation, so the real mapper's ``GetLocatorRadius()`` reflects
    the locator display ``Radius`` -- with no external ``SetLocatorNode`` caller
    (ADR-0025 §"Consumer", ADR-0013 §6).
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_locator_seam_or_skip(pipeline)

    data, display = _wire_surface_with_display(slicer)

    locator = _add_or_skip(slicer, LOCATOR_NODE_CLASS)
    known_radius = 5.25
    locator.SetPickedPositionWorld(10.0, 20.0, 30.0)
    _attach_locator_display(slicer, locator, known_radius)

    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    mapper = _active_real_mapper_or_skip(pipeline, slicer)
    assert abs(mapper.GetLocatorRadius() - known_radius) < 1e-4, (
        "the Pipeline must resolve the scene's single vtkMRMLLocatorNode and "
        "thread it onto the active Representation so its display Radius reaches "
        f"the mapper's uLocatorRadius; got {mapper.GetLocatorRadius()} "
        f"(expected {known_radius})."
    )


def test_pipeline_locator_off_when_no_locator_node_in_scene():
    """Invariant 3 (negative): no locator node -> the consumer stays off.

    A Pipeline dispatched over a surface with NO ``vtkMRMLLocatorNode`` in the
    scene must leave the mapper's ``GetLocatorRadius()`` at ``0.0`` -- the
    resolution does not false-positive and the shader off state holds
    (ADR-0025 §"Rendering").
    """
    slicer = _slicer_or_skip()
    pipeline = _make_pipeline_or_skip()
    _require_locator_seam_or_skip(pipeline)

    data, display = _wire_surface_with_display(slicer)
    # No vtkMRMLLocatorNode is added to the scene.
    pipeline.SetDisplayNode(display)
    pipeline.UpdatePipeline()

    mapper = _active_real_mapper_or_skip(pipeline, slicer)
    assert abs(mapper.GetLocatorRadius()) < 1e-6, (
        "with no vtkMRMLLocatorNode in the scene the mapper's uLocatorRadius "
        f"must be 0 (the shader off state); got {mapper.GetLocatorRadius()}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
