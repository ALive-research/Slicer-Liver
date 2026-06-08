# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 5 — source / CMake conformance greps.

ADR-0024 §Conformance, pinned as static (no-Slicer) source checks:

  * ``LiverSegmentation/CMakeLists.txt`` declares NO ``EXTENSION_DEPENDS``
    entry for TotalSegmentator and NONE for MONAILabel (Alternative C +
    Alternative H rejections).
  * ``LiverSegmentation/ToolWrappers/`` contains NO ``MONAILabel.py``
    (Alternative H: the wrapper was retracted).
  * NO new ``vtkMRML*DisplayNode`` subclass ships under
    ``LiverSegmentation/`` (Stage 2 uses stock
    ``vtkMRMLSegmentationDisplayNode``).
  * ``slicer.util.pip_install`` appears ONLY under
    ``LiverSegmentation/ToolWrappers/`` (the lazy-install code path lives
    there and nowhere else in the module).

Pure-Python: walks the source tree, no Slicer / Qt / network.  These checks
are meaningful only once the module directory has source in it; until then
each asserts the absence-properties hold vacuously (the module dir is the
test's own ``Testing/`` subtree, which carries none of the forbidden
artifacts).
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


def test_cmake_has_no_totalsegmentator_or_monailabel_extension_depends():
    """No EXTENSION_DEPENDS for TotalSegmentator / MONAILabel.

    ADR-0024 §Conformance (Alternative C + Alternative H): both AI backends
    are out of the hard-dependency set -- TotalSegmentator is lazy-installed;
    MONAILabel is out of v2.0 scope entirely.
    """
    if not CMAKELISTS.is_file():
        pytest.skip(
            f"{CMAKELISTS} not present yet -- ADR-0024 module skeleton absent. "
            "Conformance pins the EXTENSION_DEPENDS exclusion for when it lands."
        )
    text = CMAKELISTS.read_text()
    # The pinned invariant (ADR-0024 §Conformance) is that neither AI backend
    # appears as an EXTENSION_DEPENDS entry.  TotalSegmentator legitimately
    # appears as the wrapper *script* filename (ToolWrappers/TotalSegmentator.py)
    # that must be compiled, so a whole-file textual ban over-reaches; we scope
    # the TotalSegmentator check to the EXTENSION_DEPENDS block.  MONAILabel has
    # no legitimate artifact under this module (Alternative H), so it stays a
    # whole-file ban.
    if "EXTENSION_DEPENDS" in text:
        depends_block = text[text.index("EXTENSION_DEPENDS"):]
        assert "TotalSegmentator" not in depends_block, (
            "LiverSegmentation/CMakeLists.txt must not declare TotalSegmentator "
            "as EXTENSION_DEPENDS (lazy-installed per ADR-0024 §'Lazy install')."
        )
    assert "MONAILabel" not in text, (
        "LiverSegmentation/CMakeLists.txt must not name MONAILabel "
        "(out of v2.0 scope per ADR-0024 Alternative H)."
    )


def test_no_monailabel_wrapper():
    """No ``ToolWrappers/MONAILabel.py``.

    ADR-0024 §Conformance / Alternative H: the originally-drafted MONAILabel
    wrapper was retracted; v2.0 ships TotalSegmentator only.
    """
    monailabel = TOOLWRAPPERS_DIR / "MONAILabel.py"
    assert not monailabel.exists(), (
        f"{monailabel} must not exist -- MONAILabel is out of v2.0 scope "
        "(ADR-0024 Alternative H)."
    )


def test_no_new_display_node_subclass():
    """No new ``vtkMRML*DisplayNode`` subclass under LiverSegmentation/.

    ADR-0024 §Conformance: Stage 2 renders with stock
    ``vtkMRMLSegmentationDisplayNode`` -- no per-module display node, no
    LayerDM Pipeline (ADR-0013 / ADR-0024 Alternative A).
    """
    if not MODULE_ROOT.is_dir():
        pytest.skip(f"{MODULE_ROOT} not present yet -- ADR-0024 module absent.")
    offenders = []
    for path in MODULE_ROOT.rglob("*"):
        if MODULE_ROOT / "Testing" in path.parents:
            continue
        name = path.name
        # C++ display-node class file or a Python class declaring one.
        if name.startswith("vtkMRML") and "DisplayNode" in name:
            offenders.append(str(path))
    assert not offenders, (
        "new display-node subclass(es) found under LiverSegmentation/: "
        f"{offenders} -- Stage 2 must use stock vtkMRMLSegmentationDisplayNode "
        "(ADR-0024 §Conformance / Alternative A)."
    )


def test_pip_install_only_under_toolwrappers():
    """``slicer.util.pip_install`` appears ONLY under ToolWrappers/.

    ADR-0024 §Conformance: the lazy-install code path is isolated to the
    per-tool wrappers; the orchestrator + widget must not call pip_install.
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
