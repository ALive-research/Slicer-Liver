# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""LiverSegmentation — Stage 2 (Anatomy Definition) scripted module package.

This package marker exists so the Stage-2 orchestrator and its per-tool
wrappers are importable as a regular Python package outside a launched
Slicer (bare ``pytest`` / CI), which is what lets the import-purity
invariant in ``Testing/Python/test_liversegmentation_import_purity.py``
exercise ``import LiverSegmentation`` and
``import LiverSegmentation.ToolWrappers.TotalSegmentator`` with no Slicer
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
imports its wrappers from the separately-staged ``LiverSegmentationLib``
sub-package.  This ``__init__`` is therefore intentionally inert.
"""

from __future__ import annotations
