# 0010. Accessibility and internationalisation stance

- **Status:** Accepted
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

A separate consideration constrains what this ADR may commit to:
Slicer-Liver is a module inside Slicer 5.x.  Visual palette, keyboard
shortcuts, theming, and accessibility infrastructure are shared across
the host application and its modules.  Users alternate between
Slicer-Liver and other Slicer modules in the same session.
Slicer-Liver cannot adopt accessibility mechanisms that diverge from
Slicer practice without breaking consistency for those users.  The
posture below therefore aligns with Slicer's stance and raises gaps
upstream rather than ships parallel solutions.

ADR-0009 (UX discipline, in flight) requires an interaction diagram
and a written design rationale on every UI-touching PR.  This ADR
records the accessibility and i18n posture those PRs are graded
against — to the extent that posture can be committed independent of
upstream Slicer.

## Decision

For v2.0.0, Slicer-Liver adopts the following posture.  The guiding
principle is **inherit Slicer's accessibility and internationalisation
posture, and raise gaps upstream rather than work around them
module-locally**.  A parallel set of Slicer-Liver-only mechanisms
would break host-application consistency and double-maintain
decisions that should be made once across the Slicer ecosystem.

### Guiding principle: align with Slicer, contribute upstream

Where Slicer has an established practice (palette, keyboard
convention, theme, conformance target), Slicer-Liver follows it.
Where Slicer-Liver identifies a platform-level gap, the appropriate
response is an upstream issue or contribution to Slicer core, not a
module-local workaround.  Before adopting any specific palette,
keyboard convention, or conformance target unilaterally, the project
surveys what Slicer already does.  Items below marked **survey
pending** are not committed; they record the question and how it is
to be resolved.

### Internationalisation

This is the tier already aligned with Slicer.

1. **Inherit Slicer's Qt Linguist infrastructure.**  All user-facing
   strings introduced or modified during the LayerDM migration (per
   ADR-0002) must be wrapped in `tr()` / `qsTr()` in C++ / QML, and in
   `slicer.qSlicerApplication.translate()` (or the project's `_(...)`
   helper) in Python.  This is the same mechanism Slicer uses for its
   own modules.  Hard-coded English string literals in new user-facing
   surfaces are a review-blocker per ADR-0009.
2. **Ship English-only `.ts` for v2.0.0.**  Translation completion is
   not in scope.  The infrastructure must be in place so that
   translators can contribute against a stable v2.x baseline.
3. **Community translation deferred to v2.1.0**, unless OUS or NTNU
   contributes a target language during the v2.0.0 cycle.  A donated
   translation that lands during v2.0.0 is MINOR per ADR-0007.

### Accessibility

The accessibility commitments come in three tiers: items
Slicer-Liver can act on within the module without affecting other
parts of Slicer; items requiring a Slicer-posture survey before any
unilateral commitment; and items that are out of scope at the
module level.

#### Tier 1 — within Slicer-Liver, low-risk

1. **Respect Slicer's font scaling.**  No hard-coded point sizes in
   widgets; use Qt's relative sizing or read Slicer's preferences.
   This is intrinsically aligned with Slicer and carries no host
   conflict.
2. **Avoid mouse-only paths for new workflow-critical actions** where
   equivalent keyboard reachability is available at the Qt widget
   level.  Pointer-required actions (e.g. drawing a 3D contour on a
   render view) are allowed where the pointer is physically intrinsic
   to the operation; their entry and exit follow whatever keyboard
   conventions Slicer establishes (see Tier 2 §5).
3. **`tr()` discipline for translation** (covered by Internationalisation
   §1; restated here because some accessibility users rely on
   translated text for screen-reader or magnification flows).

#### Tier 2 — survey pending; do not commit unilaterally

4. **Colour palette for diagrammatic surfaces.**  Slicer-Liver does
   not unilaterally adopt a project-specific palette.  Action: survey
   palette conventions Slicer uses for segment labels, region overlays,
   plot series, and state indicators.  If Slicer has a convention,
   follow it.  If Slicer has no convention, raise an upstream issue
   proposing one (Okabe-Ito, Wong 2011, is the literature-backed
   candidate the project would propose).  Do not ship a parallel
   Slicer-Liver palette.
5. **Keyboard-navigation conventions.**  Slicer-Liver follows whatever
   keyboard-navigation conventions Slicer publishes.  If Slicer has no
   published convention, the project surveys the defacto practice in
   core Slicer modules and aligns with it; any gap is raised upstream,
   not patched module-locally.
6. **Conformance target (WCAG / EN 301 549 / similar).**  Slicer-Liver
   does not claim a conformance level ahead of host Slicer.  The
   aspirational target is whatever Slicer's documented stance is.  If
   Slicer has no published stance, this is an upstream question.

#### Tier 3 — out of scope at the module level

7. **Screen-reader support** for Slicer-Liver-specific surfaces.
   Slicer's Qt accessibility bridge to AT-SPI / NVDA / VoiceOver is
   partial, and 3D-rendered surfaces are not screen-reader-friendly at
   the platform level.  This is not a problem Slicer-Liver can fix in
   v2.0.0.  Revisit in v2.1.0 only if Slicer itself has moved on the
   platform-level question.

### Medical-device usability — for reference

The medical-device usability literature provides useful reference
material:

- **IEC 62366-1:2015** — application of usability engineering to
  medical devices.
- **IEC 60601-1-6:2010+A1:2013** — usability of medical electrical
  equipment.
- **EN 301 549** — European accessibility requirements for ICT
  products and services.

This ADR does not require formal adherence to any of these standards.
References are recorded so that if the project's regulatory posture
changes the pointers are already in the decision record.

## Alternatives considered

### A. Defer all of this to v2.1.0

