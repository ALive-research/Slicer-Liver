# 0011. SNOMED-CT terminology as the dispatch key

- **Status:** Accepted
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver's v2.0.0 segmentation and modelling stack integrates
multiple upstream tools, each labelling regions in its own private
vocabulary:

- **TotalSegmentator** — deep-learning multi-organ segmentation;
  emits strings like `"portal_vein"`, `"liver"`.
- **VMTK** — vessel centreline extraction; emits geometry without
  semantic labels, plus user-assigned strings.
- **MONAILabel** — interactive tumour outlining; emits per-session
  label IDs scoped to the active model (`"Vessel-1"`, `label==5`).
- **Kumar & Oram seed-based vessel refinement** (re-implementation) —
  emits structures keyed by seed identity.

Today, modules disambiguate roles with per-tool ad-hoc strings and
combo-boxes that ask the surgeon to confirm "is this the portal vein
or the hepatic vein?" at each handoff.  The same anatomical concept
travels through three or four spellings between tools; dispatch logic
branches on those strings; the UI surfaces the disambiguation choice
in every dialog that consumes the output.

DICOM SR / DICOM Segmentation Object terminology — rooted in
SNOMED-CT (SCT) — provides an interoperable, standards-based
vocabulary already used elsewhere in Slicer (Segment Editor's
terminology selector, DICOM SEG export).  It is the de facto
vocabulary across DICOM, MONAI, and the broader medical-imaging
tooling ecosystem.

Of the concepts Slicer-Liver actually dispatches on:

- **Liver**, **Portal vein**, **Hepatic vein**, **Mass/Tumor** have
  well-known SCT codes available via the Slicer-bundled DICOM Master
  terminology.
- The **eight Couinaud segments (I–VIII)** are not in DICOM Master.
  Ten codes total (eight segments plus two compound regions or
  alternate codings) need to be carried in a project-private
  terminology file.

The choice is whether to keep dispatching on strings (cheap, immediate,
already pervasive) or to commit to SCT triples as the canonical
internal key (a refactor, but aligns the codebase with the standards
ecosystem and removes a recurring UI confirmation).

## Decision

Slicer-Liver modules use SNOMED-CT triples
`(CodingScheme, CodeValue, CodeMeaning)` as the **canonical dispatch
key** for all module-internal decisions: which algorithm to run, which
colour to render, which UI panel to show, which validation rule to
apply.  String labels appear in storage formats and tool I/O but never
in module-internal dispatch.

### 1. API contract — modules consume SCT triples, not strings

Function signatures take a `CodeIdentifier` object (or equivalent
triple).  Internal dispatch branches on the triple:

```python
def dispatch_segment(code: CodeIdentifier) -> Algorithm:
    if code == CODE_PORTAL_VEIN:
        return PortalVeinPipeline()
    if code == CODE_HEPATIC_VEIN:
        return HepaticVeinPipeline()
    ...
```

Reviewers reject PRs that branch on label strings inside module logic.
`/slicer-review` flags `if label == "portal_vein"`-shaped code as a
blocking issue.  String labels are permitted only at the I/O boundary
— reading a tool's output, writing a non-DICOM file format that
upstream consumers expect by name.

