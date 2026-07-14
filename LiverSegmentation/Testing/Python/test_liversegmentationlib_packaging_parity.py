# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Packaging-parity invariant for the ``LiverSegmentationLib`` Python sub-package.

``LiverSegmentationLib`` is a scripted module's Python sub-package: its files
are staged into the built ``qt-scripted-modules`` tree ONLY via the explicit
``LiverSegmentationLib_PYTHON_SCRIPTS`` list in
``LiverSegmentation/CMakeLists.txt`` (``ctkMacroCompilePythonScript``).  A
``.py`` present in the source tree but absent from that list is **never built
or packaged** -- it silently vanishes from a fresh build and the shipped
extension, and ``import LiverSegmentationLib.<name>`` fails at runtime.

Same drift class the sibling ``LiverResectionsLib`` parity test guards
(``LiverResections/Testing/Python/test_liverresectionslib_packaging_parity.py``):
an omitted file surfaces only as skipped launched tests that a local dev tree
masks with hand-copied strays.

Pure-Python (parses one CMake file + globs the source tree); runs in the bare
CTest row, no Slicer needed -- so this class of packaging drift fails a row
that actually executes.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB_DIR = _REPO_ROOT / "LiverSegmentation" / "LiverSegmentationLib"
# Unlike LiverResectionsLib, the staging list lives in the MODULE's
# CMakeLists.txt (there is no per-package CMakeLists under the lib dir).
_CMAKE = _REPO_ROOT / "LiverSegmentation" / "CMakeLists.txt"


def _source_py_files() -> set[str]:
    """Every ``.py`` under the source sub-package, as ``LIB_DIR``-relative POSIX paths."""
    return {
        p.relative_to(_LIB_DIR).as_posix()
        for p in _LIB_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
    }


def _cmake_scripts_list() -> set[str]:
    """The ``.py`` entries inside the ``LiverSegmentationLib_PYTHON_SCRIPTS`` set()."""
    text = _CMAKE.read_text(encoding="utf-8")
    match = re.search(
        r"set\(\s*LiverSegmentationLib_PYTHON_SCRIPTS(.*?)\)",
        text,
        re.DOTALL,
    )
    assert match is not None, (
        "LiverSegmentationLib_PYTHON_SCRIPTS set() not found in "
        f"{_CMAKE} -- the packaging list moved or was renamed."
    )
    return set(re.findall(r"[\w/]+\.py", match.group(1)))


def test_every_source_py_is_staged():
    """Every source ``.py`` must appear in the CMake SCRIPTS list.

    Otherwise it is not compiled into ``qt-scripted-modules`` / the package and
    ``import LiverSegmentationLib.<name>`` fails in a fresh build (the same
    regression class the LiverResectionsLib parity test pins).
    """
    missing = sorted(_source_py_files() - _cmake_scripts_list())
    assert not missing, (
        "LiverSegmentationLib source .py files missing from "
        "LiverSegmentationLib_PYTHON_SCRIPTS (won't be built/packaged): "
        f"{missing}. Add them to LiverSegmentation/CMakeLists.txt."
    )


def test_scripts_list_has_no_phantom_entries():
    """Every SCRIPTS entry must exist in the source tree (no stale references)."""
    phantom = sorted(_cmake_scripts_list() - _source_py_files())
    assert not phantom, (
        "LiverSegmentationLib_PYTHON_SCRIPTS lists files absent from the source "
        f"tree (stale references): {phantom}."
    )
