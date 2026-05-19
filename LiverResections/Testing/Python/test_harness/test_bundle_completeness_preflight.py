# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Harness self-tests for ``upload_baseline.sh``'s bundle-completeness
pre-flight.

GAP-1 follow-up from PR #384's /slicer-review synthesis (issue #387).
The pre-flight check defends the same partial-bundle invariant as
``capture_baseline._save_bundle`` (see ``test_save_bundle.py``), but
on the upload boundary: refuse to push a structurally invalid
baseline (PNG without MRML, MRML without camera/viewport, etc.) to
the testing-data release.  A complete bundle is the four sidecars
documented in ``LiverResections/Testing/README.md`` §"Bundle contents":

    .png  .mrml  .camera.json  .viewport.json

The tests run the script as a subprocess against an isolated fake
repo layout in ``tmp_path``.  ``DRY_RUN=1`` short-circuits the
destructive stage step *after* the pre-flight passes, so the
"all four present" success path can be characterised without
polluting the real ``Data/Baseline/`` directory or the maintainer's
``INCOMING/``.

References
----------
* ADR-0008 §"observability" — pure-Python helpers carry self-tests.
* ``LiverResections/Testing/Scripts/upload_baseline.sh``.
* PR #384 /slicer-review synthesis comment, GAP-1 (this issue) +
  GAP-4 (the upstream pre-flight finding).
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest


_HERE = pathlib.Path(__file__).resolve()
_REAL_SCRIPT = (
    _HERE.parent.parent.parent  # LiverResections/Testing/
    / "Scripts"
    / "upload_baseline.sh"
)


# Skip the whole module on Windows — the shell script is bash-only,
# and Slicer-Liver CI is Ubuntu-only at present.  Use ``sys.platform``
# rather than ``shutil.which("bash")`` so the skip reason is precise.
pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="upload_baseline.sh is bash-only; Slicer-Liver CI is Ubuntu-only.",
)


