# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The Stage-2 explicit-correspondence import path (ADR-0034 §Amendments).

Importing a loaded segmentation is an EXPLICIT act of correspondence: the
Import… dialog carries a mapping table under the source picker — one row
per source segment, an "Import as" combo per row whose default is
"— skip —".  There is NO auto-match: neither the source segment's name nor
a ``TerminologyEntry`` tag it happens to carry routes anything; the surgeon
states every correspondence, and only mapped segments land.  The seam:

    LiverSegmentationLogic.importSegmentation(sourceNode, correspondences)
        -> canonicalNode | None

where ``correspondences`` maps source segment id -> structure-vocabulary
SCT code (skipped segments absent).  Every mapped segment flows through the
SAME landing kernel the AI accept path uses (``_landSegment``), arriving
native ``InProgress`` with the ``imported`` source tag and taking the
EXPECTED structure's identity — the vocabulary title as its name, the
structure visual defaults, the SCT tag.  Several rows may map to ONE
structure (the multifocal shape): the first takes the vocabulary title,
later ones "<Title> 2", "<Title> 3"…

A row that already landed — in particular a surgeon-``Completed`` one — is
NEVER overwritten or demoted by an import: the incoming segment lands as an
extra same-code row and the surgeon decides which to keep (the dialog
annotates such structures "(already present)", still selectable).  The
source node is consumed (removed) only when EVERY segment was mapped; any
skipped row keeps the source untouched in the scene, and an all-skip
mapping is a graceful no-op.

Scene-needing: launched-Slicer harness (``pytest_launched``); skips cleanly
under bare ``PythonSlicer -m pytest``.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_CANONICAL = "canonical"

# SCT type codes per ADR-0024 §"Output contract" (the ADR-0011 vocabulary).
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"

# The explicit-correspondence logic seam.
IMPORT_SEAM = "importSegmentation"

#: The serialization shape the STOCK terminology navigator writes
#: (``vtkSlicerTerminologiesModuleLogic::SerializeTerminologyEntry``): the
#: context/category/type/modifier/anatomic tilde chain.  The repo's readers
#: grep ``^<code>^`` (ADR-0011), which must recognise this format too.
STOCK_NAVIGATOR_LIVER_ENTRY = (
    "Segmentation category and type - 3D Slicer General Anatomy list"
    "~SCT^123037004^Anatomical Structure"
    "~SCT^10200004^Liver"
    "~^^"
    "~Anatomic codes - DICOM master list"
    "~^^"
    "~^^"
)


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "deliverable absent; the correspondence import flow cannot be "
            "exercised."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation, LiverSegmentation.LiverSegmentationLogic()


def _require_seam(logic):
    """RED gate: the explicit-correspondence seam must exist for these pins."""
    assert hasattr(logic, IMPORT_SEAM), (
        f"LiverSegmentationLogic.{IMPORT_SEAM}() is missing -- the "
        "explicit-correspondence import path (ADR-0034 §Amendments) is not "
        "implemented."
    )


def _source_segmentation(slicer, names, nodeName="Loaded"):
    """A plain (un-roled) source segmentation with named empty segments.

    Stands in for a loaded-from-disk segmentation; built through
    ``AddEmptySegment`` like the sibling suites' fixtures.  Returns
    ``(node, {name: segmentId})``.
    """
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", nodeName)
    segmentation = node.GetSegmentation()
    ids = {name: segmentation.AddEmptySegment(name, name) for name in names}
    return node, ids


def _segment_tag(segment, tag):
    import vtk

    text = vtk.mutable("")
    segment.GetTag(tag, text)
    return str(text)


def _sct_segment_ids(module, canonical, code):
    """All segment ids on ``canonical`` whose terminology tag carries ``code``."""
    segmentation = canonical.GetSegmentation()
    return [
        segment_id
        for segment_id in list(segmentation.GetSegmentIDs())
        if f"^{code}^"
        in _segment_tag(segmentation.GetSegment(segment_id), module.TERMINOLOGY_ENTRY_TAG)
    ]


def _in_scene(slicer, node):
    return node.GetScene() is slicer.mrmlScene and slicer.mrmlScene.IsNodePresent(node)


