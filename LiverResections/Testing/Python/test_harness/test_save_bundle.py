# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Harness self-tests for ``capture_baseline._save_bundle``.

GAP-1 follow-up from PR #384's /slicer-review synthesis (issue #387).

``_save_bundle`` is the heart of the capture flow: on a single 's'
keypress in the capture window it materialises the four-file bundle
(``.png`` + ``.mrml`` + ``.camera.json`` + ``.viewport.json``) into
the staging directory.  The contract documented in
``LiverResections/Testing/README.md`` is:

1. All four sidecars are written.
2. The ``notes.md`` sidecar is NOT written automatically — it stays
   an optional, on-demand human-rationale file (see the bundle table
   in the README).
3. If the screenshot step (the first action) fails, the helper raises
   and leaves no half-written sidecars — the partial-bundle invariant
   that ``upload_baseline.sh``'s pre-flight check also defends.

``capture_baseline`` does top-level ``import qt`` / ``import slicer``
/ ``import vtk``.  None of those are importable in a plain pytest
environment (or even in a Slicer Python that is not running inside a
QApplication), so this module **stubs all three into**
``sys.modules`` **before** importing ``capture_baseline``.  The stubs
record the calls the helper makes against them, which is exactly the
surface this test characterises.

References
----------
* ADR-0008 §"observability" — pure-Python helpers carry self-tests.
* ``LiverResections/Testing/README.md`` §"Bundle contents" — the
  four-file contract.
* ``LiverResections/Testing/Scripts/upload_baseline.sh`` — the
  upload-side pre-flight that also defends the partial-bundle
  invariant.
