# Implementation plan — multi-system territory seeding (ADR-0037 slice 5, REVISED)

- **Status:** Planning (no code)
- **Design of record:** [ADR-0037](../adr/0037-vascular-territories-off-markups.md)
  §"Amendment — connected-tree-constrained centerline seeding (slice 5)" —
  this plan REVISES that amendment (see §ADR revision below).
- **Branch:** `feature/vasc-territories-connected-tree` (slice-5 work already
  landed, commits `3256bc7..cfab74d`; NOT pushed).
- **Cross-checked ADRs:** 0037 (all amendments), 0036, 0011, 0013, 0014,
  0034, 0010, 0004, 0027.

## Why the current design is wrong

The landed slice-5 design LOCKS each territory to ONE connected vessel tree:
the first seed picks the system, later seeds snap to that component
(`_constrain_to_active_tree`), and the component glows (`_highlight_tree_actor`).
That is clinically wrong. A vascular territory may legitimately be defined by
seeds in MULTIPLE disjoint systems — e.g. points a,b on a hepatic vein plus
c,d on the portal vein. Portal and hepatic are disjoint components whose
centerlines are derived INDEPENDENTLY, and BOTH contribute to the one
territory's map region. The single-tree lock forbids exactly the case the
surgeon needs.

The revised model: a **territory** owns a set of seeds; each seed belongs to
the **structure** (input segment) whose closed surface it is nearest; VMTK
runs **once per structure that has ≥2 seeds**; each resulting centerline is
tagged with the territory's int and all feed the territory's map region.

## Scope

Remove the single-tree placement lock and the glow halo. Introduce a pure-VTK
seed→structure mapping. Group extraction by structure (one VMTK run per
≥2-seed structure, N centerlines per territory). Colour each seed row by its
structure's segment colour. Flag a territory whose any touched structure has
<2 seeds. Revise the ADR-0037 slice-5 amendment to record the flip.

---

## Part A — what to REMOVE

### A1. The single-tree placement lock (C4)

- `TerritoryPlacementPipeline._constrain_to_active_tree` (3D) and
  `TerritorySlicePipeline._constrain_to_active_tree` (2D): DELETE. In both
  `ProcessInteractionEvent` add-on-click paths drop the
  `world = self._constrain_to_active_tree(world)` line — the raw
  surface-snapped `world` from `_event_world_on_surface` /
  `_snap_event_to_surface` goes straight to `_add_point`. The visibility-gated
  pick already restricts snapping to VISIBLE vessels
  (`vascular_surface_polydata`), which is the retained, correct gate: hide a
  system to avoid stray seeds on it.
- `nearest_point_on` (VesselConnectivity.py): becomes UNUSED once
  `_constrain_to_active_tree` is gone. KEEP the function only if the
  seed→structure mapping (B) reuses it; per the recommendation below the
  mapping uses a closed-surface cell/point locator per segment, so
  `nearest_point_on` over a single merged tree is no longer called. RECOMMEND
  deleting it and its dedicated test in `test_territories_connectivity.py`,
  unless B's mapping ends up delegating to it.

### A2. The glow halo / active-tree highlight (C5)

In `TerritoryPlacementPipeline`:
- DELETE `_highlight_tree_mapper`, `_highlight_tree_actor`,
  `ACTIVE_TREE_GLOW_COLOR`, `activeTreePolyData`, `highlightActor`,
  `_reconcile_active_tree_highlight`, and `_active_tree_polydata` /
  `_active_tree_cache_key`.
- In `_attach_halo_renderer` drop `overlay.AddActor(self._highlight_tree_actor)`
  (the SEED-hover glow halo `_halo_actor` STAYS — that is the yellow/green
  edit cue, unrelated to the active tree).
- In `_reconcile_highlight` drop the trailing
  `self._reconcile_active_tree_highlight()` call.

In `TerritorySlicePipeline`:
- DELETE `activeTreePolyData`, `_constrain_to_active_tree`,
  `_active_tree_polydata`, `_active_tree_cache_key` and the
  `connected_component_at` / `nearest_point_on` import.

### A3. `connected_component_at` — reassess