def test_mapped_import_fills_checklist_rows_under_review():
    """C1 — the stated correspondences fill the pre-seeded checklist rows.

    Source names are deliberately OUTSIDE the vocabulary: the mapping — not
    any name — routes each segment.  Each landed structure flips
    ``isStructureAccepted`` True, the canonical row count is unchanged
    (placeholder replacement, no duplicate rows), and ``isStageComplete``
    stays False — imports arrive under review (native ``InProgress``),
    never as the surgeon's confirm.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()

    source, ids = _source_segmentation(slicer, ["seg_a", "seg_b", "seg_c"])
    returned = logic.importSegmentation(
        source,
        {
            ids["seg_a"]: SCT_LIVER_CODE,
            ids["seg_b"]: SCT_PORTAL_VEIN_CODE,
            ids["seg_c"]: SCT_HEPATIC_VEIN_CODE,
        },
    )

    assert returned is not None, (
        "importSegmentation must return the canonical node on success."
    )
    assert returned.GetAttribute(ROLE_ATTRIBUTE) == ROLE_CANONICAL
    assert returned.GetID() == canonical.GetID(), (
        "the canonical node's IDENTITY never changes on import -- the "
        "pre-seeded-canonical model replaces the retired node promotion."
    )
    for code in (SCT_LIVER_CODE, SCT_PORTAL_VEIN_CODE, SCT_HEPATIC_VEIN_CODE):
        assert logic.isStructureAccepted(code) is True, (
            f"isStructureAccepted({code}) must be True after the mapped "
            "import lands the structure (explicit correspondence)."
        )
    assert canonical.GetSegmentation().GetNumberOfSegments() == rows_before, (
        "mapped imports REPLACE their empty checklist placeholders -- no "
        "duplicate rows may accrue (ADR-0034 §Amendments landing contract)."
    )
    assert logic.isStageComplete() is False, (
        "imported segments land under review (native InProgress); Stage 2 "
        "completes only on the surgeon's per-row Completed confirm."
    )


def test_mapped_segment_takes_the_expected_structure_identity():
    """C2 — a mapped segment comes out AS the structure: name, colour, SCT."""
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    source, ids = _source_segmentation(slicer, ["whatever the tool called it"])
    logic.importSegmentation(
        source, {ids["whatever the tool called it"]: SCT_LIVER_CODE}
    )

    liver_ids = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)
    assert len(liver_ids) == 1, (
        "the mapped segment must land INTO the pre-seeded placeholder "
        f"(exactly one liver-tagged row); got {len(liver_ids)}."
    )
    segment = canonical.GetSegmentation().GetSegment(liver_ids[0])
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    assert (
        segments_logic.GetSegmentStatus(segment) == segments_logic.InProgress
    ), "the landed row must read native InProgress ('produced, under review')."
    assert _segment_tag(segment, module.SOURCE_TAG) == module.SOURCE_IMPORTED, (
        "the landed row must carry the 'imported' provenance source tag."
    )
    assert segment.GetName() == "Liver parenchyma", (
        "the landed row takes the EXPECTED structure's identity: the "
        "vocabulary title, not the source segment's name."
    )
    expected_color = module.STRUCTURE_VISUAL_DEFAULTS[SCT_LIVER_CODE]["color"]
    assert segment.GetColor() == pytest.approx(expected_color), (
        "the landed row takes the structure's default colour, not the "
        "source segment's."
    )


def test_skipped_segments_never_land_and_mapping_overrides_carried_tags():
    """C3 — skip means skip, and the stated mapping beats a carried SCT tag.

    A source segment carrying a portal-vein ``TerminologyEntry`` tag but
    absent from the correspondences lands NOTHING (tag-based auto-routing
    is retired); a tagged segment mapped to a DIFFERENT structure lands as
    the MAPPED structure — the surgeon's explicit mapping is the only
    resolution.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()
    source, ids = _source_segmentation(slicer, ["carries_tag", "seg_x"])
    logic.tagSegmentWithSct(
        source, ids["carries_tag"], SCT_PORTAL_VEIN_CODE, "Portal vein"
    )
    logic.tagSegmentWithSct(source, ids["seg_x"], SCT_PORTAL_VEIN_CODE, "Portal vein")

    returned = logic.importSegmentation(
        source, {ids["seg_x"]: SCT_HEPATIC_VEIN_CODE}
    )

    assert returned is not None
    assert logic.isStructureAccepted(SCT_HEPATIC_VEIN_CODE) is True, (
        "the mapped segment must land as the structure the surgeon STATED."
    )
    assert logic.isStructureAccepted(SCT_PORTAL_VEIN_CODE) is False, (
        "a carried TerminologyEntry tag must not route anything -- the "
        "skipped tagged segment lands nothing and the mapped one lands as "
        "its STATED structure (auto-match is retired)."
    )
    assert canonical.GetSegmentation().GetNumberOfSegments() == rows_before, (
        "only the mapped segment lands (placeholder replacement); the "
        "skipped one must not appear as any extra row."
    )
    assert _in_scene(slicer, source), (
        "a partially mapped import must keep the source node in the scene."
    )


