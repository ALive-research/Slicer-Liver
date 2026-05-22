# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
# ==============================================================================
#
# MRML kit for the v2.0.0 vascular-territories class hierarchy
# (ADR-0023 §"Class abstraction for territories" + the architecture
# UML in Docs/architecture/territories-class-hierarchy.md).
#
# The kit name (``vtkSlicerVascularTerritoriesModuleMRML``) is
# decoupled from the parent module's MODULE_NAME (which is still
# ``LiverSegments`` for in-process Python compatibility); the symbol
# rename of the parent scripted module is a separate task tracked by
# the follow-up implementer commit.
#
# Sibling-of-source layout matches LiverResections/MRML/CMakeLists.txt.

project(vtkSlicerVascularTerritoriesModuleMRML)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES)

set(${KIT}_SRCS
  vtkMRMLAbstractTerritoriesNode.h
  vtkMRMLAbstractTerritoriesNode.cxx
  vtkMRMLStdCouinaudTerritoriesNode.h
  vtkMRMLStdCouinaudTerritoriesNode.cxx
  vtkMRMLCustomTerritoriesNode.h
  vtkMRMLCustomTerritoriesNode.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  ${MRML_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleMRML(
  NAME ${KIT}
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
)

#-----------------------------------------------------------------------------
# C++ low-level tests (ADR-0008 §2 "C++ low-level" row, ctkTest driver,
# no Slicer launch, no Qt).  The skeletons are deliberately red against
# the stub .cxx — the follow-up implementer commit fills in bodies and
# the same tests go green.  ADR-0027 test-first discipline.
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
