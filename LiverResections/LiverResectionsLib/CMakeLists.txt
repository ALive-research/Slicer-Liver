#-----------------------------------------------------------------------------
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# T2.6-LayerDM — Python install rules for the LayerDM Pipeline classes.
#
# Mirrors the convention used by Slicer-core's ``MarkupsLib`` and the
# upstream ``LayerDMLib``: compile a Python sub-package alongside the
# loadable module so the C++ ``setup()`` can ``import
# LiverResectionsLib`` and call its registration helper (ADR-0013 §5
# call 3).
#
# Layout (matches the Slicer-core ``<Module>Lib`` convention):
#
# * ``LiverResectionsLib/__init__.py`` — re-exports
#   ``registerPipelineCreator`` + ``LiverBezierSurfacePipeline``.
# * ``LiverResectionsLib/LiverBezierSurfacePipeline.py`` — the
#   Pipeline class (ADR-0013 §4) + the creator registration helper
#   (ADR-0013 §5 call 3).
# * ``LiverResectionsLib/Representations/`` — one Python module per
#   Representation class (ADR-0013 §6).
#-----------------------------------------------------------------------------

set(LiverResectionsLib_PYTHON_SCRIPTS
  __init__.py
  ControlPolygonPipeline.py
  DistanceMaps.py
  LiverBezierSurfacePipeline.py
  LocatorReslicer.py
  ResectionPlanningWidget.py
  ResectionStateMachine.py
  ResectogramLocatorProducer.py
  ResectogramPipeline.py
  SliceContourPipeline.py
  SliceControlPolygonPipeline.py
  TargetModel.py
  ResectogramViewManager.py
  Representations/__init__.py
  Representations/BezierPlanningRepresentation.py
  Representations/ConfirmedRepresentation.py
  Representations/DistanceSpheroidInitRepresentation.py
  Representations/SlicingPlaneInitRepresentation.py
  Representations/FlattenedSurfaceRepresentation.py
  Representations/VascularContourRepresentation.py
  )

set(LiverResectionsLib_PYTHON_RESOURCES
  )

ctkMacroCompilePythonScript(
  TARGET_NAME LiverResectionsLib
  SCRIPTS "${LiverResectionsLib_PYTHON_SCRIPTS}"
  RESOURCES "${LiverResectionsLib_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}/LiverResectionsLib
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}/LiverResectionsLib
  NO_INSTALL_SUBDIR
  )