def test_many_to_one_lands_numbered_same_code_rows():
    """C4 — several rows may map to ONE structure: the multifocal shape.

    All mapped segments land tagged with the same code; the first takes
    the vocabulary title, subsequent ones "<Title> 2", "<Title> 3"…
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()
    source, ids = _source_segmentation(slicer, ["lesion_a", "lesion_b", "lesion_c"])
    returned = logic.importSegmentation(
        source,
        {
            ids["lesion_a"]: SCT_MASS_CODE,
            ids["lesion_b"]: SCT_MASS_CODE,
            ids["lesion_c"]: SCT_MASS_CODE,
        },
    )

    assert returned is not None
    assert not _in_scene(slicer, source), (
        "every segment was mapped: the source must be consumed."
    )
    mass_ids = _sct_segment_ids(module, canonical, SCT_MASS_CODE)
    assert len(mass_ids) == 3, (
        f"three mapped segments must land three mass-tagged rows; got "
        f"{len(mass_ids)}."
    )
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    names = []
    for segment_id in mass_ids:
        segment = canonical.GetSegmentation().GetSegment(segment_id)
        names.append(segment.GetName())
        assert (
            segments_logic.GetSegmentStatus(segment) == segments_logic.InProgress
        )
        assert _segment_tag(segment, module.SOURCE_TAG) == module.SOURCE_IMPORTED
    assert sorted(names) == ["Tumors", "Tumors 2", "Tumors 3"], (
        "many->1 rows take numbered vocabulary titles (the multifocal "
        f"shape); got {names!r}."
    )
    assert (
        canonical.GetSegmentation().GetNumberOfSegments() == rows_before + 2
    ), "first mass row replaces the placeholder; the other two are extras."


def test_landed_confirmed_row_is_never_overwritten():
    """C5 — a landed (here: Completed) row survives a re-import untouched.

    Maintainer-agreed never-overwrite rule: when the expected row already
    landed, the incoming same-structure segment lands as an EXTRA row
    (numbered vocabulary title, same SCT tag, InProgress + imported) and
    the original keeps its content AND status — the surgeon decides which
    to keep.  In particular the AI path's demote-on-rerun staleness rule
    does NOT ride the import path.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    first, ids = _source_segmentation(slicer, ["liver"])
    logic.importSegmentation(first, {ids["liver"]: SCT_LIVER_CODE})
    landed_id = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)[0]
    landed = canonical.GetSegmentation().GetSegment(landed_id)
    segments_logic.SetSegmentStatus(landed, segments_logic.Completed)

    second, ids = _source_segmentation(slicer, ["liver"])
    logic.importSegmentation(second, {ids["liver"]: SCT_LIVER_CODE})

    liver_ids = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)
    assert len(liver_ids) == 2, (
        "re-importing an already-landed structure must add an EXTRA "
        f"same-code row, never replace; got {len(liver_ids)} liver row(s)."
    )
    original = canonical.GetSegmentation().GetSegment(landed_id)
    assert original is not None, "the original landed row must survive."
    assert (
        segments_logic.GetSegmentStatus(original) == segments_logic.Completed
    ), (
        "the surgeon's Completed confirm must NOT be demoted by an import "
        "(the demote-on-rerun rule is the AI re-run path's, not the "
        "import's)."
    )
    extra_ids = [sid for sid in liver_ids if sid != landed_id]
    extra = canonical.GetSegmentation().GetSegment(extra_ids[0])
    assert segments_logic.GetSegmentStatus(extra) == segments_logic.InProgress
    assert _segment_tag(extra, module.SOURCE_TAG) == module.SOURCE_IMPORTED
    assert extra.GetName() == "Liver parenchyma 2", (
        "the extra row also takes the structure identity, numbered past "
        "the already-landed same-code row (the multifocal title shape)."
    )


