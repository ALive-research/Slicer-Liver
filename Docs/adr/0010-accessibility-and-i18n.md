# 0010. Accessibility and internationalisation stance

- **Status:** Proposed
- **Date:** 2026-05-15
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver inherits Slicer 5.x's Qt-based UI and the existing Qt
Linguist infrastructure (`.ts` files, `tr()` / `qsTr()` markers, the
`slicer.qSlicerApplication.translate()` Python entry point).  No prior
ADR commits a position on either accessibility or internationalisation.
The current state of the codebase reflects that absence:

- User-facing strings are mostly English literals, not wrapped for
  translation.
- No colour-blind palette audit has been performed on segment labels,
  region overlays, or plot series.
- Keyboard-only operation of primary workflows is not guaranteed; some
  paths are mouse-only by construction.

The user population is surgeons and radiologists in clinical
environments.  Three forces apply:

- **Colour-blindness is common** — roughly 8% of men have a red-green
  deficiency.  Diagrammatic surfaces that rely on hue alone (segment
  colour swatches, vessel-tree highlights, resection-state cues) fail
  for this fraction of users.
- **Font-scaling needs grow with age**, and the clinical population
  skews older than the average software user.  Hard-coded point sizes
  in widgets defeat Slicer's application-level font scaling.
- **Keyboard navigation matters for ergonomics** in long sessions and
  for users who alternate between Slicer-Liver and PACS / EMR
  applications that are keyboard-driven.

Multilingual deployments at non-English centres (Spanish, French,
Mandarin, German, Norwegian) are plausible over the v2 lifecycle.
Retrofitting `tr()` markers after the fact is expensive; adding them
at write-time is nearly free.

ADR-0009 (UX discipline, in flight) requires a methodology statement
and an interaction diagram on every UI-touching PR.  This ADR commits
the specific accessibility and i18n posture that those PRs must
comply with — without it, ADR-0009 has no concrete criteria to grade
against.

## Decision

For v2.0.0, Slicer-Liver adopts the following posture.

### Internationalisation

1. **Inherit Slicer's Qt Linguist infrastructure.**  All user-facing
   strings introduced or modified during the LayerDM migration (per
   ADR-0002) must be wrapped in `tr()` / `qsTr()` in C++ / QML, and in
   `slicer.qSlicerApplication.translate()` (or the project's `_(...)`
   helper) in Python.  Hard-coded English string literals in
   user-facing surfaces are a review-blocker per ADR-0009.
2. **Ship English-only `.ts` for v2.0.0.**  Translation completion is
   not in scope for the v2.0.0 release.  The infrastructure must be
   in place so that translators can contribute against a stable v2.x
   baseline without a code change.
3. **Community translation deferred to v2.1.0**, unless OUS or NTNU
   contributes a target language during the v2.0.0 cycle.  A donated
   translation during v2.0.0 lands as a MINOR per ADR-0007.

### Accessibility

1. **Colour-blind safe palette.**  Adopt the Okabe-Ito 8-colour
   qualitative palette (Wong, *Nature Methods* 2011; equivalent
   palettes such as Tol acceptable) for any new diagrammatic UI
   surface — segment labels, region overlays, plot series, state
   indicators.  Re-skin existing palettes opportunistically during
   the LayerDM migration; a full re-skin is not blocking for v2.0.0.
   Verify with a simulator (Coblis, sim-daltonism) as part of UX
   review per ADR-0009.
2. **Keyboard navigation for primary actions.**  Every
   workflow-critical action must be reachable without a mouse.
   Mouse-only paths are a review-blocker.  Pointer-required actions
   (e.g. drawing a 3D contour on a render view) are allowed where the
   pointer is physically intrinsic to the operation; their entry and
   exit must still be keyboard-reachable.
3. **Font scaling via Slicer preferences.**  No hard-coded point sizes
   in widgets; respect Slicer's application-level font-size scaling.
   Audit existing modules opportunistically as they are touched.
4. **Screen-reader support: out of scope for v2.0.0.**  Qt's
   accessibility bridge to AT-SPI / NVDA / VoiceOver is partial, and
   Slicer-Liver's 3D-rendered surfaces are not screen-reader-friendly
   at the platform level.  Revisit in v2.1.0 with explicit scope.
5. **WCAG 2.1 AA referenced as aspirational target.**  Full
   compliance is not claimed for v2.0.0.  Per ADR-0009, PRs that move
   the project further from AA must cite a reason.

### Medical-device alignment

