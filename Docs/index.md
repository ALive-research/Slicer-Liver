# Slicer-Liver

Slicer-Liver is a 3D Slicer extension for liver analysis and therapy
planning.  This documentation site is the rendered surface of the
project's committed architectural ledger + dependency notes.

:::{note}
This site is in **scaffold state**.  The full content migration from
the project's existing Markdown tree (`Docs/adr/`,
`Docs/architecture/`, `Docs/dependencies/`) into a navigable Sphinx
TOC is the next step — tracked under the migration follow-up to
[ADR-0017](adr/0017-sphinx-readthedocs.md).  Until then this page
acts as the entry point and the existing `Docs/**/*.md` files
remain the canonical reading material via direct file browsing on
GitHub.
:::

## Project links

- [Source repository](https://github.com/ALive-research/Slicer-Liver)
- [Architecture Decision Records](https://github.com/ALive-research/Slicer-Liver/tree/preview/Docs/adr)
  — committed under `Docs/adr/`.
- [Architecture diagrams](https://github.com/ALive-research/Slicer-Liver/tree/preview/Docs/architecture)
  — committed under `Docs/architecture/`.
- [Dependency notes](https://github.com/ALive-research/Slicer-Liver/tree/preview/Docs/dependencies)
  — committed under `Docs/dependencies/`.

## Documentation infrastructure

The build is described in [ADR-0017](adr/0017-sphinx-readthedocs.md):
Sphinx with MyST/Markdown source, `sphinx_rtd_theme`, hosted on
ReadTheDocs.  Mirrors the upstream Slicer-core convention.

```{toctree}
:maxdepth: 1
:caption: Scaffold

adr/0017-sphinx-readthedocs.md
adr/0018-nurbs-extension-surface.md
```