`connected_component_at` is still used by
`VascularTerritories._territorySurface` to narrow the per-territory VMTK input.
Under the revised extraction (B4) the VMTK input surface becomes the
**per-structure** closed surface (each structure is meshed independently and
is already a coherent surface for VMTK). Whether a further connectivity
narrowing is still needed depends on whether a single input SEGMENT can carry
DISJOINT pieces (the "structure with disjoint pieces" edge case, Q4). RECOMMEND:
KEEP `connected_component_at` and KEEP narrowing the per-structure surface to
the connected component of the structure's OWN seed centroid (or its first
seed), so a segment that accidentally holds two disjoint tubes still feeds VMTK
one coherent tree. This preserves the `15de967` triangulate-before-decimate
ordering. So `connected_component_at` survives, `nearest_point_on` does not.

### KEEP (do not touch)

- The visibility-gated pick (`vascular_surface_polydata` + `visibility_mtime`,
  `_ensure_pick` MTime rebuild) in both pipelines — the correct "hide a system
  to avoid stray seeds" mechanism.
- The `<2-seed` skip in `extractCenterlines` (`4090aa5`) — refined into a
  per-structure gate (B4), not removed.
- The VMTK triangulate/decimate (`preprocessAndDecimate`, `15de967`).
- All seed rendering, hover/grab halo, cross-view reslice, arm/module-gate.

---

## Part B — what to BUILD

### B1. Seed→structure mapping helper (pure-VTK Python lib)

**Location:** a new pure-VTK helper, RECOMMENDED in a new small module
`VascularTerritoriesLib/SeedStructureMapping.py` (mirrors `VesselConnectivity`:
imports `vtk` only, bare-unit-testable, no MRML/Slicer/Qt/GL). Rationale
(ADR-0004 split): the geometry (nearest closed-surface to a point) is pure
polydata → Python; the segment→closed-surface + segment→colour resolution
reads MRML segment state and rides existing C++/Python seams.

**Signature (pure core):**
```
nearest_structure(structures, point) -> key | None
```
where `structures` is an ordered sequence of `(key, closed_surface_polydata)`
and `key` is the segment id (str). Builds a `vtkCellLocator`
(`FindClosestPoint`) per structure surface, returns the key of the structure
with the smallest distance to `point`. A `(distance)` tie or an equal-distance
boundary point resolves to the FIRST structure in order (deterministic; Q3).

**MRML-facing wrapper (in `VascularTerritories.py` logic or a thin adapter):**
resolve the per-segment closed surfaces once via the C++
`GetVascularSegmentIds` + `GetClosedSurfaceRepresentation` per id (NOT the
merged `GetVascularSurfacePolyData`, which loses the id→surface split). Pass
the `(segmentId, surface)` list to `nearest_structure`. The segment id is the
stable structure identity (matches the maintainer's "structure/segment" mental
model; in real data segment ≡ component).

**Caching/perf (Q3):** cache the per-segment `vtkCellLocator`s keyed by
`visibility_mtime(segmentation)` (same MTime seam the pick uses), so the N
locators are built once per surface-version, not per seed. Mapping a seed is
then N `FindClosestPoint` calls (N = vessel-segment count, small — 2–4 in real
data). This is cheaper than the current per-seed `vtkPolyDataConnectivityFilter`
region-grow.

### B2. Persisting the seed→structure assignment

A seed's structure is a DERIVED property (nearest surface), recomputable, so
it need NOT be a new carrier slot (ADR-0014: no new node family, no new carrier
slot). RECOMMEND: compute on demand from the carrier point + the current
segmentation surfaces, cached in the pipeline/table by MTime. This keeps the
carrier's existing point round-trip as the only durable state (conforms to the
slice-5 "reuse the carrier round-trip" persistence decision, now without a
connectivity seed).

**OPEN QUESTION Q5** (below): if re-mapping on every table repaint is too
costly OR if a seed's nearest-structure can flip when a surface is hidden, we
may want to STAMP the assignment at placement time. Recommendation: derive on
demand for now; revisit only if a flicker/perf issue surfaces.

### B3. Table: coloured seed rows + per-structure warning glyph

`TerritoriesTableWidget` changes (composite-row tree, single column):

**Seed-row colour by structure.** In `_buildSeedRow`, the seed row currently
shows a plain `QLabel("Seed N — on surface")`. Add a small colour swatch
(a `QLabel` with a filled pixmap, or reuse the `ctkColorPickerButton`
render-only) tinted with the seed's STRUCTURE colour. The colour comes from
the INPUT SEGMENTATION's per-segment display colour
(`segmentationDisplayNode.GetSegmentDisplayColor(segmentId)` /
`segment.GetColor()`), NOT the territory palette. Resolve the seed's structure
via B1. ADR-0010: colour is NEVER the only cue — pair the swatch with the
structure's NAME text (e.g. "Seed 2 — Portal vein") so the row is legible
without colour.

