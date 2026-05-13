# 0001. Resection is a three-node MRML assembly

- **Status:** Proposed
- **Date:** 2026-05-13
- **Deciders:** Rafael Palomar (recording rationale on behalf of original authors)
- **Diagrams:** [current-mrml-node-hierarchy](../architecture/current-mrml-node-hierarchy.puml)
- **PR:** _filled in on merge_

## Context

A liver resection, as used by surgeons through the SlicerLiver UI, has three
logically distinct artefacts:

1. **An initial sketch** — a 2-point line the user places on the imaging to
   indicate cutting plane direction (Slicing or Distance contour modes).
2. **The editable geometry** — a 4×4 grid of Bezier control points giving a
   cubic Bezier patch that approximates the resection plane.
3. **The resection metadata** — margins, colours, state, references to source
   volumes (CT, distance map, vascular segments), and provenance.

Two non-negotiable Slicer platform constraints bound the solution space:

- **Interactive 3D widgets require `vtkMRMLMarkupsNode` inheritance.** Slicer's
  Markups widget machinery (`vtkSlicerMarkupsWidget` and the displayable
  manager pipeline in `Modules/Loadable/Markups/`) is hard-wired to the
  `vtkMRMLMarkupsNode` class tree. Re-implementing it on a different base
  would mean re-implementing interactive 3D handles, projection geometry, and
  event routing — thousands of lines of upstream-maintained infrastructure.
- **`vtkMRMLStorableNode` is the conventional save target.** The Slicer I/O
  manager expects whole-object serialization through `vtkMRMLStorableNode` +
  `vtkMRMLStorageNode`. Cross-volume references and provenance fields are
  conventionally carried by Storable nodes.

These two base trees do not unify: `vtkMRMLMarkupsNode` does **not** inherit
from `vtkMRMLStorableNode`. Any "single content node" design must therefore
sacrifice one side — either reimplement the widget pipeline on a Storable, or
forfeit the standard save path.

This ADR is recorded retrospectively: the design was already implemented in
commits `938a2d5..727bd36` (2019) but the rationale lived only in the heads
of the original authors. Future contributors (human and AI) need this written
down to avoid re-litigating it.

## Decision

A liver resection is represented in MRML as a **three-node assembly** managed
by `vtkSlicerLiverResectionsLogic`:

1. **Initialization node** — exactly one of
   `vtkMRMLMarkupsSlicingContourNode` or `vtkMRMLMarkupsDistanceContourNode`,
   both inheriting `vtkMRMLMarkupsLineNode`. Two control points; drives the
   workflow state from `Initialization` to `Deformation`.
2. **Geometry node** — `vtkMRMLMarkupsBezierSurfaceNode`, inheriting
   `vtkMRMLMarkupsNode`. Sixteen control points; reuses Slicer's Markups
   widget pipeline for interactive editing.
3. **Content node** — `vtkMRMLLiverResectionNode`, inheriting
   `vtkMRMLStorableNode`. Holds margins, colours, state, and weak references
   to the geometry node, the active initialization node, and the source
   volumes. Acts as the conventional save target via
   `vtkMRMLLiverResectionCSVStorageNode`, which delegates control-point I/O
   back to the Bezier geometry node.

`vtkSlicerLiverResectionsLogic` owns the assembly's lifecycle: it creates the
three nodes together, maintains bidirectional mappings between them (see
*Consequences*), observes their events to coordinate state transitions, and
removes them as a unit.

## Alternatives considered

### A. Single content node with embedded geometry

The sixteen Bezier control points would live directly on
`vtkMRMLLiverResectionNode` instead of on a sibling Markups node, eliminating
the multi-node assembly.

**Rejected** because interactive 3D editing of the Bezier patch requires the
Slicer Markups widget pipeline, which is tied to `vtkMRMLMarkupsNode`
inheritance. Reimplementing this pipeline on a `vtkMRMLStorableNode` would
duplicate thousands of lines of upstream code that already exists, and would
impose a permanent integration cost as upstream Markups continues to evolve.
The widget machinery's bug fixes and improvements would no longer be
inherited for free.

### B. Geometry-only node, no metadata content node

The resection would be only the Bezier surface Markups node; margins,
colours, and provenance would live on the display node or as node attributes
on the Markups node.

**Rejected** because the clinical workflow requires loading and saving a
resection as one atomic object with cross-volume provenance (which CT
volume, which distance map, which vascular segmentation it was planned
against). The Markups class tree has no natural place for such cross-volume
references. The `Storable` + `StorageNode` pattern, on the other hand, is
designed exactly for this — its serialization can capture node-reference
fields that resolve correctly on scene reload.

### C. Two-node assembly: no initialization node

The user would place 16 control points directly on the Bezier surface
without an intermediate 2-point sketch.

**Rejected** based on clinical UX feedback: surgeons reported wanting to
indicate cutting-plane *direction* first and refine geometry afterward.
Conflating those two operations into a 16-point edit raises cognitive load
during the first 5 seconds of placement, which is exactly where most edits
are aborted and restarted. The Slicing/Distance contour modes (two-point
lines) preserve this initial sketch phase cheaply.

## Consequences

### Easier

- Bezier interaction reuses the upstream Slicer Markups widget pipeline; we
  inherit its bug fixes and improvements automatically.
- Initialization modes (Slicing, Distance, future Curved) are testable
  independently of the geometry node — adding a third initialization mode
  requires no changes to `vtkMRMLMarkupsBezierSurfaceNode`.
- The resection metadata can be saved and reloaded as one `.lrp.fcsv` object
  through the standard Slicer I/O manager.

### Harder

- `vtkSlicerLiverResectionsLogic` must maintain bidirectional mappings
  between the three nodes (currently six `std::map` members; lifecycle
  cleanup is error-prone — see header line 153 author comment *"too many
  maps"*). A separate ADR will propose replacing maps with MRML node
  attribute references that survive scene reload natively.
- Property ownership is split across the three nodes in ways that surprise
  new readers. ~30 display-related fields currently live on
  `vtkMRMLLiverResectionNode` and are pushed one-way into
  `vtkMRMLMarkupsBezierSurfaceDisplayNode` on every `Modified()`. A future
  ADR will propose a dedicated `vtkMRMLLiverResectionDisplayNode` to clean
  this up.
- `vtkMRMLLiverResectionNode` is `Storable` but its storage node delegates
  I/O to a sibling Markups node — a thin-facade pattern that is correct but
  surprising. The class header should carry a comment pointing at this ADR
  so future readers find the rationale.
- Loading a `.lrp.fcsv` file requires constructing the three nodes in the
  correct order (geometry first, then content node with references resolved,
  then any active initialization node). This ordering is enforced inside
  `vtkMRMLLiverResectionCSVStorageNode::ReadDataInternal`; tests must cover
  reload after a fresh scene to catch ordering regressions.

## References

- Slicer Markups widget pipeline: `Modules/Loadable/Markups/VTKWidgets/`
  in the Slicer source tree.
- `vtkMRMLStorableNode` / `vtkMRMLStorageNode` contract:
  `Libs/MRML/Core/vtkMRMLStorableNode.h`.
- Historical commits introducing the three-node split: `938a2d5..727bd36`
  (2019, `LiverResections/`).
- Related (future): ADR-0002 will address the `Logic` six-maps navigation;
  ADR-0003 will address dedicated `vtkMRMLLiverResectionDisplayNode` and
  property ownership.
