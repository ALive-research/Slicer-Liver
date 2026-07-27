# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 -- the shared 3D control-point placement/edit base (interaction seam).

ADR-0038 §Decision extracts a shared ``SurfacePointPlacementPipeline3D``
base from the mature resection pipelines; VascularTerritories, resection,
and (this branch) LiverVolumetry become clients over a small
``PointProvider`` seam.  The base owns the add-on-click / drag-to-edit /
delete / bare-move-decline arbitration, the display-space pick-radius
grab, and the four LayerDM integration invariants; the consumer supplies
the points, the edges flag, the drag/delete write-backs, the display-node
channel, AND -- per the ADR's implementation amendment (2026-07-27) -- a
SWAPPABLE PICK PROVIDER.

This file pins the 3D base's interaction contract against a FAKE FLAT
``PointProvider`` (no edges, no vessel gating, no data-model knowledge):

* add-on-click adds EXACTLY ONE point (ADR-0038 §Decision / ADR-0037
  §Decision 2 mirror);
* a drag edits the NEAREST existing point (ADR-0033 grab seam);
* delete removes EXACTLY ONE point;
* a bare move is DECLINED -- ``(False, +inf)`` -- so the camera is
  untouched (ADR-0033 hover discipline);
* an unrelated ``Modified`` causes NO drift;

and the KEY ADR-0038-amendment invariant:

