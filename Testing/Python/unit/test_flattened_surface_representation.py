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
        blur_enabled: bool = False,
        blur_radius: float = 2.0,
    ) -> None:
        self.show_2d = show_2d
        self.mirror = mirror
        self.flexible = flexible
        self.texture_num_comps = texture_num_comps
        self.blur_enabled = blur_enabled
        self.blur_radius = blur_radius

    def GetShowResection2D(self) -> bool:
        return self.show_2d

    def GetMirrorDisplay(self) -> bool:
        return self.mirror

    def GetEnableFlexibleBoundary(self) -> bool:
        return self.flexible

    def GetTextureNumComps(self) -> int:
        return self.texture_num_comps

    def GetBlurEnabled(self) -> bool:
        return self.blur_enabled

    def GetBlurRadius(self) -> float:
        return self.blur_radius


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
    """Return a factory that constructs the Representation with an injected mapper.

    The custom ``vtkOpenGLResection2DPolyDataMapper`` is off the path in the
    bare-VTK unit layer (ADR-0008 §2), so production's resolve-or-raise path
    cannot run here; each construction injects a generic ``vtkPolyDataMapper``
    instance via the ``resection_mapper_2d`` seam (ADR-0014 §3).  Some tests
    then swap in a MatRatio stub over that mapper; the injection just gets the
    construction past the resolve-or-raise gate.
    """
    import vtk

    from Representations.FlattenedSurfaceRepresentation import (
        FlattenedSurfaceRepresentation,
    )

    def _make_rep(renderer=None):
        return FlattenedSurfaceRepresentation(
            renderer, resection_mapper_2d=vtk.vtkPolyDataMapper()
        )

    return _make_rep


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


# --------------------------------------------------------------------------- #
# Gaussian-blur post-pass (T3-g2) — the net-new v2.0 on/off blur invariant.
#
# qMRMLThreeDView owns the shared renderer's render-pass chain (it resets
# SetPass(nullptr) on every view-node ModifiedEvent), so the Representation
# hosts the blur on a PRIVATE overlay renderer it adds to the render window
# when BlurEnabled is true (ADR-0013 §6 — the Representation owns the pass).
# These pin: the overlay renderer is created + added to the window with the
# vtkGaussianBlurPass set on IT when blur engages; the toggle is live
# (true->false->true reuses the same objects); teardown removes the overlay
# from the window; a no-renderer reconcile is a no-op.  They need a real
# renderer + render window (SetPass / AddRenderer), so they skip when the
# render-pass classes are unavailable.
#
# The OVERLAY renderer carries the pass — NOT the main renderer (whose
# GetPass() is not None inside a live qMRMLThreeDView, so asserting it is
# None there would be wrong).
# --------------------------------------------------------------------------- #


@pytest.fixture
def render_pass_or_skip(vtk_module):
    if getattr(vtk_module, "vtkGaussianBlurPass", None) is None:
        pytest.skip("vtkGaussianBlurPass unavailable in this VTK build.")
    if getattr(vtk_module, "vtkRenderStepsPass", None) is None:
        pytest.skip("vtkRenderStepsPass unavailable in this VTK build.")
    return vtk_module


def _renderer_in_window(vtk):
    """Return a renderer wired into an offscreen render window.

    The blur pass is set directly on this renderer; a window is not strictly
    required for ``SetPass``, but an offscreen window keeps the fixture close
    to the live path without lighting real pixels.
    """
    renderer = vtk.vtkRenderer()
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.AddRenderer(renderer)
    return renderer, window


def test_blur_pass_attached_when_enabled(rep_module, render_pass_or_skip):
    """``BlurEnabled`` true → a vtkGaussianBlurPass is set on the renderer."""
    vtk = render_pass_or_skip
    renderer, _window = _renderer_in_window(vtk)
    rep = rep_module(renderer=renderer)
    assert not rep.IsBlurPassAttached()
    assert renderer.GetPass() is None

    rep.update(_StubDisplayNode(blur_enabled=True), _StubDataNode())

    assert rep.IsBlurPassAttached(), "blur not engaged with BlurEnabled true"
    assert renderer.GetPass() is rep.GetBlurPass() is not None, (
        "the blur pass is not set on the renderer"
    )
    assert rep.GetBlurPass().IsA("vtkGaussianBlurPass")
    rep.cleanup()


def test_blur_pass_absent_when_disabled(rep_module, render_pass_or_skip):
    """``BlurEnabled`` false → no pass on the renderer; blur is off."""
    vtk = render_pass_or_skip
    renderer, _window = _renderer_in_window(vtk)
    rep = rep_module(renderer=renderer)
    rep.update(_StubDisplayNode(blur_enabled=False), _StubDataNode())
    assert not rep.IsBlurPassAttached()
    assert renderer.GetPass() is None
    rep.cleanup()


def test_blur_toggles_live(rep_module, render_pass_or_skip):
    """Toggling ``BlurEnabled`` across successive ``update()`` calls engages
    then disengages blur without rebuilding the assembly — the live-toggle
    invariant (ADR-0013 §6).  The SAME pass object is reused on re-engage (no
    rebuild / leak)."""
    vtk = render_pass_or_skip
    renderer, _window = _renderer_in_window(vtk)
    rep = rep_module(renderer=renderer)

    rep.update(_StubDisplayNode(blur_enabled=True), _StubDataNode())
    assert renderer.GetPass() is rep.GetBlurPass() is not None
    blur_pass = rep.GetBlurPass()

    rep.update(_StubDisplayNode(blur_enabled=False), _StubDataNode())
    assert not rep.IsBlurPassAttached()
    assert renderer.GetPass() is None

    rep.update(_StubDisplayNode(blur_enabled=True), _StubDataNode())
    assert renderer.GetPass() is blur_pass, "blur pass was rebuilt on re-engage"
    rep.cleanup()


