# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Pure-VTK unit skeletons for the VascularTerritories vessel-adhering
highlight pick core.

Feature: while placing vessel-annotation markers (a
``vtkMRMLMarkupsFiducialNode`` tagged ``VascularTerritories.VascTerrId``)
the highlight adheres to the input segmentation's closed-surface mesh
under the cursor, and on click the placed fiducial SNAPS onto that mesh.
The snap target is the segmentation's closed-surface polydata; an
off-surface click resolves to the nearest-surface projection.  A raw
(un-snapped) point is used only when there is no mesh at all — and that
raw fallback is the CALLER's concern, not the pick core's: the core just
signals "no surface" by returning ``None``.

These are the two pure-VTK, bare-unit-testable increments:

* INCREMENT 1 — the pick core: given a surface ``vtkPolyData`` + a cursor
  ray (world ``p1``->``p2``), return the adhering world point.
* INCREMENT 2 — locator cache invalidation: the pick is backed by a
  ``vtkCellLocator`` (or equivalent) built from the polydata; when the
  polydata's ``MTime`` advances (the segment mesh was edited/rebuilt) the
  next pick must reflect the NEW surface, not a stale cache.

Discipline: this layer runs under bare ``PythonSlicer -m pytest`` — no
Slicer scene, no Qt, no GL.  Surfaces are built from ``vtkSphereSource`` /
``vtkPlaneSource`` / hand-built ``vtkPolyData``; rays are plain world
coordinates; assertions are geometry-real (the expected on-surface point
is computed by construction — e.g. a ray down the +z axis through a unit
sphere centred at the origin hits ``(0, 0, 1)``).

The SUT does not exist yet.  Per the ADR-0027 red->skip lifecycle the
import is guarded and every test SKIP-PENDINGs on ``ImportError``; the
skips lift automatically when the implementer lands the module.  The
proposed seam is a NEW ``VascularTerritoriesLib`` package (there is no
Lib dir today — the module is the legacy single-file
``VascularTerritories.py``); the pick core lives at
``VascularTerritoriesLib/VesselSurfacePick.py``.

References
----------
* ADR-0025 — Locator Architecture; the pick-core / cell-locator pattern
  this vessel highlight mirrors (a vessel-specific highlight, distinct
  from the resection locator).
* ADR-0027 — invariant-test-first discipline; the red->skip-lifts-at-
  implementation lifecycle these skeletons follow.
* ADR-0004 — Python/C++ boundary; the pick math is pure Python.
* ADR-0003 — testability invariant; this unit layer imports no Slicer /
  MRML / Qt.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip(
    "vtk",
    reason=(
        "vtk not importable; the pick core imports vtk, so the whole "
        "suite needs it.  Run inside Slicer's Python (PythonSlicer) or "
        "any environment where the bundled vtk wheel is on sys.path."
    ),
)

# --------------------------------------------------------------------------- #
# Repo geometry — the proposed pick-core seam lives in a NEW
# ``VascularTerritoriesLib`` package alongside the legacy single-file
# ``VascularTerritories.py``.  This mirrors the ``<Module>Lib`` install
# convention already used by ``LiverResectionsLib``.  The path-insert
# lets the bare unit layer import the module before the packaging
# follow-up (Lib dir + PYTHON_SCRIPTS registration) lands.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "VascularTerritories" / "VascularTerritoriesLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

_PENDING = "VesselSurfacePick not yet implemented (ADR-0027 red->skip)"


def _import_pick():
    """Import the pick core or SKIP-PENDING when it does not exist yet.

    The implementer must provide ``VesselSurfacePick`` with, at minimum:

        class VesselSurfacePick:
            def __init__(self, polydata: vtk.vtkPolyData | None) -> None: ...
            def pick(
                self,
                p1: tuple[float, float, float],
                p2: tuple[float, float, float],
                fallback_point: tuple[float, float, float] | None = None,
            ) -> tuple[float, float, float] | None: ...

    ``pick`` returns the adhering world point (on the mesh), or ``None``
    when there is no surface to adhere to.
    """
    try:
        from VesselSurfacePick import VesselSurfacePick
    except ImportError:
        pytest.skip(_PENDING)
    return VesselSurfacePick


# --------------------------------------------------------------------------- #
# Geometry helpers (pure VTK — no Slicer, no GL)
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
# INCREMENT 1 — the pick core
# --------------------------------------------------------------------------- #


def test_ray_hit_returns_point_on_the_mesh():
    """A ray that crosses the mesh returns a point that lies ON the mesh.

    Ray straight down the +z axis through a unit sphere at the origin:
    the near hit is the north pole ``(0, 0, 1)``.  ADR-0025 pick core.
    """
    VesselSurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = VesselSurfacePick(sphere)

    hit = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))

    assert hit is not None
    assert _distance_to_surface(sphere, hit) == pytest.approx(0.0, abs=1e-3)
    assert list(hit) == pytest.approx([0.0, 0.0, 1.0], abs=2e-2)


