# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# ADR-0038 shared control-point interaction base (SlicerLiverInteractionLib).
#
# This directory hosts the Python interaction base classes extracted from
# the resection pipelines (ADR-0038 §"Shared home + names"): SurfacePick,
# PointPlacementState, SurfacePointPlacementPipeline3D/Slice, PointProvider,
# and the shared constants.  It is a pure-Python Lib (ADR-0004) hosting NO
# displayable manager (ADR-0013 §5) -- it supplies only the Pipeline base
# classes each module's own creator instantiates.
#
# The first extraction slice lands the pure-VTK SurfacePick and the
# namespaced PointPlacementState accessors; the Pipeline base classes + the
# PointProvider seam follow in a later slice.
#
# Python install rules mirror the ``<Module>Lib`` convention used by
# ``VascularTerritoriesLib`` / ``LiverResectionsLib``: a Python package
# staged alongside the scripted modules so it is importable at runtime and
# from the bare unit layer.  EVERY runtime module MUST be listed:
# ctkMacroCompilePythonScript stages ONLY the listed scripts into the
# build/install tree.

set(SlicerLiverInteractionLib_PYTHON_SCRIPTS
  __init__.py
  SurfacePick.py
  PointPlacementState.py
  SlicePointProjection.py
  PointProvider.py
  SurfacePointPlacementPipeline3D.py
  SurfacePointPlacementPipelineSlice.py
  )

set(SlicerLiverInteractionLib_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME SlicerLiverInteractionLib
  SCRIPTS "${SlicerLiverInteractionLib_PYTHON_SCRIPTS}"
  RESOURCES "${SlicerLiverInteractionLib_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/SlicerLiverInteractionLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/SlicerLiverInteractionLib
  NO_INSTALL_SUBDIR
  )

if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
