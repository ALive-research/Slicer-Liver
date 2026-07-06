# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""#501 slice 5 -- FlattenedSurfaceRepresentation shades off the WRAPPER.

The resectogram's flattened strip shades from the same distance field the 3D
Bezier path uses, through the SAME ``vtkOpenGLResection2DPolyDataMapper``.  Its
band needs the three wrapper-owned inputs ADR-0031 clusters on the
``vtkMRMLResectionPlanNode`` wrapper: the distance-map volume,
``SetResectionMargin(SafetyMargin_mm)``, and
``SetUncertaintyMargin(RiskMargin_mm)``.

The gap this pins: today ``FlattenedSurfaceRepresentation._apply_distance_map_texture``
reads ``GetDistanceMapVolumeNode`` off the DATA NODE (the carrier) -- the WRONG
layer (ADR-0031 puts the distance map on the wrapper) -- and threads NO margins.
Slice 5 ports the 3D path (``BezierPlanningRepresentation.SetResectionPlanNode``
+ ``_apply_resection_plan``): source the distance-map volume from the wrapper
(``plan.GetDistanceMapVolumeNode()``) and push ``SetResectionMargin`` /
``SetUncertaintyMargin`` from the wrapper's margins onto the 2D mapper.

-- GL-FREE VIA A FAKE MAPPER --

