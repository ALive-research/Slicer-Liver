# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The real TotalSegmentator inference wiring behind ``_runTotalSegmentator``.

The seam previously returned an EMPTY scratch node ("real inference lands
with the backend integration") — running a structure yielded nothing.
These pins fix the contract of the real wiring WITHOUT running a real
inference (CI has no model / GPU):

* ``segment()`` exports the input volume, drives the wrapper's
  ``runInference`` (monkeypatched here to write a synthetic per-label
  NIfTI, the backend's on-disk output convention), and imports the
  result into the scratch node as ONE SCT-tagged, non-empty segment.
* the SCT target table covers all four structure-vocabulary codes and builds
  a well-formed backend command line.
* a declined / failed backend install surfaces as the wrapper's typed
  exception, not a silent empty scratch.
"""

from __future__ import annotations

import os

import pytest


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _logic_or_skip(slicer):
    try:
        import LiverSegmentation
    except Exception:
        pytest.skip("LiverSegmentation module not importable.")
    return LiverSegmentation.LiverSegmentationLogic()


def _wrapper_module():
    try:
        from LiverSegmentationLib.ToolWrappers import TotalSegmentator as wrapper
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentationLib not importable ({exc}); ensure "
            "--additional-module-paths includes LiverSegmentation/."
        )
    return wrapper


def _make_input_volume(slicer, name):
    import numpy as np

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", name)
    slicer.util.updateVolumeFromArray(volume, np.zeros((8, 8, 8), dtype="int16"))
    return volume


def _write_synthetic_label(slicer, path):
    """Write a small non-empty labelmap NIfTI at ``path`` (the fake output)."""
    import numpy as np

    labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
    array = np.zeros((8, 8, 8), dtype="uint8")
    array[2:6, 2:6, 2:6] = 1
    slicer.util.updateVolumeFromArray(labelmap, array)
    assert slicer.util.saveNode(labelmap, path), f"fixture write failed: {path}"
    slicer.mrmlScene.RemoveNode(labelmap)


def test_segment_populates_scratch_from_inference_output(monkeypatch):
    """Run -> scratch holds ONE non-empty segment SCT-tagged for the target."""
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    wrapper = _wrapper_module()
    import LiverSegmentation as module

    volume = _make_input_volume(slicer, "TotalSegInferenceInput")
    scratch = None
    try:
        calls = {}

        def _fake_run_inference(input_path, output_dir, sct_code, progress_callback=None):
            calls["input_exists"] = os.path.isfile(input_path)
            calls["sct_code"] = str(sct_code)
            if progress_callback is not None:
                progress_callback("synthetic backend line")
            spec = wrapper.INFERENCE_TARGETS[str(sct_code)]
            for label in spec["labels"]:
                _write_synthetic_label(
                    slicer, os.path.join(output_dir, f"{label}.nii.gz")
                )

        monkeypatch.setattr(wrapper, "runInference", _fake_run_inference)
        # The lazy-install gate must not raise a dialog in the harness.
        monkeypatch.setattr(wrapper, "ensureBackendInstalled", lambda **kw: True)

        progress_lines = []
        scratch = logic.segment(
            volume, module.SCT_LIVER_CODE, progressCallback=progress_lines.append
        )

        assert calls.get("input_exists"), (
            "segment() must EXPORT the input volume to disk before invoking "
            "the backend (the backend consumes a file, not a MRML node)."
        )
        assert calls.get("sct_code") == module.SCT_LIVER_CODE
        assert progress_lines, "backend output lines must reach the progress callback"

        assert scratch is not None and scratch.IsA("vtkMRMLSegmentationNode")
        segmentation = scratch.GetSegmentation()
        assert segmentation.GetNumberOfSegments() == 1, (
            "the liver target must land as EXACTLY ONE segment in scratch; "
            f"got {segmentation.GetNumberOfSegments()} (the empty-scratch stub "
            "yielded 0 -- 'running totalseg does not yield any results')."
        )
        segment_id = segmentation.GetNthSegmentID(0)
        import vtk

        text = vtk.mutable("")
        scratch.GetSegmentation().GetSegment(segment_id).GetTag(
            "TerminologyEntry", text
        )
        assert module.SCT_LIVER_CODE in str(text), (
            "the imported segment must be SCT-tagged for the requested "
            f"structure (ADR-0011); tag was {str(text)!r}."
        )
    finally:
        slicer.mrmlScene.RemoveNode(volume)
        if scratch is not None:
            slicer.mrmlScene.RemoveNode(scratch)


def test_inference_target_table_covers_all_four_structures():
    """Every structure-vocabulary SCT code resolves to a backend task spec."""
    _slicer_or_skip()
    import LiverSegmentation as module

    wrapper = _wrapper_module()
    for code in (
        module.SCT_LIVER_CODE,
        module.SCT_PORTAL_VEIN_CODE,
        module.SCT_HEPATIC_VEIN_CODE,
        module.SCT_MASS_CODE,
    ):
        spec = wrapper.INFERENCE_TARGETS.get(str(code))
        assert spec is not None, f"no inference target spec for SCT {code}"
        assert spec["task"] in ("total", "liver_vessels")
        assert spec["labels"], "each spec names the output label file(s)"


def test_build_command_shapes_the_backend_invocation():
    """The command builder emits task / roi_subset / fast / device flags."""
    _slicer_or_skip()
    wrapper = _wrapper_module()

    cmd = wrapper.buildCommand(
        "/opt/bin/TotalSegmentator", "/tmp/in.nii.gz", "/tmp/out", "10200004", "cpu"
    )
    assert cmd[0] == "/opt/bin/TotalSegmentator"
    assert "-i" in cmd and "/tmp/in.nii.gz" in cmd
    assert "-o" in cmd and "/tmp/out" in cmd
    assert "--task" in cmd and "total" in cmd
    assert "--roi_subset" in cmd and "liver" in cmd
    assert "--fast" in cmd, "the total task runs fast mode (CPU-viable)"
    assert "--device" in cmd and "cpu" in cmd

    vessels = wrapper.buildCommand(
        "/opt/bin/TotalSegmentator", "/tmp/in.nii.gz", "/tmp/out", "8993003", "cpu"
    )
    assert "liver_vessels" in vessels
    assert "--fast" not in vessels, "liver_vessels has no fast variant"
    assert "--roi_subset" not in vessels


#
# buildCommandForStructures — the merged per-task command the job queue's
# coalescing rides on.  Pure-Python pins (no Slicer, no Qt): they run bare
# whenever LiverSegmentationLib resolves, and always in the launched suite.
#

_EXE = "/opt/bin/TotalSegmentator"


def test_build_command_for_structures_unions_roi_subset_when_all_restrict():
    """All specs restrict -> ``--roi_subset`` is the deduplicated union."""
    wrapper = _wrapper_module()

    cmd = wrapper.buildCommandForStructures(
        _EXE, "/tmp/in.nii", "/tmp/out", ["10200004", "32764006"], "cpu"
    )
    assert "--task" in cmd and "total" in cmd
    marker = cmd.index("--roi_subset")
    rois = cmd[marker + 1 : cmd.index("--fast")]
    assert rois == ["liver", "portal_vein_and_splenic_vein"], (
        f"the roi_subset must be the union of every spec's rois; got {rois!r}."
    )
    assert "--fast" in cmd, "liver + portal both support the fast variant."

    # Dedupe: the same code twice must not repeat its roi.
    repeated = wrapper.buildCommandForStructures(
        _EXE, "/tmp/in.nii", "/tmp/out", ["10200004", "10200004"], "cpu"
    )
    assert repeated.count("liver") == 1, (
        "a coalesced duplicate code must not duplicate its roi entry."
    )


def test_build_command_for_structures_omits_roi_subset_when_any_unrestricted(
    monkeypatch,
):
    """ONE unrestricted spec -> no ``--roi_subset`` at all.

    An unrestricted spec means the task already produces everything it can;
    restricting to the union of the OTHER specs' rois would silently drop
    the unrestricted structure's output.
    """
    wrapper = _wrapper_module()

    # Both liver_vessels specs are unrestricted -- no roi flag.
    cmd = wrapper.buildCommandForStructures(
        _EXE, "/tmp/in.nii", "/tmp/out", ["8993003", "4147007"], "cpu"
    )
    assert "--roi_subset" not in cmd
    assert "--fast" not in cmd, "liver_vessels has no fast variant."

    # A MIX of restricted + unrestricted on one task (synthetic spec: the
    # current table has no such pair) must also omit the flag.
    monkeypatch.setitem(
        wrapper.INFERENCE_TARGETS,
        "999999001",
        {"task": "total", "roi_subset": None, "labels": ["everything"], "fast": True},
    )
    mixed = wrapper.buildCommandForStructures(
        _EXE, "/tmp/in.nii", "/tmp/out", ["10200004", "999999001"], "cpu"
    )
    assert "--roi_subset" not in mixed, (
        "one unrestricted spec must drop the roi restriction entirely; "
        f"got {mixed!r}."
    )


def test_build_command_for_structures_fast_only_when_every_spec_supports_it(
    monkeypatch,
):
    """``--fast`` requires EVERY coalesced spec to support the fast variant.

    Synthetic non-fast spec on the ``total`` task (the current table has no
    same-task fast split): coalescing it with the fast-capable liver spec
    must drop ``--fast`` — a fast run of a non-fast-capable structure is a
    silent quality downgrade.
    """
    wrapper = _wrapper_module()

    monkeypatch.setitem(
        wrapper.INFERENCE_TARGETS,
        "999999002",
        {
            "task": "total",
            "roi_subset": ["spleen"],
            "labels": ["spleen"],
            "fast": False,
        },
    )
    cmd = wrapper.buildCommandForStructures(
        _EXE, "/tmp/in.nii", "/tmp/out", ["10200004", "999999002"], "cpu"
    )
    assert "--fast" not in cmd, (
        "one non-fast spec in the coalesced set must veto --fast."
    )
    assert "--roi_subset" in cmd and "spleen" in cmd and "liver" in cmd, (
        "both specs restrict, so the roi union still applies."
    )


def test_build_command_for_structures_rejects_cross_task_and_empty():
    """Cross-task sets and the empty set raise ``ValueError``.

    The job queue coalesces per task; one command covers one task only.
    """
    wrapper = _wrapper_module()

    with pytest.raises(ValueError):
        wrapper.buildCommandForStructures(
            _EXE, "/tmp/in.nii", "/tmp/out", ["10200004", "8993003"], "cpu"
        )
    with pytest.raises(ValueError):
        wrapper.buildCommandForStructures(_EXE, "/tmp/in.nii", "/tmp/out", [], "cpu")


def test_declined_backend_surfaces_as_typed_exception(monkeypatch):
    """An unavailable backend raises the wrapper's typed error, not empty scratch."""
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    wrapper = _wrapper_module()
    import LiverSegmentation as module

    monkeypatch.setattr(wrapper, "ensureBackendInstalled", lambda **kw: False)
    volume = _make_input_volume(slicer, "TotalSegDeclinedInput")
    try:
        with pytest.raises(wrapper.TotalSegmentatorNotInstalled):
            logic.segment(volume, module.SCT_LIVER_CODE)
    finally:
        slicer.mrmlScene.RemoveNode(volume)


def test_stream_splitter_handles_carriage_return_progress():
    """tqdm-style \\r updates must stream as pieces, not sit in a buffer."""
    _slicer_or_skip()
    wrapper = _wrapper_module()

    pieces = wrapper._split_stream_pieces(b"Downloading: 10%\rDownloading: 55%\rDownl")
    assert pieces[:-1] == ["Downloading: 10%", "Downloading: 55%"], (
        "carriage-return-separated progress must split into pieces"
    )
    assert pieces[-1] == b"Downl", "the unterminated rest carries over raw"

    pieces = wrapper._split_stream_pieces(b"line one\nline two\n")
    assert pieces[:-1] == ["line one", "line two"]
    assert pieces[-1] == b""


def test_parse_progress_line_extracts_tqdm_percent_as_predicting():
    """An nnU-Net tqdm refresh maps to ``("predicting", NN)`` (clamped 0–100).

    The backend's sliding-window tqdm bar (stderr, merged into the child
    stream) refreshes with bare carriage returns and embeds its own bar
    glyphs / per-iteration timing — the one fine-grained percent TS emits.
    The parser lifts the leading percent and labels the phase; the raw text
    is never surfaced.
    """
    wrapper = _wrapper_module()

    assert wrapper.parseProgressLine(
        " 45%|████      | 9/20 [00:12<00:15,  1.4s/it]"
    ) == ("predicting", 45)
    assert wrapper.parseProgressLine("100%|██████████| 20/20 [00:28<00:00]") == (
        "predicting",
        100,
    )
    # A leading 0% (bar just started) is still a valid determinate signal.
    assert wrapper.parseProgressLine("  0%|          | 0/20 [00:00<?, ?it/s]") == (
        "predicting",
        0,
    )
    # A stray decimal-second reading must NOT be mistaken for a percent.
    assert wrapper.parseProgressLine("Predicted in 1.4s") == (None, None)


def test_parse_progress_line_maps_milestones_to_clean_indeterminate_stages():
    """TS milestone prints map to a clean stage word, ``percent=None``.

    These lines are ordered phase markers, not percentages, so they render
    indeterminate with clean stage text (a fabricated number would mislead).
    """
    wrapper = _wrapper_module()

    assert wrapper.parseProgressLine("Resampling...") == ("resampling", None)
    assert wrapper.parseProgressLine("Predicting part 1 of 3 ...") == (
        "predicting",
        None,
    )
    assert wrapper.parseProgressLine("Predicting...") == ("predicting", None)
    assert wrapper.parseProgressLine("Saving segmentations...") == ("saving", None)
    assert wrapper.parseProgressLine(
        "Generating rough segmentation for cropping..."
    ) == ("preparing", None)


def test_parse_progress_line_ignores_unrecognised_chatter():
    """Unrecognised lines return ``(None, None)`` so the caller leaves its bar.

    The blank line, the citation banner, the usage-stats notice — none carry a
    stage or percent, so the parser reports nothing and the bar is untouched
    (the raw text is never echoed onto our surface).
    """
    wrapper = _wrapper_module()

    assert wrapper.parseProgressLine("") == (None, None)
    assert wrapper.parseProgressLine("   ") == (None, None)
    assert wrapper.parseProgressLine(
        "If you use this tool please cite: https://pubs.rsna.org/..."
    ) == (None, None)
    assert wrapper.parseProgressLine(
        "TotalSegmentator sends anonymous usage statistics."
    ) == (None, None)


def test_parse_progress_line_drives_a_realistic_merged_stream():
    """A representative merged stream yields clean, ordered stage/percent hits.

    Feeds the pieces a real run would emit (milestone prints on stdout, tqdm
    ``\\r`` refreshes on stderr, both merged) through the stream splitter and
    the parser end-to-end — the widget's exact wiring — and checks the
    distilled sequence, never the raw text.
    """
    wrapper = _wrapper_module()

    raw = (
        b"Resampling...\n"
        b"Predicting part 1 of 3 ...\n"
        b"  0%|          | 0/20 [00:00<?, ?it/s]\r"
        b" 50%|#####     | 10/20 [00:14<00:14,  1.4s/it]\r"
        b"100%|##########| 20/20 [00:28<00:00,  1.4s/it]\r\n"
        b"Saving segmentations...\n"
    )
    *pieces, remainder = wrapper._split_stream_pieces(raw)
    assert remainder == b"", "a newline-terminated stream leaves no carry-over."

    distilled = [
        parsed
        for parsed in (wrapper.parseProgressLine(piece) for piece in pieces)
        if parsed != (None, None)
    ]
    assert distilled == [
        ("resampling", None),
        ("predicting", None),
        ("predicting", 0),
        ("predicting", 50),
        ("predicting", 100),
        ("saving", None),
    ], f"the distilled progress sequence mismatched: {distilled!r}."


def test_sct_tagging_applies_the_structure_visual_defaults():
    """Tagging a segment applies the v1-parity colour + 3D opacity.

    Every AI-produced segment arrived solid green (the generic import
    default) -- v1's look was per-structure: translucent parenchyma so
    interior structures read, and the canonical vessel colours the v1
    display node carried (hepatic (0,151,206)/255; portal
    (216,101,79)/255).  tagSegmentWithSct is the single funnel every
    path (AI accept, import) goes through, so the defaults apply there.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    import LiverSegmentation as module

    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    try:
        node.CreateDefaultDisplayNodes()
        seg_liver = node.GetSegmentation().AddEmptySegment("l", "Liver")
        seg_hepatic = node.GetSegmentation().AddEmptySegment("h", "Hepatic vein")

        logic.tagSegmentWithSct(node, seg_liver, module.SCT_LIVER_CODE, "Liver")
        logic.tagSegmentWithSct(
            node, seg_hepatic, module.SCT_HEPATIC_VEIN_CODE, "Hepatic vein"
        )

        import pytest as _pytest

        liver_color = node.GetSegmentation().GetSegment(seg_liver).GetColor()
        assert tuple(liver_color) == _pytest.approx(
            (221 / 255.0, 130 / 255.0, 101 / 255.0), abs=1e-3
        ), "the liver segment must get the standard liver colour, not green"
        hepatic_color = node.GetSegmentation().GetSegment(seg_hepatic).GetColor()
        assert tuple(hepatic_color) == _pytest.approx(
            (0.0, 151 / 255.0, 206 / 255.0), abs=1e-3
        ), "the hepatic vein must get the v1 canonical vessel blue"

        display = node.GetDisplayNode()
        assert display.GetSegmentOpacity3D(seg_liver) == _pytest.approx(0.2), (
            "the parenchyma renders translucent (v1 opacity 0.2) so the "
            "interior structures read"
        )
        assert display.GetSegmentOpacity3D(seg_hepatic) == _pytest.approx(1.0), (
            "vessels stay opaque"
        )
    finally:
        slicer.mrmlScene.RemoveNode(node)


def test_visual_defaults_survive_accept_onto_the_canonical_node():
    """The CANONICAL display node must carry the opacity after Accept.

    Per-segment 3D opacity lives on the DISPLAY NODE, not the segment:
    applying it while tagging the scratch node meant the setting died
    with the scratch node on Accept -- the copied liver segment rendered
    opaque on the canonical node (the re-demo finding).  Colour travels
    with the segment; opacity must be re-applied post-merge.
    """
    slicer = _slicer_or_skip()
    logic = _logic_or_skip(slicer)
    import pytest as _pytest

    import LiverSegmentation as module

    slicer.mrmlScene.Clear(0)
    scratch = logic.createScratchSegmentation()
    seg_id = scratch.GetSegmentation().AddEmptySegment("l", "Liver")
    logic.tagSegmentWithSct(scratch, seg_id, module.SCT_LIVER_CODE, "Liver")

    canonical = logic.accept(scratch)

    display = canonical.GetDisplayNode()
    assert display is not None, "canonical must carry a display node after Accept"
    canon_seg_id = canonical.GetSegmentation().GetNthSegmentID(0)
    assert display.GetSegmentOpacity3D(canon_seg_id) == _pytest.approx(0.2), (
        "the parenchyma's translucent 3D opacity must survive the merge "
        "onto the canonical node -- it lives on the display node and does "
        "not travel with the copied segment."
    )

# The re-frame-after-landing pin (formerly the card onAccept test) moved to
# test_liversegmentation_toolbar_run_lands_directly.py: the landing gesture
# is the toolbar Run now (ADR-0034 §Amendments), and the re-frame rides it.
