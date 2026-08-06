# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the per-seed VISIBILITY CONTEXT on the seed carrier.

A volumetry seed records the ordered set of segment IDs visible at placement
(top-first) alongside its owning-segment binding: that snapshot IS the seed's
reproducible definition (the visibility-composed carve rule,
``VisibilityCarve``).  This file pins the carrier slot:

* SET/GET -- ``SetNthSeedVisibilityContext`` stores an ordered segment-ID
  list; ``GetNthSeedVisibilityContext`` returns it verbatim (order preserved).
* PARALLEL SLOT -- the context rides the same placement index as the
  coordinate / label / binding: a remove shifts it in lockstep, and a context
  write never perturbs the coordinate (ADR-0014 four-layer discipline).
* DEFAULT EMPTY -- a fresh seed carries an empty context (a legacy seed
  semantics: no snapshot, no carve).
* STORAGE ROUND-TRIP -- the ``.vsd.json`` document persists the context and a
  read restores it in order.

HARNESS: launched Slicer (wrapped C++ node).  SKIPS CLEANLY bare via the
shared guards; RUNS launched (ADR-0027).
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
STORAGE_NODE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_carrier_or_skip(slicer, name="SeedsContextCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    if not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} has no SetNthSeedVisibilityContext -- the "
            "visibility-context slot has not landed (ADR-0027)."
        )
    return node


def _string_array(vtk, values):
    arr = vtk.vtkStringArray()
    for value in values:
        arr.InsertNextValue(value)
    return arr


def _context_of(vtk, carrier, index):
    out = vtk.vtkStringArray()
    carrier.GetNthSeedVisibilityContext(index, out)
    return [out.GetValue(i) for i in range(out.GetNumberOfValues())]


def test_context_round_trips_in_order():
    """The snapshot list comes back verbatim, order preserved (top-first)."""
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(1.0, 2.0, 3.0)

    carrier.SetNthSeedVisibilityContext(0, _string_array(vtk, ["Tumor", "Segment_2", "Parenchyma"]))

    assert _context_of(vtk, carrier, 0) == ["Tumor", "Segment_2", "Parenchyma"], (
        "the visibility context must round-trip in order -- the snapshot IS "
        "the seed's reproducible definition."
    )


def test_fresh_seed_has_an_empty_context():
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(0.0, 0.0, 0.0)

    assert _context_of(vtk, carrier, 0) == [], (
        "a fresh seed carries an empty context (legacy semantics: no carve)."
    )


def test_context_write_does_not_move_the_seed():
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(4.0, 5.0, 6.0)

    carrier.SetNthSeedVisibilityContext(0, _string_array(vtk, ["A"]))

    assert tuple(carrier.GetNthSeed(0)) == pytest.approx((4.0, 5.0, 6.0), abs=1e-9), (
        "a context write must NOT move the seed coordinate (ADR-0014 four-layer)."
    )


def test_remove_shifts_the_context_in_lockstep():
    """Removing a seed shifts the tail contexts up with their coordinates."""
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    for i in range(3):
        carrier.AddSeed(float(i), 0.0, 0.0)
        carrier.SetNthSeedVisibilityContext(i, _string_array(vtk, [f"ctx{i}"]))

    carrier.RemoveNthSeed(1)

    assert _context_of(vtk, carrier, 0) == ["ctx0"]
    assert _context_of(vtk, carrier, 1) == ["ctx2"], (
        "the context is a PARALLEL slot: a remove shifts it in lockstep with "
        "the coordinate."
    )


def test_out_of_range_context_access_is_safe():
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    carrier.SetNthSeedVisibilityContext(5, _string_array(vtk, ["A"]))  # no-op
    assert _context_of(vtk, carrier, 5) == []


def test_storage_round_trips_the_context(tmp_path):
    """The .vsd.json document persists + restores the per-seed context."""
    slicer = _slicer_or_skip()
    import vtk

    carrier = _make_carrier_or_skip(slicer)
    carrier.AddSeed(1.0, 2.0, 3.0)
    carrier.SetNthSeedBinding(0, "sceneSegID", "Parenchyma")
    carrier.SetNthSeedVisibilityContext(0, _string_array(vtk, ["Segment_1", "Parenchyma"]))

    storage = slicer.mrmlScene.AddNewNodeByClass(STORAGE_NODE_CLASS)
    if storage is None:
        pytest.skip(f"{STORAGE_NODE_CLASS} not registered (ADR-0027).")
    path = str(tmp_path / "context-roundtrip.vsd.json")
    storage.SetFileName(path)
    assert storage.WriteData(carrier) == 1

    sink = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "ContextSink")
    reader = slicer.mrmlScene.AddNewNodeByClass(STORAGE_NODE_CLASS)
    reader.SetFileName(path)
    assert reader.ReadData(sink) == 1

    assert _context_of(vtk, sink, 0) == ["Segment_1", "Parenchyma"], (
        "the storage document must round-trip the visibility context in order."
    )
    assert sink.GetNthSeedBindingSegmentID(0) == "Parenchyma"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
