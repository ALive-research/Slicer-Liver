# Smoke test — docs-only CI filter

This file exists only to validate that the `non-docs` filter in
`.github/workflows/ci.yml` correctly skips the heavy `build-test`
job for pure-docs PRs (touching only `Docs/**`).

Per the `non-docs` filter introduced in the docs-only-filter
negation fix:

- A PR that touches **only** files matching `!Docs/**` (or the
  other allowed negations: `!*.md`, `!.readthedocs.yaml`,
  `!requirements-docs.txt`, etc.) should produce
  `steps.changes.outputs.non-docs == 'false'`.
- `build-test` is gated by `if: steps.changes.outputs.non-docs ==
  'true'` and therefore should not run.

This page can be safely deleted once the smoke test has confirmed
the behaviour.
