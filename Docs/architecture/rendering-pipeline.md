# Rendering pipeline — LayerDM dispatch through to shader uniforms

Reference companion to [ADR-0013][adr-0013] §5 + [ADR-0018][adr-0018].
Shows the data flow from the moment a `vtkMRMLBezierSurfaceNode`
lands in the scene to the point a custom OpenGL mapper writes
framebuffer pixels.  Two views: a **class diagram** of the C++ /
Python types involved + a **sequence diagram** of the runtime
dispatch.

[adr-0013]: ../adr/0013-layerdm-pipeline-pattern.md
[adr-0014]: ../adr/0014-livermarkups-dissolution.md
[adr-0018]: ../adr/0018-nurbs-extension-surface.md

## Class structure

```mermaid
classDiagram
    direction TB

    class vtkMRMLScene {
        <<Slicer-core>>
    }
    class vtkMRMLBezierSurfaceNode {
        <<v2.0.0 data node>>
    }
    class vtkMRMLBezierSurfaceDisplayNode {
        <<v2.0.0 display node>>
        +GridVisibility / Divisions / Thickness
        +ResectionGridColor
        +ResectionMargin / UncertaintyMargin
        +TerminologyEntry
    }
    class vtkMRMLLayerDisplayableManager {
        <<upstream LayerDM>>
        Observes scene
        Per-view singleton
    }
    class vtkMRMLLayerDMPipelineFactory {
        <<upstream LayerDM>>
        AddPipelineCreator()
        CreatePipeline(viewNode, displayNode)
    }
    class vtkMRMLLayerDMPipelineScriptedCreator {
        <<upstream LayerDM>>
        SetPythonCallback(tryCreate)
    }

    class LiverBezierSurfacePipeline {
        <<v2.0.0 — Python>>
        SetDisplayNode()
        UpdatePipeline()
        OnRendererAdded()
        cleanup()
        Dispatch: (state, initMode) → Representation
    }

    class BezierPlanningRepresentation {
        <<v2.0.0 — Python>>
        Active in (Planning, *)
    }
    class SlicingPlaneInitRepresentation {
        <<v2.0.0 — Python>>
        Active in (Init, SlicingPlane)
    }
    class DistanceSpheroidInitRepresentation {
        <<v2.0.0 — Python>>
        Active in (Init, DistanceSpheroid)
    }
    class ConfirmedRepresentation {
        <<ADR-0019 Proposed>>
        Active in (Confirmed, *)
    }

    class vtkOpenGLBezierResectionPolyDataMapper {
        <<post T2-mapper-relocation>>
        Bezier surface render
        + grid-overlay shader (Planning)
        + parenchyma-trim shader (Confirmed)
        Both gated by uniform feeds
    }
    class vtkOpenGLDistanceContourPolyDataMapper {
        <<post T2-mapper-relocation>>
        Distance-map contour shader
    }
    class vtkOpenGLResectogramPolyDataMapper {
        <<post T2-mapper-relocation;<br/>T3 wire-up>>
        Resectogram texture path
    }
    class FragmentShader {
        <<GLSL>>
        Bernstein basis evaluation
        Grid overlay: tan(uv*π*divs) > thickness
        Margin / uncertainty colour stops
        Parenchyma trim by distance
    }

    vtkMRMLScene "1" --> "*" vtkMRMLBezierSurfaceNode : contains
    vtkMRMLBezierSurfaceNode "1" --> "1" vtkMRMLBezierSurfaceDisplayNode : SetAndObserveDisplayNodeID

    vtkMRMLScene "1" --> "1" vtkMRMLLayerDisplayableManager : observed by (per view)
    vtkMRMLLayerDisplayableManager ..> vtkMRMLLayerDMPipelineFactory : dispatches
    vtkMRMLLayerDMPipelineFactory ..> vtkMRMLLayerDMPipelineScriptedCreator : per-creator
    vtkMRMLLayerDMPipelineScriptedCreator ..> LiverBezierSurfacePipeline : Python lambda<br/>(tryCreate)

    LiverBezierSurfacePipeline ..> BezierPlanningRepresentation : Planning
    LiverBezierSurfacePipeline ..> SlicingPlaneInitRepresentation : Init / SlicingPlane
    LiverBezierSurfacePipeline ..> DistanceSpheroidInitRepresentation : Init / DistanceSpheroid
    LiverBezierSurfacePipeline ..> ConfirmedRepresentation : Confirmed<br/>(ADR-0019)

    BezierPlanningRepresentation ..> vtkOpenGLBezierResectionPolyDataMapper : surface + grid uniforms
    ConfirmedRepresentation ..> vtkOpenGLBezierResectionPolyDataMapper : trim uniforms on / grid off
    BezierPlanningRepresentation ..> vtkOpenGLDistanceContourPolyDataMapper : distance contours

    vtkOpenGLBezierResectionPolyDataMapper ..> FragmentShader : GLSL uniforms
    vtkOpenGLDistanceContourPolyDataMapper ..> FragmentShader : GLSL uniforms
    vtkOpenGLResectogramPolyDataMapper ..> FragmentShader : GLSL uniforms

    vtkMRMLBezierSurfaceDisplayNode ..> vtkOpenGLBezierResectionPolyDataMapper : uniform feed
```

The class diagram shows:

- **Scene → display node → Pipeline**: the scene owns data + display
  nodes; `vtkMRMLLayerDisplayableManager` observes scene events and
  uses the factory to instantiate one Pipeline per `(view,
  display node)` pair.
- **Pipeline → Representation**: one Pipeline owns four
  Representations (v2.0.0 + ADR-0019); dispatch table on
  `(ResectionState, InitializationMode)` picks one active at a time.
