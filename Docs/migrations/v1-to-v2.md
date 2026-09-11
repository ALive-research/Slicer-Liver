# v1 to v2 migration guide

Slicer-Liver v2.0.0 is a near-total rewrite.  This note tells an existing
v1 user what carries over, what does not, and what to do about it.

:::{warning}
**Read this before upgrading if you have saved v1 resection plans.**
Legacy `.lrp.fcsv` plans **cannot be opened in v2**, and v2 ships no
converter.  Keep a working v1 installation until you have dealt with
every plan you care about.
:::

## At a glance

| | Carries over? |
| --- | --- |
| CT/MR volumes, segmentations, models (Slicer-core types) | **Yes** |
| v1 scenes (`.mrml` / `.mrb`) | **Partially** — core nodes load; all Slicer-Liver nodes are dropped |
| v1 resection plans (`.lrp.fcsv`) | **No** |
| Scripts against `vtkMRMLLiverResectionNode` | **No** — rewrite required |
| Module `LiverSegments` | **No** — renamed `VascularTerritories` |
| Module `LiverMarkups` | **No** — removed |

## What v1 carried

The v1 resection format (`.lrp.fcsv`) is a 15-column Markups-fiducial
CSV.  It stores **only the 16 Bezier control points** of the resection
surface (a 4x4 control polygon) in the LPS coordinate system.  It carries
no clinical or plan-level metadata.

## What v2 expects

The v2 plan format (`.lrp.json`, schema version 2) is rooted on the
resection **plan**, with the surface persisted as a polymorphic `surface`
block.  Beyond the control polygon, the plan carries:

- `safetyMargin` — clinical safety margin (mm).
- `riskMargin` — clinical risk margin (mm).
- `orderIndex` — zero-based position in the operative sequence.
- `state` — plan-level state machine (`Init` / `Planning` / `Confirmed`).

The reader admits **only `schemaVersion == 2`**.

## `.lrp.fcsv` files do not load in v2

:::{note}
**This section corrects an earlier version of this document**, which
described a seamless migration through
`vtkMRMLResectionPlanStorageNode::ReadFcsv`.  That path existed during v2
development and was **retired** along with the v1 markups subsystem.  It
is not in the shipped release, and the earlier text promised an upgrade
that does not happen.
:::

As shipped:

- `qSlicerLiverResectionsReader` advertises only
  `Liver resection plan (*.lrp.json)`; any other extension is rejected
  with *"Unsupported file extension"*.
- `vtkMRMLResectionPlanStorageNode` reads and writes only the v2 JSON
  schema.  Its header states outright: *legacy `.lrp.fcsv` files no
  longer load.*

There is **no converter, no batch tool, and no automatic migration.**

## What to do with your v1 plans

1. **Keep a working v1 installation.**  This is the only way to *open* a
   `.lrp.fcsv` plan.  Do not remove it until every plan you care about is
   either re-created in v2 or consciously abandoned.
2. **Decide per plan whether it is worth re-creating.**  A v1 file carries
   only 16 control points — no margins, no ordering, no state.  Most of
   what a v2 plan means was never in the file.
3. **Re-create the plan in v2.**  Stage 4's guided initialisation
   (auto-seeded handles, drag, candidate re-fit) is usually faster than
   transcribing control points, and it yields a plan with real margins and
   a distance map attached.
4. **If you must recover the exact geometry**, the control points are
   readable by hand.  The file is a plain markups fiducial CSV in **LPS**;
   v2 works in **RAS**, so negate X and Y and leave Z unchanged.  Write
   them onto a v2 carrier with the row/column setter:

   ```python
   logic = slicer.modules.liverresections.logic()
   plan = logic.CreateResectionPlan("Recovered")
   surface = plan.GetGeometryNode()          # vtkMRMLBezierSurfaceNode
   for row in range(4):
       for col in range(4):
           x, y, z = points_ras[row * 4 + col]
           surface.SetControlPoint(row, col, x, y, z)
   ```

   `SetControlPoint(row, col, x, y, z)` is the Python-wrappable entry
   point; the flat `SetControlGrid(const double*)` does not cross the
   wrap.

## Fields v1 never had

Every v2 field except the control points is **absent from v1** and
therefore **not recoverable**.  A reconstructed plan starts at these
defaults:

| Field | Default |
| --- | --- |
| `safetyMargin` | `0.0` |
| `riskMargin` | `0.0` |
| `orderIndex` | `-1` |
| `state` | `Init` |

A safety margin of 0 mm is **not** a clinical statement — it is the
neutral default for an unknown value.  **Review the margins, order, and
state before using a reconstructed plan clinically.**

## Scenes

A v1 `.mrml` or `.mrb` scene opens in v2, but **every Slicer-Liver node in
it is dropped**, because no v1 node class is registered any more.  Volumes,
segmentations and models load normally.

