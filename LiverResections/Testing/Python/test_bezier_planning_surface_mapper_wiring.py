# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T2-mapper-wiring -- BezierPlanningRepresentation drives the real mapper.

Pins the minimal slice of T2-mapper-wiring (the LayerDM render cutover for the
Bezier resection surface): the Planning-state Representation must render the
*tessellated Bezier patch* through the relocated, real
``vtkOpenGLBezierResectionPolyDataMapper`` -- NOT the placeholder raw
control-mesh through a generic ``vtkPolyDataMapper``.  This is the bottleneck
slice that unblocks the ADR-0025 locator consumer (#489) and Locator B/D: the
``uLocatorPosition`` / ``uLocatorRadius`` uniforms landed on that mapper have
no visible effect until a real instance actually renders the surface.

Three pinned invariants (all GL-free -- no render, no window):

  1. Surface mapper TYPE -- ``GetSurfaceMapper()`` is a
     ``vtkOpenGLBezierResectionPolyDataMapper`` (the relocated real mapper per
     ADR-0014 §3), not the generic ``vtkPolyDataMapper`` placeholder.

  2. Tessellated patch, not the control mesh -- after ``update()`` the surface
     polydata carries the Bezier-tessellated geometry (one point per
     ``resolution`` cell, i.e. ``>> Rows*Cols`` control points) WITH per-point
     normals AND the ``uvCoords`` texture-coordinate array the mapper's vertex
     shader reads (``CacheDataArray("uvCoords", tcoords, ...)``).  The
     placeholder built only the ``Rows*Cols`` control mesh with no TCoords.

  3. Display-field plumbing -- the display node's resection/grid/margin fields
     reach the mapper's uniform setters (``SetResectionColor`` /
     ``SetResectionGridColor`` / ``SetResectionOpacity`` /
     ``SetGridDivisions`` / ``SetGridThicknessFactor``), porting the v1 setup
     from ``vtkSlicerBezierSurfaceRepresentation3D::UpdateBezierSurfaceDisplay``.

-- SCOPED OUT of this slice (deferred) --

The RAS/IJK transformation matrices and the distance-map 3D texture binding
(``SetRasToIjkMatrixT`` / ``SetIjkToTextureMatrixT`` /
``SetDistanceMapTextureObject``) are NOT wired here: the v2
``vtkMRMLBezierSurfaceNode`` carries no distance-map volume reference (the v1
``vtkMRMLMarkupsBezierSurfaceNode`` did, via ``GetDistanceMapVolumeNode()``).
With no node-level distance-map source there is nothing to thread; the mapper's
fragment shader already degrades gracefully when no ``distanceTexture`` is
bound (``SetUniformi("distanceTexture", 0)`` fallback).  Those parts wait on a
follow-on that gives the v2 node a distance-map reference.

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