- **Representation → custom OpenGL mapper**: each Representation
  owns a (small) set of mappers; the mappers live under
  `LiverResections/VTKWidgets/` post T2-mapper-relocation.
- **Mapper → fragment shader**: each mapper feeds uniforms to a
  GLSL fragment shader that does the actual pixel work.  The
  display node's fields (`GridVisibility`, `GridDivisions`,
  `ResectionMargin`, …) wire into the uniform binds.

## Sequence

```mermaid
sequenceDiagram
    participant User
    participant Scene as vtkMRMLScene
    participant Logic as vtkSlicerLiverResectionsLogic
    participant DM as vtkMRMLLayerDisplayableManager<br/>(upstream)
    participant Factory as vtkMRMLLayerDMPipelineFactory<br/>(upstream)
    participant Pipeline as LiverBezierSurfacePipeline
    participant Rep as BezierPlanningRepresentation
    participant Mapper as vtkOpenGLBezierResectionPolyDataMapper<br/>(post T2-mapper-relocation)
    participant GPU as GLSL fragment shader

    Note over User,Scene: User opens .lrp.json OR adds a resection via toolbar
    User->>Scene: Add vtkMRMLBezierSurfaceNode
    Scene->>Logic: NodeAddedEvent
    Note over Logic,DM: Logic invoked via RegisterNodes() per ADR-0013 §5 call 1
    Scene->>DM: NodeAddedEvent (data + display nodes)

    Note over DM,Factory: ADR-0013 §5 call 2: DM observes scene<br/>and dispatches per display-node class
    DM->>Factory: CreatePipeline(viewNode, displayNode)
    Factory->>Factory: lookup creator for vtkMRMLBezierSurfaceDisplayNode
    Note over Factory: ADR-0013 §5 call 3:<br/>creator registered via AddPipelineCreator
    Factory->>Pipeline: instantiate

    Pipeline->>Pipeline: SetDisplayNode(displayNode)
    Pipeline->>Pipeline: GetDisplayableNode() → vtkMRMLBezierSurfaceNode
    Pipeline->>Pipeline: observe (state, initMode) modifications

    Note over Pipeline,Rep: Dispatch table per ADR-0013 §4:<br/>(ResectionState, InitializationMode) → Representation
    Pipeline->>Rep: select by (Planning, *)
    Rep->>Mapper: SetInputData(controlGridPolyData)
    Rep->>Mapper: SetUniform(GridDivisions, GridThickness, ResectionGridColor)
    Rep->>Mapper: SetUniform(ResectionMargin, UncertaintyMargin)

    Note over Mapper,GPU: ADR-0014 §3 — grid is a *shader feature*,<br/>not separate geometry
    Mapper->>GPU: render pass
    GPU->>GPU: evaluate Bernstein basis on parametric (u,v)
    GPU->>GPU: overlay grid: tan(uv * pi * gridDivisions) > thickness
    GPU->>GPU: trim by parenchyma distance (Confirmed-state shader)
    GPU-->>Mapper: framebuffer
```

## What lands when

| Element                                          | Status                       |
|--------------------------------------------------|------------------------------|
| `vtkMRMLBezierSurfaceNode` + display + storage   | ✓ landed (PRs #341/#348/#350/#361) |
| `vtkSlicerLiverResectionsLogic::RegisterNodes()` | ✓ landed (PR #364)            |
| `vtkMRMLLayerDisplayableManager::RegisterInDefaultViews()` | ✓ landed (PR #369) |
| `vtkMRMLLayerDMPipelineFactory::AddPipelineCreator(...)`   | ✓ landed (PR #369) |
| `LiverBezierSurfacePipeline` (lifecycle, dispatch)         | ✓ landed (PR #354 + #369) |
| `BezierPlanningRepresentation` (with generic mapper)       | ✓ landed (PR #354)  |
| `SlicingPlaneInitRepresentation`                           | ✓ landed (PR #358)  |
| `DistanceSpheroidInitRepresentation`                       | ✓ landed (PR #359)  |
| Custom OpenGL mappers (`vtkOpenGLBezierResectionPolyDataMapper`, …) | ⏳ **T2-mapper-relocation** |
| Display-node fields → mapper uniforms              | ⏳ T2-mapper-relocation |
| Fragment-shader grid overlay                       | ⏳ T2-mapper-relocation |
| Parenchyma-trim shader (Confirmed state)           | ⏳ T2-mapper-relocation + ADR-0019 |
| Resectogram texture path                           | ⏳ T3 |

## Notes

- The upstream `vtkMRMLLayerDisplayableManager` is **generic** — it
  hosts Pipelines without per-module specialisation.  Slicer-Liver
  does NOT subclass it ([ADR-0002][adr-0002] migration commitment;
  rule captured in the project's no-custom-DM memory).
- Pipeline creators are registered as **scripted Python callbacks**
  via `vtkMRMLLayerDMPipelineScriptedCreator` — see PR #369's
  `registerPipelineCreator()` for the canonical invocation.
- The dispatch axis is **display-node class** for the factory and
  **(state, initMode) for the Pipeline's internal Representation
  table**.  ADR-0018 §3 commits sibling Pipelines (not a third axis)
  for the future Bezier vs NURBS divergence.
- Today's Representations attach a **generic** `vtkPolyDataMapper`;
  the custom OpenGL mappers under `LiverMarkups/VTKWidgets/` swap
  in during **T2-mapper-relocation**.

[adr-0002]: ../adr/0002-migrate-to-slicerlayerdm.md
