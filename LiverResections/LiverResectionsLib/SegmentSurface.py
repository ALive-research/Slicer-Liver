# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Surface extraction for a segmentation segment, by a CHOSEN method.

Two ways to turn a segment into a mesh, side by side:

``marching-cubes``
    Slicer's own closed-surface conversion.  Fast, exact about which
    voxels are in, and it inherits the labelmap's voxel staircase --
    which at CT resolution is a real feature of the output, not noise to
    be assumed away.

``poisson``
    Screened Poisson surface reconstruction (ADR-0040): sample the
    segment boundary as an oriented point cloud, then solve for the
    smooth surface whose indicator gradient best matches those normals.
    Slower, and it approximates rather than interpolates -- it will not
    reproduce a one-voxel spike, by design.

ADR-0040 §Conformance is explicit that PSR is offered ALONGSIDE marching
cubes, never as a silent replacement: *the surface a user gets is the one
they chose*.  That is why ``method`` is a required-by-default argument
threaded from the caller rather than a module-level mode, and why the
default here is the existing behaviour.  Neither method is "better" in
general -- staircase fidelity and smoothness are a trade the surgeon
makes, not one this module makes for them.

The two PSR steps are the wrapped Algorithm-library classes, so the whole
composition is Python (ADR-0004) over C++ primitives that were built to
be reachable from it.

References
----------
* ADR-0040 -- Poisson surface reconstruction from segmentations.
* ADR-0015 §1 -- pure-VTK Algorithm library, no MRML linkage.
* ``reference_algorithm_wrapped_class_namespace`` -- these classes
  resolve ONLY via the wrapped module, never ``slicer`` or plain ``vtk``.