**OPEN QUESTION Q6:** segment display colour vs a generated palette. The
maintainer said "the segmentation's per-segment display colour."
RECOMMENDATION: use the segment display colour (matches what the surgeon sees
in the 3D vessel render, zero new mapping). Fall back to the territory palette
only when the segment colour is unavailable.

**Territory warning glyph on any <2-seed structure.** The current territory
status is a flat `seedCount < 2` check (`_MIN_SEEDS_FOR_COMPLETE`). REPLACE it
with a per-structure query: group the territory's seeds by structure (B1),
and if ANY touched structure has <2 seeds, show the warning glyph + text
("⚠ <structure> needs at least two seeds"), because that structure cannot
yield a centerline. Extend `_territoryStatus`/`_buildTerritoryRow` to compute
the grouping. Keep the existing glyph+text rendering (ADR-0010). The check
lives in a small table/logic query `territory_structure_seed_counts(carrier,
territory, mapping)` — reused by extraction (B4) so the table and the extractor
agree on the gate. RECOMMEND placing that query in `SeedStructureMapping.py`
(pure, bare-testable) taking already-mapped `(seed, structureKey)` pairs.

### B4. Extraction: group by structure (`extractCenterlines`)

In `VascularTerritories.extractCenterlines` / `_extractOneTerritory`:

- For each territory carrying points, MAP each seed to its structure (B1) over
  the FULL-res per-segment surfaces.
- GROUP the territory's seeds by structure id.
- For each structure with **≥2 seeds**: resolve that structure's closed
  surface (`GetClosedSurfaceRepresentation(segmentId)`), optionally narrow to
  its connected component (A3 / Q4), triangulate+decimate
  (`preprocessAndDecimate`, preserving `15de967`), build ONE transient
  fiducial from that structure's ordered seeds, run VMTK ONCE, and wire the
  resulting centerline into `CenterlineRefs` + `Groupings` under the
  TERRITORY id (unchanged wiring), marked with the territory's int
  (`MarkSegmentWithID` via the existing `_wireCenterlineOutput`).
- A structure with **<2 seeds** is SKIPPED (no VMTK run) and contributes to
  the territory's warning flag (B3).
- A territory spanning two structures → TWO VMTK runs → TWO centerlines, both
  grouped under the territory, both marked with the territory's int.

**Idempotency:** `_clearTerritoryCenterlines` currently clears ALL of a
territory's prior refs before wiring the new one, then `_wireCenterlineOutput`
appends ONE. With N centerlines per territory this must change: clear the
territory's refs ONCE at the start of the territory's extraction, then APPEND
each structure's centerline. RECOMMEND: hoist the clear out of
`_wireCenterlineOutput` into `extractCenterlines` (once per territory, before
the structure loop), and let `_wireCenterlineOutput` only append. Re-extraction
then yields exactly the current ≥2-seed structures' centerlines.

**Map compute already handles N:** `build_centerline_model` iterates ALL
`CenterlineRefs`, reads each centerline's territory via `Groupings`, marks it
with the territory's derived int (`territory_label_ints`), and sums them into
the search model. Multiple centerlines sharing one territory int already feed
one map region. No change needed to `calculateVascularTerritoryMap` or
`MarkSegmentWithID`. CONFIRMED by reading `build_centerline_model`.

- `_vascularSurface` (merged vessels) and `_territorySurface`
  (connected-component-at-seed[0]) are SUPERSEDED for the grouped path. Keep
  `_vascularSurface`'s per-segment resolution but expose the per-segment split
  (see B1 wrapper). `_territorySurface`'s index-0 recovery is replaced by
  per-structure surfaces; retire it (or repurpose it as the per-structure
  connected-component narrow, A3).

---

## Part C — tests to CHANGE / ADD (ADR-0027)

### Must change (landed slice-5 tests that encode the removed design)

