# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0034 §Amendments — the anatomy segments table on Slicer-native primitives.

The table and the review contract move onto stock Slicer segmentation
primitives: the panel is a configured ``qMRMLSegmentsTableView`` over the
canonical node; the pre-seeded checklist is REAL empty segments (rows ARE
segments, no parallel bookkeeping); the review contract is the NATIVE
per-segment status (``Segmentation.Status`` tag, ``NotStarted`` /
``InProgress`` / ``Completed`` / ``Flagged``).

Pins (ADR-0034 §Amendments + §Conformance read through them):

  * ``getOrCreateCanonicalSegmentation`` pre-seeds one terminology-tagged
    EMPTY segment per structure-vocabulary entry, in vocabulary order, all
    reading native ``NotStarted``; idempotent on the second call.
  * ``segmentsTable()`` returns the configured stock view (status column
    on), bound to the canonical node.
  * ``setup()`` mints exactly ONE canonical (idempotent across widget
    rebuilds) with the pre-seeded checklist and binds the table to it —
    the "no node is selected" empty state never shows; the refresh path
    (``_bindSegmentsTable`` on scene change) stays a pure read that never
    mints.
  * ``accept()`` lands a scratch segment INTO its pre-seeded row (the
    placeholder is replaced, not duplicated; order preserved) as native
    ``InProgress`` with the per-segment source tag.
  * ``structureStatus`` maps the native vocabulary, incl. ``Flagged`` and
    the marked-absent attestation.
  * the toolbar's Mark absent writes the attestation shape on the selected
    empty row: the canonical marked-absent attribute + native ``Completed``
    on the empty segment, read back as ``Marked absent``.

Needs the launched-Slicer harness (module + Qt + MRML); skips cleanly
under bare pytest via the shared guards.
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


def _sct_segment_ids(module, canonical, code):
    """All segment ids on ``canonical`` whose terminology tag carries ``code``."""
    import vtk

    segmentation = canonical.GetSegmentation()
    ids = []
    for segment_id in list(segmentation.GetSegmentIDs()):
        text = vtk.mutable("")
        segmentation.GetSegment(segment_id).GetTag(
            module.TERMINOLOGY_ENTRY_TAG, text
        )
        if f"^{code}^" in str(text):
            ids.append(segment_id)
    return ids


def test_getorcreate_pre_seeds_expected_structures_idempotently():
    """One terminology-tagged EMPTY segment per vocabulary entry, in order,
    all native ``NotStarted``; a second call adds nothing (ADR-0034
    §Amendments: rows ARE segments; the empty state teaches the goal)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()
    segmentation = canonical.GetSegmentation()

    assert segmentation.GetNumberOfSegments() == len(module.STRUCTURE_TABS), (
        "getOrCreateCanonicalSegmentation must pre-seed exactly one empty "
        "segment per structure-vocabulary entry (ADR-0034 §Amendments)."
    )
    segments_logic = _segments_logic(slicer)
    for index, (title, code) in enumerate(module.STRUCTURE_TABS):
        segment_id = segmentation.GetNthSegmentID(index)
        segment = segmentation.GetSegment(segment_id)
        assert segment.GetName() == title, (
            f"pre-seeded row {index} must carry the vocabulary title "
            f"{title!r} in vocabulary order; got {segment.GetName()!r}."
        )
        ids = _sct_segment_ids(module, canonical, code)
        assert ids == [segment_id], (
            f"row {title!r} must be THE segment terminology-tagged "
            f"^{code}^ (the format the whole repo greps, ADR-0011)."
        )
        assert (
            segments_logic.GetSegmentStatus(segment)
            == segments_logic.NotStarted
        ), (
            f"pre-seeded row {title!r} must read native NotStarted -- the "
            "checklist placeholder is expected, not produced."
        )
        expected_color = module.STRUCTURE_VISUAL_DEFAULTS[code]["color"]
        assert tuple(segment.GetColor()) == pytest.approx(
            expected_color, abs=1e-3
        ), f"row {title!r} must carry the structure visual-default colour."

    second = logic.getOrCreateCanonicalSegmentation()
    assert second.GetID() == canonical.GetID()
    assert segmentation.GetNumberOfSegments() == len(module.STRUCTURE_TABS), (
        "pre-seeding must be idempotent -- a second getOrCreate call adds "
        "no duplicate rows."
    )


def test_segments_table_is_a_configured_stock_view_bound_to_canonical(qt_widgets):
    """``segmentsTable()`` is a ``qMRMLSegmentsTableView`` with the status
    column visible, bound to the canonical node (ADR-0034 §Amendments:
    Alternative B un-rejected; the native status cell is the review
    gesture)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()

    widget = _widget_or_skip(slicer, qt_widgets)
    table = widget.segmentsTable()
    assert table is not None, (
        "the Stage-2 panel must host the anatomy segments table "
        "(ADR-0034 §Decision 1, as amended)."
    )
    assert table.className() == "qMRMLSegmentsTableView", (
        "the table must be the STOCK qMRMLSegmentsTableView -- the custom "
        "QTableWidget is retired (ADR-0034 §Amendments)."
    )
    assert table.statusColumnVisible, (
        "the status column must be visible -- the native status-cell click "
        "is the surgeon's confirm gesture."
    )
    assert not table.layerColumnVisible
    node = table.segmentationNode()
    assert node is not None and node.GetID() == canonical.GetID(), (
        "the view must be bound to the canonical segmentation node."
    )