def test_full_mapping_consumes_source_partial_keeps_it():
    """C6 — consumption rule: the source goes ONLY when every segment mapped."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    logic.getOrCreateCanonicalSegmentation()

    # Full mapping: the copied segments live on in canonical; the source goes.
    source, ids = _source_segmentation(slicer, ["only"])
    assert logic.importSegmentation(source, {ids["only"]: SCT_LIVER_CODE}) is not None
    assert not _in_scene(slicer, source), (
        "a fully mapped import must consume (remove) the source node."
    )

    # Partial mapping: landing happens, but the source node stays.
    partial, ids = _source_segmentation(slicer, ["one", "two"])
    returned = logic.importSegmentation(partial, {ids["one"]: SCT_PORTAL_VEIN_CODE})
    assert returned is not None, "the mapped segment must still land."
    assert logic.isStructureAccepted(SCT_PORTAL_VEIN_CODE) is True
    assert _in_scene(slicer, partial), (
        "any skipped row must leave the source node untouched in the scene."
    )


def test_skip_all_and_degenerate_imports_are_noops():
    """C7 — all-skip / absent mapping / None source: graceful no-ops.

    The all-skip source carries a segment literally named ``liver``: with
    no stated correspondence NOTHING lands — no name is ever matched, no
    carried vocabulary bridges apply (auto-match is retired).
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()

    source, _ids = _source_segmentation(slicer, ["liver"])
    assert logic.importSegmentation(source, {}) is None, (
        "an all-skip mapping is a graceful no-op returning None."
    )
    assert logic.importSegmentation(source) is None, (
        "an ABSENT mapping lands nothing -- in particular the segment "
        "named 'liver' must NOT be auto-matched by name."
    )
    assert _in_scene(slicer, source), (
        "a no-op import must leave the source node in the scene."
    )
    assert canonical.GetSegmentation().GetNumberOfSegments() == rows_before, (
        "a no-op import must not touch the canonical rows."
    )
    assert logic.isStructureAccepted(SCT_LIVER_CODE) is False

    assert logic.importSegmentation(None, {"sid": SCT_LIVER_CODE}) is None
    empty_source = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "Empty"
    )
    assert logic.importSegmentation(empty_source, {"sid": SCT_LIVER_CODE}) is None
    assert _in_scene(slicer, empty_source), (
        "a degenerate import must leave the source node in the scene."
    )
    assert logic.isStageComplete() is False, (
        "no-op imports must not complete Stage 2 (ADR-0034 §Amendments "
        "completion predicate)."
    )


