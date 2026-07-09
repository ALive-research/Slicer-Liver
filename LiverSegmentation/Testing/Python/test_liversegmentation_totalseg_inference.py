# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The real TotalSegmentator inference wiring behind ``_runTotalSegmentator``.

The seam previously returned an EMPTY scratch node ("real inference lands
with the backend integration") — running a structure card yielded nothing.
These pins fix the contract of the real wiring WITHOUT running a real
inference (CI has no model / GPU):

* ``segment()`` exports the input volume, drives the wrapper's
  ``runInference`` (monkeypatched here to write a synthetic per-label
  NIfTI, the backend's on-disk output convention), and imports the
  result into the scratch node as ONE SCT-tagged, non-empty segment.
* the SCT target table covers all four structure-card codes and builds
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
    from LiverSegmentationLib.ToolWrappers import TotalSegmentator as wrapper

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


def test_inference_target_table_covers_all_four_cards():
    """Every structure card's SCT code resolves to a backend task spec."""
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
