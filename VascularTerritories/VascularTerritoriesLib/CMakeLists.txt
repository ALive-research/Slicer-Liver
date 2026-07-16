#-----------------------------------------------------------------------------
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# VascularTerritories annotation + vessel-adhering-highlight — Python
# install rules for the pure-Python pick core, the shared interaction
# state, the LayerDM placement/highlight/slice pipelines, and the
# annotation table widget (ADR-0037).
#
# Mirrors the ``<Module>Lib`` convention used by ``LiverResectionsLib``
# and Slicer-core's ``MarkupsLib``: a Python sub-package staged
# alongside the scripted module so it is importable at runtime and from
# the bare unit layer.
#
# EVERY runtime module MUST be listed below: ctkMacroCompilePythonScript
# stages ONLY the listed scripts into the build/install tree, and the
# package ``__init__`` swallows a missing-module ImportError (degrading
# the feature to silently disabled).  A file present on disk but absent
# here works in the source tree yet vanishes in an installed build.
#-----------------------------------------------------------------------------

set(VascularTerritoriesLib_PYTHON_SCRIPTS
  __init__.py
  VesselSurfacePick.py
  VesselHighlightWiring.py
  VesselHighlightPipeline.py
  TerritoryInteractionState.py
  TerritoryPlacementPipeline.py
  TerritorySliceProjection.py
  TerritorySlicePipeline.py
  TerritoriesTableWidget.py
  )

set(VascularTerritoriesLib_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME VascularTerritoriesLib
  SCRIPTS "${VascularTerritoriesLib_PYTHON_SCRIPTS}"
  RESOURCES "${VascularTerritoriesLib_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/VascularTerritoriesLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/VascularTerritoriesLib
  NO_INSTALL_SUBDIR
  )
