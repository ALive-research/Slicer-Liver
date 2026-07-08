# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Pipeline tests for ``LiverBezierSurfacePipeline`` — T2.6-LayerDM.

Per ADR-0013 §5 the Pipeline now hard-requires the upstream LayerDM
library's ``vtkMRMLLayerDMScriptedPipeline`` base.  These tests
therefore ``pytest.importorskip("LayerDMLib")`` at module level —
they execute only inside a Slicer process where the upstream
extension has loaded.  In pure-Python pytest runs (the default
local + pre-commit path) the whole file is skipped.

The tests below exercise the LayerDM lifecycle the manager would
invoke:

1. Construct the Pipeline with no args.
2. ``SetDisplayNode(displayNode)`` — derives the data node via
   ``displayNode.GetDisplayableNode()``, attaches observers.
3. ``UpdatePipeline()`` — drives the ``(state, initMode)`` dispatch.
4. ``cleanup()`` — detaches observers.

The previous standalone-path tests (kwarg-based constructor against
stub nodes) are retired with the project-local Pipeline stand-in
that pre-dated T2.6-LayerDM.  Dispatch-table coverage moves to the
workflow-layer test that drives the Pipeline through a real LayerDM
displayable manager (``Testing/Python/workflow/``).

References
----------
* ADR-0013 §5 — three registration calls + Pipeline lifecycle.
* ADR-0008 §2 — unit-layer testing discipline (revised to allow
  ``importorskip`` gating once the base library lands).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# Module-level skip — runs only inside a Slicer process with the
# upstream LayerDM extension loaded.
pytest.importorskip("LayerDMLib")

# --------------------------------------------------------------------------- #
# Repo geometry — Pipeline lives at
# ``LiverResections/LiverResectionsLib/LiverBezierSurfacePipeline.py``
# per the ``<Module>Lib`` install convention adopted at T2.6-LayerDM.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


@pytest.fixture
def pipeline_module():
    """Import the Pipeline module under test."""
    import LiverBezierSurfacePipeline as mod

    return mod


@pytest.fixture
def bezier_nodes():
    """Construct a ``vtkMRMLBezierSurface{,Display}Node`` pair.

    Wires them via ``data.AddAndObserveDisplayNodeID(display.GetID())``
    so the Pipeline's ``SetDisplayNode`` override can read the data
    node off ``GetDisplayableNode()``.
    """
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLParametricSurfaceDisplayNode")
    data.AddAndObserveDisplayNodeID(display.GetID())
    try:
        yield data, display
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


def test_pipeline_constructs_no_arg(pipeline_module):
    """The LayerDM-base constructor takes no positional arguments."""
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    assert pipeline.GetDataNode() is None
    assert pipeline.GetCurrentRepresentationName() is None
    pipeline.cleanup()


def test_pipeline_set_display_node_derives_data_node(
    pipeline_module, bezier_nodes
):
    """``SetDisplayNode`` reads ``GetDisplayableNode`` for the data node."""
    data, display = bezier_nodes
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    pipeline.SetDisplayNode(display)
    assert pipeline.GetDataNode() is data
    pipeline.cleanup()


def test_pipeline_update_dispatches_state(pipeline_module, bezier_nodes):
    """``UpdatePipeline`` activates the Representation matching the state."""
    data, display = bezier_nodes
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    pipeline.SetDisplayNode(display)

    # The Bezier surface node defaults to (state=Init,
    # mode=SlicingPlane) per the C++ enum default.
    pipeline.UpdatePipeline()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_SLICING_PLANE_INIT
    )

    # Transition to (state=Planning) → BezierPlanning slot wins.
    data.SetState(pipeline_module.STATE_PLANNING)
    pipeline.UpdatePipeline()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_BEZIER_PLANNING
    )

    # ADR-0019: transition to (state=Confirmed) → Confirmed slot wins.
    data.SetState(pipeline_module.STATE_CONFIRMED)
    pipeline.UpdatePipeline()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_CONFIRMED
    )

    # Round-trip back to Planning re-activates BezierPlanning.
    data.SetState(pipeline_module.STATE_PLANNING)
    pipeline.UpdatePipeline()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_BEZIER_PLANNING
    )

    pipeline.cleanup()


