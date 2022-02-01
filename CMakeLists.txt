cmake_minimum_required(VERSION 3.13.4)

project(SlicerLiver)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/SlicerLiver")
set(EXTENSION_CATEGORY "Liver")
set(EXTENSION_CONTRIBUTORS "Rafael Palomar (Oslo University Hospital / NTNU), Ole Vegard Solberg (SINTEF), Geir Arne Tangen (SINTEF), Javier Pérez de Frutos (SINTEF)")
set(EXTENSION_DESCRIPTION "3D Slicer extension for liver analysis and therapy planning")
set(EXTENSION_ICONURL "http://www.slicer.org/slicerWiki/images/f/ff/SlicerLiver.png")
set(EXTENSION_SCREENSHOTURLS "http://www.slicer.org/slicerWiki/images/a/ae/BasicLiverResection.png")
set(EXTENSION_DEPENDS "Markups")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LiverMarkups)
add_subdirectory(LiverResections)
add_subdirectory(Liver)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
