# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0034 §Amendments item 4 — the embedded Segment Editor increment.

Edit is an embedded ``qMRMLSegmentEditorWidget`` in a collapsible section
directly under the anatomy segments table (the MONAILabel /
SegmentationReview idiom), replacing the jump-to-module Edit button:

  * The editor lives inside a ``ctkCollapsibleButton``, collapsed by
    default, placed between the segments table and the import section.
  * It drives its OWN non-singleton ``vtkMRMLSegmentEditorNode`` — never
    the stock Segment Editor module's singleton — with a curated effect
    list (the AI-mask-correction set) and the node-selector rows hidden:
    the canonical node and the Stage-1 PortalVenous volume are pinned
    inputs, not user choices.
  * Selecting a table row syncs the editor's current segment; the
    toolbar's Edit button expands the section and syncs the selection
    (the module jump is deleted).
  * Demote-on-edit (ADR-0034 §Decision 2 staleness, as amended): a
    CONTENT modification to a ``Completed`` segment hosted on the
    canonical node demotes it to ``InProgress`` — the hook rides
    ``vtkSegmentation::SourceRepresentationModified`` (segment id as call
    data on the editor-apply funnel), so stock-module edits are covered
    too.  Writing the status TAG itself must never demote or recurse,
    and the pre-seed / landing paths must not spuriously demote rows
    they do not land.

Needs the launched-Slicer harness (module + Qt + MRML); skips cleanly
under bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"

#: The curated AI-mask-correction effect set (ADR-0034 §Amendments item 4).
CURATED_EFFECTS = ["Paint", "Erase", "Scissors", "Islands", "Smoothing"]


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


def _add_input_volume(slicer):
    """A Stage-1 PortalVenous working volume (the editor's pinned source)."""
    import numpy as np

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    slicer.util.updateVolumeFromArray(volume, np.zeros((8, 8, 8), dtype="int16"))
    volume.SetAttribute("LiverRole", "PortalVenous")
    return volume


def _sct_segment_id(module, canonical, code):
    """The single segment id on ``canonical`` terminology-tagged ``code``."""
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
    assert len(ids) == 1, f"expected exactly one segment tagged ^{code}^; got {ids!r}."
    return ids[0]


def _modify_segment_content(slicer, canonical, segment_id, dim=4):
    """Write voxel CONTENT into a canonical segment via the editor funnel.

    ``vtkSlicerSegmentationsModuleLogic.SetBinaryLabelmapToSegment`` is the
    same ``vtkSegmentationModifier.ModifyBinaryLabelmap`` path every Segment
    Editor effect apply routes through, and it fires
    ``vtkSegmentation::SourceRepresentationModified`` with the segment id as
    call data — exactly the event the demote-on-edit hook observes.
    """
    import vtk

    labelmap = slicer.vtkOrientedImageData()
    labelmap.SetDimensions(dim, dim, dim)
    labelmap.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
    labelmap.GetPointData().GetScalars().Fill(1)
    assert slicer.vtkSlicerSegmentationsModuleLogic.SetBinaryLabelmapToSegment(
        labelmap, canonical, segment_id
    ), "the content write through the editor funnel must succeed."


def _canonical_of(widget):
    canonical = widget.segmentsTable().segmentationNode()
    assert canonical is not None, "setup must have bound the canonical node."
    return canonical


# --------------------------------------------------------------------------- #
# The embedded editor: shape, configuration, pinned inputs.
# --------------------------------------------------------------------------- #


