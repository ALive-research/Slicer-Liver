# 0019. Resection state machine: extend to a third `Confirmed` state

- **Status:** Proposed
- **Date:** 2026-05-18
- **Deciders:** Rafael Palomar
- **Diagrams:** `Docs/architecture/resection-state-machine.md`
- **PR:** _filled in on merge_

## Context

The v2.0.0 resection state machine that landed across PRs #341
(data-node ResectionState enum + initial 2-state contract) and #350
(read-only-after-Planning enforcement) is a **2-state automaton**:

```
       Init  →  Planning   (irreversible)
```

Per [ADR-0014][adr-0014] §4 and PR #350's per-setter guards on
`vtkMRMLBezierSurfaceNode`, once a resection transitions from `Init`
to `Planning` the init data (slicing-plane origin/normal + init
points OR distance-spheroid center/radii + init points) becomes
**read-only audit data**.  No `Planning → Init` transition is
permitted.

Review feedback on PR #369 (T2.6-LayerDM) surfaced a missing third
state, observable in the v1 user experience but not captured in the
v2.0.0 contract:

> *"After the resection has been defined, for visualization, the
> control points/polygon disappear (no further manipulation possible)
> and the resection exceeding the liver parenchyma is removed
> (shader; current v1 has this functionality). This provides users
> with a cleaner view. This state can be called `Locked` or
> `Confirmed` and it has a way back to resection modification."*
> — RafaelPalomar on PR #369, 2026-05-18

The clinical workflow this third state enables:

- The surgeon iterates on the Bezier-surface control polygon to
  shape the resection plane during **`Planning`**.
- When satisfied, the surgeon **`Confirms`** the resection.  The
  control polygon + widget visuals disappear; the surface is
  rendered with the parenchyma-trim shader (the bit of the surface
  outside the liver is hidden); the visualization is "clean" for
  review or surgical-plan export.
- If the surgeon changes their mind, they can **return to
  `Planning`** to modify the control polygon — the surface +
  control-polygon visuals reappear, the trim shader disengages.

Crucial detail: the `Confirmed` state is **not "done"**; it is a
viewing mode that locks manipulation without losing the ability to
go back.  Modelling it as a state of the same data node (vs a flag
on the display node) is the architectural decision this ADR
commits.

The v1 module (legacy `vtkMRMLLiverResectionNode` family) carried
this functionality in a parallel enum (`Initialization` /
`Deformation` / `Completed`); the v2.0.0 work consolidated to
2-state and the third concept got lost in translation.  This ADR
restores it under the v2.0.0 contract.

[adr-0001]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0001-resection-three-node-assembly.md
[adr-0013]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0014-livermarkups-dissolution.md
[adr-0018]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0018-nurbs-extension-surface.md

## Decision

Extend `vtkMRMLBezierSurfaceNode::ResectionState` from a 2-state
enum (`Init = 0`, `Planning = 1`) to a **3-state enum**:

```
ResectionState ::= Init = 0
                 | Planning = 1
                 | Confirmed = 2
```

with the transition table:

```
                            ┌──────────────────────────────────────┐
                            ▼                                      │
        Init ──────────► Planning ◄═══════════════════► Confirmed
   (start state)      (irreversible from Init;       (round-trippable
                       reversible from Confirmed)     with Planning)
```

The full transition matrix:

| From → To  | Init | Planning  | Confirmed |
|------------|------|-----------|-----------|
| Init       | self | **allowed** (irreversible) | forbidden |
| Planning   | forbidden (per ADR-0014 §4) | self | **allowed** |
| Confirmed  | forbidden | **allowed** (round-trip back) | self |

Forbidden transitions emit a `vtkWarningMacro` and reject the state
change (mirrors PR #350's existing rejection pattern for
`Planning → Init`).

### Per-state contract

| State        | Control polygon | Widget interaction | Surface render | Init data       | Audit fields |
|--------------|-----------------|--------------------|----------------|-----------------|--------------|
| `Init`       | absent          | init-mode-specific widget (markers + plane / spheroid) | minimal (init geometry) | editable | live |
| `Planning`   | visible (M×N grid + ring glyphs) | `vtkLiverBezierWidget` enabled (left-drag, right-drag-ring, right-click context) | full surface; grid overlay shader on; **no parenchyma trim** | **read-only** | preserved |
| `Confirmed`  | **hidden**      | widget **disabled** | full surface; grid overlay **off**; **parenchyma-trim shader on** | **read-only** | preserved |

### Pipeline dispatch (per [ADR-0013][adr-0013] §4)

The Pipeline's dispatch table grows a row:

| `(ResectionState, InitializationMode)`   | Representation                                |
|------------------------------------------|-----------------------------------------------|
| `(Init, SlicingPlane)`                   | `SlicingPlaneInitRepresentation` (existing)   |
| `(Init, DistanceSpheroid)`               | `DistanceSpheroidInitRepresentation` (existing) |
| `(Planning, *)`                          | `BezierPlanningRepresentation` (existing)     |
| **`(Confirmed, *)`**                     | **`ConfirmedRepresentation`** (new)           |

