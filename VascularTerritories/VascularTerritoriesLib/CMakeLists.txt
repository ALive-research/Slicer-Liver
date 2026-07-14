#-----------------------------------------------------------------------------
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# VascularTerritories vessel-adhering-highlight — Python install rules
# for the pure-Python pick core (and, in later increments, the LayerDM
# highlight pipeline).
#
# Mirrors the ``<Module>Lib`` convention used by ``LiverResectionsLib``
# and Slicer-core's ``MarkupsLib``: a Python sub-package staged
# alongside the scripted module so it is importable at runtime and from
# the bare unit layer.
#
# Layout:
#
# * ``VascularTerritoriesLib/__init__.py`` — re-exports the public
#   pick-core class.
# * ``VascularTerritoriesLib/VesselSurfacePick.py`` — the pure-VTK pick
#   core (ADR-0004 Python pick math, ADR-0025 locator pattern).
#-----------------------------------------------------------------------------

set(VascularTerritoriesLib_PYTHON_SCRIPTS
  __init__.py
  VesselSurfacePick.py
  VesselHighlightPipeline.py
  TerritoryPlacementPipeline.py
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
