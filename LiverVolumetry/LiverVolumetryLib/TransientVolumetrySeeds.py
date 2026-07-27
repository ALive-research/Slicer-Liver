# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the carrier->transient-fiducial adapter.

``vtkLiverVolumetryLogic`` keeps its C++ signatures unchanged (ADR-0015): it
takes a ``vtkMRMLMarkupsFiducialNode*``.  The seeds-off-markups migration
feeds it a TRANSIENT fiducial built INSIDE the call from the seed carrier
(``vtkMRMLVolumetrySeedsNode``), mirroring ADR-0037 §Decision 4 /
``VascularTerritoriesLib.TransientVmtkSeeds``.

Two layers, split on the ADR-0004 Python/C++ boundary:

* ``build_fiducial_payload`` -- a DEPENDENCY-FREE core mapping ordered
  ``(x, y, z, label)`` seeds to a fiducial-shaped payload, preserving
  coordinate + LABEL + order.  It imports neither ``slicer`` nor ``vtk`` nor
  Qt, so the mapping invariant is bare-unit-testable
  (``test_volumetry_seed_transient_fiducial.py``).
* ``build_transient_fiducial`` -- a thin Logic wrapper over the core that
  creates the transient ``vtkMRMLMarkupsFiducialNode`` in a live scene from a
  carrier node (positions + per-seed labels as control-point labels), returning
  the node the caller feeds the logic and later removes.  Pinned end to end by
  ``test_volumetry_compute_from_carrier.py``.

The per-seed LABEL must round-trip into the transient fiducial's control-point
label so ``GenerateSegmentsLabelMap`` still names generated segments correctly
(ADR-0038 §Conformance).

References
----------
* ADR-0038 -- §Conformance (per-seed labels round-trip so generated segments
  keep their names).
* ADR-0004 -- Python/C++ boundary; keep the mapping pure Python.
* ADR-0015 -- the C++ region-grow logic is unchanged (transient adapter, not a
  signature rewrite).
* VascularTerritoriesLib/TransientVmtkSeeds.py -- the transient-builder idiom
  this mirrors.
"""

from __future__ import annotations


def build_fiducial_payload(seeds):
    """Map ordered ``(x, y, z, label)`` seeds to a fiducial-shaped payload.

    Reproduces ``seeds`` 1:1 in placement ORDER as ``((x, y, z), label)``
    pairs, preserving each seed's coordinate and its LABEL (the generated
    segment name).  Pure -- no live scene, no markups, no wrapped node -- so
    the mapping invariant is bare-unit-testable (ADR-0038 §Conformance).

    :param seeds: iterable of ``(x, y, z, label)`` tuples in placement order.
    :returns: list of ``((x, y, z), label)`` pairs, one per input seed, in the
        SAME order.
    """
    payload = []
    for x, y, z, label in seeds:
        payload.append(((float(x), float(y), float(z)), label))
    return payload


def seeds_from_carrier(seedsNode):
    """Read a ``vtkMRMLVolumetrySeedsNode`` into ordered ``(x, y, z, label)``.

    The carrier read the pure core consumes: walks the carrier in placement
    order (``GetNumberOfSeeds`` / ``GetNthSeed`` / ``GetNthSeedLabel``) so the
    label stays bound to its coordinate.  Kept separate from
    ``build_fiducial_payload`` so the pure core never touches a wrapped node.
    """
    seeds = []
    if seedsNode is None:
        return seeds
    for i in range(seedsNode.GetNumberOfSeeds()):
        coord = seedsNode.GetNthSeed(i)
        seeds.append(
            (float(coord[0]), float(coord[1]), float(coord[2]), seedsNode.GetNthSeedLabel(i))
        )
    return seeds


def build_transient_fiducial(scene, seedsNode):
    """Build a transient ``vtkMRMLMarkupsFiducialNode`` from the seed carrier.

    The thin Logic wrapper over ``build_fiducial_payload`` (ADR-0004): adds a
    fiducial node to ``scene``, sets each control point's position + LABEL from
    the carrier's seeds in placement ORDER, and returns it.  The caller feeds it
    to the unchanged ``vtkLiverVolumetryLogic`` and REMOVES it afterwards -- no
    persistent markups survive (ADR-0014 §"Fourth layer").

    The control-point LABEL round-trip is the segment-name fidelity
    ``GenerateSegmentsLabelMap`` reads (ADR-0038 §Conformance).
    """
    import vtk

    node = scene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    payload = build_fiducial_payload(seeds_from_carrier(seedsNode))
    for (x, y, z), label in payload:
        index = node.AddControlPoint(vtk.vtkVector3d(x, y, z))
        node.SetNthControlPointLabel(index, label)
    return node
