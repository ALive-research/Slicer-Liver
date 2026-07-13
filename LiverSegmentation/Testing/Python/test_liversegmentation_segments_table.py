# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""ADR-0034 increment 1 — the read-only anatomy segments table.

Stage 2's panel gains a single always-visible segments table, pre-seeded
with the expected structures BEFORE any data exists (the empty state
teaches the goal), rendered from the current canonical-node state.  This
increment is read-only: it lands alongside the existing tabs; row
actions, the tab retirement, and the queue arrive in later increments.

Pins (ADR-0034 §Conformance):

  * Pre-seeded rows exist with ``○ Missing`` before any data — one row
    per structure-vocabulary entry, in surgeon-workflow order.
  * Row status derivation from canonical state: no SCT segment ->
    ``○ Missing`` (or ``∅ Marked absent`` under the explicit
    attestation attribute); SCT segment present -> ``● Review``;
    the per-segment confirm tag -> ``✓ Confirmed``.  Status renders as
    GLYPH + TEXT, never colour alone (ADR-0010).
  * The table refreshes from the scene: a segment landing in the
    canonical node flips its row Missing -> Review.

Needs the launched-Slicer harness (module + Qt + MRML); skips cleanly
under bare pytest via the shared guards.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"


def _slicer_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _module_or_skip():
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    return LiverSegmentation


def _widget_or_skip(slicer, registry):
    from conftest import _require_qt_widget

    _require_qt_widget()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 surgeon-UI "
            "deliverable absent."
        )
    module = _module_or_skip()
    widget = module.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _status_text(table, row):
    """The rendered status cell text (glyph + text in one cell)."""
    item = table.item(row, _column(table, "Status"))
    return item.text() if item is not None else ""


def _column(table, title):
    for col in range(table.columnCount):
        header = table.horizontalHeaderItem(col)
        if header is not None and header.text() == title:
            return col
    raise AssertionError(f"no {title!r} column in the segments table")


def test_table_pre_seeded_with_missing_rows(qt_widgets):
    """One row per vocabulary structure, all ``○ Missing``, before any
    data exists — the empty state names the goal (ADR-0034 §Decision 1)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    widget = _widget_or_skip(slicer, qt_widgets)

    table = widget.segmentsTable()
    assert table is not None, (
        "the Stage-2 panel must host the anatomy segments table "
        "(ADR-0034 §Decision 1)."
    )
    assert table.rowCount == len(module.STRUCTURE_TABS), (
        "one pre-seeded row per structure-vocabulary entry."
    )
    structure_col = _column(table, "Structure")
    for row, (title, _code) in enumerate(module.STRUCTURE_TABS):
        assert table.item(row, structure_col).text() == title, (
            "rows follow the surgeon-workflow vocabulary order."
        )
        status = _status_text(table, row)
        assert "○" in status and "Missing" in status, (
            f"pre-seeded row {title!r} must read '○ Missing' (glyph + "
            f"text, ADR-0010); got {status!r}."
        )
    source_col = _column(table, "Source")
    assert table.item(0, source_col).text() == "—", (
        "no data -> the Source column reads the em-dash placeholder."
    )


def test_status_derivation_from_canonical_state():
    """``structureStatus(canonical, code)`` — the row-status vocabulary
    derived from the canonical node (ADR-0034 §Decision 2 semantics,
    readable before the writers land in increment 2)."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()

    # No canonical node at all -> Missing.
    assert module.structureStatus(None, module.SCT_LIVER_CODE) == (
        module.STATUS_MISSING
    )

    logic = module.LiverSegmentationLogic()
    canonical = logic.getOrCreateCanonicalSegmentation()
    try:
        # Canonical exists but holds no liver segment -> Missing.
        assert (
            module.structureStatus(canonical, module.SCT_LIVER_CODE)
            == module.STATUS_MISSING
        )

        # The explicit clinical attestation (never inferred): the
        # marked-absent attribute flips the EMPTY row to Marked absent.
        canonical.SetAttribute(
            module.MARKED_ABSENT_ATTRIBUTE_PREFIX + module.SCT_MASS_CODE, "1"
        )
        assert (
            module.structureStatus(canonical, module.SCT_MASS_CODE)
            == module.STATUS_MARKED_ABSENT
        )

        # An SCT-tagged segment lands -> Review (nothing counts until the
        # surgeon confirms; ADR-0034 §Decision 2).
        segment_id = canonical.GetSegmentation().AddEmptySegment("liver")
        logic.tagSegmentWithSct(
            canonical, segment_id, module.SCT_LIVER_CODE, "Liver"
        )
        assert (
            module.structureStatus(canonical, module.SCT_LIVER_CODE)
            == module.STATUS_REVIEW
        )

        # The per-segment confirm tag -> Confirmed.
        canonical.GetSegmentation().GetSegment(segment_id).SetTag(
            module.CONFIRMED_TAG, "1"
        )
        assert (
            module.structureStatus(canonical, module.SCT_LIVER_CODE)
            == module.STATUS_CONFIRMED
        )
    finally:
        slicer.mrmlScene.RemoveNode(canonical)


def test_table_refreshes_when_a_segment_lands(qt_widgets):
    """A segment landing in the canonical node flips its row
    Missing -> Review on refresh; the other rows stay Missing."""
    slicer = _slicer_or_skip()
    module = _module_or_skip()
    widget = _widget_or_skip(slicer, qt_widgets)

    logic = widget.logic
    canonical = logic.getOrCreateCanonicalSegmentation()
    try:
        segment_id = canonical.GetSegmentation().AddEmptySegment("liver")
        logic.tagSegmentWithSct(
            canonical, segment_id, module.SCT_LIVER_CODE, "Liver"
        )
        widget._refreshSegmentsTable()
        table = widget.segmentsTable()

        assert "Review" in _status_text(table, 0), (
            "the liver row must flip to '● Review' once its SCT segment "
            "lands in the canonical node."
        )
        assert "Missing" in _status_text(table, 1), (
            "rows without a canonical segment stay '○ Missing'."
        )
    finally:
        slicer.mrmlScene.RemoveNode(canonical)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
