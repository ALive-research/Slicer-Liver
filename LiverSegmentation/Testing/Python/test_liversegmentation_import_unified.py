# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""The unified Stage-2 import path (ADR-0034 §Amendments; §Decision 2).

Importing a loaded segmentation no longer PROMOTES the source node to
canonical: the canonical node's identity is stable, and every imported
segment flows through the SAME landing kernel the AI accept path uses
(``_landSegment``), arriving as native ``InProgress`` with the ``imported``
source tag.  The seam:

    LiverSegmentationLogic.importSegmentation(sourceSegmentationNode)
        -> canonicalNode | None

Per-source-segment SCT resolution order (ADR-0011 dispatch):

  1. an existing ``TerminologyEntry`` tag carrying a structure-vocabulary
     code wins (no name help needed);
  2. else the segment NAME is matched against the
     ``Resources/Terminology/LabelToSCT/`` bridge JSONs (labels + SCT code
     meanings, ADR-0011);
  3. else the segment is unmatched and lands as an EXTRA untagged row —
     structure assignment is then the stock terminology-navigator gesture
     on the table's colour swatch.

Matched segments land into their pre-seeded checklist placeholder only when
the placeholder is EMPTY and provenance-free (the standing landing rule); a
row that already landed — and in particular a surgeon-``Completed`` row — is
NEVER overwritten or demoted by an import: the incoming segment lands as an
extra same-code row and the surgeon decides which to keep.  The source node
is consumed (removed) after a fully successful copy and left untouched on
any failure.

Scene-needing: launched-Slicer harness (``pytest_launched``); skips cleanly
under bare ``PythonSlicer -m pytest``.  RED before the seam lands, green
after (ADR-0027 test-first).
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_CANONICAL = "canonical"

# SCT type codes per ADR-0024 §"Output contract", confirmed against the
# Resources/Terminology/LabelToSCT/ bridges.
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"

# The unified-import logic seam this increment introduces.
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
            "deliverable absent; the unified import flow cannot be exercised."
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
    """RED gate: the unified-import seam must exist for these pins to bite."""
    assert hasattr(logic, IMPORT_SEAM), (
        f"LiverSegmentationLogic.{IMPORT_SEAM}() is missing -- the unified "
        "import path (ADR-0034 §Amendments; §Decision 2 'the import path "
        "unifies') is not implemented."
    )


def _source_segmentation(slicer, names):
    """A plain (un-roled) source segmentation with named empty segments.

    Stands in for a loaded-from-disk segmentation; built through
    ``AddEmptySegment`` like the sibling suites' fixtures.  Returns
    ``(node, {name: segmentId})``.
    """
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Loaded")
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


