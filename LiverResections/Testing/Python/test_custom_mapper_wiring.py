# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Custom-OpenGL-mapper wiring -- the Representations drive the REAL mappers.

Sibling of ``test_bezier_planning_surface_mapper_wiring.py``, which already pins
"the Planning surface mapper IS the real ``vtkOpenGLBezierResectionPolyDataMapper``
in launched Slicer."  This file extends that invariant to the OTHER
Representations that carry a custom OpenGL shader mapper (relocated to
``LiverResections/VTKWidgets/`` per ADR-0014 §3):

  * ``DistanceSpheroidInitRepresentation`` -- its spheroid contour mapper IS the
    real ``vtkOpenGLDistanceContourPolyDataMapper`` (the triaxial-ellipsoid
    banding shader, ADR-0015 §"Stack 4").
  * ``VascularContourRepresentation`` -- its two overlay mappers ARE the real
    ``vtkOpenGLDistanceContourPolyDataMapper`` + ``vtkOpenGLSlicingContourPolyDataMapper``.
  * ``FlattenedSurfaceRepresentation`` -- its 2D resection mapper IS the real
    ``vtkOpenGLResection2DPolyDataMapper``.

These assertions are the invariant that makes it SAFE to convert the
"custom mapper unresolved -> silent generic ``vtkPolyDataMapper`` fallback" into
a LOUD hard requirement: once the mapper MUST be the real class under launched
Slicer, a resolver miss is a misconfiguration to surface, not a shader-less
degradation to tolerate (ADR-0008 §2 -- the "no-VTK unit layer" the fallback
aspired to was never built).

Genuinely-generic mappers (the ``DistanceSpheroidInit`` sphere markers, the
``SlicingPlaneInit`` plane mapper, the ``Confirmed`` surface mapper whose custom
relocation has not landed) are DELIBERATELY not pinned here -- they are correct
as plain ``vtkPolyDataMapper`` and must stay that way (no "colour-of-the-sky"
absence assertions).

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

The custom mappers (LiverResections VTKWidgets) are wrapped-C++ classes reachable
only inside a launched Slicer with the module loaded; a bare
``PythonSlicer -m pytest`` has ``slicer.mrmlScene is None`` and the wrapped
classes off the path, so this SKIPS CLEANLY via the shared
``slicer_pytest_support`` guards.  The Representations are plain Python + VTK;
the tests need no render window.

See also:
  * Docs/adr/0014-livermarkups-dissolution.md §3   (mapper relocation)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §6     (Representations as pipelines)
  * Docs/adr/0008-testing-strategy.md §2             (the unbuilt no-VTK layer)
  * LiverResections/Testing/Python/test_bezier_planning_surface_mapper_wiring.py
"""

from __future__ import annotations

import pytest

DISTANCE_CONTOUR_MAPPER_CLASS = "vtkOpenGLDistanceContourPolyDataMapper"
SLICING_CONTOUR_MAPPER_CLASS = "vtkOpenGLSlicingContourPolyDataMapper"
RESECTION_2D_MAPPER_CLASS = "vtkOpenGLResection2DPolyDataMapper"


def _slicer_or_skip():
    """Resolve a launched ``slicer`` module or skip cleanly under bare pytest."""
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_or_skip(module_name, class_name):
    """Import ``class_name`` from ``LiverResectionsLib.Representations.<module>``.

    Skips cleanly when the Representation is not importable in this environment
    (a bare-pytest run skips earlier via ``_slicer_or_skip``).
    """
    try:
        module = __import__(
            f"LiverResectionsLib.Representations.{module_name}",
            fromlist=[class_name],
        )
        return getattr(module, class_name)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{class_name} not importable ({exc!r}) -- the Representation is "
            "not reachable in this environment."
        )


def _assert_is_real_mapper(mapper, expected_class):
    """Assert ``mapper`` is the real wrapped ``expected_class``.

    Mirrors ``test_bezier_planning_surface_mapper_wiring._require_real_mapper``'s
    positive pin: under launched Slicer the custom mapper MUST resolve to the
    relocated real class (ADR-0014 §3), never the generic ``vtkPolyDataMapper``.
    """
    assert mapper is not None, (
        f"Representation must construct its {expected_class} mapper; got None."
    )
    assert mapper.IsA(expected_class), (
        f"mapper must be the relocated real {expected_class} (ADR-0014 §3), "
        f"got {type(mapper).__name__}."
    )


def test_distance_spheroid_uses_real_distance_contour_mapper():
    """The spheroid contour mapper is the real ``vtkOpenGLDistanceContourPolyDataMapper``.

    ``DistanceSpheroidInitRepresentation`` bands the triaxial-ellipsoid implicit
    through the custom distance-contour shader (ADR-0015 §"Stack 4"); the sphere
    MARKER mappers stay generic and are intentionally not pinned here.
    """
    _slicer_or_skip()
    rep_class = _import_or_skip(
        "DistanceSpheroidInitRepresentation", "DistanceSpheroidInitRepresentation"
    )
    rep = rep_class()
    _assert_is_real_mapper(rep.GetSpheroidMapper(), DISTANCE_CONTOUR_MAPPER_CLASS)


def test_vascular_contour_uses_real_contour_mappers():
    """Both vascular-overlay mappers are the real custom contour mappers.

    ``VascularContourRepresentation`` renders the distance- and slicing-contour
    overlays through the relocated ``vtkOpenGLDistanceContourPolyDataMapper`` and
    ``vtkOpenGLSlicingContourPolyDataMapper`` (ADR-0014 §3, ADR-0025 §Context).
    """
    _slicer_or_skip()
    rep_class = _import_or_skip(
        "VascularContourRepresentation", "VascularContourRepresentation"
    )
    rep = rep_class()
    _assert_is_real_mapper(
        rep.GetDistanceContourMapper(), DISTANCE_CONTOUR_MAPPER_CLASS
    )
    _assert_is_real_mapper(
        rep.GetSlicingContourMapper(), SLICING_CONTOUR_MAPPER_CLASS
    )


def test_flattened_surface_uses_real_resection_2d_mapper():
    """The resectogram 2D mapper is the real ``vtkOpenGLResection2DPolyDataMapper``.

    ``FlattenedSurfaceRepresentation`` samples the distance field through the
    relocated 2D resection mapper's ``sampler3D`` (ADR-0025 §Context).
    """
    _slicer_or_skip()
    rep_class = _import_or_skip(
        "FlattenedSurfaceRepresentation", "FlattenedSurfaceRepresentation"
    )
    rep = rep_class()
    _assert_is_real_mapper(
        rep.GetResectionMapper2D(), RESECTION_2D_MAPPER_CLASS
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
