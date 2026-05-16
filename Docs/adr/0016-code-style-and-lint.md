# 0016. Code style discipline and CI enforcement (adopt Slicer's infrastructure)

- **Status:** Proposed
- **Date:** 2026-05-16
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver v2.0.0 work has shifted to an agentic-development pattern
(see PRs #301–#334, T1-A through T2 Stack 1).  Agents produce code
that compiles and tests pass but often diverges from project
conventions — brace style, header guards, naming, indentation,
trailing whitespace, line endings, Python idiom drift.  Each
divergence is small; aggregated across a release cycle they shift
human-reviewer load from *"is this architecturally right?"* to
*"are these braces in the wrong place?"*.  Style noise drowns out
substance feedback exactly when substance review matters most.

Slicer itself solved this problem.  Upstream
[`Slicer/Slicer`](https://github.com/Slicer/Slicer) ships:

- `.clang-format` (Mozilla-based with overrides — Allman braces,
  `ColumnLimit: 180`, sorted includes, `BreakBeforeBraces: Allman`,
  templates always broken, etc.).
- `.pre-commit-config.yaml` orchestrating:
  - `pre-commit/pre-commit-hooks` general checks (large files, merge
    conflict markers, end-of-file fixer, mixed-line-ending, trailing
    whitespace, YAML syntax, debug-statement detection).
  - `astral-sh/ruff-pre-commit` for Python lint + autofix.
  - `pre-commit/mirrors-clang-format` for C++ formatting.
  - `asottile/pyupgrade` to keep Python idioms current (`--py312-plus`).
  - `pre-commit/mirrors-prettier` for YAML.
  - `python-jsonschema/check-jsonschema` for Dependabot + workflow
    schema validation.
- `.github/workflows/lint.yml` running `pre-commit/action@v3.0.1` on
  every PR.  The action's default behaviour is to run hooks only on
  PR-touched files — built-in gradual cutover; existing un-reformatted
  files are grandfathered until something touches them.
- `.github/workflows/commit-message.yml` running Slicer's own
  `slicer-check-commit-message-action` so commit subjects follow the
  project's `STYLE:` / `BUG:` / `ENH:` / `DOC:` / `FIX:` / `COMP:` /
  `TEST:` prefix convention.
- `.git-blame-ignore-revs` listing bulk-reformat commits so
  `git blame` skips past mechanical changes.

The conventions and tools are stable, well-tested across years of
upstream Slicer development, and applied uniformly to extensions
maintained inside the Slicer organization.  Re-deriving any of this
from first principles would duplicate upstream maintenance for zero
project-specific value.

## Decision

Slicer-Liver **mirrors Slicer's style enforcement infrastructure
verbatim**, adapted only for repository-specific paths (branch refs).
Specifically:

1. **`.clang-format`** — copied verbatim from upstream Slicer.
2. **`.pre-commit-config.yaml`** — copied verbatim from upstream
   Slicer (same hooks, same versions, same exclusions).
3. **`.github/workflows/lint.yml`** — copied from upstream Slicer with
   one adaptation: branch references changed from `main` to `preview`
   to match Slicer-Liver's branch model (per
   [ADR-0006](0006-branch-model.md)).
4. **`.github/workflows/commit-message.yml`** — same: branch ref
   adaptation only.  Uses upstream's
   `Slicer/slicer-check-commit-message-action` directly.
5. **`.git-blame-ignore-revs`** — initially empty (or carrying only a
   header note); entries appended when bulk-reformat commits land.

### Cutover discipline

The `pre-commit/action`'s default behaviour — run hooks only on
PR-touched files — gives us automatic gradual cutover: new code is
enforced from this ADR forward, existing un-reformatted code is
grandfathered until something touches it.

Per-module **bulk-reformat commits** are expected to land as part of
the LayerDM migration cascade:

- **T2 Stack 7** (LiverMarkups retirement + LiverResections rewrite)
  ships a `STYLE:` commit reformatting all of `LiverResections/` and
  the new `Algorithm/` subdirectory in one shot.
- **v2.1.0 LayerDM expansions** (per ADR-0012's deferred modules)
  reformat their target module the same way.

Each bulk-reformat commit is appended to `.git-blame-ignore-revs` so
`git blame` for the affected lines reports the substantive author who
last touched the logic, not the mechanical reformat.

### Upstream-tracking discipline

When Slicer updates its `.clang-format` or `.pre-commit-config.yaml`,
Slicer-Liver mirrors the change within a reasonable cadence
(target: within one release cycle, or sooner if the change fixes a
correctness bug).  Mirroring is a mechanical diff-and-apply, not a
re-design discussion.  Significant divergence from upstream is itself
a decision warranting a follow-on ADR.

### For agentic development specifically

Agents producing Slicer-Liver code:

1. **Locally**: run `pre-commit run --all-files` before pushing.  The
   pre-commit hook surfaces and (where possible) auto-fixes style
   issues *before* the CI gate sees them.
2. **On the CI gate**: the `lint.yml` workflow re-runs the hooks on
   PR-touched files.  If the agent's push omitted the local
   pre-commit run, CI fails with a clear diff showing what's wrong;
   the agent (or a follow-on agent) re-runs the formatter and pushes
   a fixup commit.
3. **In agent prompts**: the orchestrating session should mention
   "run `pre-commit run --all-files` before opening the PR" in the
   standard agent brief.  Future iteration may bake this into a
   pre-PR-push checklist captured in `~/.claude/projects/<…>/memory/`.

## Alternatives considered

### A. Roll our own style configuration

Pick `.clang-format` knobs from first principles, adopt only the
subset of pre-commit hooks Slicer-Liver "needs", maintain the lint
workflow independently of upstream.

**Rejected** because the upstream Slicer infrastructure is the
working answer to a problem the Slicer ecosystem has already solved.
Duplicating it means signing up to track upstream's improvements
manually, drift from upstream conventions, and surface a different
style "feel" to contributors who also work on Slicer core or other
Slicer extensions.  No project-specific value justifies the
divergence.

### B. Defer until v2.1.0

Keep style enforcement informal for v2.0.0 (relying on reviewer
attention), introduce the tooling in v2.1.0 after T2 settles.

**Rejected** because the cost of setting it up now is small (one ADR
+ one tooling PR) and the cost-savings compound across every agent-
produced PR from this ADR forward.  The longer we wait, the more
un-reformatted code accumulates and the larger the eventual
reformat cost.

### C. Lint-on-all-files instead of lint-on-PR-touched-files

Configure the CI workflow to run `pre-commit run --all-files`
unconditionally, forcing the entire codebase to conform at the
moment this ADR lands.

**Rejected** because the existing C++ in `Liver/`, `LiverMarkups/`,
`LiverResections/`, `LiverSegments/`, `LiverVolumetry/` doesn't yet
conform to Slicer's `.clang-format`.  A big-bang reformat would
either gate this ADR on doing the reformat first (delaying the
benefit for unrelated PRs) or generate a wall of CI failures on
every PR that touches existing files.  The `pre-commit/action`
default — touch-list-only — is the gradual-cutover path that
sidesteps both pains.

### D. Pre-commit only, no CI gate

Install the pre-commit hook locally; trust contributors to run it
before push; no CI enforcement.

**Rejected** because agentic development weakens the trust premise.
Local pre-commit hooks only fire if the contributor's environment is
configured for them; an agent running in a fresh worktree does not
have the hook installed unless its prompt arranges it.  The CI gate
is the load-bearing enforcement.  Local pre-commit is the developer-
ergonomics layer on top.

## Consequences

### Easier

- **Review load shifts from style to substance.**  Reviewers stop
  flagging brace placement and start engaging with architecture.
- **Agentic-PR review becomes mechanical at the style layer.**  An
  agent's PR either passes the lint gate (style is conformant by
  definition — the formatter ran) or it doesn't (the agent or a
  follow-up agent runs `pre-commit run --all-files`, commits the
  result, re-pushes).
