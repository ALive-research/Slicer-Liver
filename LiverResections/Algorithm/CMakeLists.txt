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
# Eigen3 (header-only, MPL2).  Slicer's superbuild exposes Eigen via
# the standard Slicer_USE_FILE include; we also try find_package as
# a fall-back so direct CMake builds of the extension work too.
#-----------------------------------------------------------------------------
find_package(Eigen3 QUIET)

set(${KIT}_INCLUDE_DIRECTORIES
   ${CMAKE_CURRENT_BINARY_DIR}
  )
if(Eigen3_FOUND)
  list(APPEND ${KIT}_INCLUDE_DIRECTORIES ${EIGEN3_INCLUDE_DIR})
endif()

set(${KIT}_SRCS
  vtkLiverPlaneRingExtractor.h
  vtkLiverPlaneRingExtractor.cxx
  vtkLiverSpheroidRingExtractor.h
  vtkLiverSpheroidRingExtractor.cxx
  vtkLiverContourParameterizer.h
  vtkLiverContourParameterizer.cxx
  vtkLiverBezierFitter.h
  vtkLiverBezierFitter.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  ${VTK_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleLogic(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

# Eigen3 — header-only, attach as a PUBLIC dependency where the
# target supports it.  Slicer's superbuild path provides the include
# directory; the find_package call above is the system-install fallback.
if(Eigen3_FOUND AND TARGET Eigen3::Eigen)
  target_link_libraries(${KIT} PUBLIC Eigen3::Eigen)
endif()

#-----------------------------------------------------------------------------
# C++ low-level tests live next to the algorithm classes (ADR-0008 §2).
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
