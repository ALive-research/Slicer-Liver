# Architecture Decision Records (ADRs)

This directory holds the durable architectural decisions made for
Slicer-Liver.  Each ADR captures **one decision** in a form that is short,
self-contained, and diffable.

The format is Michael Nygard's classic
[Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
— see `0000-template.md`.

## When to write an ADR

Write one when **any** of the following is true:

- The decision is architectural (affects > 1 module or MRML node).
- There was a real alternative you rejected — capturing *why* saves future
  re-deliberation.
- The decision encodes a constraint a future contributor would not be able
  to infer from the code (a regulatory requirement, a Slicer/VTK quirk, a
  performance ceiling, a clinical workflow assumption).
- A reviewer (human or `/slicer-review`) keeps re-asking the same question
  across PRs — that question deserves an ADR answer.

Do **not** write one for: routine refactors, bug fixes, style changes, or
choices that are obvious from reading the resulting code.

## Numbering and lifecycle

- ADRs are numbered sequentially: `NNNN-kebab-case-title.md`.  Never
  renumber; the number is part of the ADR's permanent identity.
- Status starts as `Proposed`, becomes `Accepted` on merge, may later
  become `Superseded by NNNN` or `Deprecated`.
- An ADR is **append-only by convention**: if the decision needs to change,
  write a new ADR that supersedes it.  This preserves the audit trail.

## Linking and citation

- Link to relevant diagrams: `[target-mrml-node-hierarchy](../architecture/target-mrml-node-hierarchy.puml)`.
- Link to the PR that landed it (filled in after merge).
- Link to upstream Slicer/VTK issues or Discourse threads that informed the
  decision.

## How `/slicer-review` uses these

The `/slicer-review` command reads every ADR with status `Accepted` into the
review context.  A PR that contradicts an Accepted ADR receives a **blocking**
comment quoting the relevant ADR section.  If the PR is intentionally
superseding the ADR, that supersession must be explicit (new ADR added in the
same PR, old one updated to `Superseded by NNNN`).

## Authoring

```sh
# Find the next ADR number (handles the no-ADRs-yet case)
next=$(ls Docs/adr/[0-9][0-9][0-9][0-9]-*.md 2>/dev/null \
       | sed -E 's|.*/([0-9]{4})-.*|\1|' \
       | sort -n | tail -1)
n=$(printf '%04d' $(( ${next:-0} + 1 )))
cp Docs/adr/0000-template.md Docs/adr/${n}-<title>.md
```

Edit the new file, set Status to `Proposed`, fill in Context/Decision/
Consequences, link diagrams, open a PR.  On merge, change Status to
`Accepted` and add the PR link.
