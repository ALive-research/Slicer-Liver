# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Unit invariants for the vessel-adhering-highlight LayerDM Pipeline.

The Pipeline (``VascularTerritoriesLib.VesselHighlightPipeline``) paints a
marker glyph adhering to the input segmentation's closed-surface mesh
under the cursor, and hides it off-surface.  These tests pin the testable
seams; the actual GL glow / adherence appearance is eyeball-gated (a
launched, GL-real check), NOT covered here.

Pinned invariants:

* pick integration — given a stub renderer that unprojects to a known ray
  and an injected pick core over a known surface, the hover resolves the
  on-surface marker position and publishes it onto the display node
  (marker actor moves to the picked point, marker shown);
* off-surface hover — a miss (pick returns ``None``) hides the marker;
* hover discipline (ADR-0033) — ``CanProcessInteractionEvent`` DECLINES a
  bare mouse move (returns ``False``) so the camera is untouched, and its
  side effect is the only thing that moves the marker.

Import is guarded on ``LayerDMLib`` (reachable only from a launched Slicer
with the SlicerLayerDisplayableManager extension on the path); the tests
SKIP bare and RUN launched, mirroring the ControlPolygonPipeline unit
suite.  The display-node round-trip is pinned separately in the launched
MRML wrapper test.

References
----------
* ADR-0013 — LayerDM Pipeline pattern (one Pipeline per display-node type).
* ADR-0033 — hover discipline (claim as side effect, decline bare moves).
* ADR-0025 — the display-node / pick-core template.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

# The pick core is pure-VTK and importable bare; the Pipeline needs
# LayerDMLib.  Insert the Lib dir so the bare layer can at least reach the
# pick core to build a real surface for the injected core.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "VascularTerritories" / "VascularTerritoriesLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


def _import_pipeline():
    """Import the Pipeline class or SKIP when LayerDMLib is unreachable."""
    try:
        from VascularTerritoriesLib.VesselHighlightPipeline import (
            VesselHighlightPipeline,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VesselHighlightPipeline not importable ({exc!r}) -- LayerDMLib "
            "not reachable in this environment (bare unit layer)."
        )
    return VesselHighlightPipeline


def _import_pick():
    from VesselSurfacePick import VesselSurfacePick

    return VesselSurfacePick


# --------------------------------------------------------------------------- #
# Test doubles (no Slicer scene, no Qt, no GL)
# --------------------------------------------------------------------------- #


class _FakeDisplayNode:
    """Minimal stand-in for vtkMRMLTerritoriesHighlightDisplayNode.

    Carries the data-only fields the Pipeline reads/writes (no rendering
    logic, ADR-0013 §5) and a Modified no-op.
    """

    def __init__(self):
        self._point = [0.0, 0.0, 0.0]
        self._adhering = False
        self._radius = 3.0
        self._color = [1.0, 0.6, 0.1]
        self._visibility = True
        # The attribute channel the shared interaction state rides (arm /
        # module-active): the module-scoped overlay gate is read off it.
        self._attributes: dict = {}

    def GetAttribute(self, key):
        return self._attributes.get(key)

    def SetAttribute(self, key, value):
        self._attributes[key] = value

    def GetAdheringPointWorld(self):
        return list(self._point)

    def SetAdheringPointWorld(self, x, y, z):
        self._point = [x, y, z]

    def GetAdhering(self):
        return self._adhering

    def SetAdhering(self, value):
        self._adhering = bool(value)

    def GetRadius(self):
        return self._radius

    def GetColor(self):
        return list(self._color)

    def GetVisibility(self):
        return self._visibility

    def Modified(self):
        pass


class _FakeEvent:
    """A mouse-move event at a fixed display pixel."""

    def __init__(self, display_position=(100, 100), etype=None):
        self._pos = display_position
        self._type = etype if etype is not None else vtk.vtkCommand.MouseMoveEvent

    def GetDisplayPosition(self):
        return self._pos

    def GetType(self):
        return self._type


class _FakeRenderer:
    """A renderer whose DisplayToWorld unprojects to a fixed +z ray.

    Any display pixel at depth 0 maps to ``(0, 0, 5)`` and at depth 1 to
    ``(0, 0, -5)`` — the +z ray the pick-core sphere test uses, so the
    on-surface hit is the north pole ``(0, 0, 1)``.
    """

    def __init__(self):
        self._display = [0.0, 0.0, 0.0]

    def SetDisplayPoint(self, x, y, z):
        self._display = [x, y, z]

    def DisplayToWorld(self):
        pass

    def GetWorldPoint(self):
        if self._display[2] <= 0.0:
            return (0.0, 0.0, 5.0, 1.0)
        return (0.0, 0.0, -5.0, 1.0)


def _unit_sphere():
    source = vtk.vtkSphereSource()
    source.SetRadius(1.0)
    source.SetThetaResolution(64)
    source.SetPhiResolution(64)
    source.Update()
    return source.GetOutput()


def _wire_pipeline(pipeline, display, renderer, pick):
    """Attach the doubles onto the Pipeline via its unit seams.

    Also opens the module-scoped overlay gate on the display double: the gate
    is default-CLOSED and the widget's ``enter()`` owns it, so a Pipeline test
    with no widget has to say "the module is showing" itself -- otherwise the
    marker correctly never draws and every assertion here would be asserting
    the gate rather than the hover.
    """
    pipeline._display_node = display
    pipeline._renderer = renderer
    pipeline.SetPickCore(pick)
    from TerritoryInteractionState import set_overlays_enabled

    set_overlays_enabled(display, True)


# --------------------------------------------------------------------------- #
# Pick integration
# --------------------------------------------------------------------------- #


