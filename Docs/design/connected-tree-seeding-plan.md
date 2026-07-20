# Implementation plan — connected-tree-constrained centerline seeding (ADR-0037 slice 5)

- **Status:** Planning (no code)
- **Design of record:** [ADR-0037](../adr/0037-vascular-territories-off-markups.md)
  §"Amendment — connected-tree-constrained centerline seeding (slice 5)".
- **Branch:** `feature/vasc-territories-connected-tree`, stacked on #602 (slice 4).
- **Cross-checked ADRs:** 0037 (all amendments), 0036, 0011, 0033, 0032, 0013, 0014, 0027, 0004, 0025.

## Scope

Constrain a territory's seed set to a single connected vessel tree. The
compute amendment resolved the VMTK input surface by merging every segment
(`80432b3`); real liver data (parenchyma + portal + hepatic + tumour in one
node) makes merge-all wrong — portal and hepatic are disjoint components and
a medial path tunnelling between them is meaningless. Slice 5 (a) filters the
surface candidates to vascular-SCT-typed segments, (b) makes the first seed of
a territory define its active connected tree, (c) constrains later seeds to
that component (snap-or-reject), (d) runs each per-territory extraction over
that single component (superseding merge-all), and (e) highlights the active
tree while placing.

## Locked design (from ADR-0037, not re-litigated here)

1. Vessel candidates = segments whose `TerminologyEntry` TYPE is vascular
   (`SCT^29092000` Vein / `SCT^51114001` Artery + broad vessel set); exclude
   liver (`SCT^10200004`) + tumour. Real data tags vessels under category
   `SCT^85756007` Tissue with generic Vein/Artery types.
2. First seed defines the territory's active connected tree.
3. Later seeds snap-to / reject against the active tree.
4. Per-extraction VMTK surface = that one component (supersedes `80432b3`).
5. Active tree highlighted in 3D + 2D while placing (styling deferred).

**RESOLVED (baked in):** active-tree persistence = reuse
`AnnotationPoints[territory][0]` as the connectivity seed. No new carrier
slot, no stored mesh, no volatile region id. The active tree is recovered on
demand by re-running `vtkPolyDataConnectivityFilter` in `ClosestPointRegion`
mode seeded at the territory's first annotation point. By the single-tree
constraint every seed lies on the same component, so any surviving seed
(including a new index-0 after deletion) recovers the same tree; deleting the
first seed is safe. All seeds deleted ⇒ no active tree. Interaction state
(armed / active-territory) stays on the display node
(per `feedback_layerdm_state_on_display_node`); durable identity rides the
carrier's existing point round-trip (ADR-0014 layering).

## Grounding in the current code

- **Vessel merge-all seam:** `VesselHighlightWiring.closed_surface_polydata`
  (`VascularTerritories/VascularTerritoriesLib/VesselHighlightWiring.py`)
  appends *every* segment's closed surface into one mesh. Three consumers:
  `TerritoryPlacementPipeline._ensure_pick` (3D pick),
  `TerritorySlicePipeline` (2D pick), and
  `VascularTerritories.polyDataFromNode` (line 1077, the extraction surface
  via `_preprocessedSurface` → `preprocessAndDecimate`).
  `VesselHighlightPipeline` also builds its pick core from it.
- **SCT-tag precedent:** `vtkSlicerVascularTerritoriesLogic::GetLiverSegmentId`
  (`Logic/vtkSlicerVascularTerritoriesLogic.cxx:317`) already does exactly the
  match we need for the inverse set — substring match `SCT^10200004` on the
  segment's `GetTag("TerminologyEntry", tag)`, tolerant of the meaning string,
  ADR-0011-conformant. The vessel resolver is the same idiom with the vascular
  token set and the liver/tumour exclusion.
- **Extraction path:** `extractCenterlines` (line 732) → `_preprocessedSurface`
  (781, decimates once, shared across territories) → per-territory
  `_extractOneTerritory` (796). The `<2-seed` skip (`4090aa5`) is at line 773;
  the triangulate-before-decimate fix (`15de967`) lives in the C++
  `scl.preprocessAndDecimate` behind `preprocessAndDecimate` (1046).
- **Carrier API:** `vtkMRMLCustomTerritoriesNode` exposes
  `AddAnnotationPoint` / `GetNthAnnotationPoint` /
  `GetNumberOfAnnotationPoints` / `RemoveNthAnnotationPoint` /
  `GetAnnotationTerritoryIds`. Index-0 is the first placed seed — the RESOLVED
  connectivity seed.