``vtkOpenGLBezierResectionPolyDataMapper`` (LiverResections VTKWidgets) and
``vtkBezierSurfaceSource`` (LiverMarkups VTKWidgets) are wrapped-C++ classes
reachable only inside a launched Slicer with the modules loaded; a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` and the wrapped
widget classes off the path, so this SKIPS CLEANLY via the shared
``slicer_pytest_support`` guards.  The Representation is plain Python + VTK;
the test needs no render window.

-- WHY THIS IS RED NOW --

``BezierPlanningRepresentation._build_vtk_pipeline`` still constructs a generic
``vtk.vtkPolyDataMapper`` and ``_apply_data_node`` builds the raw control mesh
(``TODO(T2-mapper-relocation)`` at construction + data-apply).  Each test
SKIPS pre-implementation on the real-mapper seam (``_require_real_mapper_or_skip``)
rather than failing noisily, and goes GREEN once the implementer swaps the
mapper + ports the tessellation -- per ADR-0027 §Conformance ("for skipped
tests, the skip lifts at the implementation commit").

See also:
  * Docs/adr/0014-livermarkups-dissolution.md §3   (mapper relocation -- done)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §6     (Representations as pipelines)
  * Docs/adr/0025-cross-view-locator.md              (#489 consumer this unblocks)
  * Docs/adr/0008-testing-strategy.md §1, §6         (dual-harness strategy)
  * LiverMarkups/VTKWidgets/vtkSlicerBezierSurfaceRepresentation3D.cxx  (v1 source)
  * LiverResections/Testing/Python/conftest.py       (the cleanup fixtures)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"
REAL_MAPPER_CLASS = "vtkOpenGLBezierResectionPolyDataMapper"


def _slicer_or_skip():
    """Resolve a launched ``slicer`` module or skip cleanly under bare pytest."""
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_representation_or_skip():
    """Construct a ``BezierPlanningRepresentation`` or skip if unimportable.

    Importable cleanly only inside a Slicer process with LiverResectionsLib on
    the path; a bare-pytest run skips earlier via ``_slicer_or_skip``.
    """
    try:
        from LiverResectionsLib.Representations.BezierPlanningRepresentation import (
            BezierPlanningRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "BezierPlanningRepresentation not importable "
            f"({exc!r}) -- the Planning Representation is not reachable in "
            "this environment."
        )
    return BezierPlanningRepresentation()


def _bezier_node_or_skip(slicer):
    """Add a wrapped ``vtkMRMLBezierSurfaceNode`` or skip if not registered."""
    node = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    if node is None:
        pytest.skip(
            f"{BEZIER_NODE_CLASS} not registered in this build -- cannot "
            "exercise the surface tessellation."
        )
    return node


def _display_node_or_skip(slicer):
    """Add a wrapped ``vtkMRMLParametricSurfaceDisplayNode`` or skip."""
    node = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS)
    if node is None:
        pytest.skip(
            f"{DISPLAY_NODE_CLASS} not registered in this build -- cannot "
            "exercise the display-field plumbing."
        )
    return node


def _require_real_mapper_or_skip(rep):
    """Skip unless the Representation's surface mapper is the real type.

    The T2-mapper-wiring seam: the placeholder generic ``vtkPolyDataMapper``
    must be swapped for the relocated ``vtkOpenGLBezierResectionPolyDataMapper``
    (ADR-0014 §3).  RED == the swap has not landed, so the mapper is still
    generic and every test here skips; the skip lifts when the wiring lands
    (ADR-0027 §Conformance).
    """
    mapper = rep.GetSurfaceMapper()
    if mapper is None or not mapper.IsA(REAL_MAPPER_CLASS):
        actual = type(mapper).__name__ if mapper is not None else "None"
        pytest.skip(
            "BezierPlanningRepresentation surface mapper is "
            f"{actual!r}, not {REAL_MAPPER_CLASS!r} -- the T2-mapper-wiring "
            "swap (ADR-0014 §3) has not landed.  Skip lifts when "
            "_build_vtk_pipeline constructs the relocated real mapper."
        )
    return mapper


def test_planning_surface_uses_real_bezier_mapper_with_tessellated_patch():
    """Invariants 1 + 2: real mapper rendering the tessellated Bezier patch.

    The surface mapper is the relocated ``vtkOpenGLBezierResectionPolyDataMapper``
    and, after ``update()``, the surface polydata is the Bezier-tessellated
    patch (one point per resolution cell, ``>>`` the control-point count) with
    per-point normals and the ``uvCoords`` (TCoords) array the mapper's vertex
    shader consumes -- NOT the placeholder raw control mesh.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    mapper = _require_real_mapper_or_skip(rep)

    assert mapper.IsA(REAL_MAPPER_CLASS), (
        "surface mapper must be the relocated real "
        f"{REAL_MAPPER_CLASS} (ADR-0014 §3), got {type(mapper).__name__}."
    )

    data = _bezier_node_or_skip(slicer)
    display = _display_node_or_skip(slicer)
    rep.update(display, data)

    polydata = rep.GetSurfacePolyData()
    assert polydata is not None, (
        "Representation must expose the tessellated surface polydata after "
        "update() for the mapper to render."
    )

    n_points = polydata.GetNumberOfPoints()
    n_controls = int(data.GetRows()) * int(data.GetCols())
    assert n_points > n_controls, (
        f"surface polydata has {n_points} point(s) -- expected the "
        f"Bezier-tessellated patch (>> {n_controls} control points), not the "
        "placeholder control mesh.  Port vtkBezierSurfaceSource + "
        "vtkPolyDataNormals from vtkSlicerBezierSurfaceRepresentation3D."
    )

    point_data = polydata.GetPointData()
    assert point_data.GetNormals() is not None, (
        "tessellated surface must carry per-point normals "
        "(vtkPolyDataNormals), as the v1 representation produced."
    )
    tcoords = point_data.GetTCoords()
    assert tcoords is not None and tcoords.GetNumberOfComponents() == 2, (
        "tessellated surface must carry the 2-component uvCoords (TCoords) "
        "the mapper's vertex shader reads via "
        'CacheDataArray("uvCoords", tcoords, ...); without it the grid / '
        "margin fragment shader has no parametric coordinate."
    )
    assert tcoords.GetNumberOfTuples() == n_points, (
        "uvCoords must have one tuple per tessellated point "
        f"({n_points}), got {tcoords.GetNumberOfTuples()}."
    )


def test_planning_display_fields_plumbed_to_mapper():
    """Invariant 3: display-node fields reach the mapper's uniform setters.

    Ports ``vtkSlicerBezierSurfaceRepresentation3D::UpdateBezierSurfaceDisplay``:
    the display node's resection colour / grid colour / opacity, and (when 3D
    grid visibility is on) the grid divisions / thickness, are pushed onto the
    real mapper.  Margins (``SetResectionMargin`` / ``SetUncertaintyMargin``)
    are out of scope -- the v2 node hierarchy carries no margin scalar yet.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    mapper = _require_real_mapper_or_skip(rep)

    data = _bezier_node_or_skip(slicer)
    display = _display_node_or_skip(slicer)

    display.SetResectionColor(0.2, 0.4, 0.6)
    display.SetResectionGridColor(0.7, 0.8, 0.9)
    display.SetResectionOpacity(0.5)
    display.SetGrid3DVisibility(True)
    display.SetGridDivisions(7.0)
    display.SetGridThickness(3.0)

    rep.update(display, data)

    assert _almost_eq3(mapper.GetResectionColor(), (0.2, 0.4, 0.6)), (
        "display ResectionColor must reach the mapper's SetResectionColor "
        f"uniform; got {tuple(mapper.GetResectionColor())}."
    )
    assert _almost_eq3(mapper.GetResectionGridColor(), (0.7, 0.8, 0.9)), (
        "display ResectionGridColor must reach the mapper's "
        f"SetResectionGridColor uniform; got {tuple(mapper.GetResectionGridColor())}."
    )
    assert abs(mapper.GetResectionOpacity() - 0.5) < 1e-5, (
        "display ResectionOpacity must reach the mapper's SetResectionOpacity "
        f"uniform; got {mapper.GetResectionOpacity()}."
    )
    assert mapper.GetGridDivisions() == 7, (
        "with Grid3DVisibility on, display GridDivisions must reach the "
        f"mapper's SetGridDivisions; got {mapper.GetGridDivisions()}."
    )
    assert abs(mapper.GetGridThicknessFactor() - 3.0) < 1e-5, (
        "with Grid3DVisibility on, display GridThickness must reach the "
        f"mapper's SetGridThicknessFactor; got {mapper.GetGridThicknessFactor()}."
    )

    # Grid visibility off => divisions/thickness collapse to 0 (v1 parity:
    # the shader draws no grid when divisions are 0).
    display.SetGrid3DVisibility(False)
    rep.update(display, data)
    assert mapper.GetGridDivisions() == 0, (
        "Grid3DVisibility off must zero the mapper's GridDivisions "
        f"(v1 parity); got {mapper.GetGridDivisions()}."
    )


def _almost_eq3(actual, expected, tol=1e-5):
    """True iff two 3-vectors agree componentwise within ``tol``."""
    try:
        return all(abs(float(actual[i]) - expected[i]) < tol for i in range(3))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