def test_ray_miss_projects_to_nearest_surface_point():
    """A ray that misses the mesh returns the NEAREST-surface projection
    of the fallback world point — still ON the mesh.

    Fallback point ``(3, 0, 0)`` outside a unit sphere at the origin
    projects to ``(1, 0, 0)``.  ADR-0025 nearest-surface fallback.
    """
    VesselSurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = VesselSurfacePick(sphere)

    # A ray well clear of the sphere (parallel to +x at y=10).
    projected = pick.pick(
        p1=(-5.0, 10.0, 0.0),
        p2=(5.0, 10.0, 0.0),
        fallback_point=(3.0, 0.0, 0.0),
    )

    assert projected is not None
    assert _distance_to_surface(sphere, projected) == pytest.approx(
        0.0, abs=1e-3
    )
    assert list(projected) == pytest.approx([1.0, 0.0, 0.0], abs=2e-2)


def test_no_surface_returns_none():
    """No polydata (or an empty mesh) -> the pick core returns ``None``.

    The raw-point fallback is the CALLER's concern; the core only signals
    "no surface".  ADR-0025 pick core contract.
    """
    VesselSurfacePick = _import_pick()

    pick_none = VesselSurfacePick(None)
    assert pick_none.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0)) is None

    pick_empty = VesselSurfacePick(vtk.vtkPolyData())
    assert pick_empty.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0)) is None


def test_fold_over_picks_the_nearest_hit_to_ray_origin():
    """A ray crossing the mesh twice returns the hit NEAREST the ray
    origin, not the far one.

    Ray from ``(0, 0, 5)`` down the -z axis through a unit sphere at the
    origin crosses at ``z=+1`` (near) and ``z=-1`` (far).  The near hit
    ``(0, 0, 1)`` wins.  ADR-0025 nearest-hit selection.
    """
    VesselSurfacePick = _import_pick()
    sphere = _unit_sphere()
    pick = VesselSurfacePick(sphere)

    hit = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))

    assert hit is not None
    assert list(hit) == pytest.approx([0.0, 0.0, 1.0], abs=2e-2)
    # The far hit would be z=-1; assert we did NOT pick it.
    assert hit[2] > 0.0


# --------------------------------------------------------------------------- #
# INCREMENT 2 — locator cache invalidation
# --------------------------------------------------------------------------- #


def test_pick_reflects_new_surface_after_polydata_mutation():
    """When the polydata's ``MTime`` advances (segment mesh edited/rebuilt)
    the next pick reflects the NEW surface, not a stale cached locator.

    Build a flat z=0 plane; pick a ray down +z -> hits z=0.  Translate all
    points to z=+3 and mark the polydata modified; the SAME ray picked
    again must now hit z=+3.  ADR-0025 locator-cache invalidation.
    """
    VesselSurfacePick = _import_pick()
    plane = _xy_plane()
    pick = VesselSurfacePick(plane)

    first = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))
    assert first is not None
    assert first[2] == pytest.approx(0.0, abs=1e-3)

    # Mutate the surface: lift every point to z=+3, advance MTime.
    points = plane.GetPoints()
    for i in range(points.GetNumberOfPoints()):
        x, y, _ = points.GetPoint(i)
        points.SetPoint(i, x, y, 3.0)
    points.Modified()
    plane.Modified()

    second = pick.pick(p1=(0.0, 0.0, 5.0), p2=(0.0, 0.0, -5.0))
    assert second is not None
    assert second[2] == pytest.approx(3.0, abs=1e-3), (
        "stale locator cache returned the old surface"
    )


def test_nearest_projection_also_reflects_new_surface_after_mutation():
    """A missing-ray nearest-projection pick also tracks the mutated
    surface — the cache invalidation applies to the closest-point path,
    not just the ray-cast path.  ADR-0025 locator-cache invalidation.
    """
    VesselSurfacePick = _import_pick()
    sphere = _unit_sphere(radius=1.0)
    pick = VesselSurfacePick(sphere)

    # Miss the sphere; project the fallback (3,0,0) -> (1,0,0).
    before = pick.pick(
        p1=(-5.0, 10.0, 0.0),
        p2=(5.0, 10.0, 0.0),
        fallback_point=(3.0, 0.0, 0.0),
    )
    assert before is not None
    assert list(before) == pytest.approx([1.0, 0.0, 0.0], abs=2e-2)

    # Rebuild the sphere at radius 2 in place (deep-copy new geometry in).
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
        "stale locator cache returned the old radius"
    )
