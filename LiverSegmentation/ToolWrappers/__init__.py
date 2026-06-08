# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Per-tool wrappers for the LiverSegmentation Stage-2 orchestrator.

Each wrapper isolates one external segmenter consumed via its Python API
(currently TotalSegmentator in v2.0 per
``Docs/adr/0024-segmentation-orchestration.md`` §"Per-structure
micro-workflows").  The lazy-install code path (ADR-0024 §"Lazy install
for AI backends") lives here and nowhere else in the module: the
orchestrator and widget never call ``slicer.util.pip_install``.

Import-time purity invariant: no wrapper may ``import totalsegmentator`` nor
call ``pip_install`` at module-import time.  Both are deferred to the
call path (``ensureBackendInstalled`` / ``run``), so this package and its
members import cleanly with no network and no multi-GB model download.
"""

from __future__ import annotations
