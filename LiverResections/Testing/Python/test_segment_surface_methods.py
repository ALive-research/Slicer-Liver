# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Tests for ``LiverResectionsLib.SegmentSurface`` (ADR-0040 phase 4).

-- WHY THIS IS A LAUNCHED-SLICER PYTEST --

The Poisson path composes two wrapped Algorithm-library classes, which
are reachable only inside a launched Slicer with the module loaded.
Under bare ``PythonSlicer -m pytest`` the wrapped module is off the path
and every Poisson test here SKIPS CLEANLY.  The dispatch tests, which
touch no C++, run in both.

The point of this file is the CHOICE, which ADR-0040 §Conformance makes
a requirement rather than a nicety: *PSR is offered alongside marching
cubes, not as a silent replacement -- the surface a user gets is the one
they chose.*  A test suite that only checked "PSR produces a mesh" would
pass just as happily if PSR had quietly become the only option, or if
asking for it had quietly returned marching cubes.
"""

from __future__ import annotations

import pytest

vtk = pytest.importorskip("vtk", reason="VTK is required for surface extraction tests.")


@pytest.fixture(scope="module")
def segment_surface():
    """The module under test, package-imported or loaded from source.

    The source-path fallback is what lets the CHOICE tests run in the
    bare row.  ``LiverResectionsLib`` is loadable-module Python and is
    not importable outside a launched Slicer, so a plain package import
    would make every test here skip -- and a green row that only ever
    skips is worth nothing, a lesson this project has paid for more than
    once (#449, #454, #459, #460).

    Loading by path is safe precisely because of how this module is
    written: at import time it needs ``vtk`` and nothing else -- no
    ``slicer``, no MRML, no wrapped C++.  The Algorithm classes are
    resolved lazily, inside the functions that use them, so the
    reconstruction tests still skip here while the dispatch tests run.
    If that ever stops being true this fixture will fail loudly rather
    than quietly skip, which is the right way round.
    """
    try:
        from LiverResectionsLib import SegmentSurface

        return SegmentSurface
    except ImportError:
        pass

    import importlib.util
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[2]
        / "LiverResectionsLib"
        / "SegmentSurface.py"
    )
    if not source.is_file():
        pytest.skip(f"SegmentSurface.py not found at {source}.")
    spec = importlib.util.spec_from_file_location("SegmentSurface", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def algorithm():
    """The wrapped Algorithm library, or a skip."""
    return pytest.importorskip(
        "vtkSlicerLiverResectionsModuleAlgorithmPython",
        reason=(
            "vtkSlicerLiverResectionsModuleAlgorithm not built / not on "
            "sys.path; skip the Poisson half of the surface tests."
        ),
    )


def _sphere_labelmap(radius=12, label=3, shape=40, spacing=(1.0, 1.0, 1.0)):
    """A labelmap holding a solid sphere of ``label`` voxels.

    Returned as a plain ``vtkImageData`` with an explicit matrix, so this
    fixture needs no MRML and no Slicer scene.
    """
    image = vtk.vtkImageData()
    image.SetDimensions(shape, shape, shape)
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    image.GetPointData().GetScalars().Fill(0)

    centre = shape // 2
    for k in range(shape):
        for j in range(shape):
            for i in range(shape):
                dx, dy, dz = i - centre, j - centre, k - centre
                if dx * dx + dy * dy + dz * dz <= radius * radius:
                    image.SetScalarComponentFromDouble(i, j, k, 0, label)

    matrix = vtk.vtkMatrix4x4()
    for axis in range(3):
        matrix.SetElement(axis, axis, spacing[axis])
    return image, matrix, label


# --------------------------------------------------------------------------- #
# The choice itself.  These need no C++ and no scene.
# --------------------------------------------------------------------------- #


def test_both_methods_are_offered(segment_surface):
    """Marching cubes must remain on the menu, and be listed first.

    ADR-0040 offers PSR ALONGSIDE marching cubes. If PSR ever became the
    only entry, every caller would silently switch -- which is exactly
    the outcome the ADR forbids.
    """
    methods = segment_surface.surface_methods()
    assert segment_surface.METHOD_MARCHING_CUBES in methods
    assert segment_surface.METHOD_POISSON in methods
    assert methods[0] == segment_surface.METHOD_MARCHING_CUBES


def test_an_unknown_method_returns_none_rather_than_guessing(segment_surface):
    """A typo must not silently produce the other method's surface.

    Returning a surface for an unrecognised name is worse than returning
    nothing: the caller believes they got what they asked for.
    """
    assert segment_surface.segment_surface(object(), "seg", method="spline") is None


def test_missing_inputs_are_a_no_op(segment_surface):
    assert segment_surface.segment_surface(None, "seg") is None
    assert segment_surface.segment_surface(object(), "") is None


def test_the_default_method_is_marching_cubes(segment_surface):
    """The default is the PREVIOUS behaviour.

    Landing a new reconstruction method must change nothing for anyone
    who did not ask for it. Asserted through the real dispatcher with a
    recording stub, rather than by reading the signature's default, so a
    later refactor that moves the default elsewhere still trips this.
    """
    calls = []

    class RecordingSegmentation:
        def GetClosedSurfaceInternalRepresentation(self, segment_id):
            calls.append(segment_id)
            return vtk.vtkPolyData()

    result = segment_surface.segment_surface(RecordingSegmentation(), "liver")
    assert calls == ["liver"], "the default did not take the marching-cubes path"
    assert result is not None


# --------------------------------------------------------------------------- #
# The Poisson path.  Needs the wrapped C++ classes.
# --------------------------------------------------------------------------- #


def test_poisson_reconstructs_a_labelmap(segment_surface, algorithm):
    image, matrix, label = _sphere_labelmap()

    surface = segment_surface.reconstruct_labelmap(image, label)

    assert surface is not None
    assert surface.GetNumberOfPoints() > 0
    assert surface.GetNumberOfPolys() > 0


def test_poisson_lands_on_the_labelled_object(segment_surface, algorithm):
    """The surface must sit where the voxels are.

    A reconstruction returned in the solver's own normalised cube would
    still be a valid non-empty mesh, so bounds are what actually
    distinguishes a wired pipeline from a plausible-looking one.
    """
    radius, shape = 12, 40
    image, matrix, label = _sphere_labelmap(radius=radius, shape=shape)

    surface = segment_surface.reconstruct_labelmap(image, label)
    assert surface is not None

    bounds = surface.GetBounds()
    centre = shape // 2
    for axis in range(3):
        low, high = bounds[2 * axis], bounds[2 * axis + 1]
        assert low == pytest.approx(centre - radius, abs=0.15 * radius)
        assert high == pytest.approx(centre + radius, abs=0.15 * radius)


def test_poisson_ignores_voxels_of_another_label(segment_surface, algorithm):
    """A neighbouring structure must not bleed into the reconstruction.

    Stage 2's segments SHARE one binary-labelmap layer, so the image a
    segment hands back holds its neighbours' voxels too. Reconstructing
    on "non-zero" rather than "equal to my label" would fuse them into
    one surface -- a wrong result that looks entirely plausible.
    """
    shape, inner_radius, outer_radius = 48, 8, 20
    image, matrix, _ = _sphere_labelmap(radius=inner_radius, label=3, shape=shape)

    # A second, larger structure under a DIFFERENT label, wrapped around
    # the first without touching it.
    centre = shape // 2
    for k in range(shape):
        for j in range(shape):
            for i in range(shape):
                dx, dy, dz = i - centre, j - centre, k - centre
                d2 = dx * dx + dy * dy + dz * dz
                if inner_radius * inner_radius < d2 <= outer_radius * outer_radius:
                    image.SetScalarComponentFromDouble(i, j, k, 0, 7)

    surface = segment_surface.reconstruct_labelmap(image, 3)
    assert surface is not None

    worst = 0.0
    for index in range(surface.GetNumberOfPoints()):
        x, y, z = surface.GetPoint(index)
        dx, dy, dz = x - centre, y - centre, z - centre
        worst = max(worst, (dx * dx + dy * dy + dz * dz) ** 0.5)

    assert worst < 0.5 * (inner_radius + outer_radius), (
        f"the reconstruction reaches radius {worst:.1f}, into the "
        f"label-7 shell at {inner_radius}..{outer_radius}"
    )


def test_depth_is_the_adapter_default_when_unspecified(segment_surface, algorithm):
    """An unspecified depth must mean the ADR's 7, resolved at one place."""
    reconstructor = algorithm.vtkLiverPoissonSurfaceReconstruction
    assert reconstructor.GetDefaultDepth() == 7

    image, matrix, label = _sphere_labelmap()
    implicit = segment_surface.reconstruct_labelmap(image, label)
    explicit = segment_surface.reconstruct_labelmap(
        image, label, depth=reconstructor.GetDefaultDepth()
    )

    assert implicit is not None and explicit is not None
    # The extractor subsamples by stride and the solver is deterministic,
    # so "same depth" must mean literally the same mesh.
    assert implicit.GetNumberOfPoints() == explicit.GetNumberOfPoints()
    assert implicit.GetNumberOfPolys() == explicit.GetNumberOfPolys()


def test_an_absent_label_yields_no_surface(segment_surface, algorithm):
    """Asking for a label that is not present is not an error, but it is
    not a surface either -- and must not return the whole volume."""
    image, matrix, _ = _sphere_labelmap(label=3)
    assert segment_surface.reconstruct_labelmap(image, 99) is None


# --------------------------------------------------------------------------- #
# The apply seam: the chosen surface BECOMES the segment's closed surface, so
# every downstream consumer inherits the choice through the path it already
# uses.  Needs a real scene, so these are launched-only.
# --------------------------------------------------------------------------- #


@pytest.fixture
def scene_segment():
    """A labelmap-backed segment in a real scene, or a skip."""
    slicer = pytest.importorskip(
        "slicer", reason="a MRML scene is required for the apply-seam tests."
    )
    if not hasattr(slicer, "vtkSlicerSegmentationsModuleLogic"):
        pytest.skip("Segmentations logic unavailable outside a launched Slicer.")

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "psr-test")
    node.CreateDefaultDisplayNodes()

    # A NON-ZERO extent on purpose. A segment's labelmap is cropped to its
    # own bounding box, and a zero-based fixture cannot tell a correct
    # index mapping from one that drops the offset -- which is exactly the
    # bug this pipeline shipped and the phase-4 eyeball caught.
    image = vtk.vtkImageData()
    image.SetExtent(10, 49, 20, 59, 5, 44)
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    image.GetPointData().GetScalars().Fill(0)
    for k in range(5, 45):
        for j in range(20, 60):
            for i in range(10, 50):
                if (i - 30) ** 2 + (j - 40) ** 2 + (k - 25) ** 2 <= 14 * 14:
                    image.SetScalarComponentFromDouble(i, j, k, 0, 1)

    oriented = slicer.vtkOrientedImageData()
    oriented.DeepCopy(image)
    segment_id = node.GetSegmentation().AddEmptySegment("psr-seg")
    slicer.vtkSlicerSegmentationsModuleLogic.SetBinaryLabelmapToSegment(
        oriented, node, segment_id
    )
    yield node, segment_id
    slicer.mrmlScene.RemoveNode(node)


