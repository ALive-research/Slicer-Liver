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
import importlib
import json
import pathlib
import sys

import qt  # type: ignore[import-not-found]
import slicer  # type: ignore[import-not-found]


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
    here = pathlib.Path(__file__).resolve().parent
    parent = str(here.parent)  # LiverResections/Testing/
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return importlib.import_module(f"Python.scenarios.{name}")


def _serialise_camera(view_node) -> dict:
    """Read the live ``vtkCamera`` state into a plain JSON-ready dict."""
    cam_logic = slicer.modules.cameras.logic()
    cam_node = cam_logic.GetViewActiveCameraNode(view_node)
    cam = cam_node.GetCamera()
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
    return {
        "size": [int(size.width()), int(size.height())],
        "background": [
            *view_node.GetBackgroundColor(),
        ],
        "anti_aliasing_frames": int(
            view_widget.threeDView().renderWindow().GetMultiSamples()
        ),
    }


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

    # PNG — screenshot of the 3D view, off the same render window as
    # the replay test will hit.
    image = qt.QPixmap.grabWidget(view_widget.threeDView())
    image.save(str(png_path), "PNG")

    # MRML — full scene save.  Saves alongside any referenced data
    # files in the same directory; for the synthetic-parenchyma
    # scenario the data is generated in-memory so the .mrml file
    # alone is enough.
    slicer.util.saveScene(str(mrml_path))

    with cam_path.open("w") as fh:
        json.dump(_serialise_camera(view_node), fh, indent=2, sort_keys=True)
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
    ) -> None:
        super().__init__()
        self._test_name = test_name
        self._staging_dir = staging_dir
        self._view_node = view_node
        self._view_widget = view_widget

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
                return True
            if key == qt.Qt.Key_Q:
                print("quit without saving")
                qt.QApplication.instance().quit()
                return True
        return False


def main() -> int:
    args = _parse_argv()
    staging_dir = pathlib.Path(args.staging_dir) if args.staging_dir else _default_staging_dir()

    scenario = _load_scenario(args.test)
    scenario.setup_scene()

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
        view_widget.setMRMLViewNode(view_node)
    else:
        view_widget = layout_manager.threeDWidget(0)
        view_node = view_widget.mrmlViewNode()

    scenario.setup_camera(view_node)
    scenario.setup_viewport(view_node)

    width = getattr(
        scenario,
        "VIEWPORT_WIDTH",
        scenario.describe()["viewport"]["size"][0],
    )
    height = getattr(
        scenario,
        "VIEWPORT_HEIGHT",
        scenario.describe()["viewport"]["size"][1],
    )
    view_widget.resize(width, height)
    view_widget.show()
    view_widget.threeDView().forceRender()

    print(
        f"Visual-baseline capture for {args.test} — "
        f"press 's' to save the bundle, 'q' to quit without saving."
    )

    key_filter = _KeyFilter(args.test, staging_dir, view_node, view_widget)
    view_widget.installEventFilter(key_filter)
    qt.QApplication.instance().installEventFilter(key_filter)

    # Run the Qt event loop until 'q' or window close.
    return qt.QApplication.instance().exec_()


if __name__ == "__main__":
    sys.exit(main())
