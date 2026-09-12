# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python-side tests for ``vtkLiverPoissonSurfaceReconstruction`` (ADR-0040).

These are not a translation of the C++ test.  They exist because
**ADR-0040 §Conformance makes Python reachability part of the definition
of done**, and explicitly says a C++-only test does not discharge it.

The reason is recorded history rather than principle: this project has
twice shipped a C++ entry point that compiled, linked, passed its C++
tests and was invisible from Python (#636, #640).  The VTK wrapper skips
unwrappable signatures *silently*, so nothing fails -- the symbol simply
is not there.  Since ADR-0004 puts the callers of this algorithm in
Python, an unreachable reconstruction would be an unusable one.

So what is asserted here is the BOUNDARY: that the class and its methods
survive wrapping, that arguments cross it in both directions, and that a
``vtkPolyData`` comes back with real geometry in it.  The numerical
quality of the reconstruction is the C++ test's job
(``vtkLiverPoissonSurfaceReconstructionTest.cxx``), and duplicating it
here would only mean two places to update.

References
----------
* ADR-0040 §5 -- the Python boundary is a first-class deliverable.
* ADR-0040 §Conformance -- default depth 7; Python test mandatory.
* ADR-0008 §3 -- dual-mode (Python wrapper + C++ ctkTest) discipline.
* ``reference_algorithm_wrapped_class_namespace`` -- Algorithm-library
  classes resolve ONLY via the wrapped module, never via ``slicer`` or
  plain ``vtk``.
"""

from __future__ import annotations

import math

import pytest


@pytest.fixture(scope="module")
def algorithm_module():
    """Import the C++ Algorithm wrapper, skipping if unavailable."""
    return pytest.importorskip(
        "vtkSlicerLiverResectionsModuleAlgorithmPython",
        reason=(
            "vtkSlicerLiverResectionsModuleAlgorithm not built / not on "
            "sys.path; skip the Python side of the PSR adapter."
        ),
    )


@pytest.fixture(scope="module")
def psr(algorithm_module):
    """The adapter class itself.

    ``getattr`` rather than attribute access so a MISSING class fails as
    an explicit assertion naming what went wrong, instead of an
    ``AttributeError`` traceback that reads like a typo in the test.
    """
    cls = getattr(algorithm_module, "vtkLiverPoissonSurfaceReconstruction", None)
    assert cls is not None, (
        "vtkLiverPoissonSurfaceReconstruction is absent from the wrapped "
        "Algorithm module. The class exists in C++ but did not survive "
        "VTK wrapping -- the failure mode of #636 and #640."
    )
    return cls


def _sphere_cloud(radius=50.0, centre=(10.0, -20.0, 5.0), n_theta=30, n_phi=60):
    """An oriented point cloud sampling a sphere, off the origin."""
    import vtk

    points = vtk.vtkPoints()
    normals = vtk.vtkFloatArray()
    normals.SetNumberOfComponents(3)
    normals.SetName("Normals")

    for i in range(1, n_theta):
        theta = math.pi * i / n_theta
        for j in range(n_phi):
            phi = 2.0 * math.pi * j / n_phi
            nx = math.sin(theta) * math.cos(phi)
            ny = math.sin(theta) * math.sin(phi)
            nz = math.cos(theta)
            points.InsertNextPoint(
                centre[0] + radius * nx,
                centre[1] + radius * ny,
                centre[2] + radius * nz,
            )
            normals.InsertNextTuple3(nx, ny, nz)

    cloud = vtk.vtkPolyData()
    cloud.SetPoints(points)
    cloud.GetPointData().SetNormals(normals)
    return cloud


def test_default_depth_is_reachable_and_is_seven(psr):
    """The ADR's depth decision must be readable from Python.

    A caller that cannot ask for the default has to hard-code 7 at every
    call site, which is how a documented default quietly becomes several
    undocumented ones.
    """
    assert hasattr(psr, "GetDefaultDepth"), "GetDefaultDepth did not survive wrapping"
    assert psr.GetDefaultDepth() == 7, (
        "ADR-0040 fixes the default octree depth at 7, not upstream's 8: "
        "phase 1 measured depths 8 and 9 tracking a CT-resolution liver "
        "worse than 7. Changing this needs fresh measurement, not a test edit."
    )


def test_reconstructs_a_surface_from_a_python_built_cloud(psr):
    """The whole boundary, end to end, from Python.

    A ``vtkPolyData`` built in Python goes in; a populated
    ``vtkPolyData`` comes back. This is the assertion ADR-0040
    §Conformance actually requires -- and note it would still have
    passed for #636 and #640 right up until the argument types were
    wrong, which is why it invokes rather than introspects.
    """
    import vtk

    cloud = _sphere_cloud()
    surface = vtk.vtkPolyData()

    assert psr.Reconstruct(cloud, psr.GetDefaultDepth(), surface) is True

    assert surface.GetNumberOfPoints() > 0
    assert surface.GetNumberOfPolys() > 0
    normals = surface.GetPointData().GetNormals()
    assert normals is not None, "the reconstruction carries no point normals"
    assert normals.GetNumberOfTuples() == surface.GetNumberOfPoints()


def test_reconstruction_lands_where_the_cloud_is(psr):
    """Geometry survives the boundary, not just object identity.

    Scale and offset are the things a wrapping bug mangles quietly: a
    reconstruction returned in PSR's internal normalised cube would still
    be a valid non-empty mesh, and every assertion above would pass.
    """
    import vtk

    radius = 50.0
    centre = (10.0, -20.0, 5.0)
    cloud = _sphere_cloud(radius=radius, centre=centre)
    surface = vtk.vtkPolyData()
    assert psr.Reconstruct(cloud, 6, surface) is True

    bounds = surface.GetBounds()
    for axis, c in enumerate(centre):
        low, high = bounds[2 * axis], bounds[2 * axis + 1]
        assert low == pytest.approx(c - radius, abs=0.05 * radius)
        assert high == pytest.approx(c + radius, abs=0.05 * radius)


@pytest.mark.parametrize(
    "depth",
    [0, 15],
    ids=["below-minimum", "above-maximum"],
)
def test_out_of_range_depth_is_refused(psr, depth):
    """Rejection crosses the boundary as ``False``, not as an exception.

    Depth is exponential in memory; an unchecked value is a hang or a
    bad_alloc rather than a wrong answer. The Python caller must see a
    return value it can branch on.
    """
    import vtk

    cloud = _sphere_cloud(n_theta=10, n_phi=20)
    surface = vtk.vtkPolyData()
    assert psr.Reconstruct(cloud, depth, surface) is False
    assert surface.GetNumberOfPoints() == 0


def test_a_cloud_without_normals_is_refused(psr):
    """Normals are the signal, so their absence is an error, not a default.

    Poisson reconstruction solves for the indicator function whose
    gradient matches the normals. Estimating them here instead would
    produce a confident result with no reliable orientation -- and an
    inward-oriented cloud reconstructs the COMPLEMENT of the object,
    which looks like a plausible surface right up until it is used.
    """
    import vtk

    points = vtk.vtkPoints()
    points.InsertNextPoint(0.0, 0.0, 0.0)
    points.InsertNextPoint(1.0, 0.0, 0.0)
    cloud = vtk.vtkPolyData()
    cloud.SetPoints(points)

    surface = vtk.vtkPolyData()
    assert psr.Reconstruct(cloud, 7, surface) is False
    assert surface.GetNumberOfPoints() == 0


def test_a_failed_call_clears_a_populated_output(psr):
    """Failure must EMPTY the output, never leave the previous result.

    A caller that ignores the return value should render nothing rather
    than a stale surface silently attributed to the new input -- the
    worse of the two failure modes, because it looks like it worked.
    """
    import vtk

    cloud = _sphere_cloud(n_theta=20, n_phi=40)
    surface = vtk.vtkPolyData()
    assert psr.Reconstruct(cloud, 5, surface) is True
    assert surface.GetNumberOfPoints() > 0

    assert psr.Reconstruct(None, 7, surface) is False
    assert surface.GetNumberOfPoints() == 0
    assert surface.GetNumberOfPolys() == 0
