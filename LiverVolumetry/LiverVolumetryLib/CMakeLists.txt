#-----------------------------------------------------------------------------
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# LiverVolumetry seeds-off-markups client — Python install rules for the
# pure carrier->transient-fiducial adapter, the flat PointProvider adapter,
# the in-volume slice-click pick, and the LayerDM Pipeline creators (ADR-0038
# implementation amendment; volumetry-seeds-layerdm-plan.md §3).
#
# Mirrors the ``<Module>Lib`` convention used by ``VascularTerritoriesLib``
# and ``LiverResectionsLib``: a Python sub-package staged alongside the
# scripted module so it is importable at runtime and from the bare unit layer.
#
# EVERY runtime module MUST be listed below: ctkMacroCompilePythonScript
# stages ONLY the listed scripts into the build/install tree, and the
# package ``__init__`` swallows a missing-module ImportError (degrading the
# feature to silently disabled).  A file present on disk but absent here
# works in the source tree yet vanishes in an installed build.
#-----------------------------------------------------------------------------

set(LiverVolumetryLib_PYTHON_SCRIPTS
  __init__.py
  TransientVolumetrySeeds.py
  VolumetrySeedProvider.py
  InVolumePick.py
  SeedTargetResolution.py
  VolumetrySeedPipeline.py
  VolumetrySeedsTableWidget.py
  )

set(LiverVolumetryLib_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME LiverVolumetryLib
  SCRIPTS "${LiverVolumetryLib_PYTHON_SCRIPTS}"
  RESOURCES "${LiverVolumetryLib_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/LiverVolumetryLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/LiverVolumetryLib
  NO_INSTALL_SUBDIR
  )
