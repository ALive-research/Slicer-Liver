# 0017. Sphinx + ReadTheDocs documentation infrastructure

- **Status:** Proposed
- **Date:** 2026-05-18
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver's documentation has grown into an un-navigable pile of
Markdown files:

```
Docs/
├── adr/                   16 ADRs (0001–0016), README index
├── architecture/          PUML + MMD diagrams
└── dependencies/          SlicerLayerDM.md, …
```

Plus top-level `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
`CITATION.cff`.  No rendered table-of-contents, no cross-document
search, no per-section navigation, no PDF/epub export, no API
reference, no version-pinned hosted copy.  External contributors
discover ADRs by browsing the GitHub directory listing; internal
contributors archaeologise via `grep` and memory of paths.

The v2.0.0 architectural refactor has been driven by the ADR ledger
+ committed architecture diagrams.  As the ledger grows past 16 ADRs
and the architecture diagrams accumulate, the value of presenting
this material as a *navigable hosted doc site* (with TOC, search,
versioned snapshots, cross-references) grows correspondingly.

Slicer-core solved the same problem in 2017 via Sphinx +
ReadTheDocs.  The infrastructure is mature, well-documented, and
the upstream's exact configuration (`.readthedocs.yaml` v2 +
`Docs/conf.py` + `requirements-docs.txt` + MyST/Markdown + the
`sphinx_rtd_theme`) is a known-good reference Slicer-Liver can
adopt verbatim.

## Decision

Adopt **Sphinx + MyST/Markdown + ReadTheDocs** as Slicer-Liver's
documentation infrastructure, matching the Slicer-core convention:

- **Source format**: Markdown (MyST) — keeps the existing 20+ `.md`
  files reusable without conversion.  RST is supported for future
  files that need it (e.g., directives the MyST extension set
  doesn't cover), but Markdown is the project default.
- **Theme**: `sphinx_rtd_theme` — matches Slicer-core; the
  ReadTheDocs-native look + per-page navigation sidebar are the
  features Slicer-Liver actually needs at this scale.  Reject
  `pydata-sphinx-theme` / `furo` for the v2.0.0 cycle — the
  Slicer-family consistency outweighs the modernity advantage of
  the alternatives, and theme migration is a one-line change later.
- **Hosting**: ReadTheDocs (free for public repos).  Versions
  pinned to `preview` (latest) + per-release tags (post-v2.0.0).
- **Build CI**: a new `.github/workflows/docs-build.yml` runs
  `sphinx-build` against every PR + push, fails on `WARNING` per
  Sphinx's `-W` flag.  Catches link-rot + MyST syntax errors before
  merge.  Publishing to ReadTheDocs is handled by RTD's own
  GitHub-webhook integration, not this workflow.
- **API auto-generation**: deferred.  Sphinx `autodoc` for Python
  modules + `Breathe`+`Doxygen` for C++ are substantial follow-up
  work; the v2.0.0 surface is small enough that the in-source
  doxygen comments + the architectural narrative in ADRs cover
  developer needs.  Re-evaluate post-v2.1.0.

## Sphinx extensions adopted (mirror Slicer-core)

| Extension                  | Purpose                                                     |
|----------------------------|-------------------------------------------------------------|
| `myst_parser`              | Markdown → reST AST.                                        |
| `sphinx_rtd_theme`         | Theme.                                                      |
| `sphinx_markdown_tables`   | Render Markdown tables.                                     |
| `sphinx-jsonschema`        | Render JSON schema definitions (deferred-use; T2.5 schema). |
| `sphinx_design`            | Tabs, cards, admonition variants.                           |
| `sphinx_reredirects`       | Handle page moves without 404s.                             |
| `notfound.extension`       | Better 404 page.                                            |
| `sphinx.ext.autodoc`       | Python API auto-generation surface (lazy-enabled).          |

MyST extensions enabled: `attrs_inline`, `colon_fence`,
`dollarmath`, `linkify`.  `myst_heading_anchors = 6`.

## Migration scope (this ADR; not in the scaffold PR)

The migration from "pile of `.md`" to "structured Sphinx tree" is
deferred to a follow-up PR after the scaffold lands.  The migration
moves:

- **ADRs** → `Docs/architecture/decisions/` (or kept at `Docs/adr/`
  with a Sphinx `toctree` pointing at them; the latter is the
  Slicer-core style).
- **Architecture diagrams** → `Docs/architecture/` (already
  present); added to a dedicated TOC chapter with the PUML/MMD
  files rendered to SVG at build time.
- **Dependencies** → `Docs/dependencies/` (already present); added
  to a "Build + integration" chapter.
- **Module documentation** → new chapter (`Docs/modules/`) per
  loadable module (LiverResections, LiverMarkups, …).

The migration PR also writes the top-level `Docs/index.md` with
the full TOC.  The scaffold PR ships only a stub `index.md` that
renders the title + a "migration in progress" notice.

## Why not RST as the project default

Mixed allowed, Markdown default.  Reasoning:

- 20+ existing `.md` files migrate as-is via MyST (zero conversion).
- Markdown's syntax surface is smaller — lower friction for
  external contributors writing one-off doc PRs.
- MyST supports every RST feature the project realistically needs
  (admonitions via `:::{note}`, cross-refs via `[](path.md)`,
  directives via `:::{directive}`).
- Slicer-core itself runs MyST/Markdown; matching keeps the
  cognitive overhead low for contributors who move between the
  upstream and this project.

## Why `sphinx_rtd_theme` rather than `pydata-sphinx-theme` or `furo`

- Slicer-core uses `sphinx_rtd_theme`.  External readers landing on
  Slicer-Liver docs after Slicer-core docs get a consistent
  experience.
- `pydata-sphinx-theme` is technically more polished + has better
  search; but it's the SciPy-family convention, not the
  Slicer-family one.  Slicer-Liver is closer to Slicer than to
  SciPy.
- `furo` is the smallest, most modern theme but lacks the
  per-section sidebar TOC that medium-sized doc trees need.

Theme migration is reversible with a one-line change in
`Docs/conf.py`; this decision is not load-bearing.

## Why ReadTheDocs rather than GitHub Pages

- RTD provides version-pinned snapshots (per-branch, per-tag) for
  free on public repos — GitHub Pages requires a custom CI workflow
  + branch management for the same surface.
- RTD's search index is automatic + per-version.
- RTD provides PDF + epub builds for free; GitHub Pages does not.
- The Slicer-core docs live on RTD; cognitive consistency.

GitHub Pages is a fine fallback if RTD's free-tier limits become a
problem in the future (very unlikely at Slicer-Liver's traffic
profile).

## Consequences

**Positive:**

- ADR ledger gets a proper TOC + search.  Cross-references between
  ADRs (e.g., "ADR-0013 §5" callouts that currently render as
  inline text) become live links.
- Architecture diagrams render in-place (PUML/MMD → SVG at build
  time).
- Dependency docs (`SlicerLayerDM.md` from PR #368) get a stable
  hosted URL contributors can link to from issues + reviews.
- API auto-generation (Python `autodoc`; later C++ via
  `Breathe`+`Doxygen`) becomes incrementally enable-able post-v2.0.0.
- External contributors landing on the docs see Slicer-family
  styling, not raw Markdown.
- Doc-CI catches link rot + MyST syntax errors before merge.

**Negative:**

- One more CI workflow to maintain (`docs-build.yml`).  Mitigation:
  the workflow mirrors Slicer-core's; the build itself is fast
  (~30s for a small tree).
- ReadTheDocs adds a third party to the dev loop (RTD itself goes
  down occasionally).  Mitigation: the build is also runnable
  locally via `make -C Docs html`, and the GitHub Actions docs job
  serves as the merge-gate (RTD is the *hosting*, not the *check*).
- `requirements-docs.txt` becomes another dependency surface to
  bump (Sphinx + extensions).  Mitigation: pin major versions only;
  Dependabot can submit minor-version bumps automatically.
- Migration PR (deferred) is moderate-effort: rewriting in-doc
  cross-references from raw paths to MyST-link form takes care
  across 20+ files.

## Rollout plan

1. **PR 1 (this ADR + scaffold)**:
   - `Docs/conf.py` (Sphinx config).
   - `Docs/index.md` (minimal entry stub).
   - `.readthedocs.yaml` (RTD build config).
   - `requirements-docs.txt` (Sphinx + extensions).
   - `.github/workflows/docs-build.yml` (CI build-only).
   - This ADR (0017).
   - No migration of existing `.md` content.

2. **PR 2 (migration)** — separate PR:
   - Move ADRs under a proper TOC (or keep at `Docs/adr/` with
     `toctree` references).
   - Move architecture diagrams under a "Architecture" chapter
     with rendered PUML/MMD.
   - Migrate dependency docs.
   - Populate `Docs/index.md` with the full TOC.
   - Wire up ReadTheDocs project (one-time admin step on the RTD
     side; the maintainer registers the project).

3. **PR 3+ (incremental polish)**:
   - Module-by-module documentation under `Docs/modules/`.
   - Python `autodoc` enable for `LiverResectionsLib`.
   - JSON schema rendering for the `.lrp.json` v1 schema from
     PR #361 via `sphinx-jsonschema`.

## Out of scope for this ADR

- C++ API reference via `Breathe`+`Doxygen`.  Deferred to v2.1.0.
- Search-index tuning beyond RTD defaults.
- Custom branding / logo / favicon (uses Slicer-Liver's existing
  `SlicerLiver.png`).
- Translation / i18n.  Slicer-Liver docs ship in English only for
  v2.0.0.

## Cross-references

<!--
  Cross-document links below point at the GitHub-rendered files
  rather than at MyST cross-refs.  The scaffold PR landing this
  ADR explicitly excludes the older ADRs from the Sphinx build
  (per conf.py's exclude_patterns), so MyST xref-resolution
  cannot reach them.  The migration follow-up swaps these for
  `[](file.md)` cross-refs once the ADRs join the toctree.
-->

- [ADR-0006](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0006-branch-model.md)
  — `preview` branch hosts the rendered docs at the `latest`
  version on RTD; `main` hosts a pinned snapshot per stable release.
- [ADR-0008](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0008-testing-strategy.md)
  §3 — `render_interactive` fixture pattern; once docs land, the
  dual-mode test pattern can link directly to a hosted "Run the
  demo" page.
- [ADR-0016](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0016-code-style-and-lint.md)
  — code style discipline precedent.  ADR-0017 is the docs-side
  equivalent: adopt upstream Slicer's infrastructure verbatim
  rather than invent.
- Upstream reference:
  [Slicer/Slicer Docs](https://github.com/Slicer/Slicer/tree/main/Docs)
  + [slicer.readthedocs.io](https://slicer.readthedocs.io/).
