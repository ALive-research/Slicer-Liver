# 02 — Node-reference graph in scene

Shows how the nodes are wired together at runtime via standard
`SetAndObserveNodeReferenceID` roles. The key principle: the resection
plan **references** the surface (polymorphic), but does **not**
reference territories or volumetry partitions (no semantic link beyond
visual co-existence in the scene).

```mermaid
graph LR
    subgraph SCENE[vtkMRMLScene]
        direction TB

        Plan["vtkMRMLResectionPlanNode<br/>(Plan-A)"]
        Surface["vtkMRMLBezierSurfaceNode<br/>(or NurbsSurfaceNode)"]
        SurfaceDisp["vtkMRMLParametricSurfaceDisplayNode<br/>(shared, concrete)"]
        TargetOrgan["vtkMRMLModelNode<br/>(liver parenchyma)"]

        PlanStorage["vtkMRMLResectionPlanStorageNode<br/>→ Plan-A.lrp.json"]

        subgraph INDEPENDENT[Scene-level — independent of plan]
            direction TB
            Territories["vtkMRMLStdCouinaudTerritoriesNode<br/>(or CustomTerritoriesNode)<br/>method wrapper"]
            CanonicalSeg["vtkMRMLSegmentationNode<br/>(canonical, Stage 2 output)<br/>segment masks"]
            Partitions["vtkMRMLLiverVolumetryPartitionNode<br/>(v2.1, deferred)"]
            StageState["Scene singleton<br/>(stage selection attribute)"]

            Territories -- segments --> CanonicalSeg
        end

        Plan -- geometry --> Surface
        Surface -- standard display ref --> SurfaceDisp
        Surface -- TargetOrganModelNodeID --> TargetOrgan
        Plan -- standard storage ref --> PlanStorage
    end

    style Plan fill:#d4f4d4,color:#000
    style Surface fill:#d4e8f4,color:#000
    style SurfaceDisp fill:#d4e8f4,color:#000
    style PlanStorage fill:#fff2cc,color:#000
    style INDEPENDENT fill:#f4f4f4,color:#000
    style Territories fill:#d4f4d4,color:#000
    style CanonicalSeg fill:#d4e8f4,color:#000
    style Partitions fill:#ffe0d4,color:#000
    style StageState fill:#ffe0d4,color:#000
```

Note: the Territories node ↔ Segmentation pair mirrors the Plan ↔
Surface pair (same green wrapper / blue carrier colouring). Both pairs
are instances of the wrapper-vs-carrier pattern articulated in
[document 06](06-pattern-and-audit.md).

## What references what

| Source | Role | Target | Slicer mechanism |
|---|---|---|---|
| `ResectionPlanNode` | `geometry` | `AbstractParametricSurfaceNode` | new node-reference role |
| `ResectionPlanNode` | storage | `ResectionPlanStorageNode` | standard `SetAndObserveStorageNodeID` |
| `AbstractParametricSurfaceNode` | display | `ParametricSurfaceDisplayNode` (shared by all subclasses) | standard `SetAndObserveDisplayNodeID` |
| `AbstractParametricSurfaceNode` | `TargetOrganModelNodeID` | `vtkMRMLModelNode` | existing on the Bezier node today |

## What does **not** reference what

- Plan ⇏ Territories. No reference role. **Reason**: only visual
  co-existence in the surgeon's view; no computational coupling.
- Plan ⇏ Volumetry partitions. Same reason; deferred to v2.1.
- Plan ⇏ Stage selection. UI state belongs to a scene-singleton, not
  to any specific plan.

## Multiple plans in scene

Multiple `ResectionPlanNode` instances coexist. Each owns its own
surface (one-to-one) and its own storage. The territories /
partitions / stage state are shared scene-level state visible to all
plans. Each surface has its own display node — multiple instances of
the **same shared class** `vtkMRMLParametricSurfaceDisplayNode`.

```mermaid
graph LR
    PlanA[Plan-A] --> SurfA[Surface-A]
    PlanB[Plan-B] --> SurfB[Surface-B]
    PlanC[Plan-C] --> SurfC[Surface-C]

    SurfA --> DispA[Display-A<br/>ParametricSurfaceDisplayNode]
    SurfB --> DispB[Display-B<br/>ParametricSurfaceDisplayNode]
    SurfC --> DispC[Display-C<br/>ParametricSurfaceDisplayNode]

    Territories[Territories<br/>scene-singleton in practice]

    PlanA -.no ref.- Territories
    PlanB -.no ref.- Territories
    PlanC -.no ref.- Territories

    style Territories fill:#ffe0d4,color:#000
    style PlanA fill:#d4f4d4,color:#000
    style PlanB fill:#d4f4d4,color:#000
    style PlanC fill:#d4f4d4,color:#000
    style DispA fill:#d4e8f4,color:#000
    style DispB fill:#d4e8f4,color:#000
    style DispC fill:#d4e8f4,color:#000
```
