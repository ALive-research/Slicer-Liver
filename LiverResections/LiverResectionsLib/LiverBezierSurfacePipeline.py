# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""State-aware LayerDM Pipeline for the Bezier-surface concept.

This is the first concrete instantiation of the LayerDM Pipeline
pattern committed by `ADR-0013`_ §4 and the LiverMarkups dissolution
named by `ADR-0014`_ §2.  One Pipeline observes a
``vtkMRMLBezierSurfaceNode`` (data, ADR-0014 §1), its paired
``vtkMRMLBezierSurfaceDisplayNode`` (decoration, ADR-0013 §8) and —
when wired — the orchestrating ``vtkMRMLLiverResectionNode``'s
``ResectionState`` / ``InitializationMode`` enums (per ADR-0013 §4).
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
* On the **display node** — ``vtkMRMLBezierSurfaceDisplayNode`` —
  decoration mutations.
* On the **orchestrating-state node** (optional, when wired) —
  ``vtkMRMLLiverResectionNode`` — coarse-grained workflow state
  changes that some Representations gate on.

All three callbacks route into ``UpdatePipeline()``.  See ADR-0013 §4
for the rationale: the orchestrating-state node's ``ResectionState`` /
``InitializationMode`` enums drive Representation dispatch.

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
        }

        # Whether Representations have been constructed yet — guards
        # ``_ensure_representations`` so it runs exactly once.
        self._representations_initialised = False

        # The Representation that ``UpdatePipeline`` last activated.
        # ``None`` before the first ``UpdatePipeline``.
        self._current_representation_name: str | None = None

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

        # Build the dispatch key.  Falls back to ``0`` MTime for nodes
        # whose ``GetMTime`` is unavailable (defensive — stub nodes in
        # tests may not implement it).
        state = _safe_get_state(self._data_node)
        init_mode = _safe_get_init_mode(self._data_node)
        data_mtime = _safe_get_mtime(self._data_node)
        display_mtime = _safe_get_mtime(self._display_node)
        resection_mtime = _safe_get_mtime(self._resection_node)

        key = (state, init_mode, data_mtime, display_mtime, resection_mtime)
        if key == self._last_update_key:
            return  # idempotent short-circuit
        self._last_update_key = key

        active_name = self._select_representation(state, init_mode)
        self._current_representation_name = active_name

        active = self._representations.get(active_name) if active_name else None
        if active is not None:
            active.update(self._display_node, self._data_node)

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
        """Attach the orchestrating-state node (``vtkMRMLLiverResectionNode``).

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

    def GetResectionNode(self) -> Any | None:
        return self._resection_node

    def GetDataNode(self) -> Any | None:
        return self._data_node

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
        """Map ``(state, initMode)`` → Representation key per ADR-0014 §2.

        Returns ``None`` when no Representation matches (e.g. an
        unrecognised state value).
        """
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


def registerPipelineCreator() -> None:
    """Register the ``LiverBezierSurfacePipeline`` creator with LayerDM.

    Idempotent — adding the same creator twice is a no-op in the
    upstream ``vtkMRMLLayerDMPipelineFactory::AddPipelineCreator``
    via the ``ContainsPipelineCreator`` guard.  Safe to call from
    ``qSlicerLiverResectionsModule::setup()`` on every module load.

    The creator returns a fresh ``LiverBezierSurfacePipeline``
    instance only when the (viewNode, node) pair matches
    ``(vtkMRMLViewNode, vtkMRMLBezierSurfaceDisplayNode)``.  Other
    combinations short-circuit to ``None`` so subsequent registered
    creators get a chance to handle them.
    """
    # Imports deferred so this module remains importable in plain
    # Python (tests use ``pytest.importorskip("LayerDMLib")`` already;
    # the additional ``slicer``-prefixed symbols below are only
    # reachable inside a Slicer process).
    from slicer import (  # type: ignore[import-not-found]
        vtkMRMLBezierSurfaceDisplayNode,
        vtkMRMLLayerDMPipelineFactory,
        vtkMRMLLayerDMPipelineScriptedCreator,
        vtkMRMLViewNode,
    )

    def tryCreate(viewNode, node):
        if not isinstance(viewNode, vtkMRMLViewNode):
            return None
        if not isinstance(node, vtkMRMLBezierSurfaceDisplayNode):
            return None
        return LiverBezierSurfacePipeline()

    creator = vtkMRMLLayerDMPipelineScriptedCreator()
    creator.SetPythonCallback(tryCreate)
    vtkMRMLLayerDMPipelineFactory.GetInstance().AddPipelineCreator(creator)
