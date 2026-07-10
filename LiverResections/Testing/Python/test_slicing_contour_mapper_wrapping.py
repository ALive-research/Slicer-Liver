# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python-wrappable plane accessors on the slicing-contour shader mapper.

The v1 initialization's live contour is SHADER-based: the whole liver
renders through ``vtkOpenGLSlicingContourPolyDataMapper`` and the
fragment shader keeps only a thin band around the bisector plane
(maintainer requirement: shader-based, no CPU-cutter substitute).  The
original plane setters take ``std::array<float, 4>`` and do not
Python-wrap; the LayerDM Init Representation drives the shader from
Python (ADR-0014 §3), so the mapper needs wrappable overloads.
"""

from __future__ import annotations

import pytest


def _mapper_or_skip():
    from slicer_pytest_support import import_slicer_or_skip

    import_slicer_or_skip()
    try:
        import vtkSlicerLiverResectionsModuleVTKWidgetsPython as widgets
    except ImportError:
        pytest.skip(
            "vtkSlicerLiverResectionsModuleVTKWidgetsPython not importable "
            "-- wrapped VTKWidgets classes need a launched Slicer."
        )
    mapper = widgets.vtkOpenGLSlicingContourPolyDataMapper()
    if mapper is None:
        pytest.skip("vtkOpenGLSlicingContourPolyDataMapper not constructible.")
    return mapper


def test_plane_accessors_round_trip_from_python():
    """SetPlanePositionWorld/SetPlaneNormalWorld wrap and round-trip."""
    mapper = _mapper_or_skip()

    assert hasattr(mapper, "SetPlanePositionWorld"), (
        "the std::array plane setters do not Python-wrap; the mapper must "
        "expose the wrappable World overloads for the Init Representation."
    )
    mapper.SetPlanePositionWorld(1.0, 2.0, 3.0)
    mapper.SetPlaneNormalWorld(0.0, 1.0, 0.0)
    assert tuple(mapper.GetPlanePositionWorld()) == pytest.approx((1.0, 2.0, 3.0))
    assert tuple(mapper.GetPlaneNormalWorld()) == pytest.approx((0.0, 1.0, 0.0))


def test_contour_visibility_and_thickness_wrap():
    mapper = _mapper_or_skip()
    mapper.SetContourThickness(2.0)
    mapper.SetContourVisibility(True)
    assert mapper.GetContourThickness() == pytest.approx(2.0)
    assert mapper.GetContourVisibility() is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
