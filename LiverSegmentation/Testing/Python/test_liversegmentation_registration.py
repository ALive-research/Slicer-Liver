# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 1 — module registration + isStageComplete() symbol surface.

Pins the first conformance bullet of
``Docs/adr/0024-segmentation-orchestration.md`` §Conformance
("``LiverSegmentation/`` exists as a scripted module ... hosts the
orchestrator class") and the Stage-2 predicate contract from
``Docs/adr/0023-unified-gui-stage-workflow.md`` §"Per-stage state-indicator
semantics".

The Liver shell (``Liver/Liver.py`` ``_STAGE_MODULE``) auto-discovers this
module under the Slicer module name ``liversegmentation`` and queries the
Python-convention ``isStageComplete()`` on its logic
(``LiverVolumetryLogic.isStageComplete()`` is the precedent).  This test
asserts that surface exists and is shaped correctly.

RED until the implementer lands ``LiverSegmentation/LiverSegmentation.py``
per ADR-0024.  Scene-needing: runs under a minimal qSlicerApplication.
"""

from __future__ import annotations

import pytest

# Slicer module name the Liver shell's ``_STAGE_MODULE`` maps Stage 2 to.
# Kept as a named constant so the registration contract is grep-able.
MODULE_NAME = "liversegmentation"


def _liversegmentation_logic():
    """Resolve the registered ``liversegmentation`` module's logic instance.

    Skips when the module is not on ``--additional-module-paths`` (so the
    scaffold stays green while the implementer's module is absent).
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- the implementer must "
            "land LiverSegmentation/LiverSegmentation.py per ADR-0024 and put "
            "it on --additional-module-paths."
        )
    return module.logic()


def test_module_registers_as_liversegmentation():
    """The scripted module registers under the Slicer name ``liversegmentation``.

    ADR-0024 §Conformance: ``LiverSegmentation/`` exists as a scripted module
    hosting the Stage-2 orchestrator; the Liver shell discovers it by this
    exact lowercase name (``Liver/Liver.py`` ``_STAGE_MODULE``).
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    assert module is not None, (
        f"'{MODULE_NAME}' not registered in slicer.modules -- ADR-0024 "
        "mandates a net-new LiverSegmentation scripted module the Liver shell "
        "auto-discovers via _STAGE_MODULE (no Liver.py edits)."
    )


def test_logic_exposes_callable_isstagecomplete_returning_bool():
    """The module logic exposes a callable ``isStageComplete()`` returning bool.

    Python-convention predicate per ADR-0023 §"Per-stage state-indicator
    semantics" (``LiverVolumetryLogic.isStageComplete()`` precedent).  The
    Liver shell calls this to drive the Stage-2 sidebar indicator.
    """
    logic = _liversegmentation_logic()
    assert hasattr(logic, "isStageComplete"), (
        "LiverSegmentation logic must expose isStageComplete() "
        "(Python convention, LiverVolumetryLogic precedent)."
    )
    predicate = logic.isStageComplete
    assert callable(predicate), "isStageComplete must be callable."
    result = predicate()
    assert isinstance(result, bool), (
        f"isStageComplete() must return bool, got {type(result).__name__}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
