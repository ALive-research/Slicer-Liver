# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
# ==============================================================================
#
# MRML kit for the ADR-0038-amendment LiverVolumetry seeds-off-markups
# migration (volumetry-seeds-layerdm-plan.md §3a): the seed data carrier,
# its storage node, and the data-only seed-placement display node.
#
# The kit name ``vtkSlicerLiverVolumetryModuleMRML`` follows the project's
# per-module kit-library convention (matches MODULE_NAME = ``LiverVolumetry``).
#
# Sibling-of-source layout matches VascularTerritories/MRML/CMakeLists.txt.

project(vtkSlicerLiverVolumetryModuleMRML)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_LIVERVOLUMETRY_MODULE_MRML_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES)

set(${KIT}_SRCS
  vtkMRMLVolumetrySeedsNode.h
  vtkMRMLVolumetrySeedsNode.cxx
  vtkMRMLVolumetrySeedsStorageNode.h
  vtkMRMLVolumetrySeedsStorageNode.cxx
  vtkMRMLVolumetrySeedsDisplayNode.h
  vtkMRMLVolumetrySeedsDisplayNode.cxx
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
