# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 5 (UI) — a card Run produces exactly ONE scratch node.

ADR-0024 §"Per-structure micro-workflows" + §"Output contract": a structure
card's *Run* step drives the orchestrator to invoke the AI backend and land
its output in a single orchestrator-private **scratch**
``vtkMRMLSegmentationNode`` (``LiverSegmentation.Role`` = ``scratch``).  Run
must NOT create or mutate the canonical node — the canonical node only ever
grows via :meth:`accept` (ADR-0024 §Terminology "commit / Accept", rejecting
Alternative D auto-commit).

The orchestrator owns a ``segment(volume, sctTarget) -> scratchNode`` method
(the TotalSegmentator wrapper's ``run()`` was a stub).  A real TotalSegmentator
run cannot execute in CI (multi-GB model + GPU); this test **mocks the backend**
by monkeypatching the orchestrator's tool-invocation seam so it produces a
synthetic scratch segmentation, exercising the orchestrator/UI flow without a
real inference.

Scene-needing: runs under the launched-Slicer harness
(``Liver/Testing/Python/run_pytest_launched.py`` / ``pytest_launched``).
RED until the implementer lands ``segment()`` + the card Run wiring per
ADR-0024.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"

# SCT type codes per ADR-0024 §"Output contract" (confirmed against the
# Resources/Terminology/LabelToSCT/ bridges: TotalSegmentator.json liver +
# portal_vein_and_splenic_vein; KumarOram.json hepatic vein; Mass per the
# DICOM master list).  Named constants so the SCT contract is grep-able.
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"


def _orchestrator_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; card Run flow cannot be exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _segmentation_nodes(slicer, role):
    nodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    return [n for n in nodes if n.GetAttribute(ROLE_ATTRIBUTE) == role]


def _add_input_volume(slicer):
    """Add a Stage-1 PortalVenous-role scalar volume for the orchestrator input."""
    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    volume.SetAttribute("LiverRole", "PortalVenous")
    return volume


def _mock_backend_segment(monkeypatch, slicer, orch):
    """Monkeypatch the backend tool seam to mint a synthetic scratch node.

    A real TotalSegmentator run is impossible in CI; the invariant under test
    is the orchestrator/UI scratch-node bookkeeping, not inference accuracy.
    We replace whatever low-level tool-invocation helper ``segment()`` calls
    with a synthetic producer that adds one empty segment to a scratch node.

    TODO(impl): pin the exact seam name the implementer chooses (e.g.
    ``_runTotalSegmentator`` / the ToolWrappers.TotalSegmentator.run import).
    The pinned invariant is "Run -> one scratch node, canonical untouched",
    independent of the seam's spelling.
    """
    def _fake(volume, sctTarget, *args, **kwargs):
        scratch = orch.createScratchSegmentation()
        scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        return scratch

    for seam in ("_invokeBackend", "_runTotalSegmentator", "_segmentWithBackend"):
        if hasattr(orch, seam):
            monkeypatch.setattr(orch, seam, _fake)
            return
    pytest.fail(
        "orchestrator must expose a mockable backend seam called by "
        "segment() (e.g. _invokeBackend / _runTotalSegmentator) so CI can "
        "exercise the Run flow without a real TotalSegmentator inference "
        "(ADR-0024 §'Lazy install for AI backends') -- not yet implemented."
    )


def test_card_run_produces_exactly_one_scratch_node(monkeypatch):
    """Run mints one scratch node; no premature canonical node.

    ADR-0024 §"Per-structure micro-workflows" + §"Output contract": a card's
    Run step lands output in a scratch ``vtkMRMLSegmentationNode``; Run never
    creates the canonical node (that path is Accept-only, rejecting
    Alternative D).
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "segment"):
        pytest.fail(
            "orchestrator must expose segment(volume, sctTarget) -> "
            "scratchNode per ADR-0024 §'Per-structure micro-workflows' -- "
            "not yet implemented (the wrapper's run() was a stub)."
        )

    volume = _add_input_volume(slicer)
    _mock_backend_segment(monkeypatch, slicer, orch)

    scratch = orch.segment(volume, SCT_LIVER_CODE)

    assert scratch is not None and scratch.IsA("vtkMRMLSegmentationNode"), (
        "segment() must return a vtkMRMLSegmentationNode scratch node."
    )
    assert scratch.GetAttribute(ROLE_ATTRIBUTE) == ROLE_SCRATCH, (
        "segment() output must carry role=scratch (ADR-0024 §Terminology)."
    )
    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 1, (
        "exactly one scratch node must exist after a single Run."
    )
    assert len(_segmentation_nodes(slicer, ROLE_CANONICAL)) == 0, (
        "Run must NOT create the canonical node -- canonical grows only on "
        "Accept (ADR-0024 §Terminology, rejecting Alternative D auto-commit)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
