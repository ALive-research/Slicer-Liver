# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared annotation-interaction state on the highlight display node (ADR-0037).

The Stage-2 placement is *pipeline-managed* (ADR-0037 §Decision 2), not a
Slicer interaction node / mouse mode.  But LayerDM owns the placement
Pipeline instance's lifecycle — it creates its own per view — so the widget
and its table cannot reach that instance directly.  The two sides meet on
the shared ``vtkMRMLTerritoriesHighlightDisplayNode``: the table WRITES the
arm state / active territory / carrier binding onto the display node, and the
manager-driven Pipeline READS them back at event time.

These are the accessors both sides use.  The module imports nothing heavy
(no LayerDMLib, no Qt) so the table can depend on it without dragging in the
Pipeline's LayerDM dependency.

* armed + active territory ride as string attributes (cheap, XML-transient).
* the carrier rides as a typed node-reference role.
"""

from __future__ import annotations

from typing import Any

#: Display-node attribute keys / reference role for the interaction state.
ARMED_ATTR = "VascularTerritories.Armed"
ACTIVE_TERRITORY_ATTR = "VascularTerritories.ActiveTerritory"
MODULE_ACTIVE_ATTR = "VascularTerritories.ModuleActive"
CARRIER_REFERENCE_ROLE = "VascularTerritories.carrier"


def set_armed(displayNode: Any, armed: bool) -> None:
    """Publish the arm state onto the shared highlight display node."""
    if displayNode is not None:
        displayNode.SetAttribute(ARMED_ATTR, "1" if armed else "0")


def is_armed(displayNode: Any) -> bool:
    return displayNode is not None and displayNode.GetAttribute(ARMED_ATTR) == "1"


def set_module_active(displayNode: Any, active: bool) -> None:
    """Publish the module-active gate onto the shared highlight display node.

    Belt-and-suspenders beyond the armed flag (ADR-0037 slice-5 concern #1):
    the owning module's ``enter()`` / ``exit()`` flips this so no view lands a
    seed while VascularTerritories is not the active module.
    """
    if displayNode is not None:
        displayNode.SetAttribute(MODULE_ACTIVE_ATTR, "1" if active else "0")


def is_module_active(displayNode: Any) -> bool:
    """True unless the module has EXPLICITLY closed the gate.

    An UNSET attribute reads active: LayerDM creates the placement Pipelines
    the moment the display node enters the scene (before any ``enter()``), and
    a placement/edit gesture must still land in that window.  The gate is the
    module's ``exit()`` writing ``"0"`` -- the decline is opt-in, so opening
    the module (or never touching the flag) leaves placement enabled.
    """
    return displayNode is None or displayNode.GetAttribute(MODULE_ACTIVE_ATTR) != "0"


def set_active_territory(displayNode: Any, territoryId: str | None) -> None:
    """Publish the active territory onto the shared highlight display node."""
    if displayNode is not None:
        displayNode.SetAttribute(ACTIVE_TERRITORY_ATTR, territoryId or "")


def get_active_territory(displayNode: Any) -> str | None:
    if displayNode is None:
        return None
    value = displayNode.GetAttribute(ACTIVE_TERRITORY_ATTR)
    return value or None


def set_carrier(displayNode: Any, carrier: Any) -> None:
    """Bind the annotation carrier onto the display node (typed node ref).

    Fires an explicit ``Modified()``: LayerDM creates the view pipelines when
    the display node enters the scene, which is BEFORE this bind, and a node-
    reference change does not reliably emit ``ModifiedEvent``.  The explicit
    Modified drives LayerDM's ``UpdatePipeline`` on every view so each
    pipeline (re)attaches its carrier observer and starts tracking seeds.
    """
    if displayNode is None:
        return
    carrierId = carrier.GetID() if carrier is not None else None
    displayNode.SetNodeReferenceID(CARRIER_REFERENCE_ROLE, carrierId)
    displayNode.Modified()


def get_carrier(displayNode: Any) -> Any | None:
    if displayNode is None:
        return None
    return displayNode.GetNodeReference(CARRIER_REFERENCE_ROLE)