- `test_territories_placemode_constraint.py`: the C4 constraint tests
  (`test_first_seed_defines_the_active_tree`, later-seed-snaps,
  `activeTreePolyData`/`highlightActor` seam) assert the REMOVED lock+halo.
  REWRITE to pin the NEW invariant: a later seed on a DIFFERENT component is
  KEPT AS-IS (no snap) — a territory MAY straddle systems. Drop the
  `activeTreePolyData` / `highlightActor` assertions.
- `test_territories_connectivity.py`: keep the `connected_component_at` tests
  IF A3 keeps per-structure narrowing; drop the `nearest_point_on` +
  index-0-persistence-for-the-lock tests (the persistence rationale is gone).
- The C5 highlight assertions (in the constraint file and any
  `test_vessel_highlight_*` overlap): drop the active-tree actor input pin.
- `test_territories_surface_resolution.py`: the vessel-SCT resolver
  (`GetVascularSegmentIds` / `GetVascularSurfacePolyData`) STAYS valid and its
  suite mostly holds; ADD a per-segment-split assertion if B1's wrapper needs
  id→surface (the merged resolver test is unaffected).
- `test_territories_vmtk_feed.py`: extend for group-by-structure — a territory
  with seeds on two structures produces TWO centerlines; the ≥2-per-structure
  gate skips a 1-seed structure; idempotent re-extraction.

### New invariants to pin

- **Seed→structure mapping** (new `test_territories_seed_structure.py`, bare):
  a seed nearest structure A's surface maps to A; nearest B maps to B; a
  boundary/tie resolves deterministically to the first-in-order structure.
- **Per-structure ≥2 warning** (bare, table or mapping query): a territory
  with 2 seeds on A + 1 on B flags the warning (B under-seeded); 2+2 does not.
- **Extraction one-centerline-per-≥2-seed-structure** (feed test): grouping
  drives exactly one VMTK run per qualifying structure; the mixed-system
  territory yields 2 centerlines both grouped under the territory.
- **No straddle-snap** (constraint file, rewritten): a later off-component seed
  is added at its own snapped point, unchanged.

---

## Part D — ADR-0037 slice-5 amendment revision

Rewrite ADR-0037 §"Amendment — connected-tree-constrained centerline seeding
(slice 5)" so the design of record FLIPS:

- REMOVE "First seed defines the active vessel tree", "Seeds constrained to
  the active tree", and "Active tree highlighted while placing".
- REPLACE with: (a) a territory owns seeds across possibly-multiple disjoint
  structures; (b) each seed is assigned to the input SEGMENT whose closed
  surface it is nearest; (c) the pick stays visibility-gated (hide a system to
  avoid stray seeds) — this is the only placement constraint; (d) extraction
  GROUPS a territory's seeds by structure and runs VMTK once per structure with
  ≥2 seeds, over that structure's surface; (e) a structure with <2 seeds is
  skipped and flags the territory (glyph+text, ADR-0010); (f) N centerlines
  per territory, all marked with the territory int, all feeding the one map
  region; (g) seed rows in the table are coloured by structure (segment
  display colour) with the structure name (ADR-0010); (h) no glow halo.
- Keep the vessel-SCT-type surface section (still correct).
- Update §Conformance (slice 5): replace the "two seeds → different trees /
  snap / persist" points with "seed→structure mapping is deterministic",
  "≥2-per-structure gate", "one centerline per ≥2-seed structure", "mixed-
  system territory yields 2 centerlines", "no straddle-snap".

Note the amendment may reference PR numbers in prose (planning docs may);
code comments referencing the superseded design must NOT carry PR/issue refs
(`feedback_no_pr_refs_in_code`).

---

## Slice / PR breakdown

This is all on the unpushed `feature/vasc-territories-connected-tree` branch.
The landed slice-5 commits encode the wrong design, so the cleanest history is
NOT to pile a revert on top.

**RECOMMENDATION: amend in place via an interactive rebase is risky (13
commits, shared conceptual chain). Instead add follow-on commits that (1)
remove the lock+halo, (2) add mapping+grouping, (3) revise ADR+tests — then
squash-clean at PR time if the maintainer wants linear history.** Concretely:

- **Commit 1 (BUG/ENH):** remove `_constrain_to_active_tree` (both pipelines),
  the active-tree highlight actor + overlay wiring, `nearest_point_on`; rewrite
  the constraint test to pin no-straddle-snap. Green both harnesses.
- **Commit 2 (ENH):** `SeedStructureMapping.py` + the group-by-structure
  extraction rework + the N-centerline idempotency hoist; feed + mapping tests.
