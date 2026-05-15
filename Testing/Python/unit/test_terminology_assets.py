"""Tests for the SCT terminology assets shipped per ADR-0011.

Verifies four invariants:

1. `Resources/Terminology/SlicerLiver-Terminology.json` and the three
   `Resources/Terminology/LabelToSCT/*.json` files exist and are valid JSON.
2. The main terminology JSON conforms to the dcmqi
   `segment-context-schema.json` (the same schema Slicer's bundled
   `DICOM-Master.json` declares).  Validation runs in any Python with
   `jsonschema`; skipped when unavailable or when offline.
3. The main terminology JSON loads via Slicer's Terminologies module logic
   (`vtkSlicerTerminologiesModuleLogic`).  Requires Slicer's Python;
   `importorskip` skips outside that environment.
4. Each `LabelToSCT/*.json` bridge has the contract this project ships:
   `tool`, `mappings`, and (per entry) `label` plus either `sct: null`
   (out-of-scope) or a full `(CodingSchemeDesignator, CodeValue,
   CodeMeaning)` triple.
"""

from __future__ import annotations

import json
import pathlib
import urllib.request

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
TERMINOLOGY_DIR = REPO_ROOT / "Resources" / "Terminology"
MAIN_FILE = TERMINOLOGY_DIR / "SlicerLiver-Terminology.json"
LABEL_BRIDGES = sorted((TERMINOLOGY_DIR / "LabelToSCT").glob("*.json"))

# Current canonical location of the dcmqi schema (relocated from
# doc/segment-context-schema.json to doc/schemas/segment-context-schema.json
# upstream; Slicer's bundled JSONs still reference the old URL but the
# schema content is identical).
DCMQI_SCHEMA_URL = (
    "https://raw.githubusercontent.com/qiicr/dcmqi/master"
    "/doc/schemas/segment-context-schema.json"
)


def test_main_terminology_file_exists():
    assert MAIN_FILE.is_file(), f"missing {MAIN_FILE}"


def test_label_bridges_present():
    names = {p.stem for p in LABEL_BRIDGES}
    assert names == {"TotalSegmentator", "MONAILabel", "KumarOram"}, names


@pytest.mark.parametrize("path", [MAIN_FILE, *LABEL_BRIDGES], ids=lambda p: p.name)
def test_files_are_valid_json(path):
    json.loads(path.read_text())


def test_main_terminology_validates_against_dcmqi_schema():
    jsonschema = pytest.importorskip("jsonschema")
    try:
        with urllib.request.urlopen(DCMQI_SCHEMA_URL, timeout=15) as r:
            schema = json.loads(r.read())
    except Exception as exc:
        pytest.skip(f"dcmqi schema fetch failed (offline?): {exc}")

    data = json.loads(MAIN_FILE.read_text())
    jsonschema.validate(data, schema)


def test_main_terminology_loads_in_slicer():
    slicer = pytest.importorskip("slicer", reason="requires Slicer Python")
    terminologies_module = getattr(slicer.modules, "terminologies", None)
    if terminologies_module is None:
        pytest.skip("Slicer Terminologies module not available in this build")
    logic = terminologies_module.logic()
    context_name = logic.LoadTerminologyFromFile(str(MAIN_FILE))
    assert context_name, (
        f"LoadTerminologyFromFile returned empty context name for {MAIN_FILE.name}; "
        "the JSON failed to load."
    )
    # Confirm categories actually populated under the loaded context name.
    n_categories = logic.GetNumberOfCategoriesInTerminology(context_name)
    assert n_categories > 0, (
        f"Loaded context '{context_name}' has no categories — "
        "structure parsed but content is empty."
    )


@pytest.mark.parametrize("bridge", LABEL_BRIDGES, ids=lambda p: p.name)
def test_label_bridge_contract(bridge):
    data = json.loads(bridge.read_text())
    assert "tool" in data, f"{bridge.name}: missing top-level 'tool'"
    assert "mappings" in data, f"{bridge.name}: missing top-level 'mappings'"
    for entry in data["mappings"]:
        assert "label" in entry, f"{bridge.name}: mapping entry missing 'label'"
        sct = entry.get("sct")
        if sct is not None:
            for key in ("CodingSchemeDesignator", "CodeValue", "CodeMeaning"):
                assert key in sct, (
                    f"{bridge.name}: mapping '{entry['label']}' missing sct.{key}"
                )
