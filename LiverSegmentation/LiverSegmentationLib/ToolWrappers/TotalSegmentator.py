# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""TotalSegmentator tool wrapper — lazy-installed AI backend for Stage 2.

ADR-0024 §"Lazy install for AI backends": TotalSegmentator is a heavy
dependency (multi-GB models, GPU recommended) and is therefore NOT declared
as an ``EXTENSION_DEPENDS``.  It is pip-installed on first surgeon invocation
of an AI feature, never at import time.

Import-time purity (pinned by
``Testing/Python/test_liversegmentation_import_purity.py``): this module must
import cleanly with no network and no model download.  Concretely:

  * ``import totalsegmentator`` happens INSIDE the call path only
    (``ensureBackendInstalled`` / ``run``), never at module top level.
  * ``slicer.util.pip_install`` is reached only after an explicit surgeon
    size-confirmation, and only on ``ImportError`` of the backend.

On install failure (network, disk, GPU absence) the wrapper surfaces a clear
error and leaves the manual Segment-Editor path available (ADR-0024
§"Failure paths").
"""

from __future__ import annotations

import logging

#
# Lazy-install contract.  Kept as module-level named constants so the
# size-confirmation copy and the pinned version floor are grep-able and
# editable in one place (ADR-0024 §"Lazy install for AI backends").
#

#: Human-readable download-size estimate shown in the install-confirm dialog.
TOTALSEGMENTATOR_DOWNLOAD_SIZE = "~3 GB"

#: PyPI requirement string with a pinned version floor.  A floor (not an exact
#: pin) keeps the surgeon on a known-good minimum while allowing upstream
#: bugfix uptake; the wrapper isolates upstream API churn (ADR-0024
#: §Consequences "Per-tool wrappers isolate upstream API churn").
TOTALSEGMENTATOR_REQUIREMENT = "TotalSegmentator>=2.4.0"

#: The importable backend package name (distinct from the PyPI project name).
BACKEND_MODULE_NAME = "totalsegmentator"

#: Backend task specs per structure-card SCT code.  Mirrors the
#: ``Resources/Terminology/LabelToSCT/TotalSegmentator.json`` bridge
#: (ADR-0011); ``labels`` names the per-class output files the backend
#: writes into the output directory.  ``fast`` marks tasks with a
#: CPU-viable 3 mm fast variant (``total`` only; ``liver_vessels`` has
#: none).  Hepatic vein maps to the combined ``liver_vessels`` class —
#: deliberately over-inclusive until the Kumar-Oram per-vessel
#: refinement lands (the bridge JSON records the same caveat for the
#: combined portal label).
INFERENCE_TARGETS = {
    # Liver (SCT 10200004)
    "10200004": {
        "task": "total",
        "roi_subset": ["liver"],
        "labels": ["liver"],
        "fast": True,
    },
    # Portal vein (SCT 32764006) — TS combines portal + splenic.
    "32764006": {
        "task": "total",
        "roi_subset": ["portal_vein_and_splenic_vein"],
        "labels": ["portal_vein_and_splenic_vein"],
        "fast": True,
    },
    # Hepatic vein (SCT 8993003) — combined intrahepatic vessels.
    "8993003": {
        "task": "liver_vessels",
        "roi_subset": None,
        "labels": ["liver_vessels"],
        "fast": False,
    },
    # Mass (SCT 4147007)
    "4147007": {
        "task": "liver_vessels",
        "roi_subset": None,
        "labels": ["liver_tumor"],
        "fast": False,
    },
}


class TotalSegmentatorNotInstalled(RuntimeError):
    """Raised when the backend is absent and install was declined or failed."""


def _backend_importable() -> bool:
    """Return True iff the TotalSegmentator backend imports here and now.

    The import is performed INSIDE this function (call path), never at module
    top level, so module import stays pure per ADR-0024 §"Lazy install".
    """
    import importlib

    try:
        importlib.import_module(BACKEND_MODULE_NAME)
    except ImportError:
        return False
    return True


def _confirmInstall(parent=None) -> bool:
    """Show a size-confirmation dialog; return True iff the surgeon accepts.

    Uses a Qt message box so the surgeon sees the download footprint before a
    multi-GB install begins (ADR-0024 §"Lazy install": "prompts the surgeon
    with a confirmation dialog").  Falls back to refusing the install in a
    headless context where Qt has no usable dialog surface.
    """
    try:
        import qt
    except ImportError:  # pragma: no cover — headless / no-Qt context
        logging.warning(
            "TotalSegmentator install confirmation requested without Qt; "
            "declining the install (no interactive surface available)."
        )
        return False

    message = (
        f"Install TotalSegmentator? {TOTALSEGMENTATOR_DOWNLOAD_SIZE} download "
        "+ GPU recommended.\n\n"
        "The AI segmentation backend is downloaded on first use only. "
        "You can keep working with manual Segment Editor tools if you decline."
    )
    answer = qt.QMessageBox.question(
        parent,
        "Install TotalSegmentator",
        message,
        qt.QMessageBox.Ok | qt.QMessageBox.Cancel,
        qt.QMessageBox.Cancel,
    )
    return answer == qt.QMessageBox.Ok


def ensureBackendInstalled(parent=None, confirm=True) -> bool:
    """Ensure the TotalSegmentator backend is importable; install if needed.

    Reusable hook (ADR-0024 §"Lazy install": "expose a reusable
    ensureBackendInstalled() hook"; the settings panel pre-download affordance
    reuses it).  Returns True iff the backend is importable on return.

    Flow:
      1. Already importable -> return True (no dialog, no install).
      2. Absent + ``confirm`` -> show the size-confirm dialog; on decline
         return False (manual path stays available).
      3. ``slicer.util.pip_install`` the pinned requirement, then re-check the
         import.  On any failure return False without raising, so the caller
         can fall back to the manual Segment-Editor path.

    The ``import totalsegmentator`` and ``slicer.util.pip_install`` calls live
    here (call path), not at module top level — the import-purity invariant.
    """
    if _backend_importable():
        return True

    if confirm and not _confirmInstall(parent):
        logging.info("TotalSegmentator install declined by the surgeon.")
        return False

    try:
        import slicer

        slicer.util.pip_install(TOTALSEGMENTATOR_REQUIREMENT)
    except Exception as exc:  # noqa: BLE001 — surface any install failure mode
        logging.error("TotalSegmentator install failed: %s", exc)
        return False

    if not _backend_importable():
        logging.error(
            "TotalSegmentator install reported success but the backend is "
            "still not importable."
        )
        return False

    return True


def run(parent=None, confirm=True):
    """Entry point for an AI segmentation step (lazy-install guarded).

    Ensures the backend is installed (prompting on first use), then imports it
    inside this call path and returns the imported module for the orchestrator
    to drive.  Raises :class:`TotalSegmentatorNotInstalled` when the backend is
    unavailable so the orchestrator can route the surgeon to the manual path.
    """
    if not ensureBackendInstalled(parent=parent, confirm=confirm):
        raise TotalSegmentatorNotInstalled(
            "TotalSegmentator backend is not available; use the Segment "
            "Editor manual path or retry the install."
        )

    import importlib

    return importlib.import_module(BACKEND_MODULE_NAME)


def resolveExecutable() -> str | None:
    """Path to the ``TotalSegmentator`` console script, or ``None``.

    ``pip_install`` inside Slicer lands console scripts beside the Python
    interpreter (``python-install/bin/``); derive that location from the
    installed backend package so the resolve works regardless of the
    launcher's ``PATH``.  Falls back to a plain ``PATH`` lookup.  Import
    stays inside the call path (the import-purity invariant).
    """
    import importlib
    import os
    import shutil

    try:
        backend = importlib.import_module(BACKEND_MODULE_NAME)
    except ImportError:
        return shutil.which("TotalSegmentator")

    # site-packages/totalsegmentator/__init__.py -> python-install/bin/
    package_dir = os.path.dirname(os.path.abspath(backend.__file__))
    prefix = os.path.dirname(os.path.dirname(os.path.dirname(package_dir)))
    candidate = os.path.join(prefix, "bin", "TotalSegmentator")
    if os.path.isfile(candidate):
        return candidate
    return shutil.which("TotalSegmentator")


def detectDevice() -> str:
    """``"gpu"`` when an NVIDIA driver is visible, else ``"cpu"``.

    The backend's default device is GPU and errors out without CUDA; an
    explicit device keeps the CPU-only path deterministic.
    """
    import shutil

    return "gpu" if shutil.which("nvidia-smi") else "cpu"


def buildCommand(executable, input_path, output_dir, sct_code, device) -> list:
    """The backend command line for one structure target (pure, testable).

    Per-class file output (no ``--ml``): the backend writes
    ``<output_dir>/<label>.nii.gz`` per class, which the orchestrator
    loads by name — no class-index bookkeeping.
    """
    spec = INFERENCE_TARGETS[str(sct_code)]
    command = [
        str(executable),
        "-i",
        str(input_path),
        "-o",
        str(output_dir),
        "--task",
        spec["task"],
    ]
    if spec["roi_subset"]:
        command += ["--roi_subset", *spec["roi_subset"]]
    if spec["fast"]:
        command.append("--fast")
    command += ["--device", str(device)]
    return command


def runInference(input_path, output_dir, sct_code, progress_callback=None) -> None:
    """Run one structure's inference as a SUBPROCESS, streaming progress.

    Out-of-process keeps the Slicer GUI alive during the minutes-long
    inference; each backend stdout/stderr line reaches
    ``progress_callback`` (the structure card's status surface).  Raises
    ``RuntimeError`` with the output tail on a non-zero exit, and
    :class:`TotalSegmentatorNotInstalled` when no executable resolves.
    """
    import subprocess

    executable = resolveExecutable()
    if executable is None:
        raise TotalSegmentatorNotInstalled(
            "TotalSegmentator console script not found; run the install first."
        )

    command = buildCommand(executable, input_path, output_dir, sct_code, detectDevice())
    logging.info("TotalSegmentator invocation: %s", " ".join(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    tail: list = []
    assert process.stdout is not None
    # Byte-chunk read split on BOTH newline kinds: the backend's tqdm
    # progress refreshes with bare carriage returns, which a readline
    # loop would sit on for the whole download/predict phase — exactly
    # the silent stretch the progress surface exists for.
    buffer = b""
    while True:
        chunk = process.stdout.read1(4096)
        if not chunk:
            break
        buffer += chunk
        *pieces, buffer = _split_stream_pieces(buffer)
        for piece in pieces:
            tail.append(piece)
            del tail[:-20]
            if progress_callback is not None:
                progress_callback(piece)
    remainder = buffer.decode("utf-8", "replace").strip()
    if remainder:
        tail.append(remainder)
        if progress_callback is not None:
            progress_callback(remainder)
    returncode = process.wait()
    if returncode != 0:
        raise RuntimeError(
            "TotalSegmentator failed (exit %d):\n%s" % (returncode, "\n".join(tail))
        )


def _split_stream_pieces(buffer: bytes) -> list:
    """Split ``buffer`` on ``\\r``/``\\n``; last element is the unterminated rest.

    Returns decoded, stripped pieces (empties dropped) with the raw
    undecoded remainder as the final element — the streaming loop's
    carry-over.
    """
    import re

    parts = re.split(rb"[\r\n]", buffer)
    remainder = parts.pop()
    pieces = [
        part.decode("utf-8", "replace").strip()
        for part in parts
        if part.strip()
    ]
    return [*pieces, remainder]
