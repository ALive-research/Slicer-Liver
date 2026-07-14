# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0034 §Decision 6 — the validate-and-next SEAM (explain API + row marking).

This increment ships everything the shell's "Validate and next" button
(which itself stays with the phase-contracts work, #440) will need, plus a
Stage-2-local "Validate anatomy" affordance:

  * ``LiverSegmentationLogic.explainStageIncomplete()`` returns the list of
    ``(sctCode, title, statusText)`` for every expected structure NOT
    satisfying the completion predicate (native ``Completed`` — incl. the
    empty-``Completed`` absence attestation).  An empty list == stage
    complete.  The predicate and the explanation are the SAME derivation
    (both route through ``structureStatus``), pinned equivalent here:
    ``isStageComplete()`` iff ``explainStageIncomplete() == []``.
  * ``LiverSegmentationWidget.markUnresolvedRows()`` /
    ``clearUnresolvedMarks()`` mark/unmark the offending rows.  Mechanism:
    the stock ``qMRMLSegmentsTableView`` offers no Python-writable
    background/decoration role that survives the model's per-update item
    regeneration (and the name/colour data must not be abused, per the
    brief), so marking is realised as SELECTING the offending rows
    (``setSelectedSegmentIDs``) plus a glyph+text summary line on the shared
    status label ("Unresolved: Portal vein (Missing), Tumors (Review)"),
    never colour alone (ADR-0010).
  * The marks CLEAR LIVE: resolving a row (native status flip to
    ``Completed``, or a landing) re-evaluates and unmarks, riding the
    existing canonical-segmentation observation / ``_onSceneChanged``.

Needs the launched-Slicer harness (module + Qt + MRML); skips cleanly under
bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _module_or_skip():
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    return LiverSegmentation


def _widget_or_skip(slicer, registry):
    from conftest import _require_qt_widget

    _require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 surgeon-UI "
            "deliverable absent."
        )
    module = _module_or_skip()
    widget = module.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _segments_logic(slicer):
    """The native per-segment status surface (enum + static accessors)."""
    return slicer.vtkSlicerSegmentationsModuleLogic


def _sct_segment_id(module, canonical, code):
    """The (first) segment id on ``canonical`` whose terminology tag has ``code``."""
    import vtk

    segmentation = canonical.GetSegmentation()
    for segment_id in list(segmentation.GetSegmentIDs()):
        text = vtk.mutable("")
        segmentation.GetSegment(segment_id).GetTag(
            module.TERMINOLOGY_ENTRY_TAG, text
        )
        if f"^{code}^" in str(text):
            return segment_id
    return None


def _fill_segment(slicer, segment):
    """Give ``segment`` a tiny non-empty binary labelmap (a "landed" row)."""
    import vtk

    name = (
        slicer.vtkSegmentationConverter.GetSegmentationBinaryLabelmapRepresentationName()
    )
    image = slicer.vtkOrientedImageData()
    image.SetDimensions(2, 2, 2)
    image.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    image.GetPointData().GetScalars().Fill(segment.GetLabelValue())
    segment.AddRepresentation(name, image)


def _confirm(slicer, module, canonical, code):
    """Simulate the surgeon's status-cell confirm of a structure row.

    A data-carrying ``Completed`` row (a real segmentation the surgeon
    accepts); the empty-``Completed`` absence attestation is exercised
    separately.
    """
    segments_logic = _segments_logic(slicer)
    segment = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, code)
    )
    _fill_segment(slicer, segment)
    segments_logic.SetSegmentStatus(segment, segments_logic.Completed)
    return segment


# --------------------------------------------------------------------------- #
# Explain API (logic).
# --------------------------------------------------------------------------- #


