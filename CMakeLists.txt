cmake_minimum_required(VERSION 3.13.4)

project(SlicerLiver)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/ALive-research/Slicer-Liver")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_STATUS "Beta")
set(EXTENSION_CONTRIBUTORS "Rafael Palomar (Oslo University Hospital / NTNU), Ole V. Solberg (SINTEF), Geir A. Tangen (SINTEF), Egidijus Pelanis (Oslo University Hospital), Davit Aghayan (Oslo University Hospital), Gabriella D'Albenzio (Oslo University Hospital), Ruoyan Meng (NTNU), Javier Perez-de-Frutos (SINTEF), Ruoyan Meng (NTNU)")
set(EXTENSION_DESCRIPTION "3D Slicer extension for liver analysis and therapy planning")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/SlicerLiver.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_01.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_02.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_03.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_04.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_05.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_06.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_07.png https://raw.githubusercontent.com/ALive-research/Slicer-Liver/main/Screenshots/Slicer-Liver_screenshot_08.png")
set(EXTENSION_DEPENDS
  SlicerVMTK
  SegmentEditorExtraEffects
  ExtraMarkups
  # Upstream is the SlicerLayerDisplayableManager repo
  # (https://github.com/KitwareMedical/SlicerLayerDisplayableManager) but
  # its ``project()`` and exported ``*Config.cmake`` file are named
  # ``LayerDisplayableManager``.  The EXTENSION_DEPENDS entry must
  # match the project name so Slicer's launcher-settings block
  # (``SlicerBlockAdditionalLauncherSettings.cmake``) can
  # ``find_package(${dep})`` it and forward its
  # ``LIBRARY_PATHS_LAUNCHER_BUILD`` + ``PYTHONPATH_LAUNCHER_BUILD``
  # into the launcher's module-paths list.  Otherwise the upstream
  # ``vtkSlicerLayerDMModule*`` libraries land on ``_DIR-NOTFOUND``
  # entries in the launcher INI and the LayerDM Python symbols never
  # become importable from ``slicer`` at runtime.
  LayerDisplayableManager
  )

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)

# Patch the SlicerVMTK launcher paths.  ``SlicerVMTKConfig.cmake``
# (image-installed, not modifiable from here) exports
# ``SlicerVMTK_LIBRARY_PATHS_LAUNCHER_BUILD`` pointing at
# ``${SlicerVMTK_DIR}/../lib/Slicer-5.11/.`` -- which doesn't exist,
# because the SuperBuild leaves the actual VMTK runtime libraries +
# Python wrappers under the inner sub-build at
# ``${SlicerVMTK_DIR}/../SlicerVmtk-build/lib/Slicer-5.11/qt-loadable-modules/``
# instead of staging them in the location the Config advertises.
# Without the fix below ``libqSlicerBranchClipperModule.so`` fails
# to ``dlopen libvtkvmtkCommon.so`` and ``ExtractCenterline.py``
# fails to ``import vtkvmtkComputationalGeometryPython``.
#
# We cannot just ``list(APPEND SlicerVMTK_*_LAUNCHER_BUILD ...)`` in
# this scope because ``SlicerBlockAdditionalLauncherSettings.cmake``
# (included transitively from ``Slicer_USE_FILE`` below) re-runs
# ``find_package(SlicerVMTK QUIET)`` per dependency, which
# re-executes ``SlicerVMTKConfig.cmake`` and overwrites any prior
# in-scope append.
#
# The supported extension point is the ``_EP_LABEL_*_LAUNCHER_BUILD``
# list mechanism that the block also iterates over (after the
# per-EXTENSION_DEPENDS find_package loop): variable names
# registered there are read AFTER find_package and their values
# appended to the aggregate launcher INI list.  Pattern mirrors the
# canonical SlicerSOFA ``SuperBuild/External_Sofa.cmake`` block
# (PR Slicer/SlicerSOFA#43 and successors).
# Resolve ``SlicerVMTK_DIR`` here from ``$ENV{...}`` rather than the
# CMake cache variable: at this point in the file (BEFORE the launcher
# block's ``find_package(SlicerVMTK QUIET)`` populates the cache var),
# the CMake-scope ``SlicerVMTK_DIR`` is empty.  The
# ``slicer-build-ubuntu2404`` image sets ``SlicerVMTK_DIR`` as a
# Dockerfile ``ENV`` so any container-based CI step inherits it
# without needing ``-DSlicerVMTK_DIR=...`` at the cmake invocation
# (the project's CI workflow only passes ``-DSlicer_DIR`` and
# ``-DLayerDisplayableManager_DIR`` explicitly).  If the env var is
# unset (e.g. host-side development outside the image), the IS_DIRECTORY
# guard below skips the patch and the launcher INI degrades to the
# upstream broken-paths shape -- ``ExtractCenterline`` then fails at
# runtime exactly as before this fix, surfacing the missing env.
set(_slicervmtk_dir_from_env "$ENV{SlicerVMTK_DIR}")
set(_slicervmtk_superbuild_lib "${_slicervmtk_dir_from_env}/../SlicerVmtk-build/${Slicer_QTLOADABLEMODULES_LIB_DIR}")

