"""State-aware LayerDM Pipeline for the Bezier-surface concept.

This is the first concrete instantiation of the LayerDM Pipeline
pattern committed by `ADR-0013`_ §4 and the LiverMarkups dissolution
named by `ADR-0014`_ §2.  One Pipeline observes a
``vtkMRMLBezierSurfaceNode`` (data, ADR-0014 §1), its paired
``vtkMRMLBezierSurfaceDisplayNode`` (decoration, ADR-0013 §8) and —
when wired — the orchestrating ``vtkMRMLLiverResectionNode``'s
``ResectionState`` / ``InitializationMode`` enums (per ADR-0013 §4).
The Pipeline owns three Representations keyed on the
``(state, initMode)`` tuple; ``update()`` activates whichever
Representation matches the current tuple.

Scope of this skeleton — first T2.2 stack iteration
---------------------------------------------------
This is the **first iteration of the T2.2 stack** (Path B scoping;
see the v2.0.0 release tracker).  Only the ``BezierPlanning``
Representation is wired up; the two ``Init``-state Representations
(``SlicingPlaneInit`` and ``DistanceSpheroidInit``) are placeholder
slots with TODO markers and land in the remaining T2.2 iterations.

Out of scope here, per the brief:

* Registration with LayerDM's ``vtkMRMLLayerDMPipelineFactory`` —
  lands in T2.6 alongside ``qSlicerLiverResectionsModule::setup()``
  changes.
* The custom widget ``vtkLiverBezierWidget`` (T2.3).
* The storage class ``vtkMRMLBezierSurfaceStorageNode`` (T2.5).
* Legacy ``vtkMRMLLiverResectionNode`` cleanup (T2.7).

Pipeline base class
-------------------
ADR-0013 §5 names ``vtkMRMLLayerDMScriptedPipeline`` (imported as
``from LayerDMLib import vtkMRMLLayerDMScriptedPipeline``) as the
canonical base.  That dependency is not yet present in the
Slicer-Liver build environment (LayerDMLib lands with T2.6's module
registration work).  This file therefore defines a small abstract
base class ``LayerDMScriptedPipelineBase`` that mirrors the contract
ADR-0013 §5 documents (``initialize`` / ``update`` / ``cleanup``,
renderer handle, manager-driven creation) and is unit-testable in
isolation.  When LayerDMLib becomes importable, T2.6 will swap the
base class out for the real one — the call surface is intentionally
identical.

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

All three callbacks route into ``update()``.  See ADR-0013 §4 for
the rationale: the orchestrating-state node's ``ResectionState`` /
``InitializationMode`` enums drive Representation dispatch.

Idempotency
-----------
``update()`` memoises the (state, initMode, dataMTime, displayMTime)
tuple it ran against most recently.  A second call with no
intervening node mutation is a no-op — required by ADR-0013 §3's
``update()`` contract.

References
----------
* `ADR-0011`_ — SCT terminology dispatch (the ``TerminologyEntry``
  field on the display node is the dispatch key for the Pipeline's
  colour / label / badge decisions when populated).
* `ADR-0013`_ — Pipeline pattern (primary spec).
* `ADR-0014`_ — LiverMarkups dissolution (names the three
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
# Pipeline base — soft-import the real LayerDM base when available, fall
# back to a project-local ABC mirroring the same call surface otherwise.
# --------------------------------------------------------------------------- #

try:  # pragma: no cover — exercised inside Slicer with LayerDMLib built
    from LayerDMLib import vtkMRMLLayerDMScriptedPipeline as _PipelineBase

    _USING_LAYER_DM_BASE = True
except ImportError:  # pragma: no cover — pure-Python / not-yet-built path
    _USING_LAYER_DM_BASE = False

    class _PipelineBase:
        """Project-local stand-in for ``vtkMRMLLayerDMScriptedPipeline``.

        Mirrors the lifecycle contract documented in ADR-0013 §5:

        * ``initialize()`` — called once when the Pipeline is constructed
          by the manager.  Subclasses build their Representations here.
        * ``update()`` — called when the data node, display node, or
          orchestrating-state node fires ``ModifiedEvent``.  Must be
          idempotent.
        * ``cleanup()`` — called when the manager destroys the Pipeline.
          Subclasses release observers and detach actors here.
        * ``GetRenderer()`` — returns the renderer the Pipeline draws
          into.  Returns ``None`` in the standalone path; tests inject
          a stub or a real ``vtkRenderer`` as needed.

        T2.6 swaps this out for ``LayerDMLib.vtkMRMLLayerDMScripted
        Pipeline``; the call surface above is the contract that survives
        the swap.  Until then this allows the Pipeline to be exercised
        from direct Python instantiation and unit tests without a Slicer
        runtime.
        """

        def __init__(self) -> None:
            self._renderer: Any | None = None

        def initialize(self) -> None:  # noqa: D401 - LayerDM verb
            """Lifecycle hook — override in subclasses."""

        def update(self) -> None:  # noqa: D401 - LayerDM verb
            """Lifecycle hook — override in subclasses."""

        def cleanup(self) -> None:  # noqa: D401 - LayerDM verb
            """Lifecycle hook — override in subclasses."""

        def SetRenderer(self, renderer: Any) -> None:
            self._renderer = renderer

        def GetRenderer(self) -> Any:
            return self._renderer


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

    Constructor
    -----------
    ``LiverBezierSurfacePipeline(data_node, display_node=None,
    resection_node=None, renderer=None)``

    * ``data_node`` — ``vtkMRMLBezierSurfaceNode`` carrying geometry
      and the local state machine.  Required.
    * ``display_node`` — ``vtkMRMLBezierSurfaceDisplayNode`` carrying
      decoration.  Optional at construction time (matches the LayerDM
      lifecycle where the display node may be wired up post-init).
    * ``resection_node`` — ``vtkMRMLLiverResectionNode``, the
      orchestrating-state node from ADR-0013 §4.  Optional at this
      stack iteration (T2.6 wires the registration that ensures it
      is present).
    * ``renderer`` — the ``vtkRenderer`` the Pipeline draws into.
      Optional; injected by LayerDM's manager when running inside
      Slicer.

    Lifecycle
    ---------
    Per ADR-0013 §5 the Pipeline is created and destroyed by the
    LayerDM manager (not by hand).  In standalone use (e.g. the
    direct-instantiation unit tests) the caller is responsible for
    ``cleanup()`` to release observers.

    Idempotency
    -----------
    ``update()`` is idempotent: the Pipeline records the
    ``(state, initMode, dataMTime, displayMTime)`` tuple it last ran
    against and short-circuits when nothing has changed.
    """

    def __init__(
        self,
        data_node: Any,
        display_node: Any | None = None,
        resection_node: Any | None = None,
        renderer: Any | None = None,
    ) -> None:
        super().__init__()

        if data_node is None:
            raise ValueError(
                "LiverBezierSurfacePipeline requires a non-None data_node"
            )

        self._data_node = data_node
        self._display_node: Any | None = None
        self._resection_node: Any | None = None

        # Observer tags so cleanup() can detach precisely.
        self._observer_tags: dict[int, list[int]] = {}

        # Memoised dispatch input — see update() for the invariant.
        self._last_update_key: tuple | None = None

        # Update counter — workflow tests assert idempotency by checking
        # this counter does not advance on a no-op update().
        self._update_count: int = 0

        # Representation slots.  Keys match ADR-0014 §2 names.  At this
        # stack iteration only BezierPlanning is constructed; the two
        # Init slots are ``None`` placeholders with TODO markers and
        # land in later T2.2 iterations.
        self._representations: dict[str, Any | None] = {
            REPRESENTATION_SLICING_PLANE_INIT: None,
            REPRESENTATION_DISTANCE_SPHEROID_INIT: None,
            REPRESENTATION_BEZIER_PLANNING: None,
        }

        # The Representation that ``update()`` last activated.  ``None``
        # before the first ``update()``.
        self._current_representation_name: str | None = None

        if renderer is not None:
            self.SetRenderer(renderer)

        self.initialize()

        if display_node is not None:
            self.SetDisplayNode(display_node)
        if resection_node is not None:
            self.SetResectionNode(resection_node)

        # Always observe the data node — geometry + local state machine
        # changes route through update() regardless of whether the
        # display / resection nodes are attached yet.
        self._attach_observer(data_node)

    # ------------------------------------------------------------------ #
    # Lifecycle hooks (override LayerDM contract)
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Construct Representations.

        Per ADR-0013 §6, Representations are constructed once and reused
        across state transitions — no add/remove churn on the MRML scene
        as the surgeon moves through the workflow.

        This iteration wires only ``BezierPlanningRepresentation``.
        The two Init-state Representations land in later T2.2 stack
        iterations.
        """
        # Local import to avoid a circular import when the Representations
        # package grows.  The Representation classes themselves are small
        # and have no Slicer dependency.
        #
        # Two import paths supported:
        #
        # * Package-relative — used when this module is imported as
        #   ``LiverResections.Python.LiverBezierSurfacePipeline`` (the
        #   future install layout, once T2.6 wires the loadable module's
        #   Python install rules).
        # * Top-level — used when this directory has been prepended to
        #   ``sys.path`` directly, which is the convention adopted by
        #   the unit-layer tests under ``Testing/Python/unit/`` (matches
        #   the sys.path manipulation in ``test_bezier_characterization
        #   .py``).
        try:  # pragma: no cover - exercised once per import path
            from .Representations.BezierPlanningRepresentation import (
                BezierPlanningRepresentation,
            )
        except ImportError:
            from Representations.BezierPlanningRepresentation import (  # type: ignore[no-redef]
                BezierPlanningRepresentation,
            )

        self._representations[REPRESENTATION_BEZIER_PLANNING] = (
            BezierPlanningRepresentation(renderer=self.GetRenderer())
        )

        # TODO(T2.2 SlicingPlaneInit): populate slot per ADR-0014 §2.
        #   self._representations[REPRESENTATION_SLICING_PLANE_INIT] = (
        #       SlicingPlaneInitRepresentation(renderer=self.GetRenderer())
        #   )
        # TODO(T2.2 DistanceSpheroidInit): populate slot per ADR-0014 §2.
        #   self._representations[REPRESENTATION_DISTANCE_SPHEROID_INIT] = (
        #       DistanceSpheroidInitRepresentation(renderer=self.GetRenderer())
        #   )

    def update(self) -> None:
        """Dispatch the active Representation by ``(state, initMode)``.

        Idempotent: a second call with no intervening node mutation is
        a no-op observationally — the memoised
        ``(state, initMode, dataMTime, displayMTime)`` key short-circuits
        the work.  Tests assert this by checking ``_update_count`` does
        not advance on the second call.
        """
        # Build the dispatch key.  Falls back to ``0`` MTime for nodes
        # whose ``GetMTime()`` is unavailable (defensive — stub nodes in
        # unit tests may not implement it).
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

    def cleanup(self) -> None:
        """Detach observers and tear down Representations.

        Safe to call multiple times.  Per ADR-0013 §5, normally invoked
        by LayerDM's manager when the display node leaves the scene.
        """
        for node, tag_list in self._observed_nodes_for_cleanup():
            for tag in tag_list:
                try:
                    node.RemoveObserver(tag)
                except Exception:  # pragma: no cover - defensive
                    pass
        self._observer_tags.clear()
        if hasattr(self, "_observed_node_refs"):
            self._observed_node_refs.clear()

        for rep in self._representations.values():
            if rep is not None:
                try:
                    rep.cleanup()
                except Exception:  # pragma: no cover - defensive
                    pass

    # ------------------------------------------------------------------ #
    # Node attachment
    # ------------------------------------------------------------------ #

    def SetDisplayNode(self, display_node: Any) -> None:
        """Attach the display node and start observing it.

        Re-entrant: replaces an already-attached display node and rewires
        the observer.
        """
        if self._display_node is not None:
            self._detach_observer(self._display_node)
        self._display_node = display_node
        if display_node is not None:
            self._attach_observer(display_node)
        # Invalidate the memoised dispatch key — the next ``update()``
        # picks up the new display node.
        self._last_update_key = None

    def GetDisplayNode(self) -> Any | None:
        return self._display_node

    def SetResectionNode(self, resection_node: Any) -> None:
        """Attach the orchestrating-state node (``vtkMRMLLiverResectionNode``).

        Per ADR-0013 §4 the Pipeline's observation set is not limited to
        its own display node — when the displayed concept's behaviour
        depends on a state machine carried by another MRML node, the
        Pipeline observes that node too.
        """
        if self._resection_node is not None:
            self._detach_observer(self._resection_node)
        self._resection_node = resection_node
        if resection_node is not None:
            self._attach_observer(resection_node)
        self._last_update_key = None

    def GetResectionNode(self) -> Any | None:
        return self._resection_node

    def GetDataNode(self) -> Any:
        return self._data_node

    # ------------------------------------------------------------------ #
    # Introspection — used by the unit-layer tests
    # ------------------------------------------------------------------ #

    def GetRepresentation(self, name: str) -> Any | None:
        """Return the Representation registered under ``name`` (or None)."""
        return self._representations.get(name)

    def GetCurrentRepresentationName(self) -> str | None:
        """Return the name of the Representation activated by the last
        ``update()`` — or ``None`` if ``update()`` has not run yet."""
        return self._current_representation_name

    def GetUpdateCount(self) -> int:
        """Total number of ``update()`` calls that did real work
        (short-circuits do not count).  Tests use this to assert
        idempotency."""
        return self._update_count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _select_representation(
        self, state: int | None, init_mode: int | None
    ) -> str | None:
        """Map ``(state, initMode)`` → Representation key per ADR-0014 §2.

        Returns ``None`` when no Representation matches (e.g. an
        unrecognised state value, or the Init Representations have not
        been populated yet at this stack iteration).
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

        Routes the callback into ``update()``.  Stores the observer tag
        so ``cleanup()`` can detach precisely.
        """
        if node is None or not hasattr(node, "AddObserver"):
            return

        # ``AddObserver`` accepts both the integer event id and the
        # string ``"ModifiedEvent"``; the string form is portable across
        # the wrapped MRML modules and pure-VTK stubs alike.
        tag = node.AddObserver("ModifiedEvent", self._on_node_modified)
        # Index by id() — node references hash on object identity in
        # the wrapped VTK Python and would not work as dict keys in some
        # ``vtkObject`` subclasses.  Keep a parallel list of strong refs
        # so the cleanup loop can call ``RemoveObserver`` on them.
        self._observer_tags.setdefault(id(node), []).append(tag)
        if not hasattr(self, "_observed_node_refs"):
            self._observed_node_refs: list[Any] = []
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
        if hasattr(self, "_observed_node_refs"):
            try:
                self._observed_node_refs.remove(node)
            except ValueError:
                pass

    def _observed_nodes_for_cleanup(self):
        """Yield ``(node, tags)`` pairs for every currently-observed node."""
        refs = getattr(self, "_observed_node_refs", [])
        for node in refs:
            yield node, list(self._observer_tags.get(id(node), []))

    def _on_node_modified(self, caller: Any, event: str) -> None:
        """VTK observer callback — re-runs ``update()``.

        Signature matches what VTK passes ``AddObserver`` callbacks:
        ``(caller, event_name_or_id)``.  Both arguments are unused —
        ``update()`` re-reads node state directly.
        """
        del caller, event  # observers route uniformly into update()
        self.update()


# --------------------------------------------------------------------------- #
# Safe accessors — tolerant of stub nodes that omit GetMTime / GetState etc.
# --------------------------------------------------------------------------- #


def _safe_get_state(node: Any) -> int | None:
    """Read ``GetState()`` off ``node`` defensively.

    Returns ``None`` if the node is ``None`` or does not implement
    ``GetState()`` — used by unit tests with partial stub nodes.
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
