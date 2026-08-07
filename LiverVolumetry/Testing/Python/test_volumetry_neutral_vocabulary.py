# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- neutral vocabulary in the volumetry core.

Volumetry is a NEUTRAL measuring instrument, not a resection planner: the
core path (module strings, the panel ``.ui``, the seeds table, the generated
artifact names) carries no resection-planning vocabulary.

* The generated leftover segment is named ``Unassigned`` -- never the
  resection-planning ``Remnant`` (the ``UNSEEDED_SEGMENT_LABEL`` constant).
* ``remnant`` appears NOWHERE in the module's sources or panel.
* ``resection`` wording is confined to the OPTIONAL refine-by-resection
  control (which legitimately names the refinement it applies).

Bare-runnable (ADR-0027): pure file-content checks -- no ``slicer`` import,
no scene, no Qt.
"""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET

_MODULE_DIR = pathlib.Path(__file__).resolve().parents[2]
_MODULE_PY = _MODULE_DIR / "LiverVolumetry.py"
_PANEL_UI = _MODULE_DIR / "Resources" / "UI" / "LiverVolumetryWidget.ui"
_LIB_DIR = _MODULE_DIR / "LiverVolumetryLib"


def _core_sources():
    return [_MODULE_PY, _PANEL_UI] + sorted(_LIB_DIR.glob("*.py"))


def test_no_remnant_vocabulary_anywhere_in_the_core():
    """``remnant`` (any case) appears nowhere in the module core.

    The word is resection-planning vocabulary; the neutral instrument names
    the unseeded leftover ``Unassigned``.
    """
    offenders = []
    for path in _core_sources():
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(r"remnant", line, re.IGNORECASE):
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert not offenders, (
        "resection-planning vocabulary ('remnant') crept back into the "
        "volumetry core:\n" + "\n".join(offenders)
    )


def test_unseeded_segment_label_is_unassigned():
    """The generated leftover segment's name constant is the neutral
    ``Unassigned`` (source-level pin -- bare-runnable without importing the
    Slicer module)."""
    text = _MODULE_PY.read_text(encoding="utf-8")
    match = re.search(
        r'^UNSEEDED_SEGMENT_LABEL\s*=\s*"([^"]+)"', text, re.MULTILINE
    )
    assert match is not None, (
        "LiverVolumetry.py must define UNSEEDED_SEGMENT_LABEL (the generated "
        "leftover segment's neutral name)."
    )
    assert match.group(1) == "Unassigned"
    assert 'SetName(UNSEEDED_SEGMENT_LABEL)' in text, (
        "generateSegments must name the leftover segment via the constant."
    )


def test_panel_resection_wording_is_confined_to_the_refine_control():
    """``resection`` wording in the panel belongs ONLY to the optional
    refine-by-resection control (checkbox / label / combo), which legitimately
    names the refinement -- no other core control presumes resection planning.
    """
    tree = ET.parse(_PANEL_UI)
    offenders = []

    def _walk(node, owner):
        name = node.get("name") or owner
        if node.tag == "widget":
            owner = node.get("name") or owner
        for child in node:
            _walk(child, owner)
        if node.tag == "string" and node.text and re.search(
            r"resect", node.text, re.IGNORECASE
        ):
            allowed = owner and re.search(
                r"refine|resection", owner, re.IGNORECASE
            )
            if not allowed:
                offenders.append(f"{owner}: {node.text.strip()[:80]}")
        del name

    _walk(tree.getroot(), "")
    assert not offenders, (
        "resection wording outside the refine-by-resection control:\n"
        + "\n".join(offenders)
    )


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
