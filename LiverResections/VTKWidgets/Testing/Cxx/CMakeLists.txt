#-----------------------------------------------------------------------------
# C++ low-level tests for the LiverResections VTKWidgets library.
# Per ADR-0008 §2 — "C++ low-level" row, ctkTest driver, no Slicer
# launch, no Qt.  Pattern mirrors the Algorithm/Testing/Cxx and
# MRML/Testing/Cxx subdirectories.
#-----------------------------------------------------------------------------

set(KIT vtkSlicer${MODULE_NAME}ModuleVTKWidgets)

#-----------------------------------------------------------------------------
set(KIT_TEST_SRCS
  vtkLiverBezierWidgetTest1.cxx
  vtkOpenGLLiverResectionMappersRelocationTest1.cxx
  vtkOpenGLDistanceContourMapperSpheroidSSOTTest.cxx
  )

#-----------------------------------------------------------------------------
slicerMacroConfigureModuleCxxTestDriver(
  NAME ${KIT}
  SOURCES ${KIT_TEST_SRCS}
  INCLUDE_DIRECTORIES
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
    ${CMAKE_CURRENT_BINARY_DIR}/..
    # The spheroid-SSOT test calls
    # vtkLiverSpheroidRingExtractor::ComputeQuadricCoefficients directly
    # (the canonical (centre, radii) -> a0..a9 builder, ADR-0015
    # §"Stack 4").  Pull in the Algorithm library's headers + binary dir
    # (for its generated export header).
    ${vtkSlicer${MODULE_NAME}ModuleAlgorithm_SOURCE_DIR}
    ${vtkSlicer${MODULE_NAME}ModuleAlgorithm_BINARY_DIR}
  WITH_VTK_DEBUG_LEAKS_CHECK
  WITH_VTK_ERROR_OUTPUT_CHECK
  )

# The spheroid-SSOT test links the Algorithm library so it can call the
# single-source-of-truth coefficient builder directly (ADR-0015
# §"Stack 4").  The mapper's own link onto the Algorithm library is wired
# by the implementer in LiverResections/VTKWidgets/CMakeLists.txt.
target_link_libraries(${KIT}CxxTests
  vtkSlicer${MODULE_NAME}ModuleAlgorithm
  )

SIMPLE_TEST(vtkLiverBezierWidgetTest1)
SIMPLE_TEST(vtkOpenGLLiverResectionMappersRelocationTest1)

# GPU-path / SSOT consistency pin for the distance-spheroid init contour
# (ADR-0014 §2 triaxial-ellipsoid contour, ADR-0015 §"Stack 4" render ==
# extract).  RED-by-construction: the mapper seam SetSpheroid(...) /
# GetSpheroidQuadricCoefficients(...) does not exist yet, so the check is
# compiled out behind LIVER_SPHEROID_GPU_QUADRIC_SSOT and the test
# degrades to a CTest skip.  Once the implementer adds the seam (deriving
# the quadric via the SSOT) and links the Algorithm library into the
# mapper, define -DLIVER_SPHEROID_GPU_QUADRIC_SSOT here to lift the skip.
SIMPLE_TEST(vtkOpenGLDistanceContourMapperSpheroidSSOTTest)
set_tests_properties(vtkOpenGLDistanceContourMapperSpheroidSSOTTest PROPERTIES
  SKIP_RETURN_CODE 125
  )
# The mapper seam SetSpheroid(...) / GetSpheroidQuadricCoefficients(...)
# now exists and derives the quadric from the SSOT, and the Algorithm
# library is linked into VTKWidgets — lift the skip so the consistency
# check (mapper coeffs == SSOT) compiles in and the test runs for real.
set_property(SOURCE vtkOpenGLDistanceContourMapperSpheroidSSOTTest.cxx APPEND PROPERTY COMPILE_DEFINITIONS LIVER_SPHEROID_GPU_QUADRIC_SSOT)
