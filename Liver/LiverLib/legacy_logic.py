# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
#   * Neither the name of Oslo University Hospital nor the names
#     of Contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#   HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#   THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#   This file was originally developed by Rafael Palomar (Oslo University
#   Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
#   Research Council of Norway through the ALive project (grant nr. 311393).
#
# ==============================================================================

"""Legacy LiverLogic — orphaned domain compute to be relocated.

This module holds the LiverLogic class historically embedded in
``Liver/Liver.py``: signed-Maurer distance maps (SimpleITK), Bezier
surface fitting / elliptic-Fourier descriptors, and a handful of
VTK polydata utilities.  None of this code belongs in the Liver
shell — the shell composes, it does not compute (ADR-0023
§"Shell composition (Option H)").

The relocation lands in two passes:

  1.  T5.2-d (this file): move the code out of ``Liver/Liver.py``
      so the shell becomes import-clean and shrinks to its
      composition role.  The leading underscore in the module name
      signals "private; awaiting full relocation to its rightful
      owner module."
  2.  Orphaned-domain-code relocation follow-up: split the contents
      into the per-stage modules they actually belong to
      (``LiverResections`` for the Bezier algorithm bridges + resection
      helpers, ``LiverDistanceMaps`` for the SignedMaurer pipeline,
      etc.).

Test coverage for the Bezier helpers lives at
``Testing/Python/unit/test_bezier_characterization.py`` and is
loaded directly from this file rather than via ``Liver.py``.
"""

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern

import logging

import vtk
import slicer
from vtk.util.numpy_support import vtk_to_numpy
from slicer.ScriptedLoadableModule import *
import numpy as np
from numpy import size


class LiverLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
computation done by your module.  The interface
should be such that other python code can import
this class and make use of the functionality without
requiring an instance of the Widget.
Uses ScriptedLoadableModuleLogic base class, available at:
https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
"""


  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    ScriptedLoadableModuleLogic.__init__(self)

  def computeDistanceMaps(self, tumorNode, parenchymaNode, hepaticNode, portalNode, outputNode, downSamplingRate=1):

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
        # tumorDistanceImageDown =  self.imageResample( tumorDistanceImage, [150,150,150], "linear")

      # Compute parenchyma distance map
      if parenchymaNode is not None:
        parenchymaImage = sitkUtils.PullVolumeFromSlicer(parenchymaNode)
        parenchymaDistanceImage = sitk.SignedMaurerDistanceMap(parenchymaImage, False, False, True)
        logging.debug("Computing Parenchyma Distance Map...")
        # parenchymaDistanceImageDown = self.imageResample( parenchymaDistanceImage, [150,150,150], "linear")

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

      #Combine distance maps
      if downSamplingRate != 1:
        imageSize = tumorImage.GetSize()
        newSize = [round(i/downSamplingRate) for i in imageSize]
        tumorDistanceImageDown =  self.imageResample( tumorDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        parenchymaDistanceImageDown = self.imageResample( parenchymaDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        hepaticDistanceImageDown = self.imageResample( hepaticDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        portalDistanceImageDown = self.imageResample( portalDistanceImage, [newSize[0],newSize[1],newSize[2]], "linear")
        compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImageDown, parenchymaDistanceImageDown, hepaticDistanceImageDown, portalDistanceImageDown] if i])
      else:
        compositeDistanceMap = sitk.Compose(*[i for i in [tumorDistanceImage, parenchymaDistanceImage, hepaticDistanceImage, portalDistanceImage] if i])

      sitkUtils.PushVolumeToSlicer(compositeDistanceMap, targetNode = outputNode, className='vtkMRMLVectorVolumeNode')
      outputNode.SetAttribute('DistanceMap', "True")
      outputNode.SetAttribute('Computed', "True")

  def imageResample(self, inputImage, resampledSize, interpolatorType):
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

  def preprocessing(self, surfacePolyData, targetNumberOfPoints=800000, decimationAggressiveness=2):
    numberOfInputPoints = surfacePolyData.GetNumberOfPoints()

    if numberOfInputPoints == 0:
      raise ValueError("Input surface model is empty")

    elif numberOfInputPoints <= 400000:
      subdiv = vtk.vtkLinearSubdivisionFilter()
      subdiv.SetInputData(surfacePolyData)
      subdiv.SetNumberOfSubdivisions(1)
      subdiv.Update()
      subPolyData = subdiv.GetOutput()

      if subPolyData.GetNumberOfPoints() == 0:
        logging.warning("Mesh subdivision failed. Skip subdivision step.")

      numberOfPoints = subPolyData.GetNumberOfPoints()
      reductionFactor = (numberOfPoints - targetNumberOfPoints) / numberOfPoints
      print('reduction factor',reductionFactor)

      if reductionFactor > 0.0:
        surfacePolyData = self.run_decimation(subPolyData, reductionFactor)
      else:
        surfacePolyData = vtk.vtkPolyData()  # Create an empty vtkPolyData object
        surfacePolyData.DeepCopy(subPolyData)

    preprocessedPolyData = self.process_polydata(surfacePolyData)
    return self.create_model_node(preprocessedPolyData)

  def run_decimation(self, inputPolyData, reductionFactor):
    decimation = vtk.vtkDecimatePro()
    decimation.SetInputData(inputPolyData)
    decimation.SetTargetReduction(reductionFactor)
    decimation.SetPreserveTopology(True)
    decimation.SetFeatureAngle(60.0)
    decimation.SetBoundaryVertexDeletion(False)
    decimation.SetDegree(20)
    decimation.SetMaximumError(0.001)
    decimation.Update()
    return decimation.GetOutput()

  def process_polydata(self, inputPolyData):
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(inputPolyData)
    cleaner.Update()

    triangulator = vtk.vtkTriangleFilter()
    triangulator.SetInputData(cleaner.GetOutput())
    triangulator.PassLinesOff()
    triangulator.PassVertsOff()
    triangulator.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(triangulator.GetOutput())
    normals.SetAutoOrientNormals(1)
    normals.SetFlipNormals(0)
    normals.SetConsistency(1)
    normals.SplittingOff()
    normals.Update()

    return normals.GetOutput()

  def create_model_node(self, polyData):
    modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')
    modelNode.SetName("PreprocessedLiver")
    modelNode.CreateDefaultDisplayNodes()
    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetOpacity(0.2)
    modelDisplayNode.Visibility3DOff()
    modelNode.SetAndObservePolyData(polyData)
    return modelNode

  def CreatePolyDataFromCoords(self, coordinates):
    """
    Takes the x, y, and z coordinates of a 3D numpy array and creates a vtkPolyData object
    :param coordinates: 3D numpy array of x,y,z coordinates
    :return: vtkPolyData
    """

    points = vtk.vtkPoints()
    cells = vtk.vtkCellArray()
    polydata = vtk.vtkPolyData()

    for k in range(size(coordinates, 0)):
      point = coordinates[k]
      pointId = points.InsertNextPoint(point[:])
      cells.InsertNextCell(1)
      cells.InsertCellPoint(pointId)

    cells.Modified()
    points.Modified()
    polydata.SetPoints(points)
    polydata.SetVerts(cells)

    return polydata

  def extract_points(self, liverNode, point1, refDist, contourThickness):
    points = liverNode.GetPolyData().GetPoints()
    numberOfPoints = liverNode.GetPolyData().GetNumberOfPoints()
    points = np.array([points.GetPoint(i) for i in range(0, numberOfPoints)])
    dist = np.linalg.norm(points - point1, axis=1)
    final_points = points[np.abs(dist - refDist) < contourThickness]
    return final_points

  def distance(self, P1, P2):
    res = ((P1[0] - P2[0]) ** 2 + (P1[1] - P2[1]) ** 2 + (P1[2] - P2[2]) ** 2) ** 0.5
    return res

  def optimized_path(self, coords, start=None):
    """
    This function finds the nearest point to a point
    coords should be a numpy array
    """
    if start is None:
      start = coords[0]
    pass_by = coords
    path = [start]
    pass_by = np.delete(pass_by, 0, axis=0)
    distances = []
    while pass_by.shape[0] > 0:
      nearest = pass_by[np.argmin(np.linalg.norm(path[-1] - pass_by, axis=1))]
      dist = np.linalg.norm(path[-1] - nearest)
      distances.append(dist)
      path.append(nearest)
      pass_by = np.delete(pass_by, np.argwhere(np.all(pass_by == nearest, axis=1)), axis=0)

    return np.asarray(path), np.asarray(distances)

  def normalize_efd3d(self, coeffs, size_invariant=True, return_transformation=False):
    """ This method should be used when the original coordinates don't need to be preserved, for example for allowing
    comparison between polygons of differing sizes. It implements the normalization procedure in Bose, Paromita. The
    encoding and Fourier descriptors of arbitrary curves in 3-dimensional space. Diss. State University System of
    Florida, 2000.
    This function is a modified 3D version from https://github.com/hbldh/pyefd
    """

    # ToDO: check the affidability of this normalization method for 3D points in case you may want to use it for
    #  other purpose

    A = np.array([
      [coeffs[0, 0], coeffs[0, 1], (coeffs[0, 2] * coeffs[0, 5] - coeffs[0, 4] * coeffs[0, 3])],
      [coeffs[0, 2], coeffs[0, 3], (coeffs[0, 1] * coeffs[0, 4] - coeffs[0, 0] * coeffs[0, 5])],
      [coeffs[0, 4], coeffs[0, 5], (coeffs[0, 0] * coeffs[0, 3] - coeffs[0, 1] * coeffs[0, 2])],
    ]
    )

    inv_A = np.linalg.inv(A)
    # print(inv_A)
    ace_new = []
    bdf_new = []
    for n in range(1, coeffs.shape[0] + 1):
      x = inv_A.dot(
        np.array(
          [
            [coeffs[n - 1, 1]],
            [coeffs[n - 1, 3]],
            [coeffs[n - 1, 5]],
          ]
        ).flatten()
      )
      ace_new.append(x)

      y = inv_A.dot(
        np.array(
          [
            [coeffs[n - 1, 0]],
            [coeffs[n - 1, 2]],
            [coeffs[n - 1, 4]],
          ]
        )
      ).flatten()
      bdf_new.append(y)

    ace_array = np.array(ace_new)
    bdf_array = np.array(bdf_new)
    normalized_coeffs = np.vstack(
      (ace_array[:, 0], bdf_array[:, 0], ace_array[:, 1], bdf_array[:, 1], ace_array[:, 2], bdf_array[:, 2])).T
    # print('ace', ace_array)
    # print('bdf', bdf_array)
    # print('result', normalized_coeffs)

    size = np.sqrt(coeffs[0, 0] ** 2 + coeffs[0, 2] ** 2 + coeffs[0, 4] ** 2)
    if size_invariant:
      # Obtain size-invariance by normalizing.
      coeffs /= np.abs(size)

    if return_transformation:
      return coeffs, size
    else:

      return normalized_coeffs

  def elliptic_fourier_descriptors(self,
                                   contour, order=8, normalize=False, return_transformation=False
                                   ):
    """Calculate elliptical Fourier descriptors for a contour.

    Args:
         contour: A numpy.ndarray contour array of size [M x 3].
         order: The order of Fourier coefficients to calculate.
         normalize: If the coefficients should be normalized.
         return_transformation: If the normalization parametres should be returned. Default is False.

    Returns:
        coeffs: A [order x 6]array of Fourier coefficients and optionally the
        transformation parametres scale, psi_1 (rotation) and theta_1(phase)

    This function is a modified 3D version from https://github.com/hbldh/pyefd

    """
    dxyz = np.diff(contour, axis=0)
    dt = np.sqrt((dxyz ** 2).sum(axis=1))
    t = np.concatenate([([0.0]), np.cumsum(dt)])  # Return the cumulative sum of the elements along a given axis

    T = t[-1]

    phi = (2 * np.pi * t) / T

    orders = np.arange(1, order + 1)
    consts = T / (2 * orders * orders * np.pi * np.pi)
    phi = phi * orders.reshape((order, -1))
    d_cos_phi = np.cos(phi[:, 1:]) - np.cos(phi[:, :-1])
    d_sin_phi = np.sin(phi[:, 1:]) - np.sin(phi[:, :-1])
    a = consts * np.sum((dxyz[:, 0] / dt) * d_cos_phi, axis=1)
    b = consts * np.sum((dxyz[:, 0] / dt) * d_sin_phi, axis=1)
    c = consts * np.sum((dxyz[:, 1] / dt) * d_cos_phi, axis=1)
    d = consts * np.sum((dxyz[:, 1] / dt) * d_sin_phi, axis=1)
    e = consts * np.sum((dxyz[:, 2] / dt) * d_cos_phi, axis=1)
    f = consts * np.sum((dxyz[:, 2] / dt) * d_sin_phi, axis=1)

    coeffs = np.concatenate(
      [
        a.reshape((order, 1)),
        b.reshape((order, 1)),
        c.reshape((order, 1)),
        d.reshape((order, 1)),
        e.reshape((order, 1)),
        f.reshape((order, 1))
      ],
      axis=1,
    )

    if normalize:
      coeffs = self.normalize_efd3d(coeffs, return_transformation=return_transformation)
      # print(coeffs)

    return coeffs

  def inverse_transform(self, coeffs, locus=(0, 0, 0), n_coords=12, harmonic=10):
    '''
    Perform an inverse fourier transform to convert the coefficients back into
    spatial coordinates.
    Implements Kuhl and Giardina method of computing the performing the
    transform for a specified number of harmonics. This code is adapted
    from the pyefd module. See the original paper for more detail:
    Kuhl, FP and Giardina, CR (1982). Elliptic Fourier features of a closed
    contour. Computer graphics and image processing, 18(3), 236-258.
    Args:
        coeffs (numpy.ndarray): A numpy array of shape (harmonic, 6)
            representing the four coefficients for each harmonic computed.
        locus (tuple): The x,y,z coordinates of the centroid of the contour being
            generated. Use calculate_dc_coefficients() to generate the correct
            locus for a shape.
        n_coords (int): The number of coordinate pairs to compute. A larger
            value will result in a more complex shape at the expense of
            increased computational time. Defaults to 300.
        harmonics (int): The number of harmonics to be used to generate
            coordinates, defaults to 10. Must be <= coeffs.shape[0]. Supply a
            smaller value to produce coordinates for a more generalized shape.
    Returns:
        numpy.ndarray: A numpy array of shape (harmonics, 6) representing the
        four coefficients for each harmonic computed.

    This function is a modified 3D version from https://github.com/hbldh/pyefd
    '''

    t = np.linspace(0, 1, n_coords).reshape(1, -1)
    n = np.arange(harmonic).reshape(-1, 1)

    xt = (np.matmul(coeffs[:harmonic, 0].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 1].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[0])

    yt = (np.matmul(coeffs[:harmonic, 2].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 3].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[1])

    zt = (np.matmul(coeffs[:harmonic, 4].reshape(1, -1),
                    np.cos(2. * (n + 1) * np.pi * t)) +
          np.matmul(coeffs[:harmonic, 5].reshape(1, -1),
                    np.sin(2. * (n + 1) * np.pi * t)) +
          locus[2])

    reconstruction = np.stack([xt, yt, zt], axis=1)

    return reconstruction

  def calculate_dc_coefficients(self, contour):
    """ Calculate the :math:`A_0`, :math:`C_0` and :math:`E_0` coefficients of the elliptic Fourier series.
     Args
     numpy.ndarray contour: A contour array of size [M x 3]

     Returns:
        The A_0`, C_0, E_0` coefficients

    This function is a modified 3D version from https://github.com/hbldh/pyefd
    """
    dxyz = np.diff(contour, axis=0)
    dt = np.sqrt((dxyz ** 2).sum(axis=1))
    t = np.concatenate([([0.0]), np.cumsum(dt)])
    T = t[-1]

    xi = np.cumsum(dxyz[:, 0]) - (dxyz[:, 0] / dt) * t[1:]
    A0 = (1 / T) * np.sum(((dxyz[:, 0] / (2 * dt)) * np.diff(t ** 2)) + xi * dt)
    delta = np.cumsum(dxyz[:, 1]) - (dxyz[:, 1] / dt) * t[1:]
    C0 = (1 / T) * np.sum(((dxyz[:, 1] / (2 * dt)) * np.diff(t ** 2)) + delta * dt)
    zi = np.cumsum(dxyz[:, 2]) - (dxyz[:, 2] / dt) * t[1:]
    E0 = (1 / T) * np.sum(((dxyz[:, 2] / (2 * dt)) * np.diff(t ** 2)) + zi * dt)

    # Adding those values to the coefficients to make them relate to true origin.
    return contour[0, 0] + A0, contour[0, 1] + C0, contour[0, 2] + E0

  def Nyquist(self, X):
    """
    The total number of harmonics that can be computed for any outline is equal to half of the total number of
    outline coordinates (i.e. the ‘Nyquist frequency’). len(X)=len(Y)=len(Z)
    Args:
        X (list): A list (or numpy array) of x coordinate values.

    Returns:
        int: The nyquist frequency, expressed as a number of harmonics.
    """
    return len(X) // 2

  def FourierPower(self, coeffs, X, threshold=0.9999):
    '''
    Compute the total Fourier power and find the minium number of harmonics
    required to exceed the threshold fraction of the total power (precisely, total energy spectral density).
    This is a good method for identifying the number of harmonics to use to
    describe a polygon. For more details see:
    C. Costa et al. / Postharvest Biology and Technology 54 (2009) 38-47
    Warning:
        The number of coeffs must be >= the nyquist freqency.
    Args:
        coeffs (numpy.ndarray): A numpy array of shape (n, 6) representing the
            four coefficients for each harmonic computed.
        X (list): A list (or numpy array) of x coordinate values.
        threshold (float): The threshold fraction of the total Fourier power,
            the default is 0.9999.
    Returns:
        int: The number of harmonics required to represent the contour above
        the threshold Fourier power.
    '''
    nyquist = self.Nyquist(X)

    totalPower = 0
    currentPower = 0

    for n in range(nyquist):
      totalPower += ((coeffs[n, 0] ** 2) + (coeffs[n, 1] ** 2) +
                     (coeffs[n, 2] ** 2) + (coeffs[n, 3] ** 2) + (coeffs[n, 4] ** 2) + (coeffs[n, 5] ** 2)) / 3

    for i in range(nyquist):
      currentPower += ((coeffs[i, 0] ** 2) + (coeffs[i, 1] ** 2.) +
                       (coeffs[i, 2] ** 2) + (coeffs[i, 3] ** 2.) + (coeffs[i, 4] ** 2) + (coeffs[i, 5] ** 2)) / 3

      if (currentPower / totalPower) > threshold:
        return i + 1

  def compute_simple_pca(self, poly_data_input):
    """
    Computes Principal Component Analysis of a mesh
    :param poly_data_input: compute PCA of this vtkPolyData
    :return: eigenvector which is the direction for the profile of the contour
    """
    x_array = vtk.vtkDoubleArray()
    x_array.SetNumberOfComponents(1)
    x_array.SetName('x')
    y_array = vtk.vtkDoubleArray()
    y_array.SetNumberOfComponents(1)
    y_array.SetName('y')
    z_array = vtk.vtkDoubleArray()
    z_array.SetNumberOfComponents(1)
    z_array.SetName('z')

    for i in range(0, poly_data_input.GetNumberOfPoints()):
      pt = poly_data_input.GetPoint(i)
      x_array.InsertNextValue(pt[0])
      y_array.InsertNextValue(pt[1])
      z_array.InsertNextValue(pt[2])

    table = vtk.vtkTable()
    table.AddColumn(x_array)
    table.AddColumn(y_array)
    table.AddColumn(z_array)

    pca_stats = vtk.vtkPCAStatistics()

    if vtk.VTK_MAJOR_VERSION <= 5:
      pca_stats.SetInput(table)

    else:
      pca_stats.SetInputData(table)

    pca_stats.SetColumnStatus("x", 1)
    pca_stats.SetColumnStatus("y", 1)
    pca_stats.SetColumnStatus("z", 1)

    pca_stats.RequestSelectedColumns()
    pca_stats.SetDeriveOption(True)
    pca_stats.Update()

    eigenvalues = vtk.vtkDoubleArray()
    pca_stats.GetEigenvalues(eigenvalues)
    eigenvector0 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(0, eigenvector0)
    eigenvector1 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(1, eigenvector1)
    eigenvector2 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(2, eigenvector2)

    eigv0 = [0.0, 0.0, 0.0]
    eigv1 = [0.0, 0.0, 0.0]
    eigv2 = [0.0, 0.0, 0.0]

    for i in range(0, 3):
      eigv0[i] = eigenvector0.GetValue(i)
      eigv1[i] = eigenvector1.GetValue(i)
      eigv2[i] = eigenvector2.GetValue(i)

    eigen_dict = {'eigenvalues': eigenvalues, 'eigenvectors': [eigv0, eigv1, eigv2]}

    eigen_vectors = eigen_dict['eigenvectors']
    eigen_vectors_array = np.asarray(eigen_vectors).reshape(3, -1)
    eigenvalues = np.asarray(eigenvalues).reshape(3, -1)
    # cross = np.cross(eigen_vectors_array[0],eigen_vectors_array[1])

    # TODO: It could be better using a cross product as direction contour's profile
    return eigen_vectors_array[1], eigenvalues[0]

  def project_points_to_plane(self, mesh, origin=None, normal=(0, 0, 1)):
    """
    Project points of this mesh to a plane and find the furthest point to the center of mass.
    Return the max pointID
    """

    # Make plane
    normal = normal / np.linalg.norm(normal)  # MUST HAVE MAGNITUDE OF 1
    plane = vtk.vtkPlane()
    plane.SetOrigin(origin)
    plane.SetNormal(normal)
    projPts = vtk.vtkPoints()
    for i in range(mesh.GetNumberOfPoints()):
      currPoint = mesh.GetPoint(i)
      newPoint = np.zeros(3)
      plane.ProjectPoint(currPoint, newPoint)
      projPts.InsertNextPoint(newPoint)

    projPd = vtk.vtkPolyData()
    projPd.SetPoints(projPts)
    projected_array = vtk_to_numpy(projPd.GetPoints().GetData())

    center = vtk.vtkCenterOfMass()
    center.SetInputDataObject(projPd)
    center.Update()
    center = np.array(center.GetCenter())

    distances = np.linalg.norm(projected_array - center, axis=1)
    max_id = distances.argmax()

    return max_id

  def Unordered2orderedPointCloud(self, positions):

    global newpoints
    N = len(positions)
    listpoints = []

    for x in range(int(N / 2) + 1):
      if N % 2 == 0:
        listpoints.append(positions[x])
        listpoints.append(positions[-x])
        newpoints = np.asarray([listpoints[1:-1]]).squeeze()
      else:
        listpoints.append(positions[x])
        listpoints.append(positions[-x])
        newpoints = np.asarray([listpoints[1:]]).squeeze()

    # pointCloud = CreatePolyDataFromCoords(newpoints)
    xSpline = vtk.vtkKochanekSpline()
    ySpline = vtk.vtkKochanekSpline()
    zSpline = vtk.vtkKochanekSpline()

    pointCloud_list = list()
    final_parametric_spline_list = list()
    parametric_spline_list = list()
    source_spline_list = list()
    final_source_spline_list = list()

    for i in range(N):
      if i % 2 == 0:
        pointCloud_list.append(
          self.CreatePolyDataFromCoords(newpoints[i:i + 2, :]))

        # parametric_spline_list.append(spline)
        parametric_spline_list.append(vtk.vtkParametricSpline())
        source_spline_list.append(vtk.vtkParametricFunctionSource())

    for i in range(len(pointCloud_list)):
      parametric_spline_list[i].SetXSpline(xSpline)
      parametric_spline_list[i].SetYSpline(ySpline)
      parametric_spline_list[i].SetZSpline(zSpline)
      parametric_spline_list[i].SetPoints(pointCloud_list[i].GetPoints())
      # print(i)
      final_parametric_spline_list.append(parametric_spline_list[i])

      source_spline_list[i].SetParametricFunction(final_parametric_spline_list[i])
      source_spline_list[i].SetUResolution(20)
      source_spline_list[i].SetVResolution(20)
      source_spline_list[i].SetWResolution(20)
      source_spline_list[i].SetScalarModeToDistance()
      final_source_spline_list.append(source_spline_list[i])
      final_source_spline_list[i].Update()

    appendFilter = vtk.vtkAppendPolyData()
    for i in range(len(pointCloud_list)):
      appendFilter.AddInputData(final_source_spline_list[i].GetOutput())

    appendFilter.Update()

    spline_lines = appendFilter.GetOutput()
    points = spline_lines.GetPoints().GetData()
    points_array = vtk_to_numpy(points)
    # print("Number of points in the mask: {}".format(spline_lines.GetNumberOfPoints()))

    # newNode = slicer.vtkMRMLModelNode()
    # slicer.mrmlScene.AddNode(newNode)
    # newNode.SetName("MaskPoints")
    # newNode.SetAndObservePolyData(spline_lines)
    # display = slicer.vtkMRMLModelDisplayNode()
    # slicer.mrmlScene.AddNode(display)

    return points_array, spline_lines

  def compute_pca(self, poly_data_input, extent, start=0, stop=500, step=1):
    """
    Computes Principal Component Analysis of a mesh
    :param poly_data_input: compute PCA of this vtkPolyData
    :param extent of the line
    :return: eigenvalues, eigenvectors
    """
    x_array = vtk.vtkDoubleArray()
    x_array.SetNumberOfComponents(1)
    x_array.SetName('x')
    y_array = vtk.vtkDoubleArray()
    y_array.SetNumberOfComponents(1)
    y_array.SetName('y')
    z_array = vtk.vtkDoubleArray()
    z_array.SetNumberOfComponents(1)
    z_array.SetName('z')

    points = vtk.vtkPoints()
    for i in range(start, stop, step):
      # print(i)
      pt = poly_data_input.GetPoint(i)
      x_array.InsertNextValue(pt[0])
      y_array.InsertNextValue(pt[1])
      z_array.InsertNextValue(pt[2])
      points.InsertNextPoint(pt)

    # print(points.GetNumberOfPoints())
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)

    com = vtk.vtkCenterOfMass()
    com.SetInputData(polydata)
    com.SetUseScalarsAsWeights(False)
    com.Update()
    center = com.GetCenter()

    table = vtk.vtkTable()
    table.AddColumn(x_array)
    table.AddColumn(y_array)
    table.AddColumn(z_array)

    pca_stats = vtk.vtkPCAStatistics()

    if vtk.VTK_MAJOR_VERSION <= 5:
      pca_stats.SetInput(table)

    else:
      pca_stats.SetInputData(table)

    pca_stats.SetColumnStatus("x", 1)
    pca_stats.SetColumnStatus("y", 1)
    pca_stats.SetColumnStatus("z", 1)

    pca_stats.RequestSelectedColumns()
    pca_stats.SetDeriveOption(True)
    pca_stats.Update()

    eigenvalues = vtk.vtkDoubleArray()
    pca_stats.GetEigenvalues(eigenvalues)
    eigenvector0 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(0, eigenvector0)
    eigenvector1 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(1, eigenvector1)
    eigenvector2 = vtk.vtkDoubleArray()
    pca_stats.GetEigenvector(2, eigenvector2)

    eigv0 = [0.0, 0.0, 0.0]
    eigv1 = [0.0, 0.0, 0.0]
    eigv2 = [0.0, 0.0, 0.0]

    for i in range(0, 3):
      eigv0[i] = eigenvector0.GetValue(i)
      eigv1[i] = eigenvector1.GetValue(i)
      eigv2[i] = eigenvector2.GetValue(i)

    eigen_dict = {'eigenvalues': eigenvalues, 'eigenvectors': [eigv0, eigv1, eigv2], 'center': [center]}

    # create the line
    eigen_vectors = eigen_dict['eigenvectors']
    eigen_vectors_array = np.asarray(eigen_vectors)
    center1 = np.asarray(eigen_dict['center'])
    line = np.vstack((center1 - eigen_vectors_array[0] * extent, center1 + eigen_vectors_array[0] * extent))
    x1 = np.linspace(line[0, 0], line[1, 0], 20)
    y1 = np.linspace(line[0, 1], line[1, 1], 20)
    z1 = np.linspace(line[0, 2], line[1, 2], 20)
    line1 = np.vstack((x1, y1, z1)).T

    result_dict = {'line': line1, 'eigen_vector': eigen_vectors_array[0], 'center': center1}
    # line1, eigen_vectors_array[0], center1

    return result_dict

  def line3D_afterSlopeAverage(self, center, eigen_average, extent):

    line = np.vstack((center - eigen_average * extent, center + eigen_average * extent))
    x1 = np.linspace(line[0, 0], line[1, 0], 50)
    y1 = np.linspace(line[0, 1], line[1, 1], 50)
    z1 = np.linspace(line[0, 2], line[1, 2], 50)
    line1 = np.vstack((x1, y1, z1)).T

    return line1

  def spline_line_fromClosedCurve(self, curveNode, liverModelNode):
    """
    Computes spline lines from a ClosedMarkupCurve
    :param curve: close curve node, curve = slicer.util.getNode("CC")
    :param liverModelNode: liver 3D Model,  liver = slicer.util.getNode("liver")
    :return: points array of the spline lines and the polydata
    """
    global newpoints
    curveNode.SetAndObserveSurfaceConstraintNode(liverModelNode)

    # Step 1: Resample curve
    resampleNumber = 100
    currentPoints = curveNode.GetCurvePointsWorld()
    newPoints = vtk.vtkPoints()
    sampleDist = curveNode.GetCurveLengthWorld() / (resampleNumber - 1)

    closedCurveOption = 1
    curveNode.ResamplePoints(currentPoints, newPoints, sampleDist, closedCurveOption)

    vector = vtk.vtkVector3d()
    pt = [0, 0, 0]
    resampledCurve = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsClosedCurveNode", "resampledCurveOrig")
    for controlPoint in range(0, newPoints.GetNumberOfPoints()):
      newPoints.GetPoint(controlPoint, pt)
      vector[0] = pt[0]
      vector[1] = pt[1]
      vector[2] = pt[2]
      resampledCurve.AddControlPoint(vector)

    resampledCurve.SetDisplayVisibility(False)
    curveNode.SetDisplayVisibility(True)
    # Step 2: REORDER THE RESAMPLED POINTS ID AND CREATE A POLYDATA.
    # This step will split the points IDS in 2 parts in order to correctly apply the knitting algorithm.
    # get the numpy array in order to split the curve id in two section
    markupsPositions = slicer.util.arrayFromMarkupsControlPoints(resampledCurve)
    # markupsPositions = slicer.util.arrayFromMarkupsCurvePoints(resampledCurve)
    N = len(markupsPositions)
    listpoints = []

    if N % 2 == 0:
      for x in range(int(N / 2) + 1):
        listpoints.append(markupsPositions[x])
        listpoints.append(markupsPositions[-x])
        newpoints = np.asarray([listpoints[1:-1]]).squeeze()
    else:
      for x in range(int(N / 2) + 1):
        listpoints.append(markupsPositions[x])
        listpoints.append(markupsPositions[-x])
        newpoints = np.asarray([listpoints[1:]]).squeeze()

    # Step 3: PIECEWISE SPLINE INTERPOLATION
    xSpline = vtk.vtkKochanekSpline()
    ySpline = vtk.vtkKochanekSpline()
    zSpline = vtk.vtkKochanekSpline()

    pointCloud_list = list()
    final_parametric_spline_list = list()
    parametric_spline_list = list()
    source_spline_list = list()
    final_source_spline_list = list()

    for i in range(N):
      if i % 2 == 0:
        pointCloud_list.append(
          self.CreatePolyDataFromCoords(newpoints[i:i + 2, :]))

        # parametric_spline_list.append(spline)
        parametric_spline_list.append(vtk.vtkParametricSpline())
        source_spline_list.append(vtk.vtkParametricFunctionSource())

    for i in range(len(pointCloud_list)):
      parametric_spline_list[i].SetXSpline(xSpline)
      parametric_spline_list[i].SetYSpline(ySpline)
      parametric_spline_list[i].SetZSpline(zSpline)
      parametric_spline_list[i].SetPoints(pointCloud_list[i].GetPoints())
      # print(i)
      final_parametric_spline_list.append(parametric_spline_list[i])

      source_spline_list[i].SetParametricFunction(final_parametric_spline_list[i])
      source_spline_list[i].SetUResolution(20)
      source_spline_list[i].SetVResolution(20)
      source_spline_list[i].SetWResolution(20)
      source_spline_list[i].SetScalarModeToDistance()
      final_source_spline_list.append(source_spline_list[i])
      final_source_spline_list[i].Update()

    appendFilter = vtk.vtkAppendPolyData()
    for i in range(len(pointCloud_list)):
      appendFilter.AddInputData(final_source_spline_list[i].GetOutput())

    appendFilter.Update()

    spline_lines = appendFilter.GetOutput()
    points = spline_lines.GetPoints().GetData()
    points_array = vtk_to_numpy(points)
    print(f"Number of points in the mask: {spline_lines.GetNumberOfPoints()}")

    return points_array, spline_lines

  def compute_parametrization(self, points, centripetal=True):
    # Length of the points array
    num_points = len(points)

    # Calculate chord lengths
    cds = np.zeros([num_points + 1, 1])
    # cds = [0.0 for _ in range(num_points + 1)]
    cds[-1] = 1.0
    for i in range(1, num_points):
      distance = np.linalg.norm(points[i, :] - points[i - 1, :], ord=2)
      # distance = linalg.point_distance(points[i], points[i - 1])
      cds[i] = np.sqrt(distance) if centripetal else distance

    # Find the total chord length
    d = sum(cds[1:-1])

    # Divide individual chord lengths by the total chord length
    uk = np.zeros([num_points, 1])
    for i in range(num_points):
      uk[i] = sum(cds[0:i + 1]) / d

    return uk

  def compute_averaging_params_surface(self, points, size_u, size_v):
    """
    Compute knot averaging as recommended in The NURBS Book (2nd Edition), pp.366-367
    :param points: surface point arranged in a grid NxNx3
    :param size_u: number of points on the u-direction
    :param size_v: number of points on the v-direction
    :return:
    """
    # finding params in v direction
    size_u, size_v = points.shape[0:2]
    params_v = []
    for u in range(size_u):
      temp = self.compute_parametrization(points[u]).reshape((1, size_v))
      params_v.append(temp)
    params_v = np.concatenate(params_v, 0)
    # finding params in u direction
    params_v = np.mean(params_v, 0)
    params_u = []
    for v in range(size_v):
      temp = self.compute_parametrization(points[:, v]).reshape((size_u, 1))
      params_u.append(temp)
    params_u = np.concatenate(params_u, 1)

    params_u = np.mean(params_u, 1)
    return params_u, params_v

  def evaluate_basis_bezier(self, t, degree):
    """
    Evaluates basis functions
    """

    # Initialize b vector
    b = np.zeros(degree + 1, dtype=np.float64)
    b[0] = 1
    t1 = 1. - t

    for j in range(1, degree + 1):
      saved = 0
      for k in range(0, j):
        temp = b[k]
        b[k] = saved + t1 * temp
        saved = t * temp

      b[j] = saved

    return b

  def fit_bezier_surface(self, points, basis_u, basis_v):
    """
    Given gridded points and basis functions for u and v, find the control points of a Bézier surface,
    using the pseudo inverse formulation
    """
    # Get the basis functions for u and v
    nu = basis_u
    nv = basis_v

    # Calculate the inverse of transpose(nu) * nu
    u_basis_transpose = np.transpose(nu)
    u_basis_product = np.matmul(u_basis_transpose, nu)
    u_basis_inverse = np.linalg.inv(u_basis_product)

    # Calculate ut_u_inv_u by multiplying u_basis_inverse with transpose(nu)
    ut_u_inv_u = np.matmul(u_basis_inverse, u_basis_transpose)

    # Calculate the inverse of transpose(nv) * nv
    v_basis_transpose = np.transpose(nv)
    v_basis_product = np.matmul(v_basis_transpose, nv)
    v_basis_inverse = np.linalg.inv(v_basis_product)

    # Calculate vt_v_inv_v by multiplying nv with v_basis_inverse
    vt_v_inv_v = np.matmul(nv, v_basis_inverse)

    # Initialize a list to store the control points
    cntrl_points = []

    # Use the pseudo inverse formulation to find the control points
    for i in range(3):
      # Get the current dimension of the points
      points_dimension = points[:, :, i]

      # Calculate the product of ut_u_inv_u * points_dimension * vt_v_inv_v
      points_cntrl = np.matmul(np.matmul(ut_u_inv_u, points_dimension), vt_v_inv_v)

      # Add the control points to the list
      cntrl_points.append(points_cntrl)

    # Convert the list to an array
    cntrl_points = np.array(cntrl_points)

    # Transpose the control points to have shape (N, N, 3)
    cntrl_points = np.transpose(cntrl_points, (1, 2, 0))

    return cntrl_points

  def runSurfacefromCurve(self, resectionNode, curveNode, liverModelNode):

    points_array = self.spline_line_fromClosedCurve(curveNode, liverModelNode)

    # create the extent with pca
    splines_poly = points_array[1]
    first_eigen = self.compute_simple_pca(splines_poly)
    extent_pca = 4 * np.sqrt(first_eigen[1])

    sub_pca = [self.compute_pca(points_array[1], extent_pca / 2, start=21 * i, stop=21 * (i + 1)) for i in
               range(50)]

    # convert a list of dictionaries into a dict of list
    sub_pca_dict = {}
    for k, v in [(key, d[key]) for d in sub_pca for key in d]:
      if k not in sub_pca_dict:
        sub_pca_dict[k] = [v]
      else:
        sub_pca_dict[k].append(v)

    eigen_average_center = np.average(np.vstack(sub_pca_dict['eigen_vector'][4:46]), axis=0)

    # TODo: the slops of the superior and inferior part of the point cloud could affect bezier Surface
    # eigen_average_start = np.average(np.vstack(sub_pca_dict['eigen_vector'][:4]), axis=0)
    # eigen_average_end = np.average(np.vstack(sub_pca_dict['eigen_vector'][46:50]), axis=0)

    # ToDO: Review the need for this: maybe check if there is a resampling function for vtk Spline
    center = sub_pca_dict['center']

    organized_data = np.vstack(
      np.array(
        [self.line3D_afterSlopeAverage(center[i], eigen_average_center, extent_pca / 2) for i in
         range(len(center))]))

    points_grid = organized_data.reshape(50, 50, 3)

    bezier_list_u = list()
    bezier_list_v = list()

    # u = self.compute_parametrization(points_grid[:, 0, 0].reshape(len(points_grid[:, 0, 0]), 1))
    # v = self.compute_parametrization(points_grid[0, :, 0].reshape(len(points_grid[0, :, 0]), 1))

    param_surface = self.compute_averaging_params_surface(points_grid, 50, 50)
    u = param_surface[0].reshape(-1, 1)
    v = param_surface[1].reshape(-1, 1)

    # for u direction

    for i in range(u.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(u[i], 3)
      bezier_list_u.append(bezier_basis)

    bezier_basis_u = np.array(bezier_list_u)

    # for v direction

    for i in range(v.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(v[i], 3)
      bezier_list_v.append(bezier_basis)

    bezier_basis_v = np.array(bezier_list_v)

    ctrl_points = self.fit_bezier_surface(points_grid, bezier_basis_u, bezier_basis_v)

    control_points = ctrl_points.reshape(-1, 3)

    points = vtk.vtkPoints()
    #
    for i in range(0, len(control_points)):
      points.InsertNextPoint(control_points[i])

    # BezierNode = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLMarkupsBezierSurfaceNode")
    # Transfer the control points to the resection node
    BezierNode = resectionNode.GetBezierSurfaceNode()
    BezierNode.RemoveAllControlPoints()
    BezierNode.SetControlPointPositionsWorld(points)
    BezierDisplay = BezierNode.GetDisplayNode()
    BezierDisplay.SetGlyphScale(0.0)
    BezierDisplay.VisibilityOn()
    # BezierDisplay.SetClipOut(True)

  def runSurfacefromEFD(self, resectionNode, distanceNode, liverNode):

    point1 = distanceNode.GetNthControlPointPosition(1)
    lenghtText = distanceNode.GetPropertiesLabelText()
    refDist = float(lenghtText.split('m')[0])
    contourThickness = 0.05

    final_points = self.extract_points(liverNode, point1, refDist, contourThickness)

    # Step 2: order the points according the shape of the contour
    optimazing = self.optimized_path(final_points)
    sorted1 = optimazing[0]
    distances = optimazing[1]
    # print("max", np.max(distances))
    # print("distances", distances)

    for i in range(len(distances)):
      if distances[i] > 30:
        max_id = np.argmax(distances)
        sorted1 = sorted1[0:max_id]

    # Step 3: Calculate the harmonics and 3DEF coefficients in frequency space

    nyquist = self.Nyquist(sorted1[:, 0])
    tmpcoeffs = self.elliptic_fourier_descriptors(sorted1, normalize=False, order=nyquist)
    harmonic = self.FourierPower(tmpcoeffs, sorted1[:, 0], threshold=0.9999)
    # print('harmonic', harmonic)
    efd = self.elliptic_fourier_descriptors(sorted1, normalize=False, order=harmonic)

    # Step 4: Reconstruction in 3D space
    coeffs0 = self.calculate_dc_coefficients(sorted1)
    rec = self.inverse_transform(efd, harmonic=harmonic, locus=coeffs0, n_coords=100)
    squeeze_rec = np.squeeze(rec)
    points = squeeze_rec.T

    poly_contour = self.CreatePolyDataFromCoords(points)

    # Step 5: deciding the starting point
    normal = self.compute_simple_pca(poly_contour)
    origin = np.array(poly_contour.GetCenter())
    length = np.array(poly_contour.GetLength())
    origin -= length
    max_id = self.project_points_to_plane(poly_contour, origin=origin, normal=normal[0])

    poly_points = poly_contour.GetPoints().GetData()
    poly_points = vtk_to_numpy(poly_points)

    new_points = poly_points[max_id:]
    last_part = poly_points[0:max_id]
    organizedPoints = np.vstack((new_points, last_part))

    distanceContourPoints = self.CreatePolyDataFromCoords(organizedPoints)

    # Review the need for this: merging points on the same position
    cleanFilter = vtk.vtkCleanPolyData()
    cleanFilter.SetInputData(distanceContourPoints)
    cleanFilter.ConvertPolysToLinesOn()
    cleanFilter.ConvertStripsToPolysOn()
    cleanFilter.PointMergingOn()
    cleanFilter.Update()
    surfaceFilter = vtk.vtkDataSetSurfaceFilter()
    surfaceFilter.SetInputData(cleanFilter.GetOutput())
    surfaceFilter.Update()

    points = surfaceFilter.GetOutput().GetPoints().GetData()
    organizedPoints = vtk_to_numpy(points)

    points_array = self.Unordered2orderedPointCloud(organizedPoints)

    # print('number of points', points_array[0].shape)
    #
    # create the extent
    origin = np.mean(points_array[0], axis=0)
    euclidian_distance = np.linalg.norm(points_array[0] - origin, axis=1)
    np.max(euclidian_distance)

    # create the extent with pca
    splines_poly = points_array[1]
    first_eigen = self.compute_simple_pca(splines_poly)
    extent_pca = 4 * np.sqrt(first_eigen[1])

    sub_pca = [self.compute_pca(points_array[1], extent_pca / 2, start=21 * i, stop=21 * (i + 1)) for i in
               range(50)]

    # convert a list of dictionaries into a dict of list
    sub_pca_dict = {}
    for k, v in [(key, d[key]) for d in sub_pca for key in d]:
      if k not in sub_pca_dict:
        sub_pca_dict[k] = [v]
      else:
        sub_pca_dict[k].append(v)

    eigen_average_center = np.average(np.vstack(sub_pca_dict['eigen_vector'][4:46]), axis=0)

    # TODo: the slops of the superior and inferior part of the point cloud could affect bezier Surface
    np.average(np.vstack(sub_pca_dict['eigen_vector'][:4]), axis=0)
    np.average(np.vstack(sub_pca_dict['eigen_vector'][46:50]), axis=0)

    # ToDO: Review the need for this: maybe check if there is a resampling function for vtk Spline
    center = sub_pca_dict['center']

    organized_data = np.vstack(
      np.array(
        [self.line3D_afterSlopeAverage(center[i], eigen_average_center, extent_pca / 2) for i in
         range(len(center))]))

    points_grid = organized_data.reshape(50, 50, 3)

    bezier_list_u = list()
    bezier_list_v = list()

    # u = self.compute_parametrization(points_grid[:, 0, 0].reshape(len(points_grid[:, 0, 0]), 1))
    # v = self.compute_parametrization(points_grid[0, :, 0].reshape(len(points_grid[0, :, 0]), 1))

    param_surface = self.compute_averaging_params_surface(points_grid, 50, 50)
    u = param_surface[0].reshape(-1, 1)
    v = param_surface[1].reshape(-1, 1)

    # for u direction

    for i in range(u.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(u[i], 3)
      bezier_list_u.append(bezier_basis)

    bezier_basis_u = np.array(bezier_list_u)

    # for v direction

    for i in range(v.shape[0]):
      bezier_basis = self.evaluate_basis_bezier(v[i], 3)
      bezier_list_v.append(bezier_basis)

    bezier_basis_v = np.array(bezier_list_v)

    ctrl_points = self.fit_bezier_surface(points_grid, bezier_basis_u, bezier_basis_v)

    control_points = ctrl_points.reshape(-1, 3)
    points = vtk.vtkPoints()
    #
    for i in range(0, len(control_points)):
      points.InsertNextPoint(control_points[i])

    # BezierNode = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLMarkupsBezierSurfaceNode")
    # Transfer the control points to the resection node
    BezierNode = resectionNode.GetBezierSurfaceNode()
    BezierNode.RemoveAllControlPoints()
    BezierNode.SetControlPointPositionsWorld(points)
    BezierDisplay = BezierNode.GetDisplayNode()
    BezierDisplay.VisibilityOn()

    # BezierDisplay.SetClipOut(True)
