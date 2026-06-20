# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T3-g3c -- presentation fixes for the auto-populated resectogram drawer.

T3-g3/g3b landed the auto-populated resectogram drawer + an embedded
``qMRMLThreeDWidget`` bound to the singleton resectogram view node
(``test_resectogram_open_view_action.py`` pins those invariants).  But the
embedded view DUPLICATES the shared 3D anatomy scene instead of presenting the
flattened ``(u, v)`` strip alone, and the widget sits left-aligned + letterboxed
in the drawer.  T3-g3c fixes presentation in three planes -- WITHOUT a custom
DisplayableManager (ADR-0013 §5; the ``feedback_layerdm_no_custom_dm`` lesson);
view-node + display-node + layout configuration only.  The trigger throughout
is the SELECTION (no [Open] button -- the maintainer removed it):

  A. DISPLAY-NODE VIEW RESTRICTION (strip into the dedicated view).
     Triggering with the gate satisfied restricts the
     ``vtkMRMLResectogramDisplayNode`` TO the singleton resectogram view -- its
     ViewNodeIDs list is EXACTLY [the resectogram view node ID], via the Slicer
     display-node allowlist (``vtkMRMLDisplayNode::AddViewNodeID`` /
     ``SetViewNodeIDs``; an EMPTY list means "all views", so a non-empty list
     of exactly that one ID is the active restriction -- ADR-0023 §Stage-4).

  B. SELECTED SURFACE RESTRICTED AWAY FROM THE RESECTOGRAM VIEW.
     The SELECTED Bezier surface's own display node(s) are restricted AWAY from
     the resectogram view, so the 3D anatomy of the resection surface does not
     bleed into the flattened strip.  The owned-anatomy restriction:
     ``IsViewNodeIDPresent(resectogramViewID)`` is False on each of the
     surface's display nodes, AND each was ACTIVELY restricted (its ViewNodeIDs
     list is non-empty -- left as the default empty == all-views would still
     show in the resectogram view).  UNKNOWN-anatomy isolation (parenchyma /
     other nodes) is explicitly DEFERRED and NOT asserted here.

  C. CAMERA FRAMING (parallel, looking down the flattened quad).
     After trigger, the resectogram view's ``vtkMRMLCameraNode`` is PARALLEL
     projection (``GetParallelProjection()`` truthy) and its focal point is the
     flattened-quad centre (mirrors ``Resectogram4x4BlurOff.setup_camera``:
     ``CAMERA_FOCAL_POINT``).  The camera lives on the VIEW node (resolved via
     ``slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)``), NOT
     the representation's vestigial ``_resectogram_camera``.  Pinned as a pose
     with tolerance, NOT as pixels (no GL render here).

  D. LAYOUT (the embedded widget fills the panel).
     The embedded ``qMRMLThreeDWidget`` has horizontal size policy Expanding and
     a non-trivial ``minimumHeight``, and is placed in the module panel's grid,
     so it fills the panel width instead of being left-aligned + letterboxed.
     Queryable without a GL render; the embed itself only happens with a main
     window, so this invariant is gated behind ``_require_main_window_or_skip``
     exactly as g3b's embed test is.

All invariants are GPU-FREE (minimal ``qSlicerApplication``, no GL render).
A--C run under the headless launched harness; D needs a main window to embed
(matching g3b).  The strip FILLING the panel against an anatomy backdrop is the
orchestrator's interactive ``:0`` eyeball pass, NOT pinned here (no pixel
assertion).

-- WHY THIS IS A LAUNCHED-SLICER PYTEST (NOT A ctkTest) --

