# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Interactive baseline-capture driver for the LiverResections visual-regression suite.

Run from a terminal::

    Slicer --no-main-window \\
           --python-script LiverResections/Testing/Python/capture_baseline.py \\
           --test BezierSurface4x4Planning

The driver:

1. Imports the scenario module (``scenarios.<test>``).
2. Calls ``setup_scene()`` to populate the MRML scene.
3. Calls ``setup_camera()`` + ``setup_viewport()`` to fix the render
   geometry.
4. Renders the scene into a Qt window using the LayerDM-aware
   ``qMRMLThreeDView`` widget.
5. Listens for keypress events:

   - ``s``  save the bundle to ``Testing/baselines-staging/<test>.*``
            (.png + .mrml + .camera.json + .viewport.json) and print a
            single-line "next step" hint with the upload-script
            invocation.
   - ``q``  quit without saving.

The capture flow is **user-launched**, not agent-orchestrated.  A
human reviewer presses ``s`` only after visually confirming the scene
matches the spec for that scenario.

References
----------
* ADR-0003 — characterisation-test invariant.
* ADR-0020 §"Rollout plan" §7 — capture-then-replay workflow.
"""

from __future__ import annotations

import argparse
import faulthandler
import importlib
import json
import pathlib
import sys

# Install a SIGSEGV / SIGABRT handler that dumps a C stack trace to
# stderr before the process dies — invaluable when debugging crashes in
# the bezier mapper's GL texture upload that yield no Python traceback.
# Use the raw stderr file descriptor (fd 2): Slicer's ``--python-script``
# replaces ``sys.stderr`` with ``PythonQtStdOutRedirect`` which lacks
# ``fileno()``, so passing ``sys.stderr`` to ``faulthandler.enable``
# raises ``AttributeError``.
import os as _os
faulthandler.enable(file=_os.fdopen(2, "w", buffering=1, closefd=False), all_threads=True)

# noqa: E402 — these imports deliberately follow ``faulthandler.enable``
# above so that any segfault thrown during Qt/Slicer/VTK module load is
# caught by the handler and printed to stderr.  Ruff's "module imports
# at top of file" rule does not encode this ordering requirement.
import qt  # type: ignore[import-not-found]  # noqa: E402
import slicer  # type: ignore[import-not-found]  # noqa: E402
import vtk  # type: ignore[import-not-found]  # noqa: E402


def _parse_argv() -> argparse.Namespace:
    """Slice out the ``--`` separated args that Slicer's launcher
    forwards to the python script.

    Slicer-launcher arg conventions: a single ``--`` separates
    launcher arguments from script arguments.  Everything after
    ``--`` lands in ``sys.argv``.
    """
    parser = argparse.ArgumentParser(
        description="Capture a visual-regression baseline for a Slicer-Liver scenario."
    )
    parser.add_argument(
        "--test",
        required=True,
        help=(
            "Name of the scenario module under "
            "LiverResections/Testing/Python/scenarios/ "
            "(e.g. BezierSurface4x4Planning)."
        ),
    )
    parser.add_argument(
        "--staging-dir",
        default=None,
        help=(
            "Directory to write the staged bundle into.  Defaults to "
            "<repo>/Testing/baselines-staging/ if the script is invoked "
            "from a Slicer-Liver source checkout."
        ),
    )
    # Drop everything up to the first '--' (the launcher's own argv).
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        argv = sys.argv[idx + 1 :]
    else:
        argv = sys.argv[1:]
    return parser.parse_args(argv)


def _default_staging_dir() -> pathlib.Path:
    """Locate ``<repo>/Testing/baselines-staging/`` relative to this script.

    Layout: this file lives at
    ``LiverResections/Testing/Python/capture_baseline.py``; walk up
    three levels to the repo root, then drop into ``Testing/``.
    """
    here = pathlib.Path(__file__).resolve()
    repo_root = here.parents[3]
    return repo_root / "Testing" / "baselines-staging"


def _load_scenario(name: str):
    """Import ``scenarios.<name>`` from this package.

    The script may be invoked outside of a normal package context
    (``Slicer --python-script <abs path>``); add the package's parent
    to ``sys.path`` so the relative import succeeds.
    """
    # This file lives at ``LiverResections/Testing/Python/``; the scenario
    # package path is ``Python.scenarios.<name>`` (``Python/`` carries an
    # ``__init__.py``).  For that dotted import to resolve, the directory
    # CONTAINING ``Python/`` -- i.e. ``LiverResections/Testing`` -- must be
    # on ``sys.path``.
    here = pathlib.Path(__file__).resolve().parent
    testing_dir = str(here.parent)  # LiverResections/Testing/
    if testing_dir not in sys.path:
        sys.path.insert(0, testing_dir)
    return importlib.import_module(f"Python.scenarios.{name}")


def _live_renderer(view_widget):
    """Return the first ``vtkRenderer`` of the view widget's render window.

    ``qMRMLThreeDView.renderer()`` is C++-only — not exposed through
    PythonQt — so we reach the renderer through the render-window's
    renderer collection, which is plain VTK and fully wrapped.
    """
    return view_widget.threeDView().renderWindow().GetRenderers().GetFirstRenderer()


def _live_camera(view_widget):
    """Return the VTK camera the view widget actually renders with.

    In ``--no-main-window`` mode the standalone ``qMRMLThreeDWidget`` is
    not bound to an MRML camera node by the layout manager, so the
    ``vtkMRMLCameraNode`` ``setup_camera`` configures is orphaned.  The
    renderer's active VTK camera is the only authoritative source for
    what was actually drawn.
    """
    return _live_renderer(view_widget).GetActiveCamera()


def _serialise_camera(view_node, view_widget) -> dict:
    """Read the live ``vtkCamera`` state into a plain JSON-ready dict."""
    cam = _live_camera(view_widget)
    return {
        "position": list(cam.GetPosition()),
        "focal_point": list(cam.GetFocalPoint()),
        "view_up": list(cam.GetViewUp()),
        "parallel_scale": cam.GetParallelScale(),
        "view_angle": cam.GetViewAngle(),
        "clipping_range": list(cam.GetClippingRange()),
    }


def _serialise_viewport(view_node, view_widget) -> dict:
    """Capture deterministic render-window state into a dict."""
    size = view_widget.size
    renderer = _live_renderer(view_widget)
    background = list(renderer.GetBackground())
    return {
        "size": [int(size.width()), int(size.height())],
        "background": background,
        "anti_aliasing_frames": int(
            view_widget.threeDView().renderWindow().GetMultiSamples()
        ),
    }


def _apply_camera_to_live_view(view_widget, camera_spec: dict) -> None:
    """Write the deterministic camera pose to the renderer's VTK camera.

    The standalone ``qMRMLThreeDWidget`` does not honour MRML camera-
    node mutations (no layout manager glue), so the scenario's
    ``setup_camera(view_node)`` only configures an orphan MRML node.
    Capture must write to the live VTK camera directly for the render
    pose to match the scenario spec.
    """
    cam = _live_camera(view_widget)
    cam.SetPosition(*camera_spec["position"])
    cam.SetFocalPoint(*camera_spec["focal_point"])
    cam.SetViewUp(*camera_spec["view_up"])
    cam.SetParallelScale(camera_spec["parallel_scale"])
    cam.SetViewAngle(camera_spec["view_angle"])
    cam.SetClippingRange(*camera_spec["clipping_range"])


def _apply_viewport_to_live_view(view_widget, viewport_spec: dict) -> None:
    """Write background/AA settings to the live renderer + render window.

    Same rationale as ``_apply_camera_to_live_view``: the MRML view-node
    settings the scenario writes are not propagated to the standalone
    widget's renderer.
    """
    renderer = _live_renderer(view_widget)
    renderer.SetBackground(*viewport_spec["background"])
    renderer.SetBackground2(*viewport_spec["background"])
    render_window = view_widget.threeDView().renderWindow()
    render_window.SetMultiSamples(int(viewport_spec["anti_aliasing_frames"]))


def _save_bundle(
    test_name: str,
    staging_dir: pathlib.Path,
    view_node,
    view_widget,
) -> None:
    """Write the 4-file bundle into ``staging_dir``."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    png_path = staging_dir / f"{test_name}.png"
    mrml_path = staging_dir / f"{test_name}.mrml"
    cam_path = staging_dir / f"{test_name}.camera.json"
    vp_path = staging_dir / f"{test_name}.viewport.json"

    # PNG — snapshot the GL back-buffer directly, identical to the
    # source ``replay_test.py::_render_scenario`` will compare against.
    #
    # The previous implementation used ``qt.QPixmap.grabWidget()``,
    # which reads the Qt-composited surface AFTER device-pixel-ratio
    # scaling, freetype glyph rasterisation, and Qt's own surface
    # composition.  Replay uses ``vtkWindowToImageFilter`` straight
    # off the OpenGL render window, so the two pipelines produced
    # different pixels for the same scene — every captured baseline
    # would have been a guaranteed mismatch against any future replay
    # (the textbook "baseline != what replay would produce" bug).
    # Sharing the pixel source between capture and replay means any
    # future delta surfaces as a real regression, not a tooling
    # artefact.
    three_d_view = view_widget.threeDView()
    three_d_view.forceRender()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(three_d_view.renderWindow())
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    # Already-rendered back buffer; do not force a re-render here.
    w2i.SetShouldRerender(0)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(png_path))
    writer.SetInputData(w2i.GetOutput())
    writer.Write()

    # MRML — full scene save.  Saves alongside any referenced data
    # files in the same directory; for the synthetic-parenchyma
    # scenario the data is generated in-memory so the .mrml file
    # alone is enough.
    slicer.util.saveScene(str(mrml_path))

    with cam_path.open("w") as fh:
        json.dump(_serialise_camera(view_node, view_widget), fh, indent=2, sort_keys=True)
    with vp_path.open("w") as fh:
        json.dump(_serialise_viewport(view_node, view_widget), fh, indent=2, sort_keys=True)

    # Single-line "next step" hint, matching the contract described
    # in this PR's README and the task brief.
    print(
        f"saved {test_name} bundle to {staging_dir}; "
        f"next step: ./LiverResections/Testing/Scripts/upload_baseline.sh {test_name}"
    )