def test_embedded_editor_exists_collapsed_and_configured(qt_widgets):
    """The panel hosts a stock ``qMRMLSegmentEditorWidget`` inside a
    collapsed ``ctkCollapsibleButton`` under the table (above the import
    section), selectors hidden, curated effect list pinned, bound to the
    canonical node + the Stage-1 PortalVenous source volume (ADR-0034
    §Amendments item 4)."""
    slicer = _slicer_or_skip()
    _module_or_skip()
    slicer.mrmlScene.Clear(0)

    volume = _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)

    editor = widget.embeddedEditor()
    assert editor is not None, (
        "the Stage-2 panel must host the embedded Segment Editor "
        "(ADR-0034 §Amendments item 4)."
    )
    assert editor.className() == "qMRMLSegmentEditorWidget", (
        "Edit must be the STOCK qMRMLSegmentEditorWidget -- no bespoke "
        "editor surface."
    )

    section = widget.embeddedEditorSection()
    assert section is not None and section.className() == "ctkCollapsibleButton", (
        "the editor must sit inside a ctkCollapsibleButton section."
    )
    assert section.collapsed, (
        "the editor section must be COLLAPSED by default -- the table is "
        "the primary surface; Edit is the opt-in gesture."
    )
    assert editor in section.findChildren("qMRMLSegmentEditorWidget"), (
        "the editor widget must live INSIDE the collapsible section."
    )

    # Placement: directly under the table (with its toolbar), ABOVE the
    # import section.
    layout = widget.layout
    load_section = slicer.util.findChild(widget.parent, "LoadSegmentationSection")
    assert (
        layout.indexOf(widget.segmentsTable())
        < layout.indexOf(section)
        < layout.indexOf(load_section)
    ), (
        "the editor section must sit under the segments table and above "
        "the import section (ADR-0034 §Amendments item 4)."
    )

    # Pinned inputs: the node-selector rows are hidden -- the canonical
    # node and the Stage-1 volume are contracts, not user choices.
    assert not editor.segmentationNodeSelectorVisible, (
        "the segmentation-node selector row must be hidden."
    )
    assert not editor.sourceVolumeNodeSelectorVisible, (
        "the source-volume selector row must be hidden."
    )
    assert not editor.switchToSegmentationsButtonVisible, (
        "the switch-to-Segmentations module button must be hidden -- the "
        "jump-out path is retired."
    )

    # Curated effects: the AI-mask-correction set, nothing else.
    assert list(editor.effectNameOrder()) == CURATED_EFFECTS, (
        "the effect list must be the curated AI-mask-correction set; got "
        f"{list(editor.effectNameOrder())!r}."
    )
    assert not editor.unorderedEffectsVisible, (
        "effects outside the curated order must be hidden "
        "(unorderedEffectsVisible False)."
    )

    # Bound inputs: the canonical node + the Stage-1 PortalVenous volume.
    canonical = _canonical_of(widget)
    bound = editor.segmentationNode()
    assert bound is not None and bound.GetID() == canonical.GetID(), (
        "the editor must be pinned to the canonical segmentation node."
    )
    source = editor.sourceVolumeNode()
    assert source is not None and source.GetID() == volume.GetID(), (
        "the editor's source volume must be the Stage-1 PortalVenous "
        "volume (logic.selectInputVolume), like the table bind."
    )


def test_embedded_editor_node_is_not_the_stock_singleton(qt_widgets):
    """The embedded editor drives its OWN non-singleton
    ``vtkMRMLSegmentEditorNode`` -- never the stock Segment Editor
    module's singleton, so embedded edits cannot clobber (or be
    clobbered by) the stock module's state."""
    slicer = _slicer_or_skip()
    _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    editor_node = widget.embeddedEditor().mrmlSegmentEditorNode()
    assert editor_node is not None, (
        "the embedded editor must have its parameter node set on setup."
    )
    assert not editor_node.GetSingletonTag(), (
        "the embedded editor's parameter node must be NON-singleton."
    )

    # Mint the stock module's singleton exactly the way SegmentEditor.py
    # does and pin that the two are DIFFERENT nodes.
    stock = slicer.mrmlScene.GetSingletonNode(
        "SegmentEditor", "vtkMRMLSegmentEditorNode"
    )
    if stock is None:
        stock = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSegmentEditorNode")
        stock.UnRegister(None)
        stock.SetSingletonTag("SegmentEditor")
        stock = slicer.mrmlScene.AddNode(stock)
    assert stock.GetID() != editor_node.GetID(), (
        "the embedded editor must NOT share the stock Segment Editor "
        "module's singleton parameter node."
    )
    # Singleton nodes survive the fixture's scene Clear -- reclaim the
    # minted stock node explicitly so the scene returns to baseline.
    slicer.mrmlScene.RemoveNode(stock)


