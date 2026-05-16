"""Python unit tests for ``LiverBezierSurfacePipeline`` — T2.2 PR 1.

The Pipeline is pure Python and has no hard dependency on a wrapped
MRML module (per ADR-0013 §1: Pipelines are Python; per ADR-0008 §2:
unit-layer tests have no Slicer / no view).  These tests therefore
drive the Pipeline with **stub** node objects that implement the
minimum API surface the Pipeline reads — ``GetState`` / ``GetInitMode``
on the data node, ``GetMTime`` on every node, and the
``AddObserver`` / ``RemoveObserver`` pair so the Pipeline can attach
its observer plumbing.

The companion C++-wrapped node test
(``test_bezier_surface_node.py``) exercises the real
``vtkMRMLBezierSurfaceNode`` separately; a full workflow-layer test
under ``Testing/Python/workflow/`` lands with T2.6 when the LayerDM
view-manager fixture is wired up.

References
----------
* ADR-0013 §4, §5, §6 — state-aware Pipelines, lifecycle, idempotency.
* ADR-0014 §2 — names the three Representations and their
  state-conditional dispatch.
* ADR-0008 §2 — unit-layer testing discipline.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry — the Pipeline lives under ``LiverResections/Python/``; add
# that directory to ``sys.path`` so ``import LiverBezierSurfacePipeline``
# resolves without depending on a Slicer-built install layout.  Pattern
# matches the sys.path manipulation in ``test_bezier_characterization.py``.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "Python"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Stub nodes — minimum API the Pipeline reads.
# --------------------------------------------------------------------------- #


class _StubObservable:
    """Mimics the bits of ``vtkObject`` the Pipeline calls."""

    def __init__(self) -> None:
        self._observers: dict[int, callable] = {}
        self._next_tag = 1
        self._mtime = 1

    def AddObserver(self, event: str, callback) -> int:  # noqa: D401 - VTK verb
        tag = self._next_tag
        self._next_tag += 1
        self._observers[tag] = callback
        return tag

    def RemoveObserver(self, tag: int) -> None:
        self._observers.pop(tag, None)

    def Modified(self) -> None:
        self._mtime += 1
        for cb in list(self._observers.values()):
            cb(self, "ModifiedEvent")

    def GetMTime(self) -> int:
        return self._mtime


class _StubDataNode(_StubObservable):
    """Stub for ``vtkMRMLBezierSurfaceNode``."""

    def __init__(
        self,
        state: int = 0,  # Init
        init_mode: int = 0,  # SlicingPlane
        control_grid: tuple = (0.0,) * 48,
    ) -> None:
        super().__init__()
        self._state = state
        self._init_mode = init_mode
        self._control_grid = control_grid

    def GetState(self) -> int:
        return self._state

    def SetState(self, state: int) -> None:
        if state == self._state:
            return
        self._state = state
        self.Modified()

    def GetInitMode(self) -> int:
        return self._init_mode

    def SetInitMode(self, mode: int) -> None:
        if mode == self._init_mode:
            return
        self._init_mode = mode
        self.Modified()

    def GetControlGrid(self):
        return self._control_grid

    def SetControlGrid(self, values) -> None:
        self._control_grid = tuple(values)
        self.Modified()


class _StubDisplayNode(_StubObservable):
    """Stub for ``vtkMRMLBezierSurfaceDisplayNode``."""

    def __init__(
        self,
        color: tuple = (1.0, 1.0, 1.0),
        opacity: float = 1.0,
        grid_visibility: bool = False,
    ) -> None:
        super().__init__()
        self._color = color
        self._opacity = opacity
        self._grid_visibility = grid_visibility

    def GetResectionColor(self):
        return self._color

    def SetResectionColor(self, color) -> None:
        self._color = tuple(color)
        self.Modified()

    def GetResectionOpacity(self) -> float:
        return self._opacity

    def SetResectionOpacity(self, opacity: float) -> None:
        self._opacity = float(opacity)
        self.Modified()

    def GetGridVisibility(self) -> bool:
        return self._grid_visibility

    def SetGridVisibility(self, visible: bool) -> None:
        self._grid_visibility = bool(visible)
        self.Modified()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def pipeline_module():
    """Import the Pipeline module under test."""
    import LiverBezierSurfacePipeline as mod

    return mod


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def test_pipeline_constructs_with_data_node_only(pipeline_module):
    """Construct Pipeline with a data node, no display node, no scene.

    Per ADR-0013 §5 the Pipeline is normally created by the LayerDM
    manager once both nodes are in the scene; tolerating a partial
    wiring at construction time keeps the standalone-instantiation
    path (used by these unit tests and by T2.6's direct registration)
    simple.
    """
    data = _StubDataNode()
    pipeline = pipeline_module.LiverBezierSurfacePipeline(data_node=data)

    assert pipeline.GetDataNode() is data
    assert pipeline.GetDisplayNode() is None
    assert pipeline.GetResectionNode() is None
    pipeline.cleanup()


def test_pipeline_rejects_none_data_node(pipeline_module):
    """ValueError when constructed without a data node (defensive)."""
    with pytest.raises(ValueError):
        pipeline_module.LiverBezierSurfacePipeline(data_node=None)


def test_pipeline_attaches_observers_when_full_node_set_supplied(
    pipeline_module,
):
    """Construct with data + display + resection → observers on all three.

    The implementation detail (the observer-tags dict) is internal to
    the Pipeline; this test reads it directly because the observable
    side-effect (``update()`` fires on any node mutation) is the
    contract under test below in ``test_pipeline_dispatches_*``.
    """
    data = _StubDataNode()
    display = _StubDisplayNode()
    resection = _StubObservable()

    pipeline = pipeline_module.LiverBezierSurfacePipeline(
        data_node=data,
        display_node=display,
        resection_node=resection,
    )

    # Three distinct ids() observed.
    assert len(pipeline._observer_tags) == 3  # noqa: SLF001 - internal
    pipeline.cleanup()
    assert len(pipeline._observer_tags) == 0  # noqa: SLF001 - internal


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def test_pipeline_dispatches_to_bezier_planning_on_state_planning(
    pipeline_module,
):
    """Mutate state Init→Planning → ``BezierPlanning`` becomes active.

    The Init Representations are not populated in this PR (skeleton —
    two follow-up PRs will land them), so this test exercises the
    one wired-up dispatch edge.
    """
    data = _StubDataNode(state=pipeline_module.STATE_INIT)
    display = _StubDisplayNode()
    pipeline = pipeline_module.LiverBezierSurfacePipeline(
        data_node=data, display_node=display
    )

    # Before Init→Planning, dispatch resolves to the SlicingPlaneInit
    # slot — which is None in this PR.  ``update()`` runs but no
    # active Representation is set.
    pipeline.update()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_SLICING_PLANE_INIT
    )

    # Transition the state machine.
    data.SetState(pipeline_module.STATE_PLANNING)
    # The observer fires update() automatically on Modified.
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_BEZIER_PLANNING
    )

    pipeline.cleanup()


def test_pipeline_dispatches_distance_spheroid_init_when_mode_set(
    pipeline_module,
):
    """When state=Init and mode=DistanceSpheroid, that slot wins dispatch.

    The slot is None in this PR; this test pins the dispatch *key*
    selection (``_select_representation``) so the follow-up PRs that
    populate the slot do not have to re-design the table.
    """
    data = _StubDataNode(
        state=pipeline_module.STATE_INIT,
        init_mode=pipeline_module.INIT_MODE_DISTANCE_SPHEROID,
    )
    pipeline = pipeline_module.LiverBezierSurfacePipeline(data_node=data)
    pipeline.update()
    assert pipeline.GetCurrentRepresentationName() == (
        pipeline_module.REPRESENTATION_DISTANCE_SPHEROID_INIT
    )
    pipeline.cleanup()


def test_pipeline_update_is_idempotent(pipeline_module):
    """Calling update() twice with no node mutation is a no-op.

    Per ADR-0013 §3 the ``update()`` contract is idempotent.  The
    Pipeline memoises (state, mode, mtimes); the second call hits
    the short-circuit and does NOT advance the update counter.
    """
    data = _StubDataNode(state=pipeline_module.STATE_PLANNING)
    display = _StubDisplayNode()
    pipeline = pipeline_module.LiverBezierSurfacePipeline(
        data_node=data, display_node=display
    )

    # The constructor wired an observer on ``data`` which will not
    # fire until something mutates.  Manually invoke update() once
    # to capture the baseline counter.
    pipeline.update()
    first = pipeline.GetUpdateCount()

    pipeline.update()
    second = pipeline.GetUpdateCount()

    assert second == first, "update() must be idempotent on no-change"
    pipeline.cleanup()


def test_pipeline_update_advances_on_node_modification(pipeline_module):
    """Mutating a node's MTime invalidates the memo and update() runs.

    Inverse of the idempotency test above — exercises the failure
    mode the memoisation defends against.
    """
    data = _StubDataNode(state=pipeline_module.STATE_PLANNING)
    pipeline = pipeline_module.LiverBezierSurfacePipeline(data_node=data)
    pipeline.update()
    baseline = pipeline.GetUpdateCount()

    # Real mutation — the SetState path bumps MTime and re-emits the
    # observer callback; the Pipeline runs update() once more.
    data.SetControlGrid([float(i) for i in range(48)])

    assert pipeline.GetUpdateCount() > baseline
    pipeline.cleanup()


# --------------------------------------------------------------------------- #
# Display-node attachment (re-entrant SetDisplayNode)
# --------------------------------------------------------------------------- #


def test_pipeline_swap_display_node_rewires_observer(pipeline_module):
    """Replacing the display node detaches the old observer and attaches
    a new one to the replacement.
    """
    data = _StubDataNode(state=pipeline_module.STATE_PLANNING)
    display1 = _StubDisplayNode()
    pipeline = pipeline_module.LiverBezierSurfacePipeline(
        data_node=data, display_node=display1
    )

    pipeline.update()
    count_after_first_update = pipeline.GetUpdateCount()

    display2 = _StubDisplayNode()
    pipeline.SetDisplayNode(display2)

    # Mutating the OLD display node must NOT fire update().
    display1.SetResectionColor((0.0, 0.0, 0.0))
    assert pipeline.GetUpdateCount() == count_after_first_update

    # Mutating the NEW display node DOES fire update().
    display2.SetResectionColor((0.0, 0.0, 0.0))
    assert pipeline.GetUpdateCount() > count_after_first_update

    pipeline.cleanup()
