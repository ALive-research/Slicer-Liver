# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""LayerDM Pipeline for the resectogram concept.

The resectogram is the flattened 2D image of the Bezier ``(u, v)``
parameter domain (`ADR-0025`_ §Context).  Per `ADR-0013`_ §1 there is
exactly ONE Pipeline per display-node TYPE: the 3D Bezier-surface
Pipeline already owns ``vtkMRMLParametricSurfaceDisplayNode``, so the
resectogram gets its own dedicated ``vtkMRMLResectogramDisplayNode``
and the ``ResectogramPipeline`` is keyed on THAT type.  Keying a second
Pipeline on the shared parametric-surface display node would violate
§1; the dedicated display node is the maintainer's resolution of that
fork.

This Pipeline is the v2.0 LayerDM-bound home of the resectogram render
path that the v1 monolith ``vtkSlicerBezierSurfaceRepresentation3D``
currently drives.  It composes two Representations (`ADR-0013`_ §6):

* ``FlattenedSurfaceRepresentation`` — the flattened-quad source, the
  2D resection mapper + actor, the private overlay camera, the
  distance-map texture binding, and the anisotropic ``MatRatio``
  scaling routed through the ``vtkLiverResectogramAspectRatio`` /
  ``vtkLiverResectogramPixelMapping`` Algorithm helpers (`ADR-0015`_
  §1) — no re-derivation of the v1 math.
* ``VascularContourRepresentation`` — the distance- and
  slicing-contour overlays the surgeon reads vessel proximity from.

Unlike the Bezier Pipeline there is no ``(state, initMode)`` dispatch:
the resectogram is a single composite render path.  ``UpdatePipeline()``
forwards the current display + data nodes to BOTH Representations and
short-circuits when nothing has changed (`ADR-0013`_ §3 idempotency
contract).

