# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Dedicated-view manager for the resectogram concept (`ADR-0023`_ §Stage-4).

The resectogram is the flattened 2D image of the Bezier ``(u, v)``
parameter domain (`ADR-0025`_ §Context).  `ADR-0023`_ §Stage-4 names it
as the ONE custom Slicer layout v2.0 ships: it renders in a dedicated 3D
view, NOT as a sub-viewport of the shared anatomy 3D view (the retired v1
``CoRenderer2D`` path).

``ResectogramViewManager`` owns the dedicated ``vtkMRMLViewNode`` that
carries the resectogram singleton tag.  The view node is a **singleton**:
re-running ``setup()`` (module reload, second open) re-targets the
existing node rather than multiplying view nodes — the singleton-tag
mechanism the Slicer view machinery already enforces.  This mirrors the
SlicerHyperProbe ``HyperprobeViewManager._create_view_node`` precedent:
a private view node with a custom ``LayoutName`` / ``LayoutLabel`` and box
+ axis labels off, so the flattened panel reads as a clean 2D image.

No custom DisplayableManager (`ADR-0013`_ §5; the
``feedback_layerdm_no_custom_dm`` lesson): the dedicated view gets the
upstream LayerDM displayable manager for free via
``RegisterInDefaultViews()``, and the registered ``ResectogramPipeline``
creator — tightened to fire ONLY for the view carrying
``RESECTOGRAM_VIEW_SINGLETON_TAG`` — dispatches the flattened strip into
this view's renderer alone.

References
----------
* `ADR-0013`_ §1, §5 — one Pipeline per display-node type; the three
  registration calls; no custom DisplayableManager.
* `ADR-0023`_ §Stage-4 — the dedicated resectogram view as the one custom
  Slicer layout v2.0 ships.
* `ADR-0025`_ §Context — the resectogram as the flattened ``(u, v)`` image.

.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0023: ../../Docs/adr/0023-resection-plan-architecture.md
.. _ADR-0025: ../../Docs/adr/0025-locator-architecture.md
"""

from __future__ import annotations

from typing import Any

# The singleton tag the dedicated resectogram view carries.  The tightened
# ``registerResectogramPipelineCreator().tryCreate`` discriminates the
# dedicated view from every shared 3D anatomy view by this exact value.
# Human-readable, prefix-free (the Hyperprobe custom-view convention,
# ADR-0023 §Stage-4).  The dispatch tests pin the same literal in
# ``Testing/Python/conftest.py`` as RESECTOGRAM_VIEW_SINGLETON_TAG.
RESECTOGRAM_VIEW_SINGLETON_TAG = "LiverResectogram"

# Human-facing layout name / label for the dedicated view.  Reused as the
# Slicer view-node ``LayoutName`` / ``LayoutLabel`` (the Hyperprobe
# precedent uses the bare concept name for both).
_RESECTOGRAM_VIEW_LAYOUT_NAME = "LiverResectogram"
_RESECTOGRAM_VIEW_LAYOUT_LABEL = "Resectogram"


class ResectogramViewManager:
    """Owns the dedicated ``vtkMRMLViewNode`` for the resectogram display.

    Singleton-by-tag: ``ensureViewNode()`` returns the existing tagged view
    node when one is already in the scene, creating it only on first call.
    Constructing the manager is side-effect-free; the view node is created
    lazily on the first ``ensureViewNode()`` so a bare import (e.g. in a
    unit test that only reads the tag constant) does not mutate the scene.
    """

    def __init__(self) -> None:
        self._view_node: Any | None = None

    def ensureViewNode(self) -> Any:  # noqa: N802 - Slicer/Qt verb convention
        """Return the dedicated resectogram view node, creating it once.

        Singleton (re-target, don't multiply) per the dedicated-view
        decision: a second call returns the SAME node.  Resolves an
        already-present tagged node first (e.g. after a scene reload that
        kept the singleton), so the manager never appends a duplicate.
        """
        import slicer  # type: ignore[import-not-found]

        if self._view_node is not None:
            return self._view_node

        existing = self._find_tagged_view_node(slicer)
        if existing is not None:
            self._view_node = existing
            return existing

        view = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLViewNode")
        view.SetName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)
        view.SetLayoutName(_RESECTOGRAM_VIEW_LAYOUT_NAME)
        view.SetLayoutLabel(_RESECTOGRAM_VIEW_LAYOUT_LABEL)
        # The flattened panel reads as a clean 2D image: drop the 3D box
        # and axis labels (the Hyperprobe precedent does the same).
        view.SetBoxVisible(False)
        view.SetAxisLabelsVisible(False)
        self._view_node = view
        return view

    def getViewNode(self) -> Any | None:  # noqa: N802 - Slicer/Qt verb convention
        """Return the owned view node, or ``None`` if not yet created."""
        return self._view_node

    @staticmethod
    def _find_tagged_view_node(slicer: Any) -> Any | None:
        """Return the scene's resectogram-tagged view node, if any."""
        scene = slicer.mrmlScene
        count = scene.GetNumberOfNodesByClass("vtkMRMLViewNode")
        for index in range(count):
            node = scene.GetNthNodeByClass(index, "vtkMRMLViewNode")
            if (
                node is not None
                and node.GetSingletonTag() == RESECTOGRAM_VIEW_SINGLETON_TAG
            ):
                return node
        return None