def _canonicals(slicer, module):
    return [
        node
        for node in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
        if node.GetAttribute(module.ROLE_ATTRIBUTE) == module.ROLE_CANONICAL
    ]


def test_setup_binds_the_table_immediately_on_a_fresh_scene(qt_widgets):
    """Right after ``setup()`` on a fresh scene the table is bound and the
    four-row checklist is on screen -- the stock view's "no node is
    selected" empty state never shows (ADR-0034 §Decision 1: the empty
    state teaches the goal)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    table = widget.segmentsTable()
    bound = table.segmentationNode()
    assert bound is not None, (
        "setup() must mint-or-adopt the canonical node and bind the table "
        "to it immediately -- the 'no node is selected' state is retired."
    )
    assert bound.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    ), "the pre-seeded checklist must be visible the moment Stage 2 opens."


def test_setup_mints_exactly_one_canonical_idempotently(qt_widgets):
    """``setup()`` mints exactly ONE canonical with the pre-seeded checklist,
    idempotent across widget rebuilds; the scene-change refresh path stays
    a pure read that never mints (ADR-0034 §Amendments; ADR-0024 §'Output
    contract' single-canonical)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    first = _widget_or_skip(slicer, qt_widgets)
    canonicals = _canonicals(slicer, module)
    assert len(canonicals) == 1, (
        "setup() on a fresh scene must mint exactly one canonical node."
    )
    canonical = canonicals[0]

    # A widget REBUILD adopts the existing canonical, never a second one.
    second = _widget_or_skip(slicer, qt_widgets)
    assert len(_canonicals(slicer, module)) == 1, (
        "a widget rebuild must adopt the existing canonical, not mint a "
        "second one (get-or-create idempotence)."
    )
    assert second.segmentsTable().segmentationNode().GetID() == canonical.GetID()
    assert canonical.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    ), "re-running setup() must not duplicate the pre-seeded checklist rows."

    # The refresh path is a pure READ: with the canonical gone, a scene-
    # change refresh unbinds and must NOT mint a replacement.
    slicer.mrmlScene.RemoveNode(canonical)
    first._onSceneChanged()
    assert first.segmentsTable().segmentationNode() is None, (
        "with no canonical in the scene the refresh must leave the view "
        "unbound."
    )
    assert _canonicals(slicer, module) == [], (
        "_bindSegmentsTable is a pure read -- a scene-change refresh must "
        "never mint the canonical (getOrCreate is setup()'s explicit write "
        "gesture)."
    )

    # A canonical landing in the scene re-binds via the scene observer.
    replacement = first.logic.getOrCreateCanonicalSegmentation()
    first._onSceneChanged()
    bound = first.segmentsTable().segmentationNode()
    assert bound is not None and bound.GetID() == replacement.GetID(), (
        "the view must re-bind to a canonical node arriving after setup."
    )


