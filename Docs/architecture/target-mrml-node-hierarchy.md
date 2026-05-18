# Target MRML node hierarchy — post-T2 + ADR-0018 extension surface

Reference companion to [ADR-0018][adr-0018].  Shows the post-T2
parametric-surface family (`vtkMRMLBezierSurfaceNode` trio) with the
v2.0.0 variable-size commitment + the v2.1 NURBS sibling extension
surface.

[adr-0018]: ../adr/0018-nurbs-extension-surface.md
[adr-0014]: ../adr/0014-livermarkups-dissolution.md
[adr-0015]: ../adr/0015-cpp-algorithm-library.md
[adr-0001]: ../adr/0001-resection-three-node-assembly.md

## Class hierarchy

```{mermaid}
classDiagram
    direction LR

    class vtkMRMLStorableNode {
        <<Slicer-core>>
    }
    class vtkMRMLDisplayableNode {
        <<Slicer-core>>
    }
    class vtkMRMLDisplayNode {
        <<Slicer-core>>
    }
    class vtkMRMLStorageNode {
        <<Slicer-core>>
    }

    vtkMRMLStorableNode <|-- vtkMRMLDisplayableNode

    class vtkMRMLBezierSurfaceNode {
        <<v2.0.0>>
        +int Rows = 4
        +int Cols = 4
        +double[3*Rows*Cols] ControlGrid
        +ResectionState State : Init | Planning
        +InitializationMode InitMode : SlicingPlane | DistanceSpheroid
        +double[3] SlicingPlaneOrigin
        +double[3] SlicingPlaneNormal
        +double[3] SlicingPlaneInitPoint0
        +double[3] SlicingPlaneInitPoint1
        +double[3] DistanceSpheroidCenter
        +double DistanceSpheroidRadiusX
        +double DistanceSpheroidRadiusY
        +double DistanceSpheroidRadiusZ
        +int NumberOfDistanceSpheroidInitPoints
        +double[3*N] DistanceSpheroidInitPoints
        +string TargetOrganModelNodeID
    }

    class vtkMRMLBezierSurfaceDisplayNode {
        <<v2.0.0>>
        +string TerminologyEntry
        +int GridVisibility
        +int GridDivisions
        +double GridThickness
        +double[3] ResectionGridColor
        +double ResectionMargin
        +double UncertaintyMargin
    }

    class vtkMRMLBezierSurfaceStorageNode {
        <<v2.0.0>>
        +.lrp.json schemaVersion = 2
        +legacy .lrp.fcsv read-only migration
    }

    class vtkMRMLNurbsSurfaceNode {
        <<v2.1 Proposed>>
        +int Rows
        +int Cols
        +int DegreeU
        +int DegreeV
        +double[] KnotsU
        +double[] KnotsV
        +double[Rows*Cols] Weights
        +double[3*Rows*Cols] ControlGrid
        +ResectionState State
        +InitializationMode InitMode
    }

    class vtkMRMLNurbsSurfaceDisplayNode {
        <<v2.1 Proposed>>
    }

    class vtkMRMLNurbsSurfaceStorageNode {
        <<v2.1 Proposed>>
        +.lrp.json schemaVersion = 3
    }

    vtkMRMLDisplayableNode <|-- vtkMRMLBezierSurfaceNode
    vtkMRMLDisplayableNode <|-- vtkMRMLNurbsSurfaceNode : sibling
    vtkMRMLDisplayNode <|-- vtkMRMLBezierSurfaceDisplayNode
    vtkMRMLDisplayNode <|-- vtkMRMLNurbsSurfaceDisplayNode
    vtkMRMLStorageNode <|-- vtkMRMLBezierSurfaceStorageNode
    vtkMRMLStorageNode <|-- vtkMRMLNurbsSurfaceStorageNode

    vtkMRMLBezierSurfaceNode "1" --> "1" vtkMRMLBezierSurfaceDisplayNode : display ref
    vtkMRMLBezierSurfaceNode "1" --> "1" vtkMRMLBezierSurfaceStorageNode : storage ref
    vtkMRMLNurbsSurfaceNode "1" --> "1" vtkMRMLNurbsSurfaceDisplayNode : display ref
    vtkMRMLNurbsSurfaceNode "1" --> "1" vtkMRMLNurbsSurfaceStorageNode : storage ref
```

## Notes

- **Sibling, not subclass.** Per [ADR-0018][adr-0018] §"Why a single data
  type per representation kind, not a parent class", the NURBS trio
  parallels the Bezier trio without a shared parent.  Field-level
  duplication (`Rows`, `Cols`, `ControlGrid`, `State`, `InitMode`) is
  intentional — it preserves Slicer's "peer types, no geometry-parent"
  convention (`vtkMRMLModelNode` and `vtkMRMLMarkupsNode` are
  parallel; this trio is parallel for the same reasons).
- **Default for the Bezier node is 4×4** ([ADR-0018][adr-0018] §1).  Variable
  M×N is admitted; legacy `.lrp.fcsv` files (per
  [ADR-0014][adr-0014] §5's migration path) implicitly load as 4×4.
- **Legacy `vtkMRMLLiverResection*` nodes** (the pre-rename / pre-T2
  family) are retired by **T2.7**.  They do not appear here.
- **NURBS-specific fields** (`DegreeU`, `DegreeV`, `KnotsU`, `KnotsV`,
  `Weights`) live ONLY on `vtkMRMLNurbsSurfaceNode`; the Bezier node
  has no degree field (always polynomial degree `Rows-1` × `Cols-1`)
  and no weights (uniform rational coefficients are implicit Bezier).
- The data → display node reference is the
  `SetAndObserveDisplayNodeID` standard Slicer relationship.  The
  data → storage node reference is `SetAndObserveStorageNodeID` per
  [ADR-0001][adr-0001].

## Out of scope of this diagram

- The LayerDM Pipeline + Representation taxonomy — see
  `surface-representation-taxonomy.md`.
- The render-time data flow (Pipeline → Mapper → shader) — see
  `rendering-pipeline.md`.
- The widget control-grid grouping math — see
  `control-grid-grouping.md`.
- Trimmed NURBS, subdivision surfaces — out of scope per
  [ADR-0018][adr-0018]'s "Out of scope" section.
