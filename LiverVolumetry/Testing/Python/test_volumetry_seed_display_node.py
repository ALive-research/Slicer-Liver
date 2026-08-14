# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the volumetry seed display node is DATA-ONLY.

``volumetry-seeds-layerdm-plan.md`` §3a adds a module-local
``vtkMRMLVolumetrySeedsDisplayNode`` following the ADR-0025/0033 data-only
display-node shape: it CARRIES the interaction state (arm / hover / grab),
a ``pickSurface`` reference, and the transient adhering point -- but it
does NO rendering itself (the LayerDM Pipeline renders; ADR-0013 §5 forbids
a per-module displayable manager).  The interaction state living on the
SHARED display node -- not a Python pipeline instance -- is the hard-won
LayerDM lesson (``feedback_layerdm_state_on_display_node``): the base's
``PointPlacementState`` accessors read/write it here.

This file pins the data-only contract:

* the display node HOLDS arm / hover / grab state + a ``pickSurface`` node
  reference + a transient point, all read-back-able;
* the display node does NOT expose rendering machinery (no actors, no
  mapper, no displayable-manager class of its own) -- an absence pin with a
  credible creep-in path (the v1 markups display node DID render), not a
  colour-of-the-sky absence (``feedback_no_colour_of_the_sky_tests``).

