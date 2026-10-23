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
# LayerDisplayableManager is NOT listed here.  It moved into Slicer core
# and so is conditional -- see the SLICERLIVER_LAYERDM_IS_CORE block
# after find_package(Slicer), which appends it only when this Slicer
# does not already provide it.
set(EXTENSION_DEPENDS
  SlicerVMTK
  SegmentEditorExtraEffects
  ExtraMarkups
  )

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)

#-----------------------------------------------------------------------------
# LayerDM: a Slicer CORE module, or the standalone extension?
#
# LayerDM was an extension (KitwareMedical/SlicerLayerDisplayableManager)
# until Slicer merged it into core as ``Modules/Loadable/LayerDM``
# (Slicer PR 9184, 2026-10-07).  The catalog entry was then removed from
# the Slicer extensions index (index PR 2412, 2026-10-12), so on a Slicer
# that carries the core module there is no extension to depend on -- and
# on an older Slicer there is no core module to link.  Both are live:
# 5.12.x has only the extension, 5.13 and later have only the core
# module.
#
# Detected by TARGET EXISTENCE rather than by version arithmetic.
# ``SlicerTargets.cmake`` (included by ``SlicerConfig.cmake``, so already
# processed by the find_package above) exports core module libraries,
# and the core module builds the SAME kit name the extension did.  So
# the question "does this Slicer ship LayerDM?" is answerable directly,
# without hard-coding which release absorbed it -- a number that would
# be a guess today and a maintenance burden forever.
#
# This must sit AFTER find_package(Slicer) (the targets do not exist
# before it) and BEFORE ``include(${Slicer_USE_FILE})``, which is what
# consumes EXTENSION_DEPENDS.
if(TARGET vtkSlicerLayerDMModuleMRMLDisplayableManager)
  set(SLICERLIVER_LAYERDM_IS_CORE ON)
  message(STATUS "Slicer-Liver: LayerDM provided by Slicer core")
else()
  set(SLICERLIVER_LAYERDM_IS_CORE OFF)
  message(STATUS "Slicer-Liver: LayerDM provided by the LayerDisplayableManager extension")
  # The EXTENSION_DEPENDS entry must match the upstream ``project()``
  # name so Slicer's launcher-settings block
  # (``SlicerBlockAdditionalLauncherSettings.cmake``) can
  # ``find_package(${dep})`` it and forward its
  # ``LIBRARY_PATHS_LAUNCHER_BUILD`` + ``PYTHONPATH_LAUNCHER_BUILD``
  # into the launcher's module-paths list.  Otherwise the upstream
  # ``vtkSlicerLayerDMModule*`` libraries land on ``_DIR-NOTFOUND``
  # entries in the launcher INI and the LayerDM Python symbols never
  # become importable from ``slicer`` at runtime.
  list(APPEND EXTENSION_DEPENDS LayerDisplayableManager)
endif()

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
# Launched-Slicer module paths for LayerDM.
#
# The launched Python tests need the LayerDM modules REGISTERED with the
# module manager, not merely importable, so they pass the extension's
# module trees via ``--additional-module-paths``.
#
# EMPTY when LayerDM is core: core modules are already on Slicer's own
# module path, and ``LayerDisplayableManager_DIR`` is then undefined --
# expanding it anyway would feed the launcher paths like
# ``/lib/Slicer-5.13/qt-loadable-modules``, which are not merely useless
# but actively wrong.
#
# ``SLICERLIVER_LAYERDM_SLICER_ARGS`` carries the FLAG as well as the
# paths, because at the call sites where these are the only paths, an
# ``--additional-module-paths`` left with no values would swallow the
# following argument.
set(SLICERLIVER_LAYERDM_MODULE_PATHS "")
set(SLICERLIVER_LAYERDM_SLICER_ARGS "")
if(NOT SLICERLIVER_LAYERDM_IS_CORE)
  set(SLICERLIVER_LAYERDM_MODULE_PATHS
    "${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}"
    "${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}"
    )
  set(SLICERLIVER_LAYERDM_SLICER_ARGS
    --additional-module-paths
    ${SLICERLIVER_LAYERDM_MODULE_PATHS}
    )
endif()

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