"""

from __future__ import annotations

import json
import pathlib
import sys
import types

import pytest


# --------------------------------------------------------------------------- #
# Stub modules
# --------------------------------------------------------------------------- #
#
# ``capture_baseline`` does ``import qt`` / ``import slicer`` /
# ``import vtk`` at module top level.  Inject minimal stub modules
# into ``sys.modules`` *before* the import so the module loads in
# plain CPython.  The stubs only need to expose the symbols that
# ``_save_bundle`` (and the helpers it calls — ``_serialise_camera``,
# ``_serialise_viewport``) reaches for.


class _StubVTKWindowToImageFilter:
    """Records the ``SetInput`` argument + supports the small fluent
    surface ``_save_bundle`` calls."""

    def __init__(self) -> None:
        self._input = None
        self.updated = False

    def SetInput(self, render_window) -> None:  # noqa: N802 (VTK API)
        self._input = render_window

    def SetInputBufferTypeToRGB(self) -> None:  # noqa: N802
        pass

    def ReadFrontBufferOff(self) -> None:  # noqa: N802
        pass

    def SetShouldRerender(self, _flag: int) -> None:  # noqa: N802
        pass

    def Update(self) -> None:  # noqa: N802
        self.updated = True

    def GetOutput(self):  # noqa: N802
        return object()  # opaque sentinel — writer doesn't introspect it


class _StubVTKPNGWriter:
    """PNG writer stub.

    Default behaviour writes a deterministic 8-byte PNG-signature blob
    to the configured filename.  ``fail_on_write=True`` raises from
    ``Write()`` — exercises the partial-bundle invariant.
    """

    fail_on_write = False

    def __init__(self) -> None:
        self._filename: pathlib.Path | None = None

    def SetFileName(self, path: str) -> None:  # noqa: N802
        self._filename = pathlib.Path(path)

    def SetInputData(self, _data) -> None:  # noqa: N802
        pass

    def Write(self) -> None:  # noqa: N802
        if type(self).fail_on_write:
            raise RuntimeError("simulated screenshot-write failure")
        assert self._filename is not None
        # PNG magic header — minimal valid-looking bytes.
        self._filename.write_bytes(b"\x89PNG\r\n\x1a\n")


def _make_vtk_stub() -> types.ModuleType:
    vtk = types.ModuleType("vtk")
    vtk.vtkWindowToImageFilter = _StubVTKWindowToImageFilter
    vtk.vtkPNGWriter = _StubVTKPNGWriter
    return vtk


class _StubCamera:
    """Stub ``vtkCamera`` — fixed numbers so the JSON contents are
    asserted exactly."""

    def GetPosition(self):  # noqa: N802
        return (1.0, 2.0, 3.0)

    def GetFocalPoint(self):  # noqa: N802
        return (0.0, 0.0, 0.0)

    def GetViewUp(self):  # noqa: N802
        return (0.0, 1.0, 0.0)

    def GetParallelScale(self):  # noqa: N802
        return 1.5

    def GetViewAngle(self):  # noqa: N802
        return 30.0

    def GetClippingRange(self):  # noqa: N802
        return (0.1, 1000.0)


class _StubCameraNode:
    def GetCamera(self):  # noqa: N802
        return _StubCamera()


class _StubCamerasLogic:
    def GetViewActiveCameraNode(self, _view_node):  # noqa: N802
        return _StubCameraNode()


class _StubCamerasModule:
    def logic(self):
        return _StubCamerasLogic()


class _StubModules:
    cameras = _StubCamerasModule()


class _StubUtil:
    """``slicer.util.saveScene`` stub — writes a placeholder MRML
    blob so the resulting file exists for the assertions."""

    @staticmethod
    def saveScene(path: str) -> bool:  # noqa: N802 (Slicer API)
        pathlib.Path(path).write_text(
            '<?xml version="1.0"?>\n<MRML version="1.0"></MRML>\n'
        )
        return True


def _make_slicer_stub() -> types.ModuleType:
    slicer = types.ModuleType("slicer")
    slicer.modules = _StubModules()
    slicer.util = _StubUtil()
    return slicer


class _StubQEvent:
    KeyPress = 6  # match Qt's enum value; unused by _save_bundle


class _StubQt:
    KeyPress = _StubQEvent.KeyPress
    Key_S = 83
    Key_Q = 81


class _StubQObject:
    """Minimal ``QObject`` substitute — capture_baseline subclasses it
    in ``_KeyFilter``; the subclass body is not exercised by these
    tests, so any object that supports an empty ``__init__`` works."""

    def __init__(self, *_args, **_kwargs) -> None:
        pass


def _make_qt_stub() -> types.ModuleType:
    qt = types.ModuleType("qt")
    qt.QEvent = _StubQEvent
    qt.Qt = _StubQt
    qt.QObject = _StubQObject
    # ``QApplication`` is reached for in ``_KeyFilter.eventFilter`` only,
    # not in ``_save_bundle``; provide a marker so any accidental call
    # surfaces as an attribute error rather than a silent no-op.
    qt.QApplication = types.SimpleNamespace()
    return qt


@pytest.fixture
def capture_module(monkeypatch):
    """Import ``capture_baseline`` under stubbed Qt / Slicer / VTK
    modules and return the imported module object.

    Each test gets a fresh import so the per-test ``fail_on_write``
    toggle on ``_StubVTKPNGWriter`` cannot leak into a sibling test.
    """
    # Ensure default behaviour at fixture entry — paranoid clean-slate
    # in case a prior test crashed before the fixture's teardown.
    _StubVTKPNGWriter.fail_on_write = False

    monkeypatch.setitem(sys.modules, "qt", _make_qt_stub())
    monkeypatch.setitem(sys.modules, "slicer", _make_slicer_stub())
    monkeypatch.setitem(sys.modules, "vtk", _make_vtk_stub())

    here = pathlib.Path(__file__).resolve()
    harness_dir = here.parent.parent  # LiverResections/Testing/Python/
    monkeypatch.syspath_prepend(str(harness_dir))

    # Force re-import so the stubs above are picked up fresh.
    monkeypatch.delitem(sys.modules, "capture_baseline", raising=False)
    import capture_baseline  # noqa: E402

    yield capture_baseline

    # Defensive: reset the toggle for the next fixture entry.
    _StubVTKPNGWriter.fail_on_write = False


# --------------------------------------------------------------------------- #
# Stub view-node + view-widget surfaces
# --------------------------------------------------------------------------- #


class _StubRenderWindow:
    def GetMultiSamples(self) -> int:  # noqa: N802
        return 0


class _StubThreeDView:
    def __init__(self) -> None:
        self.force_render_calls = 0

    def forceRender(self) -> None:  # noqa: N802 (Slicer API)
        self.force_render_calls += 1

    def renderWindow(self):  # noqa: N802
        return _StubRenderWindow()


class _StubSize:
    def __init__(self, w: int, h: int) -> None:
        self._w = w
        self._h = h

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


class _StubViewWidget:
    def __init__(self) -> None:
        self._three_d_view = _StubThreeDView()
        self.size = _StubSize(800, 600)

    def threeDView(self):  # noqa: N802
        return self._three_d_view


class _StubViewNode:
    def GetBackgroundColor(self):  # noqa: N802
        return (0.0, 0.0, 0.0)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_save_bundle_writes_all_four_sidecars(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """The four-file bundle contract: ``.png`` + ``.mrml`` +
    ``.camera.json`` + ``.viewport.json`` all written into the
    staging dir."""
    capture_module._save_bundle(
        "FakeScenario",
        tmp_path,
        _StubViewNode(),
        _StubViewWidget(),
    )

    expected = {
        "FakeScenario.png",
        "FakeScenario.mrml",
        "FakeScenario.camera.json",
        "FakeScenario.viewport.json",
    }
    actual = {p.name for p in tmp_path.iterdir()}
    assert expected == actual, f"missing/extra files: {expected ^ actual}"


def test_save_bundle_camera_json_shape(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """The ``.camera.json`` sidecar carries the six documented keys
    (``LiverResections/Testing/README.md`` §"Bundle contents")."""
    capture_module._save_bundle(
        "FakeScenario",
        tmp_path,
        _StubViewNode(),
        _StubViewWidget(),
    )
    payload = json.loads((tmp_path / "FakeScenario.camera.json").read_text())
    assert set(payload.keys()) == {
        "position",
        "focal_point",
        "view_up",
        "parallel_scale",
        "view_angle",
        "clipping_range",
    }
    # Spot-check one value to pin the serialiser → JSON path.
    assert payload["position"] == [1.0, 2.0, 3.0]


def test_save_bundle_viewport_json_shape(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """The ``.viewport.json`` sidecar carries size + background +
    anti-aliasing."""
    capture_module._save_bundle(
        "FakeScenario",
        tmp_path,
        _StubViewNode(),
        _StubViewWidget(),
    )
    payload = json.loads((tmp_path / "FakeScenario.viewport.json").read_text())
    assert payload == {
        "size": [800, 600],
        "background": [0.0, 0.0, 0.0],
        "anti_aliasing_frames": 0,
    }


def test_save_bundle_does_not_write_notes_md(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """The optional ``notes.md`` sidecar must NOT be auto-emitted.

    Per the README, ``notes.md`` is a human-rationale file added by
    the maintainer on demand.  The auto-capture path must not invent
    one — silent placeholder content would defeat its purpose.
    """
    capture_module._save_bundle(
        "FakeScenario",
        tmp_path,
        _StubViewNode(),
        _StubViewWidget(),
    )
    assert not (tmp_path / "FakeScenario.notes.md").exists()
    # Same check generalised: no .md file appears at all.
    assert not any(p.suffix == ".md" for p in tmp_path.iterdir())


def test_save_bundle_creates_staging_dir(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """``mkdir(parents=True, exist_ok=True)`` runs first — the
    caller can pass a not-yet-extant directory."""
    nested = tmp_path / "nested" / "staging"
    assert not nested.exists()

    capture_module._save_bundle(
        "FakeScenario",
        nested,
        _StubViewNode(),
        _StubViewWidget(),
    )
    assert nested.is_dir()
    assert (nested / "FakeScenario.png").exists()


def test_save_bundle_screenshot_failure_leaves_no_sidecars(
    capture_module,
    tmp_path: pathlib.Path,
) -> None:
    """Partial-bundle invariant.

    The screenshot is the FIRST artefact written.  If it raises
    (simulated by toggling ``fail_on_write`` on the PNG-writer stub),
    the helper must propagate the exception and must NOT have written
    any of the JSON or MRML sidecars — those rely on the screenshot
    having landed.  This is the capture-side mirror of the
    ``upload_baseline.sh`` pre-flight check (which rejects partial
    bundles at the upload boundary).
    """
    _StubVTKPNGWriter.fail_on_write = True
    try:
        with pytest.raises(RuntimeError, match="simulated screenshot-write failure"):
            capture_module._save_bundle(
                "FakeScenario",
                tmp_path,
                _StubViewNode(),
                _StubViewWidget(),
            )
    finally:
        _StubVTKPNGWriter.fail_on_write = False

    # No sidecar files were written.  The staging dir may still exist
    # (``mkdir(exist_ok=True)`` ran before the failing write) — that's
    # fine; the contract is about *bundle artefacts*, not the dir.
    leftovers = [p.name for p in tmp_path.iterdir()]
    forbidden_sidecars = {
        "FakeScenario.mrml",
        "FakeScenario.camera.json",
        "FakeScenario.viewport.json",
    }
    assert not (forbidden_sidecars & set(leftovers)), (
        f"partial bundle leaked sidecars on screenshot failure: {leftovers}"
    )