- **IEC 62366-1:2015** (Usability engineering for medical devices)
  and **IEC 60601-1-6:2010+A1:2013** (usability of medical electrical
  equipment) both treat accessibility as a usability dimension.  This
  ADR is the connecting commitment: the project tracks toward those
  frameworks even where formal certification is not in scope today.
- **EN 301 549** (European accessibility for ICT products) is the
  relevant procurement-side standard for EU public-sector deployment
  and is referenced for the same reason.

## Alternatives considered

### A. Defer all of this to v2.1.0

Treat v2.0.0 as a pure LayerDM migration release and pick up
accessibility and i18n as a follow-on cycle.

**Rejected** because `tr()` markers cost almost nothing at write-time
and are expensive to retrofit across an already-merged codebase.
Keyboard-path discipline is similarly cheaper at write-time than as
an after-the-fact audit.  The v2.0.0 migration is the natural moment
to set the discipline; missing it means paying retrofit cost during
v2.1.0.

### B. Full WCAG 2.1 AA compliance for v2.0.0

Commit to full AA conformance — including screen-reader support for
3D surfaces — as a release criterion.

**Rejected** because 3D-rendered surfaces and screen-reader
interaction are unsolved at the Slicer platform level, not just in
Slicer-Liver.  The cost of solving them upstream is disproportionate
to the stated needs of the user population, and would block v2.0.0
indefinitely on work that is not Slicer-Liver's to do.

### C. Adopt a third-party design system

Pull in Material, Carbon, or another design system and re-skin the UI
on top of it, obtaining accessibility tokens and patterns for free.

**Rejected** because Slicer-Liver runs inside Slicer 5.x's existing
Qt theming.  Introducing a parallel design system breaks consistency
with the host application and confuses users who switch between
Slicer-Liver and other Slicer modules in the same session.
Accessibility wins here are real but the consistency cost is higher.

### D. Custom in-house palette and i18n format

Define a Slicer-Liver-specific palette and a Slicer-Liver-specific
translation file format independent of Qt Linguist.

**Rejected** because both reinvent infrastructure that Slicer already
provides and integrates with.  Custom palettes lose the literature
backing of Okabe-Ito; a custom translation format loses the entire
Qt Linguist translator ecosystem.

## Consequences

### Easier

- **Slicer-Liver becomes deployable at non-English centres without a
  code change cycle.**  A new language requires only a translation
  contribution against the existing `.ts` baseline.
- **The screen-reader gap is explicit, not silent.**  Future
  contributors and reviewers know what was deferred and why; the
  v2.1.0 scope conversation starts from a documented position.
- **UX PRs have concrete grading criteria** per ADR-0009: palette
  check, keyboard-path check, `tr()` discipline, font-scaling check.
- **Medical-device alignment is traceable.**  IEC 62366-1, IEC
  60601-1-6, and EN 301 549 references give a starting point for any
  future certification-scoped work without committing to certification
  today.

### Harder

- **Per-PR overhead.**  `tr()` marking discipline costs minutes per
  PR; colour-blind palette verification on new visual surfaces costs
  minutes; keyboard-path verification on new widgets costs minutes.
  Material at the population level, marginal per individual PR.
- **Opportunistic re-skin of legacy palettes** may take multiple PR
  cycles to complete.  Tracked as a v2.0.0 issue rather than blocking
  the release.
- **Reviewer load.**  ADR-0009 reviewers must now check this ADR's
  criteria on every UI-touching PR.  The checklist is short but
  non-empty.

## References

- Wong, B. *Color blindness*. **Nature Methods** 8, 441 (2011) —
  source of the Okabe-Ito 8-colour palette.
- [WCAG 2.1](https://www.w3.org/TR/WCAG21/) — Web Content
  Accessibility Guidelines, AA conformance level.
- IEC 62366-1:2015 — *Medical devices — Part 1: Application of
  usability engineering to medical devices*.
- IEC 60601-1-6:2010+A1:2013 — *Medical electrical equipment — Part
  1-6: General requirements for basic safety and essential
  performance — Collateral standard: Usability*.
- EN 301 549 — *Accessibility requirements for ICT products and
  services* (European Telecommunications Standards Institute).
- [Qt Linguist Manual](https://doc.qt.io/qt-5/qtlinguist-index.html)
  — the translation infrastructure Slicer-Liver inherits.
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the LayerDM
  migration during which `tr()` discipline is introduced.
- [ADR-0007](0007-version-numbering-policy.md) — adding new language
  translations is a MINOR bump; removing translation infrastructure
  would be a MAJOR.
- ADR-0009 — UX discipline (in flight) — the per-PR methodology
  that grades against this ADR's criteria.
