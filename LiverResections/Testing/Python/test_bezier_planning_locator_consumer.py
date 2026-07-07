# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Locator consumer -- BezierPlanningRepresentation drives the locator uniforms.

Pins the Representation half of the ADR-0025 locator *consumer* slice (#489
consumer half): ``BezierPlanningRepresentation`` reads a single
``vtkMRMLLocatorNode``'s picked world point + its display-node radius and drives
the real ``vtkOpenGLBezierResectionPolyDataMapper``'s locator uniforms
(``uLocatorPosition`` / ``uLocatorRadius``, ADR-0025 §"Rendering").  The
consumer is realised INSIDE the existing T2 Bezier surface Representation -- NO
new displayable manager, NO new pipeline factory (ADR-0013 §5).

The seam this pins:

  * ``rep.SetLocatorNode(node)`` -- the Pipeline threads the resolved single
    locator node onto the active Representation before ``update()`` (mirrors the
    existing ``SetResectionPlanNode`` thread, ADR-0013 §6).
  * ``rep.update(display, data)`` -- when the locator node carries a
    ``PickedPositionWorld`` and its display node a ``Radius``, the real mapper's
    ``GetLocatorPosition()`` matches that world point and ``GetLocatorRadius()``
    matches the display radius (invariant 1).  When there is no locator node
    (``SetLocatorNode(None)``) or no active picked position, the mapper's
    ``GetLocatorRadius()`` is ``0.0`` -- the shader's off state
    (``uLocatorRadius == 0``, invariant 2).

SCOPE: this pins the node -> consumer half only.  The FULL producer ->
``vtkMRMLLocatorNode`` -> consumer chain (issue #489; ADR-0025 §Conformance
[test]) closes when Slice B (the resectogram producer) lands; the producer is
not exercised here.

