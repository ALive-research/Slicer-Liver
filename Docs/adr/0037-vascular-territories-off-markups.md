# 0037. VascularTerritories transition off markups onto LayerDM custom artifacts + table UI

- **Status:** Accepted
- **Date:** 2026-07-14
- **Deciders:** Rafael Palomar
- **Diagrams:** [`Docs/architecture/territories-class-hierarchy.md`](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/territories-class-hierarchy.md) (extended during implementation with the annotation carrier)
- **Supersedes:** [ADR-0036](0036-vessel-highlight-separate-instance.md) (scoped only the hover highlight as a separate instance; this ADR subsumes it into the full module transition).
- **Relates to:** the resection-plan transition —
  [ADR-0032](0032-v2-interaction-via-layerdm-pipeline-seam.md) (interaction through the Pipeline seam),
  [ADR-0033](0033-control-polygon-display-aspect.md) (hover discipline),
  [ADR-0034](0034-stage2-segments-table.md) (table UI paradigm),
  [ADR-0025](0025-locator-architecture.md) (the pick-core reused);
  and the dissolution direction of
  [ADR-0002](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0002-migrate-to-slicerlayerdm.md),
  [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md),
  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md),
  [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md).
- **PR:** <filled in on merge>

## Context

VascularTerritories annotates vessels by placing endpoint markers that
seed VMTK centerline extraction; those markers are Slicer
`vtkMRMLMarkupsFiducialNode`s, and the module's widget, its
`vtkMRMLCustomTerritoriesNode` (whose header declares an unimplemented
`EndpointRefs` markups-reference slot), and its VMTK feed are all
coupled to markups.  Issue #569 was written as a "display-node
migration"; the maintainer corrected the scope: **transition the module
off markups entirely onto the v2 architecture, the same way the
resection plan was transitioned**, and make the panel table-based.

The precedent is settled.  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
dissolved the resection's markups assembly onto a
wrapper/carrier/display/storage node family driven by a LayerDM
scripted Pipeline;
[ADR-0032](0032-v2-interaction-via-layerdm-pipeline-seam.md) put the
interaction on that Pipeline's `CanProcess`/`ProcessInteractionEvent`
seam (no `vtkAbstractWidget`, no per-module displayable manager); and
[ADR-0034](0034-stage2-segments-table.md) made the workflow surface a
table.  VascularTerritories is the last annotation surface still on
markups.

The hover half already exists on the feature branch: `VesselSurfacePick`
(ray-onto-surface pick core, unit-tested), `VesselHighlightPipeline`,
and the data-only `vtkMRMLTerritoriesHighlightDisplayNode` —
ADR-0025/0033-conformant, carried forward unchanged.  What remains is to
move the annotation *storage and placement* off markups and the panel
onto a table.

## Decision

1. **Annotation carrier (ADR-0014 Fourth layer).** The ordered,
   surface-snapped annotation points live on the existing
   `vtkMRMLCustomTerritoriesNode` (the Manual/Custom method wrapper) —
   its never-implemented `EndpointRefs` markups slot is replaced by an
   own point carrier, per territory, with a storage node round-trip
   (mirroring `vtkMRMLResectionPlanStorageNode`).  No new parallel node
   family; no markups reference anywhere.  The Auto path
   (`vtkMRMLStdCouinaudTerritoriesNode`, AI labelmap) carries no
   annotation points and is out of scope.

2. **Placement + edit via the Pipeline seam
   ([ADR-0032](0032-v2-interaction-via-layerdm-pipeline-seam.md) /
   [ADR-0033](0033-control-polygon-display-aspect.md)).** A LayerDM
   scripted Pipeline reuses `VesselSurfacePick` + the adhering
   highlight: a click claims the gesture and adds one surface-snapped
   point to the carrier; a drag edits the nearest point; a bare hover is
   declined (camera untouched) beyond raising the highlight.  There is
   **no markup place mode** and **no annotation state machine** —
   add-on-click / drag-to-edit / delete-from-table is the whole
   lifecycle (the table row is the state).

