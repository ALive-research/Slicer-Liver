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

This file also pins the slice-5 (PR-A) VESSEL-SCT-FILTER invariant (T1):

* T1 (launched) — VESSEL-SCT RESOLVER.  ADR-0037 slice 5 narrows the
  centerline surface candidates to segments whose ``TerminologyEntry`` TYPE
  code is vascular (``SCT^29092000`` Vein / ``SCT^51114001`` Artery + a
  documented allowlist), EXCLUDING the liver (``SCT^10200004``) and tumour
  segments.  Given a multi-segment segmentation carrying real-data-shaped tags
  (liver, vein, artery, tumour), the resolver returns ONLY the vessel segment
  ids.  Mirrors the ``GetLiverSegmentId`` C++ idiom (``logic.scl``); needs
  segmentation infra + the wrapped C++ logic so it SKIPS cleanly bare and RUNS
  launched, and SKIP-PENDINGs on the not-yet-existing resolver method until
  PR-A lands (ADR-0027).

See also:
  * Docs/adr/0037-vascular-territories-off-markups.md  (§Decision 4;
    §Amendment — connected-tree-constrained centerline seeding (slice 5))
  * Docs/adr/0011-terminology-standard-clinical-terms.md  (the SCT-tag match)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * Docs/design/connected-tree-seeding-plan.md  (C1 vessel-surface resolver; T1)
  * VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py
    (closed_surface_polydata — the shared surface-resolution seam)
  * VascularTerritories/Testing/Python/test_territories_connectivity.py
    (the bare pure-VTK connectivity twin, T2/T3)
  * VascularTerritories/Testing/Python/test_territories_vmtk_feed.py
    (the transient-node lifecycle + real VMTK run)
  * VascularTerritories/Testing/Python/conftest.py  (the skip guards)
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk")

CUSTOM_TERRITORIES_CLASS = "vtkMRMLCustomTerritoriesNode"
SEGMENTATION_CLASS = "vtkMRMLSegmentationNode"

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


# =========================================================================== #
# T1 — vessel-SCT resolver keeps vessels, excludes liver + tumour (launched)
# =========================================================================== #
#
# ADR-0037 slice 5 (PR-A): the centerline surface candidates are the input
# segments whose TerminologyEntry TYPE code is a vascular concept (Vein /
# Artery + a documented allowlist); the liver-SCT and tumour segments are
# excluded.  Real data tags vessels under category SCT^85756007 (Tissue) with
# the generic Vein/Artery types, so the fixtures use those real-data shapes.

# Slice-5 (PR-A) vessel-resolver seam (proposed; sharpen at landing).  Mirrors
# the GetLiverSegmentId idiom on the wrapped C++ logic (logic.scl).
VASCULAR_SEGMENT_IDS_METHOD = "GetVascularSegmentIds"

# Real-data-shaped TerminologyEntry tags (category ~ type), matching the
# _LIVER_TERMINOLOGY shape used in test_territories_map_compute.py.  Vessels
# are tagged under category SCT^85756007 (Tissue) with the generic Vein/Artery
# types; the liver + tumour carry their own category/type pairs.
_LIVER_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^~Anatomic codes~^^~^^"
)
_VEIN_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^29092000^Vein~^^~Anatomic codes~^^~^^"
)
_ARTERY_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^85756007^Body tissue~SCT^51114001^Artery~^^~Anatomic codes~^^~^^"
)
_TUMOUR_TERMINOLOGY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^260787004^Physical object~SCT^19227008^Malignant neoplasm~^^~Anatomic codes~^^~^^"
)


def _cpp_vascular_logic_or_skip(logic):
    """The wrapped C++ logic exposing ``GetVascularSegmentIds`` (``logic.scl``).

    The vessel-SCT resolver mirrors ``GetLiverSegmentId`` — it lives on the C++
    logic (it reads MRML segment tags), reached through ``scl``.  SKIP-PENDINGs
    on the not-yet-existing resolver method until PR-A lands (ADR-0027).
    """
    cpp = getattr(logic, "scl", None)
    if cpp is None:
        pytest.skip(
            "VascularTerritoriesLogic has no scl (the wrapped C++ logic) -- "
            "launched build required (ADR-0027)."
        )
    if not hasattr(cpp, VASCULAR_SEGMENT_IDS_METHOD):
        pytest.skip(
            f"vtkSlicerVascularTerritoriesLogic has no {VASCULAR_SEGMENT_IDS_METHOD}"
            " -- the ADR-0037 slice-5 (PR-A) vessel-SCT resolver has not landed."
            "  The skip lifts at the implementation commit (ADR-0027)."
        )
    return cpp


