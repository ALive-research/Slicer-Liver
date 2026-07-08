# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""State-aware LayerDM Pipeline for the Bezier-surface concept.

This is the first concrete instantiation of the LayerDM Pipeline
pattern committed by `ADR-0013`_ §4 and the LiverMarkups dissolution
named by `ADR-0014`_ §2.  One Pipeline observes a
``vtkMRMLBezierSurfaceNode`` (data, ADR-0014 §1), its paired
``vtkMRMLParametricSurfaceDisplayNode`` (decoration, ADR-0013 §8) and —
when wired — the orchestrating ``vtkMRMLResectionPlanNode``'s
``State`` / ``InitializationMode`` (per ADR-0013 §4).
The Pipeline owns three Representations keyed on the
``(state, initMode)`` tuple; ``UpdatePipeline()`` activates whichever
Representation matches the current tuple.

Pipeline base class
-------------------
ADR-0013 §5 names ``vtkMRMLLayerDMScriptedPipeline`` (imported as
``from LayerDMLib import vtkMRMLLayerDMScriptedPipeline``) as the
canonical base.  T2.6-LayerDM swapped from the project-local stand-in
to a hard requirement on the upstream LayerDM library.  Unit tests
that previously ran in pure-Python pytest now ``pytest.importorskip
("LayerDMLib")`` at module level — they execute only inside a Slicer
process where LayerDMLib is importable.

Lifecycle (LayerDM-managed)
---------------------------
Per ADR-0013 §5 the Pipeline is created and destroyed by LayerDM's
``vtkMRMLLayerDMPipelineManager``:

1. ``__init__()`` — no-arg constructor (LayerDM contract).  Calls
   ``SetPythonObject(self)`` via the base.  Initialises Representation
   slots to ``None``; Representations are built lazily once the
   display node is attached and a renderer is available.
2. ``SetViewNode(viewNode)`` — assigned by the manager before
   ``SetDisplayNode``; observed for ``ModifiedEvent`` by the base.
3. ``SetDisplayNode(displayNode)`` — assigned by the manager.  The
   override derives ``self._data_node = displayNode.GetDisplayableNode()``,
   wires the observers, and builds Representations the first time it
   runs.
4. ``UpdatePipeline()`` — called by the manager when the display
   node, data node, or view state changes (and on ``ResetDisplay()``).
   Performs the ``(state, initMode)`` dispatch and forwards to the
   active Representation's ``update()``.  Idempotent.
5. ``cleanup()`` — invoked from ``OnRendererRemoved`` (and by direct
   callers in tests).  Detaches observers and tears down
   Representations.

Observer dispatch
-----------------
The Pipeline attaches three ``vtkCommand::ModifiedEvent`` observers:

* On the **data node** — ``vtkMRMLBezierSurfaceNode`` —
  geometry / state-machine mutations.
* On the **display node** — ``vtkMRMLParametricSurfaceDisplayNode`` —
  decoration mutations.
* On the **orchestrating-state node** (optional, when wired) —
  ``vtkMRMLResectionPlanNode`` — coarse-grained workflow state
  changes that some Representations gate on.

All three callbacks route into ``UpdatePipeline()``.  See ADR-0013 §4
for the rationale: the orchestrating-state node's ``State`` /
``InitializationMode`` drive Representation dispatch.

Idempotency
-----------
``UpdatePipeline()`` memoises the (state, initMode, dataMTime,
displayMTime, resectionMTime) tuple it ran against most recently.  A
second call with no intervening node mutation is a no-op — required
by ADR-0013 §3's ``update()`` contract.

Pipeline-creator registration
-----------------------------
The C++ ``qSlicerLiverResectionsModule::setup()`` performs ADR-0013
§5's three-call contract:

* Call 1 — ``vtkMRMLScene::RegisterNodeClass`` for the
  ``BezierSurface{Node,DisplayNode,StorageNode}`` trio (landed by the
  prior T2.6 commit).
* Call 2 — ``vtkMRMLLayerDisplayableManager::RegisterInFactory`` +
  ``RegisterInDefaultViews`` (lands here, in the C++ ``setup()``).
