# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared control-point interaction state on a display node (ADR-0038).

The placement of draggable control points is *pipeline-managed*
(ADR-0032/0033), not a Slicer interaction node / mouse mode.  LayerDM owns
the placement Pipeline instance's lifecycle -- it creates its own per view
-- so the widget and its table cannot reach that instance directly.  The
two sides meet on the shared MRML display node: the widget/table WRITES the
arm state / active key / carrier binding onto the display node, and the
manager-driven Pipeline READS them back at event time.

ADR-0038 §"Shared home + names" extracts these accessors out of
``VascularTerritoriesLib.TerritoryInteractionState`` and PARAMETERIZES the
attribute-key namespace per consumer, so two consumers (vascular
territories, volumetry, resection) get independent keys on their own
display nodes and never read each other's flags.  The active-key suffix
defaults to the neutral ``Active``; the vascular-territories shim passes
``active_suffix="ActiveTerritory"`` to reproduce its historical keys exactly.

The class imports nothing heavy (no LayerDMLib, no Qt) so a table can
depend on it without dragging in the Pipeline's LayerDM dependency.

* armed + active key + module-active ride as string attributes (cheap,
  XML-transient);
* the carrier rides as a typed node-reference role.
"""

from __future__ import annotations

import uuid
from typing import Any

#: Nonce identifying THIS application session.  The overlay gate is stored as
#: a display-node attribute, and attributes are serialized into the scene --
#: so a plain ``"1"`` would make a scene saved with the overlays up resurrect
#: them in a later session where the owning module was never opened (and where
#: no widget exists to scrub the flag).  Storing the session nonce instead
#: makes the gate FAIL SAFE: any value that this session did not write --
#: unset, or persisted by an earlier session -- reads CLOSED.
_SESSION_NONCE = uuid.uuid4().hex


class PointPlacementState:
    """Namespaced arm/active/module-active/carrier accessors on a display node.

    ``namespace`` is the attribute-key / node-reference-role prefix; each
    consumer passes its own so the keys are disjoint on the shared display
    node (ADR-0038 §"Shared home + names").
    """

    def __init__(self, namespace: str, active_suffix: str = "Active") -> None:
        self._armed_attr = f"{namespace}.Armed"
        self._active_attr = f"{namespace}.{active_suffix}"
        self._module_active_attr = f"{namespace}.ModuleActive"
        self._overlay_session_attr = f"{namespace}.OverlaySession"
        self._grabbing_attr = f"{namespace}.Grabbing"
        self._carrier_role = f"{namespace}.carrier"

    # ------------------------------------------------------------------ #
    # Arm state
    # ------------------------------------------------------------------ #
    def set_armed(self, displayNode: Any, armed: bool) -> None:
        """Publish the arm state onto the shared display node."""
        if displayNode is not None:
            displayNode.SetAttribute(self._armed_attr, "1" if armed else "0")

    def is_armed(self, displayNode: Any) -> bool:
        return (
            displayNode is not None
            and displayNode.GetAttribute(self._armed_attr) == "1"
        )

    # ------------------------------------------------------------------ #
    # Module-active gate
    # ------------------------------------------------------------------ #
    def set_module_active(self, displayNode: Any, active: bool) -> None:
        """Publish the module-active gate onto the shared display node.

        Belt-and-suspenders beyond the armed flag: the owning module's
        ``enter()`` / ``exit()`` flips this so no view lands a point while
        the owning module is not active.
        """
        if displayNode is not None:
            displayNode.SetAttribute(self._module_active_attr, "1" if active else "0")

    def is_module_active(self, displayNode: Any) -> bool:
        """True unless the module has EXPLICITLY closed the gate.

        An UNSET attribute reads active: LayerDM creates the placement
        Pipelines the moment the display node enters the scene (before any
        ``enter()``), and a placement/edit gesture must still land in that
        window.  The gate is the module's ``exit()`` writing ``"0"`` -- the
        decline is opt-in, so opening the module (or never touching the
        flag) leaves placement enabled.

        This deliberately-optimistic default is why DRAWING has its own gate
        (``overlays_visible``, default closed): an overlay drawn before any
        ``enter()`` is visible clutter under whatever module the surgeon
        actually has open, whereas a declined click is a lost gesture.
        """
        return (
            displayNode is None
            or displayNode.GetAttribute(self._module_active_attr) != "0"
        )

    # ------------------------------------------------------------------ #
    # Overlay gate (module-scoped, default CLOSED, session-scoped)
    # ------------------------------------------------------------------ #
    def set_overlays_visible(self, displayNode: Any, visible: bool) -> None:
        """Open/close this module's TRANSIENT-overlay gate on the display node.

        The owning module's ``enter()`` opens it and its ``exit()`` closes it,
        so nothing the module draws stays on screen under another module.
        Distinct from ``set_module_active``: that one guards the add-on-click /
        placement channel and must stay open in the window between the display
        node entering the scene (when LayerDM builds the Pipelines) and the
        module's first ``enter()``; drawing, by contrast, must NOT start in
        that window.
        """
        if displayNode is not None:
            displayNode.SetAttribute(
                self._overlay_session_attr, _SESSION_NONCE if visible else "")

    def overlays_visible(self, displayNode: Any) -> bool:
        """False unless THIS session's ``enter()`` has opened the gate.

        Fails safe in both directions the module cannot observe: a display
        node whose gate this session never opened (the module was never
        entered, so no Pipeline of ours has a surgeon looking at it) and a
        gate value persisted by an EARLIER session (a scene saved with the
        overlays up, reloaded with the module untouched -- no widget exists
        then to scrub it) both read CLOSED.
        """
        return (
            displayNode is not None
            and displayNode.GetAttribute(self._overlay_session_attr) == _SESSION_NONCE
        )

    # ------------------------------------------------------------------ #
    # Grab (drag-in-flight) flag
    # ------------------------------------------------------------------ #
    def set_grabbing(self, displayNode: Any, grabbing: bool) -> None:
        """Publish that a point-drag gesture is IN FLIGHT on the display node.

        The manager-driven Pipeline sets this on a grab and clears it on
        release; a widget/table observing the CARRIER reads it to defer its
        expensive full rebuild until the drag ends (a drag relocates one
        point per mouse-move, each firing the carrier's ``Modified``, so a
        naive observer would rebuild the whole view per frame).  Rides as a
        cheap string attribute on the display node -- NOT the carrier -- so
        setting/clearing it never itself fires the carrier observer.
        """
        if displayNode is not None:
            displayNode.SetAttribute(self._grabbing_attr, "1" if grabbing else "0")

    def is_grabbing(self, displayNode: Any) -> bool:
        return (
            displayNode is not None
            and displayNode.GetAttribute(self._grabbing_attr) == "1"
        )

    # ------------------------------------------------------------------ #
    # Active key
    # ------------------------------------------------------------------ #
    def set_active(self, displayNode: Any, key: str | None) -> None:
        """Publish the active key onto the shared display node."""
        if displayNode is not None:
            displayNode.SetAttribute(self._active_attr, key or "")

    def get_active(self, displayNode: Any) -> str | None:
        if displayNode is None:
            return None
        value = displayNode.GetAttribute(self._active_attr)
        return value or None

    # ------------------------------------------------------------------ #
    # Carrier binding
    # ------------------------------------------------------------------ #
    def set_carrier(self, displayNode: Any, carrier: Any) -> None:
        """Bind the data carrier onto the display node (typed node ref).

        Fires an explicit ``Modified()``: LayerDM creates the view
        pipelines when the display node enters the scene, which is BEFORE
        this bind, and a node-reference change does not reliably emit
        ``ModifiedEvent``.  The explicit Modified drives LayerDM's
        ``UpdatePipeline`` on every view so each pipeline (re)attaches its
        carrier observer and starts tracking points (ADR-0032/0033).
        """
        if displayNode is None:
            return
        carrierId = carrier.GetID() if carrier is not None else None
        displayNode.SetNodeReferenceID(self._carrier_role, carrierId)
        displayNode.Modified()

    def get_carrier(self, displayNode: Any) -> Any | None:
        if displayNode is None:
            return None
        return displayNode.GetNodeReference(self._carrier_role)
