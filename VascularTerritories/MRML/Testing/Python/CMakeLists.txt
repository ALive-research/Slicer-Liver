# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# Slicer-driven Python wrapper test for the v2.0.0 territories node
# hierarchy (ADR-0023 §"Class abstraction for territories").  Pins the
# Python-side polymorphic dispatch + Subject Hierarchy folder
# placement invariants; the C++ low-level tests pin the rest.

# Python tests must opt-in to LayerDisplayableManager module loading
# explicitly.  Slicer's ``slicer_add_python_unittest`` macro auto-
# appends only the *current project's* build-dir module paths to
# ``--additional-module-paths``; extension-dependency modules
# reachable via ``PYTHONPATH`` (set by ``SlicerBlockAdditionalLauncherSettings``)
# are import-able as Python packages but never loaded into the Slicer
# module manager, so ``from slicer import vtkMRMLLayerDMPipelineI``
# raises ``ImportError`` at test startup.  Mirrors the pattern
# SlicerLayerDM itself uses for its own Python tests
# (``SlicerLayerDM/LayerDM/Testing/Python/CMakeLists.txt``).
slicer_add_python_unittest(
  SCRIPT TerritoriesNodeWrapperTest.py
  SLICER_ARGS
    --additional-module-paths
    ${LayerDisplayableManager_DIR}/${Slicer_QTLOADABLEMODULES_LIB_DIR}
    ${LayerDisplayableManager_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
)