def _build_fake_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Mirror the slice of the repo layout the script reaches for.

    Returns the path to the script copy inside the fake repo.  The
    script resolves ``REPO_ROOT`` from ``SCRIPT_DIR/../../..``, so
    placing it at ``<tmp>/LiverResections/Testing/Scripts/`` gives
    a ``REPO_ROOT`` of ``<tmp>`` — same shape as the real checkout.
    """
    scripts_dir = tmp_path / "LiverResections" / "Testing" / "Scripts"
    scripts_dir.mkdir(parents=True)
    script_copy = scripts_dir / "upload_baseline.sh"
    shutil.copy2(_REAL_SCRIPT, script_copy)
    script_copy.chmod(0o755)

    (tmp_path / "Testing" / "baselines-staging").mkdir(parents=True)
    (tmp_path / "LiverResections" / "Testing" / "Data" / "Baseline").mkdir(parents=True)
    return script_copy


def _stage_bundle(
    tmp_path: pathlib.Path,
    test_name: str,
    *,
    extensions: tuple[str, ...],
) -> None:
    """Write deterministic placeholder bytes into the staging dir for
    the requested subset of bundle extensions.

    The pre-flight only checks ``-f`` presence, so any non-empty
    content works.  Use distinct contents per extension to surface
    any accidental cross-wiring in the script.
    """
    staging = tmp_path / "Testing" / "baselines-staging"
    for ext in extensions:
        (staging / f"{test_name}.{ext}").write_text(
            f"placeholder for {test_name}.{ext}\n"
        )


def _run_script(
    script: pathlib.Path,
    test_name: str,
    incoming_dir: pathlib.Path,
    *,
    dry_run: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke the script with a controlled environment.  ``DRY_RUN=1``
    short-circuits the destructive stage step so success-path tests
    don't pollute the fake repo or the real one."""
    env = os.environ.copy()
    env["ALIVE_TESTING_DATA_INCOMING"] = str(incoming_dir)
    if dry_run:
        env["DRY_RUN"] = "1"
    return subprocess.run(
        ["bash", str(script), test_name],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_preflight_accepts_complete_bundle(tmp_path: pathlib.Path) -> None:
    """All four sidecars present → script exits 0 in dry-run mode.

    The success path is characterised under ``DRY_RUN=1`` so the test
    does not write into the real repo's ``Data/Baseline/`` directory
    or shell out to ``gh``.
    """
    script = _build_fake_repo(tmp_path)
    incoming = tmp_path / "INCOMING"
    incoming.mkdir()
    _stage_bundle(
        tmp_path,
        "BezierSurface4x4Planning",
        extensions=("png", "mrml", "camera.json", "viewport.json"),
    )

    result = _run_script(
        script,
        "BezierSurface4x4Planning",
        incoming,
    )
    assert result.returncode == 0, (
        f"script exited {result.returncode} on complete bundle\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "dry-run" in result.stdout.lower()
    # The dry-run path must NOT touch INCOMING or the stub dir.
    assert list(incoming.iterdir()) == []
    stub_dir = tmp_path / "LiverResections" / "Testing" / "Data" / "Baseline"
    assert list(stub_dir.iterdir()) == []


@pytest.mark.parametrize(
    "missing_ext",
    ["png", "mrml", "camera.json", "viewport.json"],
)
def test_preflight_rejects_single_missing_sidecar(
    tmp_path: pathlib.Path,
    missing_ext: str,
) -> None:
    """Any one of the four sidecars missing → script exits non-zero
    with a clear "incomplete bundle" message in stderr.

    Parametrised over all four extensions so a future re-ordering of
    the bundle list can't accidentally let one slip through the
    check.
    """
    script = _build_fake_repo(tmp_path)
    incoming = tmp_path / "INCOMING"
    incoming.mkdir()
    present = tuple(
        ext for ext in ("png", "mrml", "camera.json", "viewport.json")
        if ext != missing_ext
    )
    _stage_bundle(tmp_path, "BezierSurface4x4Planning", extensions=present)

    result = _run_script(
        script,
        "BezierSurface4x4Planning",
        incoming,
    )
    assert result.returncode != 0, (
        f"script unexpectedly succeeded with {missing_ext} missing"
    )
    assert "incomplete bundle" in result.stderr.lower(), (
        f"stderr did not flag incomplete bundle: {result.stderr!r}"
    )
    assert f"BezierSurface4x4Planning.{missing_ext}" in result.stderr


def test_preflight_rejects_all_missing(tmp_path: pathlib.Path) -> None:
    """Empty staging dir (no sidecars) → script exits non-zero with
    every sidecar listed."""
    script = _build_fake_repo(tmp_path)
    incoming = tmp_path / "INCOMING"
    incoming.mkdir()
    # Deliberately do NOT call _stage_bundle — the staging dir exists
    # (created by _build_fake_repo) but is empty.

    result = _run_script(
        script,
        "BezierSurface4x4Planning",
        incoming,
    )
    assert result.returncode != 0
    stderr = result.stderr.lower()
    assert "incomplete bundle" in stderr
    for ext in ("png", "mrml", "camera.json", "viewport.json"):
        assert f"beziersurface4x4planning.{ext}" in stderr, (
            f"stderr did not list missing {ext}: {result.stderr!r}"
        )


def test_preflight_rejects_when_alive_incoming_unset(
    tmp_path: pathlib.Path,
) -> None:
    """``ALIVE_TESTING_DATA_INCOMING`` unset → script refuses to run.

    This guards the documented contract that the operator point the
    script at an actual testing-data checkout before invoking it.
    """
    script = _build_fake_repo(tmp_path)
    _stage_bundle(
        tmp_path,
        "BezierSurface4x4Planning",
        extensions=("png", "mrml", "camera.json", "viewport.json"),
    )

    env = os.environ.copy()
    env.pop("ALIVE_TESTING_DATA_INCOMING", None)
    # Keep DRY_RUN off so we'd notice if the pre-flight order ever
    # let an unset INCOMING through.
    result = subprocess.run(
        ["bash", str(script), "BezierSurface4x4Planning"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "ALIVE_TESTING_DATA_INCOMING" in result.stderr
