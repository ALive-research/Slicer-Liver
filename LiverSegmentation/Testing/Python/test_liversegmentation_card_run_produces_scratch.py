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


# =========================================================================== #
# Silent-hand-off GUARD — a card Run with no PortalVenous volume must not
# silently drive the backend with a None volume.
# =========================================================================== #
#
# ``_StructureCard.onRun`` calls ``self._widget.logic.segment(volume, ...)``
# where ``volume = selectInputVolume()`` is None when no Stage-1
# ``LiverRole='PortalVenous'`` volume exists.  A None volume must NOT reach
# ``segment()`` (no scratch node minted, no misleading progress bar); instead
# the card surfaces feedback on ``statusLabel`` and leaves Accept/Reject
# disabled.  The counterpart: WITH a PortalVenous volume, Run proceeds.
#
# ADR-0024 §"Per-structure micro-workflows" (the Stage-1/Stage-2 hand-off is
# an explicit precondition, not a silent no-op); test-first per ADR-0027.


def _require_qt_widget_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_card_or_skip(slicer, orch, sctCode):
    """Build one ``_StructureCard`` GL-free on a stand-in widget.

    The card only touches its owning widget through ``self._widget.logic``;
    it does not need the full ``LiverSegmentationWidget`` (which builds a
    QTabWidget + scene observers).  A minimal stand-in carrying the real
    orchestrator ``logic`` exercises the real ``selectInputVolume`` /
    ``segment`` paths while keeping construction cheap and GL-free (only the
    card's own QPushButton/QLabel/QProgressBar are built; nothing renders).

    ``_refreshTabGlyphs`` is stubbed on the stand-in so ``onAccept``'s call is
    a no-op here (glyph refresh is covered by the accepted-glyph suite).
    """
    _require_qt_widget_or_skip()
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")

    card_cls = getattr(LiverSegmentation, "_StructureCard", None)
    if card_cls is None:
        pytest.fail(
            "LiverSegmentation must expose the per-structure card controller "
            "(_StructureCard) that owns onRun -- ADR-0024 "
            "§'Per-structure micro-workflows'."
        )

    class _StandInWidget:
        def __init__(self, logic):
            self.logic = logic

        def _refreshTabGlyphs(self):
            pass

    widget = _StandInWidget(orch)
    card = card_cls(widget, "Liver", sctCode)
    return card


def test_card_run_without_portalvenous_volume_does_not_segment(monkeypatch):
    """Run with no PortalVenous volume mints no scratch node + surfaces feedback.

    ADR-0024 §"Per-structure micro-workflows": Stage 2 works on the Stage-1
    PortalVenous volume.  With none tagged, ``selectInputVolume()`` is None;
    onRun must NOT hand a None volume to ``segment()`` (no scratch node), and
    must surface actionable feedback on ``statusLabel`` while leaving
    Accept/Reject disabled and the progress bar hidden.

    RED-as-skip until the guard lands: today's onRun calls ``segment(None,...)``
    -> ``_runTotalSegmentator(None,...)`` -> a scratch node, and sets the
    "Review the result" text with Accept/Reject enabled.

    The backend seam is monkeypatched so, even under the current (unfixed)
    behaviour, no real inference runs and the leak-checking teardown stays
    honest.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "segment"):
        pytest.fail(
            "orchestrator must expose segment(volume, sctTarget) per ADR-0024 "
            "-- not yet implemented."
        )
    _mock_backend_segment(monkeypatch, slicer, orch)

    card = _make_card_or_skip(slicer, orch, SCT_LIVER_CODE)

    # No PortalVenous volume in the scene: selectInputVolume() -> None.
    assert orch.selectInputVolume() is None, (
        "precondition: no PortalVenous-role volume exists for this test."
    )

    card.onRun()

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 0, (
        "onRun with no PortalVenous volume must NOT call segment() -- no "
        "scratch node may be minted from a None input (ADR-0024 Stage-1/"
        "Stage-2 hand-off precondition)."
    )
    status = card.statusLabel.text
    assert status and status != "Idle" and "Review the result" not in status, (
        "onRun must surface actionable feedback on statusLabel (e.g. 'Tag a "
        "PortalVenous volume in Case Setup first.'), not the post-run "
        f"'Review the result' text; got {status!r}."
    )
    assert card.acceptButton.enabled is False, (
        "Accept must stay disabled when Run did not produce a result."
    )
    assert card.rejectButton.enabled is False, (
        "Reject must stay disabled when Run did not produce a result."
    )
    assert card.progressBar.visible is False, (
        "the progress bar must not be left visible when Run short-circuits."
    )


def test_card_run_with_portalvenous_volume_still_segments(monkeypatch):
    """Run WITH a PortalVenous volume still drives the backend + mints scratch.

    Counterpart to the guard: the short-circuit must be scoped to the
    missing-input case only.  With a Stage-1 PortalVenous volume present,
    onRun proceeds — one scratch node, Accept/Reject enabled.

    ADR-0024 §"Per-structure micro-workflows".
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "segment"):
        pytest.fail(
            "orchestrator must expose segment(volume, sctTarget) per ADR-0024 "
            "-- not yet implemented."
        )

    _add_input_volume(slicer)  # LiverRole='PortalVenous'
    _mock_backend_segment(monkeypatch, slicer, orch)

    card = _make_card_or_skip(slicer, orch, SCT_LIVER_CODE)
    card.onRun()

    assert len(_segmentation_nodes(slicer, ROLE_SCRATCH)) == 1, (
        "onRun with a PortalVenous volume must proceed and mint exactly one "
        "scratch node (ADR-0024 §'Per-structure micro-workflows')."
    )
    assert card.acceptButton.enabled is True, (
        "Accept must be enabled after a successful Run."
    )
    assert card.rejectButton.enabled is True, (
        "Reject must be enabled after a successful Run."
    )


