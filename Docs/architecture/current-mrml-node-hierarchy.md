# Slicer-Liver MRML node hierarchy — current state (2026-05-13)

Descriptive snapshot of the MRML class graph for the `LiverResections` and
`LiverMarkups` modules as it exists today on `preview`. This file documents
*what is*, not what should be — see [`adr/0001-resection-three-node-assembly.md`](../adr/0001-resection-three-node-assembly.md)
for the historical rationale behind the current shape.

```mermaid
classDiagram
    %% =======================================================
    %% Slicer core base classes (external — for orientation)
    %% =======================================================
    class vtkMRMLNode
    class vtkMRMLStorableNode
    class vtkMRMLTransformableNode
    class vtkMRMLDisplayableNode
    class vtkMRMLMarkupsNode
    class vtkMRMLMarkupsLineNode
    class vtkMRMLMarkupsDisplayNode
    class vtkMRMLStorageNode
    class vtkMRMLMarkupsFiducialStorageNode
    class vtkMRMLAbstractSliceViewDisplayableManager
    <<abstract>> vtkMRMLNode
    <<abstract>> vtkMRMLStorableNode
    <<abstract>> vtkMRMLTransformableNode
    <<abstract>> vtkMRMLDisplayableNode
    <<abstract>> vtkMRMLMarkupsNode
    <<abstract>> vtkMRMLMarkupsLineNode
    <<abstract>> vtkMRMLMarkupsDisplayNode
    <<abstract>> vtkMRMLStorageNode
    <<abstract>> vtkMRMLMarkupsFiducialStorageNode
    <<abstract>> vtkMRMLAbstractSliceViewDisplayableManager

    vtkMRMLNode <|-- vtkMRMLStorableNode
    vtkMRMLStorableNode <|-- vtkMRMLTransformableNode
    vtkMRMLTransformableNode <|-- vtkMRMLDisplayableNode
    vtkMRMLDisplayableNode <|-- vtkMRMLMarkupsNode
    vtkMRMLMarkupsNode <|-- vtkMRMLMarkupsLineNode
    vtkMRMLNode <|-- vtkMRMLStorageNode
    vtkMRMLStorageNode <|-- vtkMRMLMarkupsFiducialStorageNode

    %% =======================================================
    %% LiverResections.MRML — content node + storage
    %% =======================================================
    class vtkMRMLLiverResectionNode {
        +State : enum
        +InitMode : enum
        +ResectionMargin, UncertaintyMargin : double
        +Colors, Grid, Opacity, ...
        +SetTargetOrganModelNode(weak)
        +SetDistanceMapVolumeNode(weak)
        +SetVascularSegmentsVolumeNode(weak)
        +SetBezierSurfaceNode(weak)
        +SetInitializationNode(weak)
    }
    class vtkMRMLLiverResectionCSVStorageNode {
        +ReadDataInternal(node)
        +WriteDataInternal(node)
    }

    vtkMRMLStorableNode <|-- vtkMRMLLiverResectionNode
    vtkMRMLMarkupsFiducialStorageNode <|-- vtkMRMLLiverResectionCSVStorageNode
    vtkMRMLLiverResectionNode "1" -- "1" vtkMRMLLiverResectionCSVStorageNode : default storage

    %% =======================================================
    %% LiverMarkups.MRML — geometry + initialization nodes
    %% =======================================================
    class vtkMRMLMarkupsBezierSurfaceNode {
        +MaximumNumberOfControlPoints = 16
        +RequiredNumberOfControlPoints = 16
    }
    class vtkMRMLMarkupsBezierSurfaceDisplayNode {
        +ResectionColor, MarginColor
        +GridDivisions, Opacity
    }
    class vtkMRMLMarkupsSlicingContourNode
    class vtkMRMLMarkupsSlicingContourDisplayNode
    class vtkMRMLMarkupsDistanceContourNode
    class vtkMRMLMarkupsDistanceContourDisplayNode

    vtkMRMLMarkupsNode <|-- vtkMRMLMarkupsBezierSurfaceNode
    vtkMRMLMarkupsLineNode <|-- vtkMRMLMarkupsSlicingContourNode
    vtkMRMLMarkupsLineNode <|-- vtkMRMLMarkupsDistanceContourNode
    vtkMRMLMarkupsDisplayNode <|-- vtkMRMLMarkupsBezierSurfaceDisplayNode
    vtkMRMLMarkupsDisplayNode <|-- vtkMRMLMarkupsSlicingContourDisplayNode
    vtkMRMLMarkupsDisplayNode <|-- vtkMRMLMarkupsDistanceContourDisplayNode

    vtkMRMLMarkupsBezierSurfaceNode "1" -- "1" vtkMRMLMarkupsBezierSurfaceDisplayNode
    vtkMRMLMarkupsSlicingContourNode "1" -- "1" vtkMRMLMarkupsSlicingContourDisplayNode
    vtkMRMLMarkupsDistanceContourNode "1" -- "1" vtkMRMLMarkupsDistanceContourDisplayNode

    %% =======================================================
    %% The three-node resection assembly (ADR-0001)
    %% =======================================================
    vtkMRMLLiverResectionNode ..> vtkMRMLMarkupsBezierSurfaceNode : weak ref (geometry)
    vtkMRMLLiverResectionNode ..> vtkMRMLMarkupsSlicingContourNode : weak ref (init, mode A)
    vtkMRMLLiverResectionNode ..> vtkMRMLMarkupsDistanceContourNode : weak ref (init, mode B)
    vtkMRMLLiverResectionCSVStorageNode ..> vtkMRMLMarkupsBezierSurfaceNode : delegates I/O

    %% =======================================================
    %% LiverResections.MRMLDM — slice-view rendering
    %% =======================================================
    class vtkMRMLLiverResectionsDisplayableManager2D
    vtkMRMLAbstractSliceViewDisplayableManager <|-- vtkMRMLLiverResectionsDisplayableManager2D
    vtkMRMLLiverResectionsDisplayableManager2D ..> vtkMRMLMarkupsBezierSurfaceNode : reads, renders 2D cross-sections

    note for vtkMRMLLiverResectionNode "Storable: conventional save target. Owns metadata, state, and weak refs to geometry/init/source-data nodes."
    note for vtkMRMLMarkupsBezierSurfaceNode "MarkupsNode: reuses Slicer widget pipeline. Holds the 16 Bezier control points."
```

## Reading guide

- **Solid arrows** (`<|--`): UML inheritance — child class points to its
  parent. Read *"vtkMRMLStorableNode is a vtkMRMLNode"*.
- **Dashed arrows** (`..>`): associations / weak references that do not
  imply ownership. The three-node resection assembly is held together by
  these.
- **`1 -- 1`** lines: composition. The default node pair created together
  (e.g. a content node and its default storage node).
- Top-level abstract classes (`<<abstract>>`) come from Slicer core and
  are included only as orientation; they are not maintained in
  Slicer-Liver.

## Module grouping (read top-to-bottom)

1. **Slicer core base classes** — external; for reference only.
2. **LiverResections.MRML** — the resection content node and its storage
   node.
3. **LiverMarkups.MRML** — the geometry node (BezierSurface) and the two
   initialization-mode nodes (Slicing / Distance contour), each with
   their display nodes.
4. **Three-node resection assembly** — the cross-package associations
   that make a single resection (Initialization + Geometry + Content);
   see [ADR-0001](../adr/0001-resection-three-node-assembly.md).
5. **LiverResections.MRMLDM** — the slice-view displayable manager that
   reads the geometry node and renders 2D cross-sections.
