# LiverVolumetry seeds off markups + a REUSABLE placement seam — plan (#570 interpretation B)

Status: DRAFT plan (no code written). v2.0.0 (milestone #4, tracker #305).
Branch: `feature/volumetry-layerdm` off `preview` (carries all of #569).
Author: planning pass, 2026-07-25. Supersedes the earlier
`volumetry-layerdm-plan.md` finding (which recommended interpretation A;
the maintainer has now ruled **B, with reusability first-class**).

> Plan, not a decision record. Genuine maintainer choices are marked
> **OPEN QUESTION** with a recommendation; the plan proceeds on the
> recommendation so the staging is concrete.

---

## 0. Headline — the reusable seam is already an ACCEPTED decision (ADR-0038)

The prompt's hypothesis was "extract a reusable core FROM VascularTerritories
(#569) and refactor #569 to consume it." Reading the code changes the shape:

**ADR-0038 ("Unify the control-point visualization + interaction across
resection and vascular territories", Accepted 2026-07-16) already decided to
do exactly this extraction — and mandated the OPPOSITE direction.** Its
Decision:

- Extract a **shared control-point interaction/visualization base** (a 3D base
  + a slice base) parameterized by a small **point-provider seam** (points +
  per-point colour; edges yes/no; drag/delete write-backs; the display-node
  channel for arm/hover/grab state).
- **Direction of extraction: resection → base**, because the resection
  pipelines (`ControlPolygonPipeline` / `SliceControlPolygonPipeline`) are the
  "richer, battle-tested originals (edges, digest gates, state-machine
  integration); territories become the second, simpler client."
- Implementation "deferred to a follow-up issue."

`TerritoryPlacementPipeline` / `TerritorySlicePipeline` were themselves built
by **mirroring** the resection pipelines (their own docstrings + ADR-0038
§Context say so), so extracting the generic core FROM VascularTerritories would
re-derive a base that resection then also has to be retrofitted onto — against
the direction ADR-0038 already ruled.

**Consequence for this plan.** #570-with-reusability is the natural TRIGGER to
finally implement ADR-0038's deferred extraction: LiverVolumetry seeds are the
*third* consumer, and a third consumer is what justifies paying the extraction
now. The generic core is the ADR-0038 base; the split below is done against
ADR-0038's seam, extracting from resection as the ADR mandates, with #569 and
volumetry as the two simpler clients. This is a scope EXPANSION vs the prompt's
"extract from #569" framing — see OPEN QUESTION 1.

**ADR CONFLICT FLAGGED:** the prompt says "extract from #569, refactor #569 to
consume." ADR-0038 §Decision says "extract from resection, territories is a
client." The plan follows the ADR (it is Accepted); if the maintainer wants the
narrower "just #569 + volumetry share, leave resection alone for now" scope,
that is a deviation from ADR-0038 that needs recording as an ADR-0038 amendment
(OQ1).

---

## 1. The generic-vs-specific split (the heart of the plan)

Read in full: `VesselSurfacePick.py` (151), `TerritoryInteractionState.py` (97),
`TerritoryPlacementPipeline.py` (1036), `TerritorySlicePipeline.py` (932),
`VesselHighlightWiring.py` (274), `vtkMRMLCustomTerritoriesNode.h`,
`vtkMRMLTerritoriesHighlightDisplayNode.h`, `TransientVmtkSeeds.py`,
`vtkLiverVolumetryLogic.h`, `LiverVolumetry.py`.

### 1a. GENERIC — moves to the shared ADR-0038 base (Liver prefix dropped, T2.7)

| Today (VascularTerritories) | Generic core | Nature |
|---|---|---|
| `VesselSurfacePick` | **`SurfacePick`** | Already pure-VTK, mesh-agnostic, zero Slicer/Qt. Ray→closed-surface intersect-nearest + closest-point fallback, lazy `vtkCellLocator` with MTime invalidation. Rename only; move verbatim. |
| `TerritoryInteractionState` (arm/active/module-active/carrier accessors on a display node) | **`PointPlacementState`** | Generic machinery; only the attribute-key *strings* are namespaced (`VascularTerritories.Armed`…). Parameterize the namespace prefix so each consumer gets its own keys on its own display node. |
| `TerritoryPlacementPipeline` (3D) minus territory grouping + vessel gating | **`SurfacePointPlacementPipeline3D`** (ADR-0038 3D base) | The add-on-click / drag-to-edit-nearest / delete / bare-move-decline (ADR-0033) arbitration; the display-space pick-radius grab; seed-glyph sphere rendering; hover marker + glow-halo overlay (`vtkOutlineGlowPass`); the 4 LayerDM traps (one pipeline per (view,type); configure-before-AddNode; UpdatePipeline on ResetDisplay; RequestRender no mid-event flush); `_jump_slices_to_world`; cursor-ray unproject; nearest-point-in-display. |
| `TerritorySlicePipeline` (2D) minus the same specifics | **`SurfacePointPlacementPipelineSlice`** (ADR-0038 slice base) | Slice projection into XY (`inverse(XYToRAS)`), distance-graded alpha, signed side tint, hard presence cutoff, hollow-circle handles + hover ring, the grab seam. |
| shared constants (`HALO_HOVER_COLOR/GRAB_COLOR`, scales, `FADE_DISTANCE_MM`, `POINT_PICK_RADIUS_PX`, `HANDLE_MIDTONE_FACTOR`) | **base module constants** | ADR-0038 §Context names these explicitly as duplicated. |
| the **point-provider seam** the base reads/writes | **`PointProvider`** protocol | ADR-0038 §Decision's seam: `iter_points()->(world, base_rgb)`; `has_edges()->bool`; `add_point(world)`, `move_point(key, world)`, `delete_point(key)`; `display_node` for the arm/hover/grab channel. Resection supplies grid+edges; territories + volumetry supply flat point lists, no edges. |

### 1b. VascularTerritories-SPECIFIC — stays in `VascularTerritoriesLib`

- **Per-territory grouping.** The carrier keys points per surgeon-named
  territory (`AddAnnotationPoint(territoryId, x,y,z)`, `GetAnnotationTerritoryIds`).
  The base sees a FLAT ordered point set; the territory→points fan-out lives in
  the VascularTerritories `PointProvider` adapter over `vtkMRMLCustomTerritoriesNode`.
- **Vessel visibility gating** — `VesselHighlightWiring.vascular_surface_polydata`,
  `VisibleStructuresCache`, `per_segment_vascular_surfaces`, `_segment_is_vascular`,
  `VASCULAR_TYPE_TOKENS` (SCT^29092000/51114001), `seed_structure_visible`. All
  vessel/SCT-specific. STAYS. The base takes an OPTIONAL "seed-visible?(point)"
  and "pick-surface polydata" hook; VascularTerritories passes the vessel-gated
  ones, volumetry passes trivial ones (see §3).
- `SeedStructureMapping`, `VesselConnectivity`, `TransientVmtkSeeds`,
  `VesselHighlightPipeline`/`VesselHighlightWiring` (hover highlight — the
  base's hover marker subsumes the *generic* half, but the vessel-SCT surface
  resolution is specific), `TerritorySliceProjection`, `TerritoryLabelMap`.
- **MRML:** `vtkMRMLAbstractTerritoriesNode`, `vtkMRMLCustomTerritoriesNode`,
  `vtkMRMLStdCouinaudTerritoriesNode`, storage, `vtkMRMLTerritoriesHighlightDisplayNode`.
  All stay module-owned (one display-node type per module, ADR-0013 §1).
- `TerritoriesTableWidget` — territory rows are specific. The point-row + delete
  idiom MAY share a tiny helper, but defer (low payoff, high coupling). STAYS.

### 1c. The GENERIC carrier + display-node SHAPE (not a shared class — a template)

Do NOT hoist `vtkMRMLCustomTerritoriesNode` into a shared MRML class. ADR-0014's
four-layer split is per-module (each module owns its wrapper/carrier/display/
storage). What is generic is the **shape**, which each consumer instantiates:

- a **data-carrier** of ordered surface-snapped points (flat, or keyed by a
  group id) with a per-group display slot (colour/label/visibility);
- a **data-only display node** (ADR-0025/0033 shape) carrying the arm/hover/grab
  interaction state + a `pickSurface` reference + transient adhering point;
- a **storage node** round-trip.

The volumetry carrier + display node are NEW module-local classes following this
shape (§3), not reuses of the territories ones.

### 1d. WHERE the shared core lives (recommendation)

**Recommendation: a new shared Python Lib package `SlicerLiverInteractionLib`**
(name OPEN — OQ2), a sibling to `LayerDMLib`, importable by any module's Lib.
Rationale:

- ADR-0004: widgets/interaction stay Python — the base is Python pipelines, so a
  Python Lib is the right home, NOT a C++ layer.
- ADR-0013 §5: the base hosts NO custom displayable manager — it is scripted
  Pipelines + the point-provider seam; each module keeps its own 3 registration
  calls (RegisterNodeClass + upstream LayerDM RegisterInFactory + Pipeline
  creator). The base only supplies the Pipeline BASE CLASSES the module's
  creator instantiates.
- Do NOT put it in `LayerDMLib` (that is upstream SlicerLayerDM's package; the
  base is Slicer-Liver-specific affordance). Do NOT put it in one module's Lib
  (creates a cross-module import dependency the wrong way).
- **`Liver` prefix dropped** on every new class (T2.7 / #341/#345 convention).

---

## 2. The #569 refactor — behaviour-preserving, characterization-guarded

ADR-0038 §Decision makes VascularTerritories a client of the base. Refactor
`TerritoryPlacementPipeline` / `TerritorySlicePipeline` to SUBCLASS the base and
supply a `PointProvider` adapter over `vtkMRMLCustomTerritoriesNode`, passing the
vessel-gated pick-surface + seed-visible hooks. The territory-specific behaviour
(grouping, vessel visibility gating, VMTK feed, connectivity) is UNCHANGED.

**Why behaviour-preserving:** the extracted base is the same code lifted, not
rewritten; the specific behaviour is re-injected through the seam. No user-
visible affordance changes.

**Characterization net (must stay GREEN, UNCHANGED — ADR-0027 + characterization-
tests-before-refactor):** every existing `VascularTerritories/Testing/Python`
test, both harnesses. The load-bearing ones for the refactor:

- `test_vessel_surface_pick.py` — pins `SurfacePick` (was `VesselSurfacePick`);
  the ONLY test whose imports change (rename), so it may edit the import line —
  the assertions stay identical.
- `test_territories_placement_pipeline.py` — 3D add/drag/delete/decline/no-drift
  arbitration. MUST pass unchanged against the refactored subclass.
- `test_territories_slice_pipeline.py` — slice projection/fade/side/presence.
- `test_territories_structure_visibility.py`, `test_territories_seed_structure.py`,
  `test_territories_surface_resolution.py` — vessel gating stays specific; MUST
  pass unchanged (proves the seam kept the gating hooks wired).
- `test_territories_annotation_carrier.py`, `test_territories_table.py`,
  `test_territories_vmtk_feed.py`, `test_territories_connectivity.py`,
  `test_territories_map_compute.py`, `test_territories_widget_panel.py`,
  `test_territories_action_enablement.py`, `test_vessel_highlight_*` — all
  unchanged.

If any of these needs an ASSERTION change, the refactor is NOT behaviour-
preserving — STOP and escalate. Only import-path lines may change (the renames).

---

## 3. LiverVolumetry application — seeds off markups onto the shared seam

Today (`LiverVolumetry.py`): a `qSlicerMarkupsPlaceWidget` +
`vtkMRMLMarkupsFiducialNode` (`ROIMarkersList`) fed to the C++ logic. The logic
reads per-point **labels** and positions:

- `vtkLiverVolumetryLogic::GetROIPointsLabelValue(labelmap, ROIMarkersList)`
- `vtkLiverVolumetryLogic::ComputeAdvancedPlanningVolumetry(..., ROIMarkersList, ...)`
- `vtkLiverVolumetryLogic::GenerateSegmentsLabelMap(..., ROIMarkersList)`
- `LiverVolumetry.py` reads `GetNthControlPointLabel` / `GetNthFiducialLabel` /
  `GetNumberOfControlPoints` to name generated segments.

So a volumetry seed = a labelled surface-snapped point; the label becomes a
segment name. This is a FLAT labelled point set — the base's flat consumer with
a per-point label slot.

### 3a. New module-local MRML (following §1c shape; `Liver` prefix dropped)

- **`vtkMRMLVolumetrySeedsNode`** — data-carrier: ordered surface-snapped points,
  each with a label + display colour; storage round-trip. (Flat — no grouping;
  the label is a per-point attribute, not a group key.)
- **`vtkMRMLVolumetrySeedsStorageNode`** — `.vsd.json` round-trip.
- **`vtkMRMLVolumetrySeedsDisplayNode`** — data-only (ADR-0025/0033): arm/hover/
  grab state, `pickSurface` ref (the input segmentation / target labelmap
  surface), transient adhering point, radius. NO rendering logic.

C++ MRML lives in a new `LiverVolumetry/MRML/` following the
VascularTerritories/MRML CMake pattern (upstream `SlicerMacro*` /
`vtkMacroKitPythonWrap`; platform-neutral).

### 3b. Placement pipeline registration (ADR-0013 §5 — 3 calls, NO custom DM)

In `LiverVolumetry.py` widget setup (mirroring VascularTerritories):
1. `RegisterNodeClass` for the 3 new node classes;
2. upstream LayerDM DM `RegisterInFactory`;
3. a Pipeline creator matching `(vtkMRMLViewNode, vtkMRMLVolumetrySeedsDisplayNode)`
   that returns `SurfacePointPlacementPipeline3D` wired to a volumetry
   `PointProvider` adapter; plus the slice creator for
   `SurfacePointPlacementPipelineSlice`.

The volumetry `PointProvider`:
- `iter_points()` → carrier points + per-point colour;
- `has_edges()` → False;
- `add/move/delete` → carrier writes;
- pick-surface hook → the input segmentation's closed surface (or the target
  labelmap's surface), NOT vessel-SCT-gated (volumetry seeds may land anywhere
  on the region); seed-visible hook → trivially True.

### 3c. C++ compute unchanged (ADR-0015) — the transient-fiducial adapter

Keep `vtkLiverVolumetryLogic` C++ SIGNATURES unchanged (they take
`vtkMRMLMarkupsFiducialNode*`). Feed them a **transient fiducial built inside the
call from the carrier**, mirroring ADR-0037 §Decision 4 / `TransientVmtkSeeds.py`
(the VMTK feed's exact idiom). The pure mapping (carrier points+labels →
fiducial-shaped payload) is a dependency-free function (bare-unit-testable); the
transient `vtkMRMLMarkupsFiducialNode` creation is a thin Logic wrapper (ADR-0004).
The per-point LABEL must round-trip into the transient fiducial's control-point
label so `GenerateSegmentsLabelMap` still names segments correctly.

**Why port (transient adapter) not rewrite the C++:** ADR-0015 keeps the ITK/VTK
region-grow C++ intact; rewriting its signatures to a new carrier type would
balloon the diff into T2.7 territory and touch
`vtkSlicerLiverVolumetryModuleLogicPython` import sites for no behaviour gain.
The adapter is the cheap, invariant-preserving path.

### 3d. Retire the markups seed list

Remove `ROIMarkersListSelector` / `qSlicerMarkupsPlaceWidget` and their handlers;
replace with a minimal seeds table (§6, coordinated with #417). Migrate any
persisted scene with a fiducial `ROIMarkersList` (graceful load path).

---

## 4. The ADR — extend ADR-0038 (do NOT author ADR-0039)

**Recommendation: EXTEND ADR-0038 with an implementation amendment; do NOT open
ADR-0039.** ADR-0038 already made the reusable-seam decision + shape and named
its implementation "deferred to a follow-up issue." #570-with-reusability IS that
follow-up. The amendment records:

- the extraction is triggered by adding LiverVolumetry as the **third consumer**;
- the shared home = `SlicerLiverInteractionLib` (OQ2) + the concrete base +
  seam names (§1a);
- LiverVolumetry joins as a client with a flat, no-edges, ungated `PointProvider`;
- the resection→base direction is honoured (resection pipelines are extracted;
  #569 + volumetry are clients);
- the move-bezier-off-markups goal (`project_move_bezier_off_markups`) is the
  natural FOURTH consumer once its own ADR lands — the seam is designed to admit
  it (grouped control-point manipulation = a grouped `PointProvider`).

A NEW ADR-0039 would fork the decision ADR-0038 already owns → two ADRs for one
seam. Only open ADR-0039 if the maintainer chooses the narrower "#569+volumetry
only, resection untouched" scope (OQ1), which genuinely deviates from ADR-0038.

**ADRs this touches:** 0038 (the seam — amended), 0037 (VascularTerritories,
refactored to client), 0032/0033 (interaction seam + hover discipline — the base
enforces them once), 0013 §1/§5 (one pipeline per type; 3 registration calls; no
custom DM), 0014 (four-layer split — volumetry gets its own carrier/display/
storage), 0025 (data-only display node + reslice), 0015 (C++ compute intact),
0004 (Python interaction/widgets), 0012 (v2.0.0 LayerDM scope — this discharges
volumetry's obligation via a real off-markups migration, superseding the earlier
"compute-then-display, marginal" reading now that the maintainer chose B),
0002 (LayerDM migration target), 0027 (invariant-test-first), 0010 (a11y table),
0011 (SCT — only the vessel gating, which stays specific).

---

## 5. #417 reconciliation

#417 (unified planning-table volumetry/seeds/groupings widget) also owns a
volumetry/seeds table. **Recommendation: ship a MINIMAL volumetry seeds table
now** (columns: visibility, colour swatch, label, on-surface status, delete;
Python composition ADR-0004; a11y glyph+text ADR-0010) as the replacement for the
retired place-widget — volumetry needs *some* seed UI to be usable end-to-end
(the v2.0.0 fully-usable bar). Keep it deliberately THIN and carrier-backed so
#417 can later absorb it by re-parenting the same carrier under the unified
table. Do NOT build territory-style grouping UI here. Flag in the PR that the
table is a #417 seam, not its final form. (If the maintainer prefers, defer the
table entirely to #417 and ship seeds-off-markups with placement-only + a
transient list — OQ3; NOT recommended, leaves volumetry unusable for naming
segments.)

---

## 6. Slice / PR breakdown (recommended ordering)

ADR first, then extract+refactor (behaviour-preserving, its own PR), then the
volumetry application. Stacked off `preview` (each on the prior).

- **PR 0 — ADR-0038 implementation amendment** (authored as a separate
  maintainer-authorized step, not by the implementer). Records §1d home, §1a
  names, volumetry-as-third-consumer, resection→base direction.
- **PR 1 — extract the ADR-0038 base + refactor #569 (behaviour-preserving).**
  Create `SlicerLiverInteractionLib` with `SurfacePick`, `PointPlacementState`,
  `SurfacePointPlacementPipeline3D/Slice`, `PointProvider`, shared constants.
  Rebase resection (`ControlPolygonPipeline` / `SliceControlPolygonPipeline`)
  AND VascularTerritories pipelines onto the base via seam adapters. The entire
  existing resection + VascularTerritories characterization suites (both
  harnesses) stay green UNCHANGED (§2). This is the biggest, riskiest PR — it is
  a pure refactor with the two existing suites as the net.
  - **OPEN QUESTION 1** gates the SIZE of this PR: full ADR-0038 (resection +
    territories both clients) vs the prompt's narrower "territories + volumetry
    share, resection later." Recommend full ADR-0038.
- **PR 2 — LiverVolumetry seeds off markups.** New `vtkMRMLVolumetrySeedsNode` +
  storage + display node; the volumetry `PointProvider` adapter; the 3
  registration calls; the transient-fiducial C++ adapter (§3c) feeding the
  unchanged `vtkLiverVolumetryLogic`; retire `ROIMarkersList` + place widget.
- **PR 3 — minimal volumetry seeds table** (§5), a11y glyph+text, #417 seam note.
  (May fold into PR 2 if small.)

If OQ1 = narrow scope: PR 1 extracts FROM #569 only (not resection), and PR 0
becomes a NEW ADR-0039 recording the deviation from ADR-0038's resection→base
direction.

---

## 7. Test plan (ADR-0027, two-harness discipline)

Mirror the `VascularTerritories/Testing/Python` layout + its `conftest.py`
(snap/teardown autouse, mirrors LiverSegmentation conftest). **Two harnesses:**
launched-Slicer AND bare `PythonSlicer -m pytest` scaffold — a green launched run
is NOT a green bare run. **Launched-sweep root-order trap:** keep any new
volumetry test root ordered so **LiverSegmentation root stays LAST**, or the
conftest collision fakes ~34 failures. **LayerDM state on the display node:** the
arm/active/carrier/pick state MUST live on the shared display node, not a Python
pipeline instance (bit hard on #593) — verify LIVE.

- **Generic base (new, in the shared Lib's Testing):**
  - `test_surface_pick.py` — bare pure-VTK (rename of the vessel-pick test's
    geometry assertions, now against `SurfacePick`).
  - `test_point_placement_pipeline_3d.py` — bare-ish: add-on-click / drag-nearest
    / delete-one / bare-move-decline / no-drift, against a fake `PointProvider`.
  - `test_point_placement_pipeline_slice.py` — projection/fade/side/presence.
  - `test_point_placement_state.py` — arm/active/module-active/carrier accessors,
    namespaced keys. Bare.
- **#569 characterization net** (§2) — unchanged assertions, both harnesses.
- **LiverVolumetry (new):**
  - `test_volumetry_seed_carrier.py` — carrier add/move/delete + label + storage
    round-trip. Bare pure-VTK (wrapped C++ node imported via the module's wrapped
    logic Python module, never plain `vtk`/`slicer`).
  - `test_volumetry_seed_transient_fiducial.py` — the pure carrier→fiducial-
    payload mapping preserves position + LABEL + order. Bare.
  - `test_volumetry_seed_placement.py` — the volumetry `PointProvider` + base:
    click adds one seed on the surface, drag edits nearest, delete removes one.
    Launched (LayerDM + view).
  - `test_volumetry_seed_display_node.py` — data-only contract. Bare-VTK.
  - `test_volumetry_compute_from_carrier.py` — `vtkLiverVolumetryLogic` fed the
    transient fiducial produces the SAME volumetry table + segment names as the
    old `ROIMarkersList` path (the invariant that the port preserves compute).
  - Registration smoke — the 3 ADR-0013 §5 calls register with NO custom DM.

Implementer-brief hygiene (bake into any handoff): `./Utilities/SetupForDevelopment.sh`;
local pre-commit + relevant CTest BEFORE push; build inside worktree `build/`;
pre-PR grep for `guix`/`nix`/`apt`/`brew` (platform neutrality); NO PR/issue refs
in source; NO `Co-Authored-By: Claude` / "Generated with" in commit messages;
AI-authorship notice in PR body only.

---

## 8. Risks

- **Refactor-scope blast radius (highest).** PR 1 touches resection AND
  territories pipelines at once. Mitigation: the two mature characterization
  suites are the net; extract in small commits (pick → state → 3D base → slice
  base → resection client → territories client), running both suites per step.
- **The base leaking a specific concern.** The vessel-visibility gating and the
  territory grouping must NOT bleed into the base (ADR-0038 §"What is not
  shared"). Guard: the base test uses a FAKE flat `PointProvider` with no gating;
  if it needs a vessel concept, the seam is wrong.
- **LABEL fidelity in the transient fiducial** — if the per-seed label doesn't
  round-trip, `GenerateSegmentsLabelMap` mis-names segments. Pinned by
  `test_volumetry_compute_from_carrier.py` + `test_volumetry_seed_transient_fiducial.py`.
- **#417 collision** (§5) — minimal carrier-backed table mitigates; PR note.
- **Direction conflict with ADR-0038** (§0) — resolved by following the ADR;
  OQ1 escalates if the maintainer wants the narrower scope.
- **T2.7 rename temptation** — new classes drop `Liver` (required); do NOT rename
  existing `vtkLiverVolumetryLogic` / `vtkMRMLCustomTerritoriesNode` inside #570
  (that is T2.7; balloons the diff + touches wrapped-Python import sites).
- **Volumetry pick surface** — is the seed snapped to the input segmentation
  surface or the target labelmap? The old markups path let seeds land free in
  space; snapping is a behaviour CHANGE. See OQ4.

---

## 9. OPEN QUESTIONS (consolidated)

> **RESOLVED 2026-07-27 (maintainer).** OQ1 = **full ADR-0038** (extract from
> resection; resection + territories + volumetry all clients). OQ2 =
> **`SlicerLiverInteractionLib`**. OQ3 = **minimal carrier-backed table now**
> (thin, re-parentable, #417 seam). OQ4 = **in-volume / slice-click pick**, NOT
> surface-snap — the seed is a region-grow voxel index (`vtkLiverVolumetryLogic`
> `TransformPhysicalPointToIndex` → `ConnectedThreshold`), so it must land
> inside the region; the pick step is a swappable provider on the seam (base
> extension). OQ5 = **amend ADR-0038** (done — see the ADR's Implementation
> amendment 2026-07-27), no ADR-0039. The §3b "pick-surface = input segmentation
> closed surface" line is SUPERSEDED by OQ4's in-volume pick.

1. **Scope of the extraction (gates PR 1 size + the ADR choice).** Full ADR-0038
   (extract from resection; resection + territories + volumetry all clients) vs
   the prompt's narrower "extract from #569; resection untouched for now."
   **Recommend: full ADR-0038** — it is Accepted and names this the follow-up; a
   narrower scope deviates from its resection→base direction and needs an
   ADR-0038 amendment (or a new ADR-0039) recording the deviation.
2. **Shared-core home + name.** `SlicerLiverInteractionLib` (recommended) vs
   folding into `LayerDMLib` (rejected: upstream package) vs a module Lib
   (rejected: wrong-way dependency). Confirm the name.
3. **Volumetry seeds table now, or defer to #417.** **Recommend: minimal
   carrier-backed table now** (volumetry must be usable end-to-end for v2.0.0);
   thin + re-parentable so #417 absorbs it.
4. **Seed snapping semantics.** Do volumetry seeds SNAP to a surface (the base's
   default, on-surface ~0) or may they land free in the volume (the old markups
   behaviour)? Region-growing seeds are conceptually IN the volume, not on a
   surface. **Recommend:** snap to the target region's surface for placement UX
   but allow the carrier to hold the raw picked point; confirm whether the
   region-grow needs interior seeds (may require an "in-volume" pick variant, not
   the surface pick) — this is the one place volumetry may need a base EXTENSION
   rather than a plain client.
5. **ADR: amend 0038 vs new 0039.** **Recommend: amend 0038** (it owns the
   decision). New 0039 only if OQ1 = narrow scope.

---

## 10. Suggested next handoff

- Resolve **OQ1 + OQ4** first (they gate the shape). Then:
- **ADR step** (maintainer-authorized): amend ADR-0038 with §1d/§1a/third-consumer.
- `liver-test-designer` — the generic-base invariants + the volumetry
  compute-preservation invariant, characterization-first.
- `liver-implementer` — PR 1 (extract+refactor, behaviour-preserving) THEN PR 2/3.
- Until OQ1 + OQ4 are answered: do not write code.
