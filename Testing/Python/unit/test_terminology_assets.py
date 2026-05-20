# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

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


# ---------------------------------------------------------------------------
# Couinaud-specific assertions.
#
# The ten Couinaud codes carried by `SlicerLiver-Terminology.json` MUST be
# the authoritative SNOMED-CT triples — not project-private placeholders.
# Absence from Slicer's bundled `DICOM-Master.json` is the reason this file
# ships at all; the codes themselves are real and must not drift.
# ---------------------------------------------------------------------------

# CodeMeaning -> CodeValue, verified against the SNOMED-CT browser.
EXPECTED_COUINAUD_TYPES = {
    "Caudate lobe of liver":  "71133005",
    "Liver segment II":       "277956007",
    "Liver segment III":      "277957003",
    "Liver segment IV":       "277958008",
    "Liver segment IVa":      "871688003",
    "Liver segment IVb":      "871689006",
    "Liver segment V":        "277959000",
    "Liver segment VI":       "277960005",
    "Liver segment VII":      "277961009",
    "Liver segment VIII":     "277962002",
}

LIVER_SEGMENT_CATEGORY_CODE = "245553001"


def _liver_segment_category():
    """Locate the 'Liver segment' category, asserting it is present."""
    data = json.loads(MAIN_FILE.read_text())
    cats = [
        c for c in data["SegmentationCodes"]["Category"]
        if c.get("CodeMeaning") == "Liver segment"
    ]
    assert len(cats) == 1, (
        f"expected exactly one 'Liver segment' category, found {len(cats)}"
    )
    return cats[0]


def test_liver_segment_category_uses_authoritative_sct():
    """The category itself is SNOMED-CT 245553001 'Liver segment',
    not a project-private namespace."""
    cat = _liver_segment_category()
    assert cat["CodingSchemeDesignator"] == "SCT", (
        f"category scheme must be SCT, got {cat['CodingSchemeDesignator']!r} — "
        "private-scheme placeholders are not acceptable"
    )
    assert cat["CodeValue"] == LIVER_SEGMENT_CATEGORY_CODE, (
        f"category code must be {LIVER_SEGMENT_CATEGORY_CODE}, "
        f"got {cat['CodeValue']!r}"
    )


def test_couinaud_types_all_use_sct():
    """Regression test against placeholder-scheme leakage: every Couinaud
    segment type must declare CodingSchemeDesignator='SCT'."""
    cat = _liver_segment_category()
    wrong_scheme = [
        (t["CodeMeaning"], t["CodingSchemeDesignator"])
        for t in cat["Type"]
        if t["CodingSchemeDesignator"] != "SCT"
    ]
    assert not wrong_scheme, (
        f"Couinaud types using non-SCT scheme: {wrong_scheme}"
    )


def test_couinaud_codes_match_authoritative_set():
    """Every Couinaud segment must carry the verified SNOMED-CT triple.
    The mapping is authoritative for v2.0.0 and a drift here is either a
    typo or a regression to placeholder codes."""
    cat = _liver_segment_category()
    actual = {t["CodeMeaning"]: t["CodeValue"] for t in cat["Type"]}
    assert actual == EXPECTED_COUINAUD_TYPES, (
        f"Couinaud CodeMeaning→CodeValue mismatch.\n"
        f"  expected: {EXPECTED_COUINAUD_TYPES}\n"
        f"  actual:   {actual}"
    )


def test_couinaud_types_count_is_ten():
    """Sanity check — eight standard Couinaud segments (I–VIII) plus the
    two clinically meaningful IVa/IVb subdivisions = ten types."""
    cat = _liver_segment_category()
    assert len(cat["Type"]) == 10, (
        f"expected 10 Couinaud types (I–VIII + IVa + IVb), got {len(cat['Type'])}"
    )
