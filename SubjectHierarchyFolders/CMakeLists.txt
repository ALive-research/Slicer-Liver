# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

#-----------------------------------------------------------------------------
# Standalone wrapped Subject-Hierarchy folder utility kit
# ``vtkSlicerSubjectHierarchyFolders`` (T5.2-f programmatic
# Subject-Hierarchy management).
#
# ADR-0023 §"Subject Hierarchy management convention": centralises the
# per-stage SH-folder lookup / lazy-create / reparent dance behind one
# binary-identical implementation shared by the C++ module logics
# (VascularTerritories, LiverResections) and the Python caller
# (LiverSegmentation).  ADR-0004 reasoned exception: wrapped C++ rather
# than Python-by-default, because only wrapped C++ is reachable from both
# the C++ callers and the Python caller (see the ADR amendment).
#
# The kit name carries no ``Liver`` prefix (closed-vocabulary convention,
# the T2.7 rename family).  It is a pure ``vtkObject`` utility, not a
# ``vtkMRMLNode``, and links MRMLCore only (ADR-0003 testability
# invariant; ADR-0008 §2 "C++ low-level").
#
# ``SlicerMacroBuildModuleMRML`` builds the wrapped VTK library and emits
# the Python module ``vtkSlicerSubjectHierarchyFoldersPython`` that the
# LiverSegmentation consumer + the reachability pytest import.  Although
# this is not a "module", the macro is the project's wrapped-VTK-library
# entry point; ``FOLDER`` is passed explicitly so it does not depend on a
# ``MODULE_NAME`` (this directory is a standalone kit, not a module).

project(vtkSlicerSubjectHierarchyFolders)

set(KIT ${PROJECT_NAME})

set(${KIT}_EXPORT_DIRECTIVE "VTK_SLICER_SUBJECTHIERARCHYFOLDERS_EXPORT")

set(${KIT}_INCLUDE_DIRECTORIES)

set(${KIT}_SRCS
  vtkSlicerSubjectHierarchyFolders.h
  vtkSlicerSubjectHierarchyFolders.cxx
  )

set(${KIT}_TARGET_LIBRARIES
  ${MRML_LIBRARIES}
  )

#-----------------------------------------------------------------------------
SlicerMacroBuildModuleMRML(
  NAME ${KIT}
  FOLDER "SubjectHierarchyFolders"
  EXPORT_DIRECTIVE ${${KIT}_EXPORT_DIRECTIVE}
  INCLUDE_DIRECTORIES ${${KIT}_INCLUDE_DIRECTORIES}
  SRCS ${${KIT}_SRCS}
  TARGET_LIBRARIES ${${KIT}_TARGET_LIBRARIES}
  )

#-----------------------------------------------------------------------------
# C++ low-level test (ADR-0008 §2 "C++ low-level" row, ctkTest driver,
# no Slicer launch, no Qt).  Landed test-first per ADR-0027 ahead of this
# implementation; the kit class above flips it green.
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()