class _KeyFilter(qt.QObject):
    """Qt event filter — listens for 's' (save) and 'q' (quit) keys."""

    def __init__(
        self,
        test_name: str,
        staging_dir: pathlib.Path,
        view_node,
        view_widget,
        loop: qt.QEventLoop,
    ) -> None:
        super().__init__()
        self._test_name = test_name
        self._staging_dir = staging_dir
        self._view_node = view_node
        self._view_widget = view_widget
        self._loop = loop

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        if event.type() == qt.QEvent.KeyPress:
            key = event.key()
            if key == qt.Qt.Key_S:
                _save_bundle(
                    self._test_name,
                    self._staging_dir,
                    self._view_node,
                    self._view_widget,
                )
                self._loop.quit()
                return True
            if key == qt.Qt.Key_Q:
                print("quit without saving")
                self._loop.quit()
                return True
        return False


def main() -> int:
    args = _parse_argv()
    staging_dir = pathlib.Path(args.staging_dir) if args.staging_dir else _default_staging_dir()

    scenario = _load_scenario(args.test)
    try:
        scenario.setup_scene()
    except Exception as exc:  # noqa: BLE001 — surface every error
        import traceback
        sys.stderr.write(
            f"FATAL: scenario.setup_scene() raised {type(exc).__name__}: {exc}\n"
        )
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

    # Build the interactive view.  qMRMLThreeDWidget hosts a
    # qMRMLThreeDView which carries the VTK render window through the
    # LayerDM display-manager group.
    layout_manager = slicer.app.layoutManager()
    if layout_manager is None:
        # ``--no-main-window`` boots elide the layout manager; create
        # the widget directly.  This matches trame-slicer's
        # standalone-view pattern.
        view_widget = slicer.qMRMLThreeDWidget()
        view_widget.setMRMLScene(slicer.mrmlScene)
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
        if view_node is None:
            view_node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLViewNode", "VisualCaptureView"
            )
        # Show the widget + force a first render BEFORE binding the
        # view node, so the GL context is initialised and VTK's GL
        # extension loader has resolved ``glGetError`` and friends.
        # ``setMRMLViewNode`` attaches the displayable-manager group
        # to the view's renderer, which immediately fires the bezier
        # representation's ``UpdateFromMRML`` → texture-upload path.
        # That path calls ``vtkOpenGLClearErrorMacro`` (a ``glGetError``
        # drain) at function entry; if the GL function pointers
        # haven't been loaded yet (no render has occurred), the call
        # segfaults on a NULL function pointer.
        # Verified via gdb: SIGSEGV at addr 0x0 inside
        # ``vtkClearOpenGLErrors`` (vtkOpenGLError.h:219), called from
        # ``vtkMultiTextureObjectHelper::CreateSeq3DFromRaw`` line 79.
        view_widget.show()
        view_widget.threeDView().forceRender()
        view_widget.setMRMLViewNode(view_node)
    else:
        view_widget = layout_manager.threeDWidget(0)
        view_node = view_widget.mrmlViewNode()

    # Scenarios driving a standalone VTK Representation (plain actors, not
    # MRML-displayable-manager geometry) expose ``attach_to_renderer`` so
    # their actors land in the live renderer.  The view was shown + force-
    # rendered above, so the GL context is up before the contour mapper
    # touches GL state.  Scenarios that render through MRML display nodes
    # (the Bezier surfaces) omit this hook and are unaffected.
    attach = getattr(scenario, "attach_to_renderer", None)
    if attach is not None:
        attach(_live_renderer(view_widget))

    scenario.setup_camera(view_node)
    scenario.setup_viewport(view_node)

    # In ``--no-main-window`` mode the standalone ``qMRMLThreeDWidget``
    # is not bound to an MRML camera node + a layout manager, so the
    # MRML-side configuration the scenario just performed is orphaned.
    # Push the same fixture values directly onto the live VTK camera +
    # renderer so the captured render matches the spec.
    spec = scenario.describe()
    _apply_camera_to_live_view(view_widget, spec["camera"])
    _apply_viewport_to_live_view(view_widget, spec["viewport"])

    width = spec["viewport"]["size"][0]
    height = spec["viewport"]["size"][1]
    view_widget.resize(width, height)
    view_widget.show()
    view_widget.threeDView().forceRender()

    print(
        f"Visual-baseline capture for {args.test} — "
        f"press 's' to save the bundle, 'q' to quit without saving."
    )

    # Slicer's primary ``QApplication.exec_()`` is already on the
    # stack by the time ``--python-script`` runs.  Re-entering it
    # returns immediately ("event loop is already running").  Use a
    # nested ``QEventLoop`` instead — Qt explicitly supports nesting
    # these, and the key filter calls ``loop.quit()`` to unblock.
    loop = qt.QEventLoop()
    key_filter = _KeyFilter(args.test, staging_dir, view_node, view_widget, loop)
    view_widget.installEventFilter(key_filter)
    qt.QApplication.instance().installEventFilter(key_filter)

    return loop.exec_()


if __name__ == "__main__":
    # See replay_test.py::_exit for the rationale: Slicer's
    # ``--python-script`` interpreter wrapper does not exit the
    # QApplication event loop on plain ``sys.exit``.
    _code = main()
    try:
        import slicer  # type: ignore[import-not-found]

        slicer.util.exit(_code)
    except ImportError:
        sys.exit(_code)
