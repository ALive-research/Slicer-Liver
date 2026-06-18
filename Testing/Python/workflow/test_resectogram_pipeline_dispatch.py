# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Workflow-layer registration + dispatch test for the T3 ResectogramPipeline.

Per ADR-0013 §1 there is exactly ONE Pipeline per display-node TYPE.  The
maintainer decision for T3 is KEYING = a dedicated display node: T3 adds a
new ``vtkMRMLResectogramDisplayNode`` and the ResectogramPipeline is a
standalone Pipeline keyed on THAT type — NOT on the shared
``vtkMRMLParametricSurfaceDisplayNode`` that the T2 Bezier 3D-surface
Pipeline owns.  ADR-0013 §5 for T3 is therefore:

* RegisterNodeClass(``vtkMRMLResectogramDisplayNode``) — NEW.
* the upstream LayerDM displayable-manager RegisterInDefaultViews() —
  already present (T2 wired it; idempotent).
* AddPipelineCreator keyed on ``vtkMRMLResectogramDisplayNode`` — the
  only new §5 wiring.

This test pins TWO specific invariants (ADR-0027 — the specific
invariant, not "some pipeline exists"):

1. **Dispatch fires for the new type.**  Adding a
   ``vtkMRMLResectogramDisplayNode`` to a scene with a LayerDM-aware 3D
   view causes the manager to instantiate a live ResectogramPipeline /
   bridge for it.
2. **No collision with the Bezier Pipeline.**  Adding a
   ``vtkMRMLParametricSurfaceDisplayNode`` must NOT produce a
   ResectogramPipeline, and adding a ``vtkMRMLResectogramDisplayNode``
   must NOT produce a Bezier-surface Pipeline.  Two creators keyed on
   two distinct display-node types do not cross-fire (ADR-0013 §1 —
   one Pipeline per display-node type).

