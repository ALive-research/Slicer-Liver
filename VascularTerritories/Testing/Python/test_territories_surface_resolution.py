# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0037 Stage-3 — the centerline surface-resolution invariant.

The VMTK centerline feed (``VascularTerritoriesLogic.extractCenterlines``)
runs the extractor over the input segmentation's closed-surface mesh
(``polyDataFromNode`` / ``_preprocessedSurface``).  The extractor called
with ``segmentId`` was, by the feed's convention, a *territory* id (or the
empty string, "extract every territory") — NOT a segmentation *segment*
id.  Passing that empty string straight into
``GetClosedSurfaceRepresentation`` never resolves a segment, so the mesh
came back with zero points and the surface silently degraded to ``None``.

The real SlicerVMTK extractor hard-fails on an empty/``None`` surface ("no
Voronoi diagram was generated" / "vtkvmtkCapPolyData has 0 connections" /
"could not compute surface normals").  This file pins the SURFACE-RESOLUTION
invariant that is actually broken — NOT the VMTK compute itself (that stays
env-/eyeball-gated in ``test_territories_vmtk_feed.py``):

* i1 (launched) — SEGMENT RESOLUTION.  Given a ``vtkMRMLSegmentationNode``
  carrying ONE segment with a closed-surface representation,
  ``polyDataFromNode(seg, "")`` and ``_preprocessedSurface(seg)`` return a
  NON-EMPTY ``vtkPolyData`` (points > 0): the segment is actually resolved,
  not an empty-segment-id no-op.  Converges on the SAME whole-vessel-tree
  resolution the pick/highlight path uses
  (``VesselHighlightWiring.closed_surface_polydata``), so placement-snap and
  centerline extraction see the same mesh.  Needs Slicer's segmentation
  logic to build the closed surface; SKIPS cleanly bare, RUNS launched.
* i2 (launched) — HONEST DEGRADATION.  When ``_preprocessedSurface`` DOES
  return ``None``/empty (a genuinely empty segmentation), the feed must NOT
  invoke the extractor with a ``None``/empty surface — it skips that
  territory's extraction instead of crashing the real extractor.  The
  extractor is monkeypatched to CAPTURE its surface argument, so the
  invariant is "the real extractor is never fed ``None``/empty", not a VMTK
  run.  SKIPS cleanly bare, RUNS launched.

Red->green (ADR-0027): i1 FAILS against the empty-segment-id
``GetClosedSurfaceRepresentation(segmentId="")`` (zero points) and PASSES
once the segmentation branch resolves the real segment(s); i2 FAILS against
the feed handing ``None`` to the extractor and PASSES once the feed skips a
missing surface.  Launched-only (Slicer segmentation logic + a live scene);
SKIP bare.

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py
    (closed_surface_polydata — the shared surface-resolution seam)
  * VascularTerritories/Testing/Python/test_territories_vmtk_feed.py
    (the transient-node lifecycle + real VMTK run)
  * VascularTerritories/Testing/Python/conftest.py  (the skip guards)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"

TERRITORY_A = "SegmentVII"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in conftest.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _logic_or_skip(slicer):
    try:
        from VascularTerritories import VascularTerritoriesLogic
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VascularTerritoriesLogic not importable ({exc!r}).")
    logic = VascularTerritoriesLogic()
    if not hasattr(logic, "polyDataFromNode"):
        pytest.skip(
            "VascularTerritoriesLogic has no polyDataFromNode -- the "
            "surface-resolution seam is unavailable (ADR-0027)."
        )
    return logic


def _sphere_segmentation(slicer, center=(0.0, 0.0, 0.0), radius=20.0):
    """A segmentation node carrying ONE closed-surface sphere segment.

    Mirrors the ``test_vessel_highlight_wiring`` fixture: import a sphere
    model into a fresh segmentation so it carries a genuine closed-surface
    representation (the pick/snap + centerline paths both read this mesh).
    """
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(32)
    source.SetPhiResolution(32)
    source.Update()

    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "Vessel")
    modelNode.SetAndObservePolyData(source.GetOutput())

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "SurfaceResolutionVessel")
    segmentationNode.CreateDefaultDisplayNodes()
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentationNode)
    slicer.mrmlScene.RemoveNode(modelNode)
    return segmentationNode


def _empty_segmentation(slicer):
    """A segmentation node with NO segment (no closed surface to resolve)."""
    return slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "EmptyVessel")


def _make_carrier_or_skip(slicer, name="SurfaceResolutionCarrier"):
    node = slicer.mrmlScene.AddNewNodeByClass(CUSTOM_TERRITORIES_CLASS, name)
    if node is None:
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} not registered -- the ADR-0037 "
            "annotation carrier is unavailable (launched build) (ADR-0027)."
        )
    if not hasattr(node, "AddAnnotationPoint"):
        pytest.skip(
            f"{CUSTOM_TERRITORIES_CLASS} has no AddAnnotationPoint -- the "
            "ADR-0037 annotation carrier has not landed (ADR-0027)."
        )
    return node


# --------------------------------------------------------------------------- #
# i1 — segment resolution: an empty segment id still resolves the mesh
# --------------------------------------------------------------------------- #


