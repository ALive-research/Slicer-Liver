# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 (amendment) -- the LiverVolumetry seeds table widget.

Pins the carrier-backed seeds table (the volumetry sibling of the
VascularTerritories ``TerritoriesTableWidget``, simplified for the FLAT seed
carrier):

* ROW-PER-SEED -- the table has one row per carrier seed, in placement order,
  matching ``GetNumberOfSeeds`` (the carrier is the model).
* CARRIER MODIFIED REBUILD -- adding a seed to the carrier (outside the table)
  grows the row count without an explicit refresh (the table observes the
  carrier's ``ModifiedEvent``).
* LABEL EDIT -- committing the row's ``QLineEdit`` writes ``SetNthSeedLabel``
  on the carrier (the label becomes the generated segment name, ADR-0038
  §Conformance) without touching the seed coordinate.
* COLOUR EDIT -- the row's colour picker writes ``SetNthSeedColor`` without
  touching the coordinate.
* DELETE -- the row's delete button calls ``RemoveNthSeed``, dropping exactly
  that seed; the ``deleteSeed`` entry point converges on the same carrier
  method.
* OBSERVER TEARDOWN -- ``cleanup`` detaches the carrier observer so a
  parentless widget does not survive to app shutdown holding a MRML observer
  (feedback_launched_widget_teardown_crash).

HARNESS: launched Slicer.  The table needs Qt (``qt.QTableWidget`` +
``ctk.ctkColorPickerButton``) + the wrapped ``vtkMRMLVolumetrySeedsNode``
carrier, so a bare ``PythonSlicer -m pytest`` (``slicer.mrmlScene is None``,
no Qt) SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards; the CTest
row collects + skips bare and RUNS launched (ADR-0027).

References
----------
* ADR-0038 -- §"Consumers ledger" + §Conformance (per-seed labels become
  generated segment names).
* ADR-0014 -- the four-layer split (a display edit must not touch geometry).
* ADR-0010 -- glyph/text pairing (icon controls carry text + tooltip).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/Testing/Python/test_territories_table.py -- the
  carrier-backed table idiom this mirrors (hierarchical variant).
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _qt_or_skip():
    from conftest import _require_qt_widget

    _require_qt_widget()


def _make_carrier_or_skip(slicer, name="SeedsTableCarrierTest"):
    """Mint a seed carrier exposing the flat seed API, or skip-pend (ADR-0027)."""
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(
            f"{SEEDS_NODE_CLASS} not registered -- the ADR-0038-amendment "
            "volumetry seed carrier has not landed (launched build; ADR-0027)."
        )
    for method in ("AddSeed", "GetNumberOfSeeds", "GetNthSeed"):
        if not hasattr(node, method):
            pytest.skip(
                f"{SEEDS_NODE_CLASS} has no {method} -- the seed carrier API "
                "has not landed (ADR-0027)."
            )
    return node


def _import_table_or_skip():
    """Import the seeds table widget class, or skip-pend (ADR-0027)."""
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VolumetrySeedsTableWidget not importable ({exc!r}) -- the ADR-0038 "
            "seeds table has not landed OR Qt/ctk is not reachable here.  The "
            "skip lifts at the implementation commit (ADR-0027)."
        )
    return VolumetrySeedsTableWidget


def _make_table_or_skip(slicer, carrier):
    """Construct the table over the carrier, or skip-pend the seam (ADR-0027)."""
    VolumetrySeedsTableWidget = _import_table_or_skip()
    try:
        table = VolumetrySeedsTableWidget(carrier=carrier)
    except TypeError as exc:
        pytest.skip(
            f"VolumetrySeedsTableWidget(carrier=) seam absent ({exc!r}) -- the "
            "ADR-0038 widget constructor has not landed (ADR-0027)."
        )
    for method in ("table", "rowCount"):
        if not hasattr(table, method):
            pytest.skip(
                f"VolumetrySeedsTableWidget has no {method} seam (ADR-0027)."
            )
    return table


# --------------------------------------------------------------------------- #
# ROW-PER-SEED + carrier-modified rebuild
# --------------------------------------------------------------------------- #


def test_table_has_one_row_per_seed(qt_widgets):
    """The table renders one row per carrier seed, matching the seed count."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    for x, y, z in [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)]:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    assert table.rowCount() == carrier.GetNumberOfSeeds() == 3, (
        "the table must render one row per carrier seed."
    )
    assert table.table().rowCount == 3


def test_carrier_modified_event_rebuilds_the_table(qt_widgets):
    """A carrier ``ModifiedEvent`` rebuilds the table (the carrier is the model).

    Adding a seed to the carrier (outside the table) grows the row count with
    no explicit refresh -- the table observes the carrier.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)

    carrier.AddSeed(1.0, 0.0, 0.0)
    before = table.rowCount()

    carrier.AddSeed(2.0, 0.0, 0.0)  # fires ModifiedEvent

    after = table.rowCount()
    assert after == before + 1, (
        "a carrier ModifiedEvent must rebuild the table (row count grows with "
        "the seed count) -- the carrier is the model, no manual refresh."
    )


