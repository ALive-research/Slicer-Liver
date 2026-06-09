# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 10 (UI) — segment() reads the Stage-1 PortalVenous volume.

ADR-0024 §"Per-structure micro-workflows": Stage 2 segments the
portal-venous-phase volume produced by Stage 1.  The orchestrator's
``segment(volume, sctTarget)`` consumes the Stage-1 volume flagged
``LiverRole = "PortalVenous"`` (the Stage-1 / Stage-2 hand-off contract).

This pins the input-selection invariant: when the orchestrator selects the
working volume for a card Run, it picks the ``LiverRole="PortalVenous"``
volume — not an arbitrary scalar volume in the scene.  A real
TotalSegmentator inference cannot run in CI, so the backend seam is
**mocked**; the mock records which volume the orchestrator handed it.

Scene-needing: launched-Slicer harness (``pytest_launched``).
RED until the implementer lands the Stage-1 input-selection path per
ADR-0024.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"

# Stage-1 / Stage-2 hand-off: the working volume carries this attribute/value.
LIVER_ROLE_ATTRIBUTE = "LiverRole"
LIVER_ROLE_PORTAL_VENOUS = "PortalVenous"

SCT_LIVER_CODE = "10200004"


def _orchestrator_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; input selection cannot be "
            "exercised yet."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def test_select_input_volume_picks_portalvenous_role():
    """The orchestrator's input selection picks the PortalVenous volume.

    ADR-0024 §"Per-structure micro-workflows": Stage 2 works on the Stage-1
    portal-venous-phase volume.  With a decoy non-portal volume also present,
    the orchestrator's input selection must resolve to the
    ``LiverRole="PortalVenous"`` volume.

    TODO(impl): pin the implementer's input-selection accessor name (e.g.
    ``selectInputVolume()`` / ``_portalVenousVolume()``).  The pinned
    invariant is "the PortalVenous-role volume is chosen", not the spelling.
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    selector = None
    for name in ("selectInputVolume", "_portalVenousVolume", "inputVolume"):
        if hasattr(orch, name):
            selector = getattr(orch, name)
            break
    if selector is None:
        pytest.fail(
            "orchestrator must resolve its working volume from the Stage-1 "
            "LiverRole='PortalVenous' volume (e.g. selectInputVolume()) per "
            "ADR-0024 §'Per-structure micro-workflows' -- not yet implemented."
        )

    decoy = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Arterial")
    decoy.SetAttribute(LIVER_ROLE_ATTRIBUTE, "Arterial")
    portal = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Portal")
    portal.SetAttribute(LIVER_ROLE_ATTRIBUTE, LIVER_ROLE_PORTAL_VENOUS)

    selected = selector() if callable(selector) else selector
    assert selected is not None, (
        "input selection must resolve a volume when a PortalVenous-role "
        "volume exists."
    )
    assert selected.GetID() == portal.GetID(), (
        "input selection must pick the LiverRole='PortalVenous' volume, not "
        "the decoy Arterial volume (ADR-0024 Stage-1/Stage-2 hand-off)."
    )


def test_segment_runs_against_portalvenous_volume(monkeypatch):
    """segment() drives the backend with the PortalVenous volume.

    ADR-0024 §"Per-structure micro-workflows": end-to-end, the volume handed
    to the (mocked) backend is the PortalVenous one.  The backend seam is
    mocked to record its volume argument and return a synthetic scratch node;
    no real TotalSegmentator inference occurs.

    TODO(impl): align the mocked seam name with the implementer's choice
    (same seam as test_liversegmentation_card_run_produces_scratch).
    """
    slicer, orch = _orchestrator_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "segment"):
        pytest.fail(
            "orchestrator must expose segment(volume, sctTarget) per ADR-0024 "
            "-- not yet implemented (the wrapper's run() was a stub)."
        )

    portal = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Portal")
    portal.SetAttribute(LIVER_ROLE_ATTRIBUTE, LIVER_ROLE_PORTAL_VENOUS)

    recorded = {}

    def _fake(volume, sctTarget, *args, **kwargs):
        recorded["volume_id"] = volume.GetID() if volume is not None else None
        scratch = orch.createScratchSegmentation()
        scratch.GetSegmentation().AddEmptySegment("synthetic", "Synthetic")
        return scratch

    seam_set = False
    for seam in ("_invokeBackend", "_runTotalSegmentator", "_segmentWithBackend"):
        if hasattr(orch, seam):
            monkeypatch.setattr(orch, seam, _fake)
            seam_set = True
            break
    if not seam_set:
        pytest.fail(
            "orchestrator must expose a mockable backend seam called by "
            "segment() so CI can exercise input selection without a real "
            "TotalSegmentator inference (ADR-0024 §'Lazy install') -- not yet "
            "implemented."
        )

    orch.segment(portal, SCT_LIVER_CODE)

    assert recorded.get("volume_id") == portal.GetID(), (
        "segment() must drive the backend with the LiverRole='PortalVenous' "
        "volume (ADR-0024 Stage-1/Stage-2 hand-off)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
