# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Init-mode ring extractors must resolve their wrapped Algorithm classes.

Regression pin for the namespace mismatch that made ``run_ring_extraction`` a
silent no-op.  ``vtkLiverPlaneRingExtractor`` and ``vtkLiverSpheroidRingExtractor``
are **Algorithm-library** classes (``LiverResections/Algorithm/``); in a
launched Slicer they are exposed ONLY on
``vtkSlicerLiverResectionsModuleAlgorithmPython`` -- not on the ``slicer`` or
``vtk`` namespaces.  The Init Representations resolved them over
``("slicer", "vtk")``, so ``_resolve_extractor_class`` returned ``None`` on
every call and the plane/spheroid intersection rings were never extracted.

This is the same namespace gap caught in the locator producer
(``vtkLiverResectogramPixelMapping`` is Algorithm-library too).

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

The wrapped Algorithm classes are reachable only inside a launched Slicer with
the module loaded; under bare ``PythonSlicer -m pytest`` the
``vtkSlicerLiverResectionsModuleAlgorithmPython`` module is off the path, so
every test here SKIPS CLEANLY.  GL free -- no render window (the extractors are
pure CPU filters; the Representations are built with no renderer).

-- WHY THIS IS RED NOW (a true regression, not skip-pending) --

Under a launched Slicer these assertions FAIL today: the resolver looks in the
wrong namespaces, returns ``None``, and ``run_ring_extraction`` returns
``None``.  They go GREEN once the resolvers point at the Algorithm wrapping.

See also:
  * Docs/adr/0014-*.md §3  (wrapped-class relocation / namespaces)
  * Docs/adr/0019-resection-state-machine.md  (Init->Planning ring extraction)
  * LiverResections/Algorithm/vtkLiverPlaneRingExtractor.h
  * LiverResections/Algorithm/vtkLiverSpheroidRingExtractor.h
"""

from __future__ import annotations

import pytest

PLANE_EXTRACTOR_CLASS = "vtkLiverPlaneRingExtractor"
SPHEROID_EXTRACTOR_CLASS = "vtkLiverSpheroidRingExtractor"
ALGORITHM_PYTHON_MODULE = "vtkSlicerLiverResectionsModuleAlgorithmPython"


def _algorithm_module_or_skip():
    """Import the Algorithm Python wrapping or skip (bare pytest has it off path)."""
    try:
        return __import__(ALGORITHM_PYTHON_MODULE)
    except ImportError:
        pytest.skip(
            f"{ALGORITHM_PYTHON_MODULE} not importable -- the wrapped Algorithm "
            "classes are only reachable inside a launched Slicer with the module "
            "loaded.  Runs under the launched-Slicer `pytest_launched` row."
        )


def _vtk_or_skip():
    """Import ``vtk`` (for the target mesh source) or skip cleanly."""
    try:
        import vtk

        return vtk
    except ImportError:
        pytest.skip("vtk not importable in this environment.")


def _plane_representation_or_skip():
    try:
        from LiverResectionsLib.Representations.SlicingPlaneInitRepresentation import (
            SlicingPlaneInitRepresentation,
            _resolve_extractor_class,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"SlicingPlaneInitRepresentation not importable ({exc!r}).")
    return SlicingPlaneInitRepresentation, _resolve_extractor_class


def _spheroid_representation_or_skip():
    try:
        from LiverResectionsLib.Representations.DistanceSpheroidInitRepresentation import (
            DistanceSpheroidInitRepresentation,
            _resolve_extractor_class,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"DistanceSpheroidInitRepresentation not importable ({exc!r}).")
    return DistanceSpheroidInitRepresentation, _resolve_extractor_class


class _FakePlaneDataNode:
    """Duck-typed stand-in exposing the SlicingPlane vec3 accessors."""

    def __init__(self, origin, normal):
        self._origin = origin
        self._normal = normal

    def GetSlicingPlaneOrigin(self):
        return self._origin

    def GetSlicingPlaneNormal(self):
        return self._normal


class _FakeSpheroidDataNode:
    """Duck-typed stand-in exposing the DistanceSpheroid center + radii accessors."""

    def __init__(self, center, radii):
        self._center = center
        self._rx, self._ry, self._rz = radii

    def GetDistanceSpheroidCenter(self):
        return self._center

    def GetDistanceSpheroidRadiusX(self):
        return self._rx

    def GetDistanceSpheroidRadiusY(self):
        return self._ry

    def GetDistanceSpheroidRadiusZ(self):
        return self._rz


def _target_sphere(vtk, radius=50.0):
    """A closed triangulated sphere mesh the extractors intersect."""
    source = vtk.vtkSphereSource()
    source.SetRadius(radius)
    source.SetThetaResolution(48)
    source.SetPhiResolution(48)
    source.Update()
    return source.GetOutput()


# --------------------------------------------------------------------------
# Resolution invariant -- the direct pin on the namespace bug.
# --------------------------------------------------------------------------


def test_plane_extractor_class_resolves_to_the_algorithm_wrapping():
    """The plane ring extractor resolves to a real class, not None."""
    algorithm = _algorithm_module_or_skip()
    _, resolve = _plane_representation_or_skip()

    expected = getattr(algorithm, PLANE_EXTRACTOR_CLASS, None)
    assert expected is not None, (
        f"{PLANE_EXTRACTOR_CLASS} is missing from {ALGORITHM_PYTHON_MODULE} -- "
        "test premise broken."
    )
    resolved = resolve(PLANE_EXTRACTOR_CLASS)
    assert resolved is not None, (
        f"_resolve_extractor_class returned None for {PLANE_EXTRACTOR_CLASS}; the "
        "Algorithm-library class is not reachable from the namespaces the resolver "
        "checks -- ring extraction silently no-ops (ADR-0014 §3)."
    )
    assert resolved is expected


def test_spheroid_extractor_class_resolves_to_the_algorithm_wrapping():
    """The spheroid ring extractor resolves to a real class, not None."""
    algorithm = _algorithm_module_or_skip()
    _, resolve = _spheroid_representation_or_skip()

    expected = getattr(algorithm, SPHEROID_EXTRACTOR_CLASS, None)
    assert expected is not None, (
        f"{SPHEROID_EXTRACTOR_CLASS} is missing from {ALGORITHM_PYTHON_MODULE} -- "
        "test premise broken."
    )
    resolved = resolve(SPHEROID_EXTRACTOR_CLASS)
    assert resolved is not None, (
        f"_resolve_extractor_class returned None for {SPHEROID_EXTRACTOR_CLASS}; the "
        "Algorithm-library class is not reachable from the namespaces the resolver "
        "checks -- ring extraction silently no-ops (ADR-0014 §3)."
    )
    assert resolved is expected


# --------------------------------------------------------------------------
# Behavioral invariant -- the plane through a sphere yields a non-empty ring.
# --------------------------------------------------------------------------


def test_plane_ring_extraction_produces_a_non_empty_ring():
    """run_ring_extraction returns a ring with points for a plane through a sphere."""
    _algorithm_module_or_skip()
    vtk = _vtk_or_skip()
    representation_cls, _ = _plane_representation_or_skip()

    representation = representation_cls()
    representation._data_node = _FakePlaneDataNode(
        origin=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0)
    )
    mesh = _target_sphere(vtk)

    ring = representation.run_ring_extraction(mesh)
    assert ring is not None, (
        "run_ring_extraction returned None for a plane through the sphere centre -- "
        "the extractor class did not resolve (silent no-op)."
    )
    assert ring.GetNumberOfPoints() > 0, (
        "The equatorial intersection ring is empty; the extractor resolved but "
        "produced no geometry."
    )
