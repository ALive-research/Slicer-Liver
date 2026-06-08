# Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Signed-Maurer distance-maps compute for the resection stage.

This module hosts the distance-maps pipeline that historically lived on
the orphaned ``LiverLogic`` class embedded in ``Liver/Liver.py`` (and
later parked in ``Liver/LiverLib/legacy_logic.py``).  Per ADR-0023
§"Shell composition (Option H)" — "The Liver shell holds no domain
logic — only composition + navigation" — the compute relocates out of
the shell into the module that owns it.  Of the groups parked on the
old class, the Bezier / EFD / PCA / mesh-preprocessing groups were dead
duplicates of the C++ ``LiverResections/Algorithm/`` library (ADR-0015)
and were deleted; only this distance-maps group genuinely relocates.

The two entry points are module-level (no instance state): the original
methods used ``self`` only to chain ``imageResample`` from
``computeDistanceMaps`` on the down-sampling path, which is preserved as
a plain function call here.
"""

import logging


def computeDistanceMaps(tumorNode, parenchymaNode, hepaticNode, portalNode, outputNode, downSamplingRate=1):
    if outputNode is not None:
        import sitkUtils
        import SimpleITK as sitk

        tumorDistanceImage = None
        parenchymaDistanceImage = None
        hepaticDistanceImage = None
        portalDistanceImage = None

        # Compute tumor distance map
        if tumorNode is not None:
            tumorImage = sitkUtils.PullVolumeFromSlicer(tumorNode)
            tumorDistanceImage = sitk.SignedMaurerDistanceMap(tumorImage, False, False, True)
            logging.debug("Computing Tumor Distance Map...")

        # Compute parenchyma distance map
        if parenchymaNode is not None:
            parenchymaImage = sitkUtils.PullVolumeFromSlicer(parenchymaNode)
            parenchymaDistanceImage = sitk.SignedMaurerDistanceMap(parenchymaImage, False, False, True)
            logging.debug("Computing Parenchyma Distance Map...")

        # Compute hepatic distance map
        if hepaticNode is not None:
            hepaticImage = sitkUtils.PullVolumeFromSlicer(hepaticNode)
            hepaticDistanceImage = sitk.SignedMaurerDistanceMap(hepaticImage, False, False, True)
            logging.debug("Computing Hepatic Distance Map...")

        # Compute portal distance map
        if portalNode is not None:
            portalImage = sitkUtils.PullVolumeFromSlicer(portalNode)
            portalDistanceImage = sitk.SignedMaurerDistanceMap(portalImage, False, False, True)
            logging.debug("Computing Portal Distance Map...")

        # Combine distance maps
        if downSamplingRate != 1:
            imageSize = tumorImage.GetSize()
            newSize = [round(i / downSamplingRate) for i in imageSize]
            tumorDistanceImageDown = imageResample(tumorDistanceImage, [newSize[0], newSize[1], newSize[2]], "linear")
            parenchymaDistanceImageDown = imageResample(parenchymaDistanceImage, [newSize[0], newSize[1], newSize[2]], "linear")
            hepaticDistanceImageDown = imageResample(hepaticDistanceImage, [newSize[0], newSize[1], newSize[2]], "linear")
            portalDistanceImageDown = imageResample(portalDistanceImage, [newSize[0], newSize[1], newSize[2]], "linear")
            compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImageDown, parenchymaDistanceImageDown, hepaticDistanceImageDown, portalDistanceImageDown] if i])
        else:
            compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImage, parenchymaDistanceImage, hepaticDistanceImage, portalDistanceImage] if i])

        sitkUtils.PushVolumeToSlicer(compositeDistanceMap, targetNode=outputNode, className='vtkMRMLVectorVolumeNode')
        outputNode.SetAttribute('DistanceMap', "True")
        outputNode.SetAttribute('Computed', "True")


def imageResample(inputImage, resampledSize, interpolatorType):
    """
    Resampling the Maurer distance map
    """
    if inputImage is not None:
        import SimpleITK as sitk

    outputOrigin = inputImage.GetOrigin()
    outputDirection = inputImage.GetDirection()
    inputSizePixels = inputImage.GetSize()
    inputSpacing = inputImage.GetSpacing()
    inputSize = [inputSpacing[0] * inputSizePixels[0],
                 inputSpacing[1] * inputSizePixels[1],
                 inputSpacing[2] * inputSizePixels[2]]

    outputSpacing = [0.0, 0.0, 0.0]
    outputSpacing[0] = inputSize[0] / float(resampledSize[0])
    outputSpacing[1] = inputSize[1] / float(resampledSize[1])
    outputSpacing[2] = inputSize[2] / float(resampledSize[2])

    NewOutputOrigin = [0.0, 0.0, 0.0]
    NewOutputOrigin[0] = outputOrigin[0] + (outputSpacing[0] / 2.0 - inputSpacing[0] / 2.0) * outputDirection[0]
    NewOutputOrigin[1] = outputOrigin[1] + (outputSpacing[1] / 2.0 - inputSpacing[1] / 2.0) * outputDirection[4]
    NewOutputOrigin[2] = outputOrigin[2] + (outputSpacing[2] / 2.0 - inputSpacing[2] / 2.0) * outputDirection[8]

    if interpolatorType == "linear":
        interpolator = sitk.sitkLinear
    elif interpolatorType == "b-spline":
        interpolator = sitk.sitkBSpline
    elif interpolatorType == "nearest neighbor":
        interpolator = sitk.sitkNearestNeighbor

    imageResampleFilter = sitk.ResampleImageFilter()
    imageResampleFilter.SetInterpolator(interpolator)
    imageResampleFilter.SetOutputOrigin(NewOutputOrigin)
    imageResampleFilter.SetOutputSpacing(outputSpacing)
    imageResampleFilter.SetOutputDirection(outputDirection)
    imageResampleFilter.SetSize(resampledSize)

    resampledImage = imageResampleFilter.Execute(inputImage)

    return resampledImage
