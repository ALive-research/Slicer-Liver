# 04 — Save / load sequence flows

Three flows matter:

1. **Save scene** — File → Save Scene saves `.mrml` plus one
   `.lrp.json` per plan.
2. **Save plan only** — File → Save (a specific plan) writes one
   `.lrp.json`.
3. **Load `.lrp.json`** standalone — opening a `.lrp.json` instantiates
   plan + surface nodes (and their display node) in the current
   scene.

## Flow 1 — Save scene

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Slicer as Slicer (scene save)
    participant Scene as vtkMRMLScene
    participant Plan as vtkMRMLResectionPlanNode
    participant Storage as vtkMRMLResectionPlanStorageNode
    participant Surface as vtkMRMLAbstractParametricSurfaceNode

    User->>Slicer: File → Save Scene
    Slicer->>Scene: Write .mrml (topology + lightweight scalars)
    Note over Scene: Plan WriteXML: refs + State + OrderIndex<br/>Surface WriteXML: SurfaceType + Rows + Cols<br/>Display WriteXML: visibility, colors, grid

    Slicer->>Scene: Iterate storable nodes
    Scene->>Plan: GetStorageNode()
    Plan-->>Scene: ResectionPlanStorageNode

    Slicer->>Storage: WriteData(Plan)
    Storage->>Plan: read plan fields (margins, name, etc.)
    Storage->>Plan: GetNodeReference(geometry) → Surface
    Storage->>Surface: read full surface state<br/>(controlGrid, initMode, init points, ...)
    Storage->>Storage: emit Plan-A.lrp.json

    Slicer->>Scene: Iterate next storable (territories, ...)
    Note over Slicer: Surface is NOT iterated — non-storable
```

## Flow 2 — Save single plan

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Slicer
    participant Storage as ResectionPlanStorageNode
    participant Plan
    participant Surface

    User->>Slicer: File → Save (Plan-A)
    Slicer->>Storage: SetFileName(Plan-A.lrp.json)
    Slicer->>Storage: WriteData(Plan)
    Storage->>Plan: read plan fields
    Storage->>Plan: GetNodeReference(geometry) → Surface
    Storage->>Surface: read full surface state
    Storage->>Storage: emit Plan-A.lrp.json
```

The single-plan save is the inner loop of the scene save — same code
path, just invoked directly.

## Flow 3 — Load standalone .lrp.json

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Slicer
    participant Storage as ResectionPlanStorageNode
    participant Scene as vtkMRMLScene
    participant Plan as new ResectionPlanNode
    participant Surface as new ParametricSurfaceNode (Bezier or NURBS)

    User->>Slicer: File → Open Plan-A.lrp.json
    Slicer->>Storage: SetFileName(Plan-A.lrp.json)
    Slicer->>Storage: ReadData
    Storage->>Storage: parse JSON, read surface.type
    Storage->>Scene: instantiate Plan node
    Storage->>Plan: populate plan fields

    alt surface.type == "Bezier"
        Storage->>Scene: instantiate BezierSurfaceNode
    else surface.type == "NURBS"
        Storage->>Scene: instantiate NurbsSurfaceNode
    end
    Storage->>Surface: populate surface state (controlGrid, ...)
    Storage->>Plan: SetNodeReference(geometry, Surface)
    Storage->>Plan: CreateDefaultDisplayNodes() on Surface
```

Scene reload (loading `.mrml` first, then `.lrp.json` files) follows
flow 3 inside the per-plan loop, with the additional context that
`.mrml` instantiation has already created the Plan + Surface nodes
with lightweight scalars; the storage step then overwrites/populates
the heavy fields.

## Failure modes

| Scenario | Behaviour |
|---|---|
| `.lrp.json` missing at scene load | Plan + Surface exist with WriteXML scalars only; control grid is zero-default; surgeon sees degraded but non-crashing plan |
| `.lrp.json` schemaVersion outside `[2, 2]` | Reader rejects with `vtkErrorMacro`; plan is not populated |
| `.lrp.json` has `surface.type = "NURBS"` but NURBS module not loaded | Reader rejects; explicit error pointing to v2.1 NURBS module |
| Plan node exists but `geometry` ref is null at save time | Storage emits warning, writes plan-only `.lrp.json` (no `surface` block) |
| Surface exists in scene without a plan referencing it | Not saved (non-storable). Lost on scene reload |