def test_pipeline_update_is_idempotent(pipeline_module, bezier_nodes):
    """A second ``UpdatePipeline`` with no node mutation is a no-op."""
    data, display = bezier_nodes
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    pipeline.SetDisplayNode(display)
    data.SetState(pipeline_module.STATE_PLANNING)

    pipeline.UpdatePipeline()
    first = pipeline.GetUpdateCount()
    pipeline.UpdatePipeline()
    second = pipeline.GetUpdateCount()
    assert second == first, "UpdatePipeline must be idempotent on no-change"

    pipeline.cleanup()


def test_pipeline_adopts_late_bound_displayable(pipeline_module):
    """A data node linked AFTER SetDisplayNode is adopted on the next update.

    The production creation ordering (``CreateDefaultDisplayNodes``) adds the
    display node to the scene -- firing the LayerDM creator and this
    Pipeline's ``SetDisplayNode`` -- BEFORE ``SetAndObserveDisplayNodeID``
    links it to the carrier.  ``GetDisplayableNode()`` is None at that
    moment; without late re-derivation the Pipeline stays permanently
    data-node-less (no observers, no dispatch, default unit patch renders).
    ``UpdatePipeline`` must re-derive and adopt the displayable once the
    link exists.
    """
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLParametricSurfaceDisplayNode")
    try:
        pipeline = pipeline_module.LiverBezierSurfacePipeline()
        # Production ordering: display handed over BEFORE the carrier link.
        pipeline.SetDisplayNode(display)
        assert pipeline.GetDataNode() is None, "no link yet -- nothing to derive"

        data.AddAndObserveDisplayNodeID(display.GetID())
        pipeline.UpdatePipeline()
        assert pipeline.GetDataNode() is data, (
            "UpdatePipeline must re-derive the data node once the display "
            "node is linked to its displayable -- otherwise the Pipeline "
            "created during CreateDefaultDisplayNodes never dispatches."
        )
        pipeline.cleanup()
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


def test_pipeline_reference_added_hook_adopts_displayable(pipeline_module):
    """``OnReferenceToDisplayNodeAdded`` adopts the referencing displayable.

    This is the LayerDM manager's designed late-binding notification: its
    node-reference observer calls the hook with ``fromNode`` == the
    displayable that just referenced our display node.  The Pipeline must
    adopt it as the data node and re-dispatch -- this is the PRODUCTION path
    that revives a Pipeline created during ``CreateDefaultDisplayNodes``
    (before the display<->displayable link existed).
    """
    import slicer

    scene = slicer.mrmlScene
    data = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceNode")
    display = scene.AddNewNodeByClass("vtkMRMLParametricSurfaceDisplayNode")
    try:
        pipeline = pipeline_module.LiverBezierSurfacePipeline()
        pipeline.SetDisplayNode(display)
        assert pipeline.GetDataNode() is None

        data.AddAndObserveDisplayNodeID(display.GetID())
        pipeline.OnReferenceToDisplayNodeAdded(data, "display")
        assert pipeline.GetDataNode() is data, (
            "the reference-added hook must adopt the referencing displayable "
            "as the data node (LayerDM late binding)."
        )
        pipeline.cleanup()
    finally:
        scene.RemoveNode(display)
        scene.RemoveNode(data)


class _FakeRenderer:
    """Records AddActor/RemoveActor so attach state is observable."""

    def __init__(self):
        self.actors = []

    def AddActor(self, actor):  # noqa: N802 - VTK verb
        if actor not in self.actors:
            self.actors.append(actor)

    def RemoveActor(self, actor):  # noqa: N802 - VTK verb
        if actor in self.actors:
            self.actors.remove(actor)


