cmake_minimum_required(VERSION 3.13.4)

project(LiverAnalysis)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/LiverAnalysis")
set(EXTENSION_CATEGORY "Liver")
set(EXTENSION_CONTRIBUTORS "Rafael Palomar (The Intervention Centre, Oslo University Hospital), Ole Vegard Solberg (SINTEF)")
set(EXTENSION_DESCRIPTION "3D Slicer extension for liver analysis")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/LiverAnalysis.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/LiverAnalysis/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(LiverAnalysis)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