* the base has NO surface-vs-volume branch.  The pick (world position for a
  click) is obtained from the INJECTED pick provider; the base places at
  whatever world point the provider returns.  This is the seam that lets
  volumetry inject an in-volume pick while territories inject SurfacePick,
  with the base unchanged (ADR-0038 §"Base extension: the pick step is
  swappable").

The base leaking a consumer concern is the highest-risk failure mode
(``volumetry-seeds-layerdm-plan.md`` §8): the FAKE provider here has no
vessel/volume concept, so if the base needs one, the seam is wrong.

HARNESS: launched Slicer.  The base is a LayerDM scripted Pipeline
importing LayerDMLib (reachable only inside a launched Slicer with the
module loaded); a bare ``PythonSlicer -m pytest`` has LayerDMLib off the
path, so every test SKIPS CLEANLY via the ``slicer_pytest_support``
guards.  The provider is a Python fake, so no carrier node is needed and
these are launched-scene-light (they do NOT need a wrapped C++ carrier --
only the LayerDMLib-importable base).

The SUT does not exist yet.  Per ADR-0027 red->skip the import + hasattr
guards skip-pend; the skips lift at the extraction commit.  Under a
launched Slicer verify run-vs-skip in the CI log -- never trust overall
green (the launched harness is green-but-skipping prone).

References
----------
* ADR-0038 -- §Decision (the seam-parameterized base) + §"Base extension"
  (the swappable pick provider; the base has no surface-vs-volume branch).
* ADR-0033 -- the grab seam + hover-decline discipline.
* ADR-0032 -- interaction through the LayerDM Pipeline seam.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/Testing/Python/test_territories_placement_pipeline.py
  -- the client suite this base's behaviour was extracted to satisfy.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Skip-guards (mirror the launched-Slicer discipline in the VascTerr conftest)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_base_or_skip():
    """Import the shared 3D base or skip-pend (ADR-0027).

    PROPOSED seam (sharpen at landing).  The base mirrors
    ``ControlPolygonPipeline`` (the resection origin) and exposes the same
    interaction verbs the territory client test drives::

        class SurfacePointPlacementPipeline3D(<LayerDM Pipeline base>):
            def SetProvider(self, provider: PointProvider) -> None: ...
            def SetPickProvider(self, pick) -> None: ...  # swappable pick
            def Arm(self) -> None / def Disarm(self) -> None: ...
            def CanProcessInteractionEvent(self, eventData) -> (bool, float): ...
            def ProcessInteractionEvent(self, eventData) -> bool: ...
    """
    try:
        from SurfacePointPlacementPipeline3D import (
            SurfacePointPlacementPipeline3D,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"SurfacePointPlacementPipeline3D not importable ({exc!r}) -- the "
            "ADR-0038 3D base has not landed OR LayerDMLib is not reachable "
            "here.  The skip lifts at the extraction commit (ADR-0027)."
        )
    return SurfacePointPlacementPipeline3D


# --------------------------------------------------------------------------- #
# A FAKE FLAT PointProvider -- no edges, no vessel/volume concept
# --------------------------------------------------------------------------- #


class _FakeFlatProvider:
    """A flat, data-model-free ``PointProvider`` (ADR-0038 §Decision seam).

    Holds an ordered list of ``(world, base_rgb)`` points in plain Python;
    ``has_edges()`` is False (territories/volumetry, not the resection
    grid); the write-backs mutate the list in place.  It has NO surface, NO
    vessel gating, NO volume -- the base must not need any of them (the §8
    leak guard).
    """

    def __init__(self):
        self._points: list[list[float]] = []
        self.base_rgb = (0.2, 0.8, 0.2)

    # -- seam the base READS --
    def iter_points(self):
        for p in self._points:
            yield (tuple(p), self.base_rgb)

    def has_edges(self) -> bool:
        return False

    def count(self) -> int:
        return len(self._points)

    def get(self, i):
        return tuple(self._points[i])

    # -- seam the base WRITES (drag / delete / add) --
    def add_point(self, world) -> int:
        self._points.append([world[0], world[1], world[2]])
        return len(self._points) - 1

    def move_point(self, key, world) -> None:
        self._points[key] = [world[0], world[1], world[2]]

    def delete_point(self, key) -> bool:
        del self._points[key]
        return True


class _FakePick:
    """A pick provider that returns a FIXED world point (no surface at all).

    The base must place at whatever world point the pick returns -- there is
    no surface here, no ray math, no volume.  This is the ADR-0038-amendment
    contract: the pick is a seam, the base has no surface-vs-volume branch.
    """

    def __init__(self, world):
        self._world = world

    def pick_for_event(self, renderer, eventData):
        return self._world


class _FakeRenderer:
    """A do-nothing renderer stand-in (the base must not depend on GL here)."""


class _Event:
    """A minimal interaction event at a fixed display pixel + type."""

    def __init__(self, etype, display_position=(100, 100)):
        self._etype = etype
        self._pos = display_position

    def GetType(self):  # noqa: N802 - VTK verb
        return self._etype

    def GetDisplayPosition(self):  # noqa: N802 - VTK verb
        return self._pos


def _wire_or_skip(pipeline, provider, pick, monkeypatch):
    """Attach the fake provider + pick + renderer, or skip-pend the seam."""
    for method in ("SetProvider", "SetPickProvider"):
        if not hasattr(pipeline, method):
            pytest.skip(
                f"SurfacePointPlacementPipeline3D has no {method} injection "
                "seam -- the ADR-0038 PointProvider / swappable-pick seam has "
                "not landed (ADR-0027)."
            )
    monkeypatch.setattr(pipeline, "_safe_get_renderer", lambda: _FakeRenderer())
    pipeline.SetProvider(provider)
    pipeline.SetPickProvider(pick)
    if hasattr(pipeline, "Arm"):
        pipeline.Arm()


# --------------------------------------------------------------------------- #
# add-on-click / bare-move-decline
# --------------------------------------------------------------------------- #


def test_click_adds_exactly_one_point_at_the_provider_pick(monkeypatch):
    """A click adds EXACTLY ONE point at the world the PICK PROVIDER returns.

    ADR-0038 §Decision (add-on-click) + §"Base extension": the base does
    NOT compute a surface point -- it places at the injected pick's world.
    Here the fake pick returns ``(7, 8, 9)`` (a point on NO surface); the
    base must place THAT.
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()
    pipeline = Base()
    provider = _FakeFlatProvider()
    pick = _FakePick((7.0, 8.0, 9.0))
    _wire_or_skip(pipeline, provider, pick, monkeypatch)

    before = provider.count()
    click = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    assert pipeline.CanProcessInteractionEvent(click)[0] is True, (
        "an armed click must be CLAIMED (add-on-click)."
    )
    assert pipeline.ProcessInteractionEvent(click) is True

    assert provider.count() == before + 1, "a click must add EXACTLY ONE point."
    assert provider.get(provider.count() - 1) == pytest.approx(
        (7.0, 8.0, 9.0), abs=1e-9
    ), "the base must place at the PICK PROVIDER's world point verbatim."


def test_no_surface_vs_volume_branch_in_the_base(monkeypatch):
    """The base has NO surface-vs-volume branch -- the pick is the ONLY source.

    ADR-0038 §"Base extension: the pick step is swappable".  Two DIFFERENT
    picks (one an arbitrary off-surface point, one an arbitrary interior
    point) must both be placed verbatim by the SAME base with NO branching
    on what kind of point it is.  If the base inspected a surface or a
    volume, one of these would be rejected / snapped -- the seam would be
    wrong (the §8 leak guard).
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()

    for world in ((123.0, -45.0, 6.0), (-1.0, -1.0, -1.0)):
        pipeline = Base()
        provider = _FakeFlatProvider()
        _wire_or_skip(pipeline, provider, _FakePick(world), monkeypatch)
        assert pipeline.ProcessInteractionEvent(
            _Event(vtk.vtkCommand.LeftButtonPressEvent)
        ) is True
        assert provider.count() == 1
        assert provider.get(0) == pytest.approx(world, abs=1e-9), (
            "the base must place at the injected pick's world with NO "
            "surface/volume branching (ADR-0038 §'Base extension')."
        )


def test_bare_move_is_declined_and_adds_nothing(monkeypatch):
    """A bare move is DECLINED and adds NO point (ADR-0033 hover discipline).

    ``CanProcessInteractionEvent`` on a bare mouse move returns
    ``(False, +inf)`` so LayerDM leaves the move to the camera; no provider
    mutation.  ADR-0038 §Decision (the grab seam owns the hover decline).
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()
    pipeline = Base()
    provider = _FakeFlatProvider()
    _wire_or_skip(pipeline, provider, _FakePick((0.0, 0.0, 1.0)), monkeypatch)

    before = provider.count()
    move = _Event(vtk.vtkCommand.MouseMoveEvent)
    can, distance2 = pipeline.CanProcessInteractionEvent(move)

    assert can is False, "a bare move must be DECLINED (camera untouched, ADR-0033)."
    assert distance2 == sys.float_info.max
    assert provider.count() == before, "a bare move must add NO point."


# --------------------------------------------------------------------------- #
# drag-to-edit-nearest / delete / no-drift
# --------------------------------------------------------------------------- #


def test_drag_edits_exactly_the_nearest_point(monkeypatch):
    """A drag mutates EXACTLY ONE point -- the nearest to the grab.

    With two points placed, a press grabs the nearest and the drag relocates
    only THAT point; the sibling is unchanged and the count is unchanged
    (ADR-0038 §Decision, ADR-0033 grab seam).  The nearest-selection + drag
    target are injected so the test stays GL-free.
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()
    pipeline = Base()
    provider = _FakeFlatProvider()
    _wire_or_skip(pipeline, provider, _FakePick((0.0, 0.0, 1.0)), monkeypatch)

    provider.add_point((0.0, 0.0, 1.0))
    provider.add_point((1.0, 0.0, 0.0))
    for seam in ("_nearest_point_in_display", "_event_world"):
        if not hasattr(pipeline, seam):
            pytest.skip(
                f"SurfacePointPlacementPipeline3D has no {seam} seam -- cannot "
                "pin nearest-selection / drag target (ADR-0027)."
            )
    # Grab resolves to point index 1 at a real squared display distance; the
    # drag relocates it to a fixed world point.
    monkeypatch.setattr(pipeline, "_nearest_point_in_display", lambda r, e: (1, 9.0))
    monkeypatch.setattr(pipeline, "_event_world", lambda r, e: (0.0, 1.0, 0.0))

    before0 = provider.get(0)
    before_count = provider.count()

    press = _Event(vtk.vtkCommand.LeftButtonPressEvent)
    can, d2 = pipeline.CanProcessInteractionEvent(press)
    assert can is True and d2 == pytest.approx(9.0), (
        "a press near a point must be claimed with the REAL squared display "
        "distance (LayerDM arbitration)."
    )
    assert pipeline.ProcessInteractionEvent(press) is True
    assert pipeline.ProcessInteractionEvent(_Event(vtk.vtkCommand.MouseMoveEvent)) is True

    assert provider.count() == before_count, "a drag must NOT add or remove points."
    assert provider.get(1) == pytest.approx((0.0, 1.0, 0.0), abs=1e-6), (
        "the drag must relocate the GRABBED (nearest) point."
    )
    assert provider.get(0) == pytest.approx(before0, abs=1e-9), (
        "the drag must NOT move the un-grabbed sibling."
    )


def test_delete_removes_exactly_one_point(monkeypatch):
    """A delete removes EXACTLY ONE point (the targeted one).

    ADR-0038 §Decision (delete write-back on the seam).  With three points,
    deleting the middle one leaves two and the tail shifts up in order.
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()
    pipeline = Base()
    provider = _FakeFlatProvider()
    _wire_or_skip(pipeline, provider, _FakePick((0.0, 0.0, 1.0)), monkeypatch)

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for p in pts:
        provider.add_point(p)

    if not hasattr(pipeline, "DeletePoint"):
        pytest.skip(
            "SurfacePointPlacementPipeline3D has no DeletePoint seam -- the "
            "delete write-back has not landed (ADR-0027)."
        )
    assert pipeline.DeletePoint(1) is True

    assert provider.count() == len(pts) - 1, "delete must remove EXACTLY ONE."
    assert provider.get(0) == pytest.approx(pts[0], abs=1e-6)
    assert provider.get(1) == pytest.approx(pts[2], abs=1e-6), (
        "after deleting the middle point, the tail must shift up in order."
    )


def test_unrelated_modified_causes_no_point_drift(monkeypatch):
    """An unrelated ``Modified`` does not add / move / drop any point.

    A carrier ``Modified`` raised for a reason OTHER than a placement
    gesture (a table repaint, a colour change, another view) must leave the
    point set byte-identical -- the reconcile is idempotent on non-geometry
    Modifieds (ADR-0038 §Decision / ADR-0037 no-drift mirror).
    """
    _slicer_or_skip()
    Base = _import_base_or_skip()
    pipeline = Base()
    provider = _FakeFlatProvider()
    _wire_or_skip(pipeline, provider, _FakePick((0.0, 0.0, 1.0)), monkeypatch)

    for p in ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)):
        provider.add_point(p)

    if not hasattr(pipeline, "_on_node_modified"):
        pytest.skip(
            "SurfacePointPlacementPipeline3D has no _on_node_modified reconcile "
            "hook -- cannot pin no-drift (ADR-0027)."
        )

    before = [provider.get(i) for i in range(provider.count())]
    pipeline._on_node_modified(None, None)
    pipeline._on_node_modified(None, None)

    assert provider.count() == len(before), "an unrelated Modified must not add/drop."
    for i, expected in enumerate(before):
        assert provider.get(i) == pytest.approx(expected, abs=1e-9), (
            f"point {i} must not drift on an unrelated Modified."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
