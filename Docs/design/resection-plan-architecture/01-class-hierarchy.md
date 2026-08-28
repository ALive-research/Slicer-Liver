# 01 — Class hierarchy

The new MRML class hierarchy splits the resection concept into three
layers (clinical / geometry / display) and introduces a polymorphic
abstract base for parametric surfaces so that Bezier and NURBS are
substitutable. The **display side stays flat**: both surface
subclasses share a single concrete `vtkMRMLParametricSurfaceDisplayNode`
(mirrors the Slicer Markups pattern where 8+ markup data subclasses
share one display class).

```mermaid
classDiagram
    direction TB

    class vtkMRMLStorableNode {
        <<Slicer-core>>
    }
    class vtkMRMLDisplayableNode {
        <<Slicer-core>>
    }
    class vtkMRMLStorageNode {
        <<Slicer-core>>
    }
    class vtkMRMLDisplayNode {
        <<Slicer-core>>
    }

    vtkMRMLStorableNode <|-- vtkMRMLDisplayableNode

    class vtkMRMLResectionPlanNode {
        <<NEW v2.0>>
        +string Name
        +double SafetyMargin
        +double RiskMargin
        +int OrderIndex
        +PlanState State : Init | Planning | Confirmed
        --node refs--
        +geometry → AbstractParametricSurfaceNode
    }

    class vtkMRMLResectionPlanStorageNode {
        <<NEW v2.0>>
        +.lrp.json schemaVersion = 2
        +legacy .lrp.fcsv read-only migration
    }

    class vtkMRMLAbstractParametricSurfaceNode {
        <<NEW abstract>>
        +unsigned int Rows
        +unsigned int Cols
        +double[3·Rows·Cols] ControlGrid
        +InitMode : SlicingPlane | DistanceSpheroid
        +SlicingPlane subordinate (origin, normal, init points)
        +DistanceSpheroid subordinate (center, radii, init points)
        +virtual GetSurfaceType() string
        +virtual EvaluateSurface(u,v) vtkPolyData
        --node refs--
        +TargetOrganModelNodeID
    }

    class vtkMRMLBezierSurfaceNode {
        <<v2.0 concrete>>
        polynomial degree = (Rows-1, Cols-1)
        weights implicit (1.0)
    }

    class vtkMRMLNurbsSurfaceNode {
        <<v2.1 concrete sibling>>
        +unsigned int DegreeU, DegreeV
        +double[] KnotsU, KnotsV
        +double[Rows·Cols] Weights
    }

    class vtkMRMLParametricSurfaceDisplayNode {
        <<NEW shared, concrete>>
        +string TerminologyEntry
        +float[3] ResectionColor
        +float[3] ResectionGridColor
        +float[3] ResectionMarginColor
        +float[3] UncertaintyMarginColor
        +bool GridVisibility, Grid3DVisibility, Grid2DVisibility
        +float GridDivisions, GridThickness
        +bool WidgetVisibility, ClipOut, InterpolatedMargins
        +bool ShowResection2D, MirrorDisplay
    }

    vtkMRMLStorableNode <|-- vtkMRMLResectionPlanNode
    vtkMRMLStorageNode  <|-- vtkMRMLResectionPlanStorageNode
    vtkMRMLDisplayableNode <|-- vtkMRMLAbstractParametricSurfaceNode
    vtkMRMLAbstractParametricSurfaceNode <|-- vtkMRMLBezierSurfaceNode
    vtkMRMLAbstractParametricSurfaceNode <|-- vtkMRMLNurbsSurfaceNode
    vtkMRMLDisplayNode <|-- vtkMRMLParametricSurfaceDisplayNode

    vtkMRMLResectionPlanNode --> vtkMRMLAbstractParametricSurfaceNode : geometry ref
    vtkMRMLBezierSurfaceNode --> vtkMRMLParametricSurfaceDisplayNode : display ref
    vtkMRMLNurbsSurfaceNode --> vtkMRMLParametricSurfaceDisplayNode : display ref
```

## Key invariants

- `vtkMRMLResectionPlanNode` is storable; its storage emits `.lrp.json`.
- `vtkMRMLAbstractParametricSurfaceNode` is **not** storable — no
  default storage node. Its bulk data is persisted by the referencing
  plan's storage.