def test_explain_lists_every_unsatisfied_structure_with_title_and_status():
    """``explainStageIncomplete`` names every structure NOT satisfying the
    completion predicate as ``(sctCode, title, statusText)`` (ADR-0034
    §Decision 6).  On a fresh pre-seeded checklist that is all four
    structures, each carrying its Missing status text."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()

    explanation = logic.explainStageIncomplete()
    # Every pre-seeded row is NotStarted -> Missing -> unresolved.
    expected = [
        (code, title, module.STATUS_MISSING[1])
        for title, code in module.STRUCTURE_TABS
    ]
    assert explanation == expected, (
        "explainStageIncomplete must list every unsatisfied structure as "
        "(sctCode, title, statusText), in vocabulary order; got "
        f"{explanation!r}."
    )

    # Resolve one (Portal vein -> Review): it stays unresolved, now carrying
    # its Review status text; the others are unchanged.
    segments_logic = _segments_logic(slicer)
    pv = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    )
    segments_logic.SetSegmentStatus(pv, segments_logic.InProgress)
    explanation = logic.explainStageIncomplete()
    pv_entry = next(
        e for e in explanation if e[0] == module.SCT_PORTAL_VEIN_CODE
    )
    assert pv_entry == (
        module.SCT_PORTAL_VEIN_CODE,
        "Portal vein",
        module.STATUS_REVIEW[1],
    ), "an InProgress row must be explained as unresolved with 'Review' text."


def test_explain_empty_on_all_completed_incl_marked_absent_empty():
    """``explainStageIncomplete`` is empty when every structure is satisfied,
    counting the empty-``Completed`` absence attestation (ADR-0034
    §Amendments) exactly like a data-carrying confirm."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()
    segments_logic = _segments_logic(slicer)

    for title, code in module.STRUCTURE_TABS:
        if code == module.SCT_MASS_CODE:
            # The multifocal Tumors row: an EMPTY Completed segment is the
            # explicit absence attestation ("no tumor in this case").
            segment = canonical.GetSegmentation().GetSegment(
                _sct_segment_id(module, canonical, code)
            )
            segments_logic.SetSegmentStatus(segment, segments_logic.Completed)
        else:
            _confirm(slicer, module, canonical, code)

    assert logic.explainStageIncomplete() == [], (
        "with every structure Completed (incl. the empty-Completed absence "
        "attestation) the explanation must be empty."
    )


def test_isstagecomplete_is_exactly_the_empty_explanation():
    """The predicate and the explanation are the SAME derivation: for every
    scene state, ``isStageComplete()`` iff ``explainStageIncomplete() == []``
    (ADR-0034 §Decision 6 — they must not drift)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()

    # No canonical: incomplete, and explained as every structure missing.
    assert logic.isStageComplete() is (logic.explainStageIncomplete() == [])

    canonical = logic.getOrCreateCanonicalSegmentation()

    # Confirm the structures one at a time; the equivalence holds at each step.
    for title, code in module.STRUCTURE_TABS:
        assert logic.isStageComplete() is (
            logic.explainStageIncomplete() == []
        ), (
            "isStageComplete() must be exactly equivalent to an empty "
            f"explanation at every step (before confirming {title!r})."
        )
        _confirm(slicer, module, canonical, code)

    assert logic.isStageComplete() is True
    assert logic.explainStageIncomplete() == []
    assert logic.isStageComplete() is (logic.explainStageIncomplete() == [])


# --------------------------------------------------------------------------- #
# Row marking + the local "Validate anatomy" affordance (widget).
# --------------------------------------------------------------------------- #


def test_validate_on_incomplete_marks_offenders_and_summarises(qt_widgets):
    """The local Validate gesture on an incomplete stage marks the offending
    rows (SELECTED in the stock view) and puts a glyph+text summary line
    listing them on the shared status label (ADR-0034 §Decision 6; ADR-0010
    never colour alone)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()

    # Confirm two structures; leave Portal vein (Missing) and Tumors (Review)
    # unresolved.
    _confirm(slicer, module, canonical, module.SCT_LIVER_CODE)
    segments_logic = _segments_logic(slicer)
    tumors = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, module.SCT_MASS_CODE)
    )
    segments_logic.SetSegmentStatus(tumors, segments_logic.InProgress)

    widget.onValidateAnatomy()

    table = widget.segmentsTable()
    selected = set(table.selectedSegmentIDs())
    offenders = {
        _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE),
        _sct_segment_id(module, canonical, module.SCT_HEPATIC_VEIN_CODE),
        _sct_segment_id(module, canonical, module.SCT_MASS_CODE),
    }
    assert selected == offenders, (
        "Validate must SELECT exactly the unresolved rows (the marking "
        f"mechanism); got {selected!r} vs {offenders!r}."
    )
    summary = widget._statusLabel.text
    assert "Unresolved" in summary
    for token in (
        "Portal vein",
        module.STATUS_MISSING[1],
        "Hepatic vein",
        "Tumors",
        module.STATUS_REVIEW[1],
    ):
        assert token in summary, (
            f"the summary line must name every offender with its status "
            f"text (glyph+text, never colour alone); {token!r} missing from "
            f"{summary!r}."
        )


