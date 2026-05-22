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