def test_blur_detached_on_cleanup(rep_module, render_pass_or_skip):
    """``cleanup()`` clears the blur pass off the renderer (forward path
    restored)."""
    vtk = render_pass_or_skip
    renderer, _window = _renderer_in_window(vtk)
    rep = rep_module(renderer=renderer)
    rep.update(_StubDisplayNode(blur_enabled=True), _StubDataNode())
    assert renderer.GetPass() is not None
    rep.cleanup()
    assert renderer.GetPass() is None, "blur pass survived cleanup on the renderer"


def test_blur_reconcile_tolerates_no_renderer(rep_module):
    """Blur reconcile is a no-op without a renderer (bare-VTK / unit path) —
    no exception, blur never engages."""
    rep = rep_module()
    rep.update(_StubDisplayNode(blur_enabled=True), _StubDataNode())
    assert not rep.IsBlurPassAttached()
    rep.cleanup()


# --------------------------------------------------------------------------- #
# Distance-map texture build discipline (resectogram render-blocker class).
# --------------------------------------------------------------------------- #
#
# The resectogram strip rendered permanently white because the texture build
# path had three defects, each pinned GL-free here through injected seams:
#
#   1. ``TextureNumComps`` (display node) defaults to 0 and nothing writes it,
#      so ``CreateSeq3DFromRaw`` was asked for a 0-component texture -- format
#      resolution fails deterministically.  The image KNOWS its component
#      count; the build must fall back to it.
#   2. ``CreateSeq3DFromRaw``'s boolean result was ignored (a VTK error is not
#      a Python exception), so a FAILED upload was bound to the mapper and the
#      already-bound idempotency guard prevented every retry.
#   3. A not-yet-realized render window (``GetInitialized()`` False) has an
#      empty texture-format table; attempting the upload there fails noisily.
#      The build must defer (return None) so a later update retries.


class _FakeTextureHelper:
    """Records CreateSeq3DFromRaw args; configurable success/failure."""

    instances: list = []
    create_result = True

    def __init__(self):
        self.calls = []
        _FakeTextureHelper.instances.append(self)

    def SetContext(self, ctx):  # noqa: N802 - VTK verb
        self.context = ctx

    def SetBorderColor(self, *rgba):  # noqa: N802 - VTK verb
        pass

    def CreateSeq3DFromRaw(self, nx, ny, nz, comps, dtype, ptr, seq):  # noqa: N802
        self.calls.append(dict(dims=(nx, ny, nz), comps=comps))
        return _FakeTextureHelper.create_result


class _FakeRenderWindow:
    def __init__(self, initialized=True):
        self._initialized = initialized

    def GetInitialized(self):  # noqa: N802 - VTK verb
        return self._initialized


class _FakeImage3D:
    def GetDimensions(self):  # noqa: N802 - VTK verb
        return (8, 8, 8)

    def GetNumberOfScalarComponents(self):  # noqa: N802 - VTK verb
        return 4

    def GetScalarPointer(self):  # noqa: N802 - VTK verb
        return None


def _texture_build_rep(rep_module, monkeypatch, initialized=True):
    import Representations.FlattenedSurfaceRepresentation as fsr

    _FakeTextureHelper.instances = []
    _FakeTextureHelper.create_result = True
    monkeypatch.setattr(
        fsr, "_import_texture_object_helper", lambda: _FakeTextureHelper
    )
    rep = rep_module()
    monkeypatch.setattr(
        rep, "_render_window", lambda: _FakeRenderWindow(initialized=initialized)
    )
    return rep


def test_texture_build_derives_comps_from_image_when_display_unset(
    rep_module, monkeypatch
):
    """Display ``TextureNumComps`` 0 (the unset default) -> the image's
    component count reaches the upload, not 0."""
    rep = _texture_build_rep(rep_module, monkeypatch)
    texture = rep._create_distance_map_texture(_FakeImage3D(), 0)
    assert texture is not None
    assert _FakeTextureHelper.instances[-1].calls[-1]["comps"] == 4, (
        "a 0 (unset) display TextureNumComps must fall back to the image's "
        "component count -- a 0-component upload fails format resolution "
        "deterministically."
    )


def test_texture_build_returns_none_on_failed_upload(rep_module, monkeypatch):
    """A False CreateSeq3DFromRaw -> None (deferred retry), NOT a broken
    texture that the caller binds and the idempotency guard then pins."""
    rep = _texture_build_rep(rep_module, monkeypatch)
    _FakeTextureHelper.create_result = False
    texture = rep._create_distance_map_texture(_FakeImage3D(), 4)
    assert texture is None, (
        "a failed upload must not be handed to the caller -- binding it "
        "permanently wedges the resectogram (already-bound guard blocks "
        "every retry)."
    )


def test_texture_build_defers_until_window_initialized(rep_module, monkeypatch):
    """An unrealized render window -> None without attempting the upload."""
    rep = _texture_build_rep(rep_module, monkeypatch, initialized=False)
    texture = rep._create_distance_map_texture(_FakeImage3D(), 4)
    assert texture is None
    assert _FakeTextureHelper.instances == [] or not any(
        h.calls for h in _FakeTextureHelper.instances
    ), (
        "no upload may be attempted on a not-yet-realized window (empty "
        "texture-format table -> guaranteed noisy failure)."
    )
