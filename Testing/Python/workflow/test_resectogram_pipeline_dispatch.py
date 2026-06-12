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


@pytest.fixture
def layerdm_threed_view():
    """Yield a LayerDM-aware 3D view + its displayable manager.

    TODO(liver-implementer): build the minimal launched-app 3D view that
    hosts a ``vtkMRMLLayerDMDisplayableManager`` (mirror the T2
    real-view fixture delivered with the Bezier Pipeline per ADR-0013
    §9).  Until that fixture lands the dispatch tests below skip with a
    clear reason rather than silently passing.
    """
    pytest.skip(
        "Invariant not yet implemented: launched LayerDM 3D-view fixture for "
        "ResectogramPipeline dispatch is not yet provided (ADR-0013 §9 "
        "real-view fixture)."
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

    # TODO(liver-implementer): query the LayerDM manager for the pipeline
    # bound to ``display`` and assert it is a ResectogramPipeline instance
    # (the creator keyed on vtkMRMLResectogramDisplayNode fired).
    pipeline = manager.GetPipelineForDisplayNode(display)
    assert pipeline is not None, (
        "No pipeline created for vtkMRMLResectogramDisplayNode — the T3 "
        "AddPipelineCreator (ADR-0013 §5) has not been wired."
    )
    assert type(pipeline).__name__ == "ResectogramPipeline"


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

    # TODO(liver-implementer): resolve the pipeline bound to each display
    # node and assert the type mapping is disjoint.
    parametric_pipeline = manager.GetPipelineForDisplayNode(parametric)
    resectogram_pipeline = manager.GetPipelineForDisplayNode(resectogram)

    assert type(parametric_pipeline).__name__ != "ResectogramPipeline", (
        "vtkMRMLParametricSurfaceDisplayNode wrongly produced a "
        "ResectogramPipeline — the creators cross-fire (ADR-0013 §1 "
        "violation)."
    )
    assert type(resectogram_pipeline).__name__ != "LiverBezierSurfacePipeline", (
        "vtkMRMLResectogramDisplayNode wrongly produced a Bezier-surface "
        "Pipeline — the creators cross-fire (ADR-0013 §1 violation)."
    )
