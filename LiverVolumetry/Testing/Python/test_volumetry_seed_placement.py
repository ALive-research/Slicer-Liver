# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- volumetry seed placement via the shared base + provider.

The volumetry client wires the shared ``SurfacePointPlacementPipeline3D``
base (SlicerLiverInteractionLib) to a volumetry ``PointProvider`` adapter
over ``vtkMRMLVolumetrySeedsNode`` and the in-volume pick
(``volumetry-seeds-layerdm-plan.md`` §3b).  This file pins the integrated
placement lifecycle -- the same add-on-click / drag-nearest / delete-one
contract the base owns, but driven through the VOLUMETRY provider + the
IN-VOLUME pick (not a surface snap):

* an armed click adds EXACTLY ONE interior seed to the carrier;
* a drag edits the NEAREST existing seed;
* delete removes EXACTLY ONE seed;
* the arm / carrier state rides the SHARED display node, not the pipeline
  instance (``feedback_layerdm_state_on_display_node``).

The base's own interaction arbitration is pinned generically in
``SlicerLiverInteractionLib/Testing/Python/test_point_placement_pipeline_3d.py``
against a fake provider; THIS file pins that the VOLUMETRY wiring (real
carrier + in-volume pick + display-node routing) lands one interior seed.

HARNESS: launched Slicer.  Needs LayerDMLib (the base), the wrapped
``vtkMRMLVolumetrySeedsNode`` carrier + display node, and a labelmap for
the in-volume pick -- all reachable only inside a launched Slicer with the
module loaded.  A bare ``PythonSlicer -m pytest`` SKIPS CLEANLY.

The SUT does not exist yet.  Per ADR-0027 red->skip the import + guards
skip-pend; the skips lift at the implementation commit.  Under a launched
Slicer verify run-vs-skip in the CI log -- never trust overall green.

References
----------
* ADR-0038 -- §Decision (the seam) + §"Base extension" (in-volume pick) +
  §"Consumers ledger" (LiverVolumetry client).
* ADR-0013 §5 -- the Pipeline creator wiring (no custom DM), pinned by
  test_volumetry_registration_smoke.py.
* ADR-0033 -- the grab seam + hover discipline the base enforces.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "SlicerLiverInteractionLib",
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_base_or_skip():
    try:
        from SurfacePointPlacementPipeline3D import (
            SurfacePointPlacementPipeline3D,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"SurfacePointPlacementPipeline3D not importable ({exc!r}) -- the "
            "ADR-0038 base has not landed OR LayerDMLib is not reachable "
            "(ADR-0027)."
        )
    return SurfacePointPlacementPipeline3D


def _import_provider_or_skip():
    """Import the volumetry PointProvider adapter, or skip-pend (ADR-0027).

    PROPOSED seam: a ``VolumetrySeedProvider`` over
    ``vtkMRMLVolumetrySeedsNode`` implementing the ADR-0038 PointProvider
    (``iter_points`` / ``has_edges`` -> False / add / move / delete /
    display_node) + the in-volume pick.  Adjust the imported name at landing.
    """
    try:
        from VolumetrySeedProvider import VolumetrySeedProvider
    except ImportError:
        pytest.skip(
            "VolumetrySeedProvider not importable -- the volumetry PointProvider "
            "adapter (plan §3b) has not landed (ADR-0027)."
        )
    return VolumetrySeedProvider


def _carrier_or_skip(slicer):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "PlacementSeeds")
    if node is None or not hasattr(node, "AddSeed"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} / AddSeed not available -- the seed carrier "
            "has not landed (ADR-0027)."
        )
    return node


def _display_or_skip(slicer):
    node = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "PlacementDisplay")
    if node is None:
        pytest.skip(f"{DISPLAY_NODE_CLASS} not registered (ADR-0027).")
    # The overlay gate is default-CLOSED and opened by the module's enter()
    # (PointPlacementState.set_overlays_visible).  A Pipeline test mints its own
    # display node and has no widget, so it models a SHOWING module explicitly.
    from slicer_pytest_support import open_module_overlay_gate

    open_module_overlay_gate(node, "LiverVolumetry")
    return node


class _FakePick:
    """A pick returning a FIXED interior world point (in-volume seed).

    The volumetry pick's own contract (a labelled interior voxel) is pinned
    in test_volumetry_in_volume_pick.py; here it is a fixed double so the
    placement wiring is isolated from the pick math.
    """

    def __init__(self, world=(5.0, 10.0, 10.0)):
        self._world = world

    def pick_for_event(self, renderer, eventData):
        return self._world


