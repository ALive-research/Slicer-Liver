# Contributing to Slicer-Liver

Thanks for taking the time to contribute! All types of contributions are encouraged and valued. It can be reporting a bug, proposing new features, submitting a fix, etc.

## How to help?

### Submitting code

We encourage you to submit pull requests as the preferred method for proposing changes to the codebase.

- Fork the [source code](https://github.com/ALive-research/Slicer-Liver)
- Build Slicer-Liver from the source code following [instructions](https://github.com/ALive-research/Slicer-Liver?tab=readme-ov-file#developers)
- **Run the development setup script once after cloning** — installs the local git hooks that enforce project style + commit-message conventions (see [Development setup](#development-setup) below).
- **Branch off `preview`** (the repository's default branch).  See [ADR-0006](Docs/adr/0006-branch-model.md) for the full branch model; the short version: new work targets `preview`; stable releases live on `main` and receive backports from `preview` periodically.
- Implement your changes, ensuring they adhere to the Python and C++ coding standards used in the project.
- Commit and push your changes with clear and descriptive messages (see [Commit message format](#commit-message-format)).
- Open a pull request **against `preview`**, clearly describing the changes you made and their purpose.

We look forward to reviewing your contributions!

### Development setup

After cloning, install `pre-commit` (once per machine) and run the
setup script (once per clone):

```bash
# Install pre-commit if you don't have it:
pipx install pre-commit        # recommended (isolates pre-commit + deps)
# or: pip install --user pre-commit
# or: brew install pre-commit
# or: sudo apt install pre-commit

# Install Slicer-Liver's git hooks into this clone:
./Utilities/SetupForDevelopment.sh
```

This installs two hook chains via `pre-commit`:

- **pre-commit stage** — clang-format, ruff, pyupgrade, trailing-whitespace, end-of-file-fixer, mixed-line-ending, JSON-schema validators, prettier (YAML), etc.  Enforced on the files you've touched.
- **commit-msg stage** — Slicer's strict commit-subject regex (see below).  Rejects non-conforming subjects at `git commit` time, before push, so you don't have to wait for CI to discover them.

Both chains are re-checked by CI (`Lint` and `check-commit-message` workflows) regardless — the local hooks just shorten the feedback loop.

To run the pre-commit chain ad-hoc against every file (e.g. before opening a PR):

```bash
pre-commit run --all-files
```

To bypass the hooks for an exceptional commit (rare; CI will still re-check on push):

```bash
git commit --no-verify
```

### Commit message format

Slicer-Liver follows Slicer's strict commit-subject format (see [ADR-0016](Docs/adr/0016-code-style-and-lint.md) and the upstream [Slicer style guide][slicer-style]):

```
<PREFIX>: <Uppercase-First-Word> <rest of subject>
```

Where `<PREFIX>` is one of:

| Prefix  | Use for                                                  |
|---------|----------------------------------------------------------|
| `ENH:`  | Enhancement / new feature / additive improvement         |
| `PERF:` | Performance improvement                                  |
| `BUG:`  | Bug fix / correctness fix                                |
| `STYLE:`| Mechanical reformat / lint cleanup                       |
| `DOC:`  | Documentation / ADR / comment changes                    |
| `COMP:` | Compilation / build-system fix                           |

**Two common mistakes the local commit-msg hook catches:**

1. **Wrong prefix**: `FIX:`, `TEST:`, `CI:` are **not** in the vocabulary.
   - `FIX: <bug>` → `BUG: ...`
   - `FIX: <build>` → `COMP: ...`
   - `TEST: <new test>` → `ENH: Add ...`
   - `TEST: <test fix>` → `BUG: ...`
   - `CI: <workflow>` → `ENH:` or `BUG:` depending on intent

2. **Lowercase first word after the colon**:
   - Bad:  `STYLE: clang-format apply on touched files` (lowercase `c`)
   - Good: `STYLE: Apply clang-format on touched files`
   - Bad:  `ENH: vtkMRMLBezierSurfaceNode reparented to ...` (lowercase `v`)
   - Good: `ENH: Reparent vtkMRMLBezierSurfaceNode to ...`

Examples (good):

```
ENH: Add display-node TerminologyEntry field (ADR-0011 + ADR-0013 §3)
BUG: Restrict pre-commit lint to PR-touched files
STYLE: Apply clang-format to touched files (lint cutover)
DOC: ADR-0014 — rename vtkMRMLLiverBezierSurface*
COMP: Resolve Eigen via ITK's bundled config
```

[slicer-style]: https://slicer.readthedocs.io/en/latest/developer_guide/style_guide.html#commits

### Report bugs

If you encounter a bug, we encourage you to report it so we can address the issue. To report a bug:

- Check the [issue tracker](https://github.com/ALive-research/Slicer-Liver/issues) to see if the bug has already been reported. If the bug has not been reported, create a new issue in the tracker.
- Include a clear and descriptive title for the issue.
Provide detailed steps to reproduce the bug, including the expected and actual outcomes.
- Specify the environment in which the bug occurred (e.g., operating system, version of Slicer-Liver, and any relevant dependencies).
- Attach any logs, screenshots, or additional information that can help in diagnosing the issue.

We appreciate your help in making Slicer-Liver better for everyone!

### Proposing new feature

We welcome suggestions for new features to improve Slicer-Liver. To propose a new feature:

- **Check existing suggestions**: Review the [issue tracker](https://github.com/ALive-research/Slicer-Liver/issues) to see if the feature has already been proposed.
- **Create a new issue**: If the feature has not been suggested, open a new issue in the tracker.
- **Provide a clear title**: Use a concise and descriptive title for the feature request.
- **Describe the feature**: Clearly explain the feature you are proposing, including its purpose and the problem it aims to solve.
Provide context: Include examples, mockups, or use cases that illustrate how the feature will be used.
- **Discuss potential implementation**: If you have ideas about how the feature could be implemented, include them in your description.

We value your input and look forward to collaborating on new ideas!

### If you have a question?

If you have a question about using or contributing to Slicer-Liver, we’re here to help!

- **Check the documentation**: Review the project [README](README.md) for guidance.
- **Search existing discussions**: Browse the [issue tracker](https://github.com/ALive-research/Slicer-Liver/issues) or [discussions](https://github.com/ALive-research/Slicer-Liver/discussions) to see if your question has already been answered.
- **Start a discussion**: If you can’t find an answer, create a new [discussion](https://github.com/ALive-research/Slicer-Liver/discussions). Clearly describe your question or concern.
- **Be specific**: Provide as much detail as possible about your question, including the context and any relevant information (e.g., version, environment, or steps you’ve taken).

We aim to build an inclusive and collaborative community, so don’t hesitate to reach out!