def _add_tagged_segment(slicer, segmentation, terminology, name, center):
    """Import one closed-surface sphere segment tagged with ``terminology``."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(10.0)
    source.SetThetaResolution(16)
    source.SetPhiResolution(16)
    source.Update()
    modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", name)
    modelNode.SetAndObservePolyData(source.GetOutput())
    slicer.modules.segmentations.logic().ImportModelToSegmentationNode(
        modelNode, segmentation)
    slicer.mrmlScene.RemoveNode(modelNode)
    segmentation_obj = segmentation.GetSegmentation()
    segId = segmentation_obj.GetNthSegmentID(segmentation_obj.GetNumberOfSegments() - 1)
    segmentation_obj.GetSegment(segId).SetTag("TerminologyEntry", terminology)
    return segId


def _multi_segment_segmentation(slicer):
    """A segmentation with liver + vein + artery + tumour segments (tagged).

    Returns ``(segmentation, {role: segId})`` so the test can assert the
    resolver keeps the two vessel segments and drops the liver + tumour.
    """
    seg = slicer.mrmlScene.AddNewNodeByClass(
        SEGMENTATION_CLASS, "VesselResolveMultiSeg")
    seg.CreateDefaultDisplayNodes()
    ids = {
        "liver": _add_tagged_segment(
            slicer, seg, _LIVER_TERMINOLOGY, "LiverModel", (0.0, 0.0, 0.0)),
        "vein": _add_tagged_segment(
            slicer, seg, _VEIN_TERMINOLOGY, "VeinModel", (40.0, 0.0, 0.0)),
        "artery": _add_tagged_segment(
            slicer, seg, _ARTERY_TERMINOLOGY, "ArteryModel", (80.0, 0.0, 0.0)),
        "tumour": _add_tagged_segment(
            slicer, seg, _TUMOUR_TERMINOLOGY, "TumourModel", (120.0, 0.0, 0.0)),
    }
    return seg, ids


def test_vascular_resolver_keeps_vessels_excludes_liver_and_tumour():
    """T1: ``GetVascularSegmentIds`` keeps vessels, drops liver + tumour.

    ADR-0037 slice 5 narrows the centerline surface candidates to segments
    whose ``TerminologyEntry`` TYPE code is vascular (``SCT^29092000`` Vein /
    ``SCT^51114001`` Artery), EXCLUDING the liver (``SCT^10200004``) and tumour
    segments.  Given a segmentation carrying real-data-shaped tags for all
    four, the resolver returns EXACTLY the vein + artery segment ids — never the
    liver or the tumour (ADR-0037 slice-5 Conformance [test]; ADR-0011 SCT-tag
    match).  Launched-only (segmentation infra + wrapped C++ logic); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    cpp = _cpp_vascular_logic_or_skip(logic)
    segmentation, ids = _multi_segment_segmentation(slicer)

    resolved = set(cpp.GetVascularSegmentIds(segmentation))

    assert ids["vein"] in resolved, (
        "the vessel resolver must KEEP the SCT^29092000 (Vein) segment "
        "(ADR-0037 slice 5)."
    )
    assert ids["artery"] in resolved, (
        "the vessel resolver must KEEP the SCT^51114001 (Artery) segment "
        "(ADR-0037 slice 5)."
    )
    assert ids["liver"] not in resolved, (
        "the vessel resolver must EXCLUDE the SCT^10200004 (Liver) segment -- "
        "the liver supplies the map region, not a vessel tree (ADR-0037 slice "
        "5; ADR-0011)."
    )
    assert ids["tumour"] not in resolved, (
        "the vessel resolver must EXCLUDE the tumour segment (ADR-0037 slice 5)."
    )
    assert resolved == {ids["vein"], ids["artery"]}, (
        "the vessel resolver must return EXACTLY the vessel segments "
        f"({{{ids['vein']}, {ids['artery']}}}), got {resolved} (ADR-0037 slice "
        "5)."
    )


def test_pick_surface_is_vessels_only_excluding_parenchyma():
    """T1b: the pick surface (``vascular_surface_polydata``) drops the parenchyma.

    ADR-0037 slice 5: the click-snap + hover surface is vessels-only, so the
    cursor snaps to a vessel and never the liver parenchyma or a tumour.  For a
    tagged multi-segment segmentation the vessels-only mesh is strictly smaller
    than the whole-segmentation mesh (the parenchyma + tumour geometry is
    absent).  Launched-only (segmentation infra); SKIPS bare.
    """
    slicer = _slicer_or_skip()
    try:
        from VascularTerritoriesLib.VesselHighlightWiring import (
            closed_surface_polydata,
            vascular_surface_polydata,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VesselHighlightWiring vessels-only seam absent ({exc!r}).")
    segmentation, _ids = _multi_segment_segmentation(slicer)

    whole = closed_surface_polydata(segmentation)
    vessels = vascular_surface_polydata(segmentation)

    assert whole is not None and whole.GetNumberOfPoints() > 0
    assert vessels is not None and vessels.GetNumberOfPoints() > 0, (
        "the vessels-only pick surface must be non-empty for a segmentation "
        "carrying vessel segments (ADR-0037 slice 5)."
    )
    assert vessels.GetNumberOfPoints() < whole.GetNumberOfPoints(), (
        "the vessels-only pick surface must be strictly smaller than the whole "
        "segmentation -- the parenchyma + tumour geometry must be absent so the "
        "cursor never snaps to the liver blob (ADR-0037 slice 5)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