def test_import_completes_the_checklist_rows_under_review():
    """U1 — bridge-name-matched segments fill the pre-seeded checklist rows.

    A source whose segments carry the bridge names/meanings (``liver``,
    ``Portal vein``, ``Hepatic vein``) lands each into its checklist
    placeholder: ``isStructureAccepted`` flips True per structure, the
    canonical row count is unchanged (placeholder replacement, no duplicate
    rows), and ``isStageComplete`` stays False — imports arrive under
    review (native ``InProgress``), never as the surgeon's confirm.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()

    source, _ids = _source_segmentation(
        slicer, ["liver", "Portal vein", "Hepatic vein"]
    )
    returned = logic.importSegmentation(source)

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
            f"isStructureAccepted({code}) must be True after the name-matched "
            "import lands the structure (ADR-0011 bridge dispatch)."
        )
    assert canonical.GetSegmentation().GetNumberOfSegments() == rows_before, (
        "matched imports REPLACE their empty checklist placeholders -- no "
        "duplicate rows may accrue (ADR-0034 §Amendments landing contract)."
    )
    assert logic.isStageComplete() is False, (
        "imported segments land under review (native InProgress); Stage 2 "
        "completes only on the surgeon's per-row Completed confirm."
    )


def test_name_match_lands_into_placeholder_as_inprogress_imported():
    """U2 — the name-matched segment IS the checklist row: InProgress + imported."""
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    source, _ids = _source_segmentation(slicer, ["liver"])
    logic.importSegmentation(source)

    liver_ids = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)
    assert len(liver_ids) == 1, (
        "the liver name-match must land INTO the pre-seeded placeholder "
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
        "placeholder replacement re-asserts the checklist row identity "
        "(vocabulary title), per the standing landing rule."
    )


def test_terminology_tagged_source_matches_without_name_help():
    """U3 — an SCT-tagged source segment routes by TAG, not by name."""
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    source, ids = _source_segmentation(slicer, ["seg_7"])
    logic.tagSegmentWithSct(source, ids["seg_7"], SCT_PORTAL_VEIN_CODE, "Portal vein")

    logic.importSegmentation(source)

    portal_ids = _sct_segment_ids(module, canonical, SCT_PORTAL_VEIN_CODE)
    assert len(portal_ids) == 1, (
        "a TerminologyEntry tag carrying a structure code must win over "
        "name matching -- the segment lands into the portal-vein "
        f"placeholder; got {len(portal_ids)} portal-tagged row(s)."
    )
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    segment = canonical.GetSegmentation().GetSegment(portal_ids[0])
    assert (
        segments_logic.GetSegmentStatus(segment) == segments_logic.InProgress
    )


def test_unmatched_segment_lands_as_extra_untagged_row():
    """U4 — no tag + no bridge name: an extra row, name kept, no SCT tag."""
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    rows_before = canonical.GetSegmentation().GetNumberOfSegments()
    source, _ids = _source_segmentation(slicer, ["mystery structure"])
    logic.importSegmentation(source)

    segmentation = canonical.GetSegmentation()
    assert segmentation.GetNumberOfSegments() == rows_before + 1, (
        "an unmatched segment must land as an EXTRA canonical row (structure "
        "assignment is the stock terminology-navigator gesture afterwards)."
    )
    extra_id = segmentation.GetNthSegmentID(rows_before)
    extra = segmentation.GetSegment(extra_id)
    assert extra.GetName() == "mystery structure", (
        "the unmatched row keeps its imported name."
    )
    tag = _segment_tag(extra, module.TERMINOLOGY_ENTRY_TAG)
    for _title, code in module.STRUCTURE_TABS:
        assert f"^{code}^" not in tag, (
            "an unmatched row must not be silently assigned a structure code."
        )
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    assert segments_logic.GetSegmentStatus(extra) == segments_logic.InProgress
    assert _segment_tag(extra, module.SOURCE_TAG) == module.SOURCE_IMPORTED


def test_landed_confirmed_row_is_never_overwritten():
    """U5 — a landed (here: Completed) row survives a re-import untouched.

    Maintainer-agreed never-overwrite rule: when the expected row already
    landed, the incoming same-structure segment lands as an EXTRA row
    (name kept, matched SCT tag, InProgress + imported) and the original
    keeps its content AND status — the surgeon decides which to keep.  In
    particular the AI path's demote-on-rerun staleness rule does NOT ride
    the import path.
    """
    slicer, module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic

    first, _ids = _source_segmentation(slicer, ["liver"])
    logic.importSegmentation(first)
    landed_id = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)[0]
    landed = canonical.GetSegmentation().GetSegment(landed_id)
    segments_logic.SetSegmentStatus(landed, segments_logic.Completed)

    second, _ids = _source_segmentation(slicer, ["liver"])
    logic.importSegmentation(second)

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
    assert extra.GetName() == "liver", (
        "the extra row keeps the incoming segment's own name -- only "
        "placeholder replacement re-asserts the vocabulary title."
    )


def test_source_consumed_on_success_untouched_on_failure():
    """U6 — the source node is removed on success; a no-op leaves it alone."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    logic.getOrCreateCanonicalSegmentation()

    # Success: the copied segments live on in canonical; the source goes
    # (the retired promotion path consumed the source too).
    source, _ids = _source_segmentation(slicer, ["liver"])
    assert logic.importSegmentation(source) is not None
    assert not _in_scene(slicer, source), (
        "a fully successful import must consume (remove) the source node."
    )

    # Failure/no-op: a source with nothing to land is left untouched.
    empty_source = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "Empty"
    )
    assert logic.importSegmentation(empty_source) is None
    assert _in_scene(slicer, empty_source), (
        "a failed/no-op import must leave the source node in the scene."
    )


