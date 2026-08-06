# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- selecting a seed row restores its visibility snapshot.

A volumetry seed's reproducible definition is its placement-time VISIBILITY
CONTEXT (the visibility-composed carve rule, ``VisibilityCarve``).  Selecting
the seed's row in the seeds table flips the segmentation's segment visibility
to EXACTLY that snapshot -- the view shows the composition that defines the
seed.  Deselecting restores nothing (the last selected context stays).

Pins on the table widget:

* SELECT RESTORES -- selecting a seed row shows exactly the snapshot's
  segments on the structure-source display node and hides the rest.
* EMPTY SNAPSHOT IS A NO-OP -- a legacy seed with no context must not blank
  the view.
* A11Y TEXT -- the seed row names its owning segment + context in text
  (tooltip), never colour/animation alone (ADR-0010).

HARNESS: launched Slicer (Qt + wrapped carrier).  SKIPS CLEANLY bare via the
shared guards; RUNS launched (ADR-0027).
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


def _make_carrier_or_skip(slicer, name="RestoreSelectCarrierTest"):
    node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, name)
    if node is None:
        pytest.skip(f"{SEEDS_NODE_CLASS} not registered (launched build; ADR-0027).")
    if not hasattr(node, "SetNthSeedVisibilityContext"):
        pytest.skip(
            f"{SEEDS_NODE_CLASS} has no SetNthSeedVisibilityContext (ADR-0027)."
        )
    return node


def _make_table_or_skip(slicer, carrier):
    try:
        from LiverVolumetryLib.VolumetrySeedsTableWidget import (
            VolumetrySeedsTableWidget,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(f"VolumetrySeedsTableWidget not importable ({exc!r}).")
    return VolumetrySeedsTableWidget(carrier=carrier)


def _make_segmentation(slicer, name="RestoreSelectSegSrc"):
    segmentation = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", name)
    segmentation.CreateDefaultDisplayNodes()
    for segmentID, segmentName in (
        ("Parenchyma", "Parenchyma"),
        ("Segment_1", "Segment 1"),
        ("Tumor", "Tumor"),
    ):
        segmentation.GetSegmentation().AddEmptySegment(segmentID, segmentName)
    return segmentation


def _set_context(carrier, index, context):
    import vtk

    ids = vtk.vtkStringArray()
    for segmentID in context:
        ids.InsertNextValue(segmentID)
    carrier.SetNthSeedVisibilityContext(index, ids)


def _select_seed_row(table, seedIndex):
    """Select the tree item carrying ``seedIndex`` (the child seed row)."""
    import qt

    tree = table.tree()
    it = qt.QTreeWidgetItemIterator(tree)
    while it.value():
        item = it.value()
        if item.data(0, qt.Qt.UserRole) == seedIndex:
            tree.setCurrentItem(item)
            return True
        it += 1
    return False


def test_selecting_a_seed_row_restores_its_snapshot(qt_widgets):
    """Selecting the row flips visibility to exactly the seed's context."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    display = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "Parenchyma")
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    # Start from a DIFFERENT live visibility so the restore is observable.
    display.SetSegmentVisibility("Parenchyma", False)
    display.SetSegmentVisibility("Segment_1", False)
    display.SetSegmentVisibility("Tumor", True)

    assert _select_seed_row(table, 0), "the seed row must be selectable."

    assert display.GetSegmentVisibility("Parenchyma"), (
        "selecting a seed row must SHOW its snapshot's segments."
    )
    assert display.GetSegmentVisibility("Segment_1")
    assert not display.GetSegmentVisibility("Tumor"), (
        "selecting a seed row must HIDE segments outside its snapshot."
    )


def test_selecting_a_snapshotless_seed_keeps_the_view(qt_widgets):
    """A legacy seed (empty context) must not blank the live visibility."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation = _make_segmentation(slicer)
    display = segmentation.GetDisplayNode()

    carrier.AddSeed(0.0, 0.0, 0.0)  # no context snapshot

    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    display.SetSegmentVisibility("Tumor", True)

    assert _select_seed_row(table, 0)

    assert display.GetSegmentVisibility("Tumor"), (
        "an empty snapshot is a NO-OP -- the live view stays."
    )


def test_seed_row_names_owner_and_context_in_text(qt_widgets):
    """The seed row's text (tooltip) names the owning segment + the context
    (ADR-0010: never colour/animation alone)."""
    slicer = _slicer_or_skip()
    _qt_or_skip()
    carrier = _make_carrier_or_skip(slicer)
    segmentation = _make_segmentation(slicer)

    carrier.AddSeed(0.0, 0.0, 0.0)
    carrier.SetNthSeedBinding(0, segmentation.GetID(), "Parenchyma")
    _set_context(carrier, 0, ["Segment_1", "Parenchyma"])

    table = _make_table_or_skip(slicer, carrier)
    qt_widgets.append(table)
    table.setStructureSource(segmentation)

    row = table._seed_rows.get(0)  # noqa: SLF001 - introspection seam
    assert row is not None
    tip = row["widget"].toolTip
    tip = tip() if callable(tip) else tip
    assert "Parenchyma" in tip, "the row text must name the owning segment."
    assert "Segment 1" in tip, "the row text must name the context segments."


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