def test_pipeline_hides_inactive_representation_on_state_switch(
    pipeline_module, bezier_nodes, monkeypatch
):
    """Init -> Planning must DETACH the init representation's actors.

    All four Representations are constructed against the renderer, so the
    SlicingPlaneInit plane + marker spheres stayed attached (and visible at
    the origin) after the carrier switched to Planning -- the stray 'second
    resection with a control point' seen in the 3D view.  Dispatch must leave
    only the ACTIVE representation's actors on the renderer.
    """
    data, display = bezier_nodes
    fake = _FakeRenderer()
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: fake)
    pipeline.SetDisplayNode(display)

    # Init state (default): dispatch attaches the init representation.
    pipeline.UpdatePipeline()
    init_rep = pipeline.GetRepresentation("SlicingPlaneInit")
    planning_rep = pipeline.GetRepresentation("BezierPlanning")
    assert init_rep is not None and planning_rep is not None

    data.SetState(1)  # Planning
    pipeline.UpdatePipeline()

    init_renderer = getattr(init_rep, "_renderer", "missing")
    assert init_renderer is None, (
        "the inactive SlicingPlaneInit representation must be detached from "
        "the renderer after the Init -> Planning switch (its plane + marker "
        "spheres otherwise linger as a stray second surface)."
    )
    planning_renderer = getattr(planning_rep, "_renderer", "missing")
    assert planning_renderer is fake, (
        "the ACTIVE BezierPlanning representation must be attached to the "
        "pipeline's renderer."
    )
    pipeline.cleanup()


def test_geometry_edit_requests_render(pipeline_module, bezier_nodes):
    """A control-point edit must request a render; MTime churn must not.

    The observer callback re-runs ``UpdatePipeline`` but historically never
    requested a render, so a Planning drag mutated the surface polydata while
    the 3D view stayed frozen until an unrelated render (camera orbit)
    repainted it.  The request is gated on the control-point GEOMETRY digest
    (the ResectogramPipeline pattern): a render-induced ``Modified`` at fixed
    geometry must NOT re-request (render feedback loop).
    """
    data, display = bezier_nodes
    pipeline = pipeline_module.LiverBezierSurfacePipeline()
    pipeline.SetDisplayNode(display)
    data.SetState(1)  # Planning

    renders = []
    pipeline.RequestRender = lambda: renders.append(1)

    data.SetControlPoint(0, 0, 1.0, 2.0, 3.0)
    assert renders, (
        "a control-point edit must request a render -- without it the 3D "
        "view repaints only on the next unrelated render (frozen drag)."
    )

    before = len(renders)
    data.Modified()  # no geometry change -- render-churn signature
    assert len(renders) == before, (
        "a Modified at fixed geometry must not re-request a render "
        "(the render feedback-loop guard)."
    )
    pipeline.cleanup()


def test_locator_pick_requests_render(pipeline_module, bezier_nodes):
    """A locator picked-point write must repaint the surface marker.

    The render-request gate keys on the control-point geometry digest,
    which a locator pick does not change -- without folding the picked
    position into the key, the uLocatorPosition uniform updates but the
    view repaints only on the next unrelated render (invisible marker).
    A Modified at an unchanged pick must still not re-request (loop guard).
    """
    import slicer

    data, display = bezier_nodes
    scene = slicer.mrmlScene
    locator = scene.AddNewNodeByClass("vtkMRMLLocatorNode")
    try:
        pipeline = pipeline_module.LiverBezierSurfacePipeline()
        pipeline.SetDisplayNode(display)
        data.SetState(1)  # Planning
        pipeline.UpdatePipeline()  # resolves + observes the locator

        renders = []
        pipeline.RequestRender = lambda: renders.append(1)

        locator.SetPickedPositionWorld(10.0, 20.0, 30.0)
        assert renders, (
            "a locator pick must request a render -- the marker uniform "
            "otherwise repaints only on the next unrelated render."
        )
        before = len(renders)
        locator.Modified()  # unchanged pick -- render-churn signature
        assert len(renders) == before, (
            "a Modified at an unchanged pick must not re-request (loop guard)"
        )
        pipeline.cleanup()
    finally:
        scene.RemoveNode(locator)
