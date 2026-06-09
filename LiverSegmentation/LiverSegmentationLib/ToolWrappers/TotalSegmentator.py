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
