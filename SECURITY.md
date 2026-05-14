# Security Policy

Slicer-Liver is a research-grade 3D Slicer extension for liver-surgery
planning.  It is **not a certified medical device** and must not be used
for clinical decision-making outside an explicit research protocol.
Even so, defects that could mislead a surgical-planning workflow are
treated as security-relevant — bugs that silently produce wrong
volumetry, distance, or resection geometry are in scope.

## Supported versions

Security fixes are applied to the **active publishing branch** for each
3D Slicer release line:

| 3D Slicer | Slicer-Liver publishing branch |
|---|---|
| 5.10 (stable) | `preview` |
| Slicer main / preview | `preview` |
| 5.6 / 5.8 (legacy) | `master` |

PRs against the `preview` branch (the default branch of this
repository) are reviewed and merged following the project's normal
process.  Older publishing branches receive fixes on a best-effort
basis.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security reports.**
Information that could be exploited to mislead a clinician should not
be disclosed publicly until a fix is available.

Report directly to:

> Rafael Palomar — <rafael.palomar@ous-research.no>

Include, when possible:

- A clear description of the issue and its impact on the workflow.
- Steps to reproduce (sample data, MRML scene, or `.lrp.fcsv` if
  needed; do not share patient data — synthesise or anonymise).
- The Slicer-Liver and 3D Slicer versions you observed it on.
- Any logs, screenshots, or stack traces.

You can expect an initial acknowledgement within **10 business days**.
This project is maintained on academic time; a longer turnaround is
possible if the report arrives during conference periods or grant
deadlines — your report is still being taken seriously.

## Coordinated disclosure

We prefer coordinated disclosure: once a fix lands on the publishing
branch and propagates through the Slicer Extension Manager nightly
build, the original report can be acknowledged in the release notes
(with the reporter's permission and credit, if desired).

If you have a specific disclosure deadline, please state it in your
initial report; we will work toward it in good faith.

## Out of scope

- Issues in 3D Slicer itself — report those at
  <https://github.com/Slicer/Slicer/security>.
- Issues in third-party Python dependencies installed via
  `slicer.util.pip_install` — report upstream first; Slicer-Liver
  will pick up upstream fixes via dependency pin updates.
- Generic build or packaging failures that do not have a security
  impact — those belong on the issue tracker.
