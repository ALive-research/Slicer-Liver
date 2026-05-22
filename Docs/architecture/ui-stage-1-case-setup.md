# UI architecture — Stage 1: Case Setup

Reference companion to [ADR-0023 §Stage 1][adr-0023] + the forthcoming [ADR-0029 — Stage 1 case-setup functional contract][adr-0029]. Captures the panel structure, control affordances, role-tagging UX, registration-detection signal, and cross-stage hand-off for Slicer-Liver's first workflow stage.

[adr-0023]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md
[adr-0029]: https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0029-stage1-case-setup-contract.md

## What this stage does

Load patient data (DICOM, NIfTI, NRRD, MetaImage, MHA — anything Slicer reads); tag each loaded volume with a clinical role (Native / Arterial / Portal venous / Delayed / Other); arrange the canonical Slicer layout. Hands off to downstream stages a manifest of role-tagged volumes.

The **dominant case is single-volume** (one Portal-venous-phase CT, common to most research datasets and many clinical acquisitions). The manifest + multi-phase affordances are progressive disclosure that only matter when ≥2 volumes are loaded.

**Registration is explicitly out of v2.0 scope** (per ADR-0029). Slicer-Liver does not ship in-extension registration UI in v2.0; when volumes are not co-registered the panel surfaces a hint pointing at Slicer's stock registration tools and lets the surgeon pick whatever fits their data.

Module home: handled directly by the `Liver` shell (section under the shell sidebar, not a separate scripted module).

## Sub-flow

```
Load → Tag Volume Roles → Layout → Hand off to Stage 2
```

## Panel layout — single-volume default (dominant case)

```
┌─ 1. Case Setup ────────────────────────────────────────────────┐
│                                                                │
│ ┌─ Load ───────────────────────────────────────────────────┐  │
│ │ [Load DICOM…]   (delegates to Slicer's DICOM browser)    │  │
│ │ [Load Volume…]  (delegates to "Add Data" for NIfTI/etc.) │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Volume ─────────────────────────────────────────────────┐  │
│ │  patient_PV.nrrd     Role: [▼ Portal venous*]            │  │
│ │  * = auto-tagged from DICOM header (surgeon-correctable) │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Layout ─────────────────────────────────────────────────┐  │
│ │  ◉ Conventional (3D + 3 ortho)                           │  │
│ │  [Apply layout]                                          │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ [Continue to Anatomy Definition ▶]                             │
└────────────────────────────────────────────────────────────────┘
```

## Panel layout — multi-volume case (progressive disclosure)

When ≥2 volumes are loaded, the single-volume row expands into a manifest table; the registration-status banner appears; the multi-phase comparison layout option unlocks.

```
┌─ 1. Case Setup ────────────────────────────────────────────────┐
│                                                                │
│ ┌─ Load ───────────────────────────────────────────────────┐  │
│ │ [Load DICOM…]   [Load Volume…]                           │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Volume manifest ────────────────────────────────────────┐  │
│ │  Name              Role                  Source          │  │
│ │ ─────────────────────────────────────────────────────    │  │
│ │  patient_PV.nrrd   [▼ Portal venous*]    NIfTI           │  │
│ │  patient_ART.dcm   [▼ Arterial]          DICOM           │  │
│ │  patient_NAT.dcm   [▼ Native]            DICOM           │  │
│ │                                                          │  │
│ │  Registration:  ✓ appears co-registered                  │  │
│ │   (or)          ⚠ may not be co-registered — see hint    │  │
│ │                                                          │  │
│ │  * = auto-tagged from DICOM header (surgeon-correctable) │  │
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

### Single-volume default

- Scene has 0 volumes → manifest empty, only `[Load …]` buttons visible. Stage 2 stays gated until at least one volume + role tag.
- Scene has 1 volume → "Volume" section (not "manifest table") shows the single volume row. No registration status, no 2-up layout option.
- Scene has ≥ 2 volumes → manifest table replaces the single-volume row. Registration-status banner appears. The 2-up layout option becomes selectable.

### Registration

**Out of v2.0 scope** per [ADR-0029][adr-0029]. Slicer-Liver does not ship registration UI; surgeon uses Slicer's stock registration tools (Slicer's Registration module category — BRAINSFit, or installed extensions like `SlicerElastix`, `SlicerANTs`) outside the Slicer-Liver shell when needed.

The registration-status banner is detection-only:

- **`✓ appears co-registered`** when all loaded volumes share the same voxel grid (origin, spacing, direction matrix, dimensions) OR share the same DICOM `FrameOfReferenceUID`. Both are *strong* signals — voxel-grid match means the data is on the same sampling grid; matching `FrameOfReferenceUID` is the DICOM contract for co-registration.
- **`⚠ may not be co-registered — see hint`** when the above doesn't hold. The hint expands to a short message naming Slicer's stock registration module category as the path forward. No `[Run registration]` button — Slicer-Liver does not invoke a specific tool.
- The detection is **soft** — surgeon's eyeball is the final judge; the hint never blocks Stage 2.

### Layout

- Canonical Slicer layout (Conventional / FourUp) is the default.
- The "2-up multi-phase comparison" layout is a Slicer-Liver-registered custom layout (CMakeLists / module-load time) showing two 3D-or-slice views side-by-side, intended for surgeons comparing Portal-venous vs Arterial phases. Only available when ≥2 volumes are loaded.

### Stage 2 unlock criterion

Stage 2 (Anatomy Definition) becomes "available" in the sidebar when **at least one volume has a role appropriate for segmentation** — typically `Portal venous`, falling back to `Native` with a warning per ADR-0023 §"Anatomy Definition". The check is soft (warns rather than blocks) so research data with single-phase NIfTI is supported.

### Defaults (per the 2026-05-21 Stage 1 walkthrough)

1. **Mandatory vs optional role-tagging** — warn-and-proceed, not block.
2. **Auto-tagging aggressiveness** — auto-tag with visible diff (asterisk badge); surgeon-correctable.
3. **Manifest** — progressive disclosure (single-volume row by default; table when ≥2 volumes).
4. **Registration** — detection-only hint banner; no in-extension UI. See ADR-0029.
5. **Single-phase research data** — first-class support (no AI-tool gating downstream).

## Cross-stage interactions

| Direction | Surface |
|-----------|---------|
| Stage 1 → Stage 2 | The role-tagged volume manifest is read by Stage 2's per-structure cards (each card's "Source" dropdown defaults to whichever volume has the `Portal venous` role; in single-volume scenes the dropdown is auto-set with no alternatives). |
| Stage 1 → Stage 3 (Auto path) | The same `Portal venous`-tagged image is the source for the TotalSegmentator Couinaud inference. |
| Stage 1 → Stage 4 | The role-tagged image identifies the canonical CT volume the Bezier-surface mapper renders against. |
| Sidebar | Stage 1 state indicator turns ✓ when at least one volume is loaded + role-tagged. |

## See also

- [ADR-0023 §Stage 1][adr-0023]
- [ADR-0029 — Stage 1 case-setup functional contract][adr-0029] (forthcoming) — codifies registration-detection algorithm + no-bundled-registration stance + single-volume-default.
- [GUI stage flow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/architecture/gui-stage-flow.md) — Stage 1 in the cross-stage data flow diagram.
- [Stage 2 — Anatomy Definition](ui-stage-2-anatomy-definition.md) — downstream consumer of the role-tagged manifest.
