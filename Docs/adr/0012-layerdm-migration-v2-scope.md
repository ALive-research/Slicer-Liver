# 0012. Scope of LayerDM migration for v2.0.0

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Amendments

- **2026-07-09 — v2.0.0 absorbs the v2.1 feature plan.**  Maintainer
  decision: v2.0.0 tags when the FULL planned feature set is usable
  end-to-end, not before.  Everything this ADR's §"Out of v2.0.0
  scope" deferred to v2.1.0 moves INTO v2.0.0 scope: the LiverSegments
  / LiverVolumetry / Modeling LayerDM display-node migrations, the
  cross-module locator unification, the feature issues previously
  milestoned v2.1.0, and the ADR-0020 / ADR-0022 implementations
  (their "target v2.1" annotations read "target v2.0" from this
  date).  The §Context MINOR-vs-MAJOR reasoning is unaffected — the
  absorbed work remains scene-compatible and additive; it simply
  ships before the tag rather than after it.  The v2.0.0 release
  tracker is the single work queue; the v2.1 tracker holds only
  post-release carries.

## Context

[ADR-0002](0002-migrate-to-slicerlayerdm.md) commits Slicer-Liver to
migrate from the legacy Markups-based three-node resection assembly
to **SlicerLayerDisplayableManager (SLDM)** display infrastructure.
The ADR outlines a phased migration that, taken at face value, covers
the full module surface: LiverMarkups, LiverResections, LiverSegments,
LiverVolumetry, and the top-level Liver module.  ADR-0002 sets the
direction; it does not commit a specific release to absorbing the
whole migration in one go.

During v2.0.0 release planning the migration cost was reconsidered
against the per-module payoff.  LayerDM's value proposition is
**interactive view-coupled display management** — picking, hovering,
multi-view linking, custom rendering pipelines per view.  That value
is concentrated in the resection-planning workflow (Bezier surface
editing, resectogram, interactive locator), where the legacy
three-node assembly and `vtkMRMLLiverResectionsDisplayableManager2D`
boilerplate are the structural pains ADR-0002 enumerates.

LiverSegments, LiverVolumetry, and the modeling pipelines (PSR,
VMTK-based surface generation) are largely **compute-then-display**
surfaces.  Their outputs — segments, models, volume tables — render
via standard Slicer mechanisms (`vtkMRMLSegmentationDisplayNode`,
`vtkMRMLModelDisplayNode`, table widgets) with no tight interactive
picking loop.  LayerDM's benefit there is marginal — primarily a
future "linked highlight / locator" feature that has no committed
v2.0.0 user requirement.

Per [ADR-0007](0007-version-numbering-policy.md), introducing **new**
display node classes is additive and MINOR-eligible (compatibility
surface N covers *renaming or removing* existing node classes, not
*adding* new ones).  Deferring the LayerDM display nodes for some
modules to v2.1.0 therefore does **not** force a v3.0.0 bump — the
deferred migrations ship as a scene-compatible MINOR release on top
of v2.0.0.

A subsequent design discussion further collapsed the in-scope module
list.  `vtkMRMLMarkupsSlicingContourNode` and
`vtkMRMLMarkupsDistanceContourNode` are not independent annotations —
they are **alternative initialisation affordances for the same Bezier
surface** (each defines a ring on the target mesh that seeds the
Bezier fit).  Two additional forces — ring-aware right-click on the
4×4 Bezier control grid, and per-role control-point glyph rendering
— require dropping the `vtkSlicerMarkupsWidget` base in favour of a
custom widget subclassing `vtkAbstractWidget` directly.  The
combined consequence: LiverMarkups dissolves entirely in v2.0.0, its
three primitives relocate into LiverResections as non-Markups data
nodes, and the v2.0.0 in-scope list shrinks to two phases.  Full
rationale lives in ADR-0014 (forthcoming).

## Decision

Narrow the v2.0.0 scope of ADR-0002's LayerDM migration to the
modules where LayerDM earns its weight.  Defer the remainder to
v2.1.0, where it ships as additive (no scene-breaking changes).

### In scope for v2.0.0 (display-side LayerDM migration)

Two phases, in order:

- **T2 — LiverResections (all-in)** — pattern-setting migration.
  Absorbs the LiverMarkups dissolution per
  ADR-0014 (forthcoming): the three Markups-derived primitives
  (BezierSurface + SlicingContour + DistanceContour) relocate into
  LiverResections as non-Markups data nodes, with a single
  state-aware LayerDM Pipeline owning three state-conditional
  Representations (per ADR-0013 §4, forthcoming).  Bezier-fitting
  and ring-extraction algorithms lift to a C++ algorithm library
  per ADR-0015 (forthcoming).  Resolves the structural
  pains ADR-0002 §1–§5 enumerate (three-node assembly, six
  `std::map` members, leaked display fields, Markups
  interaction-model ceiling, DM boilerplate).  Delivers the real-view
  fixture deferred by PR #316 (the pytest scaffold from ADR-0008's
  workflow layer); provides the worked example T3 reviews against.
- **T3 — Resectogram + distance maps** — split from LiverResections
  as its own SLDM pipeline.  View-coupled rendering with locator
  crosshair; the view-and-pipeline coupling is fundamentally a
  LayerDM concern.  Distance-map texture is a Representation inside
  the resectogram Pipeline ("entangled with resectogram texture
  generation"): one-shot CPU compute, but the display path is
  LayerDM-coupled and cannot be cleanly separated from the
  resectogram pipeline.

### Out of v2.0.0 scope (display migration deferred to v2.1.0)

For each of these modules the **data-model and algorithmic work
continues in v2.0.0**; only the LayerDM display node migration is
deferred:

- **LiverSegments** — terminology dispatch (per the forthcoming
  ADR-0011), tool integrations (TotalSegmentator, MONAILabel,
  Kumar-Oram), and LabelToSCT bridges all land in v2.0.0.  LayerDM
  display node deferred.
- **LiverVolumetry** — generic seed-and-category partition framework
  and the Couinaud preset land in v2.0.0.  LayerDM display node
  deferred.
- **Modeling pipelines (PSR, VMTK)** — backend modernisation and
  terminology-keyed dispatch land in v2.0.0.  LayerDM display node
  deferred (would only matter for cross-module locator unification,
  itself deferred).
- **Cross-module locator unification** — deferred to v2.1.0 as a
  separate concern; the LiverResections/Resectogram LayerDM
  implementation in v2.0.0 will inform the locator pattern.

The **top-level Liver module re-orchestration** is correspondingly
scoped: v2.0.0 re-orchestrates only the modules that migrated to
LayerDM.  v2.1.0 expands the re-orchestration when the deferred
modules migrate.

## Alternatives considered

### A. Full ADR-0002 migration in v2.0.0 (all modules)

Migrate LiverMarkups, LiverResections, Resectogram, distance maps,
LiverSegments, LiverVolumetry, and the modeling pipelines to LayerDM
display nodes in a single release.

**Rejected** because the per-module payoff is uneven.  LayerDM
addresses no committed user requirement in
LiverSegments/LiverVolumetry/Modeling — their outputs are
compute-then-display surfaces that render fine through standard
Slicer display nodes.  Full migration extends the release timeline
without a commensurate user-visible win, and forces the
cross-module locator pattern to be designed up-front rather than
informed by the LiverResections/Resectogram migration.

### B. Defer all of ADR-0002 to v2.1.0 (no LayerDM in v2.0.0)

Ship v2.0.0 with the data-model and algorithmic work but no LayerDM
migration; defer the entire SLDM transition to v2.1.0.

**Rejected** because the resection-planning workflow is the primary
user-facing surface of Slicer-Liver and benefits most from LayerDM.
Deferring it loses the headline win of v2.0.0 — the resection
rewrite, the resectogram side panel, the Bezier interaction
unblock.  The three-node assembly that ADR-0001 documents and
ADR-0002 supersedes is precisely the pain that v2.0.0 needs to
resolve.

### C. Ship the deferred LayerDM migrations as a v2.0.x patch series

Land LiverSegments / LiverVolumetry / Modeling LayerDM display
nodes as v2.0.1, v2.0.2, … patch releases after v2.0.0.

**Rejected** because additive display nodes are functionally MINOR
per ADR-0007, not PATCH (which is bug-fixes only — no new node
classes, no new workflows).  The natural channel for the deferred
migrations is v2.1.0.  Mis-using PATCH for additions would erode
the version-policy signal that ADR-0007 establishes.

### D. Adopt LayerDM only for the resectogram-locator path; keep LiverResections on Markups

Cut the scope tighter than option chosen — LayerDM only where the
view-coupling is unavoidable (resectogram + locator), with
LiverResections itself remaining on the three-node Markups
assembly.

**Rejected** because LiverResections benefits substantially from
LayerDM on its own.  Bezier surface interaction is fundamentally a
display-pipeline concern (ADR-0002 §4); the three-node assembly and
the six `std::map` members in `vtkSlicerLiverResectionsLogic`
(ADR-0002 §2) cannot be cleanly resolved without migrating the
resection node itself.  The cut-line is not at the resectogram
alone; LiverResections is the module where LayerDM pays the most.

## Consequences

### Easier

- **v2.0.0 ships ~25–30% less code** than a full ADR-0002 migration
  would have demanded, with the user-visible wins (resection
  planning rewrite, terminology-driven UI cleanup, generic
  volumetry, modernised modeling backends) preserved.
- **Reduces v2.0.0 risk surface** and shortens the path to release
  tag.  Each deferred module removes one migration phase from the
  v2.0.0 critical path.
- **The cross-module locator pattern is informed, not guessed.**
  The LiverResections/Resectogram LayerDM implementation in v2.0.0
  produces the implementation experience that the v2.1.0 locator
  unification design draws on.

### Harder

- **The MRML node hierarchy after v2.0.0 is partially migrated** —
  LiverResections and Resectogram carry new SLDM display nodes;
  LiverSegments / LiverVolumetry / Modeling do not.  This is a
  temporary inconsistency until v2.1.0 and must be documented in
  the v2.0.0 architecture diagrams (one diagram shows migrated
  modules, one shows the still-legacy display path).
- **v2.1.0 introduces additional new display node classes** for the
  deferred modules — a MINOR bump per ADR-0007 (additive,
  scene-compatible with v2.0.0).  Each deferred module needs its
  own migration ADR or a single covering ADR at v2.1.0 planning
  time.
- **Locator-flavoured features in segmentation/volumetry/modeling
  stay deferred** for the v2.0.0 release cycle.  No interactive
  cross-module highlight; clinicians wanting that feature wait
  until v2.1.0.

## Open questions

These do not block adoption of this ADR:

- Whether the cross-module locator unification in v2.1.0 is a single
  release or its own staged sub-roadmap.  Defer to the v2.0.0
  retrospective.
- Whether any v2.0.0 partial-LayerDM adoption uncovers a design
  constraint that forces re-scoping (e.g. the LiverResections
  pipeline pattern turns out to mandate LiverSegments migration as
  a prerequisite).  Reviewed at the end of migration phase T3.

## References

- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the canonical
  statement of the LayerDM migration target.  This ADR narrows the
  v2.0.0 slice of that migration; it does **not** retract ADR-0002's
  broader direction.
- [ADR-0007](0007-version-numbering-policy.md) — governs the
  versioning consequences (additive display nodes are MINOR; the
  deferred migrations ship in v2.1.0, not as a v2.0.x patch series).
- ADR-0009 (UX discipline) — applies to all in-scope LayerDM
  migrations: interface diagrams + methodology citations remain
  mandatory.
- ADR-0011 (terminology dispatch for LiverSegments) — the
  data-model work that lands in v2.0.0 for the
  display-migration-deferred LiverSegments module.
- ADR-0013 (forthcoming) — the canonical LayerDM Pipeline pattern
  that the T2 LiverResections migration and T3 Resectogram split
  both instantiate.
- ADR-0014 (forthcoming) — the LiverMarkups dissolution decision
  that this amendment folds into the T2 scope.
- ADR-0015 (forthcoming) — the C++ algorithm library decision
  (Bezier fitter, ring extractors, contour parameterizer)
  supporting the T2 implementation.
- [SlicerLayerDisplayableManager](https://github.com/KitwareMedical/SlicerLayerDisplayableManager)
  — the upstream framework adopted per ADR-0002.
