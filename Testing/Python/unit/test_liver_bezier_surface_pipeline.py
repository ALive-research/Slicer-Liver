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
    display = scene.AddNewNodeByClass("vtkMRMLBezierSurfaceDisplayNode")
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
