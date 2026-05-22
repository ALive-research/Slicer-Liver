# UI architecture — Stage 1: Case Setup

Reference companion to [ADR-0023 §Stage 1][adr-0023]. Captures the
panel structure, control affordances, role-tagging UX, and cross-
stage hand-off for Slicer-Liver's first workflow stage.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md

## What this stage does

Load patient data (DICOM, NIfTI, NRRD, MetaImage, MHA — anything Slicer reads); tag each loaded volume with a clinical role (Native / Arterial / Portal venous / Delayed / Other); optionally register multi-phase acquisitions; arrange the canonical Slicer layout. Hands off to downstream stages a manifest of role-tagged volumes.

Module home: handled directly by the `Liver` shell (section under the shell sidebar, not a separate scripted module).

## Sub-flow

```
Load → Tag Volume Roles → (optional) Register → Layout → Hand off to Stage 2
```

## Panel layout

```
┌─ 1. Case Setup ────────────────────────────────────────────────┐
│                                                                │
│ ┌─ Load ───────────────────────────────────────────────────┐  │
│ │ [Load DICOM…]   (delegates to Slicer's DICOM browser)    │  │
│ │ [Load Volume…]  (delegates to "Add Data" for NIfTI/etc.) │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Volume manifest ────────────────────────────────────────┐  │
│ │  Name              Role                  Source          │  │
│ │ ─────────────────────────────────────────────────────    │  │
│ │  patient_PV.nrrd   [▼ Portal venous*]    NIfTI           │  │
│ │  patient_ART.dcm   [▼ Arterial]          DICOM           │  │
│ │  patient_NAT.dcm   [▼ Native]            DICOM           │  │
│ │                                                          │  │
│ │  * = auto-tagged from DICOM header (surgeon-correctable) │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Registration (advanced) ────────────────────────────────┐  │
│ │  Status: ✓ Volumes appear pre-registered                 │  │
│ │  [Recommend registration]   (BRAINSFit / Elastix)        │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Layout ─────────────────────────────────────────────────┐  │
│ │  ◉ Conventional (3D + 3 ortho)                           │  │
│ │  ○ 2-up multi-phase comparison                           │  │
│ │  [Apply layout]                                          │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ [Continue to Anatomy Definition ▶]                             │
└────────────────────────────────────────────────────────────────┘
```

## Behaviour notes

### Role tagging

- **Vocabulary**: `Native`, `Arterial`, `Portal venous`, `Delayed/venous`, `Other`. Stored as a scene attribute on each volume node (key TBD at implementation; suggested `LiverVolume.RoleTag` — parallel to the existing `LiverSegments.SegmentationId` / `LiverSegments.VascTerrId` attribute convention).
- **Auto-tag from DICOM**: when `SeriesDescription`, `ContrastBolusAgent`, or `AcquisitionTime` headers permit inference, the manifest pre-populates the role with the heuristic guess + an asterisk badge marking it as auto-tagged. Surgeon-correctable via the dropdown.
- **NIfTI / NRRD / MetaImage**: no header hints; role starts empty; surgeon tags manually.
- **Re-loading a saved scene**: existing role tags persist on the volume nodes; manifest reflects them.

### Stage 2 unlock criterion

Stage 2 (Anatomy Definition) becomes "available" in the sidebar when **at least one volume has a role appropriate for segmentation** — typically `Portal venous`, falling back to `Native` with a warning per ADR-0023 §"Anatomy Definition". The check is soft (warns rather than blocks) so research-data with single-phase NIfTI is supported.

### Registration

- Optional. Multi-volume scenes get a hint banner: "Volumes may not be co-registered — consider [Recommend registration]."
- Delegates to stock Slicer registration modules (BRAINSFit / Elastix). Slicer-Liver does not re-skin the registration UI; it provides the entry point.

### Layout

- Canonical Slicer layout (Conventional or FourUp) is the default.
- The "2-up multi-phase comparison" layout is a Slicer-Liver-registered custom layout (CMakeLists / module-load time) showing two 3D-or-slice views side-by-side, intended for surgeons comparing Portal-venous vs Arterial phases.

### Defaults (per the 2026-05-21 Stage 1 walkthrough)

1. **Mandatory vs optional role-tagging** — warn-and-proceed, not block.
2. **Auto-tagging aggressiveness** — auto-tag with visible diff (asterisk badge); surgeon-correctable.
3. **Manifest** — explicit (the table above is always visible).
4. **Registration** — recommend, don't require.
5. **Single-phase research data** — first-class support (no AI-tool gating downstream).

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 2 | The role-tagged volume manifest is read by Stage 2's per-structure cards (each card's "Source" dropdown defaults to whichever volume has the `Portal venous` role). |
| Stage 1 → Stage 3 (Auto path) | The same `Portal venous`-tagged image is the source for the TotalSegmentator Couinaud inference. |
| Stage 1 → Stage 4 | The role-tagged image identifies the canonical CT volume the Bezier-surface mapper renders against. |
| Sidebar | Stage 1 state indicator turns ✓ when at least one volume is loaded + role-tagged. |

## See also

- [ADR-0023 §Stage 1][adr-0023]
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md) — Stage 1 in the cross-stage data flow diagram.
- [Stage 2 — Anatomy Definition](ui-stage-2-anatomy-definition.md) — downstream consumer of the role-tagged manifest.
