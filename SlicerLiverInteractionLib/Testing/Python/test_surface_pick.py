# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Pure-VTK unit skeletons for the shared ``SurfacePick`` geometry core.

ADR-0038 §"Shared home + names" extracts the vessel-adhering pick core
out of ``VascularTerritoriesLib.VesselSurfacePick`` into the shared
``SlicerLiverInteractionLib`` package as ``SurfacePick`` -- the pure-VTK
ray->closed-surface intersect-nearest + closest-point fallback with a
lazy MTime-invalidated ``vtkCellLocator``.  The move is verbatim (only the
class name drops the ``Vessel`` prefix, T2.7); the geometry contract is
identical to the ``VesselSurfacePick`` original.  This file mirrors the
assertions that live today in
``VascularTerritories/Testing/Python/test_vessel_surface_pick.py`` so the
extracted class is pinned to the SAME behaviour it had at its origin.

Discipline: this layer runs under bare ``PythonSlicer -m pytest`` -- no
Slicer scene, no Qt, no GL (ADR-0003 testability invariant; ADR-0004 the
pick math is pure Python).  Surfaces are built from ``vtkSphereSource`` /
``vtkPlaneSource``; rays are plain world coordinates; assertions are
geometry-real (a ray down +z through a unit sphere at the origin hits the
north pole ``(0, 0, 1)``).

HARNESS: bare ``PythonSlicer -m pytest`` (pure VTK) AND launched (both;
the pure-VTK core has no Slicer dependency, so it runs in either row).

The SUT does not exist yet.  Per ADR-0027 red->skip the import is guarded
and every test SKIP-PENDINGs on ``ImportError``; the skips lift when the
implementer lands ``SlicerLiverInteractionLib/SurfacePick.py`` (PR 1 of
the ADR-0038 extraction, ``volumetry-seeds-layerdm-plan.md`` §6).

References
----------
* ADR-0038 -- unify the control-point interaction; §"Shared home + names"
  names ``SurfacePick`` as the extracted pure-VTK pick core.
* ADR-0027 -- invariant-test-first; the red->skip lifecycle here.
* ADR-0004 -- Python/C++ boundary; the pick math is pure Python.
* ADR-0003 -- testability invariant; this unit layer imports no
  Slicer / MRML / Qt.
* VascularTerritories/Testing/Python/test_vessel_surface_pick.py -- the
  behaviour-preserving origin these assertions mirror.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip(
    "vtk",
    reason=(
        "vtk not importable; the pick core imports vtk.  Run inside "
        "Slicer's Python (PythonSlicer) or any environment where the "
        "bundled vtk wheel is on sys.path."
    ),
)

# --------------------------------------------------------------------------- #
# Repo geometry -- the extracted pick core lives in the NEW shared
# ``SlicerLiverInteractionLib`` package (ADR-0038 §"Shared home + names"),
# a sibling to LayerDMLib.  The path-insert lets the bare unit layer import
# the module before the packaging follow-up (Lib dir + PYTHON_SCRIPTS
# registration) lands -- the test_vessel_surface_pick.py precedent.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

_PENDING = (
    "SurfacePick not yet implemented -- the ADR-0038 extraction "
    "(SlicerLiverInteractionLib/SurfacePick.py) has not landed (ADR-0027 "
    "red->skip)."
)


def _import_pick():
    """Import the shared pick core or SKIP-PENDING when it does not exist yet.

    The implementer must provide ``SurfacePick`` with, at minimum::

        class SurfacePick:
            def __init__(self, polydata: vtk.vtkPolyData | None) -> None: ...
            def pick(
                self,
                p1: tuple[float, float, float],
                p2: tuple[float, float, float],
                fallback_point: tuple[float, float, float] | None = None,
            ) -> tuple[float, float, float] | None: ...

    ``pick`` returns the adhering world point (on the mesh), or ``None``
    when there is no surface to adhere to.  This is the SAME contract the
    ``VesselSurfacePick`` origin already satisfies (ADR-0038 verbatim move).
    """
    try:
        from SurfacePick import SurfacePick
    except ImportError:
        pytest.skip(_PENDING)
    return SurfacePick


# --------------------------------------------------------------------------- #
# Geometry helpers (pure VTK -- no Slicer, no GL)
# --------------------------------------------------------------------------- #


def _unit_sphere(center=(0.0, 0.0, 0.0), radius=1.0):
    """A dense unit sphere so ray/nearest hits land close to the ideal."""
    source = vtk.vtkSphereSource()
    source.SetCenter(*center)
    source.SetRadius(radius)
    source.SetThetaResolution(64)
    source.SetPhiResolution(64)
    source.Update()
    return source.GetOutput()


def _xy_plane(size=10.0):
    """A flat z=0 plane spanning [-size/2, size/2] in x and y."""
    source = vtk.vtkPlaneSource()
    source.SetOrigin(-size / 2.0, -size / 2.0, 0.0)
    source.SetPoint1(size / 2.0, -size / 2.0, 0.0)
    source.SetPoint2(-size / 2.0, size / 2.0, 0.0)
    source.SetResolution(20, 20)
    source.Update()
    return source.GetOutput()


def _distance_to_surface(polydata, point) -> float:
    """Distance from ``point`` to the closest point on ``polydata``."""
    locator = vtk.vtkCellLocator()
    locator.SetDataSet(polydata)
    locator.BuildLocator()
    closest = [0.0, 0.0, 0.0]
    cell_id = vtk.reference(0)
    sub_id = vtk.reference(0)
    dist2 = vtk.reference(0.0)
    locator.FindClosestPoint(list(point), closest, cell_id, sub_id, dist2)
    return float(dist2) ** 0.5


