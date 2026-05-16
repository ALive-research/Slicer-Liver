#!/usr/bin/env bash
#
# Validate commit-message subject against Slicer-Liver's strict
# commit-message convention (mirrors Slicer's slicer-check-commit-
# message-action regex per ADR-0016).
#
# Regex:  ^(ENH|PERF|BUG|STYLE|DOC|COMP): ([A-Z])+
#
# Installed as a pre-commit "commit-msg" stage hook by
#   ./Utilities/SetupForDevelopment.sh
# which runs `pre-commit install --hook-type commit-msg`.
#
# Pre-commit invokes this script with the path to the commit-message
# file (.git/COMMIT_EDITMSG) as the only argument.
#
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <path-to-commit-message-file>" >&2
  exit 2
fi

msg_file="$1"
subject="$(head -1 "$msg_file")"

# Allow fixup, squash, revert, and merge commits to pass without prefix
# check — these have well-known auto-generated subjects.
case "$subject" in
  fixup\!*|squash\!*|"Revert "*|"Merge "*)
    exit 0
    ;;
esac

# Slicer-strict regex.
if [[ ! "$subject" =~ ^(ENH|PERF|BUG|STYLE|DOC|COMP):\ [A-Z] ]]; then
  cat >&2 <<EOF

✗ Commit subject does not match the Slicer-Liver strict format.

Got:
    ${subject}

Expected:
    <PREFIX>: <Uppercase-First-Word> <rest of subject>

Where <PREFIX> is one of:
    ENH    Enhancement / new feature / additive improvement
    PERF   Performance improvement
    BUG    Bug fix / correctness fix
    STYLE  Mechanical reformat / lint cleanup
    DOC    Documentation / ADR / comment changes
    COMP   Compilation / build-system fix

Examples (good):
    ENH: Add display-node terminology field
    BUG: Restrict pre-commit lint to PR-touched files
    STYLE: Apply clang-format to touched files (lint cutover)
    DOC: ADR-0014 — rename vtkMRMLLiverBezierSurface*

Common mistakes:
- FIX: / TEST: / CI: are NOT in the strict vocabulary.
  - FIX: <bug>     -> BUG: ...
  - FIX: <build>   -> COMP: ...
  - TEST: <new>    -> ENH: Add ...
  - TEST: <fix>    -> BUG: ...
  - CI: <change>   -> ENH: / BUG: depending on intent
- The first non-space word after the colon MUST start with an
  uppercase letter.  Lowercase tool / class names trip the check:
    Bad:   STYLE: clang-format apply on touched files
    Good:  STYLE: Apply clang-format on touched files
    Bad:   ENH: vtkMRMLBezierSurfaceNode reparented
    Good:  ENH: Reparent vtkMRMLBezierSurfaceNode to vtkMRMLDisplayableNode

See CONTRIBUTING.md ("Commit message format") and
https://slicer.readthedocs.io/en/latest/developer_guide/style_guide.html#commits

If you really need to bypass this check (rare):
    git commit --no-verify
But: PR CI will re-run check-commit-message on every commit, so the
bypass only delays the failure.

EOF
  exit 1
fi

exit 0
