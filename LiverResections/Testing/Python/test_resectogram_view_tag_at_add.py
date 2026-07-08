# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The resectogram view node must carry its singleton tag AT scene-add time.

LayerDM reacts to scene node-add events: pipeline creators can be
consulted for a view node the moment it enters the scene.  The view
manager previously added the node FIRST and tagged it after
(``AddNewNodeByClass`` then ``SetSingletonTag``), so every creator that
excludes the resectogram view by its tag — the surface-family creators
per ADR-0023 §Stage-4 — saw an untagged node and leaked deformable
surface pipelines into the flattened strip view.

Pinned here with a real scene observer: a ``NodeAddedEvent`` listener
must observe the singleton tag (and the layout name) already set on the
view node when the add event fires.
"""

from __future__ import annotations

import pytest


def _slicer_or_skip():
    # Shared support module, NOT ``from conftest import`` (multi-root runs
    # resolve `conftest` to the first root's file).
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def test_singleton_tag_visible_to_node_added_observers():
    slicer = _slicer_or_skip()
    try:
        from LiverResectionsLib.ResectogramViewManager import (
            RESECTOGRAM_VIEW_SINGLETON_TAG,
            ResectogramViewManager,
        )
    except Exception:
        pytest.skip("LiverResectionsLib.ResectogramViewManager not importable.")

    import vtk

    scene = slicer.mrmlScene
    # A pre-existing tagged singleton would short-circuit creation; drop it
    # so this test exercises the CREATE path.
    stale = []
    for i in range(scene.GetNumberOfNodesByClass("vtkMRMLViewNode")):
        node = scene.GetNthNodeByClass(i, "vtkMRMLViewNode")
        if node is not None and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG:
            stale.append(node)
    for node in stale:
        scene.RemoveNode(node)

    seen = {}

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def _on_node_added(caller, event, callData):
        if callData is not None and callData.IsA("vtkMRMLViewNode"):
            seen["tag"] = callData.GetSingletonTag()
            seen["layout"] = callData.GetLayoutName()

    tag = scene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, _on_node_added)
    try:
        manager = ResectogramViewManager()
        view = manager.ensureViewNode()
        assert view is not None
        assert seen, "the observer saw no vtkMRMLViewNode add event"
        assert seen["tag"] == RESECTOGRAM_VIEW_SINGLETON_TAG, (
            "the singleton tag must be set BEFORE the node enters the scene "
            "-- creators consulted at node-add time otherwise see an "
            "untagged view and leak surface pipelines into the strip view."
        )
        assert seen["layout"], "the layout name must also be set before add"
    finally:
        scene.RemoveObserver(tag)
        node = manager.getViewNode()
        if node is not None:
            scene.RemoveNode(node)
