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
  * ``LiverSegmentationWidget.markValidationRows()`` /
    ``clearUnresolvedMarks()`` tint/untint every anatomy row by its
    validation state.  Mechanism: the stock ``qMRMLSegmentsTableView``
    installs functional per-column item delegates (terminology on the name
    column, an item delegate on opacity) and paints the status/visibility
    icons through the default delegate's decoration role, so a whole-view
    delegate would clobber them; instead each column's delegate is
    SUBCLASSED to set ``option.backgroundBrush`` from a widget-held
    per-segment tint state (``_rowValidationTint``), leaving the status-cell
    click-to-cycle review gesture intact.  Green for validated (native
    ``Completed``, incl. the empty-``Completed`` absence attestation), red
    for not-validated (Missing / Review / Flagged), plus a glyph+text summary
    line on the shared status label — the tint REINFORCES the status column,
    never colour alone (ADR-0010).  Delegate paint is not unit-testable
    headless, so these tests pin the STATE the delegate consults
    (``_rowValidationTint``), not pixels.
  * The tints UPDATE LIVE: resolving a row (native status flip to
    ``Completed``, or a landing) re-evaluates and flips its tint red -> green,
    riding the existing canonical-segmentation observation / ``_onSceneChanged``.

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


def _tint(widget, module, canonical, code):
    """The tint state (`'validated'|'unresolved'|None`) of a structure's row."""
    return widget._rowValidationTint(_sct_segment_id(module, canonical, code))


