# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Click-to-reslice CONSUMER kernel (GL-free), ADR-0025 §Click-to-reslice.

Pins the slice-reslice half of the ADR-0025 locator architecture: a
resectogram click carries a picked RAS world point on the single
``vtkMRMLLocatorNode``, and the consumer side reslices the orthogonal slice
view so the slice PLANE passes through that world point.  This file pins a NEW
module/class to be implemented later (ADR-0004 Python, ADR-0013 §5 -- no custom
displayable manager):

    LiverResectionsLib.LocatorReslicer.LocatorReslicer

The [test] pin (ADR-0025 §Conformance, verbatim): "click-to-reslice updates the
slice ``SliceToRAS`` so the slice passes through the picked world point."

THE KERNEL (the [test] pin)
---------------------------
A STATIC method::

    LocatorReslicer.reslice_slice_to_world(slice_node, world_xyz) -> bool

updates ``slice_node``'s ``SliceToRAS`` so the slice plane passes through the
RAS point ``world_xyz`` (a 3-sequence of float), PRESERVING orientation.  It is
implemented via ``vtkMRMLSliceNode.JumpSliceByOffsetting(r, a, s)`` -- which
translates the slice ALONG its normal only, so the plane's normal direction is
invariant and only the in-plane offset moves.  Returns True when it reslices;
False (a no-op) on degenerate input (``slice_node`` None, or ``world_xyz``
None), and it must not raise on those.

TEST DESIGN -- GL-free, launched-Slicer, no slice VIEW/widget
-------------------------------------------------------------
``SliceToRAS`` lives on the bare ``vtkMRMLSliceNode``; no slice view, layout
manager, or render window is realised.  The point-in-plane invariant is read
directly off the node's matrix:

  * normal  = the 3rd column of ``GetSliceToRAS()`` (rows 0..2, col 2);
  * origin  = the translation, the 4th column (rows 0..2, col 3);
  * a point ``p`` lies in the plane iff ``dot(normal, p - origin) == 0``.

Invariant 1 seeds a KNOWN non-axial orientation (a ~35 deg rotation so the
normal is not a pure axis -- a trivial axial plane would pass an
identity-preserving no-op), picks a world point deliberately OFF that plane,
reslices, and asserts (a) the point now lies in the plane and (b) the
normalized normal is unchanged (JumpSliceByOffsetting only translates).

