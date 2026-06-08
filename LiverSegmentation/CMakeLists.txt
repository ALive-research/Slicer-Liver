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
# Per-tool wrappers (ToolWrappers/) stage as an importable-but-not-swept
# Python sub-package, mirroring the LiverLib/ convention: Slicer's scripted-
# module factory scans only top-level .py files in qt-scripted-modules/, so
# these helpers import as ``LiverSegmentationLib.ToolWrappers.<name>`` from a
# launched Slicer without being mistaken for scripted modules.  The source
# tree keeps them under LiverSegmentation/ToolWrappers/ (where the
# conformance greps look); they stage under the LiverSegmentationLib package
# name to avoid a top-level ``ToolWrappers`` namespace collision and to avoid
# shadowing the LiverSegmentation.py scripted module on sys.path.
set(LiverSegmentationLib_PYTHON_SCRIPTS
  __init__.py
  ToolWrappers/__init__.py
  ToolWrappers/TotalSegmentator.py
  )

ctkMacroCompilePythonScript(
  TARGET_NAME LiverSegmentationLib
  SCRIPTS "${LiverSegmentationLib_PYTHON_SCRIPTS}"
  RESOURCES ""
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/LiverSegmentationLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/LiverSegmentationLib
  NO_INSTALL_SUBDIR
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