Pipeline base class
-------------------
`ADR-0013`_ §5 names ``vtkMRMLLayerDMScriptedPipeline`` (imported as
``from LayerDMLib import vtkMRMLLayerDMScriptedPipeline``) as the
canonical base.  This module ``pytest.importorskip("LayerDMLib")`` at
import time — it executes only inside a Slicer process where LayerDMLib
is importable (the launched-harness path, gated on issue #460 for CI).

Lifecycle (LayerDM-managed)
---------------------------
Mirrors the Bezier Pipeline lifecycle (`ADR-0013`_ §5): no-arg
``__init__``; ``SetViewNode`` / ``SetDisplayNode`` assigned by the
manager; ``UpdatePipeline()`` reconciles the Representations;
``OnRendererAdded`` builds the Representations once a renderer is
available; ``OnRendererRemoved`` / ``cleanup`` tear them down.

Pipeline-creator registration
-----------------------------
``registerResectogramPipelineCreator()`` (module bottom) performs
`ADR-0013`_ §5 call 3 — ``vtkMRMLLayerDMPipelineFactory::GetInstance()
->AddPipelineCreator(...)`` keyed on ``vtkMRMLResectogramDisplayNode``.
``qSlicerLiverResectionsModule::setup()`` delegates to it via the
loadable module's ``pythonManager()->executeString(...)``, alongside
the Bezier creator's ``registerPipelineCreator()``.

References
----------
* `ADR-0013`_ §1, §3, §5, §6 — Pipeline pattern, idempotency, the three
  registration calls, Representations as composable VTK pipelines.
* `ADR-0015`_ §1 — Algorithm-library pure-VTK helpers.
* `ADR-0025`_ §Context — the resectogram as a 1:1 image of the Bezier
  ``(u, v)`` parameter domain.

.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0015: ../../Docs/adr/0015-cpp-algorithm-library.md
.. _ADR-0025: ../../Docs/adr/0025-locator-architecture.md
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Pipeline base — hard-required on the upstream LayerDM library per ADR-0013
# §5.  Importable from any Slicer process that loaded the
# SlicerLayerDisplayableManager extension.  Tests that exercise this module
# outside Slicer ``pytest.importorskip("LayerDMLib")`` at module level.
# --------------------------------------------------------------------------- #

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase


class ResectogramPipeline(_PipelineBase):
    """Composite Pipeline for the resectogram concept.

    Constructed by LayerDM's ``vtkMRMLLayerDMPipelineManager`` via the
    creator registered by ``registerResectogramPipelineCreator()`` at
    module bottom.  No-arg constructor per the LayerDM contract.

    Owns two Representations (the flattened surface + the vascular
    contours).  ``UpdatePipeline()`` forwards the current display + data
    nodes to both and is idempotent: it records the
    ``(dataMTime, displayMTime)`` tuple it last ran against and
    short-circuits when nothing has changed.
    """

    def __init__(self) -> None:
        super().__init__()

        # Node handles — populated when the manager calls the setters.
        # ``SetDisplayNode`` derives ``_data_node`` from the display
        # node's ``GetDisplayableNode()`` back-reference.
        self._data_node: Any | None = None
        self._display_node: Any | None = None

        # Observer tags so ``cleanup()`` can detach precisely.  Index by
        # ``id(node)`` because ``vtkObject`` subclasses are not
        # universally hashable on identity.
        self._observer_tags: dict[int, list[int]] = {}
        self._observed_node_refs: list[Any] = []

        # Memoised dispatch input — see ``UpdatePipeline``.
        self._last_update_key: tuple | None = None

        # Counter workflow tests assert idempotency against: advances
        # only on real reconciliation work, not on short-circuits.
        self._update_count: int = 0

        # Composed Representations.  Built lazily by
        # ``_ensure_representations()`` once a renderer is available.
        self._flattened_surface: Any | None = None
        self._vascular_contour: Any | None = None
        self._representations_initialised = False

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle overrides
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        """Attach the display node, derive the data node, wire observers.

        Per `ADR-0013`_ §5 the manager calls this once after creating
        the Pipeline.  Re-entrant: replacing an already-attached display
        node detaches the old observers and re-derives the data node.
        """
        super().SetDisplayNode(displayNode)

        self._display_node = displayNode
        self._reattach_node_observers()

        self._last_update_key = None

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """Reconcile both Representations against the current node set.

        Idempotent: a second call with no intervening control-point mutation
        is a no-op observationally — the memoised key short-circuits the work
        (`ADR-0013`_ §3).

        The key is the data node's control-point GEOMETRY digest ALONE.  It
        deliberately does NOT fold in ``GetMTime`` of the data or display node:
        a maximize binds the resectogram view node to two live qMRMLThreeDViews
        whose renders re-``Modified()`` the surface AND the resectogram display
        node every frame, advancing those MTimes WITHOUT any geometry change.
        Keying on them would make every render-churned MTime a fresh key →
        re-feed + RequestRender on every render → the maximize render storm
        (continuous ~47 renders/s).  A control-point DRAG changes the geometry
        digest (so edit-reactivity is preserved), but render-induced MTime
        churn at fixed geometry leaves the digest unchanged → short-circuit →
        the loop is broken.  A markups control-point DRAG also advances only
        the control-point structure, not the node ``GetMTime``, so the digest
        is the correct reactivity signal on both counts.
        """
        self._ensure_representations()

        key = _safe_get_control_points_digest(self._data_node)
        if key == self._last_update_key:
            return  # idempotent short-circuit
        self._last_update_key = key

        if self._flattened_surface is not None:
            self._flattened_surface.update(self._display_node, self._data_node)
        if self._vascular_contour is not None:
            self._vascular_contour.update(self._display_node, self._data_node)

        self._update_count += 1

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        """Build Representations once a renderer is attached.

        Per `ADR-0013`_ §5 the renderer is supplied by the manager; the
        Pipeline cannot construct its actor-bearing Representations until
        ``GetRenderer()`` returns a non-None value.
        """
        del renderer  # accessed via self.GetRenderer() inside the helper
        self._ensure_representations()
        # ``OnRendererRemoved`` -> ``cleanup()`` detaches the node observers
        # (they are bundled with the renderer-scoped Representation teardown),
        # so re-establish them here.  Without this the observed set is empty
        # after the manager's initial renderer churn (SetDisplayNode attaches,
        # OnRendererRemoved detaches, OnRendererAdded historically did NOT
        # re-attach) and a control-point DRAG never reaches ``UpdatePipeline``
        # — the dragging-changes-nothing failure mode.  Also re-derives the
        # data node, covering the lifecycle where ``GetDisplayableNode()`` is
        # not yet resolvable at ``SetDisplayNode`` time.
        self._reattach_node_observers()
        # Re-emit a dispatch so the Representations re-attach their actors
        # against the new renderer.
        self._last_update_key = None
        self.UpdatePipeline()

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        """Tear down Representations when the renderer goes away."""
        del renderer
        self.cleanup()

    # ------------------------------------------------------------------ #
    # Introspection — used by the workflow / unit tests
    # ------------------------------------------------------------------ #

    def GetDataNode(self) -> Any | None:
        return self._data_node

    def GetFlattenedSurfaceRepresentation(self) -> Any | None:
        return self._flattened_surface

    def GetVascularContourRepresentation(self) -> Any | None:
        return self._vascular_contour

    def GetUpdateCount(self) -> int:
        """Total ``UpdatePipeline()`` calls that did real work
        (short-circuits do not count).  Tests assert idempotency
        against this."""
        return self._update_count

    def cleanup(self) -> None:
        """Detach observers and tear down Representations.

        Safe to call multiple times.  Per `ADR-0013`_ §5, normally
        invoked from ``OnRendererRemoved`` when the display node leaves
        the scene.
        """
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._observer_tags.clear()
        self._observed_node_refs.clear()

        for rep in (self._flattened_surface, self._vascular_contour):
            if rep is not None:
                try:
                    rep.cleanup()
                except Exception:  # pragma: no cover - defensive
                    pass

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_representations(self) -> None:
        """Build the two Representations once, on first dispatch.

        Lazy construction lets the Pipeline survive the LayerDM
        lifecycle ordering (``SetDisplayNode`` may fire before
        ``OnRendererAdded``).  Per `ADR-0013`_ §6, Representations are
        constructed once and reused.
        """
        if self._representations_initialised:
            return

        renderer = self._safe_get_renderer()

        # Local imports to avoid a circular import.  Two import paths
        # supported, mirroring the Bezier Pipeline:
        #
        # * Package-relative — when imported as
        #   ``LiverResectionsLib.ResectogramPipeline`` from a
        #   Slicer-installed loadable module.
        # * Top-level — when the directory containing this file is on
        #   ``sys.path`` directly (the unit-layer test convention).
        try:  # pragma: no cover - exercised once per import path
            from .Representations.FlattenedSurfaceRepresentation import (
                FlattenedSurfaceRepresentation,
            )
            from .Representations.VascularContourRepresentation import (
                VascularContourRepresentation,
            )
        except ImportError:
            from Representations.FlattenedSurfaceRepresentation import (  # type: ignore[no-redef]
                FlattenedSurfaceRepresentation,
            )
            from Representations.VascularContourRepresentation import (  # type: ignore[no-redef]
                VascularContourRepresentation,
            )

        self._flattened_surface = FlattenedSurfaceRepresentation(renderer=renderer)
        self._vascular_contour = VascularContourRepresentation(renderer=renderer)

        self._representations_initialised = True

    def _safe_get_renderer(self) -> Any | None:
        """Return ``self.GetRenderer()`` if available, else ``None``.

        The base ``vtkMRMLLayerDMPipelineI::GetRenderer`` is supplied
        once the manager attaches the Pipeline to a renderer.  Tests that
        construct the Pipeline before a renderer is wired need the
        ``None`` fallback.
        """
        getter = getattr(self, "GetRenderer", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # pragma: no cover - defensive
            return None

    def _reattach_node_observers(self) -> None:
        """(Re-)wire the display + data node observers, idempotently.

        The observed set is logically tied to the display/data node, NOT the
        renderer — but ``OnRendererRemoved`` -> ``cleanup()`` detaches every
        observer to release the renderer-scoped Representations, so the
        observers must be re-established whenever the display node is set or a
        renderer is (re-)attached, or the resectogram silently stops tracking
        control-point edits (the dragging-changes-nothing failure mode).

        Detaches any stale observers first so repeated calls never stack
        duplicate observers.  Re-derives ``self._data_node`` from the display
        node's ``GetDisplayableNode()`` each time, which also covers the
        lifecycle where the back-reference is not yet resolvable at
        ``SetDisplayNode`` time but is by ``OnRendererAdded``.
        """
        for node in list(self._observed_node_refs):
            self._detach_observer(node)

        self._data_node = None
        if self._display_node is None:
            return

        getter = getattr(self._display_node, "GetDisplayableNode", None)
        if getter is not None:
            self._data_node = getter()
        self._attach_observer(self._display_node)
        if self._data_node is not None:
            self._attach_observer(self._data_node)

    def _attach_observer(self, node: Any) -> None:
        """Observe the node's modification events, routed to ``UpdatePipeline()``.

        Observes ``ModifiedEvent`` AND the markups control-point edit events
        (``PointModifiedEvent`` / ``PointPositionDefinedEvent``).  A
        markups control-point DRAG does NOT advance the node's ``GetMTime``
        and fires ``PointModifiedEvent`` rather than ``ModifiedEvent``, so a
        ``ModifiedEvent``-only observer would leave the resectogram
        non-reactive to surface edits (the dragging-changes-nothing failure
        mode).  Stores every observer tag so ``cleanup()`` /
        ``_detach_observer`` can detach precisely.
        """
        if node is None or not hasattr(node, "AddObserver"):
            return

        tags = self._observer_tags.setdefault(id(node), [])
        tags.append(node.AddObserver("ModifiedEvent", self._on_node_modified))
        for event_name in ("PointModifiedEvent", "PointPositionDefinedEvent"):
            event = getattr(node, event_name, None)
            if event is not None:
                tags.append(node.AddObserver(event, self._on_node_modified))
        if node not in self._observed_node_refs:
            self._observed_node_refs.append(node)

    def _detach_observer(self, node: Any) -> None:
        if node is None:
            return
        tags = self._observer_tags.pop(id(node), [])
        for tag in tags:
            try:
                node.RemoveObserver(tag)
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            self._observed_node_refs.remove(node)
        except ValueError:
            pass

    def _on_node_modified(self, caller: Any, event: str) -> None:
        """VTK observer callback — re-runs ``UpdatePipeline()``.

        Does NOT invalidate the memoised key: ``UpdatePipeline`` keys on the
        control-point geometry digest, which a real control-point edit changes
        on its own (so the edit is picked up) but a render-induced ``Modified``
        at fixed geometry does NOT.  Resetting the key here would defeat that
        short-circuit and re-open the maximize render storm.

        Requests a render ONLY when ``UpdatePipeline`` actually did work — the
        ``_update_count`` advanced.  A render-churned ``Modified`` at unchanged
        geometry short-circuits (no count advance) → no render requested →
        the feedback loop is broken.  A real control-point DRAG advances the
        digest → real work → exactly one coalesced render through the base
        Pipeline's ``RequestRender`` (delegates to
        ``vtkMRMLLayerDMPipelineManager::RequestRender``), so the panel
        repaints live without the framework's own display-node event path.
        """
        del caller, event  # observers route uniformly into UpdatePipeline()
        before = self._update_count
        self.UpdatePipeline()
        if self._update_count == before:
            return  # short-circuited: no geometry change, no render

        request_render = getattr(self, "RequestRender", None)
        if request_render is not None:
            try:
                request_render()
            except Exception:  # pragma: no cover - defensive (stub bases)
                pass


# --------------------------------------------------------------------------- #
# Safe accessors — tolerant of stub nodes that omit the markups accessors.
# --------------------------------------------------------------------------- #


def _safe_get_control_points_digest(node: Any) -> tuple:
    """Return a digest of the data node's markups control-point positions.

    This digest is the SOLE memoisation key for ``UpdatePipeline`` (it does
    NOT fold in ``GetMTime``): a control-point edit changes the digest, while
    a render-induced ``Modified`` at fixed geometry does not, which is exactly
    the discrimination that keeps edits reactive while breaking the maximize
    render storm.  A markups control-point DRAG advances only the
    separately-timed control-point structure, not the node ``GetMTime``, so a
    geometry digest is the correct reactivity signal.  Returns an empty tuple
    when the node is missing the markups control-point accessors (stub nodes
    in unit tests) or a read raises — the key is then a constant, so a
    non-markups data node reconciles exactly once.
    """
    if node is None:
        return ()
    count_getter = getattr(node, "GetNumberOfControlPoints", None)
    position_getter = getattr(node, "GetNthControlPointPosition", None)
    if count_getter is None or position_getter is None:
        return ()
    try:
        count = int(count_getter())
        position = [0.0, 0.0, 0.0]
        digest = []
        for index in range(count):
            position_getter(index, position)
            digest.append((position[0], position[1], position[2]))
        return tuple(digest)
    except Exception:  # pragma: no cover - defensive
        return ()


# --------------------------------------------------------------------------- #
# Pipeline-creator registration — ADR-0013 §5 call 3
# --------------------------------------------------------------------------- #


_REGISTERED = False


def registerResectogramPipelineCreator() -> None:
    """Register the ``ResectogramPipeline`` creator with LayerDM.

    Performs `ADR-0013`_ §5 call 3 keyed on
    ``vtkMRMLResectogramDisplayNode`` — the dedicated display-node type
    that resolves the §1 one-Pipeline-per-type fork (a second creator on
    the shared ``vtkMRMLParametricSurfaceDisplayNode`` the Bezier
    Pipeline owns would violate §1).

    Idempotent via the module-level ``_REGISTERED`` flag.  The upstream
    ``vtkMRMLLayerDMPipelineFactory::ContainsPipelineCreator`` compares
    creators by smart-pointer identity, and every call to this function
    constructs a *fresh* ``vtkMRMLLayerDMPipelineScriptedCreator``;
    without the guard a second ``setup()`` invocation (module reload,
    Slicer restart in embedded contexts) would append a duplicate.

    The creator returns a fresh ``ResectogramPipeline`` only when the
    ``node`` is a ``vtkMRMLResectogramDisplayNode`` AND the ``viewNode`` is
    the DEDICATED resectogram view — the one carrying
    ``SetSingletonTag(RESECTOGRAM_VIEW_SINGLETON_TAG)`` (`ADR-0023`_
    §Stage-4).  Every other ``(viewNode, node)`` combination — slice views,
    the shared 3D anatomy view, the Bezier parametric-surface display node —
    short-circuits to ``None`` so the Bezier creator (and any other
    registered creator) gets a chance to handle them, and the flattened
    strip never bleeds into the shared anatomy renderer (`ADR-0013`_ §1
    disjoint keying; `ADR-0023`_ §Stage-4).
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Imports deferred so this module stays importable in plain Python
    # (tests ``pytest.importorskip("LayerDMLib")`` already; the
    # ``slicer``-prefixed symbols below are only reachable inside a
    # Slicer process).
    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLResectogramDisplayNode,
        vtkMRMLViewNode,
    )

    # Imported here (not at module top) because the tag constant lives in a
    # sibling module that itself defers its ``slicer`` import; the local
    # import keeps this module importable in plain Python.
    try:  # pragma: no cover - exercised once per import path
        from .ResectogramViewManager import RESECTOGRAM_VIEW_SINGLETON_TAG
    except ImportError:
        from ResectogramViewManager import (  # type: ignore[no-redef]
            RESECTOGRAM_VIEW_SINGLETON_TAG,
        )

    def tryCreate(viewNode, node):
        # Dedicated-view gating (ADR-0023 §Stage-4): the resectogram renders
        # ONLY into its dedicated view — the one carrying the resectogram
        # singleton tag.  ``RegisterInDefaultViews`` registers the generic
        # LayerDM DM in every 3D and slice factory, so this creator is
        # invoked for the shared anatomy view and slice views too; gating on
        # the singleton tag keeps the flattened strip out of the shared
        # anatomy renderer (ADR-0013 §1 disjoint keying).
        if not isinstance(viewNode, vtkMRMLViewNode):
            return None
        if viewNode.GetSingletonTag() != RESECTOGRAM_VIEW_SINGLETON_TAG:
            return None
        if not isinstance(node, vtkMRMLResectogramDisplayNode):
            return None
        return ResectogramPipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True