def test_validate_on_incomplete_tints_rows_by_state_and_summarises(qt_widgets):
    """The local Validate gesture on an incomplete stage tints each row by its
    validation state — green validated, red not-validated — and puts a
    glyph+text summary line naming the unresolved structures on the shared
    status label (ADR-0034 §Decision 6; the tint reinforces, ADR-0010 never
    colour alone)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()

    # Confirm two structures; leave Portal vein (Missing) and Tumors (Review)
    # unresolved.
    _confirm(slicer, module, canonical, module.SCT_LIVER_CODE)
    _confirm(slicer, module, canonical, module.SCT_HEPATIC_VEIN_CODE)
    segments_logic = _segments_logic(slicer)
    tumors = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, module.SCT_MASS_CODE)
    )
    segments_logic.SetSegmentStatus(tumors, segments_logic.InProgress)

    widget.onValidateAnatomy()

    # Validated rows read 'validated'; unresolved rows read 'unresolved'.
    assert _tint(widget, module, canonical, module.SCT_LIVER_CODE) == "validated"
    assert (
        _tint(widget, module, canonical, module.SCT_HEPATIC_VEIN_CODE)
        == "validated"
    )
    assert (
        _tint(widget, module, canonical, module.SCT_PORTAL_VEIN_CODE)
        == "unresolved"
    ), "a Missing row must tint 'unresolved'."
    assert _tint(widget, module, canonical, module.SCT_MASS_CODE) == "unresolved", (
        "a Review (InProgress) row must tint 'unresolved'."
    )

    summary = widget._statusLabel.text
    assert "Unresolved" in summary
    for token in ("Portal vein", module.STATUS_MISSING[1], "Tumors", module.STATUS_REVIEW[1]):
        assert token in summary, (
            f"the summary line must name every offender with its status "
            f"text (glyph+text, the primary carrier); {token!r} missing from "
            f"{summary!r}."
        )


def test_resolving_one_row_flips_its_tint_live_without_re_validating(qt_widgets):
    """Resolving ONE structure (native status flip to ``Completed``) flips ITS
    tint 'unresolved' -> 'validated' live — no second Validate click — and
    resolving ALL leaves every row 'validated' (ADR-0034 §Decision 6: tints
    update live)."""
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
    # Every one of the four rows is unresolved before any confirm.
    for _title, code in module.STRUCTURE_TABS:
        assert _tint(widget, module, canonical, code) == "unresolved"

    # Confirm the portal vein via its status cell -- the content edit +
    # status flip funnels through the canonical-segmentation observer the
    # widget already rides; the portal-vein tint must flip to green WITHOUT a
    # second Validate click.
    pv = canonical.GetSegmentation().GetSegment(
        _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    )
    segments_logic.SetSegmentStatus(pv, segments_logic.Completed)

    assert (
        _tint(widget, module, canonical, module.SCT_PORTAL_VEIN_CODE)
        == "validated"
    ), (
        "resolving the portal-vein row must flip ITS tint to 'validated' "
        "live, without re-clicking Validate (ADR-0034 §Decision 6)."
    )
    # Its still-unresolved sibling stays red.
    assert (
        _tint(widget, module, canonical, module.SCT_HEPATIC_VEIN_CODE)
        == "unresolved"
    ), "a still-unresolved sibling row must keep its 'unresolved' tint."

    # Resolve the rest -> every row 'validated'.
    for title, code in module.STRUCTURE_TABS:
        if code == module.SCT_PORTAL_VEIN_CODE:
            continue
        seg = canonical.GetSegmentation().GetSegment(
            _sct_segment_id(module, canonical, code)
        )
        _fill_segment(slicer, seg)
        segments_logic.SetSegmentStatus(seg, segments_logic.Completed)

    for _title, code in module.STRUCTURE_TABS:
        assert _tint(widget, module, canonical, code) == "validated", (
            "resolving every structure must leave all rows 'validated' live "
            "(ADR-0034 §Decision 6)."
        )


def test_validate_on_complete_tints_all_green_and_reports_complete(qt_widgets):
    """Validate on a complete stage tints every row 'validated' and reports
    completeness on the status label (ADR-0034 §Decision 6)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()

    for _title, code in module.STRUCTURE_TABS:
        _confirm(slicer, module, canonical, code)

    widget.onValidateAnatomy()

    for _title, code in module.STRUCTURE_TABS:
        assert _tint(widget, module, canonical, code) == "validated", (
            "a complete stage must tint every row 'validated' (green)."
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


def test_tint_state_neutral_outside_active_validation(qt_widgets):
    """The tint state the delegate consults is None for every row while no
    validation is active, and ``clearUnresolvedMarks`` returns all rows to
    None (ADR-0034 §Decision 6: a normal edit never tints a row)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = widget.logic.getOrCreateCanonicalSegmentation()
    _confirm(slicer, module, canonical, module.SCT_LIVER_CODE)

    # Before any Validate: every row neutral (None).
    for _title, code in module.STRUCTURE_TABS:
        assert _tint(widget, module, canonical, code) is None, (
            "no row may be tinted before Validate is invoked."
        )

    widget.markValidationRows()
    assert _tint(widget, module, canonical, module.SCT_LIVER_CODE) == "validated"
    assert (
        _tint(widget, module, canonical, module.SCT_PORTAL_VEIN_CODE)
        == "unresolved"
    )

    widget.clearUnresolvedMarks()
    for _title, code in module.STRUCTURE_TABS:
        assert _tint(widget, module, canonical, code) is None, (
            "clearUnresolvedMarks must return every row to neutral (None)."
        )


def test_tint_delegate_installed_on_name_column_status_column_delegate_intact(
    qt_widgets,
):
    """The tint delegate is installed on the name column (and the other tinted
    columns) while the status column keeps a functional item delegate — the
    tint SUBCLASSES each column's delegate rather than clobbering it, so the
    status-cell click-to-cycle review gesture survives (ADR-0034 §Decision 6)."""
    slicer = _slicer_or_skip()
    _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    inner = widget.segmentsTable().tableWidget()

    # Stock column layout: name = 3, status = 5.  The tint delegate on the name
    # column must still be a terminology delegate (subclassed, not replaced) so
    # name/terminology editing survives.
    from qSlicerTerminologiesModuleWidgetsPythonQt import (
        qSlicerTerminologyItemDelegate,
    )

    name_delegate = inner.itemDelegateForColumn(3)
    assert isinstance(name_delegate, qSlicerTerminologyItemDelegate), (
        "the name-column tint delegate must SUBCLASS the terminology delegate "
        "so terminology editing is preserved."
    )
    assert name_delegate in widget._tintDelegates, (
        "the name column must carry one of the widget's tint delegates."
    )

    # The tint delegate must be scoped per column, not installed whole-view
    # (a whole-view setItemDelegate would clobber the icon columns).
    assert inner.itemDelegate() not in widget._tintDelegates, (
        "the tint must be column-scoped, never a whole-view delegate."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
