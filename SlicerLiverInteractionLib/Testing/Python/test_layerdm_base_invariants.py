# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 -- the four LayerDM integration invariants asserted ONCE on the base.

ADR-0038 §Context + §Conformance [future]: the four LayerDM integration
traps that were paid TWICE (resection, then territories) must be
implemented and fixed ONCE on the shared base, and asserted once here.
The four traps (ADR-0038 §Context, verbatim):

1. ONE Pipeline per ``(view, display-node type)`` -- LayerDM creates
   exactly one Pipeline instance per (view, display-node type); a consumer
   must not spawn a second for the same pair.
2. CONFIGURE-BEFORE-``AddNode`` -- a Pipeline must be configured (provider /
   pick / display node bound) BEFORE its actors are added to the renderer;
   configuring after ``AddNode`` renders stale/empty state.
3. ``UpdatePipeline`` fires on ``ResetDisplay()``, NOT on a display-node
   ``Modified`` -- the reconcile is driven by ``ResetDisplay``; a plain
   ``Modified`` on the display node does not by itself repaint.
4. ``RequestRender`` does NOT flush mid-``ProcessInteractionEvent`` -- a
   render requested inside the interaction handler is coalesced, not
   flushed synchronously; the handler must not assume the view repainted
   before it returns.

These four are the shared LayerDM discipline (the
``feedback_layerdm_state_on_display_node`` / ``feedback_layerdm_pipeline_gotchas``
lessons made structural).  Pinning them on the base means a future fix or
UX tweak applies to every consumer at once (ADR-0038 §Consequences).

HARNESS: launched Slicer.  Every trap needs the real LayerDM machinery
(the Pipeline factory, ``ResetDisplay``, the render window's coalesced
render) reachable only inside a launched Slicer with the LayerDM modules
loaded; a bare ``PythonSlicer -m pytest`` has LayerDMLib off the path, so
every test SKIPS CLEANLY via the ``slicer_pytest_support`` guards.  Verify
run-vs-skip in the CI log -- never trust overall green.

The SUT does not exist yet.  Per ADR-0027 red->skip the import + hasattr
guards skip-pend; the skips lift at the extraction commit.

References
----------
* ADR-0038 -- §Context (the four traps, verbatim) + §Conformance [future]
  ("asserted once on the base").
* ADR-0013 §1 -- one Pipeline per display-node type (trap 1).
* ADR-0032 / ADR-0033 -- interaction seam + the render-flush handler rule.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


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
            "ADR-0038 base has not landed OR LayerDMLib is not reachable here "
            "(ADR-0027)."
        )
    return SurfacePointPlacementPipeline3D


# --------------------------------------------------------------------------- #
# Trap 1 -- one Pipeline per (view, display-node type)
# --------------------------------------------------------------------------- #


@pytest.mark.skip(
    reason=(
        "ADR-0038 trap 1 (one Pipeline per (view, display-node type)) -- the "
        "shared base + a LayerDM factory to count instances per (view, type) "
        "have not landed.  Skeleton pins the invariant; implementer fills the "
        "factory-instance assertion (ADR-0027 / ADR-0013 §1)."
    )
)
def test_one_pipeline_instance_per_view_and_display_node_type():
    """LayerDM creates EXACTLY ONE base Pipeline per (view, display-node type).

    ADR-0038 §Context trap 1 / ADR-0013 §1.  With one display node of a
    consumer's type present and one view, the factory yields exactly one
    base Pipeline instance for that (view, type) pair; adding a second
    display node of the SAME type in the SAME view must not double-register
    the base for the pair.

    TODO(implementer): once the base + the consumer's Pipeline creator land,
    drive a LayerDM view over the display node and assert the manager holds
    exactly one base instance for the (view, type) key -- not one per node,
    not two.
    """
    _slicer_or_skip()
    _import_base_or_skip()
    pytest.fail("unreachable -- test is skipped until the base + factory land.")


# --------------------------------------------------------------------------- #
# Trap 2 -- configure before AddNode
# --------------------------------------------------------------------------- #


@pytest.mark.skip(
    reason=(
        "ADR-0038 trap 2 (configure-before-AddNode) -- the shared base's "
        "actor-add ordering is not landed.  Skeleton pins the invariant; "
        "implementer fills the ordering assertion (ADR-0027)."
    )
)
def test_pipeline_is_configured_before_actors_are_added():
    """A base Pipeline binds its provider/pick/display node BEFORE AddNode.

    ADR-0038 §Context trap 2.  Configuring AFTER the actors are added to the
    renderer renders stale/empty state.  The base's setup order must be:
    bind the seam, THEN add the actors.

    TODO(implementer): assert the base's actors are absent from the renderer
    until the provider is bound, and present (with the provider's points)
    immediately after -- i.e. no window where an added actor lacks its
    configured source.
    """
    _slicer_or_skip()
    _import_base_or_skip()
    pytest.fail("unreachable -- test is skipped until the base lands.")


# --------------------------------------------------------------------------- #
# Trap 3 -- UpdatePipeline fires on ResetDisplay(), not display-Modified
# --------------------------------------------------------------------------- #


@pytest.mark.skip(
    reason=(
        "ADR-0038 trap 3 (UpdatePipeline on ResetDisplay, not display "
        "Modified) -- the shared base's reconcile driver is not landed.  "
        "Skeleton pins the invariant; implementer fills the "
        "ResetDisplay-vs-Modified assertion (ADR-0027)."
    )
)
def test_update_pipeline_is_driven_by_reset_display_not_modified():
    """``UpdatePipeline`` fires on ``ResetDisplay()``, NOT on display Modified.

    ADR-0038 §Context trap 3.  A plain ``Modified()`` on the display node
    must not by itself repaint the base; the reconcile is driven by
    ``ResetDisplay()``.  This is why ``PointPlacementState.set_carrier``
    fires an explicit path that ends in a ResetDisplay-shaped reconcile.

    TODO(implementer): spy the base's ``UpdatePipeline`` (or its reconcile
    hook); assert a bare display-node ``Modified()`` does NOT invoke it,
    while ``ResetDisplay()`` DOES.
    """
    _slicer_or_skip()
    _import_base_or_skip()
    pytest.fail("unreachable -- test is skipped until the base lands.")


# --------------------------------------------------------------------------- #
# Trap 4 -- RequestRender does not flush mid-ProcessInteractionEvent
# --------------------------------------------------------------------------- #


@pytest.mark.skip(
    reason=(
        "ADR-0038 trap 4 (RequestRender does not flush mid-"
        "ProcessInteractionEvent) -- the shared base's interaction handler is "
        "not landed.  Skeleton pins the invariant; implementer fills the "
        "coalesced-render assertion (ADR-0027)."
    )
)
def test_request_render_does_not_flush_inside_process_interaction_event():
    """A render requested inside ``ProcessInteractionEvent`` is COALESCED.

    ADR-0038 §Context trap 4.  The base must not assume the view repainted
    synchronously before the interaction handler returns; ``RequestRender``
    queues a render, it does not flush one mid-event.  A handler relying on
    a synchronous repaint (e.g. reading back a rendered pick) is the defect
    this pins.

    TODO(implementer): spy the render window's Render; assert the count does
    NOT increment during ``ProcessInteractionEvent`` (only after the event
    loop coalesces the queued RequestRender).
    """
    _slicer_or_skip()
    _import_base_or_skip()
    pytest.fail("unreachable -- test is skipped until the base lands.")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