class _FakeRenderer:
    pass


class _Event:
    def __init__(self, etype, display_position=(100, 100)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def _wire_or_skip(slicer, pipeline, carrier, displayNode, monkeypatch):
    VolumetrySeedProvider = _import_provider_or_skip()
    for method in ("SetProvider", "SetPickProvider", "SetDisplayNode"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"SurfacePointPlacementPipeline3D has no {method} seam (ADR-0027)."
            )
    from PointPlacementState import PointPlacementState  # noqa: F401  (import guard below)

    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    provider = VolumetrySeedProvider(carrier)
    # The arm/carrier state MUST ride the shared display node, not the
    # pipeline instance (feedback_layerdm_state_on_display_node).
    if hasattr(provider, "SetDisplayNode"):
        provider.SetDisplayNode(displayNode)
    pipeline.SetDisplayNode(displayNode)
    pipeline.SetProvider(provider)
    pipeline.SetPickProvider(_FakePick())
    if hasattr(pipeline, "Arm"):
        pipeline.Arm()
    return provider


def test_armed_click_adds_one_interior_seed(monkeypatch):
    """An armed click adds EXACTLY ONE interior seed to the carrier.

    ADR-0038 §Decision (add-on-click) through the volumetry provider + the
    in-volume pick; the seed lands at the pick's interior world point.
    """
    slicer = _slicer_or_skip()
    Base = _import_base_or_skip()
    carrier = _carrier_or_skip(slicer)
    displayNode = _display_or_skip(slicer)
    pipeline = Base()
    _wire_or_skip(slicer, pipeline, carrier, displayNode, monkeypatch)

    before = carrier.GetNumberOfSeeds()
    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    assert pipeline.CanProcessInteractionEvent(click)[0] is True
    assert pipeline.ProcessInteractionEvent(click) is True

    assert carrier.GetNumberOfSeeds() == before + 1, (
        "an armed click must add EXACTLY ONE interior seed."
    )


def test_drag_edits_nearest_seed(monkeypatch):
    """A drag edits the NEAREST existing seed, leaving the count unchanged."""
    slicer = _slicer_or_skip()
    Base = _import_base_or_skip()
    carrier = _carrier_or_skip(slicer)
    displayNode = _display_or_skip(slicer)
    pipeline = Base()
    _wire_or_skip(slicer, pipeline, carrier, displayNode, monkeypatch)

    carrier.AddSeed(5.0, 10.0, 10.0)
    carrier.AddSeed(15.0, 10.0, 10.0)
    for seam in ("_nearest_point_in_display", "_event_world"):
        if not hasattr(pipeline, seam):
            pytest.skip(f"base has no {seam} seam (ADR-0027).")
    monkeypatch.setattr(pipeline, "_nearest_point_in_display", lambda r, e: (1, 4.0))
    monkeypatch.setattr(pipeline, "_event_world", lambda r, e: (14.0, 11.0, 10.0))

    before_count = carrier.GetNumberOfSeeds()
    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.LeftButtonPressEvent)) is True
    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.MouseMoveEvent)) is True

    assert carrier.GetNumberOfSeeds() == before_count, "a drag must not add/remove."
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx((14.0, 11.0, 10.0), abs=1e-6), (
        "the drag must relocate the GRABBED (nearest) seed."
    )


def test_delete_removes_one_seed(monkeypatch):
    """Delete removes EXACTLY ONE seed."""
    slicer = _slicer_or_skip()
    Base = _import_base_or_skip()
    carrier = _carrier_or_skip(slicer)
    displayNode = _display_or_skip(slicer)
    pipeline = Base()
    _wire_or_skip(slicer, pipeline, carrier, displayNode, monkeypatch)

    carrier.AddSeed(5.0, 10.0, 10.0)
    carrier.AddSeed(15.0, 10.0, 10.0)
    if not hasattr(pipeline, "DeletePoint"):
        pytest.skip("base has no DeletePoint seam (ADR-0027).")

    before = carrier.GetNumberOfSeeds()
    assert pipeline.DeletePoint(0) is True
    assert carrier.GetNumberOfSeeds() == before - 1, "delete must remove EXACTLY ONE."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