"""

from __future__ import annotations

from typing import Any

import vtk

#: Slicer's closed-surface conversion.  The default: what callers got
#: before PSR existed, so adding PSR changes nothing until asked.
METHOD_MARCHING_CUBES = "marching-cubes"
#: Screened Poisson reconstruction (ADR-0040).
METHOD_POISSON = "poisson"

#: Binary-labelmap representation name (Slicer's canonical spelling).
_BINARY_LABELMAP = "Binary labelmap"
#: Closed-surface representation name.
_CLOSED_SURFACE = "Closed surface"

#: Cap on the oriented cloud handed to the solver.  A CT-resolution liver
#: boundary runs to several hundred thousand voxels, far past the point
#: where more samples change the fitted surface -- they only cost time.
#: The extractor subsamples by STRIDE, so this stays deterministic.
DEFAULT_MAX_POINTS = 200000


#: Segment tag recording which method produced the segment's CURRENT
#: closed-surface representation.  A tag rather than a node attribute
#: because the choice is per-segment: a case may want a smooth liver and
#: a staircase tumour, and one node-level flag cannot say that.
SURFACE_METHOD_TAG = "LiverSegmentation.SurfaceMethod"


def surface_methods() -> tuple[str, ...]:
    """The methods a caller may choose, in presentation order."""
    return (METHOD_MARCHING_CUBES, METHOD_POISSON)


def segment_surface(
    segmentation_node: Any,
    segment_id: str,
    method: str = METHOD_MARCHING_CUBES,
    depth: int | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> Any | None:
    """A polydata for ``segment_id``, extracted by ``method``.

    Returns ``None`` when there is nothing to extract or the chosen
    method cannot run -- an unknown method, or PSR without its wrapped
    C++ classes on the path.  ``None`` rather than a silent fallback to
    the other method: a caller who asked for PSR and got marching cubes
    without being told would be comparing the two and reading the same
    surface twice.
    """
    if segmentation_node is None or not segment_id:
        return None

    if method == METHOD_MARCHING_CUBES:
        return marching_cubes_surface(segmentation_node, segment_id)
    if method == METHOD_POISSON:
        return poisson_surface(
            segmentation_node, segment_id, depth=depth, max_points=max_points
        )
    return None


def marching_cubes_surface(segmentation_node: Any, segment_id: str) -> Any | None:
    """A deep-copied closed-surface polydata for ``segment_id``."""
    polydata = segmentation_node.GetClosedSurfaceInternalRepresentation(segment_id)
    if polydata is None:
        segmentation_node.CreateClosedSurfaceRepresentation()
        polydata = segmentation_node.GetClosedSurfaceInternalRepresentation(segment_id)
    if polydata is None:
        return None
    # Deep copy (the v1 pattern): the working mesh must not alias the
    # segmentation's internal representation, which conversions rebuild.
    copied = vtk.vtkPolyData()
    copied.DeepCopy(polydata)
    return copied


def poisson_surface(
    segmentation_node: Any,
    segment_id: str,
    depth: int | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> Any | None:
    """Reconstruct ``segment_id`` by screened Poisson (ADR-0040)."""
    labelmap, label = _segment_labelmap(segmentation_node, segment_id)
    if labelmap is None:
        return None
    return reconstruct_labelmap(labelmap, label, depth=depth, max_points=max_points)


def reconstruct_labelmap(
    labelmap: Any,
    label: int,
    depth: int | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> Any | None:
    """Oriented labelmap + label value -> reconstructed surface.

    Split out from ``poisson_surface`` because this half is pure VTK: it
    takes a ``vtkOrientedImageData`` and an integer and touches no MRML,
    which is what lets it be tested without a scene.
    """
    algorithm = _algorithm_module()
    if algorithm is None:
        return None
    extractor = getattr(algorithm, "vtkLiverOrientedPointCloudExtractor", None)
    reconstructor = getattr(algorithm, "vtkLiverPoissonSurfaceReconstruction", None)
    if extractor is None or reconstructor is None:
        return None

    # The geometry the extractor needs.  A segment's labelmap is
    # ORIENTED -- its image-to-world matrix carries spacing, direction
    # and origin together -- and the extractor takes that matrix whole
    # rather than being handed spacing separately, so an oblique
    # acquisition cannot be flattened to an axis-aligned assumption.
    ijk_to_ras = vtk.vtkMatrix4x4()
    if hasattr(labelmap, "GetImageToWorldMatrix"):
        labelmap.GetImageToWorldMatrix(ijk_to_ras)

    cloud = vtk.vtkPolyData()
    if not extractor.Extract(labelmap, ijk_to_ras, int(label), int(max_points), cloud):
        return None

    surface = vtk.vtkPolyData()
    chosen_depth = reconstructor.GetDefaultDepth() if depth is None else int(depth)
    if not reconstructor.Reconstruct(cloud, chosen_depth, surface):
        return None
    return surface


def _segment_labelmap(segmentation_node: Any, segment_id: str) -> tuple:
    """``(labelmap, labelValue)`` for ``segment_id``, or ``(None, 0)``.

    The LABEL VALUE matters as much as the image.  Stage 2's segments
    SHARE one binary-labelmap layer, so the image a segment hands back
    holds its neighbours' voxels too; only the segment's own value
    distinguishes it.  The extractor tests voxels for EQUALITY with this
    value for exactly that reason.
    """
    segmentation = segmentation_node.GetSegmentation()
    if segmentation is None:
        return None, 0
    segment = segmentation.GetSegment(segment_id)
    if segment is None:
        return None, 0

    labelmap = segment.GetRepresentation(_BINARY_LABELMAP)
    if labelmap is None:
        # A segmentation carrying only a closed surface can still be
        # asked for a labelmap; the conversion is what Slicer does
        # natively when a labelmap is needed.
        segmentation_node.CreateBinaryLabelmapRepresentation()
        labelmap = segment.GetRepresentation(_BINARY_LABELMAP)
    if labelmap is None:
        return None, 0

    return labelmap, int(segment.GetLabelValue())


def _algorithm_module() -> Any | None:
    """The wrapped Algorithm library, or ``None`` when it is off the path.

    Imported lazily and by its OWN module name.  These classes are not on
    ``slicer`` and not on plain ``vtk``; a resolver that looks there
    returns ``None`` and turns the whole feature into a silent no-op,
    which this project has shipped twice.
    """
    try:
        import vtkSlicerLiverResectionsModuleAlgorithmPython as algorithm
    except ImportError:
        return None
    return algorithm


def apply_surface_method(
    segmentation_node: Any,
    segment_id: str,
    method: str,
    depth: int | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
) -> bool:
    """Install ``method``'s surface AS the segment's closed surface.

    This is the single seam the choice travels through.  Slicer's
    closed-surface representation is what the 3D view renders, what
    ``TargetModel`` mints the hidden target mesh from, and therefore what
    the commit-boundary ring extraction runs against.  Writing the chosen
    surface there means every one of those consumers inherits the choice
    through the path it already uses -- no ``method`` argument threaded
    down a call chain, and no possibility of the rendered anatomy and the
    planned-against geometry disagreeing.

    Slicer holds an injected representation: it does not regenerate one
    that already exists, so a later ``CreateClosedSurfaceRepresentation``
    leaves this alone.  **An edit to the segment's labelmap does discard
    it**, and the surface reverts to marching cubes.  That is the right
    way round -- a reconstruction of voxels the user has since changed
    would be stale, and looking correct is what makes stale dangerous --
    but it means the tag below can go out of date, so treat it as a
    record of what was last applied, not a guarantee of what is there.

    Returns False and changes nothing when the surface cannot be built.
    """
    if segmentation_node is None or not segment_id:
        return False

    polydata = segment_surface(
        segmentation_node, segment_id, method=method, depth=depth, max_points=max_points
    )
    if polydata is None or polydata.GetNumberOfPoints() == 0:
        return False

    segmentation = segmentation_node.GetSegmentation()
    if segmentation is None:
        return False
    segment = segmentation.GetSegment(segment_id)
    if segment is None:
        return False

    segment.AddRepresentation(_CLOSED_SURFACE, polydata)
    segment.SetTag(SURFACE_METHOD_TAG, method)
    return True


def applied_surface_method(segmentation_node: Any, segment_id: str) -> str | None:
    """The method last applied to ``segment_id``, or ``None``.

    ``None`` means "nobody has chosen", which is not the same as
    "marching cubes was chosen" -- the caller decides what an absent
    choice defaults to, and the UI can tell the two apart.
    """
    if segmentation_node is None or not segment_id:
        return None
    segmentation = segmentation_node.GetSegmentation()
    if segmentation is None:
        return None
    segment = segmentation.GetSegment(segment_id)
    if segment is None:
        return None

    import vtk as _vtk

    value = _vtk.mutable("")
    if not segment.GetTag(SURFACE_METHOD_TAG, value):
        return None
    text = str(value)
    return text if text in surface_methods() else None