def test_applying_poisson_replaces_the_closed_surface(
    segment_surface, algorithm, scene_segment
):
    """The installed surface must be the one consumers read back.

    This is the whole architecture in one assertion: if the injected mesh
    does not survive read-back, the choice would have to be threaded
    through every consumer separately, and the rendered anatomy could
    disagree with the geometry the plan is built on.
    """
    node, segment_id = scene_segment

    node.CreateClosedSurfaceRepresentation()
    native = node.GetClosedSurfaceInternalRepresentation(segment_id)
    native_points = native.GetNumberOfPoints()
    assert native_points > 0

    assert segment_surface.apply_surface_method(
        node, segment_id, segment_surface.METHOD_POISSON
    )

    applied = node.GetClosedSurfaceInternalRepresentation(segment_id)
    assert applied.GetNumberOfPoints() > 0
    assert applied.GetNumberOfPoints() != native_points, (
        "the closed surface is unchanged -- the Poisson mesh was not installed"
    )
    assert (
        segment_surface.applied_surface_method(node, segment_id)
        == segment_surface.METHOD_POISSON
    )


def test_an_installed_surface_survives_a_reconversion_request(
    segment_surface, algorithm, scene_segment
):
    """CreateClosedSurfaceRepresentation must not silently undo the choice.

    Slicer does not regenerate a representation that already exists, and
    several code paths call this defensively. If it DID regenerate, the
    choice would evaporate at an arbitrary later moment.
    """
    node, segment_id = scene_segment
    assert segment_surface.apply_surface_method(
        node, segment_id, segment_surface.METHOD_POISSON
    )
    installed = node.GetClosedSurfaceInternalRepresentation(
        segment_id
    ).GetNumberOfPoints()

    node.CreateClosedSurfaceRepresentation()

    assert (
        node.GetClosedSurfaceInternalRepresentation(segment_id).GetNumberOfPoints()
        == installed
    )


def test_the_target_mesh_inherits_the_installed_surface(
    segment_surface, algorithm, scene_segment
):
    """The point of the seam: TargetModel gets the choice for free.

    ``_liver_closed_surface`` reads the closed-surface representation, so
    installing there is what makes the hidden target mesh -- and the ring
    extraction that runs against it -- use the chosen surface without any
    argument being threaded to them.
    """
    try:
        from LiverResectionsLib import TargetModel
    except ImportError:
        pytest.skip("LiverResectionsLib.TargetModel not importable.")

    node, segment_id = scene_segment
    assert segment_surface.apply_surface_method(
        node, segment_id, segment_surface.METHOD_POISSON
    )
    installed = node.GetClosedSurfaceInternalRepresentation(
        segment_id
    ).GetNumberOfPoints()

    mesh = TargetModel._liver_closed_surface(node, segment_id)
    assert mesh is not None
    assert mesh.GetNumberOfPoints() == installed


def test_no_method_applied_reads_as_none_not_as_a_default(
    segment_surface, scene_segment
):
    """"Nobody chose" and "marching cubes was chosen" are different states.

    The UI has to tell them apart to show an honest initial value.
    """
    node, segment_id = scene_segment
    assert segment_surface.applied_surface_method(node, segment_id) is None