def test_polydata_from_segmentation_resolves_a_non_empty_mesh():
    """i1: ``polyDataFromNode(seg, "")`` resolves the real segment's mesh.

    The feed passes the *territory* semantics ("" == "every territory")
    through the ``segmentId`` slot; the segmentation branch must resolve the
    actual segment(s) rather than pass the empty string straight into
    ``GetClosedSurfaceRepresentation`` (which resolves NO segment and yields
    a zero-point mesh).  ADR-0037 §Decision 4.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    segmentation = _sphere_segmentation(slicer)

    polyData = logic.polyDataFromNode(segmentation, "")

    assert polyData is not None, (
        "polyDataFromNode must resolve a segmentation's closed surface, not "
        "return None for a segment carrying geometry (ADR-0037 §Decision 4)."
    )
    assert polyData.GetNumberOfPoints() > 0, (
        "the resolved segmentation mesh must be non-empty -- an empty "
        "segment id must NOT be handed to GetClosedSurfaceRepresentation "
        "(that resolves no segment -> zero points) (ADR-0037 §Decision 4)."
    )


def test_preprocessed_surface_of_segmentation_is_non_empty():
    """i1: ``_preprocessedSurface(seg)`` decimates a non-empty resolved mesh.

    The decimated feed surface (what the extractor is actually run over) is
    NON-EMPTY for a one-segment segmentation: the resolution +
    preprocessing chain never silently degrades a real surface to ``None``.
    ADR-0037 §Decision 4.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    if not hasattr(logic, "_preprocessedSurface"):
        pytest.skip(
            "VascularTerritoriesLogic has no _preprocessedSurface -- the "
            "decimated-surface seam is unavailable (ADR-0027)."
        )
    segmentation = _sphere_segmentation(slicer)

    surfacePolyData = logic._preprocessedSurface(segmentation)

    assert surfacePolyData is not None, (
        "_preprocessedSurface must NOT degrade a one-segment segmentation to "
        "None -- the segment resolves to a real mesh (ADR-0037 §Decision 4)."
    )
    assert surfacePolyData.GetNumberOfPoints() > 0, (
        "the decimated feed surface must be non-empty for a segmentation "
        "carrying geometry (ADR-0037 §Decision 4)."
    )


def test_preprocess_tolerates_triangle_strip_surface():
    """i1: ``preprocessAndDecimate`` survives a triangle-STRIP input surface.

    A segmentation's closed-surface representation arrives as triangle strips
    (``GetNumberOfPolys() == 0``); ``vtkDecimatePro`` decimates polygons, so
    fed strips it emits an empty mesh unless the preprocessing triangulates
    FIRST.  This pins the strip case directly (the sphere-model fixture above
    retains polygons and never exercises it).  ADR-0037 §Decision 4.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    if not hasattr(logic, "preprocessAndDecimate"):
        pytest.skip(
            "VascularTerritoriesLogic has no preprocessAndDecimate -- the "
            "surface-preprocessing seam is unavailable (ADR-0027)."
        )

    source = vtk.vtkSphereSource()
    source.SetRadius(20.0)
    source.SetThetaResolution(32)
    source.SetPhiResolution(32)
    source.Update()
    stripper = vtk.vtkStripper()
    stripper.SetInputData(source.GetOutput())
    stripper.Update()
    stripSurface = stripper.GetOutput()
    assert stripSurface.GetNumberOfPolys() == 0 and stripSurface.GetNumberOfPoints() > 0, (
        "the fixture must be a genuine triangle-strip surface (0 polys)."
    )

    processed = logic.preprocessAndDecimate(stripSurface)

    assert processed is not None and processed.GetNumberOfPoints() > 0, (
        "preprocessAndDecimate must triangulate a strip surface before "
        "decimating -- a strip input must NOT decimate to an empty mesh "
        "(ADR-0037 §Decision 4)."
    )


# --------------------------------------------------------------------------- #
# i2 — honest degradation: never feed None/empty to the real extractor
# --------------------------------------------------------------------------- #


def test_empty_surface_is_not_fed_to_the_extractor(monkeypatch):
    """i2: a missing/empty surface skips extraction, never feeds the extractor.

    The real SlicerVMTK extractor hard-fails on a ``None``/empty surface (no
    Voronoi diagram / 0 cap connections / no surface normals).  When
    ``_preprocessedSurface`` returns ``None``/empty the feed must SKIP that
    territory's extraction rather than call the extractor with the empty
    surface.  The extractor is monkeypatched to CAPTURE its surface argument
    so the invariant is "the extractor is never fed None/empty", not a VMTK
    run.  ADR-0037 §Decision 4.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    if not hasattr(logic, "getCenterlineLogic"):
        pytest.skip(
            "VascularTerritoriesLogic has no getCenterlineLogic -- the "
            "ADR-0037 Stage-3 extractor injection seam is unavailable "
            "(ADR-0027)."
        )
    if not hasattr(logic, "extractCenterlines"):
        pytest.skip(
            "VascularTerritoriesLogic has no extractCenterlines -- the "
            "ADR-0037 Stage-3 feed entry point is unavailable (ADR-0027)."
        )

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddAnnotationPoint(TERRITORY_A, 1.0, 0.0, 0.0)
    carrier.AddAnnotationPoint(TERRITORY_A, 2.0, 0.0, 0.0)

    empty = _empty_segmentation(slicer)

    fed_surfaces = []

    class _CapturingExtractor:
        def extractCenterline(self, seedsNode, surfacePolyData=None, *args, **kwargs):  # noqa: N802 - VMTK verb
            fed_surfaces.append(surfacePolyData)
            return None

    monkeypatch.setattr(logic, "getCenterlineLogic", lambda: _CapturingExtractor())

    # Must not raise; must not feed the extractor a None/empty surface.
    logic.extractCenterlines(carrier, empty, "")

    for surface in fed_surfaces:
        assert surface is not None, (
            "the feed must NOT invoke the real extractor with a None surface "
            "-- an empty segmentation skips extraction (ADR-0037 §Decision 4)."
        )
        assert surface.GetNumberOfPoints() > 0, (
            "the feed must NOT invoke the real extractor with an EMPTY "
            "surface (0 points) (ADR-0037 §Decision 4)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