def test_card_run_paints_busy_state_before_the_blocking_backend_call(monkeypatch):
    """The busy signal must be VISIBLE before segment() starts blocking.

    Pressing Run gave no processing signal: the busy bar + status were set
    but Qt never repainted before the minutes-long blocking backend call
    (the first repaint came only with the first backend output line, itself
    delayed by the subprocess's slow startup).  onRun must set the busy
    state AND flush the event loop BEFORE entering segment(); this pin
    reads the card's state from INSIDE the (mocked) blocking call.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)
    _add_input_volume(slicer)

    card = _make_card_or_skip(slicer, orch, SCT_LIVER_CODE)

    seen = {}

    import qt

    def _blocking_segment(volume, sctTarget, progressCallback=None):
        seen["busy_visible"] = bool(card.progressBar.visible)
        seen["status"] = str(card.statusLabel.text)
        seen["wait_cursor"] = qt.QApplication.overrideCursor() is not None
        return None

    monkeypatch.setattr(orch, "segment", _blocking_segment)
    card.onRun()

    assert seen.get("busy_visible"), (
        "the busy/progress bar must already be visible when the blocking "
        "backend call starts -- 'no signaling that there is processing'."
    )
    assert seen.get("status"), "a starting status message must already be shown"
    assert "idle" not in seen["status"].lower(), (
        f"the status must signal processing, not {seen['status']!r}."
    )
    assert seen.get("wait_cursor"), (
        "the wait cursor must be active during the blocking backend call "
        "(the v1 setOverrideCursor(WaitCursor) idiom)."
    )
    assert qt.QApplication.overrideCursor() is None, (
        "the wait cursor must be RESTORED after onRun returns -- a stuck "
        "spinner outlives the inference otherwise."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_card_binds_an_injected_view():
    """The card is a CONTROLLER: given a view namespace, it binds -- not builds.

    The .ui-authored card (ADR-0029 designer-editable panels) supplies the
    six widgets as a ``childWidgetVariables`` namespace; the controller must
    adopt them (same public attribute names as the programmatic fallback),
    stamp the per-structure Run text, apply the initial enabled/hidden
    state, and wire the signals -- without constructing replacement widgets.
    """
    from conftest import _import_slicer_or_skip

    _import_slicer_or_skip()
    _require_qt_widget_or_skip()
    import qt

    try:
        import LiverSegmentation as module
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation module not importable ({exc}).")

    class _View:
        pass

    view = _View()
    view.RunButton = qt.QPushButton("placeholder")
    view.StatusLabel = qt.QLabel("placeholder")
    view.ProgressBar = qt.QProgressBar()
    view.AcceptButton = qt.QPushButton("Accept")
    view.RejectButton = qt.QPushButton("Reject")
    view.EditButton = qt.QPushButton("Edit in Segment Editor")

    class _StandInWidget:
        logic = None

    card = module._StructureCard(_StandInWidget(), "Liver", "10200004", view=view)
    assert card.runButton is view.RunButton, "the controller must BIND the view"
    assert card.statusLabel is view.StatusLabel
    assert card.progressBar is view.ProgressBar
    assert card.runButton.text == "Run TotalSegmentator (Liver)", (
        "the controller stamps the per-structure Run text on the bound view"
    )
    assert card.statusLabel.text == "Idle"
    assert card.acceptButton.enabled is False
    assert card.rejectButton.enabled is False
    assert card.progressBar.visible is False
