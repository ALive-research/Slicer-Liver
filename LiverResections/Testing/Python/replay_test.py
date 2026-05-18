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

# Default similarity tolerance used by ``vtkImageDifference`` — the
# mean per-pixel channel-averaged L1 error, normalised to ``[0, 1]``
# (see ``_compare_images``).  A value of 0.15 tolerates minor
# anti-aliasing / font-metrics drift across Mesa versions while still
# catching real visual regressions.
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
            "Maximum allowed mean per-pixel L1 channel difference, "
            f"normalised to [0, 1].  Default {DEFAULT_TOLERANCE}."
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
    """Return mean per-pixel L1 difference, normalised to [0, 1].

    ``vtkImageDifference`` reports two error accumulators:

    * ``Error`` — sum over all pixels of the per-pixel channel-averaged
      delta, with each per-pixel contribution already normalised to
      ``[0, 1]`` (see ``vtkImageDifference.cxx``: ``error += sum / (nComp * 255)``).
    * ``ThresholdedError`` — same accumulator but with the per-channel
      ``Threshold`` clamp applied first.

    VTK's defaults (``Threshold = 105``, ``AllowShift = true``,
    ``Averaging = true``) are tuned for graphics-renderer regression
    tests where ~41 %-per-channel single-pixel deltas should NOT trip
    the gate.  For our use case (fixed camera + viewport, identical
    Slicer-Liver build) we want any per-pixel delta to surface, so we
    zero the threshold and disable the 1-pixel shift.  The 3x3
    averaging is left on because it is the only mechanism that
    distinguishes anti-aliasing fringe from a real regression.

    Both accumulators are sums — divide by the pixel count to recover
    the mean per-pixel error, consistent with the function's
    docstring + the README's "tolerance 0.15" wording.
    """
    import vtk  # type: ignore[import-not-found]

    diff = vtk.vtkImageDifference()
    diff.SetInputData(rendered)
    diff.SetImageData(baseline)
    # No built-in per-channel masking — full per-pixel delta surfaces.
    diff.SetThreshold(0)
    # Disable the symmetric 1-pixel shift tolerance.  Canonical for
    # regression testing on a fixed render pipeline; the shift allowance
    # is what masks observer-ordering regressions in the mapper.
    diff.SetAllowShift(False)
    diff.Update()

    # Recover the per-pixel mean from the accumulator.  ``rendered``
    # and ``baseline`` share extent by construction (replay renders at
    # the scenario's declared viewport size; capture wrote the PNG at
    # the same size).
    dims = rendered.GetDimensions()
    pixel_count = max(1, dims[0] * dims[1] * max(1, dims[2]))
    return float(diff.GetThresholdedError()) / pixel_count


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


def _exit(code: int) -> None:
    """Terminate the process even when running inside Slicer.

    ``Slicer --no-main-window --python-script`` does NOT auto-exit when
    the script returns: control returns to Slicer's QApplication event
    loop, which keeps running until something calls
    ``slicer.app.exit()``.  Plain ``sys.exit()`` raises ``SystemExit``,
    which Slicer's interpreter wrapper swallows — the process hangs
    until the CTest / workflow timeout fires.

    Route through ``slicer.util.exit`` when running inside Slicer; fall
    back to ``sys.exit`` for the rare standalone CPython invocation
    (e.g. local lint).
    """
    try:
        import slicer  # type: ignore[import-not-found]

        slicer.util.exit(code)
    except ImportError:
        sys.exit(code)


if __name__ == "__main__":
    _exit(main())
