# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stage-2 (Anatomy) distance-map computation (issue #538).

Ports the v1 distance-map algorithm into the v2 workflow: for each anatomical
channel a **signed Maurer distance map**, composed into one multi-component
volume the resection mappers consume (``vtkMRMLResectionPlanNode`` distance-map
reference; the ``vtkOpenGLBezierResectionPolyDataMapper`` shader reads the
per-channel distances for the resection margins / colouring).

Two layers:

* PURE core -- ``signed_distance_map`` / ``compose_distance_map`` -- SimpleITK
  only, no Slicer scene, unit-tested in bare pytest.
* Slicer-coupled -- ``compute_distance_map_for_segmentation`` -- resolves the
  SCT-tagged canonical segments (ADR-0011), exports each to a labelmap, and
  composes the channels onto an output vector volume node.  Triggered on the
  Stage-2 accept transition (ADR-0023 §Stage 2; phase contracts #440).

Channel order matches v1: ``[tumour, parenchyma, hepatic, portal]``; absent
channels are skipped (so component indices are dense over the present channels).
Parenchyma (the liver) is the required channel -- the resection needs it.
"""

from __future__ import annotations

from typing import Any

# SCT codes identifying the canonical segments (ADR-0011).  Keyed by the v1
# channel order.
CHANNEL_SCT_CODES = {
    "tumor": "4147007",       # Mass (SCT)
    "parenchyma": "10200004",  # Liver (SCT)
    "hepatic": "8993003",      # Hepatic vein (SCT)
    "portal": "32764006",      # Portal vein (SCT)
}
CHANNEL_ORDER = ("tumor", "parenchyma", "hepatic", "portal")

# v1 SignedMaurerDistanceMap flags (image, insideIsPositive, squaredDistance,
# useImageSpacing) == (image, False, False, True): signed (inside < 0), true
# Euclidean distance in world units.
_MAURER_INSIDE_IS_POSITIVE = False
_MAURER_SQUARED = False
_MAURER_USE_IMAGE_SPACING = True


def signed_distance_map(labelmap_image: Any) -> Any:
    """Signed Maurer distance map of a binary ``labelmap_image`` (SimpleITK).

    Inside the label is negative, outside positive, in world units -- matching
    the v1 convention the resection shader expects.
    """
    import SimpleITK as sitk

    return sitk.SignedMaurerDistanceMap(
        labelmap_image,
        _MAURER_INSIDE_IS_POSITIVE,
        _MAURER_SQUARED,
        _MAURER_USE_IMAGE_SPACING,
    )


def compose_distance_map(channel_images: list, downsampling_rate: float = 1) -> Any:
    """Compose per-channel signed distance maps into one multi-component image.

    ``channel_images`` is an ordered list aligned to :data:`CHANNEL_ORDER`;
    ``None`` entries (absent channels) are skipped.  Returns the composed
    SimpleITK image, or ``None`` when no channel is present.  A single present
    channel returns a one-component image (no ``Compose`` needed).
    """
    import SimpleITK as sitk

    present = [img for img in channel_images if img is not None]
    if not present:
        return None

    distances = [signed_distance_map(img) for img in present]

    if downsampling_rate and downsampling_rate != 1:
        distances = [
            _resample(sitk, d, downsampling_rate) for d in distances
        ]

    if len(distances) == 1:
        return distances[0]
    return sitk.Compose(*distances)


def _resample(sitk: Any, image: Any, downsampling_rate: float) -> Any:
    """Downsample ``image`` by ``downsampling_rate`` with linear interpolation.

    Mirrors the v1 origin/spacing recentring so the resampled map stays aligned
    with the input geometry.
    """
    size = image.GetSize()
    spacing = image.GetSpacing()
    origin = image.GetOrigin()
    direction = image.GetDirection()

    new_size = [max(1, round(n / downsampling_rate)) for n in size]
    physical = [spacing[i] * size[i] for i in range(3)]
    new_spacing = [physical[i] / float(new_size[i]) for i in range(3)]
    # Recentre the output origin for the changed spacing (v1 imageResample).
    new_origin = [
        origin[i] + (new_spacing[i] / 2.0 - spacing[i] / 2.0) * direction[i * 4]
        for i in range(3)
    ]

    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing(new_spacing)
    resampler.SetSize([int(n) for n in new_size])
    resampler.SetOutputOrigin(new_origin)
    resampler.SetOutputDirection(direction)
    resampler.SetInterpolator(sitk.sitkLinear)
    return resampler.Execute(image)


def compute_distance_map_for_segmentation(
    segmentation_node: Any,
    reference_volume_node: Any,
    output_volume_node: Any,
    downsampling_rate: float = 1,
) -> Any:
    """Compute the composed distance map for a canonical segmentation.

    Resolves each SCT-tagged channel segment (ADR-0011), exports it to a
    labelmap against ``reference_volume_node``, and composes the per-channel
    signed distance maps onto ``output_volume_node`` (a
    ``vtkMRMLVectorVolumeNode``), tagged ``DistanceMap`` / ``Computed`` so the
    resection distance-map selectors pick it up.  Returns ``output_volume_node``
    on success, ``None`` when no channel (not even parenchyma) resolves.
    """
    import sitkUtils
    import slicer
    import vtk

    seg = segmentation_node.GetSegmentation()

    channel_images = []
    for channel in CHANNEL_ORDER:
        segment_id = _segment_id_for_sct(seg, CHANNEL_SCT_CODES[channel])
        if segment_id is None:
            channel_images.append(None)
            continue
        labelmap = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode", f"__dmap_{channel}"
        )
        ids = vtk.vtkStringArray()
        ids.InsertNextValue(segment_id)
        slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
            segmentation_node, ids, labelmap, reference_volume_node
        )
        channel_images.append(sitkUtils.PullVolumeFromSlicer(labelmap))
        slicer.mrmlScene.RemoveNode(labelmap)

    composed = compose_distance_map(channel_images, downsampling_rate)
    if composed is None:
        return None

    sitkUtils.PushVolumeToSlicer(
        composed, targetNode=output_volume_node, className="vtkMRMLVectorVolumeNode"
    )
    output_volume_node.SetAttribute("DistanceMap", "True")
    output_volume_node.SetAttribute("Computed", "True")
    return output_volume_node


def _segment_id_for_sct(segmentation: Any, sct_code: str) -> Any:
    """Return the segment id whose terminology entry carries ``sct_code``.

    Scans the segments' ``TerminologyEntry`` tag for the ``SCT^<code>^`` marker
    the canonical import writes (ADR-0011), mirroring the C++ resolver in
    ``vtkSlicerVascularTerritoriesLogic::GetLiverSegmentId`` and the Python
    reader ``LiverSegmentationLogic._sctTagTexts`` (``vtk.reference`` out-param:
    ``vtkSegment.GetTag`` takes a ``std::string&``, not a Python list).
    """
    import vtk

    marker = f"SCT^{sct_code}^"
    for i in range(segmentation.GetNumberOfSegments()):
        segment = segmentation.GetNthSegment(i)
        entry = vtk.reference("")
        if not segment.GetTag("TerminologyEntry", entry):
            continue
        if marker in str(entry):
            return segmentation.GetNthSegmentID(i)
    return None