# --------------------------------------------------------------------------- #
# INCREMENT 1 -- the pick core (mirrors test_vessel_surface_pick.py)
# --------------------------------------------------------------------------- #


def test_ray_hit_returns_point_on_the_mesh():
    """A ray that crosses the mesh returns a point that lies ON the mesh.

    Ray straight down the +z axis through a unit sphere at the origin: the
    near hit is the north pole ``(0, 0, 1)``.  ADR-0038 §"Shared home +
    names" (SurfacePick = the extracted pick core).
    """
    SurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = SurfacePick(sphere)

    hit = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))

    assert hit is not None
    assert _distance_to_surface(sphere, hit) == pytest.approx(0.0, abs=1e-3)
    assert list(hit) == pytest.approx([0.0, 0.0, 1.0], abs=2e-2)


def test_ray_miss_projects_to_nearest_surface_point():
    """A ray that misses the mesh returns the NEAREST-surface projection of
    the fallback world point -- still ON the mesh.

    Fallback point ``(3, 0, 0)`` outside a unit sphere at the origin
    projects to ``(1, 0, 0)``.  ADR-0038 §"Shared home + names" (the
    closest-point fallback).
    """
    SurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = SurfacePick(sphere)

    projected = pick.pick(
        p1=(-5.0, 10.0, 0.0),
        p2=(5.0, 10.0, 0.0),
        fallback_point=(3.0, 0.0, 0.0),
    )

    assert projected is not None
    assert _distance_to_surface(sphere, projected) == pytest.approx(0.0, abs=1e-3)
    assert list(projected) == pytest.approx([1.0, 0.0, 0.0], abs=2e-2)


def test_no_surface_returns_none():
    """No polydata (or an empty mesh) -> the pick core returns ``None``.

    The raw-point fallback is the CALLER's concern; the core only signals
    "no surface".  ADR-0038 §"Shared home + names" pick-core contract.
    """
    SurfacePick = _import_pick()

    pick_none = SurfacePick(None)
    assert pick_none.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0)) is None

    pick_empty = SurfacePick(vtk.vtkPolyData())
    assert pick_empty.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0)) is None


def test_fold_over_picks_the_nearest_hit_to_ray_origin():
    """A ray crossing the mesh twice returns the hit NEAREST the ray origin,
    not the far one.

    Ray from ``(0, 0, 5)`` down the -z axis through a unit sphere at the
    origin crosses at ``z=+1`` (near) and ``z=-1`` (far); the near hit
    ``(0, 0, 1)`` wins.  ADR-0038 §"Shared home + names" nearest-hit
    selection.
    """
    SurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = SurfacePick(sphere)

    hit = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))

    assert hit is not None
    assert list(hit) == pytest.approx([0.0, 0.0, 1.0], abs=2e-2)
    assert hit[2] > 0.0, "the far hit z=-1 must NOT win."


# --------------------------------------------------------------------------- #
# INCREMENT 2 -- lazy locator cache invalidation on MTime advance
# --------------------------------------------------------------------------- #


def test_pick_reflects_new_surface_after_polydata_mutation():
    """When the polydata's ``MTime`` advances the next pick reflects the NEW
    surface, not a stale cached locator.

    Build a flat z=0 plane; pick a ray down +z -> hits z=0.  Translate all
    points to z=+3 and mark modified; the SAME ray picked again must now hit
    z=+3.  ADR-0038 §"Shared home + names" "a lazy MTime-invalidated
    ``vtkCellLocator``".
    """
    SurfacePick = _import_pick()
    plane = _xy_plane()
    pick = SurfacePick(plane)

    first = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))
    assert first is not None
    assert first[2] == pytest.approx(0.0, abs=1e-3)

    points = plane.GetPoints()
    for i in range(points.GetNumberOfPoints()):
        x, y, _ = points.GetPoint(i)
        points.SetPoint(i, x, y, 3.0)
    points.Modified()
    plane.Modified()

    second = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))
    assert second is not None
    assert second[2] == pytest.approx(3.0, abs=1e-3), (
        "stale locator cache returned the old surface (MTime not invalidated)."
    )


def test_nearest_projection_also_reflects_new_surface_after_mutation():
    """A missing-ray nearest-projection pick also tracks the mutated surface.

    The cache invalidation applies to the closest-point path, not just the
    ray-cast path.  ADR-0038 §"Shared home + names" locator-cache
    invalidation.
    """
    SurfacePick = _import_pick()
    sphere = _unit_sphere(radius=1.0)
    pick = SurfacePick(sphere)

    before = pick.pick(
        p1=(-5.0, 10.0, 0.0),
        p2=(5.0, 10.0, 0.0),
        fallback_point=(3.0, 0.0, 0.0),
    )
    assert before is not None
    assert list(before) == pytest.approx([1.0, 0.0, 0.0], abs=2e-2)

    bigger = _unit_sphere(radius=2.0)
    sphere.GetPoints().DeepCopy(bigger.GetPoints())
    sphere.SetPolys(bigger.GetPolys())
    sphere.Modified()

    after = pick.pick(
        p1=(-5.0, 10.0, 0.0),
        p2=(5.0, 10.0, 0.0),
        fallback_point=(3.0, 0.0, 0.0),
    )
    assert after is not None
    assert list(after) == pytest.approx([2.0, 0.0, 0.0], abs=3e-2), (
        "stale locator cache returned the old radius (MTime not invalidated)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