* Call 3 — ``vtkMRMLLayerDMPipelineFactory::GetInstance()->Add
  PipelineCreator(...)`` (lands here, delegated from C++ ``setup()``
  to the Python ``registerPipelineCreator()`` function defined at
  module bottom, via the loadable-module's ``pythonManager()``).

References
----------
* `ADR-0011`_ — SCT terminology dispatch (the ``TerminologyEntry``
  field on the display node is the dispatch key for the Pipeline's
  colour / label / badge decisions when populated).
* `ADR-0013`_ §4, §5 — Pipeline pattern + three registration calls
  (primary spec).
* `ADR-0014`_ §2 — LiverMarkups dissolution (names the three
  Representations and their state-conditional dispatch).
* `ADR-0008`_ — testing strategy (three-tier coverage).

.. _ADR-0011: ../../Docs/adr/0011-sct-terminology-dispatch.md
.. _ADR-0013: ../../Docs/adr/0013-layerdm-pipeline-pattern.md
.. _ADR-0014: ../../Docs/adr/0014-livermarkups-dissolution.md
.. _ADR-0008: ../../Docs/adr/0008-testing-strategy.md
"""

from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# Pipeline base — hard-required on the upstream LayerDM library per ADR-0013
# §5.  Importable from any Slicer process that loaded the
# SlicerLayerDisplayableManager extension (an unconditional
# ``EXTENSION_DEPENDS`` entry of Slicer-Liver).  Tests that exercise this
# module outside Slicer ``pytest.importorskip("LayerDMLib")`` at module
# level — the standalone path that pre-dated T2.6-LayerDM is retired.
# --------------------------------------------------------------------------- #

from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase


# --------------------------------------------------------------------------- #
# Representation slots — keyed strings used both as the dict key in
# ``_representations`` and as the dispatch key in ``_select_representation``.
# Names match ADR-0014 §2.
# --------------------------------------------------------------------------- #

REPRESENTATION_SLICING_PLANE_INIT = "SlicingPlaneInit"
REPRESENTATION_DISTANCE_SPHEROID_INIT = "DistanceSpheroidInit"
REPRESENTATION_BEZIER_PLANNING = "BezierPlanning"
REPRESENTATION_CONFIRMED = "Confirmed"


# --------------------------------------------------------------------------- #
# State / mode integer constants
# --------------------------------------------------------------------------- #
#
# These mirror the C++ enum values pinned on
# ``vtkMRMLBezierSurfaceNode`` (header lines 135-151).  Pinning the
# Python constants explicitly means the Pipeline can read state /
# mode integers off any node-shaped object (real or stub) without a
# hard dependency on the wrapped MRML module being importable — the
# pure-Python unit tests under ``Testing/Python/unit/`` rely on that.
# When the wrapped node IS importable, ``GetState() == STATE_INIT``
# matches the C++ enum ``vtkMRMLBezierSurfaceNode::Init == 0`` and
# the dispatch tables agree.

STATE_INIT = 0
STATE_PLANNING = 1
STATE_CONFIRMED = 2

INIT_MODE_SLICING_PLANE = 0
INIT_MODE_DISTANCE_SPHEROID = 1


class LiverBezierSurfacePipeline(_PipelineBase):
    """State-aware Pipeline for the Bezier-surface concept.

    Constructed by LayerDM's ``vtkMRMLLayerDMPipelineManager`` via the
    creator registered by ``registerPipelineCreator()`` at module
    bottom.  No-arg constructor per the LayerDM contract.

    Direct instantiation is supported for tests that run inside a
    Slicer process (i.e. with LayerDMLib importable); those tests
    perform the same wiring the manager would:

    .. code-block:: python

        pipeline = LiverBezierSurfacePipeline()
        pipeline.SetDisplayNode(display_node)  # derives data_node

    The Pipeline owns three Representation slots keyed on the
    ``(state, initMode)`` tuple; ``UpdatePipeline()`` activates
    whichever Representation matches the current tuple.

    Idempotency
    -----------
    ``UpdatePipeline()`` is idempotent: the Pipeline records the
    ``(state, initMode, dataMTime, displayMTime, resectionMTime)``
    tuple it last ran against and short-circuits when nothing has
    changed.
    """

    def __init__(self) -> None:
        super().__init__()

        # Node handles — populated when the manager calls the
        # corresponding setters.  ``SetDisplayNode`` derives
        # ``_data_node`` from ``displayNode.GetDisplayableNode()``.
        self._data_node: Any | None = None
        self._display_node: Any | None = None
        self._resection_node: Any | None = None

        # Scene ``MTime`` the last plan reverse-resolution scan ran against
        # (ADR-0031).  The scan (``GetNodesByClass``) is gated on this so a
        # bare surface with no owning plan does not full-scene-scan on every
        # ``UpdatePipeline`` tick; it re-scans only when the scene structure
        # changes (a plan added later).  ``None`` forces a scan on the next
        # dispatch (reset when the display/data node changes).
        self._last_resection_scan_mtime: int | None = None

        # The cross-view locator node (ADR-0025), reverse-resolved from the
        # scene (v2.0 has exactly one).  Observed so its picked-point changes
        # re-dispatch; threaded onto the active Representation's consumer seam.
        # Discovery is gated on the scene ``MTime`` (like the plan scan) so a
        # position update to an already-resolved locator rides its own observer
        # rather than a per-tick class scan.
        self._locator_node: Any | None = None
        self._last_locator_scan_mtime: int | None = None

        # Observer tags so ``cleanup()`` can detach precisely.  Index
        # by ``id(node)`` because ``vtkObject`` subclasses are not
        # universally hashable on identity.
        self._observer_tags: dict[int, list[int]] = {}
        # Parallel strong-ref list so ``cleanup()`` can iterate
        # observed nodes by reference (not by id) when calling
        # ``RemoveObserver``.
        self._observed_node_refs: list[Any] = []

        # Memoised dispatch input — see ``UpdatePipeline`` for the
        # invariant.
        self._last_update_key: tuple | None = None

        # SlicingPlane Init-placement progress (ADR-0032 slice 3a): how many
        # of the fixed two slicing-plane init points have been placed on the
        # current carrier.  The node has no on-node placed-count (the array is
        # a fixed 2 slots), so the Pipeline owns it; reset when the carrier
        # changes (SetDisplayNode).
        self._slicing_plane_points_placed: int = 0

        # DistanceSpheroid Init-placement progress (ADR-0032 slice 3b): how many
        # distance-spheroid init points have been placed on the current carrier.
        # Unlike SlicingPlane (a fixed two slots), the spheroid capacity is
        # DYNAMIC (``GetNumberOfDistanceSpheroidInitPoints`` — default 0, sized
        # while in Init), and the node still exposes no on-node placed-count, so
        # the Pipeline owns it; reset when the carrier changes (SetDisplayNode).
        self._distance_spheroid_points_placed: int = 0

        # Counter that workflow tests assert idempotency against:
        # advances only on dispatch work, not on short-circuits.
        self._update_count: int = 0

        # Representation slots.  Keys match ADR-0014 §2 names.
        # Populated lazily by ``_ensure_representations()`` once a
        # renderer is available (see ``OnRendererAdded`` / first
        # ``UpdatePipeline``).
        self._representations: dict[str, Any | None] = {
            REPRESENTATION_SLICING_PLANE_INIT: None,
            REPRESENTATION_DISTANCE_SPHEROID_INIT: None,
            REPRESENTATION_BEZIER_PLANNING: None,
            REPRESENTATION_CONFIRMED: None,
        }

        # Whether Representations have been constructed yet — guards
        # ``_ensure_representations`` so it runs exactly once.
        self._representations_initialised = False

        # The Representation that ``UpdatePipeline`` last activated.
        # ``None`` before the first ``UpdatePipeline``.
        self._current_representation_name: str | None = None

        # On-commit extraction boundary (ADR-0019 Init->Planning
        # transition).  Per-drag ``UpdatePipeline`` ticks only MARK
        # extraction pending — the per-frame visual feedback is the
        # shader's job.  The discrete CPU ring extraction is one-shot
        # per resection: it runs exactly once when ``commit()`` consumes
        # the pending request on the Init->Planning transition.
        self._pending_extraction: bool = False

    # ------------------------------------------------------------------ #
    # LayerDM lifecycle overrides
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, displayNode: Any) -> None:  # noqa: N802 - VTK verb
        """Attach the display node, derive the data node, wire observers.

        Per ADR-0013 §5 the manager calls this once after creating
        the Pipeline.  Re-entrant: replacing an already-attached
        display node detaches the old observer and re-derives the
        data node.
        """
        # Drop the old observers (if any) before swapping the
        # ref — the Pipeline's identity is stable across the
        # display-node swap.
        if self._display_node is not None:
            self._detach_observer(self._display_node)
        if self._data_node is not None:
            self._detach_observer(self._data_node)

        # Delegate to the base for the ``GetDisplayNode()`` /
        # ``GetDisplayableNode()`` machinery.
        super().SetDisplayNode(displayNode)

        self._display_node = displayNode
        self._data_node = None
        if displayNode is not None:
            # The data node lives on the display node's
            # ``GetDisplayableNode()`` accessor — the conventional
            # MRML back-reference.
            getter = getattr(displayNode, "GetDisplayableNode", None)
            if getter is not None:
                self._data_node = getter()
            self._attach_observer(displayNode)
            if self._data_node is not None:
                self._attach_observer(self._data_node)

        # Invalidate the memoised dispatch key — the next
        # ``UpdatePipeline`` picks up the new node set.
        self._last_update_key = None
        # Force a fresh plan reverse-resolution for the new data node.
        self._last_resection_scan_mtime = None
        # Force a fresh locator re-resolution too (ADR-0025).
        self._last_locator_scan_mtime = None
        # Restart SlicingPlane init-placement for the new carrier (slice 3a).
        self._slicing_plane_points_placed = 0
        # Restart DistanceSpheroid init-placement for the new carrier (slice 3b).
        self._distance_spheroid_points_placed = 0

    def OnReferenceToDisplayNodeAdded(self, fromNode: Any, role: Any = None) -> None:  # noqa: N802 - VTK verb
        """Adopt the displayable when it links to our display node late.

        The production creation ordering (``CreateDefaultDisplayNodes``) adds
        the display node to the scene -- firing the LayerDM creator and
        ``SetDisplayNode`` -- BEFORE ``SetAndObserveDisplayNodeID`` links it
        to the carrier, so the data node derived as ``None``.  The LayerDM
        manager calls this hook at the exact link moment with ``fromNode`` ==
        the referencing displayable (the carrier); adopt it and re-dispatch.
        Without this the Pipeline stays permanently data-node-less (no
        observers, no dispatch, the default unit patch renders).
        """
        if self._data_node is None and fromNode is not None and fromNode is not self._display_node:
            self._data_node = fromNode
            self._attach_observer(fromNode)
            self._last_update_key = None
            self._last_resection_scan_mtime = None
            self._last_locator_scan_mtime = None
        self.UpdatePipeline()

    def UpdatePipeline(self) -> None:  # noqa: N802 - VTK verb
        """Dispatch the active Representation by ``(state, initMode)``.

        Idempotent: a second call with no intervening node mutation
        is a no-op observationally — the memoised key short-circuits
        the work.

        Per ADR-0013 §5 this is the entry point the LayerDM manager
        invokes when the display node, data node, or view state
        changes (and on ``ResetDisplay()``).
        """
        self._ensure_representations()

        # Late-bind the data node (the production creation ordering):
        # ``CreateDefaultDisplayNodes`` adds the display node to the scene --
        # firing the LayerDM creator and this Pipeline's ``SetDisplayNode`` --
        # BEFORE ``SetAndObserveDisplayNodeID`` links it to the carrier, so
        # ``GetDisplayableNode()`` was None at derivation time.  Re-derive
        # here; adopting also attaches the carrier observer so subsequent
        # control-grid edits re-dispatch.
        if self._data_node is None and self._display_node is not None:
            getter = getattr(self._display_node, "GetDisplayableNode", None)
            displayable = getter() if getter is not None else None
            if displayable is not None:
                self._data_node = displayable
                self._attach_observer(displayable)
                self._last_update_key = None
                self._last_resection_scan_mtime = None
                self._last_locator_scan_mtime = None

        # Reverse-resolve the orchestrating wrapper when no explicit one was
        # set (ADR-0031).  The LayerDM creator hands the Pipeline only the
        # display node (it matches on vtkMRMLParametricSurfaceDisplayNode), so
        # nothing sets _resection_node in the live render path; discover the
        # vtkMRMLResectionPlanNode whose geometry reference is our data node
        # and adopt it, so the plan's distance-map + margins reach the mapper
        # with no external SetResectionNode caller.  Re-attempted while unset
        # (the plan's geometry ref may be wired after the display node lands).
        # Gate the scan on the scene's MTime so a bare surface with no owning
        # plan does not full-scene-scan every tick (every interaction frame):
        # re-scan only when the scene structure changed since the last scan
        # (which is when a plan could have appeared).
        if self._resection_node is None and self._data_node is not None:
            scene = self._data_node.GetScene()
            scene_mtime = scene.GetMTime() if scene is not None else 0
            if scene_mtime != self._last_resection_scan_mtime:
                self._last_resection_scan_mtime = scene_mtime
                resolved = self._resolve_resection_node()
                if resolved is not None:
                    self.SetResectionNode(resolved)

        # Reverse-resolve the cross-view locator node (ADR-0025) — the scene's
        # single ``vtkMRMLLocatorNode`` — and re-target its observer when it
        # appears / disappears, so its picked-point changes re-dispatch.  Gated
        # on the scene MTime like the plan scan: a picked-point update to an
        # already-resolved locator arrives via its observer + the locator MTime
        # in the key below, not a per-tick class scan.
        if self._data_node is not None:
            scene = self._data_node.GetScene()
            scene_mtime = scene.GetMTime() if scene is not None else 0
            if scene_mtime != self._last_locator_scan_mtime:
                self._last_locator_scan_mtime = scene_mtime
                found = (
                    scene.GetFirstNodeByClass("vtkMRMLLocatorNode")
                    if scene is not None
                    else None
                )
                if found is not self._locator_node:
                    if self._locator_node is not None:
                        self._detach_observer(self._locator_node)
                    self._locator_node = found
                    if found is not None:
                        self._attach_observer(found)

        # Build the dispatch key.  Falls back to ``0`` MTime for nodes
        # whose ``GetMTime`` is unavailable (defensive — stub nodes in
        # tests may not implement it).
        state = _safe_get_state(self._data_node)
        init_mode = _safe_get_init_mode(self._data_node)
        data_mtime = _safe_get_mtime(self._data_node)
        display_mtime = _safe_get_mtime(self._display_node)
        resection_mtime = _safe_get_mtime(self._resection_node)
        locator_mtime = _safe_get_mtime(self._locator_node)

        key = (
            state, init_mode, data_mtime, display_mtime, resection_mtime, locator_mtime,
        )
        if key == self._last_update_key:
            return  # idempotent short-circuit
        self._last_update_key = key

        active_name = self._select_representation(state, init_mode)
        self._current_representation_name = active_name

        active = self._representations.get(active_name) if active_name else None
        if active is not None:
            # Thread the orchestrating wrapper to Representations that consume
            # its path-specific inputs (the Planning surface reads the
            # distance-map volume + margins off it, ADR-0031).  Only the
            # BezierPlanningRepresentation implements this; others ignore it.
            if hasattr(active, "SetResectionPlanNode"):
                active.SetResectionPlanNode(self._resection_node)
            # Thread the resolved locator node to the consumer seam (ADR-0025);
            # only BezierPlanningRepresentation implements it, others ignore.
            if hasattr(active, "SetLocatorNode"):
                active.SetLocatorNode(self._locator_node)
            active.update(self._display_node, self._data_node)

        # Init-mode parameter mutations only MARK extraction pending; the
        # discrete ring extraction is debounced behind the commit
        # boundary (ADR-0019).  Per-drag visual feedback is the shader's
        # job — it must NOT trigger the CPU extraction here.
        if state == STATE_INIT:
            self._pending_extraction = True

        self._update_count += 1

    def OnRendererAdded(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        """Build Representations once a renderer is attached.

        Per ADR-0013 §5 the renderer is supplied by the manager; the
        Pipeline cannot construct its actor-bearing Representations
        until ``GetRenderer()`` returns a non-None value.
        """
        del renderer  # accessed via self.GetRenderer() inside the helper
        self._ensure_representations()
        # Re-emit a dispatch so the active Representation re-attaches
        # its actors against the new renderer.
        self._last_update_key = None
        self.UpdatePipeline()

    def OnRendererRemoved(self, renderer: Any) -> None:  # noqa: N802 - VTK verb
        """Tear down Representations when the renderer goes away."""
        del renderer
        self.cleanup()

    # ------------------------------------------------------------------ #
    # Public extras (orchestrating-state node + introspection)
    # ------------------------------------------------------------------ #

    def SetResectionNode(self, resectionNode: Any) -> None:  # noqa: N802 - VTK verb
        """Attach the orchestrating-state node (``vtkMRMLResectionPlanNode``).

        Per ADR-0013 §4 the Pipeline's observation set is not limited
        to its own display node — when the displayed concept's
        behaviour depends on a state machine carried by another MRML
        node, the Pipeline observes that node too.
        """
        if self._resection_node is not None:
            self._detach_observer(self._resection_node)
        self._resection_node = resectionNode
        if resectionNode is not None:
            self._attach_observer(resectionNode)
        self._last_update_key = None

    def commit(self) -> None:
        """Commit the Init->Planning transition (ADR-0019).

        Constraint 3 (Stack-4 ring-extraction wiring): the discrete CPU
        ring extraction is one-shot per resection.  It runs here, exactly
        once, on the irreversible Init->Planning transition — never on
        the per-drag ``UpdatePipeline`` ticks (those only mark
        ``_pending_extraction``; per-frame feedback is the shader's job).

        ``commit()`` resolves the weakref'd target mesh off the data node
        (ADR-0014 §1, ``GetTargetModelNode()``) and routes it through the
        named, test-observable ``_run_ring_extraction`` entry point.  The
        transition is irreversible: ``commit()`` only extracts while the
        data node is still in ``Init`` and advances it to ``Planning``,
        so a second ``commit()`` is a no-op (one-shot per resection).
        """
        state = _safe_get_state(self._data_node)
        # Tolerate stub data nodes with no state accessor (None): treat a
        # missing state as still-in-Init so the single transition fires.
        if state not in (None, STATE_INIT):
            return

        target_model = self._resolve_target_model()
        self._run_ring_extraction(target_model)

        # Clear the pending request and advance the state machine so the
        # transition cannot re-fire (ADR-0019: irreversible 2-state
        # automaton; init data freezes to read-only audit data).
        self._pending_extraction = False
        setter = getattr(self._data_node, "SetState", None)
        if setter is not None:
            try:
                setter(STATE_PLANNING)
            except Exception:  # pragma: no cover - defensive
                pass

    def _resolve_target_model(self) -> Any | None:
        """Return the weakref'd target organ model node (ADR-0014 §1).

        Reads ``GetTargetModelNode()`` off the data node — the canonical
        weak ``target`` reference on ``vtkMRMLBezierSurfaceNode``.  The
        ``TODO(T2-target-mesh-weakref)`` consume sites in the Init
        Representations feed the extractor FROM here, not a hard-coded
        path or a silent ``None`` no-op.
        """
        getter = getattr(self._data_node, "GetTargetModelNode", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # pragma: no cover - defensive
            return None

    def _resolve_resection_node(self) -> Any | None:
        """Reverse-resolve the ``vtkMRMLResectionPlanNode`` wrapper.

        The plan wrapper references the surface carrier via the ``geometry``
        role (ADR-0014 §"Fourth layer"); the Pipeline reverse-walks that to
        adopt the wrapper, so it can thread the plan's distance-map + margins
        (ADR-0031) onto the Representation without an external caller.  Scans
        the scene for the plan whose ``GetGeometryNode()`` is our data node.
        Returns ``None`` when no plan owns this data node (a bare surface — the
        no-distance-map fallback).
        """
        data_node = self._data_node
        if data_node is None:
            return None
        scene = getattr(data_node, "GetScene", lambda: None)()
        if scene is None:
            return None
        try:
            plans = scene.GetNodesByClass("vtkMRMLResectionPlanNode")
        except Exception:  # pragma: no cover - defensive
            return None
        if plans is None:
            return None
        plans.InitTraversal()
        item = plans.GetNextItemAsObject()
        while item is not None:
            getter = getattr(item, "GetGeometryNode", None)
            if getter is not None:
                try:
                    if getter() is data_node:
                        return item
                except Exception:  # pragma: no cover - defensive
                    pass
            item = plans.GetNextItemAsObject()
        return None

    def _run_ring_extraction(self, target_model: Any | None = None) -> None:
        """Run the discrete ring extraction against ``target_model``.

        Named, test-observable extraction entry point the commit boundary
        routes through (Constraint 3).  Forwards the weakref'd target
        mesh to the active Init Representation's ``run_ring_extraction``
        (the ``TODO(T2-target-mesh-weakref)`` consume site), which owns
        the concrete ``vtkLiver{Plane,Spheroid}RingExtractor`` wiring.

        No-op when no target mesh is reachable — extraction needs a mesh
        to cut (ADR-0014 §1).
        """
        if target_model is None:
            return
        name = self._current_representation_name
        active = self._representations.get(name) if name else None
        runner = getattr(active, "run_ring_extraction", None) if active is not None else None
        if runner is not None:
            runner(target_model)

    def GetResectionNode(self) -> Any | None:
        return self._resection_node

    def GetDataNode(self) -> Any | None:
        return self._data_node

    # ------------------------------------------------------------------ #
    # Interaction — the LayerDM Pipeline seam (ADR-0032; no standalone
    # widget, no custom DisplayableManager).  The manager's interaction
    # logic calls CanProcessInteractionEvent on every pipeline then
    # ProcessInteractionEvent on the winner (SlicerLayerDisplayableManager
    # vtkMRMLLayerDMInteractionLogic).  Control-grid editing is gated on the
    # Planning state (ADR-0019).
    # ------------------------------------------------------------------ #

    #: Pick radius (display pixels) within which a click grabs a control point.
    _CONTROL_POINT_PICK_RADIUS_PX = 20.0

    def CanProcessInteractionEvent(self, eventData: Any):  # noqa: N802 - VTK verb
        """Return ``(canProcess, distance2)`` for the LayerDM interaction logic.

        The pipeline can process the event iff the carrier is editable
        (Planning, ADR-0019) and the cursor is within
        ``_CONTROL_POINT_PICK_RADIUS_PX`` of a control point in display space.
        ``distance2`` is the squared display distance to the nearest control
        point (smaller wins focus in the interaction logic).
        """
        import sys

        if _safe_get_state(self._data_node) != STATE_PLANNING:
            return False, sys.float_info.max
        renderer = self._safe_get_renderer()
        if renderer is None:
            return False, sys.float_info.max
        _, distance2 = self._nearest_control_point_in_display(renderer, eventData)
        if distance2 <= self._CONTROL_POINT_PICK_RADIUS_PX * self._CONTROL_POINT_PICK_RADIUS_PX:
            return True, distance2
        return False, sys.float_info.max

    def ProcessInteractionEvent(self, eventData: Any) -> bool:  # noqa: N802 - VTK verb
        """Route the interaction by resection state (ADR-0032).

        * ``Init`` + ``SlicingPlane`` — PLACE the next slicing-plane init point
          at the cursor's world position (back-projected onto the focal plane,
          since there is no picked point yet to supply depth).
        * ``Planning`` — EDIT: move the nearest control point to the cursor's
          world position (back-projected onto that point's depth).

        Returns True iff geometry changed (the interaction logic keeps focus on
        a pipeline that returns True).
        """
        renderer = self._safe_get_renderer()
        if renderer is None:
            return False
        carrier = self._data_node
        state = _safe_get_state(carrier)

        if state == STATE_INIT and _safe_get_init_mode(carrier) == INIT_MODE_SLICING_PLANE:
            world = self._event_world_on_focal_plane(renderer, eventData)
            if world is None:
                return False
            return self._place_slicing_plane_init_point(world) is not None

        if state == STATE_INIT and _safe_get_init_mode(carrier) == INIT_MODE_DISTANCE_SPHEROID:
            world = self._event_world_on_focal_plane(renderer, eventData)
            if world is None:
                return False
            return self._place_distance_spheroid_init_point(world) is not None

        if state == STATE_PLANNING:
            idx, distance2 = self._nearest_control_point_in_display(renderer, eventData)
            if idx is None or distance2 > self._CONTROL_POINT_PICK_RADIUS_PX * self._CONTROL_POINT_PICK_RADIUS_PX:
                return False
            world = self._event_world_at_control_point(renderer, eventData, idx)
            if world is None:
                return False
            return self._apply_world_point_to_nearest_control_point(world) is not None

        return False

    def _place_slicing_plane_init_point(self, world: Any) -> int | None:
        """Place the next slicing-plane init point at RAS ``world``.

        The GL-free Init-placement kernel (ADR-0032 slice 3a): when the carrier
        is in ``Init`` + ``SlicingPlane`` mode and fewer than the fixed two
        slicing-plane init points have been placed, writes the next point (slot
        0 then 1) via ``SetSlicingPlaneInitPoint`` and returns its index.  Fill
        order (not nearest-selection — that is the Planning edit path).  A
        no-op returning ``None`` when: no carrier, not ``Init`` state, not
        ``SlicingPlane`` mode, or both slots already placed (the array is full
        — the next step is ``commit()`` to fit the surface, ADR-0019).
        """
        carrier = self._data_node
        if carrier is None:
            return None
        if _safe_get_state(carrier) != STATE_INIT:
            return None
        if _safe_get_init_mode(carrier) != INIT_MODE_SLICING_PLANE:
            return None
        set_point = getattr(carrier, "SetSlicingPlaneInitPoint", None)
        if set_point is None or self._slicing_plane_points_placed >= 2:
            return None
        index = self._slicing_plane_points_placed
        try:
            placed = set_point(index, [float(world[0]), float(world[1]), float(world[2])])
        except Exception:  # pragma: no cover - defensive
            return None
        if placed is False:  # the node's Init-only guard rejected it
            return None
        self._slicing_plane_points_placed += 1
        return index

    def _place_distance_spheroid_init_point(self, world: Any) -> int | None:
        """Place the next distance-spheroid init point at RAS ``world``.

        The GL-free Init-placement kernel (ADR-0032 slice 3b): when the carrier
        is in ``Init`` + ``DistanceSpheroid`` mode and fewer than the carrier's
        DYNAMIC capacity (``GetNumberOfDistanceSpheroidInitPoints``, sized while
        in Init) have been placed, writes the next point via
        ``SetDistanceSpheroidInitPoint`` and returns its index.  Fill order (not
        nearest-selection — that is the Planning edit path).  A no-op returning
        ``None`` when: no carrier, not ``Init`` state, not ``DistanceSpheroid``
        mode, capacity unset/zero, or all points already placed (the next step
        is ``commit()`` to fit the surface, ADR-0019).
        """
        carrier = self._data_node
        if carrier is None:
            return None
        if _safe_get_state(carrier) != STATE_INIT:
            return None
        if _safe_get_init_mode(carrier) != INIT_MODE_DISTANCE_SPHEROID:
            return None
        set_point = getattr(carrier, "SetDistanceSpheroidInitPoint", None)
        get_count = getattr(carrier, "GetNumberOfDistanceSpheroidInitPoints", None)
        if set_point is None or get_count is None:
            return None
        try:
            capacity = int(get_count())
        except Exception:  # pragma: no cover - defensive
            return None
        if self._distance_spheroid_points_placed >= capacity:
            return None
        index = self._distance_spheroid_points_placed
        try:
            placed = set_point(index, [float(world[0]), float(world[1]), float(world[2])])
        except Exception:  # pragma: no cover - defensive
            return None
        if placed is False:  # the node's Init-only guard rejected it
            return None
        self._distance_spheroid_points_placed += 1
        return index

    def _event_world_on_focal_plane(self, renderer: Any, eventData: Any):
        """Back-project the cursor's display position onto the camera focal
        plane, returning RAS ``(x, y, z)``.

        Used to place init points, which have no existing picked point to
        supply a depth; the focal plane is the conventional placement depth.
        ``None`` on failure.
        """
        try:
            ex, ey = eventData.GetDisplayPosition()
            camera = renderer.GetActiveCamera()
            fp = camera.GetFocalPoint()
            renderer.SetWorldPoint(fp[0], fp[1], fp[2], 1.0)
            renderer.WorldToDisplay()
            _fx, _fy, fz = renderer.GetDisplayPoint()
            renderer.SetDisplayPoint(float(ex), float(ey), fz)
            renderer.DisplayToWorld()
            wx, wy, wz, ww = renderer.GetWorldPoint()
        except Exception:  # pragma: no cover - defensive
            return None
        if ww == 0.0:
            return None
        return (wx / ww, wy / ww, wz / ww)

    def _apply_world_point_to_nearest_control_point(self, world: Any) -> int | None:
        """Move the carrier's nearest control point to RAS ``world``.

        The GL-free interaction kernel (ADR-0032): takes a world point
        directly (no renderer / picking), finds the carrier's control point
        nearest ``world``, moves it there via ``SetControlPoint``, and returns
        its flat row-major index (``row * Cols + col``).  A no-op returning
        ``None`` when the carrier is absent or not editable — editing is
        allowed only in the ``Planning`` state (ADR-0019); ``Init`` has no
        control polygon yet and ``Confirmed`` is read-only audit data.
        """
        carrier = self._data_node
        if carrier is None or _safe_get_state(carrier) != STATE_PLANNING:
            return None
        rows_getter = getattr(carrier, "GetRows", None)
        cols_getter = getattr(carrier, "GetCols", None)
        grid_getter = getattr(carrier, "GetControlGridVector", None)
        set_point = getattr(carrier, "SetControlPoint", None)
        if None in (rows_getter, cols_getter, grid_getter, set_point):
            return None
        try:
            rows = int(rows_getter())
            cols = int(cols_getter())
            grid = grid_getter()
            wx, wy, wz = float(world[0]), float(world[1]), float(world[2])
        except Exception:  # pragma: no cover - defensive
            return None

        best_idx = None
        best_d2 = None
        for i in range(rows * cols):
            dx = grid[i * 3 + 0] - wx
            dy = grid[i * 3 + 1] - wy
            dz = grid[i * 3 + 2] - wz
            d2 = dx * dx + dy * dy + dz * dz
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_idx = i
        if best_idx is None:
            return None
        set_point(best_idx // cols, best_idx % cols, wx, wy, wz)
        return best_idx

    def _nearest_control_point_in_display(self, renderer: Any, eventData: Any):
        """Return ``(flat_index, distance2)`` of the control point nearest the
        event's display position, projecting each control point world→display.

        ``(None, inf)`` when there is no carrier / grid.  Pure geometry given a
        renderer — the display projection needs the renderer's active camera.
        """
        import sys

        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        cols_getter = getattr(carrier, "GetCols", None) if carrier else None
        rows_getter = getattr(carrier, "GetRows", None) if carrier else None
        if None in (grid_getter, cols_getter, rows_getter):
            return None, sys.float_info.max
        try:
            grid = grid_getter()
            rows = int(rows_getter())
            cols = int(cols_getter())
            ex, ey = eventData.GetDisplayPosition()
        except Exception:  # pragma: no cover - defensive
            return None, sys.float_info.max

        best_idx = None
        best_d2 = sys.float_info.max
        for i in range(rows * cols):
            renderer.SetWorldPoint(grid[i * 3 + 0], grid[i * 3 + 1], grid[i * 3 + 2], 1.0)
            renderer.WorldToDisplay()
            dx, dy, _dz = renderer.GetDisplayPoint()
            d2 = (dx - ex) ** 2 + (dy - ey) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_idx = i
        return best_idx, best_d2

    def _event_world_at_control_point(self, renderer: Any, eventData: Any, idx: int):
        """Back-project the event's display position onto the depth of control
        point ``idx``, returning the RAS ``(x, y, z)`` the point should move to.

        Uses the picked control point's current depth (display z) so a drag
        slides the point in the camera-facing plane through its own depth —
        the conventional control-point drag behaviour.  ``None`` on failure.
        """
        carrier = self._data_node
        grid_getter = getattr(carrier, "GetControlGridVector", None) if carrier else None
        cols_getter = getattr(carrier, "GetCols", None) if carrier else None
        if None in (grid_getter, cols_getter):
            return None
        try:
            grid = grid_getter()
            ex, ey = eventData.GetDisplayPosition()
            # Display z (depth) of the picked control point.
            renderer.SetWorldPoint(grid[idx * 3 + 0], grid[idx * 3 + 1], grid[idx * 3 + 2], 1.0)
            renderer.WorldToDisplay()
            _dx, _dy, dz = renderer.GetDisplayPoint()
            # Cursor display position at that depth -> world.
            renderer.SetDisplayPoint(float(ex), float(ey), dz)
            renderer.DisplayToWorld()
            wx, wy, wz, ww = renderer.GetWorldPoint()
        except Exception:  # pragma: no cover - defensive
            return None
        if ww == 0.0:
            return None
        return (wx / ww, wy / ww, wz / ww)

    def GetRepresentation(self, name: str) -> Any | None:
        """Return the Representation registered under ``name`` (or None)."""
        return self._representations.get(name)

    def GetCurrentRepresentationName(self) -> str | None:
        """Name of the Representation activated by the last
        ``UpdatePipeline()`` — or ``None`` if it has not run yet."""
        return self._current_representation_name

    def GetUpdateCount(self) -> int:
        """Total number of ``UpdatePipeline()`` calls that did real
        work (short-circuits do not count).  Tests use this to
        assert idempotency."""
        return self._update_count

    def cleanup(self) -> None:
        """Detach observers and tear down Representations.

        Safe to call multiple times.  Per ADR-0013 §5, normally
        invoked from ``OnRendererRemoved`` when the display node
        leaves the scene.
        """
        for node in list(self._observed_node_refs):
            self._detach_observer(node)
        self._observer_tags.clear()
        self._observed_node_refs.clear()

        for rep in self._representations.values():
            if rep is not None:
                try:
                    rep.cleanup()
                except Exception:  # pragma: no cover - defensive
                    pass

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _ensure_representations(self) -> None:
        """Build Representations once, on first dispatch.

        Lazy construction lets the Pipeline survive the LayerDM
        lifecycle ordering (``SetDisplayNode`` may fire before
        ``OnRendererAdded``).  Per ADR-0013 §6, Representations are
        constructed once and reused across state transitions.
        """
        if self._representations_initialised:
            return

        renderer = self._safe_get_renderer()

        # Local imports to avoid a circular import when the
        # Representations package grows.  Two import paths supported:
        #
        # * Package-relative — used when this module is imported as
        #   ``LiverResectionsLib.LiverBezierSurfacePipeline`` from a
        #   Slicer-installed loadable module.
        # * Top-level — used when the directory containing this file
        #   has been prepended to ``sys.path`` directly (the
        #   convention adopted by the unit-layer tests under
        #   ``Testing/Python/unit/``).
        try:  # pragma: no cover - exercised once per import path
            from .Representations.BezierPlanningRepresentation import (
                BezierPlanningRepresentation,
            )
            from .Representations.ConfirmedRepresentation import (
                ConfirmedRepresentation,
            )
            from .Representations.DistanceSpheroidInitRepresentation import (
                DistanceSpheroidInitRepresentation,
            )
            from .Representations.SlicingPlaneInitRepresentation import (
                SlicingPlaneInitRepresentation,
            )
        except ImportError:
            from Representations.BezierPlanningRepresentation import (  # type: ignore[no-redef]
                BezierPlanningRepresentation,
            )
            from Representations.ConfirmedRepresentation import (  # type: ignore[no-redef]
                ConfirmedRepresentation,
            )
            from Representations.DistanceSpheroidInitRepresentation import (  # type: ignore[no-redef]
                DistanceSpheroidInitRepresentation,
            )
            from Representations.SlicingPlaneInitRepresentation import (  # type: ignore[no-redef]
                SlicingPlaneInitRepresentation,
            )

        self._representations[REPRESENTATION_BEZIER_PLANNING] = (
            BezierPlanningRepresentation(renderer=renderer)
        )
        self._representations[REPRESENTATION_SLICING_PLANE_INIT] = (
            SlicingPlaneInitRepresentation(renderer=renderer)
        )
        self._representations[REPRESENTATION_DISTANCE_SPHEROID_INIT] = (
            DistanceSpheroidInitRepresentation(renderer=renderer)
        )
        self._representations[REPRESENTATION_CONFIRMED] = (
            ConfirmedRepresentation(renderer=renderer)
        )

        self._representations_initialised = True

    def _safe_get_renderer(self) -> Any | None:
        """Return ``self.GetRenderer()`` if available, else ``None``.

        The base ``vtkMRMLLayerDMPipelineI::GetRenderer`` is supplied
        once the manager attaches the Pipeline to a renderer.  Tests
        that construct the Pipeline before a renderer is wired need
        the ``None`` fallback.
        """
        getter = getattr(self, "GetRenderer", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # pragma: no cover - defensive
            return None

    def _select_representation(
        self, state: int | None, init_mode: int | None
    ) -> str | None:
        """Map ``(state, initMode)`` → Representation key per ADR-0014 §2
        and ADR-0019 §"Pipeline dispatch".

        Returns ``None`` when no Representation matches (e.g. an
        unrecognised state value).
        """
        if state == STATE_CONFIRMED:
            return REPRESENTATION_CONFIRMED
        if state == STATE_PLANNING:
            return REPRESENTATION_BEZIER_PLANNING
        if state == STATE_INIT:
            if init_mode == INIT_MODE_SLICING_PLANE:
                return REPRESENTATION_SLICING_PLANE_INIT
            if init_mode == INIT_MODE_DISTANCE_SPHEROID:
                return REPRESENTATION_DISTANCE_SPHEROID_INIT
        return None

    def _attach_observer(self, node: Any) -> None:
        """Add a ``vtkCommand::ModifiedEvent`` observer to ``node``.

        Routes the callback into ``UpdatePipeline()``.  Stores the
        observer tag so ``cleanup()`` / ``_detach_observer`` can
        detach precisely.
        """
        if node is None or not hasattr(node, "AddObserver"):
            return

        tag = node.AddObserver("ModifiedEvent", self._on_node_modified)
        self._observer_tags.setdefault(id(node), []).append(tag)
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

        Signature matches what VTK passes ``AddObserver`` callbacks:
        ``(caller, event_name_or_id)``.  Both arguments are unused —
        ``UpdatePipeline()`` re-reads node state directly.
        """
        del caller, event  # observers route uniformly into UpdatePipeline()
        self.UpdatePipeline()


# --------------------------------------------------------------------------- #
# Safe accessors — tolerant of stub nodes that omit GetMTime / GetState etc.
# --------------------------------------------------------------------------- #


def _safe_get_state(node: Any) -> int | None:
    """Read ``GetState()`` off ``node`` defensively.

    Returns ``None`` if the node is ``None`` or does not implement
    ``GetState()``.
    """
    if node is None:
        return None
    getter = getattr(node, "GetState", None)
    if getter is None:
        return None
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return None


def _safe_get_init_mode(node: Any) -> int | None:
    """Read ``GetInitMode()`` off ``node`` defensively."""
    if node is None:
        return None
    getter = getattr(node, "GetInitMode", None)
    if getter is None:
        return None
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return None


def _safe_get_mtime(node: Any) -> int:
    """Read ``GetMTime()`` off ``node`` defensively; 0 when unavailable."""
    if node is None:
        return 0
    getter = getattr(node, "GetMTime", None)
    if getter is None:
        return 0
    try:
        return int(getter())
    except Exception:  # pragma: no cover - defensive
        return 0


# --------------------------------------------------------------------------- #
# Pipeline-creator registration — ADR-0013 §5 call 3
# --------------------------------------------------------------------------- #


_REGISTERED = False


def registerPipelineCreator() -> None:
    """Register the ``LiverBezierSurfacePipeline`` creator with LayerDM.

    Idempotent via the module-level ``_REGISTERED`` flag.  The
    upstream ``vtkMRMLLayerDMPipelineFactory::ContainsPipelineCreator``
    compares creators by smart-pointer identity, and every call to
    this function constructs a *fresh*
    ``vtkMRMLLayerDMPipelineScriptedCreator``; without a guard, a
    second ``setup()`` invocation (module reload, Slicer restart in
    embedded contexts) would append a duplicate creator.  The flag
    keeps the public contract — "safe to call from
    ``qSlicerLiverResectionsModule::setup()`` on every module load" —
    intact at the Python layer.

    The creator returns a fresh ``LiverBezierSurfacePipeline``
    instance only when the (viewNode, node) pair matches
    ``(vtkMRMLViewNode, vtkMRMLParametricSurfaceDisplayNode)``.  Other
    combinations short-circuit to ``None`` so subsequent registered
    creators get a chance to handle them.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    # Imports deferred so this module remains importable in plain
    # Python (tests use ``pytest.importorskip("LayerDMLib")`` already;
    # the additional ``slicer``-prefixed symbols below are only
    # reachable inside a Slicer process).
    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLParametricSurfaceDisplayNode,
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLViewNode,
    )

    def tryCreate(viewNode, node):
        # 3D-only gating per the Path-B scoping in T2 (slice-view
        # rendering of vtkMRMLBezierSurfaceNode is deferred — the
        # Bezier surface intersected with a slice plane is a contour,
        # not a surface; that representation lives on its own task
        # (T2.6-DM-2D follow-up, paired with T2.3 slice-aware widget
        # work).  ``vtkMRMLLayerDisplayableManager::RegisterInDefaultViews``
        # registers in both 3D and slice factories, so this creator is
        # invoked for slice-view nodes too — we short-circuit to None
        # there so other registered creators (or no creator at all)
        # handle the slice path.
        if not isinstance(viewNode, vtkMRMLViewNode):
            return None
        if not isinstance(node, vtkMRMLParametricSurfaceDisplayNode):
            return None
        return LiverBezierSurfacePipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
    _REGISTERED = True
