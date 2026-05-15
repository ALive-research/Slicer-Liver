/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 1 of the
  v2.0.0 release tracker — see ADR-0015).

==============================================================================*/

#ifndef __vtkLiverContourParameterizer_h_
#define __vtkLiverContourParameterizer_h_

#include "vtkSlicerLiverResectionsModuleAlgorithmExport.h"

// VTK includes
#include <vtkPolyDataAlgorithm.h>
#include <vtkSmartPointer.h>

// STD
#include <vector>

class vtkDoubleArray;

/**
 * \class vtkLiverContourParameterizer
 *
 * \brief Parameterise a closed 3-D contour for downstream Bezier
 * fitting, in one of two modes — corner-mapping (for SlicingPlane
 * init) or Elliptic Fourier Descriptor reconstruction (for
 * DistanceSpheroid init).
 *
 * \par Mode: CornerMapping
 *  Selects 4 equally spaced indices around the ring and returns the
 *  parameterised curve as the input ring relabelled with those corner
 *  indices.  This is the lift target of the SlicingPlane parameterisation
 *  branch in ``runSurfacefromCurve``.
 *
 * \par Mode: EFD
 *  Computes Elliptic Fourier Descriptors via direct closed-form
 *  harmonic integration (the 3-D Kuhl-Giardina formulation from
 *  ``LiverLogic.elliptic_fourier_descriptors``, line ~1287 of
 *  ``Liver/Liver.py``), then reconstructs a smooth contour with a
 *  caller-specified number of points via ``LiverLogic.inverse_transform``
 *  (line ~1343), centred on the DC offset triple from
 *  ``LiverLogic.calculate_dc_coefficients`` (line ~1396).  No FFT — pure
 *  direct sum, matching the Python reference.
 *
 * \par Inputs
 *  - **Contour** (``SetInputContour``) — N closed ring points as a flat
 *    ``vtkDoubleArray`` of length 3*N.  The caller is responsible for
 *    closing the loop (i.e. either the last point repeats the first,
 *    or the test fixture handles that explicitly as in the Python
 *    characterisation tests).
 *
 * \par Parameters
 *  - ``Mode`` — ``MODE_CORNER_MAPPING`` (0) or ``MODE_EFD`` (1).
 *  - ``Order`` — Fourier order for EFD (default 8).
 *  - ``NumberOfReconstructionPoints`` — number of points the EFD inverse
 *    transform should sample (default 12; matches the characterisation
 *    test).
 *  - ``Locus`` — optional override for the DC offset triple.  If left at
 *    the sentinel ``UseComputedLocus`` (default), the parameteriser
 *    computes the DC triple internally; otherwise it uses the
 *    caller-provided values.
 *
 * \par Outputs (post-Update())
 *  - ``GetCoefficients()`` — flat (Order x 6) row-major array of the
 *    EFD coefficients (a, b, c, d, e, f).  Empty in CornerMapping mode.
 *  - ``GetDCCoefficients()`` — the three-element (A0, C0, E0) tuple
 *    actually used for the reconstruction.  Empty in CornerMapping mode.
 *  - ``GetReconstruction()`` — flat 3*NumberOfReconstructionPoints array
 *    of reconstructed contour points (x then y then z for each sample,
 *    matching the (1, 3, n_coords) shape of the Python output reshape).
 *  - On port 0, a ``vtkPolyData`` whose ``GetPoints()`` array holds the
 *    reconstructed contour (in EFD mode) or the input ring with corner
 *    indices attached as a "CornerIndices" point-data array
 *    (in CornerMapping mode).
 *
 * \par MRML invariant
 *  No ``vtkMRMLNode`` references.  Per ADR-0015.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_ALGORITHM_EXPORT vtkLiverContourParameterizer
  : public vtkPolyDataAlgorithm
{
 public:
  static vtkLiverContourParameterizer *New();
  vtkTypeMacro(vtkLiverContourParameterizer, vtkPolyDataAlgorithm);
  void PrintSelf(ostream &os, vtkIndent indent) override;

  enum Mode
  {
    MODE_CORNER_MAPPING = 0,
    MODE_EFD = 1
  };

  vtkSetMacro(Mode, int);
  vtkGetMacro(Mode, int);

  vtkSetMacro(Order, int);
  vtkGetMacro(Order, int);

  vtkSetMacro(NumberOfReconstructionPoints, int);
  vtkGetMacro(NumberOfReconstructionPoints, int);

  /// Set the input contour as a flat 3*N array (row-major xyz).
  void SetInputContour(vtkDoubleArray *contour);
  vtkDoubleArray *GetInputContour() const;

  /// Use a caller-supplied locus for EFD reconstruction.  After
  /// ``UseComputedLocusOn`` (the default) the parameteriser computes
  /// the DC triple internally via the Kuhl-Giardina A_0/C_0/E_0 formulas.
  void SetLocus(double x, double y, double z);
  vtkGetVector3Macro(Locus, double);
  vtkSetMacro(UseComputedLocus, bool);
  vtkGetMacro(UseComputedLocus, bool);
  vtkBooleanMacro(UseComputedLocus, bool);

  /// Flat (Order * 6) row-major array of EFD coefficients.
  const std::vector<double> &GetCoefficients() const { return this->Coefficients; }
  /// (A0, C0, E0) DC offsets actually used for the reconstruction.
  const std::vector<double> &GetDCCoefficients() const { return this->DC; }
  /// Reconstructed contour: 3*NumberOfReconstructionPoints values (x's,
  /// y's, z's in that order — matching the Python (1, 3, n_coords) shape).
  const std::vector<double> &GetReconstruction() const { return this->Reconstruction; }

  /// Compute EFD coefficients of an arbitrary closed 3D contour.
  /// Exposed as a static helper so callers (and tests) can drive the
  /// EFD math without instantiating the algorithm pipeline.  Direct
  /// closed-form harmonic integration; no FFT.  Returns flat (order*6)
  /// row-major (a, b, c, d, e, f) per harmonic as a VTK-wrappable
  /// vtkDoubleArray (1 component per value).
  ///
  /// `contour` must be a 3*n vtkDoubleArray of (x, y, z) triples.
  static vtkSmartPointer<vtkDoubleArray>
  ComputeEFDCoefficients(vtkDoubleArray *contour, int order);

  /// Compute the Kuhl-Giardina (A_0, C_0, E_0) DC triple for a closed
  /// 3D contour.  Returns 3 values in a vtkDoubleArray.
  static vtkSmartPointer<vtkDoubleArray>
  ComputeDCCoefficients(vtkDoubleArray *contour);

  /// Inverse EFD transform: reconstruct a contour from coefficients.
  /// Returns 3*nCoords values in the (1, 3, n_coords) layout used by
  /// the Python reference (i.e. all x's, then all y's, then all z's),
  /// packed into a vtkDoubleArray.
  static vtkSmartPointer<vtkDoubleArray>
  InverseTransform(vtkDoubleArray *coeffs,
                   int harmonic,
                   double locusX, double locusY, double locusZ,
                   int nCoords);

  /// C++-friendly overloads on raw pointers — used by the in-process
  /// pipeline and the C++ tests, which need pointer arithmetic over
  /// pre-existing std::vector buffers.
  static std::vector<double>
  ComputeEFDCoefficientsRaw(const double *contour, int nPoints, int order);
  static std::vector<double>
  ComputeDCCoefficientsRaw(const double *contour, int nPoints);
  static std::vector<double>
  InverseTransformRaw(const double *coeffs,
                      int harmonic,
                      const double locus[3],
                      int nCoords);

 protected:
  vtkLiverContourParameterizer();
  ~vtkLiverContourParameterizer() override;

  int RequestData(vtkInformation *,
                  vtkInformationVector **,
                  vtkInformationVector *) override;

 private:
  vtkLiverContourParameterizer(const vtkLiverContourParameterizer &) = delete;
  void operator=(const vtkLiverContourParameterizer &) = delete;

  int Mode;
  int Order;
  int NumberOfReconstructionPoints;
  double Locus[3];
  bool UseComputedLocus;

  vtkSmartPointer<vtkDoubleArray> Contour;
  std::vector<double> Coefficients;
  std::vector<double> DC;
  std::vector<double> Reconstruction;
};

#endif  // __vtkLiverContourParameterizer_h_
