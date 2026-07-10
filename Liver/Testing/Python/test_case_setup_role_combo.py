# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Stage-1 Case Setup: per-row role combo in the volumes table.

Walkthrough finding (2026-07-09): the standalone role dropdown +
"Assign role" button cost a selection round-trip per volume.  The Role
column hosts a QComboBox PER ROW instead — pick the role directly in
the row; the default is an explicit **None** entry, distinct from the
acquisition-phase vocabulary, and selecting it clears the tag.  The
combo writes the same shared ``LiverRole`` attribute downstream stages
read (the Stage-1/Stage-2 hand-off).
"""

from __future__ import annotations

import pytest


def _widget_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip,
        register_widget_for_teardown,
        require_mrml_scene,
        require_qt_widget,
    )

    require_qt_widget()
    slicer = import_slicer_or_skip()
    require_mrml_scene()
    try:
        import Liver  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"Liver shell not importable ({exc}).")
    widget = Liver.LiverWidget(None)
    widget.setup()
    return slicer, register_widget_for_teardown(widget)


def _add_volume(slicer, name, role=None):
    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", name)
    if role is not None:
        from LiverSegmentationLib.roles import set_volume_role

        assert set_volume_role(volume, role)
    return volume


def test_role_table_hosts_a_per_row_combo_defaulting_to_none():
    """Each table row carries a role QComboBox; untagged rows read None."""
    import qt

    slicer, widget = _widget_or_skip()
    untagged = _add_volume(slicer, "CaseComboUntagged")
    tagged = _add_volume(slicer, "CaseComboTagged", role="PortalVenous")
    try:
        widget._refreshCaseSetupTable()
        table = widget._caseSetupTable
        assert table is not None and table.rowCount >= 2

        by_name = {}
        for row in range(table.rowCount):
            item = table.item(row, 0)
            combo = table.cellWidget(row, 1)
            assert isinstance(combo, qt.QComboBox), (
                "the Role column must host a QComboBox per row (the "
                "select-then-Assign round-trip is retired)."
            )
            by_name[item.text()] = combo

        untagged_combo = by_name["CaseComboUntagged"]
        assert untagged_combo.itemData(untagged_combo.currentIndex) is None, (
            "an untagged volume's combo must sit on the explicit None entry."
        )
        tagged_combo = by_name["CaseComboTagged"]
        assert tagged_combo.itemData(tagged_combo.currentIndex) == "PortalVenous", (
            "a tagged volume's combo must reflect its stored LiverRole."
        )
    finally:
        slicer.mrmlScene.RemoveNode(untagged)
        slicer.mrmlScene.RemoveNode(tagged)


def test_row_combo_writes_and_clears_the_role():
    """Selecting a role tags the row's volume; selecting None clears it."""
    slicer, widget = _widget_or_skip()
    volume = _add_volume(slicer, "CaseComboWrite")
    try:
        widget._refreshCaseSetupTable()
        table = widget._caseSetupTable
        combo = None
        for row in range(table.rowCount):
            if table.item(row, 0).text() == "CaseComboWrite":
                combo = table.cellWidget(row, 1)
        assert combo is not None

        index = combo.findData("PortalVenous")
        assert index >= 0, "the role vocabulary must be offered in the combo"
        combo.setCurrentIndex(index)
        assert volume.GetAttribute("LiverRole") == "PortalVenous", (
            "picking a role in the row must write the shared LiverRole "
            "attribute (the Stage-1/Stage-2 hand-off)."
        )

        none_index = combo.findData(None)
        combo.setCurrentIndex(none_index)
        assert volume.GetAttribute("LiverRole") is None, (
            "selecting the None entry must CLEAR the tag."
        )
    finally:
        slicer.mrmlScene.RemoveNode(volume)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