def test_canonical_and_scratch_roles_are_not_importable_sources():
    """C8 — the orchestrator's own nodes are never import sources."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    first_id = canonical.GetSegmentation().GetNthSegmentID(0)
    assert logic.importSegmentation(canonical, {first_id: SCT_LIVER_CODE}) is None, (
        "importing the canonical into itself must be refused."
    )
    scratch = logic.createScratchSegmentation()
    scratch_id = scratch.GetSegmentation().AddEmptySegment("pending", "pending")
    assert logic.importSegmentation(scratch, {scratch_id: SCT_LIVER_CODE}) is None, (
        "scratch-role nodes are the AI landing's internal carriers, not "
        "import sources (accept() is their path)."
    )
    assert _in_scene(slicer, scratch)


def test_stock_navigator_terminology_format_is_recognized():
    """C9 — the stock navigator's serialization satisfies the ^code^ greps.

    Structure re-assignment on a landed row is the STOCK terminology
    navigator (double-click the colour swatch); its ``TerminologyEntry``
    value is the ``SerializeTerminologyEntry`` tilde chain.  Pin that (a)
    the documented stock shape is recognised by the module's SCT readers,
    and (b) a round-trip of the module's own serialization through the
    stock terminologies logic stays recognised.  (The tag routes NOTHING
    on import any more — resolution is the surgeon's explicit mapping.)
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    source, ids = _source_segmentation(slicer, ["odd name"])
    segment = source.GetSegmentation().GetSegment(ids["odd name"])
    segment.SetTag(module.TERMINOLOGY_ENTRY_TAG, STOCK_NAVIGATOR_LIVER_ENTRY)

    assert module._findSctSegment(source, SCT_LIVER_CODE) is segment, (
        "the stock navigator serialization must satisfy the module's "
        "^<code>^ SCT readers (ADR-0011)."
    )

    # Round-trip through the STOCK terminologies logic, when available.
    terminologies = getattr(slicer.modules, "terminologies", None)
    if terminologies is None:
        pytest.skip("Terminologies module not loaded; round-trip pin skipped.")
    tlogic = terminologies.logic()
    entry = slicer.vtkSlicerTerminologyEntry()
    ours = module._sctTerminologyTag(SCT_LIVER_CODE, "Liver")
    assert tlogic.DeserializeTerminologyEntry(ours, entry), (
        "the module's own TerminologyEntry serialization must be readable "
        "by the stock terminologies logic (the navigator's parser)."
    )
    restocked = tlogic.SerializeTerminologyEntry(entry)
    assert f"^{SCT_LIVER_CODE}^" in restocked, (
        "the stock re-serialization must keep the ^<code>^ marker the "
        "repo's readers grep."
    )


#
# Widget surface: the toolbar Import… gesture and its correspondence dialog.
#


def _widget_or_skip(slicer, registry):
    from conftest import _require_qt_widget

    _require_qt_widget()
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    widget = LiverSegmentation.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _dispose_dialog(widget, dialog, combo):
    """Tear an unexec'd dialog down the parented way (the double-free rule).

    ``setParent(None)`` hands the wrapper's ownership to PythonQt and a
    subsequent ``deleteLater`` destroys the same object from the Qt side —
    the parentless-widget double-free.  The dialog stays PARENTED for its
    deferred deletion, mirroring the gesture's own teardown.
    """
    combo.setMRMLScene(None)
    widget._importDialogButtons = None
    widget._importMappingTable = None
    dialog.deleteLater()


def test_toolbar_hosts_import_button(qt_widgets):
    """W1 — the selection toolbar carries the Import… gesture."""
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    button = slicer.util.findChild(widget.parent, "ImportSegmentationButton")
    assert button is not None and button.className() == "QPushButton", (
        "the toolbar must host the Import… button (ADR-0034 §Decision 2: "
        "the import path unifies; the separate load section is retired)."
    )
    assert "Import" in button.text


def test_import_gesture_with_no_eligible_source_hints(qt_widgets):
    """W2 — no importable node: the shared status label explains, no dialog."""
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    # Only the canonical (and no plain segmentation) is in the scene.
    assert widget._eligibleImportSources() == []
    widget.onImportSegmentation()
    assert "segmentation" in widget._statusLabel.text.lower(), (
        "with nothing importable the gesture must hint on the shared "
        "status label (explainable state, ADR-0009)."
    )


def test_import_dialog_table_defaults_every_row_to_skip(qt_widgets):
    """W3 — one table row per source segment; every combo defaults to skip.

    The first source segment is literally named ``liver``: even a perfect
    vocabulary name must NOT prefill its combo — the explicit-
    correspondence contract admits no auto-match of any kind.
    """
    slicer, module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    source, _ids = _source_segmentation(slicer, ["liver", "mystery structure"])
    dialog, combo, table = widget._buildImportDialog()
    try:
        combo.setCurrentNode(source)
        assert table.rowCount == 2, (
            "the mapping table must carry one row per SOURCE segment."
        )
        assert table.item(0, 0).text() == "liver"
        assert table.item(1, 0).text() == "mystery structure"
        for row in range(table.rowCount):
            row_combo = table.cellWidget(row, 1)
            assert row_combo is not None, "each row needs an Import-as combo."
            assert row_combo.count == 1 + len(module.STRUCTURE_TABS), (
                "the Import-as entries are the skip default plus the four "
                "structure-vocabulary titles."
            )
            assert row_combo.currentIndex == 0, (
                "EVERY row defaults to the skip entry -- no prefill, not "
                "even for a segment literally named 'liver'."
            )
            assert row_combo.currentText == module.IMPORT_SKIP_LABEL
    finally:
        _dispose_dialog(widget, dialog, combo)


def test_import_dialog_table_tracks_the_selected_node(qt_widgets):
    """W4 — the mapping table repopulates when the picker's node changes.

    Distinct node names: the stock picker swaps between IDENTICALLY named
    nodes without emitting any currentNodeChanged (a qMRMLNodeComboBox
    quirk) — that case is covered by the accept-time stale-table guard
    (the next pin), not by repopulation.
    """
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    first, _ids = _source_segmentation(slicer, ["a"], nodeName="LoadedA")
    second, _ids = _source_segmentation(slicer, ["x", "y", "z"], nodeName="LoadedB")
    dialog, combo, table = widget._buildImportDialog()
    try:
        combo.setCurrentNode(first)
        assert table.rowCount == 1
        assert table.item(0, 0).text() == "a"
        combo.setCurrentNode(second)
        assert table.rowCount == 3, (
            "switching the picker's node must repopulate the mapping table."
        )
        assert [table.item(row, 0).text() for row in range(3)] == ["x", "y", "z"]
    finally:
        _dispose_dialog(widget, dialog, combo)


def test_stale_mapping_table_never_leaks_onto_another_node(qt_widgets):
    """W4b — same-named nodes: a stale table reads as all-skip at accept.

    ``qMRMLNodeComboBox`` emits NO currentNodeChanged when swapping
    between two nodes that share a display name, so the table can still
    show the previous node's segments.  Their segment ids must not leak
    onto the newly picked node: the accept-time read
    (``_statedCorrespondences``) keys the table to the node it was
    populated for and reads all-skip on a mismatch.
    """
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    first, _ids = _source_segmentation(slicer, ["a"])
    second, _ids = _source_segmentation(slicer, ["x", "y", "z"])
    assert first.GetName() == second.GetName(), (
        "the quirk under test needs identically named nodes."
    )
    dialog, combo, table = widget._buildImportDialog()
    try:
        combo.setCurrentNode(first)
        table.cellWidget(0, 1).setCurrentIndex(1)  # a stated choice
        combo.setCurrentNode(second)
        if table.rowCount == 3:
            pytest.skip(
                "the picker repopulated for the same-named node -- the "
                "stale-table guard has nothing to guard here."
            )
        assert combo.currentNode() is not None
        assert combo.currentNode().GetID() == second.GetID()
        assert widget._statedCorrespondences(combo, table) == {}, (
            "a table populated for ANOTHER node must read as all-skip -- "
            "its segment ids must never ride onto the picked node."
        )
    finally:
        _dispose_dialog(widget, dialog, combo)


def test_import_dialog_annotates_already_present_structures(qt_widgets):
    """W5 — a landed structure's entry reads "(already present)", selectable.

    Picking it stays legal: the landing then adds an EXTRA same-code row
    (the never-overwrite rule, pinned logic-side).
    """
    slicer, module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    landed, ids = _source_segmentation(slicer, ["first"])
    widget.logic.importSegmentation(landed, {ids["first"]: SCT_LIVER_CODE})

    source, ids = _source_segmentation(slicer, ["second"])
    dialog, combo, table = widget._buildImportDialog()
    try:
        combo.setCurrentNode(source)
        row_combo = table.cellWidget(0, 1)
        liver_entry = row_combo.itemText(1)
        assert liver_entry == (
            "Liver parenchyma" + module.IMPORT_ALREADY_PRESENT_SUFFIX
        ), (
            "a structure whose checklist row already landed must be "
            f"annotated; got {liver_entry!r}."
        )
        assert row_combo.itemText(2) == "Portal vein", (
            "structures without a landed row carry NO annotation."
        )
        row_combo.setCurrentIndex(1)
        assert widget._importTableCorrespondences(table) == {
            ids["second"]: SCT_LIVER_CODE
        }, "the annotated entry stays selectable (extra same-code row)."
    finally:
        _dispose_dialog(widget, dialog, combo)


def test_import_table_correspondences_read_the_stated_choices(qt_widgets):
    """W6 — the table reads back {segmentId: sctCode}, skipped rows absent."""
    slicer, module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    source, ids = _source_segmentation(slicer, ["a", "b", "c"])
    dialog, combo, table = widget._buildImportDialog()
    try:
        combo.setCurrentNode(source)
        table.cellWidget(0, 1).setCurrentIndex(1)  # Liver parenchyma
        # Row 1 stays on the skip default.
        table.cellWidget(2, 1).setCurrentIndex(4)  # Tumors
        assert widget._importTableCorrespondences(table) == {
            ids["a"]: SCT_LIVER_CODE,
            ids["c"]: SCT_MASS_CODE,
        }, (
            "the correspondences must mirror the stated combos exactly "
            "(skipped rows absent; combo order is STRUCTURE_TABS order)."
        )
    finally:
        _dispose_dialog(widget, dialog, combo)


def test_import_gesture_routes_mapping_into_logic(qt_widgets):
    """W7 — a fully mapped import consumes the source and lands the rows."""
    slicer, module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    source, ids = _source_segmentation(slicer, ["liver"])
    eligible_ids = {node.GetID() for node in widget._eligibleImportSources()}
    assert source.GetID() in eligible_ids, (
        "a plain (un-roled) segmentation node must be an eligible source."
    )
    canonical = widget.logic.getOrCreateCanonicalSegmentation()
    assert canonical.GetID() not in eligible_ids, (
        "the canonical node must be excluded from the picker."
    )

    widget._importChosenSource(source, {ids["liver"]: SCT_LIVER_CODE})

    assert not _in_scene(slicer, source), "the source must be consumed."
    liver_ids = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    assert len(liver_ids) == 1
    segment = canonical.GetSegmentation().GetSegment(liver_ids[0])
    assert (
        segments_logic.GetSegmentStatus(segment) == segments_logic.InProgress
    )


def test_partial_import_keeps_source_and_says_so(qt_widgets):
    """W8 — a skipped row keeps the source and the status label explains."""
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    source, ids = _source_segmentation(slicer, ["one", "two"])
    widget._importChosenSource(source, {ids["one"]: SCT_LIVER_CODE})

    assert _in_scene(slicer, source), (
        "a partially mapped import must keep the source node in the scene."
    )
    label = widget._statusLabel.text
    assert "1 of 2" in label and "kept" in label, (
        "the status label must state the partial landing and that the "
        f"source was kept; got {label!r}."
    )


def test_skip_all_import_is_a_noop_through_the_widget(qt_widgets):
    """W9 — everything skipped: no landing, source kept, label explains."""
    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    canonical = widget.logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()
    source, _ids = _source_segmentation(slicer, ["liver"])
    widget._importChosenSource(source, {})

    assert _in_scene(slicer, source), "an all-skip import keeps the source."
    assert canonical.GetSegmentation().GetNumberOfSegments() == rows_before
    assert "kept" in widget._statusLabel.text.lower(), (
        "the status label must explain the no-op (explainable state, "
        "ADR-0009)."
    )


def test_import_dialog_carries_ok_and_cancel(qt_widgets):
    """W10 — the dialog must actually be operable: the button box carries
    real Ok + Cancel buttons wired to accept/reject.  Pins the PythonQt
    trap found live: the flags-taking QDialogButtonBox CONSTRUCTOR
    overload does not marshal and produced a buttonless dialog ("nothing
    to do after selecting the node")."""
    import qt

    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    dialog, combo, _table = widget._buildImportDialog()
    try:
        buttons = widget._importDialogButtons
        ok = buttons.button(qt.QDialogButtonBox.Ok)
        cancel = buttons.button(qt.QDialogButtonBox.Cancel)
        assert ok is not None and cancel is not None, (
            "the import dialog must offer Ok AND Cancel -- a buttonless "
            "box leaves the surgeon stranded after picking a node."
        )
        assert ok.isDefault(), "Ok must be the default (Enter confirms)."
        accepted = []
        dialog.connect("accepted()", lambda: accepted.append(1))
        ok.click()
        assert accepted, "clicking Ok must accept the dialog."
    finally:
        _dispose_dialog(widget, dialog, combo)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
