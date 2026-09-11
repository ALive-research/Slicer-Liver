# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The frame highlight survives the gesture that owns it.

The border lights while the frame is hovered or held.  A drag translates
the control grid, which fires Modified, which reconciles the pipeline --
and the reconcile restores the display node's own edge colour.  If the
highlight is not re-asserted after that restore, the gesture repaints
away its own cue: the border lights on grab and goes dark the instant the
drag does any work.

That is exactly what the eyeball caught, and it is invisible to a test
that only checks the colour right after the grab.  So the sequence here
is grab -> RECONCILE -> assert, not grab -> assert.

HARNESS: launched Slicer.  The pipeline derives from a LayerDMLib base
reachable only inside a launched Slicer, so a bare run SKIPS CLEANLY
(ADR-0027).
"""

from __future__ import annotations

import pytest


def _pipeline_module_or_skip():
    """The MODULE, not the class.

    ``from LiverResectionsLib import ControlPolygonPipeline`` yields the
    CLASS: the package __init__ does ``from .ControlPolygonPipeline import
    ControlPolygonPipeline``, rebinding the module attribute to the class.
    importlib reaches the module itself, which is what the constants below
    live on.
    """
    import importlib

    try:
        return importlib.import_module("LiverResectionsLib.ControlPolygonPipeline")
    except Exception as exc:
        pytest.skip(f"ControlPolygonPipeline not importable ({exc!r}) -- ADR-0027.")


def _display_node_or_skip(slicer):
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLControlPolygonDisplayNode")
    if node is None or not hasattr(node, "SetGrabbedGroup"):
        pytest.skip("control-polygon display node lacks group state (ADR-0027).")
    return node


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _pipeline_with_display(module, slicer):
    try:
        pipeline = module.ControlPolygonPipeline()
    except Exception as exc:
        pytest.skip(f"pipeline not constructible ({exc!r}) -- ADR-0027.")
    display = _display_node_or_skip(slicer)
    display.SetEdgeColor(0.2, 0.2, 0.9)  # a resting colour unlike the cues
    pipeline.SetDisplayNode(display)
    return pipeline, display


def test_grab_highlight_survives_a_reconcile():
    """The bug the eyeball found: a drag repainted away its own highlight."""
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    pipeline, display = _pipeline_with_display(module, slicer)

    display.SetGrabbedGroup(display.GroupFrame)
    pipeline._apply_frame_style()
    held = pipeline._edges_actor.GetProperty().GetColor()
    assert held == pytest.approx(module.FRAME_GRAB_COLOR, abs=1e-3)

    # The reconcile a drag triggers: it restores the display node's own
    # edge colour and must NOT leave it there while the frame is held.
    pipeline._apply_display_node()

    after = pipeline._edges_actor.GetProperty().GetColor()
    assert after == pytest.approx(module.FRAME_GRAB_COLOR, abs=1e-3), (
        "The reconcile restored the resting edge colour over the grab "
        "highlight.  A drag reconciles on every move, so the border goes "
        "dark the moment the gesture does any work."
    )


def test_hover_highlight_survives_a_reconcile():
    """Same guarantee for the hover cue."""
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    pipeline, display = _pipeline_with_display(module, slicer)

    display.SetHoveredGroup(display.GroupFrame)
    pipeline._apply_frame_style()
    pipeline._apply_display_node()

    after = pipeline._edges_actor.GetProperty().GetColor()
    assert after == pytest.approx(module.FRAME_HOVER_COLOR, abs=1e-3)


def test_resting_polygon_keeps_the_display_node_colour():
    """With no group cue the border is the display node's own colour.

    Guards the other direction: a highlight that never cleared would be
    just as wrong as one that never held.
    """
    slicer = _slicer_or_skip()
    module = _pipeline_module_or_skip()
    pipeline, display = _pipeline_with_display(module, slicer)

    display.SetHoveredGroup(display.GroupNone)
    display.SetGrabbedGroup(display.GroupNone)
    pipeline._apply_display_node()

    after = pipeline._edges_actor.GetProperty().GetColor()
    assert after == pytest.approx((0.2, 0.2, 0.9), abs=1e-3)