Practically: your imaging and your segmentations survive; your resections,
resection markups, and vascular-segment setup do not.

| v1 node class | v2 status |
| --- | --- |
| `vtkMRMLLiverResectionNode` | removed (split into plan + carrier + display nodes) |
| `vtkMRMLLiverResectionCSVStorageNode` | removed |
| `vtkMRMLMarkupsBezierSurfaceNode` / `...DisplayNode` | removed |
| `vtkMRMLMarkupsSlicingContourNode` / `...DisplayNode` | removed |
| `vtkMRMLMarkupsDistanceContourNode` / `...DisplayNode` | removed |

Scene-XML tag names changed to match: `LiverResection` -> `ResectionPlan`.

## Modules

| v1 | v2 |
| --- | --- |
| `Liver` | `Liver` — now a **shell** composing six workflow stages |
| `LiverResections` | `LiverResections` — rewritten onto LayerDM |
| `LiverMarkups` | **removed entirely** |
| `LiverSegments` | **renamed** `VascularTerritories` |
| — | `LiverSegmentation` — **new** (Stage 2 anatomy) |
| `LiverVolumetry` | `LiverVolumetry` — seeds moved off markups |
| — | `SlicerLiverInteractionLib` — **new** shared interaction base |
| — | `SubjectHierarchyFolders` — **new** scene-organisation helper |

`slicer.modules.livermarkups` and `slicer.modules.liversegments` no longer
resolve.  The renamed module's *displayed title* is unchanged
(*"Extract Vascular segments"*) — only the module name and its classes
changed.

## Scripting API changes

v1's `vtkMRMLLiverResectionNode` was a single node carrying geometry,
clinical metadata and display properties.  v2 splits it along
wrapper / carrier / display / storage lines.

| v1 (on `vtkMRMLLiverResectionNode`) | v2 |
| --- | --- |
| `Get/SetResectionMargin` | `vtkMRMLResectionPlanNode::Get/SetSafetyMargin` |
| `Get/SetUncertaintyMargin` | `vtkMRMLResectionPlanNode::Get/SetRiskMargin` |
| `Get/SetState` (`Initialization`/`Deformation`/`Completed`) | `Get/SetState` (`Init`/`Planning`/`Confirmed`) |
| `Get/SetInitMode` (`Flat`/`Curved`) | `InitMode` (`SlicingPlane`/`DistanceSpheroid`) — **no v1 equivalent** |
| `SetBezierSurfaceControlPoints` | `vtkMRMLBezierSurfaceNode::SetControlPoint(row, col, x, y, z)` |
| `Get/SetDistanceMapVolumeNode` | `vtkMRMLResectionPlanNode::Get/SetAndObserveDistanceMapVolumeNode` |
| display fields (`ResectionColor`, `GridVisibility`, `InterpolatedMargins`, ...) | **same names**, on `vtkMRMLParametricSurfaceDisplayNode` |

Note the asymmetry: the margin **colours** kept their v1 names
(`ResectionMarginColor`, `UncertaintyMarginColor`) on the display node,
while the margin **values** were renamed and moved to the plan node.
`ResectionMarginColor` is the colour of the band whose width is now
`SafetyMargin`.

### Margin key rename

The plan margins were renamed from `safetyMargin_mm` / `riskMargin_mm`
to `safetyMargin` / `riskMargin` in both the C++ API and the serialized
forms (scene XML + `.lrp.json`).  Values remain millimetres.  Readers
accept the legacy unit-suffixed keys, so files written before the rename
load unchanged; writers emit only the current keys.

This fallback covers files written during v2 development — it is **not** a
v1 compatibility path, since v1 had neither key.

### Logic class rename

`vtkLiverSegmentsLogic` -> `vtkSlicerVascularTerritoriesLogic`.

## File formats

| Extension | Node | Direction |
| --- | --- | --- |
| `.lrp.json` | `vtkMRMLResectionPlanStorageNode` | read + write |
| `.vta.json` | `vtkMRMLCustomTerritoriesStorageNode` | read + write |
| `.vsd.json` | `vtkMRMLVolumetrySeedsStorageNode` | read + write |
| `.lrp.fcsv` | — | **neither** |

## Before you upgrade: a checklist

1. **Inventory your `.lrp.fcsv` files** before they become unreadable in
   practice as well as in principle.
2. **Keep v1 installed** until every plan is re-created or abandoned.
3. **Install SlicerLayerDM** — v2 will not build or run without it.
   SlicerVMTK, SegmentEditorExtraEffects and ExtraMarkups were already v1
   dependencies and are unchanged.
4. **Plan for the TotalSegmentator download** (~3 GB) if you intend to use
   Stage 2's AI segmentation.
5. **Audit your scripts** against the table above.  Anything touching
   `vtkMRMLLiverResectionNode` needs rewriting, not patching.
