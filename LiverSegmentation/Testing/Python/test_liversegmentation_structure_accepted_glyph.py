# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Invariant 8 (UI) — isStructureAccepted(sct) + per-tab confirmation glyph.

The Stage-2 panel is a ``QTabWidget`` of four structure tabs (Liver
parenchyma / Portal vein / Hepatic vein / Tumors), each carrying a
confirmation glyph in its tab label that mirrors the Liver-shell idiom
(``Liver/Liver.py`` ``_stageIndicatorState`` -> ``_indicatorGlyph``, the
✓ / ● / ○ set).  A tab flips ○ -> ✓ once the CANONICAL node holds a segment
SCT-tagged for that structure — i.e. only after that structure's Accept.

The predicate driving the glyph is a new orchestrator method
``isStructureAccepted(<sct target>)`` that reads the CANONICAL node ONLY
(role-filtered, like ``_findCanonicalSegmentation``).  Scratch nodes must
never flip a tab to ✓ (canonical-only read), per ADR-0024 §"Output contract"
+ §Terminology.

Two layers are pinned:
  * **Logic** — ``isStructureAccepted(sct)`` is False pre-Accept, True after
    that structure's Accept, and stays False for scratch-only state.  This
    layer is exercised by instantiating the logic directly (scene-needing).
  * **Glyph** — the structure tab's label carries the pending glyph (○)
    before Accept and the complete glyph (✓) after, reusing the shell's
    glyph set.  This layer is exercised by constructing the widget
    (widget-needing).

Watch the PythonQt int-property gotcha: ``QTabWidget.count`` /
``.currentIndex`` are *properties*, not callables — read them as attributes.

Scene/widget-needing: launched-Slicer harness (``pytest_launched``).
RED until the implementer lands ``isStructureAccepted`` + the tab-glyph
refresh per ADR-0024.
"""

from __future__ import annotations

import pytest

MODULE_NAME = "liversegmentation"
ROLE_ATTRIBUTE = "LiverSegmentation.Role"
ROLE_SCRATCH = "scratch"
ROLE_CANONICAL = "canonical"
TERMINOLOGY_ENTRY_TAG = "TerminologyEntry"

# SCT type codes per ADR-0024 §"Output contract".
SCT_LIVER_CODE = "10200004"
SCT_PORTAL_VEIN_CODE = "32764006"
SCT_HEPATIC_VEIN_CODE = "8993003"
SCT_MASS_CODE = "4147007"

# Confirmation glyphs reused from the Liver shell (Liver/Liver.py
# _INDICATOR_COMPLETE / _INDICATOR_PENDING).  Named here so the per-tab glyph
# contract is grep-able and stays in lockstep with the shell's idiom.
GLYPH_COMPLETE = "✓"  # ✓
GLYPH_PENDING = "○"   # ○


def _logic_or_skip():
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    module = getattr(slicer.modules, MODULE_NAME, None)
    if module is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 Stage-2 "
            "surgeon-UI deliverable absent; isStructureAccepted cannot be "
            "exercised yet."
        )
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(
            f"LiverSegmentation not importable ({exc}); "
            "ensure --additional-module-paths includes LiverSegmentation/."
        )
    return slicer, LiverSegmentation.LiverSegmentationLogic()


def _add_canonical_with_sct(slicer, orch, code, meaning):
    """LAND one SCT-tagged segment on the canonical node via ``accept()``.

    Drives the production landing path (scratch -> Accept) rather than
    hand-tagging a canonical segment: under ADR-0034 §Amendments "accepted"
    reads through the native segment status (a landed segment is
    ``InProgress``; a pre-seeded empty placeholder stays ``NotStarted`` and
    does NOT count), so the fixture must land, not merely tag.
    """
    scratch = orch.createScratchSegmentation()
    segId = scratch.GetSegmentation().AddEmptySegment(meaning, meaning)
    orch.tagSegmentWithSct(scratch, segId, code, meaning)
    return orch.accept(scratch)


def test_isstructureaccepted_false_before_accept():
    """No canonical segment for a structure -> isStructureAccepted is False.

    ADR-0024 §"Output contract": a structure is "accepted" only once the
    canonical node carries a segment SCT-tagged for it.  Empty scene -> every
    structure is unaccepted.
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    if not hasattr(orch, "isStructureAccepted"):
        pytest.fail(
            "orchestrator must expose isStructureAccepted(sctTarget) reading "
            "the canonical node only, to drive the per-tab confirmation glyph "
            "(ADR-0024 §'Output contract') -- not yet implemented."
        )
    for code in (
        SCT_LIVER_CODE,
        SCT_PORTAL_VEIN_CODE,
        SCT_HEPATIC_VEIN_CODE,
        SCT_MASS_CODE,
    ):
        assert orch.isStructureAccepted(code) is False, (
            f"isStructureAccepted({code}) must be False on an empty scene."
        )