- **Placement pipelines:** `TerritoryPlacementPipeline._event_world_on_surface`
  (623) snaps via `VesselSurfacePick.pick`; `_add_point` (604) writes the
  carrier. The 2D twin is `TerritorySlicePipeline`. Both resolve the pick
  surface from the display node's `GetPickSurfaceNode()`.
- **Highlight node:** `vtkMRMLTerritoriesHighlightDisplayNode` carries
  `Adhering` / `AdheringPointWorld` (transient) + `GetPickSurfaceNode()`; no
  place for a mesh (consistent with the RESOLVED no-stored-mesh call).

No `vtkPolyDataConnectivityFilter` exists in the module yet.

## Component design

### C1 — vessel-surface resolver (C++, on the Logic)

**Where:** a new `vtkSlicerVascularTerritoriesLogic` method, e.g.
`GetVascularSegmentIds(vtkMRMLSegmentationNode*)` returning the vascular
segment ids, plus `GetVascularSurfacePolyData(node)` appending only those
segments' closed surfaces. C++, mirroring `GetLiverSegmentId` — the SCT
substring match already lives there; keeping the vascular match beside it
keeps one terminology-dispatch site (ADR-0011) and avoids a Python
reimplementation of the tag read. This is a Logic *query*, not a widget
concern, so ADR-0004 (widgets are Python) does not pull it to Python.

**Filtering:** for each segment, read `GetTag("TerminologyEntry", tag)`; keep
if `tag` contains any vascular token; drop if it contains `SCT^10200004`
(liver) or a tumour token. Match is a substring on `SCT^<code>` (scheme+code),
tolerant of the meaning string — identical to `GetLiverSegmentId`.

**Python seam:** `VesselHighlightWiring` grows a
`vascular_surface_polydata(segmentation, logic=None)` that, given the Logic,
delegates to `GetVascularSurfacePolyData`; the existing
`closed_surface_polydata` (merge-all) STAYS for the pick path (see the
pick-vs-extraction split below). `polyDataFromNode` switches its segmentation
branch (line 1077) from `closed_surface_polydata` to the vascular resolver so
extraction sees only vessels.

**Pick vs extraction (DECISION):** the highlight/pick path (`_ensure_pick` in
both pipelines, `VesselHighlightPipeline`) stays **merge-all** — a surgeon may
hover/snap anywhere on any vessel to *drop* the first seed, and the
first-seed-defines-the-tree rule needs the whole vascular surface reachable.
The *extraction* surface narrows to the active component (C3). Rationale: the
constraint is enforced at seed-commit time (C4), not by hiding surface from the
cursor; snapping the cursor pre-commit would prevent ever choosing a different
tree for a *new* territory. Recommended: pick uses the vascular-filtered
merge (vessels only, but all vessel components), NOT the raw all-segment merge
— so the cursor never snaps to liver/tumour. So: `closed_surface_polydata`
(all segments) is replaced everywhere by `vascular_surface_polydata` (vessels,
all components) for the *pick*, and by the single-component surface for the
*extraction*.

### C2 — connectivity recovery helper (C++ on the Logic, Python-thin)

**Where:** C++ `vtkSlicerVascularTerritoriesLogic::GetConnectedComponentAt(
vtkPolyData* vascularSurface, double seed[3], vtkPolyData* out)` running
`vtkPolyDataConnectivityFilter` in `SetExtractionModeToClosestPointRegion()`
with `SetClosestPoint(seed)`. C++ keeps it off the GL/interaction thread and
reuses the mapper-relocation-free Logic surface; a pure-VTK Python helper in
`VesselHighlightWiring` is an acceptable alternative (bare-testable without a
built module) — **recommended: Python pure-VTK helper**
`connected_component_at(polydata, seed)` in a small new lib module
(`VesselConnectivity.py`), because the invariant tests (C6) want it bare and
`vtkPolyDataConnectivityFilter` is fully Python-wrapped with no C++-only
dependency. Put the SCT filter in C++ (it reads MRML segment tags) and the
connectivity in Python (it is pure polydata) — clean ADR-0004 split.

**Performance:** the connectivity filter is O(cells) with a region-grow;
on a decimated vessel surface it is cheap, but it runs on *every seed placement*
(to test which component the click landed on) and on *every extraction*. Cache
by `(polydata MTime, seed-cell)` inside the placement pipeline the same way
`VesselSurfacePick` caches its locator by MTime — recover once per territory
per surface-version, not per mouse event. See OPEN QUESTION Q3.

### C3 — per-extraction single-component surface

