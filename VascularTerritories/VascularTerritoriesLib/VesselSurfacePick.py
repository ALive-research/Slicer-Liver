# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Compatibility re-export of the shared ``SurfacePick`` pick core.

ADR-0038 §"Shared home + names" extracted the vessel-adhering pick core out
of this module into the shared ``SlicerLiverInteractionLib`` package as
``SurfacePick`` (the ``Vessel`` prefix dropped, T2.7).  This module now
re-exports that class under its original name so existing call sites and
the vessel-pick characterization test keep resolving ``VesselSurfacePick``
unchanged (the extraction is behaviour-preserving -- ADR-0038 [review]).

The dual import mirrors the ``<Module>Lib`` idiom used throughout this
package: the installed/built tree stages ``SlicerLiverInteractionLib``
alongside this package on the qt-scripted-modules path; the bare unit layer
sets ``sys.path`` to the individual Lib dir, so a sibling-directory fallback
keeps the shared core importable there too.
"""

from __future__ import annotations

try:
    from SlicerLiverInteractionLib.SurfacePick import SurfacePick
except ImportError:  # bare unit layer: add the sibling Lib dir to sys.path
    import pathlib
    import sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in sys.path:
        sys.path.insert(0, str(_shared_lib))
    from SurfacePick import SurfacePick  # type: ignore[no-redef]

#: Backwards-compatible alias for the extracted shared pick core.
VesselSurfacePick = SurfacePick

__all__ = ["VesselSurfacePick"]
