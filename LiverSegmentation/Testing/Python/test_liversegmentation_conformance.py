# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Lazy-install conformance — the ADR-0024 invariants that can *regress*.

ADR-0024 §Conformance lists many reviewable invariants.  Only a subset is
worth an automated test: those that can plausibly regress through ordinary
development.  Asserting the mere *absence* of an artifact that appears only
by deliberate action (no ``MONAILabel.py``, no custom
``vtkMRML*DisplayNode``) is not such a case — nobody adds those by accident,
and a contributor who adds one on purpose would just delete the guard.
Those points are conventions checked at review, not tests (see ADR-0024
§Conformance, which marks each point ``[test]`` or ``[review]``).

This file pins the two lazy-install invariants that *do* have a credible
regression path:

  1. ``LiverSegmentation/CMakeLists.txt`` does not declare ``TotalSegmentator``
     as an ``EXTENSION_DEPENDS`` entry — TotalSegmentator is *used*, so the
     tempting "fix" for a missing-backend error is to hard-depend on it,
     which would break the lazy-install design (ADR-0024 §"Lazy install").
  2. ``slicer.util.pip_install`` appears ONLY under
     ``LiverSegmentation/ToolWrappers/`` — the install code path must stay
     isolated to the per-tool wrappers; an install call leaking into the
     orchestrator or widget is a real regression.

Pure-Python: walks the source tree, no Slicer / Qt / network.
"""

from __future__ import annotations

import pathlib

import pytest

# LiverSegmentation/ is two parents up from this Testing/Python/ file.
MODULE_ROOT = pathlib.Path(__file__).resolve().parents[2]
CMAKELISTS = MODULE_ROOT / "CMakeLists.txt"
TOOLWRAPPERS_DIR = MODULE_ROOT / "ToolWrappers"


def _python_sources(root):
    """All ``*.py`` under ``root`` except this module's own Testing/ subtree."""
    testing_dir = MODULE_ROOT / "Testing"
    return [
        p for p in root.rglob("*.py")
        if testing_dir not in p.parents and p != testing_dir
    ]


def test_cmake_does_not_hard_depend_on_totalsegmentator():
    """TotalSegmentator must not be an ``EXTENSION_DEPENDS`` entry.

    ADR-0024 §"Lazy install": TotalSegmentator is installed lazily at first
    use, never declared as a hard extension dependency.  The plausible
    regression this guards is a contributor "fixing" a missing-backend
    error by adding the dependency.
    """
    if not CMAKELISTS.is_file():
        pytest.skip(
            f"{CMAKELISTS} not present yet -- ADR-0024 module skeleton absent."
        )
    text = CMAKELISTS.read_text()
    # TotalSegmentator legitimately appears as the wrapper *script* filename
    # (ToolWrappers/TotalSegmentator.py) that must be compiled, so a
    # whole-file textual ban over-reaches; scope the check to the
    # EXTENSION_DEPENDS block.
    if "EXTENSION_DEPENDS" in text:
        depends_block = text[text.index("EXTENSION_DEPENDS"):]
        assert "TotalSegmentator" not in depends_block, (
            "LiverSegmentation/CMakeLists.txt must not declare TotalSegmentator "
            "as EXTENSION_DEPENDS (lazy-installed per ADR-0024 §'Lazy install')."
        )


def test_pip_install_only_under_toolwrappers():
    """``slicer.util.pip_install`` appears ONLY under ToolWrappers/.

    ADR-0024 §Conformance: the lazy-install code path is isolated to the
    per-tool wrappers; the orchestrator + widget must not call pip_install.
    A leak into either is a real regression of the import-purity boundary.
    """
    if not MODULE_ROOT.is_dir():
        pytest.skip(f"{MODULE_ROOT} not present yet -- ADR-0024 module absent.")
    offenders = []
    for path in _python_sources(MODULE_ROOT):
        if TOOLWRAPPERS_DIR in path.parents:
            continue
        if "pip_install" in path.read_text():
            offenders.append(str(path))
    assert not offenders, (
        "pip_install found outside LiverSegmentation/ToolWrappers/: "
        f"{offenders} -- the lazy-install code path belongs only under "
        "ToolWrappers/ (ADR-0024 §Conformance)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