3. **Table UI ([ADR-0034](0034-stage2-segments-table.md) /
   [ADR-0004](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md)).**
   The legacy `inputSurfaceSelector`/`endPointsMarkupsSelector` panel is
   replaced by a table whose rows are annotation points grouped by
   territory (columns: visibility, colour, territory/label, on-surface
   status, delete).  A **custom** table, not a stock point-list view —
   the surface-snap + territory-grouping contract has no stock fit (the
   same call [ADR-0034](0034-stage2-segments-table.md) made against
   `qMRMLSegmentsTableView` where the contract columns did not fit).
   The panel is modernised to Python-widget composition, not a C++
   widget.

4. **VMTK feed.** `ExtractCenterline` (SlicerVMTK) reads
   `GetNthControlPointPosition` / `GetNumberOfControlPoints` and a
   per-point *selected* flag (the inlet/root discrimination) off a
   markups node.  The transition builds a **transient**
   `vtkMRMLMarkupsFiducialNode` from the carrier's points *inside* the
   extraction call — preserving the start-endpoint `selected`
   convention — and discards it after.  No persistent markups node.
   When SlicerVMTK is absent the module **degrades gracefully**:
   placement and the table work; only the extraction action is disabled
   with an explaining tooltip (today the module hard-gates placement on
   VMTK — that coupling goes away once off markups).

5. **No custom displayable manager
   ([ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md) §5).**
   Rendering + interaction route through the LayerDM scripted Pipeline +
   its factory creator (the three registration calls), never a
   `vtkMRMLAbstractDisplayableManager`.  This is the sanctioned path the
   closed PR #366 (a per-module custom DM) is not: the Pipeline seam
   exists precisely so no per-module DM is needed.

### Staging

Three PRs: (1) annotation off markups — carrier + storage + placement
Pipeline + edit + representations; (2) the table UI + widget
modernisation; (3) the VMTK feed + graceful degradation.

## Alternatives considered

- **Keep Slicer markups for annotation.** Rejected — it is the coupling
  [ADR-0014](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md)
  set the project to leave; VascularTerritories is the last holdout.