def test_resolving_one_row_clears_its_mark_live_without_re_validating(qt_widgets):
    """Resolving ONE structure (native status flip to ``Completed``) clears
    ITS mark live — no second Validate click — and resolving ALL clears every
    mark (ADR-0034 §Decision 6: marks clear live)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()
    segments_logic = _segments_logic(slicer)

    # Land Portal vein + Hepatic vein under review, leave the rest Missing.
    for code in (module.SCT_PORTAL_VEIN_CODE, module.SCT_HEPATIC_VEIN_CODE):
        seg = canonical.GetSegmentation().GetSegment(
            _sct_segment_id(module, canonical, code)
        )
        _fill_segment(slicer, seg)
        segments_logic.SetSegmentStatus(seg, segments_logic.InProgress)

    widget.onValidateAnatomy()
    table = widget.segmentsTable()
    assert len(table.selectedSegmentIDs()) == len(module.STRUCTURE_TABS), (
        "all four rows unresolved before any confirm."
    )

    # Confirm the portal vein via its status cell -- the content edit +
    # status flip funnels through the canonical-segmentation observer the
    # widget already rides; the portal-vein mark must drop WITHOUT a second
    # Validate click.
    pv = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    )
    segments_logic.SetSegmentStatus(pv, segments_logic.Completed)

    pv_id = _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    assert pv_id not in set(table.selectedSegmentIDs()), (
        "resolving the portal-vein row must clear ITS mark live, without "
        "re-clicking Validate (ADR-0034 §Decision 6)."
    )
    # Its still-unresolved siblings stay marked.
    hv_id = _sct_segment_id(module, canonical, module.SCT_HEPATIC_VEIN_CODE)
    assert hv_id in set(table.selectedSegmentIDs()), (
        "a still-unresolved sibling row must keep its mark."
    )

    # Resolve the rest -> every mark gone.
    for title, code in module.STRUCTURE_TABS:
        if code == module.SCT_PORTAL_VEIN_CODE:
            continue
        seg = canonical.GetSegmentation().GetSegment(
            _sct_segment_id(module, canonical, code)
        )
        _fill_segment(slicer, seg)
        segments_logic.SetSegmentStatus(seg, segments_logic.Completed)

    assert list(table.selectedSegmentIDs()) == [], (
        "resolving every structure must clear all marks live (ADR-0034 "
        "§Decision 6)."
    )


def test_validate_on_complete_reports_complete_with_no_marks(qt_widgets):
    """Validate on a complete stage clears marks and reports completeness on
    the status label — no rows selected (ADR-0034 §Decision 6)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()

    for _title, code in module.STRUCTURE_TABS:
        _confirm(slicer, module, canonical, code)

    widget.onValidateAnatomy()

    table = widget.segmentsTable()
    assert list(table.selectedSegmentIDs()) == [], (
        "a complete stage must leave no offending rows marked."
    )
    summary = widget._statusLabel.text
    assert "complete" in summary.lower(), (
        f"Validate on a complete stage must report completeness; got "
        f"{summary!r}."
    )
    assert str(len(module.STRUCTURE_TABS)) in summary, (
        "the complete message names the count of confirmed structures "
        f"(N={len(module.STRUCTURE_TABS)}); got {summary!r}."
    )


def test_marking_mechanism_selects_exactly_the_offenders(qt_widgets):
    """The marking mechanism's own shape pin: ``markUnresolvedRows()`` SELECTS
    exactly the offending segment ids and ``clearUnresolvedMarks()`` clears
    the selection (the committed fallback — no background-role abuse; the
    stock model exposes none that survives item regeneration)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()

    # Confirm liver only; the other three are the offenders.
    _confirm(slicer, module, canonical, module.SCT_LIVER_CODE)

    widget.markUnresolvedRows()
    table = widget.segmentsTable()
    offenders = {
        _sct_segment_id(module, canonical, code)
        for _title, code in module.STRUCTURE_TABS
        if code != module.SCT_LIVER_CODE
    }
    assert set(table.selectedSegmentIDs()) == offenders, (
        "markUnresolvedRows must set the view's selection to EXACTLY the "
        "offending rows (the committed marking mechanism)."
    )

    widget.clearUnresolvedMarks()
    assert list(table.selectedSegmentIDs()) == [], (
        "clearUnresolvedMarks must clear the selection."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
