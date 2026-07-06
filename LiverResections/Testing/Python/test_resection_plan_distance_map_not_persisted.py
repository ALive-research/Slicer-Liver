# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 6 -- round-trip symmetry + the distance-map non-persistence guard.

The ``.lrp.json`` storage node (``vtkMRMLResectionPlanStorageNode``) already
round-trips every PERSISTED resection-plan field -- name, ``safetyMargin_mm`` /
``riskMargin_mm``, ``orderIndex``, ``state`` and the whole surface block (grid,
initMode, slicingPlane, distanceSpheroid); the C++ ``testPlanRootedRoundTrip``
pins that symmetry field-by-field.

This test pins the ONE input that deliberately does NOT round-trip: the
resection-plan WRAPPER's ``distanceMap`` volume reference (ADR-0031).  The
distance map is a COMPUTED input volume, and a persisted node reference would
carry a scene-local node ID that breaks across scene reloads / machines; stable
cross-machine references are deferred to v2.1 (``Docs/design/
resection-plan-architecture/05-lrp-json-schema.md`` §"references ... break
across machines. v2.1's stable-ID ..."), so v2.0 intentionally omits the
distance map from the plan document -- the plan re-links / recomputes it on load
rather than persisting a fragile ID.

WHY AN ABSENCE TEST (not "the colour of the sky").  This absence has a credible
creep-in path: a symmetry-minded storage edit that "completes" the write/read by
adding ``distanceMap`` alongside the margins would silently ship the fragile
node-ID persistence v2.1 is meant to solve.  This guard fails that edit until the
v2.1 stable-ID work lands, and documents WHY the omission is deliberate.  It is a
CHARACTERIZATION test -- green against the current build (no behaviour change);
it locks the decision, it does not drive one.

Runs under the launched-Slicer ``pytest_launched`` row (needs the registered
``vtkMRMLResectionPlanStorageNode`` + the logic create-API); SKIPS CLEANLY under
bare pytest via the shared guards.

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md  (distance map is a
    path-specific INPUT on the wrapper; silent on persistence)
  * Docs/design/resection-plan-architecture/05-lrp-json-schema.md  (v2.1
    stable-ID deferral)
  * Docs/adr/0014-livermarkups-dissolution.md §"Fourth layer"  (wrapper/carrier)
  * LiverResections/MRML/Testing/Cxx/vtkMRMLResectionPlanStorageNodeTest1.cxx
    (the positive field-by-field round-trip symmetry)
"""

from __future__ import annotations

import os
import tempfile

import pytest

MODULE_NAME = "liverresections"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"


def _slicer_or_skip():
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    return import_slicer_or_skip()


def _resection_logic_or_skip(slicer):
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(f"'{MODULE_NAME}' module not registered.")
    logic = module.logic()
    if logic is None or not hasattr(logic, "CreateResectionPlan"):
        pytest.skip("vtkSlicerLiverResectionsLogic.CreateResectionPlan not in this build.")
    return logic


def _make_plan_with_distance_map(slicer, logic, name):
    """Mint a plan with non-default margins + a wrapper distance-map ref."""
    plan = logic.CreateResectionPlan(name)
    if plan is None or not plan.IsA(PLAN_NODE_CLASS):
        pytest.skip("CreateResectionPlan did not return a resection plan.")
    for attr in ("SetSafetyMargin_mm", "SetRiskMargin_mm", "SetAndObserveDistanceMapVolumeNode",
                 "GetDistanceMapVolumeNode"):
        if not hasattr(plan, attr):
            pytest.skip(f"{PLAN_NODE_CLASS} lacks {attr} in this build (ADR-0031 API absent).")
    plan.SetSafetyMargin_mm(12.0)
    plan.SetRiskMargin_mm(3.0)
    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", f"{name}DMap")
    if volume is None:
        pytest.skip("vtkMRMLScalarVolumeNode not registered.")
    plan.SetAndObserveDistanceMapVolumeNode(volume)
    if plan.GetDistanceMapVolumeNode() is None:
        pytest.skip("distance-map ref did not attach to the wrapper (ADR-0031).")
    return plan


def _storage_or_skip(slicer, plan):
    storage = plan.CreateDefaultStorageNode()
    if storage is None or not storage.IsA("vtkMRMLResectionPlanStorageNode"):
        pytest.skip("plan has no vtkMRMLResectionPlanStorageNode default storage node.")
    slicer.mrmlScene.AddNode(storage)
    return storage


def test_distance_map_reference_does_not_round_trip():
    """A plan's wrapper distance-map ref is NOT persisted to .lrp.json (v2.0).

    Write a distance-mapped plan, read it back into a fresh plan, and assert the
    reloaded wrapper has NO distance-map reference -- the deliberate v2.0
    omission (ADR-0031; v2.1 stable-ID deferral).  The margins, which DO
    round-trip, are checked alongside as the positive-symmetry sanity so this is
    not merely asserting "nothing loaded".
    """
    slicer = _slicer_or_skip()
    slicer.mrmlScene.Clear(0)
    logic = _resection_logic_or_skip(slicer)

    source = _make_plan_with_distance_map(slicer, logic, "RoundTripSource")
    storage = _storage_or_skip(slicer, source)

    tmp_dir = tempfile.mkdtemp(prefix="lrp_roundtrip_")
    path = os.path.join(tmp_dir, "plan.lrp.json")
    storage.SetFileName(path)
    if storage.WriteData(source) != 1:
        pytest.skip("WriteData failed -- storage round-trip unavailable in this build.")

    # Fresh sink plan (its own carrier pre-wired by the create-API, so the
    # surface populates in-place); read the document back into it.
    sink = logic.CreateResectionPlan("RoundTripSink")
    sink_storage = _storage_or_skip(slicer, sink)
    sink_storage.SetFileName(path)
    assert sink_storage.ReadData(sink) == 1, "ReadData of the just-written .lrp.json failed."

    # Positive symmetry sanity: the margins DID round-trip.
    assert abs(sink.GetSafetyMargin_mm() - 12.0) < 1e-6, (
        "safetyMargin_mm must round-trip through .lrp.json."
    )
    assert abs(sink.GetRiskMargin_mm() - 3.0) < 1e-6, (
        "riskMargin_mm must round-trip through .lrp.json."
    )

    # The guard: the distance-map reference is DELIBERATELY not persisted in
    # v2.0 (ADR-0031; v2.1 stable-ID deferral).  A symmetry-minded storage edit
    # that adds it would trip here -- intended, until v2.1 stable IDs land.
    assert sink.GetDistanceMapVolumeNode() is None, (
        "the wrapper distance-map reference must NOT round-trip through "
        ".lrp.json in v2.0 -- it is a computed input whose scene-local node ID "
        "breaks across reloads; stable cross-machine references are deferred to "
        "v2.1 (ADR-0031; Docs/design/resection-plan-architecture/"
        "05-lrp-json-schema.md).  If persistence is being added, do it via the "
        "v2.1 stable-ID mechanism and update this guard."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