def test_hover_over_surface_positions_marker_on_the_mesh():
    """A hover whose ray hits the surface shows the marker AT the hit.

    The stub renderer unprojects to a +z ray through a unit sphere at the
    origin; the pick core returns the north pole ``(0, 0, 1)``.  The
    Pipeline publishes it (adhering=True) and the marker actor moves there.
    """
    VesselHighlightPipeline = _import_pipeline()
    VesselSurfacePick = _import_pick()

    pipeline = VesselHighlightPipeline()
    display = _FakeDisplayNode()
    _wire_pipeline(pipeline, display, _FakeRenderer(), VesselSurfacePick(_unit_sphere()))

    pipeline.CanProcessInteractionEvent(_FakeEvent())

    assert display.GetAdhering() is True
    assert list(display.GetAdheringPointWorld()) == pytest.approx(
        [0.0, 0.0, 1.0], abs=2e-2
    )
    # UpdatePipeline reflects the published state onto the marker actor.
    pipeline.UpdatePipeline()
    actor = pipeline.GetMarkerActor()
    assert actor.GetVisibility() == 1
    assert list(actor.GetPosition()) == pytest.approx([0.0, 0.0, 1.0], abs=2e-2)


def test_hover_off_surface_hides_the_marker():
    """A hover whose ray misses the surface hides the marker (no fallback).

    The pick core is built over an EMPTY polydata so the ray resolves to
    ``None``; the Pipeline publishes adhering=False and the marker hides.
    """
    VesselHighlightPipeline = _import_pipeline()
    VesselSurfacePick = _import_pick()

    pipeline = VesselHighlightPipeline()
    display = _FakeDisplayNode()
    display._adhering = True  # start shown to prove it gets hidden
    _wire_pipeline(
        pipeline, display, _FakeRenderer(), VesselSurfacePick(vtk.vtkPolyData())
    )

    pipeline.CanProcessInteractionEvent(_FakeEvent())

    assert display.GetAdhering() is False
    pipeline.UpdatePipeline()
    assert pipeline.GetMarkerActor().GetVisibility() == 0


# --------------------------------------------------------------------------- #
# Hover discipline (ADR-0033)
# --------------------------------------------------------------------------- #


def test_bare_move_is_declined_so_camera_is_untouched():
    """``CanProcessInteractionEvent`` DECLINES a bare move (ADR-0033).

    The marker update is a SIDE EFFECT; the return value must be
    ``(False, +inf)`` so LayerDM leaves the move to the camera.
    """
    VesselHighlightPipeline = _import_pipeline()
    VesselSurfacePick = _import_pick()

    pipeline = VesselHighlightPipeline()
    display = _FakeDisplayNode()
    _wire_pipeline(pipeline, display, _FakeRenderer(), VesselSurfacePick(_unit_sphere()))

    can, distance2 = pipeline.CanProcessInteractionEvent(_FakeEvent())

    assert can is False
    assert distance2 == sys.float_info.max
    # The side effect still fired (marker adheres) — decline != inert.
    assert display.GetAdhering() is True


def test_process_interaction_event_never_claims():
    """The highlight is a passive cue — ProcessInteractionEvent returns False."""
    VesselHighlightPipeline = _import_pipeline()

    pipeline = VesselHighlightPipeline()
    assert pipeline.ProcessInteractionEvent(_FakeEvent()) is False


def test_an_inactive_module_neither_hovers_nor_shows_the_marker():
    """The module-scoped overlay rule reaches the vessel hover marker.

    ``territory-usability`` display lifecycle: while VascularTerritories is not
    the active module, a hover must publish nothing (no surface pick, no MRML
    write) and an already-raised marker must retire -- nothing this module draws
    survives the switch.  Re-opening the gate restores the hover cue.

    The gate is the module-scoped OVERLAY flag, which is a separate channel
    from the placement gate (``set_module_active``): drawing is default-off
    until an ``enter()`` opens it, while placement stays optimistically open
    for the window before the owning widget's first ``enter()``.
    """
    VesselHighlightPipeline = _import_pipeline()
    VesselSurfacePick = _import_pick()
    from TerritoryInteractionState import set_overlays_enabled

    pipeline = VesselHighlightPipeline()
    display = _FakeDisplayNode()
    _wire_pipeline(pipeline, display, _FakeRenderer(), VesselSurfacePick(_unit_sphere()))

    pipeline.CanProcessInteractionEvent(_FakeEvent())
    pipeline.UpdatePipeline()
    assert pipeline.GetMarkerActor().GetVisibility() == 1  # precondition

    set_overlays_enabled(display, False)
    pipeline.UpdatePipeline()
    assert pipeline.GetMarkerActor().GetVisibility() == 0, (
        "an inactive module must show no vessel hover marker."
    )

    display.SetAdhering(False)
    pipeline.CanProcessInteractionEvent(_FakeEvent())
    assert display.GetAdhering() is False, (
        "an inactive module must not even publish a hover (no pick, no write)."
    )

    set_overlays_enabled(display, True)
    pipeline.CanProcessInteractionEvent(_FakeEvent())
    pipeline.UpdatePipeline()
    assert pipeline.GetMarkerActor().GetVisibility() == 1, (
        "re-entering the module restores the hover cue."
    )


def test_no_renderer_declines_without_touching_state():
    """With no renderer attached the hover declines and publishes nothing."""
    VesselHighlightPipeline = _import_pipeline()

    pipeline = VesselHighlightPipeline()
    display = _FakeDisplayNode()
    pipeline._display_node = display
    pipeline._renderer = None

    can, distance2 = pipeline.CanProcessInteractionEvent(_FakeEvent())

    assert can is False
    assert distance2 == sys.float_info.max
    assert display.GetAdhering() is False