HARNESS: launched Slicer.  ``vtkMRMLVolumetrySeedsDisplayNode`` is a
WRAPPED C++ node reachable only inside a launched Slicer with the module
loaded (the wrapped-class-namespace rule); a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` so every test
SKIPS CLEANLY.

The SUT does not exist yet.  Per ADR-0027 red->skip the
``AddNewNodeByClass``-returns-None + ``hasattr`` guards skip-pend; the
skips lift at the implementation commit.

References
----------
* ADR-0025 -- locator architecture / the data-only display-node shape +
  reslice.
* ADR-0033 -- the control-polygon display aspect (arm/hover/grab on the
  display node, hover discipline).
* ADR-0013 §5 -- no per-module displayable manager (the LayerDM Pipeline
  renders).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/MRML/vtkMRMLTerritoriesHighlightDisplayNode.h -- the
  data-only display node this mirrors.
"""

from __future__ import annotations

import pytest

DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"
SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"

# PROPOSED interaction-state surface (sharpen at landing against the
# territory highlight display node + the shared PointPlacementState keys).
ARMED_ATTR = "LiverVolumetry.Armed"
HOVER_ATTR = "LiverVolumetry.Hover"
GRAB_ATTR = "LiverVolumetry.Grab"
PICK_SURFACE_ROLE = "LiverVolumetry.pickSurface"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_display_or_skip(slicer, name="VolumetrySeedsDisplayTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, name)
    if node is None:
        pytest.skip(
            f"{DISPLAY_NODE_CLASS} not registered -- the ADR-0038-amendment "
            "volumetry seed display node (plan §3a) has not landed (ADR-0027)."
        )
    return node


def test_display_node_holds_arm_hover_grab_state():
    """The display node carries arm / hover / grab interaction state.

    ADR-0033: the arm/hover/grab state lives on the SHARED display node, not
    a pipeline instance (``feedback_layerdm_state_on_display_node``).  The
    accessors round-trip via SetAttribute/GetAttribute (the generic
    PointPlacementState channel).
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)

    node.SetAttribute(ARMED_ATTR, "1")
    node.SetAttribute(HOVER_ATTR, "2")
    node.SetAttribute(GRAB_ATTR, "2")

    assert node.GetAttribute(ARMED_ATTR) == "1"
    assert node.GetAttribute(HOVER_ATTR) == "2"
    assert node.GetAttribute(GRAB_ATTR) == "2"


def test_display_node_holds_pick_surface_reference():
    """The display node carries a ``pickSurface`` node reference.

    ADR-0025: the display node references the surface the pick resolves
    against (for volumetry, the region being seeded), so the base can
    re-resolve the pick from the node.  A typed node-reference role, not an
    instance field.
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    surface = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "PickSurface")

    node.SetNodeReferenceID(PICK_SURFACE_ROLE, surface.GetID())

    assert node.GetNodeReference(PICK_SURFACE_ROLE) is surface


def test_display_node_holds_transient_adhering_point():
    """The display node carries the transient adhering point (hover preview).

    ADR-0033: the transient (not-yet-committed) point under the cursor rides
    the display node so the Pipeline can render the preview without a
    carrier mutation.  Skip-pend on the accessor's absence (ADR-0027).
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    if not hasattr(node, "SetTransientPoint") or not hasattr(node, "GetTransientPoint"):
        pytest.skip(
            f"{DISPLAY_NODE_CLASS} has no transient-point accessor -- the "
            "ADR-0033 adhering-preview slot has not landed (ADR-0027)."
        )

    node.SetTransientPoint(1.0, 2.0, 3.0)
    assert tuple(node.GetTransientPoint()) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9)


def test_display_node_holds_transient_highlight_seed_id():
    """The display node carries the highlighted seed's STABLE ID, transiently.

    The stripes highlight rides a C++ member (``HighlightSeedID``) mirroring
    ``TransientPoint`` -- NOT a node attribute, because ``SetAttribute``
    values serialize into the scene XML and a saved highlight reloads as
    frozen orphan stripes no widget owns.  Empty string == no highlight.
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    if not hasattr(node, "SetHighlightSeedID"):
        pytest.skip(
            f"{DISPLAY_NODE_CLASS} has no SetHighlightSeedID -- the transient "
            "highlight slot has not landed (ADR-0027)."
        )

    assert node.GetHighlightSeedID() == "", "default is no highlight."

    node.SetHighlightSeedID("seed_7")
    assert node.GetHighlightSeedID() == "seed_7"

    node.SetHighlightSeedID("")
    assert node.GetHighlightSeedID() == "", "empty clears the highlight."


def test_highlight_seed_id_fires_modified_on_change_only():
    """Setting the highlight fires ModifiedEvent (the pipelines' raise/clear
    tick); re-publishing the same value must NOT churn the observers."""
    import vtk

    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    if not hasattr(node, "SetHighlightSeedID"):
        pytest.skip(f"{DISPLAY_NODE_CLASS} has no SetHighlightSeedID (ADR-0027).")

    fired = []
    tag = node.AddObserver(vtk.vtkCommand.ModifiedEvent, lambda c, e: fired.append(1))
    try:
        node.SetHighlightSeedID("seed_1")
        assert len(fired) == 1, "a highlight change must fire ModifiedEvent."
        node.SetHighlightSeedID("seed_1")
        assert len(fired) == 1, "a same-value re-publish must not fire."
        node.SetHighlightSeedID("")
        assert len(fired) == 2, "clearing must fire ModifiedEvent."
    finally:
        node.RemoveObserver(tag)


def test_highlight_seed_id_is_never_serialized_into_the_scene():
    """The scene XML must NOT carry the highlight (the TransientPoint rule).

    A saved scene freezing the highlight is exactly the bug the transient
    member fixes: on reload the frozen value rendered orphan stripes no
    widget owned.  The persisted ``radius`` is asserted PRESENT as the
    positive control that the node's own attributes did serialize.
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    if not hasattr(node, "SetHighlightSeedID"):
        pytest.skip(f"{DISPLAY_NODE_CLASS} has no SetHighlightSeedID (ADR-0027).")

    node.SetRadius(4.75)
    node.SetHighlightSeedID("seed_42")

    scene = slicer.mrmlScene
    scene.SetSaveToXMLString(1)
    try:
        scene.Commit()
        xml = scene.GetSceneXMLString()
    finally:
        scene.SetSaveToXMLString(0)

    assert "4.75" in xml, "positive control: the persisted radius must serialize."
    assert "seed_42" not in xml, (
        "the highlight must NEVER serialize into the scene XML -- it is "
        "session interaction state (the TransientPoint precedent)."
    )
    assert "highlightSeed" not in xml and "stripePhase" not in xml, (
        "no attribute-borne highlight/phase channel may reach the scene XML."
    )


def test_highlight_seed_id_does_not_ride_copy_content():
    """``CopyContent`` must not clone the transient highlight (mirrors
    TransientPoint: node duplication / restore never carries it)."""
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)
    if not hasattr(node, "SetHighlightSeedID"):
        pytest.skip(f"{DISPLAY_NODE_CLASS} has no SetHighlightSeedID (ADR-0027).")
    other = _make_display_or_skip(slicer, "VolumetrySeedsDisplayCopyTest")

    node.SetHighlightSeedID("seed_3")
    other.CopyContent(node)

    assert other.GetHighlightSeedID() == "", (
        "CopyContent must not propagate the transient highlight."
    )


def test_display_node_is_data_only_no_rendering_machinery():
    """The display node exposes NO rendering machinery (data-only, ADR-0013 §5).

    An absence pin with a credible creep-in path: the v1 markups display
    node rendered its own glyphs, and a well-meaning port could reintroduce
    an actor/mapper/DM here.  The LayerDM Pipeline renders; the display node
    only carries state (ADR-0025/0033 data-only shape).
    """
    slicer = _slicer_or_skip()
    node = _make_display_or_skip(slicer)

    for banned in ("GetActor", "GetMapper", "CreateDefaultDisplayableManager"):
        assert not hasattr(node, banned), (
            f"{DISPLAY_NODE_CLASS} must be DATA-ONLY -- it must not expose "
            f"{banned!r} (rendering is the LayerDM Pipeline's job, ADR-0013 §5)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
