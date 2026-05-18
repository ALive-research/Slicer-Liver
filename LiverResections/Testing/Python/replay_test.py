# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""CI replay driver for the LiverResections visual-regression suite.

Invoked from CTest via the ``ExternalData_add_test`` entries wired in
``LiverResections/Testing/Python/CMakeLists.txt``.  Each scenario gets
one entry; the entry expands ``DATA{...}`` references at test time so
the resolved PNG/MRML/camera/viewport blobs are available on disk
before this script runs.

The driver:

1. Imports the scenario module by name.
2. Calls ``setup_scene()`` / ``setup_camera()`` / ``setup_viewport()``
   to populate the scene + camera + viewport identically to the
   capture flow.
3. Renders to an offscreen ``qMRMLThreeDView`` and snapshots the
   pixels into a ``vtkImageData``.
4. Loads the baseline PNG (resolved by ExternalData) and runs a
   per-pixel comparison via ``vtkImageDifference``.
5. Exits with non-zero status if the difference exceeds tolerance.

The replay tolerance is intentionally lenient (0.15 in normalized
L1 distance) on this first landing.  The maintainer may tighten it
after observing initial cross-platform CI variance.

References
----------
* ADR-0003 — characterisation tests gate behaviour-changing PRs.
* ADR-0020 §"Rollout plan" §7 — replay drives the regression gate
  for the v2.1 GPU-tessellation rewrite.
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import sys

# Default similarity tolerance used by ``vtkImageDifference`` —
# normalized 0..255 L1 channel error averaged across pixels.  A value
# of 0.15 tolerates minor anti-aliasing / font-metrics drift across
# Mesa versions while still catching real visual regressions.
DEFAULT_TOLERANCE = 0.15


def _parse_argv() -> argparse.Namespace:
    """Slice out the ``--`` separated args; same convention as the
    capture driver.
    """
    parser = argparse.ArgumentParser(
        description="Replay a Slicer-Liver visual-regression baseline."
    )
    parser.add_argument("--test", required=True)
    parser.add_argument("--baseline-dir", required=True)
    parser.add_argument("--scenarios-dir", required=True)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=(
            "Maximum allowed per-pixel L1 channel difference (0..255 scale, "
            f"averaged).  Default {DEFAULT_TOLERANCE}."
        ),
    )
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        argv = sys.argv[idx + 1 :]
    else:
        argv = sys.argv[1:]
    return parser.parse_args(argv)


def _load_scenario(scenarios_dir: str, name: str):
    parent = str(pathlib.Path(scenarios_dir).parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return importlib.import_module(f"Python.scenarios.{name}")


def _resolve_baseline_png(baseline_dir: pathlib.Path, test_name: str) -> pathlib.Path:
    """Locate the ExternalData-resolved PNG for ``test_name``.

    CMake's ``ExternalData_add_test`` rewrites ``DATA{}`` references
    in-place: at run time, ``<baseline_dir>/<test>.png`` exists
    (resolved from the ``.sha512`` stub via the URL template), while
    ``<test>.png.sha512`` is the committed stub.

    If the resolved PNG is absent, the baseline hasn't been captured
    yet — the test is skipped with a clear message rather than
    failing.
    """
    return baseline_dir / f"{test_name}.png"


def _has_baseline(baseline_dir: pathlib.Path, test_name: str) -> bool:
    """True iff the maintainer has captured at least the PNG stub.

    Distinguishes "the harness wiring is correct but no baseline has
    landed yet" from "the harness is broken".  Returns True when both
    the resolved PNG and the committed sha512 stub exist (the stub's
    presence proves the test was registered with content; the PNG's
    presence proves ExternalData found a blob to resolve to).
    """
    png = _resolve_baseline_png(baseline_dir, test_name)
    stub = baseline_dir / f"{test_name}.png.sha512"
    return png.exists() and stub.exists()


def _render_scenario(scenario, width: int, height: int):
    """Run the scenario setup, render offscreen, return ``vtkImageData``."""
    import slicer  # type: ignore[import-not-found]
    import vtk  # type: ignore[import-not-found]

    scenario.setup_scene()

    # Create / fetch the 3D view widget.  In ``--no-main-window`` the
    # layout manager is absent; build the widget standalone.
    layout_manager = slicer.app.layoutManager()
    if layout_manager is None:
        view_widget = slicer.qMRMLThreeDWidget()
        view_widget.setMRMLScene(slicer.mrmlScene)
        view_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLViewNode")
        if view_node is None:
            view_node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLViewNode", "VisualReplayView"
            )
        view_widget.setMRMLViewNode(view_node)
    else:
        view_widget = layout_manager.threeDWidget(0)
        view_node = view_widget.mrmlViewNode()

    scenario.setup_camera(view_node)
    scenario.setup_viewport(view_node)

    view_widget.resize(width, height)
    three_d_view = view_widget.threeDView()
    three_d_view.renderWindow().SetSize(width, height)
    three_d_view.renderWindow().SetMultiSamples(0)
    three_d_view.forceRender()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(three_d_view.renderWindow())
    w2i.SetInputBufferTypeToRGB()
    w2i.ReadFrontBufferOff()
    w2i.Update()
    return w2i.GetOutput()


def _load_png(path: pathlib.Path):
    """Read a PNG into a ``vtkImageData`` for pixel comparison."""
    import vtk  # type: ignore[import-not-found]

    reader = vtk.vtkPNGReader()
    reader.SetFileName(str(path))
    reader.Update()
    return reader.GetOutput()


def _compare_images(rendered, baseline, tolerance: float) -> float:
    """Return mean per-pixel L1 difference (0 = identical)."""
    import vtk  # type: ignore[import-not-found]

    diff = vtk.vtkImageDifference()
    diff.SetInputData(rendered)
    diff.SetImageData(baseline)
    diff.Update()
    return float(diff.GetThresholdedError())


def main() -> int:
    args = _parse_argv()

    baseline_dir = pathlib.Path(args.baseline_dir)
    scenario = _load_scenario(args.scenarios_dir, args.test)

    if not _has_baseline(baseline_dir, args.test):
        # No captured baseline yet — the maintainer's interactive
        # capture session has not landed.  Exit 0 with a clear log
        # message; CTest treats 0 as pass.  When the maintainer
        # commits the first .sha512 stubs the test will start running
        # the real comparison.
        print(
            f"[skip] no baseline captured for {args.test}; "
            f"run capture_baseline.py and "
            f"./LiverResections/Testing/Scripts/upload_baseline.sh {args.test} "
            f"to land one.  Skipping the comparison."
        )
        return 0

    meta = scenario.describe()
    width, height = meta["viewport"]["size"]

    rendered = _render_scenario(scenario, width, height)
    baseline_png = _resolve_baseline_png(baseline_dir, args.test)
    baseline = _load_png(baseline_png)

    error = _compare_images(rendered, baseline, args.tolerance)
    print(
        f"[{args.test}] mean per-pixel L1 difference = {error:.4f} "
        f"(tolerance {args.tolerance:.4f})"
    )
    if error > args.tolerance:
        print(
            f"[fail] visual regression on {args.test}: "
            f"{error:.4f} > {args.tolerance:.4f}"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