Treat v2.0.0 as a pure LayerDM migration release and pick up
accessibility and i18n as a follow-on cycle.

**Rejected** because `tr()` markers cost almost nothing at write-time
and are expensive to retrofit across an already-merged codebase.
Keyboard-path discipline is similarly cheaper at write-time.  Even
the survey items (Tier 2) are cheaper to do now while the LayerDM
migration is in flight than as a separate retrofit cycle.

### B. Full WCAG 2.1 AA compliance for v2.0.0

Commit to full AA conformance — including screen-reader support for
3D surfaces — as a release criterion.

**Rejected** because 3D-rendered surfaces and screen-reader interaction
are unsolved at the Slicer platform level, not just in Slicer-Liver.
The cost of solving them upstream is disproportionate to the stated
needs of the user population, and would block v2.0.0 indefinitely on
work that is not Slicer-Liver's to do.

### C. Adopt a third-party design system

Pull in Material, Carbon, or another design system and re-skin the UI
on top of it, obtaining accessibility tokens and patterns for free.

**Rejected** because Slicer-Liver runs inside Slicer 5.x's existing
Qt theming.  Introducing a parallel design system breaks consistency
with the host application and confuses users who switch between
Slicer-Liver and other Slicer modules in the same session.

### D. Slicer-Liver-specific accessibility mechanisms ahead of host Slicer

Define Slicer-Liver-specific palettes, keyboard conventions, and
conformance targets without surveying Slicer's existing practice;
ship them inside the module and let other Slicer modules catch up
later.

**Rejected** because users alternate between Slicer-Liver and other
Slicer modules in the same session.  A Slicer-Liver-only palette
conflicts with adjacent modules' palettes for the same user.  Custom
keyboard conventions create cross-module muscle-memory conflicts.
The right place to address platform-level accessibility is upstream
Slicer.  This ADR commits Slicer-Liver to *consistency* with the
host, not to *leadership* on items that are platform-wide concerns.

### E. Custom in-house i18n format

Define a Slicer-Liver-specific translation file format independent of
Qt Linguist.

**Rejected** because it reinvents infrastructure Slicer already
provides and integrates with, and loses the Qt Linguist translator
ecosystem.

## Consequences

### Easier

- **Slicer-Liver becomes deployable at non-English centres without a
  code change cycle.**  A new language requires only a translation
  contribution against the existing `.ts` baseline (Internationalisation
  §1–2 are independent of the survey items).
- **The screen-reader gap is explicit, not silent.**  Future
  contributors and reviewers know what is deferred and why.
- **UX PRs have concrete Tier-1 grading criteria** per ADR-0009: font
  scaling respected, no new mouse-only critical paths, `tr()`
  discipline.
- **Host consistency is preserved.**  Slicer-Liver users see palette
  and keyboard behaviour consistent with other Slicer modules they
  use alongside it.
- **References to medical-device standards are recorded** so that if
  the project's regulatory posture changes, the pointers are already
  in the decision record.

### Harder

- **Survey work must complete before the Tier-2 items can move from
  Proposed to Accepted.**  Each survey item is tracked as a v2.0.0
  milestone work item.  Until the survey lands, Tier-2 items are
  effectively "follow Slicer as you find it" rather than concrete
  criteria.
- **Per-PR overhead.**  `tr()` marking discipline costs minutes per
  PR; font-scaling and keyboard-reachability checks cost minutes.
  Marginal at the per-PR level.
- **Upstream coordination cost** for any platform-level gap surfaced
  by the survey.  Filing a Slicer issue and waiting on its
  disposition is slower than patching module-locally, but the
  consistency win is the point of this ADR.

## Open questions

The survey items below are the work that must complete before this
ADR's Tier-2 commitments can solidify.  They are tracked as v2.0.0
milestone work items.

- **Slicer's palette conventions** for segment labels, region overlays,
  plot series, and state indicators.  Survey current practice in core
  Slicer modules; if no convention exists, draft an upstream issue
  proposing one.
- **Slicer's keyboard-navigation conventions.**  Survey published
  guidance and defacto practice; identify whether Slicer-Liver's
  current workflows diverge.
- **Slicer's WCAG or accessibility conformance stance**, if any.
  Confirm in Slicer documentation or raise the question upstream.
- **Slicer's screen-reader posture.**  Confirm the platform-level
  position so that Slicer-Liver's deferral is consistent with it.
- Whether to bundle a high-contrast theme (deferred to v2.1.0 in any
  case; depends on Slicer's theming story).
- Whether NVIDIA-driver-dependent rendering creates accessibility
  issues for low-end hardware users.  Out of v2.0.0 scope.

## References

- Wong, B. *Color blindness*. **Nature Methods** 8, 441 (2011) —
  source of the Okabe-Ito 8-colour palette (the upstream candidate
  if Slicer has no palette convention).
- [WCAG 2.1](https://www.w3.org/TR/WCAG21/) — Web Content Accessibility
  Guidelines.
- IEC 62366-1:2015 — *Medical devices — Part 1: Application of
  usability engineering to medical devices*.
- IEC 60601-1-6:2010+A1:2013 — *Medical electrical equipment — Part
  1-6: Usability*.
- EN 301 549 — *Accessibility requirements for ICT products and
  services*.
- [Qt Linguist Manual](https://doc.qt.io/qt-5/qtlinguist-index.html)
  — the translation infrastructure Slicer-Liver inherits.
- [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the LayerDM
  migration during which `tr()` discipline is introduced.
- [ADR-0007](0007-version-numbering-policy.md) — adding new language
  translations is MINOR; removing translation infrastructure would
  be MAJOR.
- ADR-0009 — UX discipline (in flight) — the per-PR grading
  framework that uses this ADR's Tier-1 criteria.
