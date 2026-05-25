# 00 — ResectionPlanNode architecture overview

## Why this exists

The post-PR #430 `/slicer-review` flagged two architectural drifts:
`OrderIndex` placement and the margin-storage path. The maintainer's
2026-05-25 review of the proposed fix surfaced a deeper question:
the legacy `vtkMRMLLiverResectionNode` was retired under T2.7's
"data vs display" split (ADR-0014), which **orphaned the clinical
layer** of a resection plan — name, margins, ordering, surgical
state. Putting these on the surface or the display node confuses
layers.

The maintainer's NURBS observation tightens the case: a clinical
plan should be representable by *different surface geometries*
(Bezier today, NURBS in v2.1). If clinical state lives on the
surface, swapping geometries means migrating clinical state. If it
lives on a separate plan node referencing an abstract surface,
swapping is polymorphic and clinical state is invariant.

The maintainer's third observation completes the model:
**territories, volumetry partitions, and stage selection are not
plan-bound** — they're scene-level state with only visual
co-existence with plans. The `.lrp.json` should carry the plan and
its surface, **nothing else**.

## What this design commits

1. **A new abstract surface hierarchy** (mirrors PR #425's
   territories pattern):
   - `vtkMRMLAbstractParametricSurfaceNode` (abstract)
   - `vtkMRMLBezierSurfaceNode` (concrete, v2.0)
   - `vtkMRMLNurbsSurfaceNode` (concrete, v2.1 sibling)
2. **A new clinical-layer node**:
   - `vtkMRMLResectionPlanNode` carrying name, safety + risk margins,
     ordering, plan state, and a `geometry` reference to the abstract
     surface.
3. **Plan owns the storage**:
   - `vtkMRMLResectionPlanStorageNode` writes `.lrp.json`.
   - `.lrp.json` carries plan fields + the referenced surface's full
     bulk data via the `type`-discriminated `surface` block.
   - The surface itself is **non-storable** (no default storage node).
4. **Slim `WriteXML` on every node** (per Markups convention):
   - `.mrml` carries identity metadata + lightweight scalars + node
     references.
   - The storage file carries everything else.
5. **No `scene.*` block in `.lrp.json`**:
   - Plan does not reference territories, partitions, or stage state.
   - Each scene-level concept persists via its own MRML mechanism.
6. **Single shared display class** (mirrors `vtkMRMLMarkupsDisplayNode`'s
   role across 8+ markup data subclasses):
   - `vtkMRMLParametricSurfaceDisplayNode` (concrete, shared) serves
     both `vtkMRMLBezierSurfaceNode` and `vtkMRMLNurbsSurfaceNode`.
   - No abstract display base, no per-surface-type display subclass.
     If NURBS-specific display fields appear later, a subclass is
     added at *that* point, not pre-emptively.

## The pattern: method-metadata wraps canonical data

The 2026-05-25 design review surfaced a pattern that recurs across
the v2.0 model:

| Wrapper (method + metadata) | →references→ | Data carrier (bulk content) |
|---|---|---|
| `vtkMRMLResectionPlanNode` | `geometry` | `vtkMRMLAbstractParametricSurfaceNode` |
| `vtkMRMLAbstractTerritoriesNode` | `segments` (proposed) | `vtkMRMLSegmentationNode` (Slicer-core) |

Both pairs do the same thing: separate the **clinical or method
metadata** (name, margins, ordering, method discriminator,
subdivision enum, SCT codes…) from the **canonical bulk data**
(control grid, init points; segment masks). The wrapper references
the carrier via a typed node-reference role; the carrier persists
through its own storage path; the wrapper's own metadata is small.

This pattern is the v2.0 expression of the **layered MRML
architecture** ADR-0014 partially established (data vs display vs
storage). It extends to **wrapper vs carrier**: clinical or method
metadata is the missing fourth layer above geometry, and it should
not be conflated with geometry, display, or storage.

The pattern was not articulated as a project-level decision before;
the audit in [06](06-pattern-and-audit.md) lists where existing ADRs
and architecture docs need amending to acknowledge it.

## Documents in this design set

- **00 — overview** (this file)
- **[01 — class hierarchy](01-class-hierarchy.md)** — the new MRML
  classes, their inheritance, the polymorphic dispatch points.
- **[02 — node references](02-node-references.md)** — runtime
  reference graph in scene; what references what and what
  deliberately does not.
- **[03 — storage ownership](03-storage-ownership.md)** — `.mrml` vs
  `.lrp.json` split; what lives where; the storability matrix.
- **[04 — save / load flows](04-save-load-flows.md)** — sequence
  diagrams for scene save, single-plan save, and standalone load;
  failure modes.
- **[05 — `.lrp.json` v2 schema](05-lrp-json-schema.md)** — the
  trimmed shape; what changed vs PR #430's shipped v2; cross-machine
  transfer implications; NURBS polymorphism preview.
- **[06 — pattern articulation + ADR audit](06-pattern-and-audit.md)** —
  the wrapper-vs-carrier pattern as a project-level invariant; per-
  ADR/arch-doc audit findings; specific amendments needed.

## Open questions for maintainer review

1. **Naming**: `vtkMRMLAbstractParametricSurfaceNode` vs
   `vtkMRMLAbstractResectionSurfaceNode` vs other. Recommended
   `Parametric` — technically precise, parallels Slicer-core
   `vtkMRMLAbstract*Node` convention.
2. **Plan-less surface storage**: surface non-storable (recommended),
   or optional fallback storage for the corner case.
3. **Scope acceptance**: ~2 weeks of focused agent-fleet work for
   the bundled landing (ADR + abstract surface + plan node + shared
   display rename + storage refactor + ADR-0014/-0018 amendments).
   Lands before T5.2-d sidebar widget so the sidebar builds on the
   right substrate.
4. **#432 disposition**: absorb into this broader refactor (margin
   path + OrderIndex relocation become trivial consequences of the
   model) and close, or keep as fine-grained tracker.
5. **Test fallout in #431**: the Phase 2 scene-scan tests (territories
   sibling-class discovery via scene scan) become obsolete when the
   `scene.classification` block disappears. Retire as part of the
   refactor PR, or preemptively.
6. **Display-class rename migration**: `vtkMRMLBezierSurfaceDisplayNode`
   → `vtkMRMLParametricSurfaceDisplayNode`. Rename touches Display
   node tests, Pipeline factory, scene-load compatibility. Manage as
   one commit inside the refactor PR.

**Resolved during 2026-05-25 design review** (no longer open):

- Display-node abstraction → answered. **No abstraction**; single
  shared concrete display class per Markups precedent.

## Out of scope for this design

- `vtkMRMLLiverVolumetryPartitionNode` (v2.1, no class exists yet).
- Cross-machine plan transfer with stable IDs (v2.1, #415).
- Locator architecture (T5.3, #414 — ADR-0025).
- Liver-shell vertical sidebar widget (T5.2-d, #410). The sidebar
  builds on `GetNodesByClass("vtkMRMLResectionPlanNode")` after this
  refactor lands.