def test_degenerate_import_is_noop_and_does_not_complete_stage():
    """U7 — None / segment-less sources: no raise, Stage 2 stays incomplete."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    assert logic.importSegmentation(None) is None
    assert logic.isStageComplete() is False, (
        "a None-source import must not complete Stage 2."
    )

    empty_source = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLSegmentationNode", "Empty"
    )
    assert logic.importSegmentation(empty_source) is None
    assert logic.isStageComplete() is False, (
        "an import that lands nothing must not complete Stage 2 (ADR-0034 "
        "§Amendments completion predicate)."
    )


def test_canonical_and_scratch_roles_are_not_importable_sources():
    """U8 — the orchestrator's own nodes are never import sources."""
    slicer, _module, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    _require_seam(logic)

    canonical = logic.getOrCreateCanonicalSegmentation()
    assert logic.importSegmentation(canonical) is None, (
        "importing the canonical into itself must be refused."
    )
    scratch = logic.createScratchSegmentation()
    assert logic.importSegmentation(scratch) is None, (
        "scratch-role nodes are the AI landing's internal carriers, not "
        "import sources (accept() is their path)."
    )
    assert _in_scene(slicer, scratch)


def test_stock_navigator_terminology_format_is_recognized():
    """U9 — the stock navigator's serialization satisfies the ^code^ greps.

    The unmatched-row assignment gesture is the STOCK terminology navigator
    (double-click the colour swatch); its ``TerminologyEntry`` value is the
    ``SerializeTerminologyEntry`` tilde chain.  Pin that (a) the documented
    stock shape is recognised by the module's SCT readers, and (b) a
    round-trip of the module's own serialization through the stock
    terminologies logic stays recognised.
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

    # The tag also routes the import (resolution step 1: tag wins).
    canonical = logic.getOrCreateCanonicalSegmentation()
    logic.importSegmentation(source)
    assert len(_sct_segment_ids(module, canonical, SCT_LIVER_CODE)) == 1

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
# Widget surface: the toolbar Import… gesture.
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


def test_toolbar_hosts_import_button(qt_widgets):
    """U10 — the selection toolbar carries the Import… gesture."""
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
    """U11 — no importable node: the shared status label explains, no dialog."""
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


def test_import_gesture_routes_chosen_source_into_logic(qt_widgets):
    """U12 — the picker's OK routes the node through the unified logic seam."""
    slicer, module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    source, _ids = _source_segmentation(slicer, ["liver"])
    eligible_ids = {node.GetID() for node in widget._eligibleImportSources()}
    assert source.GetID() in eligible_ids, (
        "a plain (un-roled) segmentation node must be an eligible source."
    )
    canonical = widget.logic.getOrCreateCanonicalSegmentation()
    assert canonical.GetID() not in eligible_ids, (
        "the canonical node must be excluded from the picker."
    )

    widget._importChosenSource(source)

    assert not _in_scene(slicer, source), "the source must be consumed."
    liver_ids = _sct_segment_ids(module, canonical, SCT_LIVER_CODE)
    segments_logic = slicer.vtkSlicerSegmentationsModuleLogic
    assert len(liver_ids) == 1
    segment = canonical.GetSegmentation().GetSegment(liver_ids[0])
    assert (
        segments_logic.GetSegmentStatus(segment) == segments_logic.InProgress
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_import_dialog_carries_ok_and_cancel(qt_widgets):
    """The picker dialog must actually be operable: the button box carries
    real Ok + Cancel buttons wired to accept/reject.  Pins the PythonQt
    trap found live: the flags-taking QDialogButtonBox CONSTRUCTOR
    overload does not marshal and produced a buttonless dialog ("nothing
    to do after selecting the node")."""
    import qt

    slicer, _module, _logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer, qt_widgets)

    dialog, combo = widget._buildImportDialog()
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
        combo.setMRMLScene(None)
        dialog.setParent(None)
        dialog.deleteLater()
