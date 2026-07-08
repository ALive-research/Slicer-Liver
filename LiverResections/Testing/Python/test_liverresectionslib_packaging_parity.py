# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Packaging-parity invariant for the ``LiverResectionsLib`` Python sub-package.

``LiverResectionsLib`` is a loadable module's Python sub-package: its files are
staged into the built ``qt-scripted-modules`` tree ONLY via the explicit
``LiverResectionsLib_PYTHON_SCRIPTS`` list in
``LiverResections/LiverResectionsLib/CMakeLists.txt`` (``ctkMacroCompilePythonScript``).
A ``.py`` present in the source tree but absent from that list is **never built
or packaged** -- it silently vanishes from a fresh build and the shipped
extension, and ``import LiverResectionsLib.<name>`` fails at runtime.

This bit twice: ``LocatorReslicer`` (#524) and ``ResectogramLocatorProducer``
(#516) were omitted, so the ADR-0025 locator producer + click-to-reslice
consumer never staged -- surfacing only as skipped launched tests
(``No module named 'LiverResectionsLib.LocatorReslicer'``) that a local dev
tree masked with hand-copied strays.

Pure-Python (parses two files); runs in the bare CTest row, no Slicer needed --
so this class of packaging drift fails a row that actually executes.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_DIR = _REPO_ROOT / "LiverResections" / "LiverResectionsLib"
_CMAKE = _LIB_DIR / "CMakeLists.txt"


def _source_py_files() -> set[str]:
    """Every ``.py`` under the source sub-package, as ``LIB_DIR``-relative POSIX paths."""
    return {
        p.relative_to(_LIB_DIR).as_posix()
        for p in _LIB_DIR.rglob("*.py")
    }


def _cmake_scripts_list() -> set[str]:
    """The ``.py`` entries inside the ``LiverResectionsLib_PYTHON_SCRIPTS`` set()."""
    text = _CMAKE.read_text(encoding="utf-8")
    match = re.search(
        r"set\(\s*LiverResectionsLib_PYTHON_SCRIPTS(.*?)\)",
        text,
        re.DOTALL,
    )
    assert match is not None, (
        "LiverResectionsLib_PYTHON_SCRIPTS set() not found in "
        f"{_CMAKE} -- the packaging list moved or was renamed."
    )
    return set(re.findall(r"[\w/]+\.py", match.group(1)))


def test_every_source_py_is_staged():
    """Every source ``.py`` must appear in the CMake SCRIPTS list.

    Otherwise it is not compiled into ``qt-scripted-modules`` / the package and
    ``import LiverResectionsLib.<name>`` fails in a fresh build (the #516/#524
    regression).
    """
    missing = sorted(_source_py_files() - _cmake_scripts_list())
    assert not missing, (
        "LiverResectionsLib source .py files missing from "
        "LiverResectionsLib_PYTHON_SCRIPTS (won't be built/packaged): "
        f"{missing}. Add them to LiverResections/LiverResectionsLib/CMakeLists.txt."
    )


def test_scripts_list_has_no_phantom_entries():
    """Every SCRIPTS entry must exist in the source tree (no stale references)."""
    phantom = sorted(_cmake_scripts_list() - _source_py_files())
    assert not phantom, (
        "LiverResectionsLib_PYTHON_SCRIPTS lists files absent from the source "
        f"tree (stale references): {phantom}."
    )
