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
set(SlicerVMTK_SuperBuildLib_LIBRARY_PATHS_LAUNCHER_BUILD
  "${SlicerVMTK_DIR}/../SlicerVmtk-build/${Slicer_QTLOADABLEMODULES_LIB_DIR}"
  )
set(SlicerVMTK_SuperBuildLib_PYTHONPATH_LAUNCHER_BUILD
  "${SlicerVMTK_DIR}/../SlicerVmtk-build/${Slicer_QTLOADABLEMODULES_LIB_DIR}"
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
# Extension modules
add_subdirectory(LiverMarkups)
add_subdirectory(LiverResections)
add_subdirectory(VascularTerritories)
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