def test_isstructureaccepted_true_after_that_structures_accept():
    """Canonical holds the structure's SCT segment -> isStructureAccepted True.

    ADR-0024 §"Output contract": once Accept lands a Portal-vein-tagged
    segment in the canonical node, isStructureAccepted(32764006) is True while
    the other structures remain False (per-structure, not global).
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    if not hasattr(orch, "isStructureAccepted"):
        pytest.fail(
            "orchestrator must expose isStructureAccepted(sctTarget) "
            "(ADR-0024 §'Output contract') -- not yet implemented."
        )

    _add_canonical_with_sct(slicer, orch, SCT_PORTAL_VEIN_CODE, "Portal vein")

    assert orch.isStructureAccepted(SCT_PORTAL_VEIN_CODE) is True, (
        "isStructureAccepted must be True once the canonical node holds that "
        "structure's SCT-tagged segment (ADR-0024 §'Output contract')."
    )
    assert orch.isStructureAccepted(SCT_LIVER_CODE) is False, (
        "isStructureAccepted is per-structure: accepting Portal vein must not "
        "flip Liver parenchyma to accepted."
    )


def test_isstructureaccepted_ignores_scratch_only_state():
    """A scratch-only SCT segment must NOT mark the structure accepted.

    ADR-0024 §Terminology + §"Output contract": the predicate is a
    canonical-only read (mirroring ``_findCanonicalSegmentation``).  A scratch
    node tagged for a structure is pending, not accepted, so the tab stays ○.
    """
    slicer, orch = _logic_or_skip()
    slicer.mrmlScene.Clear(0)
    for name in ("isStructureAccepted", "createScratchSegmentation", "tagSegmentWithSct"):
        if not hasattr(orch, name):
            pytest.fail(
                f"orchestrator missing '{name}' per ADR-0024 -- not yet "
                "implemented."
            )

    scratch = orch.createScratchSegmentation()
    segId = scratch.GetSegmentation().AddEmptySegment("liver", "Liver")
    orch.tagSegmentWithSct(scratch, segId, SCT_LIVER_CODE, "Liver")

    assert orch.isStructureAccepted(SCT_LIVER_CODE) is False, (
        "a scratch-only SCT segment must not mark the structure accepted -- "
        "isStructureAccepted reads the canonical node only (ADR-0024 "
        "§Terminology)."
    )


def _build_widget_or_skip(slicer, registry):
    """Construct the LiverSegmentationWidget under a launched Slicer.

    Widget-needing: skips cleanly under bare PythonSlicer (no qt.QWidget).
    The widget is registered with the ``qt_widgets`` fixture's ``registry``
    so its Qt tree is disposed in teardown (otherwise it survives to process
    shutdown and trips vtkDebugLeaks in the launched harness).
    """
    from conftest import _require_qt_widget

    _require_qt_widget()
    try:
        import LiverSegmentation  # type: ignore[import-not-found]
    except ImportError as exc:
        pytest.skip(f"LiverSegmentation not importable ({exc}).")
    widget = LiverSegmentation.LiverSegmentationWidget()
    widget.setup()
    registry.append(widget)
    return widget


def _structure_tab_widget(widget):
    """Return the QTabWidget of structure tabs, or fail with guidance.

    TODO(impl): pin the attribute name the implementer wires the QTabWidget
    to (e.g. ``widget.structureTabs`` / ``widget.ui.StructureTabs``).  The
    pinned invariant is "four structure tabs each carrying a confirmation
    glyph", not the attribute spelling.
    """
    for attr in ("structureTabs", "_structureTabs"):
        tabs = getattr(widget, attr, None)
        if tabs is not None:
            return tabs
    ui = getattr(widget, "ui", None)
    if ui is not None:
        for attr in ("StructureTabs", "structureTabs"):
            tabs = getattr(ui, attr, None)
            if tabs is not None:
                return tabs
    return None


def test_structure_tabs_carry_confirmation_glyphs(qt_widgets):
    """Four structure tabs, each label prefixed with a confirmation glyph.

    ADR-0024 §"Per-structure micro-workflows" surgeon UI: a QTabWidget of the
    four structure tabs, mirroring the Liver-shell glyph idiom
    (``Liver/Liver.py`` _indicatorGlyph, ✓ / ● / ○).  Pre-Accept every tab
    shows the pending glyph (○).

    NOTE PythonQt gotcha: ``QTabWidget.count`` is a *property*, not a
    callable; read it as an attribute (not ``.count()``).
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()
    if getattr(slicer.modules, MODULE_NAME, None) is None:
        pytest.skip(
            f"'{MODULE_NAME}' module not registered -- ADR-0024 surgeon-UI "
            "deliverable absent."
        )
    slicer.mrmlScene.Clear(0)
    widget = _build_widget_or_skip(slicer, qt_widgets)
    tabs = _structure_tab_widget(widget)
    if tabs is None:
        pytest.fail(
            "widget must host a QTabWidget of four structure tabs "
            "(Liver / Portal vein / Hepatic vein / Tumors) per ADR-0024 "
            "§'Per-structure micro-workflows' -- not yet implemented."
        )
    # PythonQt: .count is a property, not a callable.
    assert tabs.count == 4, (
        f"expected 4 structure tabs, got {tabs.count} (ADR-0024 four "
        "per-structure cards)."
    )
    for index in range(tabs.count):
        label = tabs.tabText(index)
        assert label.startswith(GLYPH_PENDING) or label.lstrip().startswith(
            GLYPH_PENDING
        ), (
            f"tab {index} label '{label}' must carry the pending glyph "
            f"'{GLYPH_PENDING}' pre-Accept, mirroring the Liver-shell "
            "idiom (Liver/Liver.py _indicatorGlyph)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