-- VERIFIED API (from the merged headers) --

  * ``vtkMRMLLocatorNode``:
    ``SetPickedPositionWorld(x, y, z)`` / ``GetPickedPositionWorld()`` --
    TRANSIENT double[3] RAS world point (the carrier of the picked point);
    ``CreateDefaultDisplayNodes()`` mints + wires a single
    ``vtkMRMLLocatorDisplayNode`` (ADR-0025 §"The node").
  * ``vtkMRMLLocatorDisplayNode``: ``SetRadius(double)`` / ``GetRadius()`` --
    the sphere radius that feeds ``uLocatorRadius`` (per the node's own doc).
  * ``vtkOpenGLBezierResectionPolyDataMapper`` (merged, ADR-0014 §3):
    ``GetLocatorPosition()`` (``const float*``), ``SetLocatorPosition(...)``,
    ``GetLocatorRadius()`` / ``SetLocatorRadius(float)``.

The mapper DOES expose a radius getter (``GetLocatorRadius()`` -> ``float``), so
both the on- and off-states are pinned on the readable radius.  The position
getter is a ``const float*``; VTK's Python wrapper returns that as a length-3
tuple, but where that is unreliable across builds the radius is the primary
proxy (the same readable-scalar-proxy idiom as the colour setters in
``test_bezier_planning_surface_mapper_wiring.py``).

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

``vtkOpenGLBezierResectionPolyDataMapper`` (LiverResections VTKWidgets) and the
wrapped ``vtkMRMLLocatorNode`` / ``vtkMRMLLocatorDisplayNode`` are wrapped-C++
classes reachable only inside a launched Slicer with the module loaded; a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` and those classes
off the path, so this SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards.  All GL-free: the mapper's uniform accessors need no render window.

-- WHY RED NOW --

``BezierPlanningRepresentation`` has no ``SetLocatorNode`` seam yet, so each
test skips on ``_require_locator_seam_or_skip``; the skip lifts when the
consumer slice lands (ADR-0027 §Conformance -- the skip lifts at the
implementation commit).

See also:
  * Docs/adr/0025-locator-architecture.md §"Rendering", §"Consumer", §Conformance
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5, §6
  * Docs/adr/0027-invariant-test-first-v2-implementation.md
  * LiverResections/MRML/vtkMRMLLocatorNode.h
  * LiverResections/MRML/vtkMRMLLocatorDisplayNode.h
  * LiverResections/VTKWidgets/vtkOpenGLBezierResectionPolyDataMapper.h
  * LiverResections/Testing/Python/test_bezier_planning_surface_mapper_wiring.py
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"
LOCATOR_DISPLAY_NODE_CLASS = "vtkMRMLLocatorDisplayNode"
REAL_MAPPER_CLASS = "vtkOpenGLBezierResectionPolyDataMapper"


def _slicer_or_skip():
    """Resolve a launched ``slicer`` module or skip cleanly under bare pytest."""
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_representation_or_skip():
    """Construct a ``BezierPlanningRepresentation`` or skip if unimportable."""
    try:
        from LiverResectionsLib.Representations.BezierPlanningRepresentation import (
            BezierPlanningRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "BezierPlanningRepresentation not importable "
            f"({exc!r}) -- the Planning Representation is not reachable in "
            "this environment."
        )
    return BezierPlanningRepresentation()


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _require_real_mapper_or_skip(rep):
    """Skip unless the Representation's surface mapper is the real type.

    The consumer drives ``uLocatorPosition`` / ``uLocatorRadius`` on the real
    ``vtkOpenGLBezierResectionPolyDataMapper``; on the generic placeholder
    mapper there are no locator setters to drive.  This is the same guard the
    sibling mapper-wiring test uses (ADR-0014 §3).
    """
    mapper = rep.GetSurfaceMapper()
    if mapper is None or not mapper.IsA(REAL_MAPPER_CLASS):
        actual = type(mapper).__name__ if mapper is not None else "None"
        pytest.skip(
            "BezierPlanningRepresentation surface mapper is "
            f"{actual!r}, not {REAL_MAPPER_CLASS!r} -- the real mapper the "
            "locator uniforms live on is not present."
        )
    return mapper


def _require_locator_seam_or_skip(rep):
    """Skip unless the locator-consumer seam has landed.

    RED == ``BezierPlanningRepresentation`` has no ``SetLocatorNode`` seam or
    the mapper has no ``GetLocatorRadius`` accessor.  The skip lifts when the
    ADR-0025 consumer slice wires the locator node -> mapper uniforms (ADR-0027
    §Conformance).
    """
    mapper = rep.GetSurfaceMapper()
    if not hasattr(rep, "SetLocatorNode"):
        pytest.skip(
            "BezierPlanningRepresentation has no SetLocatorNode seam -- the "
            "ADR-0025 locator consumer slice has not landed."
        )
    if not hasattr(mapper, "GetLocatorRadius"):
        pytest.skip(
            "surface mapper has no GetLocatorRadius accessor -- cannot read "
            "back the driven uLocatorRadius uniform."
        )


def _attach_locator_display(slicer, locator, radius):
    """Attach a ``vtkMRMLLocatorDisplayNode`` with a known ``Radius``.

    Uses the node's own ``CreateDefaultDisplayNodes()`` (ADR-0025 §"The node":
    mints + wires a single display node), then reads the wired display node
    back and sets its ``Radius``.  Falls back to adding + observing a display
    node explicitly if the convenience path is not present in this build.
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


def _locator_position(mapper):
    """Read the mapper's ``GetLocatorPosition()`` as a length-3 tuple, or None.

    The getter is a ``const float*``; VTK's Python wrapper usually returns a
    length-3 tuple, but where it surfaces as an opaque pointer-string the
    caller falls back to the readable radius (the same wrapping caveat the
    colour getters carry in test_bezier_planning_surface_mapper_wiring.py).
    """
    raw = mapper.GetLocatorPosition()
    try:
        pos = tuple(float(c) for c in raw)
    except (TypeError, ValueError):
        return None
    return pos if len(pos) == 3 else None


def test_planning_locator_consumer_drives_uniforms_from_node():
    """Invariant 1: the consumer drives the mapper uniforms from the node.

    With a ``vtkMRMLLocatorNode`` whose ``PickedPositionWorld`` is a known RAS
    point and a display node with a known ``Radius``, after
    ``SetLocatorNode(node)`` + ``update()`` the real mapper's
    ``GetLocatorRadius()`` reflects the display radius and (when the position
    getter is Python-readable) ``GetLocatorPosition()`` matches the world point
    within float tolerance (ADR-0025 §"Rendering").
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    mapper = _require_real_mapper_or_skip(rep)
    _require_locator_seam_or_skip(rep)

    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, DISPLAY_NODE_CLASS)

    locator = _add_or_skip(slicer, LOCATOR_NODE_CLASS)
    known_point = (12.0, -34.0, 56.0)
    known_radius = 4.5
    locator.SetPickedPositionWorld(*known_point)
    _attach_locator_display(slicer, locator, known_radius)

    rep.SetLocatorNode(locator)
    rep.update(display, data)

    assert abs(mapper.GetLocatorRadius() - known_radius) < 1e-4, (
        "the locator display node's Radius must reach the mapper's "
        f"SetLocatorRadius uniform; got {mapper.GetLocatorRadius()} "
        f"(expected {known_radius})."
    )

    # Position is a const float* getter; assert only when it is
    # Python-readable (the mapper stores float, the node is double -> tolerance).
    pos = _locator_position(mapper)
    if pos is not None:
        for got, want in zip(pos, known_point):
            assert abs(got - want) < 1e-3, (
                "the locator node's PickedPositionWorld must reach the mapper's "
                f"SetLocatorPosition uniform; got {pos} (expected {known_point})."
            )


def test_planning_locator_off_state_zeroes_radius_when_no_node():
    """Invariant 2: no locator node -> ``SetLocatorRadius(0.0)`` (marker off).

    ``SetLocatorNode(None)`` (no active locator) must leave the mapper's
    ``GetLocatorRadius()`` at ``0.0`` -- the shader's off state
    (``uLocatorRadius == 0``, ADR-0025 §"Rendering").  Pinned by first driving
    a non-zero radius from a real node, then clearing the node and confirming
    the radius collapses to zero (MRML state and GL state must not diverge).
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    mapper = _require_real_mapper_or_skip(rep)
    _require_locator_seam_or_skip(rep)

    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, DISPLAY_NODE_CLASS)

    # First establish a non-zero radius from a real locator so the zero after
    # clearing is a genuine transition, not the mapper's construction default.
    locator = _add_or_skip(slicer, LOCATOR_NODE_CLASS)
    locator.SetPickedPositionWorld(1.0, 2.0, 3.0)
    _attach_locator_display(slicer, locator, 7.0)
    rep.SetLocatorNode(locator)
    rep.update(display, data)
    assert mapper.GetLocatorRadius() > 0.0, (
        "precondition: a real locator with a positive display Radius must "
        "drive a positive uLocatorRadius before the off-state is exercised."
    )

    # Clear the locator -> the marker turns off (radius uniform 0).
    rep.SetLocatorNode(None)
    rep.update(display, data)
    assert abs(mapper.GetLocatorRadius()) < 1e-6, (
        "with no locator node the mapper's uLocatorRadius must be 0 (the "
        f"shader off state, ADR-0025 §Rendering); got {mapper.GetLocatorRadius()}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
