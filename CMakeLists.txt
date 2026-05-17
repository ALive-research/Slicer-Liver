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
#-----------------------------------------------------------------------------
# Opt-in dependency on SlicerLayerDisplayableManager (LayerDM).  Enables
# T2.6-LayerDM development (Pipeline factory registration + the upstream
# library's vtkMRMLLayerDisplayableManager per ADR-0013 §5).  OFF by
# default — production builds and the canonical CI cell stay
# byte-identical.  See Docs/dependencies/SlicerLayerDM.md for the
# local-dev + CI build-layer workflow.
option(Slicer_Liver_USE_SlicerLayerDM
       "Build Slicer-Liver with SlicerLayerDM as an EXTENSION_DEPENDS entry."
       OFF)

set(EXTENSION_DEPENDS
  SlicerVMTK
  SegmentEditorExtraEffects
  ExtraMarkups
  )

if(Slicer_Liver_USE_SlicerLayerDM)
  list(APPEND EXTENSION_DEPENDS SlicerLayerDisplayableManager)
endif()

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LiverMarkups)
add_subdirectory(LiverResections)
add_subdirectory(LiverSegments)
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