# --------------------------------------------------------------------------- #
# LABEL edit -- writes SetNthSeedLabel without touching geometry
# --------------------------------------------------------------------------- #


def test_editing_the_label_line_edit_writes_set_nth_seed_label(qt_widgets):
    """Committing the row's ``QLineEdit`` writes ``SetNthSeedLabel`` on the carrier.

    ADR-0038 §Conformance: the per-seed label becomes the generated segment
    name.  Committing an edit (setting the text + emitting ``editingFinished``)
    routes through ``setSeedLabel`` and writes the carrier -- without moving the
    seed coordinate.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedLabel"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedLabel (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "labelEdit"):
        pytest.skip("VolumetrySeedsTableWidget has no labelEdit seam (ADR-0027).")

    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.Modified()

    edit = table.labelEdit(0)
    assert edit is not None, "the seed row must carry an editable label QLineEdit."

    edit.setText("SegmentV")
    edit.editingFinished()  # commit the edit

    assert carrier.GetNthSeedLabel(0) == "SegmentV", (
        "committing the label QLineEdit must write SetNthSeedLabel on the "
        "carrier (the generated segment name; ADR-0038 §Conformance)."
    )
    # The display edit must not move the seed.
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((1.0, 2.0, 3.0), abs=1e-9), (
        "a label edit must NOT move the seed coordinate (ADR-0014 four-layer)."
    )


def test_set_seed_color_writes_carrier_without_touching_geometry(qt_widgets):
    """``setSeedColor`` writes ``SetNthSeedColor`` without moving the seed.

    ADR-0014 §"Fourth layer": a display edit writes the display slot only; the
    seed coordinate stays byte-identical.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "SetNthSeedColor"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no SetNthSeedColor (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "setSeedColor"):
        pytest.skip("VolumetrySeedsTableWidget has no setSeedColor seam (ADR-0027).")

    carrier.AddSeed(4.0, 5.0, 6.0)
    carrier.Modified()

    table.setSeedColor(0, 0.3, 0.6, 0.9)

    color = carrier.GetNthSeedColor(0)
    assert (color[0], color[1], color[2]) == pytest.approx((0.3, 0.6, 0.9), abs=1e-6)
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((4.0, 5.0, 6.0), abs=1e-9), (
        "a colour edit must NOT move the seed coordinate (ADR-0014 four-layer)."
    )


# --------------------------------------------------------------------------- #
# DELETE -- drops exactly that seed via RemoveNthSeed
# --------------------------------------------------------------------------- #


def test_delete_seed_removes_exactly_one_point(qt_widgets):
    """``deleteSeed`` removes EXACTLY ONE carrier seed; survivors keep order."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "RemoveNthSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no RemoveNthSeed (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteSeed"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteSeed seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    table.deleteSeed(1)

    assert carrier.GetNumberOfSeeds() == len(pts) - 1, (
        "delete-by-row must remove EXACTLY ONE carrier seed."
    )
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx(pts[2], abs=1e-6)


def test_delete_button_removes_exactly_that_seed(qt_widgets):
    """Clicking a row's delete button removes exactly that seed via the carrier."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    if not hasattr(carrier, "RemoveNthSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS} has no RemoveNthSeed (ADR-0027).")
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "deleteButton"):
        pytest.skip("VolumetrySeedsTableWidget has no deleteButton seam (ADR-0027).")

    pts = [(0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    for x, y, z in pts:
        carrier.AddSeed(x, y, z)
    carrier.Modified()

    delete = table.deleteButton(1)
    assert delete is not None, "the seed row must carry a delete button."
    delete.click()

    assert carrier.GetNumberOfSeeds() == len(pts) - 1, (
        "clicking a row's delete button must remove EXACTLY ONE carrier seed."
    )
    assert tuple(carrier.GetNthSeed(0)) == pytest.approx(pts[0], abs=1e-6)
    assert tuple(carrier.GetNthSeed(1)) == pytest.approx(pts[2], abs=1e-6)


# --------------------------------------------------------------------------- #
# OBSERVER teardown
# --------------------------------------------------------------------------- #


def test_cleanup_detaches_the_carrier_observer(qt_widgets):
    """``cleanup`` detaches the carrier observer so nothing survives shutdown.

    A parentless Qt widget holding a MRML observer crashes SlicerApp on
    shutdown (feedback_launched_widget_teardown_crash).  After ``cleanup``, a
    carrier ``ModifiedEvent`` no longer rebuilds the table.
    """
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    if not hasattr(table, "cleanup"):
        pytest.skip("VolumetrySeedsTableWidget has no cleanup seam (ADR-0027).")

    carrier.AddSeed(1.0, 0.0, 0.0)
    before = table.rowCount()

    table.cleanup()
    carrier.AddSeed(2.0, 0.0, 0.0)  # fires ModifiedEvent; observer is detached

    assert table.rowCount() == before, (
        "after cleanup, a carrier ModifiedEvent must NOT rebuild the table -- "
        "the observer was detached (feedback_launched_widget_teardown_crash)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
