# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Stage 2 (Anatomy Definition) scripted module per
# Docs/adr/0024-segmentation-orchestration.md.
#
# Pure Python: the orchestrator + tool wrappers are Python only (ADR-0004
# §Python/C++ boundary — no new C++ MRML node classes in v2.0).  Therefore
# NO add_subdirectory(Logic).
#
# This module declares NO hard extension dependency on the AI backends: the
# segmentation tool is lazy-installed on first surgeon use (ADR-0024 §"Lazy
# install"); the server-architecture backend is out of v2.0 scope (ADR-0024
# Alternative H).  Conformance-pinned by
# Testing/Python/test_liversegmentation_conformance.py.

#-----------------------------------------------------------------------------
set(MODULE_NAME LiverSegmentation)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  )

#-----------------------------------------------------------------------------
# Per-tool wrappers live under LiverSegmentationLib/, mirroring the
# ``<Module>Lib`` convention every sibling module uses (e.g.
# LiverResections/LiverResectionsLib).  The module ROOT carries NO
# __init__.py: Slicer's scripted-module factory scans the module's source
# directory (passed on --additional-module-paths) and would try to
# instantiate a root __init__ as a scripted module, half-initialising the
# launched application.  Housing the package one level down keeps the module
# root a plain directory of .py scripted-module files; the wrappers stage and
# import as ``LiverSegmentationLib.ToolWrappers.<name>`` both in a launched
# Slicer and under bare pytest.
# SCRIPTS paths are package-relative (used as the staged sub-path under
# DESTINATION_DIR); SOURCE_DIR points the macro at the LiverSegmentationLib/
# source subdir so it resolves the moved files.  This keeps the staged layout
# at qt-scripted-modules/LiverSegmentationLib/ToolWrappers/... unchanged.
set(LiverSegmentationLib_PYTHON_SCRIPTS
  __init__.py
  ToolWrappers/__init__.py
  ToolWrappers/TotalSegmentator.py
  )

ctkMacroCompilePythonScript(
  TARGET_NAME LiverSegmentationLib
  SCRIPTS "${LiverSegmentationLib_PYTHON_SCRIPTS}"
  RESOURCES ""
  SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/LiverSegmentationLib
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/LiverSegmentationLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/LiverSegmentationLib
  NO_INSTALL_SUBDIR
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