The Stage 3 territories family's
`vtkMRMLAbstractTerritoriesNode::GetSCTCode(int)` polymorphic accessor
is the per-segment dispatch entry point for territories consumers
(see [ADR-0023](0023-unified-gui-stage-workflow.md) §"Class
abstraction for territories" — amended 2026-05-25).  Subclass
`vtkMRMLStdCouinaudTerritoriesNode` returns Couinaud triples; subclass
`vtkMRMLCustomTerritoriesNode` returns surgeon-opted-in triples or
empty.

### 2. Private terminology file

Ship `Resources/Terminology/SlicerLiver-Terminology.json` containing:

- **Four DICOM Master triples** re-exported for convenience: Liver,
  Portal vein, Hepatic vein, Mass/Tumor.  Re-exporting (rather than
  reaching into DICOM Master at runtime) makes Slicer-Liver's
  terminology surface explicit and reviewable in one file.
- **Ten Couinaud codes** under a project-private coding scheme:
  `LIVER-SEG-I` through `LIVER-SEG-VIII` plus the two compound-region
  or alternate-coding entries.  The private coding scheme identifier
  (candidate `99SLIVER`) is project-namespaced and unambiguous; the
  exact string is finalised in the implementation PR.

The file is `tr()`-friendly for `CodeMeaning` translation.
`CodeValue` and `CodingScheme` are immutable identifiers and **must
not** pass through `tr()`.

### 3. Per-tool label bridge

Each upstream-tool integration ships a per-tool bridge JSON mapping
its native labels to SCT triples:

- `Resources/Terminology/LabelToSCT/TotalSegmentator.json`
- `Resources/Terminology/LabelToSCT/MONAILabel.json`
- `Resources/Terminology/LabelToSCT/KumarOram.json`

(Initial drafts of this ADR placed the bridge files under
`Modules/Segmentation/Resources/<Tool>/LabelToSCT.json`; the
implementation chose extension-root-level
`Resources/Terminology/LabelToSCT/<Tool>.json` to keep all
terminology assets co-located and avoid pre-committing to a
specific module's ownership of the bridges.  The paths above
reflect the actual implementation in
[PR #315](https://github.com/ALive-research/Slicer-Liver/pull/315).)

Tool wrappers consult the bridge file at the boundary, attach the SCT
triple to the segment, and emit `Unknown` for outputs they cannot
unambiguously map.  The UI surfaces a one-time mapping prompt for
`Unknown` rather than a per-result combo-box on every consumer dialog.

### 4. UI consequence — combo-box elimination

Where a module currently asks "what is this segment?" and the
terminology already answers, the combo-box is removed.  Per-result
confirmation belongs in a separate flow (the one-time mapping prompt
in §3), not embedded in every consumer dialog.

This is a concrete worked example of the UX simplification governed
by ADR-0009.

### 5. Versioning under ADR-0007

The private terminology file is a versioned contract.  Bumps map to
[ADR-0007](0007-version-numbering-policy.md) triggers as follows:

- **MINOR** — adding new private codes (e.g. extending the Couinaud
  scheme with sub-segments).  Backward-compatible: scenes referencing
  pre-existing codes still load.
- **MAJOR (N)** — renumbering or removing existing private codes.
  Persisted scenes that reference the old codes break; this is an N
  surface change per ADR-0007.
- **Managed migration** — moving a concept from the private scheme to
  public DICOM Master coding (e.g. if Couinaud segments are eventually
  added to DICOM Master): the release ships an alias mapping
  `private code → public code`, deprecates the private code over one
  MAJOR cycle, removes the private code at the following MAJOR.

## Alternatives considered

### A. String labels with a project-wide convention

Standardise on a single string vocabulary across Slicer-Liver
(`"liver"`, `"portal_vein"`, `"couinaud_segment_iv"`, ...) and
translate each tool's labels into it at the boundary.

**Rejected** because:

- Labels drift across PRs, modules, and contributors; there is no
  compiler check that `"portal_vein"` in module A matches
  `"portal_vein"` in module B.
- The vocabulary is not unique across tools or across the broader
  medical-imaging ecosystem; DICOM SEG export still has to translate.
- No interop path to DICOM SR / DICOM SEG / MONAI without a second
  translation layer.  Doing the SCT mapping anyway, but indirectly,
  costs more than committing to SCT as the internal key.

### B. Slicer Segment Editor's terminology selector everywhere, unextended

Adopt Slicer's existing terminology machinery and rely on it
end-to-end — no per-tool bridge file, no private terminology file.

**Adopted in spirit, rejected in literal form.**  This ADR commits to
the Segment Editor terminology selector as the canonical mechanism,
but extends it with two project-specific files:

- The private terminology file (§2) is required because Couinaud
  segments are not in DICOM Master.
- The per-tool bridge file (§3) is required because Slicer's
  machinery does not auto-resolve tool-native labels like
  `"portal_vein"` into SCT triples.

### C. Roll our own ontology

Design a Slicer-Liver-specific code system covering liver anatomy,
vessel structures, and lesion types.

**Rejected** because SCT is the de facto vocabulary used by DICOM,
MONAI, and the broader medical-imaging tooling ecosystem.  A bespoke
ontology gives up interop for no clinical benefit, and creates a
maintenance liability with no community uptake path.

### D. SCT triples in storage only; strings in module logic

Use SCT triples on the wire (DICOM SEG export, `.lrp.fcsv` files) but
keep module-internal dispatch on strings for convenience.

**Rejected** because the translation point becomes a recurring bug
source: every module that reads a scene re-converts triples to
strings, every module that writes a scene re-converts strings to
triples, and the per-tool ambiguity §3 solves resurfaces inside every
consumer.  The string-internal/triple-on-wire split is the worst of
both worlds.

## Consequences

### Easier

- **Per-tool dispatch bugs collapse.**  Module logic asks "is this
  code Portal Vein?" once, against a stable identity; the per-tool
  spelling differences are absorbed at the bridge boundary.
- **Combo-box noise drops.**  Dialogs that previously asked the user
  to disambiguate at every handoff lose that question entirely when
  the terminology already answers it.  Concrete UX simplification
  example for ADR-0009.
- **Cross-tool interoperability becomes default.**  DICOM SEG export
  and scene exchange with other Slicer extensions work without per-
  module translation glue.
- **Reviewer rule is mechanical.**  `if label == "..."` inside a
  module is a blocking comment; `if code == CODE_...` is fine.

### Harder

- **One `LabelToSCT.json` per integrated tool** is a small recurring
  data-asset maintenance burden.  Each new upstream tool ships its
  bridge file alongside its wrapper.
- **Existing string-based dispatch must be refactored.**  Pair each
  module's LayerDM migration ([ADR-0002](0002-migrate-to-slicerlayerdm.md))
  with its terminology cleanup; do not land the LayerDM migration of a
  module without converting its dispatch.
- **Private codes that should become public later require a managed
  deprecation.**  If DICOM Master adds Couinaud segments, the §5
  migration path runs once per concept.  Acceptable; documented.
- **The `tr()` boundary on the terminology file must be enforced.**
  Translating `CodeMeaning` is fine; translating `CodeValue` or
  `CodingScheme` silently breaks dispatch.  Linter / review rule
  required.

## References

- [SNOMED-CT](https://www.snomed.org/) — upstream terminology.
- [DICOM Segmentation Object](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.20.html)
  and DICOM SR — the standards layer this ADR ties Slicer-Liver into.
- Slicer Segment Editor terminology selector: source at
  `Modules/Loadable/Terminologies/` in the Slicer tree; bundled
  DICOM Master JSON at
  `Modules/Loadable/Terminologies/Resources/SegmentationCategoryTypeModifier-SlicerGeneralAnatomy.json`.
- Related ADRs:
  - [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the migration that
    pairs with terminology cleanup per module.
  - [ADR-0004](0004-python-cpp-boundary.md) — the Python band where
    dispatch on SCT triples lives.
  - [ADR-0007](0007-version-numbering-policy.md) — the version policy
    §5 maps the terminology contract onto.
  - ADR-0009 — UX simplification (combo-box elimination is a worked
    example under it).
