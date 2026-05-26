# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Static-AST invariant: the Liver shell carries no domain compute code.

T7 from the T5.2-d planner output.  Pins the discipline laid out in
ADR-0023 §"Shell composition (Option H)": "The Liver shell holds no
domain logic — only composition + navigation."

The test scans ``Liver/Liver.py`` with Python's ``ast`` module — no
Slicer harness needed.  It enforces two rules:

  1. **Forbidden imports**: the shell must not pull in numerical /
     algorithm packages (``numpy``, ``vmtk``, ``itk``, ``scipy``).
     Domain modules carry these where needed (``LiverResections``,
     ``LiverVolumetry``, etc.); the shell composes them.

  2. **Forbidden algorithm calls**: the shell must not invoke pure
     domain algorithms such as ``vtkCenterOfMass``, ``vtkOBBTree``,
     ``vtkContourTriangulator``, or anything from the
     ``vtkSlicerLiverResectionsModuleLogicPython`` C++ binding apart
     from the standard module-registration plumbing.

A separate follow-up issue (#437) tracks relocating the orphaned
domain code currently embedded in ``Liver/Liver.py`` lines 297-985 to
its rightful owner module.  T5.2-d itself only *unwires* that code
(stops invoking it from the shell composition); the actual relocation
is out of scope.  Once the unwiring is done and the orphaned code is
removed (or moved into a side module), this test goes green.

Red-fails on ``60c78df`` because ``Liver/Liver.py`` currently:

  * has ``import numpy as np`` + ``from numpy import size``;
  * calls Bezier-algorithm bridges and VTK compute classes directly
    from widget code paths.

See also:
  * Docs/adr/0023-unified-gui-stage-workflow.md §"Shell composition"
  * Issue #437 — orphaned domain code relocation (follow-up).
"""

from __future__ import annotations

import ast
import pathlib

import pytest


# --------------------------------------------------------------------------- #
# Forbidden vocabularies
# --------------------------------------------------------------------------- #

# Top-level package names that signal compute / domain dependency.
# Submodule imports like ``itk.something`` are also caught because
# ``ast.Import.names[i].name`` reports the full dotted path.
FORBIDDEN_IMPORT_ROOTS = frozenset({
    "numpy",
    "vmtk",
    "itk",
    "scipy",
})

# Attribute names (``ast.Attribute.attr``) that signal a direct call into
# a domain algorithm bridge.  These are sampled from the orphaned
# Liver/Liver.py compute paths; the deny-list grows as audits surface
# more cases.  ``vtkCenterOfMass``, ``vtkOBBTree``,
# ``vtkContourTriangulator`` are pure-VTK algorithms that belong to
# domain modules, not the shell.
FORBIDDEN_CALL_NAMES = frozenset({
    "vtkCenterOfMass",
    "vtkOBBTree",
    "vtkContourTriangulator",
})

# Module imports that mark a hard C++ algorithm binding the shell must
# not consume directly.  A future amendment can carve out an exception
# for narrow module-registration uses; for now the rule is "shell does
# not import these at all".
FORBIDDEN_FROM_MODULES = frozenset({
    "vtkSlicerLiverResectionsModuleLogicPython",
})


# --------------------------------------------------------------------------- #
# File-local helpers
# --------------------------------------------------------------------------- #

LIVER_PY = (
    pathlib.Path(__file__).resolve().parents[2] / "Liver.py"
)


def _parse_liver_py() -> ast.Module:
    """Parse ``Liver/Liver.py`` into an AST, skipping if absent."""
    if not LIVER_PY.is_file():
        pytest.skip(
            f"Liver/Liver.py not found at {LIVER_PY}; "
            "test must run from the Liver module's source tree."
        )
    source = LIVER_PY.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(LIVER_PY))


def _collect_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(line, module_root)`` for every ``import`` / ``from ... import``.

    ``module_root`` is the *top-level* package name.  Both
    ``import numpy`` and ``import numpy.linalg`` map to ``"numpy"``;
    both ``from numpy import size`` and ``from numpy.random import ...``
    map to ``"numpy"``.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                found.append((node.lineno, root))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue  # ``from . import x`` — relative; ignored
            root = node.module.split(".", 1)[0]
            found.append((node.lineno, root))
    return found


def _collect_call_attrs(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(line, attr_or_id)`` for every ``Call`` site.

    Captures both ``foo.bar()`` (records ``"bar"``) and ``Bar()``
    (records ``"Bar"``) so the deny-list works regardless of whether
    the algorithm is imported with the ``vtk`` namespace or aliased
    bare.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            found.append((node.lineno, func.attr))
        elif isinstance(func, ast.Name):
            found.append((node.lineno, func.id))
    return found


# --------------------------------------------------------------------------- #
# T7 — Static check on Liver/Liver.py
# --------------------------------------------------------------------------- #

def test_t7_liver_shell_has_no_forbidden_imports():
    """The shell must not import numerical / domain-compute packages.

    Pins ADR-0023 §"Shell composition (Option H)": "The Liver shell
    holds no domain logic — only composition + navigation."

    Red-fails on ``60c78df``: ``Liver/Liver.py`` currently imports
    ``numpy`` (twice — ``import numpy as np`` + ``from numpy import
    size``).
    """
    tree = _parse_liver_py()

    violations: list[str] = []
    for line, root in _collect_imports(tree):
        if root in FORBIDDEN_IMPORT_ROOTS:
            violations.append(f"  L{line}: import of forbidden root '{root}'")
        if root in FORBIDDEN_FROM_MODULES:
            violations.append(
                f"  L{line}: import from forbidden module '{root}'"
            )

    assert not violations, (
        "Liver/Liver.py contains forbidden imports — the shell must "
        "compose, not compute.  Violations:\n"
        + "\n".join(violations)
        + "\n\nMove the offending code to the relevant domain module "
        "(LiverResections / LiverVolumetry / VascularTerritories); "
        "see issue #437 for the orphaned-domain relocation tracker."
    )


def test_t7_liver_shell_has_no_forbidden_algorithm_calls():
    """The shell must not invoke pure-VTK domain algorithms.

    Pins ADR-0023 §"Shell composition (Option H)" — composition only.
    Calls to ``vtkCenterOfMass``, ``vtkOBBTree``,
    ``vtkContourTriangulator`` belong to the resections / volumetry /
    territories modules.

    Red-fails on ``60c78df`` because the orphaned domain code in
    ``Liver/Liver.py`` lines 297-985 contains direct calls to these
    bridges.
    """
    tree = _parse_liver_py()

    violations: list[str] = []
    for line, name in _collect_call_attrs(tree):
        if name in FORBIDDEN_CALL_NAMES:
            violations.append(f"  L{line}: call to forbidden '{name}()'")

    assert not violations, (
        "Liver/Liver.py invokes forbidden domain algorithms — these "
        "are compute primitives that belong inside the per-stage "
        "modules.  Violations:\n"
        + "\n".join(violations)
        + "\n\nSee issue #437 for the orphaned-domain relocation tracker."
    )