- **Commit 3 (ENH):** table seed-row colour-by-structure + per-structure
  warning glyph; table tests.
- **Commit 4 (DOC):** ADR-0037 slice-5 amendment revision + this plan.

Rationale: commit 1 is a pure removal (independently reviewable, restores
correct placement freedom); commit 2 is the compute core; commit 3 is UX;
commit 4 records the decision. Keeps the compute change reviewable apart from
the GL/table review. Validate BOTH the launched-Slicer harness and the bare
`PythonSlicer -m pytest` scaffold before pushing (`feedback_two_python_test_
harnesses`); watch the LiverSegmentation-root-last launched-sweep trap.

---

## ADR conformance / conflicts

- **ADR-0011:** seed→structure mapping keys on the same SCT-typed segment set
  (`GetVascularSegmentIds`); no new terminology dispatch site. No conflict.
- **ADR-0013 §1/§5:** removing the third highlight actor REDUCES pipeline
  surface; no new pipeline, no custom DM. Group-by-structure is a Logic
  concern, not a DM. No conflict.
- **ADR-0014:** seed→structure is DERIVED (no new carrier slot / node family);
  durable state stays the carrier point round-trip. Conforms.
- **ADR-0004:** the pure geometry (nearest-surface) lives in a Python lib;
  segment tag/colour reads ride existing seams. Conforms.
- **ADR-0010:** seed colour is paired with structure NAME text; the warning is
  glyph+text. Conforms — flag any implementation that ships colour alone.
- **ADR-0034:** the table stays a Python-composed custom tree. Conforms.
- **ADR-0036:** the vessel-adhering hover highlight is untouched; only the
  active-tree GLOW (a slice-5 addition) is removed. No conflict.
- **ADR-0027:** every behaviour change is pinned by a bare/launched invariant
  before implementation (test-first). Conforms.
- **Closed vocabulary / platform neutrality / no-PR-refs-in-code:** new class
  `SeedStructureMapping` drops any `Liver` prefix (Territories family already
  does); no build-system changes; no PR/issue numbers in source.

---

## OPEN QUESTIONS (maintainer decides; planning proceeds on the recommendation)

- **Q1 — grouping unit: segment vs raw connected component.** The maintainer
  said "structure/segment". In real data segment ≡ component.
  **RECOMMENDATION: group by SEGMENT (id).** It matches the surgeon's mental
  model, gives a stable colour (the segment display colour), and survives a
  segment that is one connected surface. Proceeding on segment grouping.
- **Q2 — a structure (segment) with DISJOINT pieces.** If one segment holds
  two disjoint tubes, VMTK over the whole segment surface tunnels between them.
  **RECOMMENDATION: narrow each per-structure surface to the connected
  component of that structure's seeds (keep `connected_component_at`), seeded
  at the structure's first-in-territory seed.** Note as a known limitation if
  a structure's seeds span its own two pieces (rare); proceeding with the
  single-component narrow.
- **Q3 — seed on a boundary between two structures.** A point equidistant to
  two surfaces. **RECOMMENDATION: deterministic first-in-order tiebreak** (by
  segment id order from `GetVascularSegmentIds`); document it. A tolerance-band
  "ambiguous" flag is a possible follow-up. Proceeding on the tiebreak.
- **Q4 — perf of nearest-structure mapping per seed.** N `FindClosestPoint`
  per seed (N = vessel segments, small). **RECOMMENDATION: cache the N cell
  locators by `visibility_mtime`; map on demand.** Cheaper than the removed
  per-seed connectivity. Proceeding on the cache.
- **Q5 — derive-on-demand vs stamp-at-placement for the seed's structure.**
  **RECOMMENDATION: derive on demand** (no carrier slot, ADR-0014). Revisit only
  if a hidden-surface re-map flicker or a repaint-perf issue appears.
- **Q6 — seed-row colour: segment display colour vs generated palette.** The
  maintainer specified the segment display colour. **RECOMMENDATION: segment
  display colour** (matches the 3D vessel render), palette only as a fallback.
  Proceeding on the segment colour.
- **Q7 — `nearest_point_on` deletion.** It becomes unused once the lock is
  removed. **RECOMMENDATION: delete it + its test** unless a reviewer wants it
  retained as a utility. Proceeding on deletion.
