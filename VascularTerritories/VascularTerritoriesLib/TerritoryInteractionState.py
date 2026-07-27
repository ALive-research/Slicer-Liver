# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Compatibility shim over the shared ``PointPlacementState`` accessors.

ADR-0038 §"Shared home + names" generalised these arm / active-territory /
module-active / carrier accessors into ``SlicerLiverInteractionLib``'s
``PointPlacementState``, parameterizing the attribute-key namespace per
consumer.  This module now delegates to a ``PointPlacementState`` bound to
the ``"VascularTerritories"`` namespace, which reproduces the original
attribute keys (``VascularTerritories.Armed`` etc.) EXACTLY, so existing
call sites and the territory characterization suite keep working unchanged
(the extraction is behaviour-preserving -- ADR-0038 [review]).

The module-level function names are preserved verbatim (including
``set_active_territory`` / ``get_active_territory``, which map onto the
base's namespace-neutral ``set_active`` / ``get_active``).

The dual import mirrors the ``<Module>Lib`` idiom used throughout this
package: the installed/built tree stages ``SlicerLiverInteractionLib``
alongside this package; the bare unit layer sets ``sys.path`` to the
individual Lib dir, so a sibling-directory fallback keeps the shared core
importable there too.
"""

from __future__ import annotations

from typing import Any

try:
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
except ImportError:  # bare unit layer: add the sibling Lib dir to sys.path
    import pathlib
    import sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in sys.path:
        sys.path.insert(0, str(_shared_lib))
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

#: The territory namespace reproduces the original attribute keys exactly.
_NAMESPACE = "VascularTerritories"
_STATE = PointPlacementState(_NAMESPACE)

#: Display-node attribute keys / reference role (kept for back-compat).
ARMED_ATTR = f"{_NAMESPACE}.Armed"
ACTIVE_TERRITORY_ATTR = f"{_NAMESPACE}.ActiveTerritory"
MODULE_ACTIVE_ATTR = f"{_NAMESPACE}.ModuleActive"
CARRIER_REFERENCE_ROLE = f"{_NAMESPACE}.carrier"


def set_armed(displayNode: Any, armed: bool) -> None:
    """Publish the arm state onto the shared highlight display node."""
    _STATE.set_armed(displayNode, armed)


def is_armed(displayNode: Any) -> bool:
    return _STATE.is_armed(displayNode)


def set_module_active(displayNode: Any, active: bool) -> None:
    """Publish the module-active gate onto the shared highlight display node."""
    _STATE.set_module_active(displayNode, active)


def is_module_active(displayNode: Any) -> bool:
    """True unless the module has EXPLICITLY closed the gate."""
    return _STATE.is_module_active(displayNode)


def set_active_territory(displayNode: Any, territoryId: str | None) -> None:
    """Publish the active territory onto the shared highlight display node."""
    _STATE.set_active(displayNode, territoryId)


def get_active_territory(displayNode: Any) -> str | None:
    return _STATE.get_active(displayNode)


def set_carrier(displayNode: Any, carrier: Any) -> None:
    """Bind the annotation carrier onto the display node (typed node ref)."""
    _STATE.set_carrier(displayNode, carrier)


def get_carrier(displayNode: Any) -> Any | None:
    return _STATE.get_carrier(displayNode)
