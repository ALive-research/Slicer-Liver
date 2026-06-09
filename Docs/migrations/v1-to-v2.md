# v1 to v2 resection-plan migration

This note documents how Slicer-Liver migrates a legacy **v1
`.lrp.fcsv`** resection file to the **v2 `.lrp.json`** plan format, and
which information is irrecoverably lost in the upgrade.

## What v1 carried

The v1 resection format (`.lrp.fcsv`) is a 15-column
Markups-fiducial CSV. It stores **only the 16 Bezier control points**
of the resection surface (a 4x4 control polygon) in the LPS coordinate
system. It carries no clinical or plan-level metadata.

## What v2 expects

The v2 plan format (`.lrp.json`, schema version 2) is rooted on the
resection **plan**, with the surface persisted as a polymorphic
`surface` block. Beyond the control polygon, the plan carries:

- `safetyMargin_mm` — clinical safety margin (mm).
- `riskMargin_mm` — clinical risk margin (mm).
- `orderIndex` — zero-based position in the operative sequence.
- `state` — plan-level state machine (`Init` / `Planning` /
  `Confirmed`).

See `Docs/design/resection-plan-architecture/05-lrp-json-schema.md`
for the full schema.

## The gap and its defaults

Every v2 field except the control points is **absent from v1** and
therefore **not recoverable** from a legacy file. On load, the
migration applies the documented v2 reader defaults:

| Field             | Default on migration |
| ----------------- | -------------------- |
| `safetyMargin_mm` | `0.0`                |
| `riskMargin_mm`   | `0.0`                |
| `orderIndex`      | `-1`                 |
| `state`           | `Init`               |

A safety margin of 0 mm is **not** a clinical statement — it is the
neutral default for an unknown value. **Review the margins, order, and
state before using a migrated plan clinically.**

## How the migration runs

The upgrade is seamless: opening a `.lrp.fcsv` through the normal load
path routes it to `vtkMRMLResectionPlanStorageNode::ReadFcsv`, which:

1. Parses the 16 control points through the legacy
   `vtkMRMLLiverResectionCSVStorageNode` (read-only parse vehicle).
   The parse converts the file's LPS coordinates to the markups RAS
   convention (X and Y are negated, Z unchanged).
2. Materialises a `vtkMRMLBezierSurfaceNode` carrier holding those 16
   RAS control points and wires it under a `vtkMRMLResectionPlanNode`
   (the wrapper-vs-carrier split — ADR-0014 §"Fourth layer").
3. Applies the v2 defaults above for every legacy-absent field.
4. Records a **loud** warning on the storage node's user-message
   collection naming the margins, order, and state as defaulted, so
   the gap is visible rather than silent.

Saving a migrated plan always writes the v2 `.lrp.json`. The
`.lrp.fcsv` format is **read-only** in v2; there is no v2 writer for
it.
