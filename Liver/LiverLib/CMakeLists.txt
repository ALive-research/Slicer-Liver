#-----------------------------------------------------------------------------
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Python helpers for the Liver scripted module.
#
# Mirrors the LiverResectionsLib/CMakeLists.txt pattern: compile a
# Python sub-package alongside the scripted module so the helper
# files import as ``LiverLib.<name>`` from a launched Slicer.
#
# Slicer's scripted-module loader does NOT sweep subdirectories of
# the module's source tree -- only top-level .py files in
# ``Liver/`` are treated as scripted modules.  Therefore files here
# (e.g. ``legacy_logic.py``) are safely importable Python helpers
# without triggering the "class <FileName> not found" loader error.
#-----------------------------------------------------------------------------

set(LiverLib_PYTHON_SCRIPTS
  __init__.py
  legacy_logic.py
  )

set(LiverLib_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME LiverLib
  SCRIPTS "${LiverLib_PYTHON_SCRIPTS}"
  RESOURCES "${LiverLib_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/LiverLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/LiverLib
  NO_INSTALL_SUBDIR
  )