def test_accept_lands_scratch_liver_into_the_preseeded_row():
    """``accept()`` replaces the liver placeholder in place: same SCT set,
    no duplicate liver rows, order preserved, native ``InProgress`` +
    source tag (ADR-0034 §Amendments landing contract)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()

    scratch = logic.createScratchSegmentation()
    seg_id = scratch.GetSegmentation().AddEmptySegment("liver", "Liver")
    logic.tagSegmentWithSct(scratch, seg_id, module.SCT_LIVER_CODE, "Liver")

    logic.accept(scratch)

    segmentation = canonical.GetSegmentation()
    assert segmentation.GetNumberOfSegments() == len(module.STRUCTURE_TABS), (
        "landing into a pre-seeded row must keep the segment count stable "
        "-- the placeholder is REPLACED, not duplicated."
    )
    liver_ids = _sct_segment_ids(module, canonical, module.SCT_LIVER_CODE)
    assert len(liver_ids) == 1, (
        "exactly one liver-tagged segment after the landing -- no duplicate "
        "liver rows (ADR-0034 §Amendments landing contract)."
    )
    assert segmentation.GetSegmentIndex(liver_ids[0]) == 0, (
        "the landed liver must occupy the placeholder's row position "
        "(checklist order is stable; the vtkSegmentation reorder API)."
    )
    segments_logic = _segments_logic(slicer)
    landed = segmentation.GetSegment(liver_ids[0])
    assert (
        segments_logic.GetSegmentStatus(landed) == segments_logic.InProgress
    ), (
        "a landed segment must read native InProgress -- 'produced, under "
        "review' (ADR-0034 §Amendments Decision 2)."
    )
    import vtk

    source = vtk.mutable("")
    landed.GetTag(module.SOURCE_TAG, source)
    assert str(source) == module.SOURCE_TOTALSEG, (
        "the accept path must stamp the per-segment source tag "
        f"({module.SOURCE_TOTALSEG!r}); got {str(source)!r}."
    )
    # The untouched rows stay pre-seeded NotStarted.
    for _title, code in module.STRUCTURE_TABS[1:]:
        other = canonical.GetSegmentation().GetSegment(
            _sct_segment_ids(module, canonical, code)[0]
        )
        assert (
            segments_logic.GetSegmentStatus(other) == segments_logic.NotStarted
        ), "rows the accept did not touch must stay NotStarted placeholders."


def test_structure_status_maps_the_native_vocabulary():
    """``structureStatus`` derives the module vocabulary from the native
    status, incl. ``Flagged`` and the marked-absent attestation (ADR-0034
    §Amendments)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    # No canonical node at all -> Missing.
    assert module.structureStatus(None, module.SCT_LIVER_CODE) == (
        module.STATUS_MISSING
    )

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()
    segments_logic = _segments_logic(slicer)

    # A pre-seeded NotStarted placeholder still reads Missing.
    assert (
        module.structureStatus(canonical, module.SCT_LIVER_CODE)
        == module.STATUS_MISSING
    )

    liver = canonical.GetSegmentation().GetSegment(
        _sct_segment_ids(module, canonical, module.SCT_LIVER_CODE)[0]
    )
    segments_logic.SetSegmentStatus(liver, segments_logic.InProgress)
    assert (
        module.structureStatus(canonical, module.SCT_LIVER_CODE)
        == module.STATUS_REVIEW
    ), "native InProgress -> '● Review' (produced, under review)."

    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)
    assert (
        module.structureStatus(canonical, module.SCT_LIVER_CODE)
        == module.STATUS_CONFIRMED
    ), "native Completed -> '✓ Confirmed' (the status-cell confirm)."

    segments_logic.SetSegmentStatus(liver, segments_logic.Flagged)
    assert (
        module.structureStatus(canonical, module.SCT_LIVER_CODE)
        == module.STATUS_FLAGGED
    ), "native Flagged -> '⚑ Flagged' (defer to a senior reviewer)."

    # The explicit clinical attestation: the attribute reads Marked absent
    # over the empty placeholder...
    canonical.SetAttribute(
        module.MARKED_ABSENT_ATTRIBUTE_PREFIX + module.SCT_MASS_CODE, "1"
    )
    assert (
        module.structureStatus(canonical, module.SCT_MASS_CODE)
        == module.STATUS_MARKED_ABSENT
    )
    # ...and over the empty Completed segment that attests it (the shape
    # the marked-absent writer produces; the attribute stays for audit).
    mass = canonical.GetSegmentation().GetSegment(
        _sct_segment_ids(module, canonical, module.SCT_MASS_CODE)[0]
    )
    segments_logic.SetSegmentStatus(mass, segments_logic.Completed)
    assert (
        module.structureStatus(canonical, module.SCT_MASS_CODE)
        == module.STATUS_MARKED_ABSENT
    )