- **A per-module custom displayable manager (PR #366 shape).** Rejected
  — [ADR-0013](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md)
  §5; the Pipeline seam supersedes it.
- **A stock point-list table.** Rejected — no stock view carries the
  surface-snap + territory-grouping contract columns (parallel to
  [ADR-0034](0034-stage2-segments-table.md)'s stock-table rejection).
- **A new parallel annotation node family.** Rejected — the existing
  `vtkMRMLCustomTerritoriesNode` is the wrapper; its unimplemented
  endpoint slot becomes the carrier, reconciling with the family rather
  than duplicating it.
- **An explicit annotation state machine
  ([ADR-0019](0019-resection-state-machine.md) shape).** Rejected —
  vessel annotation has no Init→commit boundary; the table row
  lifecycle suffices.  Revisit only if a "freeze after extraction"
  requirement appears.

## Consequences

- VascularTerritories joins the v2 architecture: no markups, LayerDM
  custom artifacts, table UI — consistent with LiverResections and
  Stage 2.
- Placement stops depending on SlicerVMTK; the module is usable for
  annotation with VMTK absent.
- The legacy 1000-line widget's placement/selector surface is rewritten
  toward Python-widget composition; the markups-coupled methods
  (`newEndpointsListCreated`, `onEndpointPlaced`, `updateHighlightWiring`)
  retire.
- ADR-0036's highlight-as-separate-instance reasoning is preserved here;
  a future cross-module locator unification (#572) is a candidate
  consumer of the highlight but must not block this transition.
- The `territories-class-hierarchy.md` diagram is extended with the
  annotation carrier.

## Conformance

- [test] The carrier stores/round-trips ordered per-territory points
  (bare-VTK unit + storage round-trip); no markups reference on the
  node.
- [test] A click through the Pipeline seam adds exactly one
  surface-snapped point; a bare move is declined (ADR-0033 invariant); a
  drag edits exactly one point; delete removes one.
- [test] The transient VMTK markups builder reproduces the carrier
  points with the start-endpoint `selected` flag; extraction is disabled
  (not crashing) when SlicerVMTK is absent while placement still works.
- [review] Rendering/interaction via the LayerDM Pipeline + creator
  only — no `vtkMRMLAbstractDisplayableManager` in VascularTerritories;
  no `vtkMRMLMarkupsFiducialNode` persisted by the annotation path.
- [review] Status/label rendered as glyph + text, never colour alone
  ([ADR-0010](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md)).
- [future] Cross-module locator unification (#572) as a candidate
  consumer of the vessel highlight.
- [future] The Auto/Couinaud path modernisation, if ever taken off its
  current stock display.

## Amendment — the territory-map compute path off the carrier (slices 2 + 3)

The staged transition (§Staging) completed the panel-modernisation half in
two increments beyond §Decision 3.  This amendment records the compute-path
decisions the implementation crystallised, so the retired-widget set and the
final workflow are documented in one place.

### Retired-widget set across slices 2 + 3

Slice 2 retired the table-duplicating v1 surface (`ColorPickerButton`,
`showHideButton`, `addSegmentationButton`, `SegmentsWidget`,
`inputSegmentSelectorWidget`, `vascularTerritoryId`) and their handlers, plus
the dead `_registerVesselHighlightPipeline` and the `copyIndex` Logic helper.
**Slice 3 additionally retires `selectedVascularTerritorySegmId`** — the
per-map output-segmentation selector — together with its `.ui` widget, its
`VascularTerritorySegmentation` param-node role, and its `setup()` wiring.
The Compute-territory-map button and `onCalculateVascularTerritoryMapButton`
survive; only the output *selection* is gone.

### Coherent two-step compute flow

The surviving workflow is a coherent two-step sequence over one input
surface: **place seeds** (add-on-click into the carrier, per §Decision 2) →
**Extract centerlines** (`onAddCenterlineButton` → `extractCenterlines`, the
transient-markups VMTK feed of §Decision 4) → **Compute territory map**
(`onCalculateVascularTerritoryMapButton`).  The compute action gates on an
input surface being selected rather than on a separate output selector.

### Derive the map target from the carrier

The output map target is **derived from the carrier, not selected** — a
carrier node-reference role (`TerritoryMapOutput`) resolves to exactly one
`vtkMRMLSegmentationNode`, auto-created and attached on first compute and
reused thereafter (one carrier == one map, consistent with the
`CenterlineRefs` + `Groupings` map of §Decision 4).  Dropping the selector
removes a manual step and the class of "wrong output picked" error; it also
retires the redundant `int(...)` string-tag reader the old
`slicer.util.getNodes("*Territory*")` scene scan depended on, because
`build_centerline_model` now sources the carrier's `CenterlineRefs` directly.

### Arbitrary-int labelmap scalar (explicitly not an SCT code)

`vtkSlicerVascularTerritoriesLogic::MarkSegmentWithID` stamps a per-territory
integer into each centerline's `segmentId` point-scalar, and
`calculateVascularTerritoryMap` reads + re-stamps a per-map
`VascularTerritories.SegmentationId` ordinal on the output.  Both are
**arbitrary distinct positive labelmap scalars, NOT SCT terminology codes**
([ADR-0011](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0011-sct-terminology-dispatch.md)
reserves SCT for the accepted-plan terminology surface, not this internal
watershed label).  The transition
derives them deterministically: the per-territory int is
`index + 1` over the carrier's `GetAnnotationTerritoryIds()` order (0 is the
labelmap background), so the same territories derive the same ints across
repeated calls (the pure `VascularTerritoriesLib.TerritoryLabelMap` core); the
per-map ordinal is issued one past the maximum `SegmentationId` already
stamped in the scene, so two carriers never collide.

## Amendment — per-territory Place mode + module-active gate (slice 4)

§Decision 2 said placement "adds one point per click" but left the *arming*
implicit ("Add Territory" armed and never disarmed, a panel "Add seeds" /
"Done" pair the only re-arm/disarm).  In use this leaked an armed view across
module switches (a click in another module could still land a seed) and the
panel buttons duplicated per-territory intent.  Slice 4 makes arming an
explicit, per-territory, exclusive toggle and gates it on the module being
active.

### Tree UX — a single-column, header-less tree of composite row widgets (extends §Decision 3)

The panel composes a `qt.QTreeWidget`, not a flat `qt.QTableWidget`:
territories are TOP-LEVEL items and seed points are CHILD items nested under
them (disclosure triangle + indentation).  This diverges from the flat
[ADR-0034](0034-stage2-segments-table.md) segments-table paradigm because
territories have a genuine parent/child structure — seeds belong *to* a
territory — that a flat table cannot express.

The tree drops the column grid and the header entirely: it is **single-column**
(`columnCount == 1`) with a **hidden header** (`header().isHidden()`), and each
item — territory top-level AND seed child — carries ONE composite `QWidget` on
column 0 (`tree.itemWidget(item, 0)`) whose `QHBoxLayout` holds the row's
controls as a **horizontal strip**.  There is no per-column cell layout and no
dead cells under a seed row; the two-level territory→seeds hierarchy is
conveyed structurally by the disclosure triangle + indentation.  The controls
are addressed by NAME (`territoryRowWidget` / `placeButton` /
`visibilityButton` / `colourButton` / `territoryLabelEdit` / `seedRowWidget` /
`seedDeleteButton` / `seedStatusText`), never by column index — the columns no
longer exist.  A **territory** row strip carries, in order, the Place toggle,
the eye-icon visibility toggle, the colour button, an editable label
`QLineEdit`, and a completeness status label; a **seed** row strip carries the
on-surface status label + a delete button.  Navigation stays via `tree()` /
`territoryIds()` / `territoryItem()` / `seedItems()`.

### Per-territory exclusive Place toggle (extends §Decision 2)

Each territory row strip leads with a checkable **Place** `QToolButton`.
Toggling it ON arms placement into THAT
territory — `set_active_territory` + `set_armed(True)` on the shared display
node, highlight made visible — and un-checks every other row's toggle
(**exclusive**: one territory armed at a time).  Toggling OFF disarms through
the shared `done()` body.  The checked state is **re-derived** from the
display node on every rebuild (`is_armed(dn) and get_active_territory(dn) ==
territoryId`), never stored in a Python field, so it survives the
carrier-`Modified` rebuild.  `Add Territory` still mints a territory and arms
it (its toggle then re-derives checked); the panel `Add seeds` + `Done`
buttons **retire** — only the `done()` disarm logic survives, as the shared
body reused by a toggle-OFF and by the module-active gate below.

### Module-active gate (extends §Decision 2)

The widget's `exit()` disarms placement (the table's shared `disarm()`/`done()`
body, then a rebuild so the toggles re-derive un-checked), so no view claims an
add-on-click while VascularTerritories is inactive.  `enter()` auto-arms
nothing.  Edits (grab/drag/delete of existing seeds) stay **independent** of
arm state — intended, not gated.

### Eye-icon visibility (extends §Decision 3)

The visibility control is a Slicer-idiomatic eye-on / eye-off
`qt.QToolButton` (the segmentation convention), not a `QCheckBox`; toggling it
flips `SetTerritoryVisibility` and its checked state is derived from
`GetTerritoryVisibility` on rebuild.

### Editable label moves to a `QLineEdit` (extends §Decision 3)

With the column grid gone, the territory label is an editable `qt.QLineEdit`
in the row strip whose `editingFinished` routes through `setTerritoryLabel` to
the carrier's display slot — the composite-row replacement for the retired
in-item editable text (and its tree `itemChanged` label handler).
