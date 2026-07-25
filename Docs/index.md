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
adr/0019-resection-state-machine.md
adr/0020-gpu-tessellation.md
adr/0021-coverage-measurement.md
adr/0022-nurbs-v2-1-design.md
adr/0023-unified-gui-stage-workflow.md
adr/0024-segmentation-orchestration.md
adr/0025-locator-architecture.md
adr/0026-segment-editor-effects.md
adr/0027-invariant-test-first-v2-implementation.md
adr/0028-parameter-node-wrapper.md
adr/0029-stage1-case-setup-contract.md
adr/0030-ci-slicer-image-pinning.md
adr/0031-distance-map-input-on-resection-plan.md
adr/0032-v2-interaction-via-layerdm-pipeline-seam.md
adr/0033-control-polygon-display-aspect.md
adr/0034-stage2-segments-table.md
adr/0035-resection-init-state-machine.md
adr/0036-vessel-highlight-separate-instance.md
adr/0037-vascular-territories-off-markups.md
adr/0038-unify-control-point-interaction.md
```

```{toctree}
:maxdepth: 1
:caption: Design packages

design/resection-plan-architecture/00-overview.md
design/resection-plan-architecture/01-class-hierarchy.md
design/resection-plan-architecture/02-node-references.md
design/resection-plan-architecture/03-storage-ownership.md
design/resection-plan-architecture/04-save-load-flows.md
design/resection-plan-architecture/05-lrp-json-schema.md
design/resection-plan-architecture/06-pattern-and-audit.md
design/connected-tree-seeding-plan.md
design/multi-system-territory-plan.md
```

```{toctree}
:maxdepth: 1
:caption: UI architecture (per-stage)

architecture/ui-stage-1-case-setup.md
architecture/ui-stage-2-anatomy-definition.md
architecture/ui-stage-3-vascular-territories.md
architecture/ui-stage-4-resection-planning.md
architecture/ui-stage-5-volumetry.md
architecture/ui-stage-6-export.md
```

```{toctree}
:maxdepth: 1
:caption: Migrations

migrations/v1-to-v2.md
```
