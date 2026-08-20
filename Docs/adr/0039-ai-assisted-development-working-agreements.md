# 0039. AI-assisted development working agreements

- **Status:** Accepted
- **Date:** 2026-08-20
- **Deciders:** Rafael Palomar
- **Relates to:**
  [ADR-0006](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0006-branch-model.md)
  (branch model — this ADR adds the integration-branch/sub-PR shape on
  top of it),
  [ADR-0005](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0005-github-actions-ci.md)
  (CI — whose unfiltered `pull_request` triggers already cover sub-PRs),
  and [ADR-0021](0021-coverage-measurement.md) (measurement posture).
- **PR:** _filled in on merge_

## Context

The Jul–Aug 2026 development campaign was our largest AI-assisted
effort to date and produced a measurable pathology alongside real
throughput: one review unit ballooned to ~15.6k changed lines across
84 commits as findings were appended to an open PR; ~23% of the
campaign's commits were `BUG:` fixes for code introduced by the same
campaign; and every consequential defect was caught by the maintainer
exercising the live application, not by the test suites or by review.
The maintainer's summary of the risk: *we do not want a repository
that can only be faced with the use of AI*.

The external evidence base points the same direction.  Review
effectiveness collapses beyond 200–400 changed lines
([SmartBear/Cisco study](https://static0.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf));
Google's review culture holds the median change near 24 lines
([Sadowski et al., ICSE-SEIP 2018](https://sback.it/publications/icse2018seip.pdf));
DORA finds AI adoption inflates batch size and taxes delivery
stability, and that AI *amplifies* the surrounding system rather than
fixing it ([DORA 2024/2025](https://dora.dev/research/));
a randomized trial found experienced maintainers on their own mature
repositories 19% *slower* with AI while believing themselves faster
([METR 2025](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/));
corpus data shows duplication and churn rising in the AI era
([GitClear 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research));
and passive delegation to AI measurably costs code comprehension
([arXiv:2601.20245](https://arxiv.org/abs/2601.20245)).  Peter Naur's
[*Programming as Theory Building*](https://pages.cs.wisc.edu/~remzi/Naur.pdf)
names the underlying failure mode: the program is the theory the team
holds, and generated text builds no theory in any human head.

Peer projects have already converged on policy: Ghostty requires AI
disclosure and holds that *the approver must be able to explain the
code*; QEMU scopes agent autonomy by change size and risk class.

## Decision

1. **Reviewable unit.**  A non-mechanical PR targets ≤ ~400 changed
   lines.  A PR freezes when opened: review and verification findings
   open a follow-up PR, never append to the one under review.
   (Mechanical sweeps — formatting, renames, generated files — are
   exempt when declared as such.)

2. **Integration branches replace stacked PRs.**  A multi-step feature
   opens `feature/<epic>` off `preview`.  Each increment is a sub-PR
   *based on the epic branch*, reviewed and merged there at the size
   above.  One final PR merges `feature/<epic>` into `preview`,
   rebase-merged so the reviewed structure survives; by then every
   hunk has been reviewed piecewise and the final PR carries a
   reviewer's map, not a wall.  Squash-merging members of a
   hand-stacked PR chain is what this replaces — it rewrites history
   under the remaining members.

3. **Cycle shape.**  Design → human sign-off → tests pinned →
   implementation.  For behaviour with a computable ground truth, a
   synthetic fixture with analytic expected values is built *before*
   the algorithm.  Design reviews run before v1, not after.

4. **Test integrity.**  An agent may not modify the tests that gate
   its own change.  Every behavioural feature carries at least one
   test on the real integrated path; suites that mock the integration
   surface are necessary but not sufficient.

5. **Merge bar (the Ghostty standard).**  A PR is mergeable only when
   a human can explain every hunk.  Agent-drafted PRs include a
   reviewer's map: suggested read order, and which hunks are
   mechanical versus load-bearing.

6. **Comment discipline.**  Comments state invariants, reasons, and
   ADR anchors.  Narrative retellings of change history belong in
   commit messages and PR bodies, not source files.

7. **ADR bar.**  New ADRs meet Nygard's criterion — the decision is
   contested and costly to reverse.  Design studies live under
   `Docs/design/` and may be marked superseded once code and tests
   carry the decision.

8. **Instrumentation.**  Each campaign records: largest PR size,
   rework ratio (`BUG:` commits fixing same-campaign code / total),
   and CI failures per PR.  Baseline (Jul–Aug 2026): 15.6k / 23% / 3.
   The next campaign must move all three.

9. **Autonomy by risk class.**
   - *Agent-led* (agent authors, human reviews): mechanical
     refactors, documentation, test scaffolds, fixes ≤ ~20 lines.
   - *Agent-drafted, human-walked-through*: UI and interaction code,
     MRML state lifecycles.
   - *Human-led* (agent assists only): architecture and
     safety-relevant semantics.

10. **Agent identity and attribution.**  Repository-resident agents
    commit under their own bot identity (the Claude GitHub App commits
    as `claude[bot]`), so authorship in history and the contributor
    graph is truthful.  Human-authored commits carry no AI trailers;
    AI-drafted PR bodies disclose the model used.  The
    GitHub-dialog agent (`@claude` in issues and PR threads) is
    triggerable only by users with write access, operates only within
    the *agent-led* risk class, opens its work as Draft PRs, and never
    flips Ready, approves, or merges — merge authority stays human.

## Consequences

- More PRs and more branch bookkeeping per feature; this is the
  deliberate price of keeping every reviewed unit inside the band
  where human review works.
- History and the contributor graph become honest about who wrote
  what; other developers can dispatch bounded agent work from GitHub
  without local tooling.
- Some raw generation throughput is given back.  The campaign data
  says a quarter of it was being repaid as rework anyway.

## Conformance

- [review] Reviewers bounce non-mechanical PRs over ~400 changed
  lines and appended-scope pushes to an open PR.
- [review] Sub-PRs target their epic branch; the epic→`preview` PR is
  rebase-merged.
- [review] Agent-drafted PR bodies name the model and include a
  reviewer's map; commit messages carry no AI trailers.
- [review] The `claude.yml` workflow keeps its scope: write-access
  trigger gate, agent-led task class, Draft PRs only, no edits to
  gating tests, no merge authority.
- [future] Automate the §8 metrics as a scheduled report.
- [future] Audit the existing ADR corpus against §7; migrate
  design-study ADRs to `Docs/design/`.
