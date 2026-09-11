# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The contour mappers' point/plane accessors are callable FROM PYTHON.

VTK's Python wrapper takes a flat ``std::vector`` of scalars but neither
``std::array`` nor a nested container, and when it meets one it SKIPS the
method SILENTLY: the build stays green, C++ tests pass, and the method
simply does not exist from Python.  Both contour mappers declare their
real accessors with ``const std::array<float, 4>&``, so none of those
four reach Python.

That is invisible to a C++ test by construction, which is why this file
exists: it asserts REACHABILITY, not behaviour.  The behaviour is already
covered by the C++ mapper tests.

The rule this pins: any C++ method a Python pipeline must call needs a
wrappable signature AND a Python caller proving it -- a passing C++ test
is not evidence of either.

HARNESS: launched Slicer.  The wrapped VTKWidgets classes resolve only
via ``vtkSlicerLiverResectionsModuleVTKWidgetsPython``, which needs the
built module on the path, so a bare run SKIPS CLEANLY (ADR-0027).
"""

from __future__ import annotations

import pytest


def _widgets_namespace_or_skip():
    """The ONLY namespace these wrapped classes resolve from.

    Not ``slicer``, not ``vtk`` -- a resolver guessing those silently
    returns None and every downstream call becomes a no-op.
    """
    try:
        import vtkSlicerLiverResectionsModuleVTKWidgetsPython as widgets
    except Exception as exc:
        pytest.skip(f"VTKWidgets Python module not importable ({exc!r}) -- ADR-0027.")
    return widgets


def _mapper_or_skip(name):
    widgets = _widgets_namespace_or_skip()
    cls = getattr(widgets, name, None)
    if cls is None:
        pytest.skip(f"{name} absent from the VTKWidgets namespace (ADR-0027).")
    return cls()


@pytest.mark.parametrize(
    ("setter", "getter", "value"),
    [
        ("SetExternalPointWorld", "GetExternalPointWorld", (1.5, -2.5, 3.5)),
        ("SetReferencePointWorld", "GetReferencePointWorld", (-4.0, 5.0, 6.0)),
    ],
)
def test_distance_contour_point_accessors_round_trip_from_python(setter, getter, value):
    """The accessors exist in Python and round-trip a world point."""
    mapper = _mapper_or_skip("vtkOpenGLDistanceContourPolyDataMapper")

    assert hasattr(mapper, setter), (
        f"{setter} is missing from Python.  The std::array<float, 4> "
        "overload does not wrap, so a wrappable variant must exist or no "
        "Python pipeline can drive this mapper."
    )
    getattr(mapper, setter)(*value)
    read = tuple(getattr(mapper, getter)())

    assert read == pytest.approx(value), (
        "The wrappable accessor must round-trip through the float[4] "
        "storage; the W component is fixed to 1 and not exposed."
    )


@pytest.mark.parametrize(
    ("setter", "getter", "value"),
    [
        ("SetPlanePositionWorld", "GetPlanePositionWorld", (7.0, 8.0, 9.0)),
        ("SetPlaneNormalWorld", "GetPlaneNormalWorld", (0.0, 1.0, 0.0)),
    ],
)
def test_slicing_contour_plane_accessors_round_trip_from_python(setter, getter, value):
    """The sibling's accessors, pinned so the pair cannot drift apart."""
    mapper = _mapper_or_skip("vtkOpenGLSlicingContourPolyDataMapper")

    assert hasattr(mapper, setter), f"{setter} is missing from Python."
    getattr(mapper, setter)(*value)
    read = tuple(getattr(mapper, getter)())

    assert read == pytest.approx(value)


def test_the_std_array_overloads_are_absent_as_expected():
    """Documents WHY the World variants exist.

    Not a demand that the array overloads be hidden -- they are C++ API
    and should stay.  This pins the reason the wrappable pair is needed,
    so a future reader does not delete it as redundant.
    """
    mapper = _mapper_or_skip("vtkOpenGLDistanceContourPolyDataMapper")

    assert not hasattr(mapper, "SetExternalPoint"), (
        "If VTK ever learns to wrap std::array, this assertion fires and "
        "the World variants can be reconsidered -- until then they are "
        "the only way in from Python."
    )
