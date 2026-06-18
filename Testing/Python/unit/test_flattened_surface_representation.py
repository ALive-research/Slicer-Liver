# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``FlattenedSurfaceRepresentation`` — ADR-0013 §6.

Mirrors ``test_confirmed_representation.py``'s structure (pure-Python
introspection assertions + a thin VTK-mediated layer).  The flattened-
surface Representation is the v2.0 LayerDM-bound home of the resectogram's
2D render assembly (`ADR-0025`_ §Context): a flattened-quad source feeding
the relocated ``vtkOpenGLResection2DPolyDataMapper``, an actor, the private
overlay camera, the distance-map texture binding, and the anisotropic
``MatRatio`` aspect-ratio scaling.

The invariants pinned here (ADR-0027 — the SPECIFIC invariant, not "some
assembly exists"):

* **MatRatio routing (T3-b)** — a square domain (or
  ``EnableFlexibleBoundary`` false) yields the isotropic ``{1, 1}``; a
  non-square domain with the toggle on yields the v1 squeeze, computed by
  the ``vtkLiverResectogramAspectRatio`` Algorithm helper (`ADR-0015`_ §1)
  — the Representation does NOT re-derive the math.  The helper itself is
  C++ (its own pure-math invariant lives in
  ``vtkLiverResectogramAspectRatioTest``); here we pin that the
  Representation calls it with the right arguments and pushes the result
  onto the mapper.
* **Overlay camera pose** — the resectogram camera is posed from the
  flattened quad's bounds, and ``MirrorDisplay`` flips the camera's z
  sign (the v1 ``ResectogramPlaneCenter`` mirror toggle).

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0015 §1 — Algorithm-library pure-VTK helpers
  (``vtkLiverResectogramAspectRatio``).
* ADR-0025 §Context — the resectogram is a 1:1 image of the Bezier
  ``(u, v)`` parameter domain.
* ADR-0027 — invariant-test-first.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry — mirrors test_confirmed_representation.py.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Stub nodes
# --------------------------------------------------------------------------- #


class _StubDisplayNode:
    def __init__(
        self,
        show_2d: bool = True,
        mirror: bool = False,
        flexible: bool = False,
        texture_num_comps: int = 1,
    ) -> None:
        self.show_2d = show_2d
        self.mirror = mirror
        self.flexible = flexible
        self.texture_num_comps = texture_num_comps

    def GetShowResection2D(self) -> bool:
        return self.show_2d

    def GetMirrorDisplay(self) -> bool:
        return self.mirror

    def GetEnableFlexibleBoundary(self) -> bool:
        return self.flexible

    def GetTextureNumComps(self) -> int:
        return self.texture_num_comps


class _StubPoints:
    """Minimal sampled-surface points object the helper would walk.

    Carries an explicit number of points so the Representation's
    ``(samplesU, samplesV)`` resolution probe resolves deterministically.
    """

    def __init__(self, num_points: int = 400) -> None:
        self.num_points = num_points

    def GetNumberOfPoints(self) -> int:
        return self.num_points


class _StubDataNode:
    def __init__(self, sampled=None) -> None:
        self.sampled = sampled if sampled is not None else _StubPoints()

    def GetSampledSurfacePoints(self):
        return self.sampled


@pytest.fixture
def rep_module():
    from Representations.FlattenedSurfaceRepresentation import (
        FlattenedSurfaceRepresentation,
    )

    return FlattenedSurfaceRepresentation


# --------------------------------------------------------------------------- #
# Pure-Python assertions (run with or without VTK)
# --------------------------------------------------------------------------- #


def test_representation_construct_with_no_renderer(rep_module):
    """Construct without a renderer — no exception, MatRatio unset."""
    rep = rep_module()
    assert rep.GetRenderer() is None
    # No update() yet → no MatRatio has been pushed.
    assert rep.GetMatRatioApplied() is None
    rep.cleanup()


def test_representation_update_tolerates_none_nodes(rep_module):
    rep = rep_module()
    rep.update(display_node=None, data_node=None)
    rep.cleanup()


def test_representation_input_refresh_memoised(rep_module):
    """A repeat update with the same surface is a no-op; a new surface
    bumps the refresh counter."""
    rep = rep_module()
    display = _StubDisplayNode()
    data = _StubDataNode()
    rep.update(display, data)
    after_first = rep.GetInputRefreshCount()
    assert after_first == 1

    rep.update(display, data)
    assert rep.GetInputRefreshCount() == after_first

    rep.update(display, _StubDataNode(sampled=_StubPoints(361)))
    assert rep.GetInputRefreshCount() == after_first + 1
    rep.cleanup()


# --------------------------------------------------------------------------- #
# MatRatio routing (T3-b) — the load-bearing aspect-ratio invariant.
# --------------------------------------------------------------------------- #


class _StubMapperWithMatRatio:
    """Drop-in mapper exposing ``SetMatRatio`` — the relocated
    ``vtkOpenGLResection2DPolyDataMapper``'s API — so the MatRatio routing
    is exercised without the wrapped C++ mapper present locally."""

    def __init__(self) -> None:
        self.mat_ratio = None
        self.texture_num_comps = None

    def SetMatRatio(self, ratio) -> None:
        self.mat_ratio = list(ratio)

    def SetTextureNumComps(self, value) -> None:
        self.texture_num_comps = int(value)

    def SetInputConnection(self, _conn) -> None:
        pass


def _inject_mat_ratio_mapper(rep):
    """Install the MatRatio stub as the Representation's 2D mapper.

    The Representation pushes MatRatio / TextureNumComps off
    ``_resection_mapper_2d`` directly (see ``_apply_mat_ratio``), so
    re-pointing the actor at the stub is unnecessary — and a real
    ``vtkActor`` (the launched harness) rejects a non-``vtkMapper`` via
    ``SetMapper``.  Setting ``_resection_mapper_2d`` is sufficient and
    works in both the bare and launched rows.
    """
    mapper = _StubMapperWithMatRatio()
    rep._resection_mapper_2d = mapper
    return mapper


def test_mat_ratio_isotropic_when_not_flexible(rep_module):
    """``EnableFlexibleBoundary`` false → the isotropic ``{1, 1}`` (the
    v1 ``Ratio`` else-branch), with NO call into the helper."""
    rep = rep_module()
    mapper = _inject_mat_ratio_mapper(rep)
    display = _StubDisplayNode(flexible=False)
    rep.update(display, _StubDataNode())
    assert mapper.mat_ratio == pytest.approx([1.0, 1.0])
    assert rep.GetMatRatioApplied() == pytest.approx((1.0, 1.0))
    rep.cleanup()


def test_mat_ratio_isotropic_when_no_sampled_surface(rep_module):
    """Flexible but no sampled surface → still ``{1, 1}`` (defensive
    short-circuit; the helper needs points)."""
    rep = rep_module()
    mapper = _inject_mat_ratio_mapper(rep)
    display = _StubDisplayNode(flexible=True)

    class _EmptyDataNode:
        def GetSampledSurfacePoints(self):
            return None

    rep.update(display, _EmptyDataNode())
    assert mapper.mat_ratio == pytest.approx([1.0, 1.0])
    rep.cleanup()


def test_mat_ratio_routes_non_square_squeeze_through_helper(
    rep_module, monkeypatch
):
    """Flexible + a non-square domain → the squeeze, computed by the
    ``vtkLiverResectogramAspectRatio`` helper.

    The Representation must NOT re-derive the v1 ``Ratio`` math — it must
    delegate to ``ComputeAspectRatio`` and push the helper's result.  We
    inject a stub helper that emulates the helper's contract for a domain
    whose v extent is twice the u extent (``{0.5, 1.0}`` — the
    ``Resectogram4x4NonSquareScaling`` scenario's value) and assert the
    Representation forwarded the call and pushed the stub's answer.
    """
    import Representations.FlattenedSurfaceRepresentation as module

    seen = {}

    class _StubHelper:
        @staticmethod
        def ComputeAspectRatio(sampled, samples_u, samples_v, flexible, out):
            seen["sampled"] = sampled
            seen["samples_u"] = samples_u
            seen["samples_v"] = samples_v
            seen["flexible"] = flexible
            # v extent twice u → longer axis (v) normalised to 1, u squeezed.
            out[0] = 0.5
            out[1] = 1.0

    monkeypatch.setattr(
        module, "_import_aspect_ratio_helper", lambda: _StubHelper
    )

    rep = rep_module()
    mapper = _inject_mat_ratio_mapper(rep)
    points = _StubPoints(400)  # 20x20 → samplesU == samplesV == 20
    display = _StubDisplayNode(flexible=True)
    rep.update(display, _StubDataNode(sampled=points))

    assert seen["sampled"] is points
    assert seen["samples_u"] == 20
    assert seen["samples_v"] == 20
    assert seen["flexible"] is True
    assert mapper.mat_ratio == pytest.approx([0.5, 1.0])
    assert rep.GetMatRatioApplied() == pytest.approx((0.5, 1.0))
    rep.cleanup()


def test_texture_num_comps_pushed_to_mapper(rep_module):
    rep = rep_module()
    mapper = _inject_mat_ratio_mapper(rep)
    rep.update(_StubDisplayNode(texture_num_comps=4), _StubDataNode())
    assert mapper.texture_num_comps == 4
    rep.cleanup()


# --------------------------------------------------------------------------- #
# VTK-mediated assertions
# --------------------------------------------------------------------------- #


@pytest.fixture
def vtk_module():
    return pytest.importorskip(
        "vtk",
        reason="vtk not importable; skip the VTK-mediated Representation tests.",
    )


def test_assembly_builds_quad_source_mapper_actor_camera(rep_module, vtk_module):
    """The full assembly is built when VTK is present (ADR-0013 §6)."""
    rep = rep_module()
    assert rep.GetBezierPlane() is not None
    assert rep.GetResectionMapper2D() is not None
    assert rep.GetResectionActor2D() is not None
    assert rep.GetResectogramCamera() is not None
    rep.cleanup()


def test_flattened_quad_source_emits_geometry(rep_module, vtk_module):
    """The flattened-quad source carries renderable geometry (T3-e go-live).

    The resectogram actor lights pixels only if its mapper has a non-empty
    flattened-domain quad to draw.  The Representation tessellates the fixed
    planar quad the v1 ``BezierPlane`` poses from (ADR-0025 §Context); pin
    that the source's output has points + a positive planar (x/y) extent so
    a regression that stops feeding the quad (the 0-lit-pixel failure mode)
    is caught at the unit layer rather than only in the GPU arena.
    """
    rep = rep_module()
    plane = rep.GetBezierPlane()
    assert plane is not None
    plane.Update()
    output = plane.GetOutput()
    assert output.GetNumberOfPoints() > 0, (
        "the flattened-quad source emitted no points -- the resectogram "
        "actor would have nothing to draw (0 lit pixels)."
    )
    bounds = output.GetBounds()
    assert bounds[1] > bounds[0], "the flattened quad has no x extent"
    assert bounds[3] > bounds[2], "the flattened quad has no y extent"
    rep.cleanup()


def test_actor_visibility_follows_show_resection_2d(rep_module, vtk_module):
    rep = rep_module()
    rep.update(_StubDisplayNode(show_2d=True), _StubDataNode())
    assert rep.GetResectionActor2D().GetVisibility() == 1
    rep.update(_StubDisplayNode(show_2d=False), _StubDataNode())
    assert rep.GetResectionActor2D().GetVisibility() == 0
    rep.cleanup()


def test_overlay_camera_posed_from_quad_bounds(rep_module, vtk_module):
    """The overlay camera is posed from the flattened quad's bounds; the
    focal point sits at the quad centre in x/y (the v1
    ``ResectogramPlaneCenter`` pose)."""
    rep = rep_module()
    rep.update(_StubDisplayNode(mirror=False), _StubDataNode())
    camera = rep.GetResectogramCamera()
    plane = rep.GetBezierPlane()
    plane.Update()
    bounds = plane.GetOutput().GetBounds()
    cx = (bounds[0] + bounds[1]) / 2.0
    cy = (bounds[2] + bounds[3]) / 2.0
    focal = camera.GetFocalPoint()
    assert focal[0] == pytest.approx(cx)
    assert focal[1] == pytest.approx(cy)
    rep.cleanup()


def test_mirror_display_flips_camera_z_sign(rep_module, vtk_module):
    """``MirrorDisplay`` flips the sign of the camera's z position — the
    v1 ``ResectogramPlaneCenter(mirror)`` toggle (ADR-0025 §Context)."""
    rep = rep_module()
    rep.update(_StubDisplayNode(mirror=False), _StubDataNode())
    z_unmirrored = rep.GetResectogramCamera().GetPosition()[2]
    rep.update(_StubDisplayNode(mirror=True), _StubDataNode())
    z_mirrored = rep.GetResectogramCamera().GetPosition()[2]
    assert z_unmirrored * z_mirrored < 0.0, (
        "MirrorDisplay must flip the resectogram camera's z sign "
        "(v1 ResectogramPlaneCenter mirror toggle)."
    )
    rep.cleanup()
