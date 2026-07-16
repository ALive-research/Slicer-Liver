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
CARRIER_REFERENCE_ROLE = "VascularTerritories.carrier"


def set_armed(displayNode: Any, armed: bool) -> None:
    """Publish the arm state onto the shared highlight display node."""
    if displayNode is not None:
        displayNode.SetAttribute(ARMED_ATTR, "1" if armed else "0")


def is_armed(displayNode: Any) -> bool:
    return displayNode is not None and displayNode.GetAttribute(ARMED_ATTR) == "1"


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
