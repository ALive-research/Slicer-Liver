# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-3 — the pure territory string->int label map (territory-map compute).

ADR-0037 §Decision 4 makes the carrier's ``CenterlineRefs`` + ``Groupings`` a
MAP: one carrier, one territory map, all its centerlines.  The
territory-map compute path derives, per territory, the arbitrary distinct
positive labelmap scalar that ``vtkSlicerVascularTerritoriesLogic
::MarkSegmentWithID`` stamps into each centerline's ``segmentId`` point-scalar.

That int is NOT an anatomy / SCT code (ADR-0011 reserves SCT terminology for
the accepted-plan terminology surface, not this internal watershed label): it
is only required to be a distinct positive integer per territory so the
downstream watershed separates the territories.  This module derives it
DETERMINISTICALLY from the carrier's canonical territory-id order:
``index + 1`` (1-based; 0 is reserved for the labelmap background).  The same
territories therefore derive the same ints across repeated calls -- the
reproducibility the compute path needs.

The ordering source of truth is the carrier's
``GetAnnotationTerritoryIds()`` (a deterministic, lexicographically-sorted
enumeration -- the carrier stores annotation points in an ordered map).  The
PURE core (``territory_label_ints``) takes an already-ordered id list so it
stays dependency-free and bare-unit-testable; the thin live reader
(``territory_label_int``) sources that order off a live carrier.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * Docs/adr/0014-livermarkups-dissolution.md  (the wrapper/carrier idiom)
  * Docs/adr/0004-python-cpp-boundary.md  (the pure core lives in Lib)
  * VascularTerritories/MRML/vtkMRMLCustomTerritoriesNode.h
    (GetAnnotationTerritoryIds is the deterministic id order)
  * VascularTerritories/Logic/vtkSlicerVascularTerritoriesLogic.h
    (MarkSegmentWithID consumes the derived int)
"""

from __future__ import annotations


def territory_label_ints(territory_ids):
    """Map an ORDERED territory-id list to its 1-based labelmap ints.

    Pure value logic -- no live carrier, no scene, no VTK -- so the mapping
    invariant is bare-unit-testable (ADR-0037 §Decision 4).  The int for a
    territory id is its position in ``territory_ids`` plus one (0 is reserved
    for the labelmap background), so the first territory maps to 1.  A fixed
    id order therefore yields a deterministic, distinct-per-territory map.

    :param territory_ids: territory ids in the carrier's canonical order
        (``GetAnnotationTerritoryIds()``).
    :returns: a ``dict`` mapping each territory id to its 1-based int, in the
        same order.
    """
    return {territoryId: index + 1 for index, territoryId in enumerate(territory_ids)}


def territory_label_int(carrier, territoryId):
    """Read a single territory's derived labelmap int off a LIVE carrier.

    A thin wrapper over :func:`territory_label_ints`: it sources the canonical
    id order from ``carrier.GetAnnotationTerritoryIds()`` then indexes into the
    pure map (ADR-0037 §Decision 4).  Returns ``None`` when the territory
    carries no annotation points (it is absent from the id enumeration).

    :param carrier: the ``vtkMRMLCustomTerritoriesNode`` annotation carrier.
    :param territoryId: the surgeon-named territory id to resolve.
    :returns: the 1-based labelmap int, or ``None`` if ``territoryId`` is not
        among the carrier's annotated territories.
    """
    ordered_ids = list(carrier.GetAnnotationTerritoryIds())
    return territory_label_ints(ordered_ids).get(territoryId)
