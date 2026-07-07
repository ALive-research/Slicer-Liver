# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Shared volume-role vocabulary for the Stage-1 -> Stage-2 hand-off (ADR-0023).

Case Setup (Stage 1, the Liver shell) tags each loaded volume with its
acquisition-phase ROLE; Anatomy Definition (Stage 2, LiverSegmentation) reads
that role to pick its working volume (``LiverRole == 'PortalVenous'``).  The
vocabulary lives here -- one shared module both sides import -- so the stored
attribute key + values cannot drift (the value is machine-stable; the
human-facing dropdown label is decoupled).

Roles are acquisition PHASES, not anatomical structures, so they carry NO SCT
code (ADR-0011's canonical-dispatch-key decision covers segmented anatomy, not
contrast phases).
"""

from __future__ import annotations

from typing import Any

#: Scene-attribute key a volume's role is stored under (the shipped key).
LIVER_ROLE_ATTRIBUTE = "LiverRole"

#: The v2.0 role vocabulary, ordered; CamelCase, no spaces (machine-stable
#: stored values -- human labels are decoupled at the UI).  Only
#: ``PortalVenous`` is consumed downstream in v2.0 (Stage-2 input selection);
#: the others are informational phase tags.
LIVER_ROLES = ("Native", "Arterial", "PortalVenous", "Delayed", "Other")

#: Convenience: the phase Stage-2 selects as its working volume.
LIVER_ROLE_PORTAL_VENOUS = "PortalVenous"


def set_volume_role(volume_node: Any, role: str) -> bool:
    """Tag ``volume_node`` with ``role`` (writes the ``LiverRole`` attribute).

    Returns ``True`` when the tag is written; ``False`` (a no-op, never raising)
    when ``volume_node`` is ``None`` or ``role`` is not one of ``LIVER_ROLES``
    -- an invalid role must not silently corrupt the Stage-1 -> Stage-2 contract.
    """
    if volume_node is None or role not in LIVER_ROLES:
        return False
    setter = getattr(volume_node, "SetAttribute", None)
    if setter is None:
        return False
    setter(LIVER_ROLE_ATTRIBUTE, role)
    return True