- `vtkMRMLAbstractParametricSurfaceNode` is `vtkAbstractTypeMacro`
  (non-instantiable). Concrete subclasses use `vtkStandardNewMacro`.
- `vtkMRMLResectionPlanNode` does **not** reference territories or
  volumetry partitions — those are independent scene-level concepts
  with their own MRML nodes.
- `vtkMRMLParametricSurfaceDisplayNode` is **shared** by all concrete
  surface subclasses (one class, multiple data-side users). Mirrors
  `vtkMRMLMarkupsDisplayNode` — 8+ markup subclasses share that one
  display class. If NURBS ever needs type-specific display fields
  (knot multiplicity, weight visualisation), a `vtkMRMLNurbsSurfaceDisplayNode`
  subclass is added **at that point**, not pre-emptively.

## Why the display side stays flat

The data side abstracts because Bezier and NURBS **diverge in
geometry** (polynomial vs rational, no-knots vs knot-vectors). The
display side does **not** diverge today — every Bezier display field
applies equally to NURBS. Abstracting where there is no divergence is
ceremony without payoff. Defer the abstraction until divergence is
real, per the Slicer-core convention.

This decision aligns with the symmetric T5.2-a verdict (PR #425) for
territories: abstract *only* when polymorphic dispatch is real.

## Parallel: territories follow the same wrap pattern

The same wrapper-vs-carrier split applies on the Stage 3 side. The
territories class hierarchy that landed in PR #425 should be tightened
to wrap a canonical `vtkMRMLSegmentationNode` (which ADR-0024 §"Stage
2 publishes one canonical Segmentation" already establishes as the
data carrier).

```mermaid
classDiagram
    direction TB

    class vtkMRMLDisplayableNode {
        <<Slicer-core>>
    }

    class vtkMRMLAbstractTerritoriesNode {
        <<abstract — method wrapper>>
        +virtual GetMethod() string
        +virtual GetSegments() vtkStringArray
        +virtual GetSegmentColor(int) double[3]
        +virtual GetSCTCode(int) string
        --node refs--
        +segments → vtkMRMLSegmentationNode
    }

    class vtkMRMLStdCouinaudTerritoriesNode {
        <<Auto path>>
        +SourceImageRef vtkMRMLScalarVolumeNode
        +AIBackendIdentifier string
        +Subdivision : I_VIII | I_VIII_with_IVab
        +ComputedAt timestamp
    }

    class vtkMRMLCustomTerritoriesNode {
        <<Manual path>>
        +CenterlineRefs vtkMRMLModelNode[]
        +EndpointRefs vtkMRMLMarkupsFiducialNode[]
        +Groupings map~CenterlineId, SegmentId~
        +SegmentNames vtkStringArray
    }

    class vtkMRMLSegmentationNode {
        <<Slicer-core — data carrier>>
        segment masks
        per-segment terminology entries
        own storage: .seg.nrrd
    }

    vtkMRMLDisplayableNode <|-- vtkMRMLAbstractTerritoriesNode
    vtkMRMLAbstractTerritoriesNode <|-- vtkMRMLStdCouinaudTerritoriesNode
    vtkMRMLAbstractTerritoriesNode <|-- vtkMRMLCustomTerritoriesNode
    vtkMRMLAbstractTerritoriesNode --> vtkMRMLSegmentationNode : segments ref
```

### What changes from PR #425's territories design

| Today (PR #425) | Proposed (tightened) |
|---|---|
| `GetLabelMap()` + `GetSegmentationNode()` in interface — duality unsettled | **Drop `GetLabelMap()`** (or forward to segmentation's binary labelmap rep) |
| `+LabelMap vtkImageData` field on both concrete subclasses | **Removed** — segment masks live in the referenced `vtkMRMLSegmentationNode` |
| No typed `segments` reference role | **Add** typed `segments` node reference on the abstract base |
| Custom path centerlines + groupings on the territories node | **Unchanged** — Manual-path inputs (not segmentation data) stay on the wrapper |

This matches the resection-plan pattern: the wrapper carries
*method-specific inputs and metadata*; the wrapper does not carry the
bulk segmentation/geometry that has its own canonical Slicer node type.