# --------------------------------------------------------------------------- #
# Selection sync + the rewired Edit button.
# --------------------------------------------------------------------------- #


def test_row_selection_syncs_editor_current_segment(qt_widgets):
    """Selecting a table row sets the editor's current segment through the
    existing deferred selection re-resolve (the same settle path the Run
    re-label rides)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = _canonical_of(widget)
    editor = widget.embeddedEditor()

    liver_id = _sct_segment_id(module, canonical, module.SCT_LIVER_CODE)
    widget.segmentsTable().setSelectedSegmentIDs([liver_id])
    widget._onTableSelectionChanged()
    slicer.app.processEvents()
    assert editor.currentSegmentID() == liver_id, (
        "selecting a table row must sync the editor's current segment."
    )

    portal_id = _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    widget.segmentsTable().setSelectedSegmentIDs([portal_id])
    widget._onTableSelectionChanged()
    slicer.app.processEvents()
    assert editor.currentSegmentID() == portal_id, (
        "a new row selection must re-sync the editor's current segment."
    )


def test_edit_button_expands_the_section_and_syncs_the_selection(qt_widgets):
    """The toolbar's Edit button expands the collapsible and syncs the
    FIRST selected row into the editor; the jump-to-module path is
    deleted (ADR-0034 §Amendments item 4: the embedded editor replaces
    the jump-to-module ✎ buttons)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    _add_input_volume(slicer)
    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = _canonical_of(widget)

    assert widget._editButton.text == "Edit", (
        "the toolbar button reads plain 'Edit' -- it no longer jumps to "
        f"the Segment Editor module; got {widget._editButton.text!r}."
    )
    assert not hasattr(widget, "onEditInSegmentEditor"), (
        "the module-jump handler must be deleted -- the embedded editor "
        "REPLACES the jump-to-module path (ADR-0034 §Amendments item 4)."
    )

    section = widget.embeddedEditorSection()
    assert section.collapsed, "precondition: the section starts collapsed."

    portal_id = _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    widget.segmentsTable().setSelectedSegmentIDs([portal_id])
    widget.onEditSelectedSegment()

    assert not section.collapsed, (
        "the Edit gesture must EXPAND the embedded-editor section."
    )
    assert widget.embeddedEditor().currentSegmentID() == portal_id, (
        "the Edit gesture must sync the selected row into the editor."
    )


# --------------------------------------------------------------------------- #
# Demote-on-edit (ADR-0034 §Decision 2 staleness rule, as amended).
# --------------------------------------------------------------------------- #


