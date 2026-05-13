# NNNN. <Short imperative title>

- **Status:** Proposed | Accepted | Superseded by NNNN | Deprecated
- **Date:** YYYY-MM-DD
- **Deciders:** <names>
- **Diagrams:** <link to relevant `Docs/architecture/*.puml|mmd`>
- **PR:** <filled in on merge>

## Context

What is the problem? What forces are in play? What constraints (clinical,
regulatory, Slicer/VTK platform, performance, team capacity) bound the
solution space?

Cite specifics:

- Upstream Slicer behaviour (with a file path or commit).
- A clinical workflow assumption (with whose workflow).
- A VTK/CTK/ITK quirk (with the GitHub issue or Discourse thread).

## Decision

What did we decide? Be precise — name the modules, classes, MRML nodes, or
files affected. Reference the target diagram element that this decision
realises.

State the decision as a present-tense imperative:

> *"Resection geometry lives on a single `vtkMRMLLiverResectionNode` per
> resection. The previous split between a `Plan` node and a `Geometry`
> node is collapsed."*

## Alternatives considered

For each alternative seriously considered, one sub-section:

### Alternative A — <name>

What it would have looked like. Why we rejected it. Be specific about
the failure mode; future contributors will pattern-match on this.

### Alternative B — <name>

(repeat as needed)

## Consequences

What becomes easier? What becomes harder?  What followup work does this
imply (other ADRs, diagram updates, migration tasks)?  Where will the
seams of this decision show up — e.g., which classes now hold state they
didn't, which observers must be added or removed?

## References

- Slicer Discourse threads, GitHub issues, papers, internal notes.
- Related ADRs (e.g. *Supersedes 0003*, *Depends on 0005*).
- PKS permanent notes if the decision is informed by a permanent note
  (e.g. `~/pks/permanent/20260507T100903` style identifier).