def test_mark_absent_toolbar_writes_the_attestation_shape(qt_widgets):
    """Mark absent on a selected empty row writes attribute + ``Completed``.

    ADR-0034 §Amendments: the explicit absence attestation is an empty
    ``Completed`` segment plus the canonical marked-absent attribute (the
    audit trail) -- exactly the shape ``structureStatus`` and
    ``isStageComplete`` already understand.  The gesture applies only to a
    row still reading native ``NotStarted``; anything else gets a hint and
    no write."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    table = widget.segmentsTable()
    canonical = table.segmentationNode()
    segments_logic = _segments_logic(slicer)

    mass_id = _sct_segment_ids(module, canonical, module.SCT_MASS_CODE)[0]
    table.setSelectedSegmentIDs([mass_id])
    widget.onMarkAbsent()

    attribute = module.MARKED_ABSENT_ATTRIBUTE_PREFIX + module.SCT_MASS_CODE
    assert canonical.GetAttribute(attribute) == "1", (
        "Mark absent must write the canonical marked-absent attribute "
        "(the audit trail, ADR-0034 §Amendments)."
    )
    mass = canonical.GetSegmentation().GetSegment(mass_id)
    assert segments_logic.GetSegmentStatus(mass) == segments_logic.Completed, (
        "Mark absent must set native Completed on the empty segment -- the "
        "explicit attestation the completion predicate counts."
    )
    assert (
        module.structureStatus(canonical, module.SCT_MASS_CODE)
        == module.STATUS_MARKED_ABSENT
    ), "the attested row must read back as Marked absent."

    # A row past NotStarted refuses the gesture: hint, no write.
    liver_id = _sct_segment_ids(module, canonical, module.SCT_LIVER_CODE)[0]
    liver = canonical.GetSegmentation().GetSegment(liver_id)
    segments_logic.SetSegmentStatus(liver, segments_logic.InProgress)
    table.setSelectedSegmentIDs([liver_id])
    widget.onMarkAbsent()

    liver_attribute = module.MARKED_ABSENT_ATTRIBUTE_PREFIX + module.SCT_LIVER_CODE
    assert canonical.GetAttribute(liver_attribute) is None, (
        "Mark absent on a row past NotStarted must not write the attribute."
    )
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress, (
        "Mark absent on a row past NotStarted must not touch its status."
    )
    status = widget._statusLabel.text
    assert status and status != "Idle", (
        "the refused gesture must surface a hint on the shared status label."
    )

    # No selection: a no-op with a hint.
    table.setSelectedSegmentIDs([])
    widget.onMarkAbsent()
    assert canonical.GetSegmentation().GetNumberOfSegments() == len(
        module.STRUCTURE_TABS
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