if(NOT _slicervmtk_dir_from_env OR NOT IS_DIRECTORY "${_slicervmtk_superbuild_lib}")
  message(WARNING
    "Slicer-Liver: SlicerVMTK SuperBuild inner library directory not "
    "found at [${_slicervmtk_superbuild_lib}] (env SlicerVMTK_DIR="
    "[${_slicervmtk_dir_from_env}]).  The VMTK runtime path correction "
    "for the launcher INI will be skipped; ``ExtractCenterline`` and "
    "VMTK Python wrappers will fail to load.  This is expected when "
    "building outside the slicer-build-ubuntu2404 CI image.")
endif()

set(SlicerVMTK_SuperBuildLib_LIBRARY_PATHS_LAUNCHER_BUILD
  "${_slicervmtk_superbuild_lib}"
  )
set(SlicerVMTK_SuperBuildLib_PYTHONPATH_LAUNCHER_BUILD
  "${_slicervmtk_superbuild_lib}"
  )

# Variable name lookup in ``SlicerBlockAdditionalLauncherSettings.cmake``
# is ``${SUPERBUILD_TOPLEVEL_PROJECT}_EP_LABEL_<label>`` and
# ``SUPERBUILD_TOPLEVEL_PROJECT`` is initialised by
# ``ExternalProjectDependency.cmake`` to ``${CMAKE_PROJECT_NAME}`` --
# i.e. ``${PROJECT_NAME}_EP_LABEL_<label>`` for a non-SuperBuild leaf
# extension like this one.
list(APPEND ${PROJECT_NAME}_EP_LABEL_LIBRARY_PATHS_LAUNCHER_BUILD
  SlicerVMTK_SuperBuildLib_LIBRARY_PATHS_LAUNCHER_BUILD
  )
list(APPEND ${PROJECT_NAME}_EP_LABEL_PYTHONPATH_LAUNCHER_BUILD
  SlicerVMTK_SuperBuildLib_PYTHONPATH_LAUNCHER_BUILD
  )

include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Standalone wrapped Subject-Hierarchy folder utility kit
# (ADR-0023 §"Subject Hierarchy management convention").  Added before
# the consuming modules so its target exists when their Logic kits link
# it (VascularTerritories, LiverResections) and so its wrapped Python
# module is built for the LiverSegmentation consumer.
add_subdirectory(SubjectHierarchyFolders)

#-----------------------------------------------------------------------------
# ADR-0038 shared control-point interaction base (SlicerLiverInteractionLib).
# A pure-Python Lib (no displayable manager, ADR-0013 §5) supplying the
# Pipeline base classes each module's own creator instantiates.  Added
# before the consuming modules so its (future) sources + its Testing tree
# are configured ahead of the clients.
add_subdirectory(SlicerLiverInteractionLib)

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LiverResections)
add_subdirectory(VascularTerritories)
add_subdirectory(LiverSegmentation)
add_subdirectory(LiverVolumetry)
add_subdirectory(Liver)

#-----------------------------------------------------------------------------
# Shared (cross-module) pytest scaffold per ADR-0008.
# Per-module Slicer self-tests continue to register from their own
# <Module>/Testing/Python/CMakeLists.txt; this directory adds the
# pytest-driven scaffold and (in follow-up PRs) the cross-module fixtures.
add_subdirectory(Testing)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