def test_content_edit_demotes_completed_segment_to_inprogress(qt_widgets):
    """(a) A CONTENT modification to a ``Completed`` segment hosted on the
    canonical node demotes it to ``InProgress`` -- an edited confirm is
    stale and must re-enter review.  The hook is segmentation-level
    (``SourceRepresentationModified``), so any editor-funnel write
    (embedded OR stock module) is covered."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = _canonical_of(widget)
    segments_logic = _segments_logic(slicer)

    liver_id = _sct_segment_id(module, canonical, module.SCT_LIVER_CODE)
    liver = canonical.GetSegmentation().GetSegment(liver_id)

    # Land content (segment not yet confirmed -- the hook must not touch
    # a non-Completed row on this write), then confirm.
    _modify_segment_content(slicer, canonical, liver_id, dim=4)
    assert (
        segments_logic.GetSegmentStatus(liver) != segments_logic.Completed
    ), "precondition: landing content must not read Completed."
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)

    # The edit: a second content write while Completed -> InProgress.
    _modify_segment_content(slicer, canonical, liver_id, dim=6)
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress
    ), (
        "editing a Completed segment must demote it to InProgress "
        "(ADR-0034 §Decision 2 staleness rule, as amended)."
    )

    # A further edit while already InProgress stays InProgress.
    _modify_segment_content(slicer, canonical, liver_id, dim=8)
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.InProgress
    ), "an edit to an InProgress segment must leave it InProgress."


def test_status_tag_writes_do_not_demote_or_recurse(qt_widgets):
    """(b) Writing the STATUS TAG itself (the surgeon's confirm gesture,
    the demote itself) must neither demote nor recurse: the hook keys on
    the CONTENT event (``SourceRepresentationModified``), which tag
    writes never fire -- ``SetSegmentStatus`` only raises
    ``SegmentModified``."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = _canonical_of(widget)
    segments_logic = _segments_logic(slicer)

    liver_id = _sct_segment_id(module, canonical, module.SCT_LIVER_CODE)
    liver = canonical.GetSegmentation().GetSegment(liver_id)
    _modify_segment_content(slicer, canonical, liver_id)
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)

    # Re-assert Completed (an idempotent tag write) -- must stay Completed.
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.Completed
    ), "re-writing Completed must not demote (no loop on the status tag)."

    # A status round-trip through Flagged -- every write must LAND as
    # written; a demoting/recursing hook would corrupt the cycle.
    segments_logic.SetSegmentStatus(liver, segments_logic.Flagged)
    assert segments_logic.GetSegmentStatus(liver) == segments_logic.Flagged
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.Completed
    ), "the status-cell cycle must land as written -- never demoted."

    # Other segment-tag writes (provenance, terminology) are metadata,
    # not content: no demote.
    liver.SetTag(module.SOURCE_TAG, module.SOURCE_TOTALSEG)
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.Completed
    ), "a segment-tag write must never demote a Completed segment."


def test_preseed_and_landing_do_not_spuriously_demote(qt_widgets):
    """(c) The pre-seed and landing paths must not spuriously demote rows
    they do not land: re-running the checklist pre-seed keeps a
    Completed confirm; landing a DIFFERENT structure's scratch keeps it
    too (the same-code staleness demote is ``_landSegment``'s own,
    already pinned in the segments-table suite)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    slicer.mrmlScene.Clear(0)

    widget = _widget_or_skip(slicer, qt_widgets)
    canonical = _canonical_of(widget)
    segments_logic = _segments_logic(slicer)
    logic = widget.logic

    liver_id = _sct_segment_id(module, canonical, module.SCT_LIVER_CODE)
    liver = canonical.GetSegmentation().GetSegment(liver_id)
    _modify_segment_content(slicer, canonical, liver_id)
    segments_logic.SetSegmentStatus(liver, segments_logic.Completed)

    # The pre-seed path (getOrCreate re-entry / scene self-heal).
    logic.getOrCreateCanonicalSegmentation()
    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.Completed
    ), "re-running the checklist pre-seed must not demote a confirm."

    # The landing path, for a DIFFERENT structure.
    scratch = logic.createScratchSegmentation()
    seg_id = scratch.GetSegmentation().AddEmptySegment("portal", "Portal vein")
    logic.tagSegmentWithSct(
        scratch, seg_id, module.SCT_PORTAL_VEIN_CODE, "Portal vein"
    )
    _modify_segment_content(slicer, scratch, seg_id)
    logic.accept(scratch)

    assert (
        segments_logic.GetSegmentStatus(liver) == segments_logic.Completed
    ), "landing another structure must not demote an unrelated confirm."
    portal_id = _sct_segment_id(module, canonical, module.SCT_PORTAL_VEIN_CODE)
    portal = canonical.GetSegmentation().GetSegment(portal_id)
    assert (
        segments_logic.GetSegmentStatus(portal) == segments_logic.InProgress
    ), "the landed structure itself reads InProgress (produced, under review)."
    # The untouched placeholders stay NotStarted -- nothing was demoted or
    # spuriously started by the landing cascade.
    for code in (module.SCT_HEPATIC_VEIN_CODE, module.SCT_MASS_CODE):
        other_id = _sct_segment_id(module, canonical, code)
        other = canonical.GetSegmentation().GetSegment(other_id)
        assert (
            segments_logic.GetSegmentStatus(other) == segments_logic.NotStarted
        ), "rows the landing did not touch must stay NotStarted."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
