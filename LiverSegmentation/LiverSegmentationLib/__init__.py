# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""LiverSegmentationLib — Stage 2 (Anatomy Definition) helper package.

Mirrors the ``<Module>Lib`` convention every sibling module uses (e.g.
``LiverResections/LiverResectionsLib``): the per-tool wrappers live under
this package, NOT at the module root.  Keeping the module root free of an
``__init__.py`` is load-bearing — Slicer's file-based scripted-module factory
scans the module's source directory (passed on ``--additional-module-paths``)
and would otherwise try to instantiate a root ``__init__`` as a scripted
module, half-initialising the launched application.  Housing the package one
level down keeps the module root a plain directory of ``.py`` scripted-module
files.

This package marker also lets the Stage-2 wrappers import as a regular Python
package outside a launched Slicer (bare ``pytest`` / CI), which is what lets
the import-purity invariant in
``Testing/Python/test_liversegmentation_import_purity.py`` exercise
``import LiverSegmentationLib.ToolWrappers.TotalSegmentator`` with no Slicer
build present (see ``Docs/adr/0024-segmentation-orchestration.md``
§"Lazy install for AI backends").

Import-time purity is load-bearing: this file (and everything it transitively
imports at module-import time) must stay free of the AI-backend install code
path.  That code path lives exclusively under ``ToolWrappers/`` and fires only
on first surgeon invocation; the orchestrator and this package marker never
trigger an install at import.

In a launched Slicer the scripted module proper is loaded from the staged
``LiverSegmentation.py`` file by Slicer's file-based scripted-module factory
(it execs the file directly, not via this package), and the orchestrator
imports its wrappers from this ``LiverSegmentationLib`` package.  This
``__init__`` is therefore intentionally inert.
"""

from __future__ import annotations
