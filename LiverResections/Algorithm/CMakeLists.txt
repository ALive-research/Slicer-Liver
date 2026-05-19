#-----------------------------------------------------------------------------
# LiverResections/Algorithm
#
# Pure-VTK algorithm library introduced by ADR-0015 (T2 Stack 1).
# Hosts four vtkAlgorithm-style classes used by the Init->Planning
# transition of the state-aware LiverResections Pipeline:
#
#   vtkLiverPlaneRingExtractor       — plane    n liver mesh -> ring
#   vtkLiverSpheroidRingExtractor    — spheroid n liver mesh -> ring
#   vtkLiverContourParameterizer     — ring -> parameterised curve
#                                     (corner-mapping or EFD mode)
#   vtkLiverBezierFitter             — parameterised curve -> 4x4 control grid
#
# Pure VTK + Eigen.  No MRML linkage (per ADR-0015 §1).  VTK Python
# wrapping is enabled via SlicerMacroBuildModuleLogic so the four
# classes are reachable from Slicer's bundled Python.
#-----------------------------------------------------------------------------

project(vtkSlicer${MODULE_NAME}ModuleAlgorithm)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_${MODULE_NAME_UPPER}_MODULE_ALGORITHM_EXPORT")

#-----------------------------------------------------------------------------
# Eigen3 (header-only, MPL2).
#
# Slicer does NOT expose Eigen as a top-level superbuild dep — it lives
# inside ITK as `ITKInternalEigen3` (a private bundle) and inside VTK's
# ThirdParty tree (also private).  The cleanest way to reach a public
# Eigen3::Eigen target from an extension is to point `find_package(Eigen3)`
# at ITK's bundled config.  ITK is already pulled in transitively by
# Slicer's `Slicer_USE_FILE`, so `${ITK_DIR}` is set in this scope.
#
# Required (not QUIET) — if Eigen3 is not findable the build must fail
# loud rather than silently compile without the include path (which was
# the cause of the first CI failure on PR #334).
#-----------------------------------------------------------------------------
find_package(ITK REQUIRED)
find_package(Eigen3 REQUIRED CONFIG
  HINTS
    "${ITK_DIR}/ITKInternalEigen3-build"
    "${ITK_DIR}/../ITK-build/ITKInternalEigen3-build"
  )

set(${KIT}_INCLUDE_DIRECTORIES
   ${CMAKE_CURRENT_BINARY_DIR}
  )

set(${KIT}_SRCS
  vtkLiverPlaneRingExtractor.h
  vtkLiverPlaneRingExtractor.cxx
  vtkLiverSpheroidRingExtractor.h
  vtkLiverSpheroidRingExtractor.cxx
  vtkLiverContourParameterizer.h
  vtkLiverContourParameterizer.cxx
  vtkLiverBezierFitter.h
  vtkLiverBezierFitter.cxx
  vtkSlicerLiverBezierControlPolygonGeometry.h
  vtkSlicerLiverBezierControlPolygonGeometry.cxx
  )

#
# Eigen3::Eigen is an INTERFACE target (header-only); folding it into
# ${KIT}_TARGET_LIBRARIES lets Slicer's macro handle the link in its
# plain target_link_libraries(...) form.  An explicit
# `target_link_libraries(${KIT} PUBLIC Eigen3::Eigen)` after the macro
# is forbidden — Slicer mixes plain and keyword forms inside the same
# target, and CMake rejects that mix.
#
set(${KIT}_TARGET_LIBRARIES
  ${VTK_LIBRARIES}
  Eigen3::Eigen
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

#-----------------------------------------------------------------------------
# C++ low-level tests live next to the algorithm classes (ADR-0008 §2).
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