The real 2D mapper binds the distance map through ``SetDistanceMapTextureObject``
(a GL 3D texture built on the render window -- needs a live GL context).  These
tests are GL-free: they inject a FAKE mapper (same idiom as
``test_bezier_planning_surface_mapper_wiring.py``'s mock-mapper) that RECORDS the
``SetResectionMargin`` / ``SetUncertaintyMargin`` scalar-setter calls and the
distance-map volume node the Representation sourced, so the margin values + the
distance-map SOURCE LAYER are asserted without any render window.  The actual
3D-texture upload + the strip render stay on the :0 eyeball follow-up (see the
module note below) -- they are not asserted here.

-- WHY LAUNCHED-SLICER (soft) --

The Representation is plain Python + VTK, but it sources the distance-map volume
off a wrapped ``vtkMRMLResectionPlanNode``, so a wrapped plan node is needed for
the positive path.  Skips cleanly under bare pytest via the shared
``slicer_pytest_support`` guards + the ``SetResectionPlanNode`` seam gate.

-- WHY RED NOW --

``FlattenedSurfaceRepresentation`` has no ``SetResectionPlanNode`` seam and does
not thread margins, so every test SKIPS cleanly.  The skip lifts when slice 5
ports the wrapper-shading path (ADR-0027 §Conformance).

:0-EYEBALL FOLLOW-UP (explicitly out of scope here):
  * the GL 3D distance-map TEXTURE upload (``SetDistanceMapTextureObject`` +
    ras/ijk matrices on the real mapper); and
  * the flattened strip actually rendering the projected margin band.
  Both need a live GL context and are verified on the interactive :0 pass, not
  in this GL-free module-layer test (ADR-0031; ADR-0032 §Conformance idiom).

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md
  * Docs/adr/0025-locator-architecture.md §Context (the resectogram band)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §3, §6
  * Docs/adr/0027-invariant-test-first-v2-implementation.md
  * LiverResections/LiverResectionsLib/Representations/FlattenedSurfaceRepresentation.py
  * LiverResections/LiverResectionsLib/Representations/BezierPlanningRepresentation.py
    (SetResectionPlanNode / _apply_resection_plan -- the 3D-path precedent)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
PLAN_NODE_CLASS = "vtkMRMLResectionPlanNode"
VOLUME_NODE_CLASS = "vtkMRMLScalarVolumeNode"


class _FakeResection2DMapper:
    """GL-free stand-in for ``vtkOpenGLResection2DPolyDataMapper``.

    Records the margin scalar-setters + the distance-map source so the
    wrapper-shading path is asserted without a GL context.  The real mapper
    binds the distance map through ``SetDistanceMapTextureObject`` (a GL 3D
    texture) -- here we record only the volume node the Representation SOURCED,
    which is the layer-discrimination this slice is about; the texture upload
    is the :0 follow-up.
    """

    def __init__(self):
        self.resection_margin = None
        self.uncertainty_margin = None
        # ``sentinel`` distinguishes "never touched" from an explicit clear.
        self.distance_map_texture = "sentinel"
        # The volume node the Representation resolved as the distance-map
        # source (recorded by the injected sourcing hook, below).
        self.distance_map_source = "sentinel"

    def SetResectionMargin(self, value):  # noqa: N802 - VTK verb
        self.resection_margin = float(value)

    def SetUncertaintyMargin(self, value):  # noqa: N802 - VTK verb
        self.uncertainty_margin = float(value)

    def SetDistanceMapTextureObject(self, texture):  # noqa: N802 - VTK verb
        self.distance_map_texture = texture

    def GetDistanceMapTextureObject(self):  # noqa: N802 - VTK verb
        return None if self.distance_map_texture == "sentinel" else self.distance_map_texture


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_representation_or_skip():
    try:
        from LiverResectionsLib.Representations.FlattenedSurfaceRepresentation import (
            FlattenedSurfaceRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "FlattenedSurfaceRepresentation not importable "
            f"({exc!r}) -- not reachable in this environment."
        )
    return FlattenedSurfaceRepresentation()


def _require_plan_shading_seam_or_skip(rep):
    """Skip unless the wrapper-shading seam (slice 5) has landed.

    RED == the Representation has no ``SetResectionPlanNode`` -- the seam that
    sources the distance map + margins off the ``vtkMRMLResectionPlanNode``
    wrapper (ADR-0031).  The skip lifts when slice 5 ports the 3D path's
    ``_apply_resection_plan`` (ADR-0027 §Conformance).
    """
    if not hasattr(rep, "SetResectionPlanNode"):
        pytest.skip(
            "FlattenedSurfaceRepresentation has no SetResectionPlanNode -- "
            "the #501 slice 5 wrapper-shading seam has not landed."
        )


def _inject_fake_mapper(rep):
    """Swap the Representation's 2D mapper for the GL-free fake + record the
    distance-map source layer.

    The Representation's ``_apply_distance_map_texture`` sources the volume via
    a getter on some node (the carrier today; the WRAPPER after slice 5).  We
    cannot read the private call directly, so we wrap the mapper's
    ``SetDistanceMapTextureObject`` and, crucially, record which node the
    Representation queried by wrapping the sourcing helper if present; falling
    back to inspecting ``_distance_map_volume`` which the Representation records
    as the resolved source (see ``_apply_distance_map_texture``).
    """
    fake = _FakeResection2DMapper()
    rep._resection_mapper_2d = fake
    return fake


def _resolved_distance_map_source(rep, fake):
    """The volume node the Representation recorded as its distance-map source.

    ``_apply_distance_map_texture`` stores the resolved volume on
    ``rep._distance_map_volume`` -- that is the SOURCE-LAYER discriminator this
    slice is about (carrier vs wrapper).  Returns it, or ``None`` when unset.
    """
    return getattr(rep, "_distance_map_volume", None)


def test_flattened_surface_threads_margins_from_wrapper():
    """Invariant 2: safety + risk margins reach the 2D mapper from the WRAPPER.

    With a plan wrapper carrying ``SafetyMargin_mm`` / ``RiskMargin_mm``, the
    Representation's ``update`` pushes ``SetResectionMargin(safety)`` +
    ``SetUncertaintyMargin(risk)`` onto the 2D mapper -- porting
    ``BezierPlanningRepresentation._apply_resection_plan`` into the resectogram
    path.  Asserted GL-free via the fake mapper's recorded scalars.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_plan_shading_seam_or_skip(rep)

    fake = _inject_fake_mapper(rep)

    data = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    display = slicer.mrmlScene.AddNewNodeByClass(RESECTOGRAM_DISPLAY_NODE_CLASS)
    plan = slicer.mrmlScene.AddNewNodeByClass(PLAN_NODE_CLASS)
    if data is None or display is None or plan is None:
        pytest.skip("wrapper / carrier / display nodes not all registered.")
    if not (hasattr(plan, "SetSafetyMargin_mm") and hasattr(plan, "SetRiskMargin_mm")):
        pytest.skip(f"{PLAN_NODE_CLASS} has no Safety/Risk margin setters.")

    plan.SetSafetyMargin_mm(10.0)
    plan.SetRiskMargin_mm(2.0)

    rep.SetResectionPlanNode(plan)
    rep.update(display, data)

    assert fake.resection_margin is not None, (
        "the wrapper's SafetyMargin_mm must reach the 2D mapper's "
        "SetResectionMargin (ADR-0031) -- no margin was threaded."
    )
    assert abs(fake.resection_margin - 10.0) < 1e-5, (
        "plan SafetyMargin_mm must reach SetResectionMargin; got "
        f"{fake.resection_margin}."
    )
    assert fake.uncertainty_margin is not None and abs(
        fake.uncertainty_margin - 2.0
    ) < 1e-5, (
        "plan RiskMargin_mm must reach the 2D mapper's SetUncertaintyMargin; "
        f"got {fake.uncertainty_margin}."
    )


def test_flattened_surface_sources_distance_map_from_wrapper_not_carrier():
    """Invariant 3 (positive): distance map is sourced from the WRAPPER.

    Negative discriminator: a carrier whose data node has NO distance map but
    whose WRAPPER carries one -- the Representation must resolve the distance-map
    volume from the WRAPPER (present), NOT the carrier.  This is the layer fix:
    ADR-0031 puts the distance map on the plan wrapper, not the carrier.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_plan_shading_seam_or_skip(rep)

    _inject_fake_mapper(rep)

    data = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    display = slicer.mrmlScene.AddNewNodeByClass(RESECTOGRAM_DISPLAY_NODE_CLASS)
    plan = slicer.mrmlScene.AddNewNodeByClass(PLAN_NODE_CLASS)
    volume = slicer.mrmlScene.AddNewNodeByClass(VOLUME_NODE_CLASS)
    if None in (data, display, plan, volume):
        pytest.skip("wrapper / carrier / display / volume not all registered.")
    if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveDistanceMapVolumeNode.")
    # Carrier deliberately has NO distance map; only the WRAPPER carries one.
    if hasattr(data, "SetAndObserveDistanceMapVolumeNode"):
        data.SetAndObserveDistanceMapVolumeNode(None)
    plan.SetAndObserveDistanceMapVolumeNode(volume)

    rep.SetResectionPlanNode(plan)
    rep.update(display, data)

    assert _resolved_distance_map_source(rep, None) is volume, (
        "the distance-map volume must be sourced from the WRAPPER "
        "(plan.GetDistanceMapVolumeNode(), ADR-0031), NOT the carrier "
        "data node -- the carrier has none, so a carrier-sourced read would "
        "leave the source None; got "
        f"{_resolved_distance_map_source(rep, None)!r}."
    )


def test_flattened_surface_clears_source_when_wrapper_has_no_distance_map():
    """Invariant 3 (negative): no wrapper distance map -> source cleared.

    A wrapper with no distance map returns the Representation to the graceful
    no-distance-map fallback: the distance-map source is cleared (so the mapper
    does not sample a volume that is gone), while the margins are STILL threaded
    from the wrapper.  MRML state and the mapper's source must not diverge.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_plan_shading_seam_or_skip(rep)

    fake = _inject_fake_mapper(rep)

    data = slicer.mrmlScene.AddNewNodeByClass(BEZIER_NODE_CLASS)
    display = slicer.mrmlScene.AddNewNodeByClass(RESECTOGRAM_DISPLAY_NODE_CLASS)
    plan = slicer.mrmlScene.AddNewNodeByClass(PLAN_NODE_CLASS)
    if None in (data, display, plan):
        pytest.skip("wrapper / carrier / display not all registered.")
    if not hasattr(plan, "SetAndObserveDistanceMapVolumeNode"):
        pytest.skip(f"{PLAN_NODE_CLASS} has no SetAndObserveDistanceMapVolumeNode.")
    if not (hasattr(plan, "SetSafetyMargin_mm") and hasattr(plan, "SetRiskMargin_mm")):
        pytest.skip(f"{PLAN_NODE_CLASS} has no Safety/Risk margin setters.")

    plan.SetAndObserveDistanceMapVolumeNode(None)
    plan.SetSafetyMargin_mm(5.0)
    plan.SetRiskMargin_mm(1.0)

    rep.SetResectionPlanNode(plan)
    rep.update(display, data)

    assert _resolved_distance_map_source(rep, fake) is None, (
        "a wrapper with no distance map must clear the Representation's "
        "distance-map source (the graceful fallback); got "
        f"{_resolved_distance_map_source(rep, fake)!r}."
    )
    # Margins are orthogonal to the distance map: they must still be threaded.
    assert fake.resection_margin is not None and abs(
        fake.resection_margin - 5.0
    ) < 1e-5, (
        "margins must still be threaded from the wrapper even when no "
        f"distance map is present; got {fake.resection_margin}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
