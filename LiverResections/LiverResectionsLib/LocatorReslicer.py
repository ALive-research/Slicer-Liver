# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Click-to-reslice consumer — locator picked point drives the slice (ADR-0025).

The cross-view locator's picked RAS world point (carried on the single
``vtkMRMLLocatorNode``, `ADR-0025`_ §"The node") drives the orthogonal slice so
its plane passes through that point ("click-to-reslice", `ADR-0025`_
§Click-to-reslice).  This is the data-flow arrow ``Node -> Slice``, distinct
from the shader-marker arrow ``Node -> Consumer -> Shader`` the T2 Pipeline
already carries.

Per `ADR-0013`_ §5 this is **not** a Pipeline or a displayable manager — it is
a plain Python observer (`ADR-0004`_): it resolves the scene's single locator,
observes its ``ModifiedEvent``, and on a picked-point change reslices the Red
slice node via ``vtkMRMLSliceNode.JumpSliceByOffsetting`` (which translates the
slice ALONG its normal only, so the plane's orientation is preserved and only
its offset moves onto the point).  Its lifecycle is owned by the caller (the
Resection Planning widget), which constructs it with the scene and calls
``cleanup()`` on teardown.  The locator reads/writes stay on the data-only
carrier (`ADR-0014`_): the reslicer reads ``GetPickedPositionWorld`` and writes
only the slice node.

Driving a single (Red) slice matches the v2.0 scope; a Red/Yellow/Green sweep
is a v2.1 enhancement alongside the deferred cross-module locator unification.

References
----------
* `ADR-0025`_ §Click-to-reslice.
* `ADR-0013`_ §5 — no custom displayable manager.
* `ADR-0004`_ — the consumer is Python.

.. _ADR-0025: ../../Docs/adr/0025-locator-architecture.md
.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../Docs/adr/0014-livermarkups-dissolution.md
.. _ADR-0004: ../../Docs/adr/0004-python-cpp-boundary.md
"""

from __future__ import annotations

from typing import Any

_LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"
#: The orthogonal slice driven by a resectogram click (v2.0 scope: Red only).
_RED_SLICE_NODE_ID = "vtkMRMLSliceNodeRed"


class LocatorReslicer:
    """Observes the single locator node and reslices the Red slice to its pick."""

    def __init__(self, scene: Any) -> None:
        self._scene = scene
        self._locator_node: Any | None = None
        self._observer_tag: int | None = None
        self.refresh()

    @staticmethod
    def reslice_slice_to_world(slice_node: Any, world_xyz: Any) -> bool:
        """Offset ``slice_node``'s plane onto the RAS point, preserving orientation.

        Uses ``vtkMRMLSliceNode.JumpSliceByOffsetting(r, a, s)`` — a translation
        along the slice normal, so the plane's normal is invariant and only its
        offset moves onto ``world_xyz``.  Returns ``True`` when it reslices;
        ``False`` (a no-op, never raising) on a degenerate input (no slice node,
        no world point, or a slice node without the jump API).
        """
        if slice_node is None or world_xyz is None:
            return False
        jump = getattr(slice_node, "JumpSliceByOffsetting", None)
        if jump is None:
            return False
        jump(float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2]))
        return True

    def refresh(self) -> None:
        """Re-resolve the scene's single locator node and (re)attach the observer.

        Idempotent: safe to call when the scene gains/loses its locator node.
        """
        found = self._resolve_locator()
        if found is self._locator_node:
            return
        self._detach()
        self._locator_node = found
        if found is not None and hasattr(found, "AddObserver"):
            self._observer_tag = found.AddObserver(
                "ModifiedEvent", self._on_locator_modified
            )

    def cleanup(self) -> None:
        """Detach the observer and drop references (symmetric with ``__init__``)."""
        self._detach()
        self._locator_node = None
        self._scene = None

    # -- internals ------------------------------------------------------- #

    def _resolve_locator(self) -> Any | None:
        if self._scene is None:
            return None
        return self._scene.GetFirstNodeByClass(_LOCATOR_NODE_CLASS)

    def _detach(self) -> None:
        if self._locator_node is not None and self._observer_tag is not None:
            try:
                self._locator_node.RemoveObserver(self._observer_tag)
            except Exception:  # pragma: no cover - defensive
                pass
        self._observer_tag = None

    def _on_locator_modified(self, caller: Any, event: str) -> None:
        self._reslice_from_locator(caller)

    def _reslice_from_locator(self, locator: Any) -> None:
        if locator is None or self._scene is None:
            return
        getter = getattr(locator, "GetPickedPositionWorld", None)
        if getter is None:
            return
        red = self._scene.GetNodeByID(_RED_SLICE_NODE_ID)
        if red is None:
            return
        self.reslice_slice_to_world(red, getter())
