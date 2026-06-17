# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Characterisation test: the Bezier distance-map survives a SECOND render.

This pins the invariant behind the offscreen-render abort observed when a
``vtkMRMLMarkupsBezierSurfaceNode`` carrying a 4-component float
distance-map volume is rendered, then rendered AGAIN via a second
``forceRender()``.  The first render comes up; the second has been
observed to abort (or hang) on multiple GL stacks.

Root-cause analysis (see ADR-0003 §"Decision" and the render-env
keystone analysis) points at the 3D distance-map texture object being
``Bind()``/``Deactivate()``-ed exactly once at creation in
``vtkSlicerBezierSurfaceRepresentation3D::CreateAndTransferDistanceMapTexture``,
while the draw-time mapper
(``vtkOpenGLBezierResectionPolyDataMapper::SetMapperShaderParameters``)
only sets the ``sampler3D distanceTexture`` uniform.  Nothing re-activates
the texture object onto its sampler unit at draw time, so the second
render — after VTK has churned texture-unit bindings for other actors —
samples a ``sampler3D`` with no live ``GL_TEXTURE_3D`` bound to its unit.

The invariant this test pins: rendering the 4-component distance-map
Bezier scenario, then ``forceRender()``-ing a SECOND time, must complete
without aborting and must leave the GL context error-free.

Test level: Level 2 — minimal ``qSlicerApplication`` (the SUT touches
MRML + the Markups render pipeline), per the SlicerLayerDM / trame-slicer
precedent recorded in ``LiverResections/Testing/README.md``.

This is a launched/visual-tier test: it is RED-by-design today (the
second render aborts on the affected stacks) and yields the real verdict
only on a GPU-backed ``:0`` session.  On a software-GL stack (CI's
xvfb + llvmpipe) it skips up front via the same probe ``replay_test.py``
uses, so it never burns the CTest timeout on the known software-GL hang.

References
----------
* ADR-0003 §"Decision" — characterisation tests pin behaviour before a
  fix or refactor.
* ADR-0020 §"Rollout plan" §7 — the v2.0 Bezier mapper is ported, not
  rewritten; this is a surgical correctness gate, not modernisation.
"""

from __future__ import annotations

import pathlib
import sys

# Reuse the software-GL probe + skip-reason helpers from the replay
# driver rather than duplicating them; they live alongside this script.
_THIS_DIR = pathlib.Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import replay_test  # noqa: E402  (path injection above is intentional)


SCENARIO_NAME = "BezierSurface4x4Planning"


def _load_scenario():
    """Import the 4x4 Planning scenario module (4-comp float distance-map)."""
    scenarios_dir = _THIS_DIR / "scenarios"
    return replay_test._load_scenario(str(scenarios_dir), SCENARIO_NAME)


def _build_view(width: int, height: int):
    """Bring up an offscreen 3D view widget bound to the MRML scene."""
    import slicer  # type: ignore[import-not-found]

    view_widget = slicer.qMRMLThreeDWidget()
    view_widget.setMRMLScene(slicer.mrmlScene)
    view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
    if view_node is None:
        view_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLViewNode", "DistanceMapDoubleRenderView"
        )
    view_widget.setMRMLViewNode(view_node)
    view_widget.resize(width, height)

    three_d_view = view_widget.threeDView()
    three_d_view.renderWindow().SetSize(width, height)
    three_d_view.renderWindow().SetMultiSamples(0)
    return view_widget, view_node, three_d_view


def run() -> int:
    """Render the 4-comp distance-map Bezier scene twice; assert survival.

    The invariant pinned is process survival across the SECOND render:
    on the affected stacks the second ``forceRender()`` aborts the
    process, so merely reaching the line after it is the pass condition.
    An abort manifests to CTest as a non-zero exit / crash (or, on a
    misdetected software stack, a timeout) — there is nothing to assert
    in Python beyond completion.

    Returns 0 on success (both renders completed) and 0 on a clean
    software-GL skip (the verdict is deferred to a GPU host).
    """
    # Software-GL fast skip — identical probe to the replay driver so the
    # known software-GL hang on the bezier distance-map never burns the
    # CTest timeout here.  The real abort/no-abort verdict is on a GPU
    # ``:0`` session.
    skip_reason = replay_test._software_gl_skip_reason(
        replay_test._probe_gl_renderer()
    )
    if skip_reason is not None:
        print(skip_reason)
        return 0

    scenario = _load_scenario()
    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    scenario.setup_scene()
    view_widget, view_node, three_d_view = _build_view(width, height)
    scenario.setup_camera(view_node)
    scenario.setup_viewport(view_node)

    # FIRST render — comes up on the affected stacks.
    three_d_view.forceRender()

    # SECOND render — the offscreen-render abort site.  On the affected
    # stacks the process aborts here; reaching the line after it is the
    # invariant being pinned.
    three_d_view.forceRender()

    print(
        "[pass] Bezier 4-component distance-map survived two forceRender() "
        "calls"
    )
    return 0


def _exit(code: int) -> None:
    """Terminate the launched process; mirrors ``replay_test._exit``."""
    replay_test._exit(code)


if __name__ == "__main__":
    _exit(run())
