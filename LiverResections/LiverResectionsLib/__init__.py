# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LiverResectionsLib — Python helpers loaded by the C++ loadable module.

This package is installed alongside the ``LiverResections`` loadable
module per ADR-0013 §7 (file layout) and exposes the LayerDM
Pipeline-creator registration entry point that
``qSlicerLiverResectionsModule::setup()`` invokes via
``pythonManager()->executeString(...)``.

The Pipeline class itself lives at
``LiverResections/LiverBezierSurfacePipeline.py`` per ADR-0013 §7 and
is mirrored into this package via the install rules in
``LiverResections/Python/CMakeLists.txt`` so it imports as
``LiverResectionsLib.LiverBezierSurfacePipeline`` from a launched
Slicer process.
"""

from .LiverBezierSurfacePipeline import (
    LiverBezierSurfacePipeline,
    registerPipelineCreator,
)

__all__ = [
    "LiverBezierSurfacePipeline",
    "registerPipelineCreator",
]