WHY LAUNCHED-SLICER / RUN-VS-SKIP
---------------------------------
Needs the wrapped ``vtkMRMLSliceNode`` (+ its ``JumpSliceByOffsetting`` /
``SliceToRAS`` API) and the importable ``LocatorReslicer`` -- reachable only
inside a launched Slicer with the module on the path; a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` and those off the
path, so every test SKIPS CLEANLY via the shared ``slicer_pytest_support``
guards.  GL-free: the matrix accessors need no render window.

The kernel tests are SKIP-PENDING on the not-yet-existing ``LocatorReslicer`` /
``reslice_slice_to_world`` (ADR-0027 -- the skip lifts at the implementation
commit); ONCE PRESENT they must ASSERT, not skip.  The secondary observer test
(invariant 3) stays skip-pending on the constructor/observe API.

See also:
  * Docs/adr/0025-locator-architecture.md §Click-to-reslice, §Conformance
  * Docs/adr/0027-invariant-test-first-v2-implementation.md  (RED / skip-pending)
  * Docs/adr/0004-python-cpp-boundary.md   (the consumer is Python)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5  (no custom DM)
  * LiverResections/MRML/Testing/Cxx/vtkMRMLLocatorNodeTest1.cxx
"""

from __future__ import annotations

import math

import pytest

SLICE_NODE_CLASS = "vtkMRMLSliceNode"
LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"

# The module/class carrying the reslice kernel (ADR-0004 Python, ADR-0013 §5).
RESLICER_MODULE = "LiverResectionsLib.LocatorReslicer"
RESLICER_CLASS = "LocatorReslicer"

# Point-in-plane / normal-preservation tolerance.  Loose enough for the double
# rounding JumpSliceByOffsetting accumulates through the RAS->offset->matrix
# round trip, tight enough that a wrong translation axis or a rotated normal
# fails.
PLANE_TOL = 1e-4


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_pipeline_resolves_locator.py /
# test_resectogram_locator_pipeline_seam.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def _reslicer_class_or_skip_pending():
    """Return ``LocatorReslicer`` or SKIP-PENDING (ADR-0027).

    RED == the ``LocatorReslicer`` module/class is absent; the skip lifts at the
    implementation commit, at which point the kernel tests ASSERT.  A bare
    pytest run cannot import it (LiverResectionsLib is off the path), so this
    also serves as the bare-run clean skip.
    """
    try:
        module = __import__(RESLICER_MODULE, fromlist=[RESLICER_CLASS])
        return getattr(module, RESLICER_CLASS)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{RESLICER_CLASS} not importable ({exc!r}) -- the ADR-0025 "
            "click-to-reslice consumer has not landed (or LiverResectionsLib is "
            "off the path).  Skip lifts at the implementation commit (ADR-0027)."
        )


def _reslice_method_or_skip_pending(reslicer_cls):
    """Return the bound ``reslice_slice_to_world`` staticmethod or SKIP-PENDING."""
    method = getattr(reslicer_cls, "reslice_slice_to_world", None)
    if not callable(method):
        pytest.skip(
            f"{RESLICER_CLASS}.reslice_slice_to_world not present -- the ADR-0025 "
            "click-to-reslice kernel has not landed.  Skip lifts at the "
            "implementation commit (ADR-0027)."
        )
    return method


# --------------------------------------------------------------------------- #
# Matrix helpers -- read the plane off vtkMRMLSliceNode.GetSliceToRAS()
# --------------------------------------------------------------------------- #


def _seed_non_axial_orientation(slice_node, vtk, angle_deg=35.0):
    """Set a KNOWN non-axial ``SliceToRAS`` so the invariant is non-trivial.

    Rotates the default axial plane ~35 deg about the R axis, so the slice
    normal is neither a pure axis nor the world point's own axis -- an
    identity-preserving no-op would then fail invariant 1.  Adopts the
    externally-built matrix the way the vtkMRMLSliceNode API documents:
    ``GetSliceToRAS()->DeepCopy(m)`` followed by ``UpdateMatrices()`` (see the
    header doc-comment on ``GetSliceToRAS``).
    """
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    m = vtk.vtkMatrix4x4()
    m.Identity()
    # Rotation about R (x): leaves R fixed, tilts the A/S columns.
    m.SetElement(1, 1, c)
    m.SetElement(1, 2, -s)
    m.SetElement(2, 1, s)
    m.SetElement(2, 2, c)
    # A non-zero origin so "passes through the point" is not accidentally the
    # origin already lying on a plane through 0.
    m.SetElement(0, 3, 5.0)
    m.SetElement(1, 3, -7.0)
    m.SetElement(2, 3, 11.0)
    slice_node.GetSliceToRAS().DeepCopy(m)
    slice_node.UpdateMatrices()


def _plane_normal(slice_to_ras):
    """Slice normal = the 3rd column (rows 0..2, col 2) of SliceToRAS."""
    return (
        slice_to_ras.GetElement(0, 2),
        slice_to_ras.GetElement(1, 2),
        slice_to_ras.GetElement(2, 2),
    )


def _plane_origin(slice_to_ras):
    """Slice origin = the translation, the 4th column (rows 0..2, col 3)."""
    return (
        slice_to_ras.GetElement(0, 3),
        slice_to_ras.GetElement(1, 3),
        slice_to_ras.GetElement(2, 3),
    )


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _normalized(v):
    n = math.sqrt(_dot(v, v))
    if n == 0.0:
        return v
    return (v[0] / n, v[1] / n, v[2] / n)


def _signed_distance_to_plane(slice_to_ras, point):
    """dot(unit_normal, point - origin) -- zero iff ``point`` lies in the plane."""
    normal = _normalized(_plane_normal(slice_to_ras))
    origin = _plane_origin(slice_to_ras)
    diff = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    return _dot(normal, diff)


# --------------------------------------------------------------------------- #
# Invariant 1 -- the point-in-plane kernel (the [test] pin)
# --------------------------------------------------------------------------- #


def test_reslice_makes_slice_plane_pass_through_world_point():
    """The [test] pin: reslice updates SliceToRAS so the plane passes through
    the picked world point, preserving orientation.

    Seed a KNOWN non-axial orientation, pick a world point deliberately OFF the
    current plane, call ``reslice_slice_to_world``, then assert:
      (a) True is returned (a reslice happened);
      (b) the picked point now lies IN the plane
          (``dot(normal, point - origin) == 0`` within PLANE_TOL);
      (c) the plane NORMAL direction is unchanged
          (JumpSliceByOffsetting only translates along the normal).
    Once ``LocatorReslicer`` lands this ASSERTS; until then it skips-pending
    (ADR-0027).
    """
    slicer = _slicer_or_skip()
    import vtk

    reslicer_cls = _reslicer_class_or_skip_pending()
    reslice = _reslice_method_or_skip_pending(reslicer_cls)

    slice_node = _add_or_skip(slicer, SLICE_NODE_CLASS)
    _seed_non_axial_orientation(slice_node, vtk)

    normal_before = _normalized(_plane_normal(slice_node.GetSliceToRAS()))

    # A world point deliberately OFF the current plane: start at the origin and
    # step ALONG the normal so the signed distance is non-zero.
    origin = _plane_origin(slice_node.GetSliceToRAS())
    world = (
        origin[0] + 40.0 * normal_before[0] + 3.0,
        origin[1] + 40.0 * normal_before[1] - 2.0,
        origin[2] + 40.0 * normal_before[2] + 6.0,
    )
    assert abs(_signed_distance_to_plane(slice_node.GetSliceToRAS(), world)) > 1.0, (
        "test setup: the chosen world point must start OFF the seeded plane, "
        "else the invariant is trivially satisfied before reslicing."
    )

    result = reslice(slice_node, world)

    assert result is True, (
        "reslice_slice_to_world must return True when it reslices a valid slice "
        f"node to a valid world point; got {result!r}."
    )
    after = slice_node.GetSliceToRAS()
    distance = _signed_distance_to_plane(after, world)
    assert abs(distance) < PLANE_TOL, (
        "after reslicing, the picked world point must lie in the slice plane "
        f"(dot(normal, point - origin) == 0); signed distance is {distance} "
        f"(tol {PLANE_TOL}) -- the SliceToRAS was not offset onto the point "
        "(ADR-0025 §Click-to-reslice)."
    )
    normal_after = _normalized(_plane_normal(after))
    for axis, (b, a) in enumerate(zip(normal_before, normal_after)):
        assert abs(a - b) < PLANE_TOL, (
            "reslice must PRESERVE the slice orientation -- JumpSliceByOffsetting "
            f"only translates along the normal; normal component {axis} changed "
            f"from {b} to {a}."
        )


# --------------------------------------------------------------------------- #
# Invariant 2 -- degenerate inputs are no-ops returning False (and never raise)
# --------------------------------------------------------------------------- #


def test_reslice_no_op_when_slice_node_none():
    """A None slice node is a no-op returning False (and must not raise)."""
    _slicer_or_skip()
    reslicer_cls = _reslicer_class_or_skip_pending()
    reslice = _reslice_method_or_skip_pending(reslicer_cls)

    assert reslice(None, (1.0, 2.0, 3.0)) is False, (
        "reslice_slice_to_world(None, world) must be a no-op returning False, "
        "not raise -- there is no slice to reslice."
    )


def test_reslice_no_op_when_world_none():
    """A None world point is a no-op returning False (and must not raise),
    leaving the slice's SliceToRAS untouched."""
    slicer = _slicer_or_skip()
    import vtk

    reslicer_cls = _reslicer_class_or_skip_pending()
    reslice = _reslice_method_or_skip_pending(reslicer_cls)

    slice_node = _add_or_skip(slicer, SLICE_NODE_CLASS)
    _seed_non_axial_orientation(slice_node, vtk)
    before = vtk.vtkMatrix4x4()
    before.DeepCopy(slice_node.GetSliceToRAS())

    assert reslice(slice_node, None) is False, (
        "reslice_slice_to_world(slice_node, None) must be a no-op returning "
        "False, not raise -- there is no world point to reslice onto."
    )
    after = slice_node.GetSliceToRAS()
    for row in range(4):
        for col in range(4):
            assert abs(after.GetElement(row, col) - before.GetElement(row, col)) < PLANE_TOL, (
                "a degenerate (world None) reslice must leave the slice's "
                f"SliceToRAS untouched; element ({row},{col}) changed."
            )


# --------------------------------------------------------------------------- #
# Invariant 3 (secondary) -- the scene-observing consumer reslices the Red slice
# --------------------------------------------------------------------------- #


def test_locator_observer_reslices_red_slice_on_picked_position():
    """Secondary: a ``LocatorReslicer(scene)`` observes the scene's single
    ``vtkMRMLLocatorNode`` and reslices the Red slice so the picked point lies
    in its plane (ADR-0025 §Click-to-reslice, consumer side).

    Skip-pending on the constructor / observe API (the primary [test] pin is the
    kernel, invariants 1+2).  Uses the launched-Slicer Red slice node
    (``vtkMRMLSliceNodeRed``) so no view/widget is realised -- SliceToRAS lives
    on the bare node.
    """
    slicer = _slicer_or_skip()
    import vtk

    reslicer_cls = _reslicer_class_or_skip_pending()
    _reslice_method_or_skip_pending(reslicer_cls)

    red = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
    if red is None:
        pytest.skip(
            "no vtkMRMLSliceNodeRed in the scene -- the launched-Slicer default "
            "slice nodes are not present in this environment."
        )
    _seed_non_axial_orientation(red, vtk)

    locator = _add_or_skip(slicer, LOCATOR_NODE_CLASS)
    if not hasattr(locator, "SetPickedPositionWorld"):
        pytest.skip(
            "vtkMRMLLocatorNode has no SetPickedPositionWorld in this build -- "
            "cannot drive the observer."
        )

    # Construct the observing consumer.  Skip-pending on the constructor/observe
    # API until the consumer lands (ADR-0027).
    try:
        reslicer = reslicer_cls(slicer.mrmlScene)
    except Exception as exc:  # pragma: no cover - constructor-shape dependent
        pytest.skip(
            f"{RESLICER_CLASS}(scene) not constructable ({exc!r}) -- the "
            "scene-observing consumer wiring has not landed (ADR-0027)."
        )
    if reslicer is None:
        pytest.skip(f"{RESLICER_CLASS}(scene) returned None.")

    origin = _plane_origin(red.GetSliceToRAS())
    normal = _normalized(_plane_normal(red.GetSliceToRAS()))
    world = (
        origin[0] + 50.0 * normal[0] + 4.0,
        origin[1] + 50.0 * normal[1] - 3.0,
        origin[2] + 50.0 * normal[2] + 8.0,
    )

    locator.SetPickedPositionWorld(*world)
    locator.Modified()

    distance = _signed_distance_to_plane(red.GetSliceToRAS(), world)
    assert abs(distance) < PLANE_TOL, (
        "setting the locator's PickedPositionWorld + firing Modified must drive "
        "the observing LocatorReslicer to reslice the Red slice so the picked "
        f"point lies in its plane; signed distance is {distance} (tol {PLANE_TOL})."
    )

    # Tear down the observer so it does not survive to process shutdown (launched
    # leak discipline; the scene-cleanup fixture reclaims the minted nodes).
    for name in ("cleanup", "RemoveObservers", "removeObservers"):
        teardown = getattr(reslicer, name, None)
        if callable(teardown):
            try:
                teardown()
            except Exception:  # pragma: no cover - defensive teardown
                pass
            break


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_pick_places_the_dot_marker_in_slice_views():
    """A locator pick must place the slice-view DOT marker (ADR-0025).

    The reslice alone moves the slice plane but leaves no visible mark.  The
    marker is a small red sphere model with slice-intersection visibility ON
    and 3D visibility OFF (the surface disc is shader-drawn), NOT the
    crosshair -- its cross-lines read as a second, conflicting cue.  Pins:
    the model exists (attribute-tagged), sits centred on the pick, is red,
    2D-visible and 3D-hidden; a second pick MOVES it (no node multiplication).
    """
    slicer = _slicer_or_skip()
    reslicer_cls = _reslicer_class_or_skip_pending()

    scene = slicer.mrmlScene

    def _marker_nodes():
        return [
            scene.GetNthNodeByClass(i, "vtkMRMLModelNode")
            for i in range(scene.GetNumberOfNodesByClass("vtkMRMLModelNode"))
            if scene.GetNthNodeByClass(i, "vtkMRMLModelNode").GetAttribute(
                "LiverLocatorMarker"
            )
            == "True"
        ]

    for stale in _marker_nodes():
        scene.RemoveNode(stale)

    locator = scene.AddNewNodeByClass("vtkMRMLLocatorNode")
    try:
        reslicer = reslicer_cls(scene)
        locator.SetPickedPositionWorld(12.0, -34.0, 56.0)

        markers = _marker_nodes()
        assert len(markers) == 1, "exactly one dot-marker model per scene"
        marker = markers[0]
        bounds = marker.GetPolyData().GetBounds()
        centre = tuple((bounds[2 * i] + bounds[2 * i + 1]) / 2.0 for i in range(3))
        assert centre == pytest.approx((12.0, -34.0, 56.0), abs=1e-3), (
            "the marker sphere must be centred on the pick"
        )
        display = marker.GetDisplayNode()
        assert display is not None
        assert tuple(display.GetColor()) == pytest.approx((1.0, 0.0, 0.0))
        assert display.GetVisibility2D(), "slice views must show the dot"
        assert not display.GetVisibility3D(), (
            "3D stays shader-drawn on the surface -- no duplicate sphere"
        )

        locator.SetPickedPositionWorld(-5.0, 6.0, -7.0)
        markers = _marker_nodes()
        assert len(markers) == 1, "a second pick must MOVE the marker, not add one"
        bounds = markers[0].GetPolyData().GetBounds()
        centre = tuple((bounds[2 * i] + bounds[2 * i + 1]) / 2.0 for i in range(3))
        assert centre == pytest.approx((-5.0, 6.0, -7.0), abs=1e-3)
        reslicer.cleanup()
    finally:
        scene.RemoveNode(locator)
        for stale in _marker_nodes():
            scene.RemoveNode(stale)