`ConfirmedRepresentation` IS NOT a render-mode flag on
`BezierPlanningRepresentation`.  It is a **first-class sibling
Representation** with its own VTK pipeline:

- No widget instance.
- Surface mapper uses the **parenchyma-trim shader** (relocated from
  `LiverMarkups/VTKWidgets/` during T2-mapper-relocation; the same
  shader the v1 module's `Completed` state uses).
- Grid-overlay shader uniforms (`GridVisibility`, `GridDivisions`,
  `GridThickness`, `ResectionGridColor` on the display node) are
  bypassed — `Confirmed` always renders the grid as off, regardless
  of the display node's `GridVisibility` field.

### Storage / persistence

`.lrp.json` schema (PR #361 v1; will be v2 after [ADR-0018][adr-0018]'s
enabler PR) carries `state` as a string-valued enum.  v1/v2 readers
that don't recognise `"Confirmed"` should fall back to `"Planning"`
gracefully (forward-compatible default).  v3 readers know all three.

For round-trip: a scene saved with a `Confirmed` resection re-opens
in `Confirmed` (the state IS persisted; the v1 module did this
correctly).  The `.lrp.json` storage round-trip in PR #361's
`vtkMRMLBezierSurfaceStorageNode` handles this transparently — the
existing `state` field carries one more enum value.

### Why `Confirmed`, not `Locked`

Both names appear in the PR #369 review comment.  `Confirmed` wins
for three reasons:

- The user intent the state captures is *commitment to the resection
  plan*, not *prevention of accidental edits*.  `Confirmed` reads
  the way the surgeon thinks about it.
- `Locked` over-specifies the implementation: it suggests the lock
  could be released without changing the plan.  `Confirmed` reads
  as "the plan is set; click here to revise it" — which is the
  intended UX.
- `Locked` collides with existing Slicer-core node concepts
  (`SetLocked`, `LockedOn`, etc.) that have a different semantic
  (markups-anti-tampering); avoiding the name avoids reader
  confusion.

### Why the round-trip transition (Confirmed → Planning), not "lock forever"

The PR #369 review comment is explicit: *"it has a way back to
resection modification"*.  This is the clinically realistic case —
plans get reviewed by colleagues, get adjusted, get re-confirmed.

Architectural consequence: the read-only-after-Planning contract
from [ADR-0014][adr-0014] §4 stays unchanged — init data is still
audit-only — but **`Planning ↔ Confirmed` is a bidirectional
manipulation cycle** for the control polygon.  Specifically:

- `Confirmed → Planning` does NOT re-open init data for editing.
- Within `Planning`, the control polygon stays editable.
- `Confirmed → Planning → Confirmed` is the expected user gesture
  for "I want to tweak the surface and re-finalise".

### Why a new Representation, not a mode flag on `BezierPlanningRepresentation`

Two reasons:

- The Pipeline-dispatch convention from [ADR-0013][adr-0013] §4 +
  §6 is *one Representation per `(state, initMode)` tuple*.  A
  mode flag inside `BezierPlanningRepresentation` would smear two
  concepts into one class — exactly the legacy pattern the
  Pipeline/Representation split set out to avoid.
- The `Confirmed` Representation's render-pipeline is genuinely
  different: different shader (parenchyma trim vs grid overlay),
  different widget binding (none vs the `vtkLiverBezierWidget`),
  different actor count.  Sibling classes capture this divergence
  honestly.

### Why a no-`Planning → Init` rule stays

`Confirmed → Planning` does NOT compose into `Confirmed → Planning
→ Init`.  Per [ADR-0014][adr-0014] §4 and PR #350, init data becomes
audit-only at the first `Init → Planning` transition; no subsequent
state changes can revert it.  `Confirmed → Planning` only re-enables
control-polygon editing, NOT init-data editing.

The transition matrix table above is the load-bearing artifact: no
row contains a `Planning → Init` or `Confirmed → Init` cell that is
"allowed".

### Why `ConfirmedRepresentation` is the right place for the trim shader

The parenchyma-trim shader is what v1 used to remove the
out-of-parenchyma portion of the resection surface for clean
viewing.  In the v2.0.0 architecture (per [ADR-0014][adr-0014] §3),
shaders live in custom OpenGL mappers, attached to Representations.
The trim shader is one of the four mappers slated for
T2-mapper-relocation; this ADR commits the trim mapper to
`ConfirmedRepresentation` (vs `BezierPlanningRepresentation`).

The grid overlay shader stays on `BezierPlanningRepresentation`.
Both mappers ultimately share a common base
(`vtkOpenGLBezierResectionPolyDataMapper`) but expose different
uniforms.  The Representation owns which uniforms are bound.

## Consequences

**Positive:**

- The v1 "clean view" UX surfaces in v2.0.0.  Plans are reviewable
  without the control-polygon visuals occluding the surface.
- The `Confirmed` state is a first-class persistence-aware state —
  scene save / reload preserves it.
- The Pipeline dispatch grows by one row; no architectural surface
  changes.  Adding new states later (e.g., `Approved` as a peer of
  `Confirmed` with co-surgeon sign-off semantics) is a small
  extension.
- Composes cleanly with [ADR-0018][adr-0018]'s NURBS sibling work:
  `Confirmed` state applies to both Bezier and NURBS representations;
  the Pipeline + Representation taxonomy is orthogonal to the
  state-machine axis.

**Negative:**

- The 2-state contract in [ADR-0014][adr-0014] §4 ages out — code
  reviewers must read this ADR alongside ADR-0014 to track the
  current state machine.  Mitigated by the inline amendment block
  at the top of [ADR-0014][adr-0014] (landed by this PR).
- The trim shader is in `LiverMarkups/VTKWidgets/` and not yet
  relocated.  `ConfirmedRepresentation` implementation IS BLOCKED
  on T2-mapper-relocation; the implementation PR (queued after
  this ADR + T2-mapper-relocation merge) lands the
  `ConfirmedRepresentation` class but its render path is a no-op
  until the trim mapper relocates.
- `.lrp.json` v1/v2 forward-compatibility relies on readers
  defaulting unknown `state` values to `"Planning"`.  The current
  storage node (PR #361 + #367) does not do this explicitly; the
  enabler PR adds the fall-through.  Until then, a v3-authored
  scene with `state = "Confirmed"` opens in older readers as a
  state-load error (acceptable for an unreleased feature).

## Rollout plan

1. **DOC PR — this ADR + state-machine diagram + ADR-0014 amendment**
   (this PR):
   - New `Docs/adr/0019-resection-state-machine.md`.
   - New `Docs/architecture/resection-state-machine.md` — Mermaid
     `stateDiagram-v2` showing the three states + transitions +
     forbidden arrows + per-state contract.
   - Light amendment to [ADR-0014][adr-0014] §4 (read-only
     audit data + 2-state → 3-state extension).

2. **ENH PR — Confirmed-state implementation** (separate PR, blocked
   on T2-mapper-relocation):
   - `vtkMRMLBezierSurfaceNode::ResectionState::Confirmed = 2`.
   - Per-setter guards updated:
     `Planning → Confirmed` allowed; `Confirmed → Planning`
     allowed; `Confirmed → Init` forbidden.
   - `ConfirmedRepresentation` Python class under
     `LiverResections/LiverResectionsLib/Representations/`.
   - Pipeline dispatch table updated.
   - `.lrp.json` reader gains the forward-compatible
     unknown-state fallback to `"Planning"`.
   - Characterisation tests pin the transition matrix.

3. **T2-mapper-relocation** (separate ENH PR, also queued):
   - Relocates the parenchyma-trim mapper from
     `LiverMarkups/VTKWidgets/` into `LiverResections/VTKWidgets/`.
   - `ConfirmedRepresentation` wires the trim mapper into its
     actor + sets the uniform feeds from the display node.

The Confirmed-state implementation lands on top of
T2-mapper-relocation; if T2-mapper-relocation slips, the Confirmed
state can land WITHOUT a working trim shader (the
Representation still hides the widget and disables the grid
overlay; the trim shader's absence just means the cut-away view
isn't there yet).

## Out of scope for this ADR

- Approval workflow (multi-surgeon sign-off).  Possible future
  state above `Confirmed` (e.g., `Approved`); not in v2.0.0.
- Undo / redo across the state machine.  The transition matrix is
  Markovian — each state change is the user's deliberate action;
  no automatic backstack.  Slicer-core's MRML undo would replay
  state changes if enabled, which is acceptable.
- UI affordance for the state transitions (button placement,
  modal-vs-inline confirmation, etc.) — covered by ADR-0009 (UX
  + design discipline); the state-machine diagram in this ADR
  is the C++/MRML-side contract, not the UX flow.

## Cross-references

- [ADR-0001][adr-0001] — three-node assembly that `State` is a field of.
- [ADR-0013][adr-0013] §4 + §6 — Pipeline dispatch contract;
  `(Confirmed, *)` becomes a new row.
- [ADR-0014][adr-0014] §4 — read-only-after-Planning audit-data rule;
  unchanged in substance, amended to note 3-state extension.
- [ADR-0018][adr-0018] §3 — sibling-Pipeline pattern for the future
  NURBS extension; `ConfirmedRepresentation` is per-Pipeline
  (Bezier today; NURBS sibling at v2.1) for the same reasons.

## References

- PR #369 review comment by RafaelPalomar (2026-05-18) — the
  feedback this ADR captures.
- v1 `vtkMRMLLiverResectionNode::ResectionState` enum
  (`Initialization` / `Deformation` / `Completed`) — the legacy
  3-state machine this ADR restores under v2.0.0 naming.