Same reasoning as the g3 action tests: a C++ ctkTest against
``ResectogramViewManager.frameCamera`` / the widget layout cannot COMPILE
before those entry points exist, breaking the RED build.  A Python launched
test SKIPS CLEANLY (no widget rep / no accessor / no ``frameCamera``)
pre-implementation and goes GREEN post (ADR-0027 §Conformance "for skipped
tests, the skip lifts at the implementation commit").

-- IMPLEMENTER CONTRACT (assumed entry points + behaviours) --

  * The open action, on trigger with the gate satisfied:
      - restricts the ``vtkMRMLResectogramDisplayNode`` to the singleton
        resectogram view (ViewNodeIDs == [resectogram view ID]); and
      - restricts the SELECTED surface's display node(s) away from that view
        (each made non-empty AND not containing the resectogram view ID).
  * ``ResectogramViewManager.frameCamera(viewNode, surface)`` -- a new entry
    point that sets ``viewNode``'s camera node to PARALLEL projection looking
    straight down the flattened (u, v) quad (focal point at the quad centre,
    parallel scale + clipping per the ``Resectogram4x4BlurOff`` pose).  If the
    implementer names it ``configureView`` / folds it into ``ensureViewNode``,
    the camera-state assertion still holds via the camera-node accessor below;
    these tests reach the CAMERA STATE, not the method name.
  * Camera-node accessor: ``slicer.modules.cameras.logic()
    .GetViewActiveCameraNode(viewNode)`` (the standard view->camera
    association; the same accessor the scenario builders use).
  * The embedded ``qMRMLThreeDWidget`` carries horizontal size policy
    ``QSizePolicy::Expanding`` and a non-trivial ``minimumHeight``, and is a
    child of the module panel.  These are queryable on the widget without a GL
    render.

The flattened-quad CENTRE is read from the ``Resectogram4x4BlurOff`` scenario's
``CAMERA_FOCAL_POINT`` so the test, the scenario, and the production framing
agree on one value (ADR-0025 §Context -- the flattened (u, v) image).

See also:
  * Docs/adr/0027-invariant-test-first-v2-implementation.md (red->green)
  * Docs/adr/0023-unified-gui-stage-workflow.md §Stage-4 (the dedicated view)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5 (no custom DM; config only)
  * Docs/adr/0025-locator-architecture.md §Context (flattened (u, v) image)
  * LiverResections/LiverResectionsLib/ResectogramViewManager.py
    (ensureViewNode singleton-by-tag; frameCamera assumed by g3c)
  * LiverResections/Testing/Python/scenarios/Resectogram4x4BlurOff.py
    (gate-satisfied surface builders + the camera pose reused below)
  * LiverResections/Testing/Python/test_resectogram_open_view_action.py
    (the g3/g3b gating + ensure + embed invariants this file extends)
"""

from __future__ import annotations

import pytest

# Reuse the g3 sibling's established helpers verbatim rather than re-inventing
# the harness (the predicate/ensure/embed scaffolding is the shared surface).
from test_resectogram_open_view_action import (
    RESECTOGRAM_DISPLAY_CLASS,
    _accessor_or_skip,
    _make_surface_with_distance_map,
    _purge_resectogram_singleton_view,
    _require_main_window_or_skip,
    _require_populated_or_skip,
    _require_widget_chrome_or_skip,
    _resectogram_three_d_widgets,
    _select_active_resection,
    _slicer_or_skip,
    _widget_or_skip,
)

# Pose tolerance for the camera-framing assertion (mm).  Generous -- the
# invariant is "the camera looks down the flattened quad centre", not a
# sub-millimetre pose match (camera drift is the most common visual-regression
# false positive; this is a coarse "is it framed at all" gate).
_FOCAL_POINT_TOLERANCE_MM = 1.0

# Per-channel tolerance for the white-background assertion.  SetBackgroundColor
# round-trips through float storage, so an exact 1.0 comparison is brittle.
_BACKGROUND_TOLERANCE = 1e-3


# --------------------------------------------------------------------------- #
# Test isolation -- reclaim the resectogram singleton view node after each test.
# Re-declared here (autouse fixtures are module-local) so this file brackets its
# own tests with the same singleton purge the g3 sibling uses; the purge BODY
# (``_purge_resectogram_singleton_view``) is imported above so there is a single
# implementation.
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _drop_resectogram_singleton_view():
    """Reclaim the resectogram singleton view node around each test.

    Mirrors the g3 sibling fixture: ``ensureViewNode()`` mints a
    ``vtkMRMLViewNode`` carrying a MRML ``SingletonTag`` that SURVIVES
    ``vtkMRMLScene.Clear(0)``; purge it both before (defend the precondition
    against an upstream leak) and after (never leak onward).  No-op under bare
    pytest.
    """
    _purge_resectogram_singleton_view()
    yield
    _purge_resectogram_singleton_view()


# --------------------------------------------------------------------------- #
# Shared drive-to-triggered-state helper.
# --------------------------------------------------------------------------- #


def _open_with_gate_satisfied(slicer):
    """Build a gate-satisfied surface and SELECT it (the auto-populate trigger).

    Returns ``(widget, bezier)`` once the drawer has auto-populated.  Skips
    cleanly (explicit, greppable reason -- #460) at every pre-implementation
    gap: no widget rep, no chrome, no accessor, or a drawer that did not
    populate (hint still visible).
    """
    slicer.mrmlScene.Clear(0)
    widget = _widget_or_skip(slicer)
    combo, hint = _require_widget_chrome_or_skip(widget)

    bezier = _make_surface_with_distance_map(slicer)
    _accessor_or_skip(bezier)
    if not _select_active_resection(widget, combo, bezier):
        pytest.skip("cannot select the active resection (implementer contract).")
    _require_populated_or_skip(hint)
    return widget, bezier


def _resectogram_view_node(slicer):
    """Return the singleton resectogram view node, or skip cleanly."""
    try:
        from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
            ResectogramViewManager,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "ResectogramViewManager not importable "
            f"({exc!r}) -- cannot resolve the singleton resectogram view node "
            "(ADR-0023 §Stage-4)."
        )
    view = ResectogramViewManager()._find_tagged_view_node(slicer)
    if view is None:
        pytest.skip(
            "no resectogram-tagged view node in the scene after trigger -- the "
            "view-node ensure path is not yet wired (covered by "
            "test_resectogram_open_view_action.py)."
        )
    return view


def _resectogram_display_nodes(bezier):
    """Return the ``vtkMRMLResectogramDisplayNode``s referenced by ``bezier``."""
    nodes = []
    for index in range(bezier.GetNumberOfDisplayNodes()):
        display = bezier.GetNthDisplayNode(index)
        if display is not None and display.IsA(RESECTOGRAM_DISPLAY_CLASS):
            nodes.append(display)
    return nodes


def _surface_anatomy_display_nodes(bezier):
    """Return the surface's NON-resectogram display node(s).

    These are the surface's own 3D-anatomy display nodes (the markups display
    node etc.) that invariant B restricts AWAY from the resectogram view.
    """
    nodes = []
    for index in range(bezier.GetNumberOfDisplayNodes()):
        display = bezier.GetNthDisplayNode(index)
        if display is not None and not display.IsA(RESECTOGRAM_DISPLAY_CLASS):
            nodes.append(display)
    return nodes


def _view_node_ids(display):
    """Return ``display``'s ViewNodeIDs as a Python list of strings.

    Uses the wrapper-stable count + Nth accessors
    (``GetNumberOfViewNodeIDs`` / ``GetNthViewNodeID``) rather than
    ``GetViewNodeIDs()`` (which returns a ``std::vector<std::string>`` that does
    not always wrap cleanly through the Python layer).
    """
    return [
        display.GetNthViewNodeID(i)
        for i in range(display.GetNumberOfViewNodeIDs())
    ]


# --------------------------------------------------------------------------- #
# Invariant A -- the resectogram strip's display node is bound to the
# dedicated view (ViewNodeIDs == [resectogram view ID]).
# --------------------------------------------------------------------------- #


def test_trigger_restricts_resectogram_display_node_to_resectogram_view():
    """After trigger, the strip display node is restricted TO the dedicated view.

    ADR-0023 §Stage-4: the open action restricts the
    ``vtkMRMLResectogramDisplayNode`` to the singleton resectogram view via the
    Slicer display-node allowlist (``AddViewNodeID`` / ``SetViewNodeIDs``).  Its
    ViewNodeIDs list is EXACTLY [the resectogram view node ID] -- a non-empty
    list (empty == all views) carrying that one ID.  RED today: g3/g3b ensure
    the display node but do not restrict it, so it stays default-all-views.
    """
    slicer = _slicer_or_skip()
    _, bezier = _open_with_gate_satisfied(slicer)
    view = _resectogram_view_node(slicer)

    displays = _resectogram_display_nodes(bezier)
    assert len(displays) == 1, (
        "expected exactly one resectogram display node after trigger (got "
        f"{len(displays)}) -- the ensure path is covered by "
        "test_resectogram_open_view_action.py."
    )
    ids = _view_node_ids(displays[0])

    assert ids == [view.GetID()], (
        "the resectogram display node must be restricted TO the singleton "
        f"resectogram view: ViewNodeIDs must be exactly [{view.GetID()!r}], got "
        f"{ids!r}.  An EMPTY list means 'all views' (no restriction); the "
        "g3c open action must call AddViewNodeID / SetViewNodeIDs so the "
        "flattened strip composites into the dedicated view alone "
        "(ADR-0023 §Stage-4; ADR-0013 §5 -- config, no custom DM)."
    )


# --------------------------------------------------------------------------- #
# Invariant B -- the selected surface's own display node(s) are restricted
# AWAY from the resectogram view (owned-anatomy restriction).
# --------------------------------------------------------------------------- #


def test_trigger_restricts_selected_surface_away_from_resectogram_view():
    """After trigger, the selected surface's display nodes exclude the dedicated view.

    ADR-0023 §Stage-4 (owned-anatomy restriction): the SELECTED Bezier surface's
    own display node(s) must NOT show in the resectogram view, so the resection
    surface's 3D anatomy does not bleed into the flattened strip.  Precise
    contract: for each surface display node, the resectogram view ID is ABSENT
    from its ViewNodeIDs AND its ViewNodeIDs list is NON-EMPTY (actively
    restricted -- a default empty list == all-views would still draw in the
    resectogram view).  UNKNOWN-anatomy isolation (parenchyma / other nodes) is
    DEFERRED and not asserted here.  RED today: g3/g3b leave the surface display
    nodes at default-all-views.
    """
    slicer = _slicer_or_skip()
    _, bezier = _open_with_gate_satisfied(slicer)
    view = _resectogram_view_node(slicer)
    view_id = view.GetID()

    anatomy_displays = _surface_anatomy_display_nodes(bezier)
    assert anatomy_displays, (
        "the selected Bezier surface must carry at least one non-resectogram "
        "(3D-anatomy) display node for the owned-anatomy restriction to apply "
        "-- the gate-satisfied fixture builds one via CreateDefaultDisplayNodes."
    )

    for display in anatomy_displays:
        ids = _view_node_ids(display)
        assert not display.IsViewNodeIDPresent(view_id), (
            "the selected surface's anatomy display node "
            f"({display.GetID()!r}) must NOT include the resectogram view "
            f"({view_id!r}) in its ViewNodeIDs ({ids!r}) -- it must be "
            "restricted AWAY so the resection surface does not bleed into the "
            "flattened strip (ADR-0023 §Stage-4 owned-anatomy restriction)."
        )
        assert ids, (
            "the selected surface's anatomy display node "
            f"({display.GetID()!r}) must be ACTIVELY restricted (non-empty "
            "ViewNodeIDs): a default EMPTY list means 'all views', which would "
            "still draw the surface in the resectogram view.  The g3c open "
            "action must call AddViewNodeID / SetViewNodeIDs to scope it to the "
            "anatomy views only (ADR-0023 §Stage-4)."
        )


# --------------------------------------------------------------------------- #
# Invariant C -- the resectogram view's camera is framed (parallel, looking
# down the flattened quad centre).
# --------------------------------------------------------------------------- #


def test_trigger_frames_resectogram_view_camera_parallel_down_quad():
    """After trigger, the resectogram view camera is parallel + framed on the quad.

    ADR-0023 §Stage-4 + ADR-0025 §Context: the open action frames the dedicated
    view's ``vtkMRMLCameraNode`` to PARALLEL projection looking straight down the
    flattened (u, v) quad (mirroring ``Resectogram4x4BlurOff.setup_camera``).
    Two pinned facts, GPU-free: ``GetParallelProjection()`` is truthy, and the
    focal point is the flattened-quad centre (the scenario's CAMERA_FOCAL_POINT)
    within tolerance.  The camera lives on the VIEW node (resolved via the
    cameras-logic accessor), NOT the representation's vestigial
    ``_resectogram_camera``.  RED today: g3/g3b do not frame the camera, so it
    keeps the default 3D-anatomy pose.
    """
    slicer = _slicer_or_skip()
    cameras_module = getattr(slicer.modules, "cameras", None)
    if cameras_module is None:
        pytest.skip(
            "the 'cameras' module is not registered -- cannot resolve the "
            "resectogram view's camera node via GetViewActiveCameraNode "
            "(ADR-0023 §Stage-4)."
        )

    _, _bezier = _open_with_gate_satisfied(slicer)
    view = _resectogram_view_node(slicer)

    camera_node = slicer.modules.cameras.logic().GetViewActiveCameraNode(view)
    if camera_node is None:
        pytest.skip(
            "no camera node associated with the resectogram view after "
            "trigger -- the g3c frameCamera path is not yet wired (it must set "
            "the view's vtkMRMLCameraNode; ADR-0023 §Stage-4)."
        )

    assert camera_node.GetParallelProjection(), (
        "the resectogram view camera must use PARALLEL projection (the "
        "flattened (u, v) strip is a 2D image; a perspective view distorts it) "
        "-- ADR-0025 §Context, mirroring Resectogram4x4BlurOff.setup_camera.  "
        "g3c must call SetParallelProjection(1) in the frameCamera path."
    )

    # The flattened-quad centre -- read from the scenario so the test, the
    # scenario, and the production framing agree on one value.
    from scenarios import Resectogram4x4BlurOff as scn  # type: ignore[import-not-found]

    expected_focal = scn.CAMERA_FOCAL_POINT
    focal = camera_node.GetFocalPoint()
    for axis, (got, want) in enumerate(zip(focal, expected_focal)):
        assert abs(got - want) <= _FOCAL_POINT_TOLERANCE_MM, (
            "the resectogram view camera focal point must sit at the flattened-"
            f"quad centre {tuple(expected_focal)!r} (axis {axis}: got {got}, "
            f"want {want}, tol {_FOCAL_POINT_TOLERANCE_MM} mm) so the camera "
            "looks straight down the quad -- ADR-0023 §Stage-4, mirroring "
            "Resectogram4x4BlurOff.setup_camera (CAMERA_FOCAL_POINT)."
        )


# --------------------------------------------------------------------------- #
# Invariant D -- the embedded qMRMLThreeDWidget fills the panel (layout).
# Gated behind a main window, exactly as g3b's embed test is.
# --------------------------------------------------------------------------- #

# Minimum height the embedded view widget must reserve so it reads as a square-
# ish strip panel rather than a letterboxed sliver.  The exact value is the
# implementer's call; the invariant is "non-trivial", so a conservative floor.
_MIN_EMBEDDED_HEIGHT_PX = 100


def test_embedded_three_d_widget_expands_to_fill_panel():
    """The embedded resectogram view widget fills the panel width (layout fix).

    ADR-0023 §Stage-4: g3c places the embedded ``qMRMLThreeDWidget`` with an
    explicit grid placement, ``QSizePolicy::Expanding`` horizontal policy, and a
    non-trivial ``minimumHeight`` (and drops the competing outer vertical
    spacer), so it fills the panel instead of being left-aligned + letterboxed.
    Queryable without a GL render -- pins the size policy + minimum height, NOT
    pixels (the strip filling the panel is the orchestrator's eyeball pass).

    Gated behind a main window like g3b's embed test: the embed (binding the
    view node to the widget) uploads the distance-map 3D texture, which needs a
    realized GL context.  Skips cleanly under the ``--no-main-window`` launched
    harness (#460 explicit-skip lesson).  RED today: g3b embeds the widget
    left-aligned + letterboxed without the Expanding policy.
    """
    import qt  # type: ignore[import-not-found]

    slicer = _slicer_or_skip()
    _require_main_window_or_skip(slicer)
    widget, _bezier = _open_with_gate_satisfied(slicer)

    embedded = _resectogram_three_d_widgets(slicer, widget)
    assert len(embedded) == 1, (
        "expected exactly one embedded qMRMLThreeDWidget after trigger (got "
        f"{len(embedded)}) -- the embed is covered by "
        "test_resectogram_open_view_action.py."
    )
    view_widget = embedded[0]

    policy = view_widget.sizePolicy
    assert policy.horizontalPolicy() == qt.QSizePolicy.Expanding, (
        "the embedded resectogram view widget must have horizontal size policy "
        "QSizePolicy::Expanding so it fills the panel width instead of being "
        f"left-aligned (got {policy.horizontalPolicy()}) -- ADR-0023 §Stage-4 "
        "layout fix."
    )

    assert view_widget.minimumHeight >= _MIN_EMBEDDED_HEIGHT_PX, (
        "the embedded resectogram view widget must reserve a non-trivial "
        f"minimumHeight (>= {_MIN_EMBEDDED_HEIGHT_PX} px) so it reads as a "
        f"square-ish strip panel, not a letterboxed sliver (got "
        f"{view_widget.minimumHeight}) -- ADR-0023 §Stage-4 layout fix."
    )


# --------------------------------------------------------------------------- #
# Invariant E -- the resectogram view node carries a flat WHITE background.
# GPU-free: SetBackgroundColor is a MRML field set inside configureView, read
# by the Slicer layout manager on a maximize.  Decoupled from the visual-
# regression scenario's BLACK background (the arena's interior-lit metrics
# assume black; only the production view goes white).
# --------------------------------------------------------------------------- #


def test_trigger_sets_resectogram_view_node_white_background():
    """After trigger, the resectogram view node's background is flat white.

    ADR-0023 §Stage-4: the production dedicated view reads as a clean 2D image
    on a flat WHITE background.  Both the flat color and the gradient endpoint
    (``BackgroundColor`` / ``BackgroundColor2``) are white so a layout-managed /
    maximized render -- which reads the MRML view node, not the embedded
    renderer -- shows the framed resectogram on white, not the default 3D blue
    gradient.  GPU-free: the field is set in ``configureView``, queryable
    without a render.  DELIBERATELY decoupled from the
    ``Resectogram4x4BlurOff`` scenario's BLACK ``BACKGROUND_RGB`` (the arena's
    interior-lit-fraction metrics assume black).  RED today: the view node keeps
    its default 3D background until the white-background wiring lands.
    """
    slicer = _slicer_or_skip()
    _open_with_gate_satisfied(slicer)
    view = _resectogram_view_node(slicer)

    from LiverResectionsLib.ResectogramViewManager import (  # type: ignore[import-not-found]
        RESECTOGRAM_VIEW_BACKGROUND_RGB,
    )

    for label, background in (
        ("BackgroundColor", view.GetBackgroundColor()),
        ("BackgroundColor2", view.GetBackgroundColor2()),
    ):
        for axis, (got, want) in enumerate(
            zip(background, RESECTOGRAM_VIEW_BACKGROUND_RGB)
        ):
            assert abs(got - want) <= _BACKGROUND_TOLERANCE, (
                f"the resectogram view node's {label} must be the production "
                f"white {tuple(RESECTOGRAM_VIEW_BACKGROUND_RGB)!r} (axis {axis}: "
                f"got {got}, want {want}, tol {_BACKGROUND_TOLERANCE}) so a "
                "layout-managed / maximized render shows the framed resectogram "
                "on white -- ADR-0023 §Stage-4.  This is decoupled from the "
                "scenario's black BACKGROUND_RGB on purpose (the arena's "
                "interior-lit metrics assume black)."
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