`extractCenterlines` currently decimates one shared surface for all
territories (line 759-764). Slice 5 makes the surface **per-territory**: for
each territory carrying ≥2 seeds, recover its active component from the
vascular surface seeded at index-0 (C2), then decimate THAT component. This
supersedes `80432b3`'s merge-all input. Ordering vs `15de967`: recover the
component FIRST (on the full-res vascular surface, so connectivity is not
fragmented by decimation), THEN triangulate+decimate the component — the
existing `preprocessAndDecimate` (which triangulates then decimates) runs on
the single component. The `<2-seed` skip (`4090aa5`, line 773) is unchanged
and runs *before* recovery so we never recover a component for an under-seeded
territory.

### C4 — seed-constraint enforcement (placement pipelines)

Both `TerritoryPlacementPipeline` (3D) and `TerritorySlicePipeline` (2D) gain
the same commit-time gate in the add-on-click path (`_add_point` /
`ProcessInteractionEvent`):

- **First seed** (`GetNumberOfAnnotationPoints(territory) == 0`): no active
  tree yet — accept the surface-snapped world point as-is. Index-0 becomes the
  connectivity seed (RESOLVED). No recovery needed on this click.
- **Later seed** (`>= 1` point): recover the active component from the
  vascular surface seeded at index-0 (C2); test whether the just-snapped world
  point lies on that component (point-in-component: build a `vtkCellLocator` /
  `FindClosestPoint` on the recovered component and compare distance to a
  tolerance, OR compare the connectivity region id of the picked cell). If on
  the active component → accept. If on a different component → **snap** the
  point to the nearest point on the active component (RECOMMENDED over reject:
  a silent reject feels broken; a snap keeps the territory coherent and is the
  ADR's first-listed option "snaps to the nearest point"). See OPEN QUESTION Q2.

**Where the hit-component test runs:** in the pipeline, after
`_event_world_on_surface` returns the snapped world point and before
`_add_point`. The recovered component is cached per (territory, surface MTime).
The 2D twin reuses the identical helper — the snap runs in world space, so the
slice-normal ray result feeds the same gate.

### C5 — active-tree highlight

Extend the existing highlight (ADR-0036) to paint the recovered active
component while a territory is armed. Drive it from the placement pipeline: on
`Arm()` / active-territory change, recover the component (C2) and hand it to a
highlight actor. The single-3D-pipeline constraint (ADR-0013 §1, already noted
in `TerritoryPlacementPipeline` docstring: it renders the hover marker itself)
means the active-tree surface actor is a THIRD actor owned by
`TerritoryPlacementPipeline` (alongside `_seed_actor`, `_marker_actor`), not a
new pipeline on the same display-node type. The 2D twin renders the component's
slice contour analogously. Styling (colour/opacity/edge) is deferred — see
OPEN QUESTION Q4. Recovery for the highlight reuses the C2 cache; no extra
compute.

## Invariant-test plan (ADR-0027)

Bare-testable (pure-VTK / MRML-node, no GUI):

- **T1 — SCT filter** (`test_territories_surface_resolution.py`, extend):
  a segmentation with liver (`SCT^10200004`) + vein (`SCT^29092000`) + tumour
  segments → the vascular resolver keeps only the vessel segment(s), excludes
  liver + tumour. Needs Slicer segmentation logic for closed surfaces → the
  filter *decision* (id set) is bare-testable on a fake segment carrying tags;
  the surface-append stays launched (mirrors the existing i1/i2 split in that
  file). The C++ id-set query gets a Cxx test beside
  `vtkSlicerVascularTerritoriesLogicLiverSegmentIdTest.cxx` —
  `...VascularSegmentIdsTest.cxx`.
- **T2 — connectivity picks one component**
  (new `test_territories_connectivity.py`, bare): a two-tube polydata (disjoint
  components) → `connected_component_at(seed_on_tube_A)` returns only tube A's
  cells; a seed on tube B returns only B. Also: the per-extraction surface for a
  territory is a single connected component (`vtkPolyDataConnectivityFilter`
  with `SetExtractionModeToAllRegions` reports exactly 1 region).
- **T3 — two seeds on disjoint components resolve to different active trees**
  (bare, same file): index-0 on A and a fresh territory's index-0 on B recover
  disjoint components.

Launched (need Slicer views / interaction):

- **T4 — placement constraint** (`test_territories_placement_pipeline.py` +
  slice twin, extend): first seed accepted anywhere on the vascular surface; a
  second seed whose snapped world point is on a different component is SNAPPED
  onto the active component (asserted: the added point lies on the index-0
  component within tolerance, never straddles). Uses the existing injected
  pick-core seam so it stays GL-free where possible; the connectivity recovery
  runs on the injected polydata.
- **T5 — highlight** (launched, eyeball-gated appearance; pinned invariant is
  that the active-tree actor's input is the index-0 component, following the
  `VesselHighlightPipeline` "pick integration pinned, GL appearance eyeball"
  precedent).

Persistence invariant [review, ADR-0037 slice-5 Conformance]: recovering the
component from index-0 after a carrier-`Modified` rebuild yields the same
component; deleting index-0 (leaving a later seed as the new index-0) still
recovers the same component. Add as a bare test in T3's file.

## Slice breakdown (RECOMMENDATION)

**Split into two stacked PRs** on `feature/vasc-territories-connected-tree`:

- **PR-A (compute):** C1 vessel-SCT resolver (C++ + Python seam) + C2
  connectivity helper + C3 per-extraction single-component surface. Tests
  T1/T2/T3 + the persistence invariant. This is the correctness core and is
  fully bare/launched-testable without touching interaction. It supersedes
  `80432b3` (call that out in the PR body, not in code, per
  `feedback_no_pr_refs_in_code`).
- **PR-B (UX):** C4 placement snap-or-reject constraint (3D + 2D) + C5
  active-tree highlight. Tests T4/T5. Depends on PR-A's helpers.

Rationale: PR-A changes what VMTK is fed (a real bug fix, mergeable on its own
and independently verifiable); PR-B changes what the surgeon can do at
placement time. Keeping them separate keeps the compute fix from being blocked
on the interaction/GL review and matches the ADR's own compute-vs-UX seam.

## ADR conformance / conflicts

- **ADR-0011:** the vascular match reuses the `GetLiverSegmentId` SCT-tag
  idiom; no SCT codes leak into labelmap scalars (those stay arbitrary ints per
  the compute amendment). No conflict.
- **ADR-0013 §5:** no new pipeline, no custom DM — the active-tree actor is
  owned by the existing `TerritoryPlacementPipeline` (one pipeline per
  display-node type). No conflict.
- **ADR-0014:** durable identity rides the carrier's existing point round-trip;
  no new node family, no new carrier slot. Conforms.
- **ADR-0032 / 0033:** the constraint runs inside the existing
  `ProcessInteractionEvent` commit path; bare-move still declines. No conflict.
- **ADR-0036:** the active-tree highlight extends the vessel-adhering
  highlight; ADR-0037 already names this. No conflict.
- **ADR-0037 compute amendment:** slice 5 explicitly SUPERSEDES merge-all — the
  ADR records this. No conflict.
- **Closed vocabulary / platform neutrality / no-PR-refs-in-code:** new C++
  classes drop the `Liver` prefix (already true for the Territories family);
  no build-system changes; no PR/issue numbers in source.

## OPEN QUESTIONS (maintainer decides; planning proceeds on the recommendation)

- **Q1 — exact vascular-SCT match set.** ADR-0037 says "the broad vessel set"
  (generic Vein `SCT^29092000` / Artery `SCT^51114001`) because real data tags
  under category `SCT^85756007` Tissue with generic types, not portal/hepatic
  codes. **Recommendation:** match the two generic type codes plus a short
  documented allowlist of common vessel type codes (e.g. blood vessel
  structure), and EXCLUDE by liver + a tumour token; keep the token list in one
  named constant in the Logic. Proceeding on the broad-generic set.
- **Q2 — snap vs reject for an off-tree later seed.** **Recommendation: snap**
  to the nearest point on the active component (ADR lists snap first; less
  surprising than a swallowed click). Proceeding on snap; a rejected-click
  variant is a one-line switch if the maintainer prefers.
- **Q3 — connectivity performance.** Recovery per seed-placement and per
  extraction. **Recommendation:** cache the recovered component per
  (territory, vascular-surface MTime) in the placement pipeline (VesselSurfacePick
  MTime-cache precedent); recover on the full-res vascular surface once, reuse
  for gate + highlight + extraction. Proceeding on the cache.
- **Q4 — active-tree highlight styling.** ADR defers it. **Recommendation:**
  reuse the hover-marker colour family at low opacity for the active component
  surface; ship a plain semi-transparent tint in PR-B and leave a styling
  follow-up. Proceeding on the plain tint.
- **Q5 — components that accidentally touch.** If portal and hepatic voxels
  abut after closed-surface meshing, connectivity would fuse them into one
  region and the constraint silently permits a straddling seed set.
  **Recommendation:** out of scope for slice 5 (the ADR assumes disjoint
  systems); note it as a known limitation and a candidate morphological-gap
  follow-up. Proceeding without a gap-opening step.
