# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""The shared 3D control-point placement/edit base (ADR-0038).

ADR-0038 §Decision extracts a shared 3D interaction/visualization base from
the mature resection pipelines; VascularTerritories, resection and
LiverVolumetry become clients over the ``PointProvider`` seam.  The base owns
the GENERIC affordance and NOTHING data-model specific (ADR-0038 §"What is
not shared"):

* the add-on-click / drag-to-edit-nearest / delete / bare-move-decline
  arbitration (ADR-0033 hover discipline: a bare move returns
  ``(False, +inf)`` so the camera is untouched);
* the display-space pick-radius grab (``_nearest_key_in_display``, which
  defaults to the enumerate-keyed ``_nearest_point_in_display`` scan);
* the cursor-ray unproject for a drag target (``_event_world``);
* the point world for a CLICK comes from the injected **pick provider**
  (ADR-0038 §"Base extension" -- the base has NO surface-vs-volume branch);
* the arm gate rides the shared display node via ``PointPlacementState``.

The seed-glyph rendering, the hover marker + glow-halo overlay
(``vtkOutlineGlowPass``), the slice-jump, and the four LayerDM integration
invariants are the base's remaining generic surface; the concrete clients
subclass this base, keep their pinned interaction seams, and re-inject their
data-model + gating (resection's Init/Planning state machine, territories'
vessel gating) through their overrides -- none of which bleed into the base.

This is a LayerDM scripted Pipeline (imports LayerDMLib, reachable only
inside a launched Slicer with the module loaded); ADR-0004 keeps the
interaction math in Python; ADR-0013 §5 keeps it a Pipeline base, NOT a
displayable manager.
"""

from __future__ import annotations

import sys
from typing import Any

import vtk

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

try:  # pragma: no cover - exercised once per import path
    from .PointPlacementState import PointPlacementState
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

#: Display-space pick radius for grabbing an existing point, in pixels
#: (the shared value the resection + territory clients carried; a press
#: within this radius of a placed point grabs it, a press outside adds one).
POINT_PICK_RADIUS_PX = 20.0

#: Hover / grab cue colours shared across every control-point surface
#: (ADR-0038 §Context): hover = yellow, grab = green.
HALO_HOVER_COLOR = (1.0, 0.9, 0.2)
HALO_GRAB_COLOR = (0.3, 1.0, 0.4)


def _event_type(eventData: Any) -> int:  # noqa: N803 - VTK arg name
    """The VTK event-type id off ``eventData`` (never-raise boundaries only)."""
    return int(eventData.GetType())


class SurfacePointPlacementPipeline3D(_PipelineBase):
    """Generic 3D add-on-click / drag / delete over a ``PointProvider``.

    Concrete consumers subclass this and supply a ``PointProvider`` +
    a pick provider; the base carries no data-model knowledge (ADR-0038).
    """

    def __init__(self, namespace: str = "SurfacePointPlacement") -> None:
        super().__init__()
        self.SetPythonObject(self)

        self._display_node: Any | None = None
        self._renderer: Any | None = None
        self._state = PointPlacementState(namespace)

        # The consumer's data model + the swappable click->world pick.
        self._provider: Any | None = None
        self._pick_provider: Any | None = None

        # Instance-field fallbacks for the bare unit layer (no display node);
        # production reads arm / module-active off the shared display node.
        self._armed: bool = False
        self._module_active: bool = True

        # Key of the point currently GRABBED by a press/move/release drag,
        # None when no drag is in flight.
        self._drag_key: Any | None = None

    # ------------------------------------------------------------------ #
    # Seam wiring
    # ------------------------------------------------------------------ #

    def SetProvider(self, provider: Any) -> None:  # noqa: N802 - VTK verb
        """Inject the consumer's ``PointProvider`` (data model seam)."""
        self._provider = provider

    def GetProvider(self) -> Any | None:  # noqa: N802 - VTK verb
        return self._provider

    def SetPickProvider(self, pick: Any) -> None:  # noqa: N802 - VTK verb
        """Inject the swappable click->world pick (ADR-0038 §"Base extension")."""
        self._pick_provider = pick

    def _safe_get_renderer(self) -> Any | None:
        return self._renderer

    # ------------------------------------------------------------------ #
    # Arm / module-active gate (rides the shared display node)
    # ------------------------------------------------------------------ #

    def Arm(self) -> None:  # noqa: N802 - VTK verb
        """Enable add-on-click."""
        if self._display_node is not None:
            self._state.set_armed(self._display_node, True)
        self._armed = True

    def Disarm(self) -> None:  # noqa: N802 - VTK verb
        """Disable add-on-click; a click then adds nothing."""
        if self._display_node is not None:
            self._state.set_armed(self._display_node, False)
        self._armed = False

    def IsArmed(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return self._state.is_armed(self._display_node)
        return self._armed

    def SetModuleActive(self, active: bool) -> None:  # noqa: N802 - VTK verb
        """Open/close the belt-and-suspenders add-on-click gate."""
        if self._display_node is not None:
            self._state.set_module_active(self._display_node, bool(active))
        self._module_active = bool(active)

    def IsModuleActive(self) -> bool:  # noqa: N802 - VTK verb
        if self._display_node is not None:
            return self._state.is_module_active(self._display_node)
        return self._module_active

    # ------------------------------------------------------------------ #
    # Interaction -- add-on-click / drag-to-edit / decline (ADR-0033)
    # ------------------------------------------------------------------ #

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM focus logic.

        * a press within ``POINT_PICK_RADIUS_PX`` of an existing point is
          claimed with the REAL squared display distance (grab for a drag);
        * an armed press over a pick-resolvable point is claimed with the
          pick radius squared (add-on-click);
        * a grabbed move/release is claimed unconditionally;
        * a bare move is DECLINED (``(False, +inf)``) so the camera is
          untouched (ADR-0033); a client may raise a hover cue as a SIDE
          EFFECT of the declined bare move via ``_on_bare_move_decline``.

        The ``_admissible`` gate hook (default ``True``) lets a client veto
        the whole arbitration on its own data-model state -- resection's
        Init/Planning gate rides here (ADR-0038 §"What is not shared"), NOT
        as a branch in this base.
        """
        try:
            if not self._admissible():
                self._drag_key = None  # a state flip mid-gesture drops the grab
                return False, sys.float_info.max
            renderer = self._safe_get_renderer()
            if renderer is None:
                self._drag_key = None
                return False, sys.float_info.max
            etype = _event_type(eventData)

            if self._drag_key is not None:
                if etype in (
                    vtk.vtkCommand.MouseMoveEvent,
                    vtk.vtkCommand.LeftButtonReleaseEvent,
                ):
                    return True, 0.0
                return False, sys.float_info.max

            if etype == vtk.vtkCommand.MouseMoveEvent:
                # Bare hover: DECLINE (camera untouched, ADR-0033).  The
                # client's hover cue is a side effect of this declined call.
                self._on_bare_move_decline(renderer, eventData)
                return False, sys.float_info.max

            if etype != vtk.vtkCommand.LeftButtonPressEvent:
                return False, sys.float_info.max

            key, distance2 = self._nearest_key_in_display(renderer, eventData)
            if key is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                return True, distance2

            if not self.IsArmed():
                return False, sys.float_info.max
            if self._pick_world(renderer, eventData) is None:
                return False, sys.float_info.max
            return True, POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Drive add-on-click / drag-to-edit-nearest (ADR-0038 §Decision).

        The generic press-grab / move / release skeleton is here; each phase
        calls a client hook (``_on_grab`` / ``_on_drag`` / ``_on_release``,
        all no-ops by default) so a client contributes its data-model side
        effects -- the resection state-machine commit, the grab-colour
        scalars, the hover halo -- WITHOUT re-implementing the arbitration
        (ADR-0038 §"What is not shared").
        """
        try:
            renderer = self._safe_get_renderer()
            if renderer is None:
                self._drag_key = None
                return False
            if not self._admissible():
                self._drag_key = None
                return False
            etype = _event_type(eventData)

            if self._drag_key is None:
                if etype != vtk.vtkCommand.LeftButtonPressEvent:
                    return False
                key, distance2 = self._nearest_key_in_display(renderer, eventData)
                if key is not None and distance2 <= POINT_PICK_RADIUS_PX * POINT_PICK_RADIUS_PX:
                    self._drag_key = key  # grab for a drag (edit gesture)
                    self._on_grab(key, renderer, eventData)
                    self.RequestRender()
                    return True
                if not self.IsArmed():
                    return False
                if not self.IsModuleActive():
                    return False
                world = self._pick_world(renderer, eventData)
                if world is None:
                    return False
                self._add_point(world)
                self.RequestRender()
                return True

            if etype == vtk.vtkCommand.LeftButtonReleaseEvent:
                self._drag_key = None
                self._on_release()
                self.RequestRender()
                return False  # gesture over -- release the focus

            if etype == vtk.vtkCommand.MouseMoveEvent:
                world = self._event_world(renderer, eventData)
                if world is None:
                    return True  # keep the grab; this move just didn't resolve
                self._move_point(self._drag_key, world)
                self._on_drag(self._drag_key)
                self.RequestRender()
                return True

            return False
        except Exception:  # pragma: no cover - C++ boundary must never raise
            return False

    # ------------------------------------------------------------------ #
    # Client extension hooks (no data-model knowledge in the base;
    # ADR-0038 §"What is not shared").  All no-ops / permissive by default;
    # the flat clients (territories, volumetry) ignore them, resection
    # fills them with the state-machine commit + hover/grab cues.
    # ------------------------------------------------------------------ #

    def _admissible(self) -> bool:
        """Veto hook for a client's own gate (default: always admit).

        A client whose data model gates interaction (resection's
        Init/Planning state machine) overrides this; the base carries no
        such gate.
        """
        return True

    def _on_grab(self, key: Any, renderer: Any, eventData: Any) -> None:
        """Called right after the base grabs ``key`` on a press (default no-op)."""

    def _on_drag(self, key: Any) -> None:
        """Called right after a drag move relocates ``key`` (default no-op)."""

    def _on_release(self) -> None:
        """Called right after the base clears the grab on release (default no-op)."""

    def _on_bare_move_decline(self, renderer: Any, eventData: Any) -> None:
        """Called on a DECLINED bare move (default no-op -- the hover cue seam)."""

    def DeletePoint(self, key: Any) -> bool:  # noqa: N802 - VTK verb
        """Remove EXACTLY ONE point via the provider (delete write-back)."""
        provider = self._provider
        if provider is None:
            return False
        return bool(provider.delete_point(key))

    # ------------------------------------------------------------------ #
    # Provider write-backs
    # ------------------------------------------------------------------ #

    def _add_point(self, world: Any) -> None:
        if self._provider is not None:
            self._provider.add_point((world[0], world[1], world[2]))

    def _move_point(self, key: Any, world: Any) -> None:
        if self._provider is not None:
            self._provider.move_point(key, (world[0], world[1], world[2]))

    def _pick_world(self, renderer: Any, eventData: Any):
        """The click's world point from the injected pick, or ``None``.

        The single place the base resolves a click to a world position; the
        surface-vs-volume choice is entirely in the injected pick provider
        (ADR-0038 §"Base extension") -- the base does not branch on it.
        """
        pick = self._pick_provider
        if pick is None:
            return None
        return pick.pick_for_event(renderer, eventData)

    # ------------------------------------------------------------------ #
    # GL-touching seams (monkeypatched in the unit layer; overridden by the
    # concrete clients where their data model differs)
    # ------------------------------------------------------------------ #

    def _nearest_key_in_display(self, renderer: Any, eventData: Any):
        """``(key, distance2)`` of the point nearest the event pixel (grab seam).

        The single seam the arbitration bodies consult for the grab hit-test:
        it MUST return a 2-tuple ``(key, distance2)`` where ``key`` is the
        drag key the write-backs expect (``None`` when nothing is near).  The
        default delegates to ``_nearest_point_in_display`` (the enumerate-keyed
        scan below); a client whose key is not a flat index -- vascular
        territories' ``(territoryId, index)`` pair -- overrides THIS adapter
        and repacks its own richer hit-test into the 2-tuple contract, without
        touching the arbitration bodies (ADR-0038 §"What is not shared").
        """
        return self._nearest_point_in_display(renderer, eventData)

    def _nearest_point_in_display(self, renderer: Any, eventData: Any):
        """``(key, distance2)`` of the provider point nearest the event pixel.

        Scans ``iter_points`` projecting each to display and returns the
        nearest with its REAL squared display distance (LayerDM arbitration).
        ``(None, +inf)`` when there is no provider / point.
        """
        provider = self._provider
        if provider is None:
            return None, sys.float_info.max
        try:
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive (fake events)
            return None, sys.float_info.max

        best_key = None
        best_d2 = sys.float_info.max
        for key, (world, _rgb) in enumerate(provider.iter_points()):
            renderer.SetWorldPoint(world[0], world[1], world[2], 1.0)
            renderer.WorldToDisplay()
            dx, dy, _dz = renderer.GetDisplayPoint()
            d2 = (dx - ex) ** 2 + (dy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_key = key
        return best_key, best_d2

    def _event_world(self, renderer: Any, eventData: Any):
        """Back-project the event pixel to a world point for a drag target.

        The default unprojects at the near/far clip and returns the pick's
        surface snap; the concrete clients override where their drag target
        differs (resection back-projects onto the grabbed point's depth).
        """
        return self._pick_world(renderer, eventData)

    # ------------------------------------------------------------------ #
    # Reconcile (idempotent -- no drift on an unrelated Modified)
    # ------------------------------------------------------------------ #

    def _on_node_modified(self, caller: Any, event: str) -> None:
        """Repaint on a carrier ``Modified`` -- idempotent, no point drift.

        The base holds no shadow copy of the point set: the provider IS the
        source of truth, so a reconcile driven by an unrelated ``Modified``
        (a table repaint, a colour change) reads the provider and repaints
        without adding / moving / dropping any point (ADR-0038 no-drift).
        """
        del caller, event
        try:
            self.RequestRender()
        except Exception:  # pragma: no cover - C++ boundary must never raise
            pass