CRITICAL — launched-harness-gated (issue #460).  This file
``pytest.importorskip("LayerDMLib")`` at module level: it executes only
inside a launched ``qSlicerApplication`` where the upstream LayerDM
extension AND the built LiverResectionsLib module paths are on the
process path.  In the bare pytest row (the default local + pre-commit
path) and in any environment lacking SlicerLayerDM on the launched
path, the WHOLE FILE SKIPS with the reason string below.  Per
``feedback_launched_pytest_harness_skips.md`` the green-but-skipping
trap is real here: this test's verdict is ONLY meaningful in the
``pytest_launched`` CI row.  Verify run-vs-skip in the CI log — a green
overall run that skipped this file has NOT exercised the dispatch.

References
----------
* ADR-0013 §1 — one Pipeline per display-node type.
* ADR-0013 §5 — the three registration calls; T3's NEW
  RegisterNodeClass + AddPipelineCreator keyed on
  ``vtkMRMLResectogramDisplayNode``.
* ADR-0027 — invariant-test-first; the specific invariant is
  type-keyed dispatch WITHOUT cross-fire, not mere pipeline existence.
* ADR-0013 §9 — the real-view fixture: the two dispatch tests consume
  the shared ``layerdm_threed_view`` fixture in ``Testing/Python/conftest.py``,
  which brings up a standalone ``qMRMLThreeDWidget`` hosting the upstream
  ``vtkMRMLLayerDisplayableManager`` and queries it via ``GetNodePipeline``.
* Mirrors the ``importorskip("LayerDMLib")`` gating used by the T2
  Bezier Pipeline tests under ``Testing/Python/unit/``.
"""

from __future__ import annotations

import pytest

# Module-level skip — runs only inside a launched Slicer process with the
# upstream LayerDM extension loaded AND LiverResectionsLib reachable.
# The reason string is intentionally explicit so run-vs-skip is greppable
# in the CI log (issue #460 green-but-skipping guard).
pytest.importorskip(
    "LayerDMLib",
    reason=(
        "ResectogramPipeline dispatch requires a launched qSlicerApplication "
        "with SlicerLayerDM + LiverResectionsLib on the process path; skipped "
        "in the bare pytest row.  Verdict is real only in the pytest_launched "
        "CI row (issue #460)."
    ),
)


def test_resectogram_display_node_registers():
    """``vtkMRMLResectogramDisplayNode`` is a registered MRML node class.

    Pins ADR-0013 §5 — T3's NEW ``RegisterNodeClass`` call.  The node
    must instantiate via the scene factory once LiverResections'
    ``setup()`` has run inside the launched app.
    """
    import slicer

    node = slicer.mrmlScene.CreateNodeByClass("vtkMRMLResectogramDisplayNode")
    assert node is not None, (
        "vtkMRMLResectogramDisplayNode did not instantiate from the scene "
        "factory — ADR-0013 §5 RegisterNodeClass for the new display node "
        "has not run (T3 not yet implemented)."
    )
    node.UnRegister(None)


def test_resectogram_creator_fires_for_its_display_node(layerdm_threed_view):
    """Adding a ``vtkMRMLResectogramDisplayNode`` builds a ResectogramPipeline.

    Pins ADR-0013 §5 — the ``AddPipelineCreator`` keyed on the new type
    produces a LIVE pipeline/bridge in the active view's pipeline set.
    """
    import slicer

    view, manager = layerdm_threed_view
    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLResectogramDisplayNode")

    # Query the LayerDM manager for the pipeline bound to ``display`` via the
    # ``GetNodePipeline`` accessor documented on vtkMRMLLayerDisplayableManager
    # as the test/debug pipeline lookup.  A live ResectogramPipeline means the
    # creator keyed on vtkMRMLResectogramDisplayNode fired (ADR-0013 §5).
    pipeline = manager.GetNodePipeline(display)
    assert pipeline is not None, (
        "No pipeline created for vtkMRMLResectogramDisplayNode — the T3 "
        "AddPipelineCreator (ADR-0013 §5) did not fire for the dedicated "
        "display-node type."
    )
    # The scripted ResectogramPipeline derives from
    # vtkMRMLLayerDMScriptedPipeline (a vtkMRMLLayerDMScriptedPipelineBridge).
    # GetNodePipeline returns the bridge; assert the bound Python object is a
    # ResectogramPipeline by its class name.
    assert type(pipeline).__name__ == "ResectogramPipeline", (
        "the pipeline bound to vtkMRMLResectogramDisplayNode is "
        f"{type(pipeline).__name__!r}, not ResectogramPipeline — the T3 "
        "creator did not build the dedicated pipeline (ADR-0013 §5)."
    )


def test_resectogram_creator_does_not_collide_with_bezier(layerdm_threed_view):
    """The two creators are keyed on disjoint display-node types.

    Pins ADR-0013 §1 — one Pipeline per display-node type, NO cross-fire:

    * a ``vtkMRMLParametricSurfaceDisplayNode`` must NOT yield a
      ResectogramPipeline (the Bezier 3D-surface Pipeline owns it), and
    * a ``vtkMRMLResectogramDisplayNode`` must NOT yield a
      Bezier-surface Pipeline.

    This is the load-bearing assertion behind the maintainer's KEYING =
    dedicated-display-node decision: keying the ResectogramPipeline on
    the SHARED ``vtkMRMLParametricSurfaceDisplayNode`` would violate
    ADR-0013 §1 (two creators on one type).
    """
    import slicer

    view, manager = layerdm_threed_view

    parametric = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLParametricSurfaceDisplayNode"
    )
    resectogram = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLResectogramDisplayNode"
    )

    # Resolve the pipeline bound to each display node via the DM's
    # GetNodePipeline accessor and assert the type mapping is disjoint.
    parametric_pipeline = manager.GetNodePipeline(parametric)
    resectogram_pipeline = manager.GetNodePipeline(resectogram)

    assert type(parametric_pipeline).__name__ != "ResectogramPipeline", (
        "vtkMRMLParametricSurfaceDisplayNode wrongly produced a "
        "ResectogramPipeline — the creators cross-fire (ADR-0013 §1 "
        "violation)."
    )
    assert type(resectogram_pipeline).__name__ != "LiverBezierSurfacePipeline", (
        "vtkMRMLResectogramDisplayNode wrongly produced a Bezier-surface "
        "Pipeline — the creators cross-fire (ADR-0013 §1 violation)."
    )


# --------------------------------------------------------------------------- #
# T3-g1 keystone invariants — the dedicated resectogram view (ADR-0023
# §Stage-4) is the ONLY view the ResectogramPipeline fires into; the shared
# anatomy 3D view stays clear (ADR-0013 §1 disjoint keying).
#
# RED-by-design (ADR-0027): both tests fail today because
# ``registerResectogramPipelineCreator().tryCreate`` gates only on
# ``isinstance(viewNode, vtkMRMLViewNode)`` (ResectogramPipeline.py
# ~L399-409) — so the creator fires for EVERY 3D view, dispatching the
# flattened strip into the shared anatomy renderer.  They go GREEN once the
# T3-g1 implementer (a) lands the dedicated singleton view (Hyperprobe
# pattern, ``SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)``) and (b)
# tightens ``tryCreate`` to fire ONLY for the view carrying that tag.
# --------------------------------------------------------------------------- #


def _first_renderer(view_widget):
    """Return the live ``vtkRenderer`` of the view widget's render window.

    ``qMRMLThreeDView.renderer()`` is C++-only (not PythonQt-wrapped); reach
    the renderer through the render-window's renderer collection, which is
    plain VTK and fully wrapped.  Same accessor the resectogram arena
    (``test_resectogram_arena.py``) and ``capture_baseline.py`` use.
    """
    return view_widget.threeDView().renderWindow().GetRenderers().GetFirstRenderer()


def _renderer_owns_actor(renderer, actor) -> bool:
    """Whether ``actor`` is in ``renderer``'s actor collection.

    Walks ``GetActors()`` by VTK-object identity (``IsSameObject``) rather
    than Python ``is`` — PythonQt/VTK can hand back distinct Python wrappers
    around the same C++ ``vtkActor``.
    """
    if renderer is None or actor is None:
        return False
    actors = renderer.GetActors()
    actors.InitTraversal()
    for _ in range(actors.GetNumberOfItems()):
        candidate = actors.GetNextActor()
        if candidate is not None and candidate.IsSameObject(actor):
            return True
    return False


def test_creator_fires_only_in_dedicated_view(layerdm_resectogram_view):
    """The ResectogramPipeline dispatches into the dedicated view, NOT the shared one.

    Pins ADR-0013 §1 (disjoint keying — one Pipeline per renderable target)
    and ADR-0023 §Stage-4 (the resectogram is the one custom Slicer layout
    v2.0 ships; it must not bleed into the shared 3D anatomy view).  With a
    single ``vtkMRMLResectogramDisplayNode`` in the scene and TWO views
    present — a shared anatomy ``vtkMRMLViewNode`` (no resectogram tag) and a
    dedicated view carrying ``RESECTOGRAM_VIEW_SINGLETON_TAG`` — the LayerDM
    DM yields a ``ResectogramPipeline`` ON THE DEDICATED VIEW and yields none
    (or anything but a ResectogramPipeline) on the shared anatomy view.

    RED-by-design (ADR-0027): the current ``tryCreate`` fires for every
    ``vtkMRMLViewNode``, so the shared anatomy view ALSO gets a
    ResectogramPipeline.  GREEN once T3-g1 tightens the creator to gate on
    the dedicated view's singleton tag.
    """
    import slicer

    shared_widget, shared_manager = layerdm_resectogram_view["shared"]
    dedicated_widget, dedicated_manager = layerdm_resectogram_view["dedicated"]

    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLResectogramDisplayNode")
    shared_widget.threeDView().forceRender()
    dedicated_widget.threeDView().forceRender()

    dedicated_pipeline = dedicated_manager.GetNodePipeline(display)
    shared_pipeline = shared_manager.GetNodePipeline(display)

    assert (
        dedicated_pipeline is not None
        and type(dedicated_pipeline).__name__ == "ResectogramPipeline"
    ), (
        "the dedicated resectogram view (singleton tag "
        f"{layerdm_resectogram_view['tag']!r}) did not get a "
        "ResectogramPipeline — T3-g1's creator must fire for the dedicated "
        "view (ADR-0023 §Stage-4)."
    )
    assert type(shared_pipeline).__name__ != "ResectogramPipeline", (
        "the SHARED anatomy view wrongly got a ResectogramPipeline — the "
        "creator still fires for every 3D view (ResectogramPipeline.py "
        "tryCreate gates only on vtkMRMLViewNode).  T3-g1 must tighten it to "
        "the dedicated view's singleton tag (ADR-0013 §1 disjoint keying)."
    )


def test_strip_actor_absent_from_shared_renderer(layerdm_resectogram_view):
    """The flattened-surface strip actor lives in the dedicated renderer ONLY.

    Pins ADR-0023 §Stage-4 at the renderer level: the
    ``FlattenedSurfaceRepresentation``'s strip actor
    (``GetResectionActor2D``) must be present in the dedicated view's
    renderer and ABSENT from the shared anatomy view's renderer collection.
    This is the visible consequence of the dispatch invariant — the strip
    rendering into the shared anatomy renderer is the bug T3-g1 fixes.

    RED-by-design (ADR-0027): today the creator fires for the shared view too,
    so its ResectogramPipeline attaches the strip actor to the shared
    renderer.  GREEN once T3-g1 tightens the creator.
    """
    import slicer

    shared_widget, shared_manager = layerdm_resectogram_view["shared"]
    dedicated_widget, dedicated_manager = layerdm_resectogram_view["dedicated"]

    display = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLResectogramDisplayNode")
    shared_widget.threeDView().forceRender()
    dedicated_widget.threeDView().forceRender()

    dedicated_pipeline = dedicated_manager.GetNodePipeline(display)
    assert (
        dedicated_pipeline is not None
        and type(dedicated_pipeline).__name__ == "ResectogramPipeline"
    ), (
        "no ResectogramPipeline on the dedicated view — cannot locate the "
        "strip actor (precondition for the renderer-ownership invariant)."
    )

    flattened = dedicated_pipeline.GetFlattenedSurfaceRepresentation()
    assert flattened is not None, (
        "the dedicated ResectogramPipeline has no FlattenedSurfaceRepresentation "
        "— the strip assembly (ADR-0013 §6) is not built."
    )
    strip_actor = flattened.GetResectionActor2D()
    assert strip_actor is not None, (
        "the FlattenedSurfaceRepresentation exposes no 2D strip actor "
        "(GetResectionActor2D) — nothing to locate in a renderer."
    )

    dedicated_renderer = _first_renderer(dedicated_widget)
    shared_renderer = _first_renderer(shared_widget)

    assert _renderer_owns_actor(dedicated_renderer, strip_actor), (
        "the resectogram strip actor is NOT in the dedicated view's renderer "
        "— the dedicated Pipeline did not attach it (ADR-0023 §Stage-4)."
    )
    assert not _renderer_owns_actor(shared_renderer, strip_actor), (
        "the resectogram strip actor is present in the SHARED anatomy "
        "renderer — the flattened strip is bleeding into the shared 3D view "
        "(the T3-g1 bug).  T3-g1 must tighten tryCreate so the creator never "
        "fires for the shared view (ADR-0013 §1; ADR-0023 §Stage-4)."
    )
