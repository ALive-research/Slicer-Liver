# Resection state machine — `Init` → `Planning` ↔ `Confirmed`

Reference companion to [ADR-0019][adr-0019].  Shows the
3-state automaton on `vtkMRMLBezierSurfaceNode::ResectionState` and
the per-state contract for control-polygon visibility, widget
interaction, surface rendering, and init-data mutability.

[adr-0019]: ../adr/0019-resection-state-machine.md
[adr-0014]: ../adr/0014-livermarkups-dissolution.md

## State diagram

```{mermaid}
stateDiagram-v2
    direction LR

    [*] --> Init : node created

    Init --> Planning : surgeon commits init data<br/>(irreversible per ADR-0014 §4)

    Planning --> Confirmed : surgeon confirms plan
    Confirmed --> Planning : surgeon revises plan

    Init --> Init : edit slicing-plane /<br/>distance-spheroid init points
    Planning --> Planning : edit control polygon
    Confirmed --> Confirmed : view-only (no edits)

    note right of Init
        Init data editable.
        Control polygon absent.
        Init-mode-specific Representation
        (SlicingPlane | DistanceSpheroid).
    end note

    note right of Planning
        Control polygon visible (M×N grid).
        vtkLiverBezierWidget enabled
        (left-drag, right-drag-ring,
         right-click context).
        Grid-overlay shader on.
        Init data read-only audit.
    end note

    note left of Confirmed
        Control polygon hidden.
        Widget disabled.
        Parenchyma-trim shader on.
        Grid overlay off.
        Init data read-only audit.
    end note
```

## Forbidden transitions (rejected with `vtkWarningMacro`)

```{mermaid}
stateDiagram-v2
    direction LR

    Planning --> Init : ❌ rejected<br/>(ADR-0014 §4: no Planning → Init)
    Confirmed --> Init : ❌ rejected<br/>(audit data permanent)

    note right of Planning
        Setter on
        vtkMRMLBezierSurfaceNode::SetState
        emits vtkWarningMacro and
        returns without Modified()
        per PR #350 precedent.
    end note
```

## Per-state contract — full table

| Field                                   | `Init`                  | `Planning`              | `Confirmed`             |
|-----------------------------------------|-------------------------|-------------------------|-------------------------|
| **Active Representation**               | init-mode-specific      | `BezierPlanningRepresentation` | `ConfirmedRepresentation` |
| Control polygon visible                 | no                      | **yes** (M×N grid)      | no                      |
| `vtkLiverBezierWidget` enabled          | no                      | **yes**                 | no                      |
| Init markers visible                    | **yes** (SlicingPlane: 2 markers; DistanceSpheroid: N markers) | no | no |
| Init-mode geometry visible              | **yes** (plane or spheroid) | no                  | no                      |
| Bezier surface visible                  | no                      | **yes** (full extent)   | **yes** (trimmed to liver parenchyma) |
| Grid-overlay shader                     | n/a                     | **on**                  | off                     |
| Parenchyma-trim shader                  | n/a                     | off                     | **on**                  |
| Init data mutable (`SetSlicingPlaneOrigin`, `SetDistanceSpheroidInitPoint`, …) | **yes** | no (rejected) | no (rejected) |
| Control-grid mutable (`SetControlGrid`, `SetControlGridPoint`) | n/a (not yet fitted) | **yes** | no (rejected) |

## Allowed transitions — full table

| From → To       | Init                    | Planning                | Confirmed               |
|-----------------|-------------------------|-------------------------|-------------------------|
| **Init →**      | self                    | **allowed (one-way)**   | forbidden               |
| **Planning →**  | forbidden               | self                    | **allowed**             |
| **Confirmed →** | forbidden               | **allowed (round-trip)** | self                    |

## Sequence: typical surgeon workflow

```{mermaid}
sequenceDiagram
    actor Surgeon
    participant Node as vtkMRMLBezierSurfaceNode
    participant Pipeline as LiverBezierSurfacePipeline
    participant Init as SlicingPlaneInitRepresentation
    participant Planning as BezierPlanningRepresentation
    participant Confirmed as ConfirmedRepresentation

    Note over Node: state = Init
    Surgeon->>Node: place init points
    Surgeon->>Pipeline: (Init, SlicingPlane) dispatch
    Pipeline->>Init: render markers + plane

    Surgeon->>Node: SetState(Planning)
    Note over Node: state = Planning;<br/>init data now read-only
    Pipeline->>Planning: render control polygon + surface

    loop control-polygon iteration
        Surgeon->>Node: SetControlGridPoint(i, j, x, y, z)
        Pipeline->>Planning: re-render
    end

    Surgeon->>Node: SetState(Confirmed)
    Note over Node: state = Confirmed
    Pipeline->>Confirmed: render trimmed surface;<br/>hide widget + control polygon

    Note over Surgeon: plan review

    alt surgeon revises
        Surgeon->>Node: SetState(Planning)
        Pipeline->>Planning: re-render control polygon + surface
    else surgeon exports plan
        Surgeon->>Node: storage→WriteData(.lrp.json)
        Note over Node: state = Confirmed persisted
    end
```

## Notes

- All three states are **first-class persisted state** — the
  `.lrp.json` v2 schema's `state` field carries `"Init"`,
  `"Planning"`, or `"Confirmed"`.  Forward-compatibility: older
  readers that don't recognise `"Confirmed"` fall back to
  `"Planning"`.
- The state machine is **per-resection** — multiple
  `vtkMRMLBezierSurfaceNode` instances in the same scene can each
  be in different states.  Useful for multi-resection treatment
  planning where one plan is reviewed (Confirmed) while another is
  being edited (Planning).
- The `Confirmed` state is **NOT terminal**.  Round-trip back to
  `Planning` is the expected user gesture for "I want to tweak this".
- The state machine is **orthogonal to** the
  [ADR-0018][adr-0018] §3 representation kind
  (Bezier vs NURBS).  A v2.1 NURBS resection has the same three
  states; the per-state contract above is identical modulo the
  surface representation.

[adr-0018]: ../adr/0018-nurbs-extension-surface.md

## Out of scope of this diagram

- The UI affordance for state transitions (button placement, modal
  confirmation, undo handling) — covered by ADR-0009 (UX +
  design discipline).
- Multi-surgeon approval workflow (`Approved` state above
  `Confirmed`) — out of v2.0.0 scope per [ADR-0019][adr-0019]'s
  "Out of scope".
- Per-setter rejection mechanics (which mutators emit warnings;
  exact warning text) — covered in [ADR-0014][adr-0014] §4 +
  PR #350's implementation.