- **Upstream-aligned developer experience.**  Anyone who has worked
  on Slicer core or another Slicer-org extension finds the same
  conventions, the same hook list, the same commit-message
  expectations.
- **`git blame` stays useful** across the bulk-reformat commits
  because of `.git-blame-ignore-revs`.

### Harder

- **One more required CI check** (`lint`).  Branch protection on
  `preview` may need to add it to its required-status-checks list
  once configured.
- **First-time contributor setup** requires installing pre-commit
  (`pip install pre-commit; pre-commit install`).  Document in
  CONTRIBUTING.md (separate small PR) and in agent briefs.
- **Bulk-reformat commits disrupt `git blame`** at the line-history
  level, but `.git-blame-ignore-revs` mitigates this for any tool
  that respects it (GitHub's blame UI does; most editors do).
- **Upstream-tracking discipline** is a recurring small task — when
  Slicer bumps `clang-format` version or adds a hook, this project
  needs to mirror within a reasonable cadence.  Schedule as a
  quarterly mirror review at the start; revisit cadence if it
  becomes friction.

## Open questions

These do not block adoption:

- **Branch protection** — should `lint` join `build-test` as a
  required status check on `preview`?  Deferred to a separate
  branch-protection PR (independent of this ADR).
- **CONTRIBUTING.md update** — adding a "First-time setup: install
  pre-commit" line is a separate small PR.
- **Commit-message format strictness** — the upstream
  `slicer-check-commit-message-action` enforces a specific prefix
  vocabulary (`STYLE:`, `BUG:`, `ENH:`, etc.).  Existing
  Slicer-Liver commit history is mostly conformant but not
  universally; the action may flag historical-style commits when
  PRs include them.  Tolerable; the action operates on commits
  in the PR, not on `preview`'s entire history.

## References

- [Slicer's style guide](https://slicer.readthedocs.io/en/latest/developer_guide/style_guide.html)
  — narrative documentation of the conventions enforced by the
  tooling adopted in this ADR.
- [`Slicer/Slicer` `.clang-format`](https://github.com/Slicer/Slicer/blob/main/.clang-format)
  — the source-of-truth file copied verbatim.
- [`Slicer/Slicer` `.pre-commit-config.yaml`](https://github.com/Slicer/Slicer/blob/main/.pre-commit-config.yaml)
  — the source-of-truth hook orchestration.
- [`pre-commit/action`](https://github.com/pre-commit/action) — the
  GitHub Action used by `lint.yml`.
- [`Slicer/slicer-check-commit-message-action`](https://github.com/Slicer/slicer-check-commit-message-action)
  — the commit-message action.
- [ADR-0005](0005-github-actions-ci.md) — establishes the GitHub
  Actions CI workflow this lint job joins.
- [ADR-0006](0006-branch-model.md) — the branch model
  (`main` / `preview`) the workflow's branch refs adapt to.
- [ADR-0008](0008-testing-strategy.md) — test discipline parallel
  to this ADR's style discipline.
- [ADR-0009](0009-ux-and-design-discipline.md) — review-blocking
  discipline ancestor; this ADR is the analogous discipline for
  *style*, just as ADR-0003 is for *behaviour testability*.
