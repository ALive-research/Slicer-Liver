# Slicer-Liver Architecture Diagrams

This directory holds **architectural intent** for Slicer-Liver as committed,
diffable text.  It is the *spec* that code is reviewed against — not after-the-
fact documentation.

## What lives here

Source-form diagrams only, embedded in Markdown so GitHub renders them
inline in PR reviews.

Every diagram is a Markdown file containing a fenced ```` ```mermaid ````
block.  GitHub renders the fence natively, so reviewers see the diagram
inside the PR diff with no extra click and no `.svg` artefact to keep
in sync.  Mermaid covers what we need: class hierarchies, sequence /
observer flows, module dependency graphs, state machines.

Each `.md` diagram file should have:

1. A short title and one-paragraph description.
2. The fenced Mermaid block as the canonical source.
3. A reading guide (legend) explaining the arrow conventions in plain
   prose.

## Naming convention

Diagrams come in two flavours, distinguished by filename prefix:

| Prefix | Meaning | Example |
|---|---|---|
| `current-` | The code as it is **today**.  Snapshot, evolves slowly. | `current-mrml-node-hierarchy.md` |
| `target-` | The architecture the refactor is moving **toward**. | `target-mrml-node-hierarchy.md` |

When `target-X` matches reality, drop the prefix (or convert it to
`current-X`) — that's how progress on a refactor is recorded.

## What to draw

Minimum useful set for any non-trivial Slicer extension:

1. **MRML node hierarchy** — every `vtkMRMLLiver*Node` and its base.  Annotate
   nodes with their lifetime owner (logic class) and the displayable manager
   that draws them.
2. **Module dependency graph** — which `qSlicerLiver*Module` depends on which.
   Reveals cycles and tangles.
3. **Observer/event flow** — sequence diagram for the most non-obvious
   interaction (e.g. resection edit → MRML modified → DM redraw → save).
4. **External integration boundary** — for SlicerSOFA, where SOFA's scene
   graph meets MRML; for Slicer-Liver, where solver outputs land in
   `vtkMRMLLiverResectionNode`.

## Review-time use

The diagrams in this directory are the **spec** a human reviewer reads
when judging whether a PR's code change preserves, advances, or drifts
from the intended architecture.  The rules of thumb a reviewer applies:

- A PR that introduces a new `vtkMRMLLiverFooNode` without updating
  `target-mrml-node-hierarchy.md` is **drift**.
- A PR that matches a `target-*` diagram **advances** the design.
- A PR that touches code referenced by a `current-*` diagram should
  update that diagram in the same PR (or justify what changed in an
  ADR).

An **optional** Claude Code slash-command,
[`/slicer-review`](https://github.com/OUH-MESHLab/slicer-review),
reads this directory into review context and applies the same rules
of thumb (plus Slicer-specific MRML/VTK correctness checks).  It is
one reviewer's tool, **not a project-wide gate**, and contributors
are not expected to install or run it — the rules above stand on
their own for any reviewer.

The skill is maintained as a separate, reusable repository under the
[OUH-MESHLab](https://github.com/OUH-MESHLab) organisation rather
than vendored here, since it applies generically across 3D Slicer
extension repositories.  See its README for installation and use.

## Authoring

Mermaid source is plain text inside a fenced Markdown block — author
with any text editor.  GitHub renders the fence on push; no local
toolchain is needed for reviewing.

Optional local preview tools:

- **Browser-based**: paste the fence content into
  https://mermaid.live for an immediate preview.
- **Editor plugins**: VS Code (`bierner.markdown-mermaid`), Emacs
  (`ob-mermaid`), IntelliJ (`mermaid` plugin).
- **CLI**: `mmdc` (mermaid-cli) for export to SVG/PNG when needed —
  rarely necessary now that GitHub renders fences.

## Relationship to ADRs

Diagrams show **shape**.  ADRs (`../adr/`) show **why that shape**.  Each
`target-*` diagram should be referenced by at least one ADR that justifies
its design and lists rejected alternatives.
