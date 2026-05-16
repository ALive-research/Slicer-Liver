#!/usr/bin/env bash
#
# Validate that every staged source file carries a year-bearing
# copyright line.  Mirrors the commit-message validator pattern in
# this directory (see check-commit-message.sh).
#
# Regex (intentionally loose):
#   Copyright \(c\) [12][0-9]{3}
#
# Examples that pass:
#   Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.
#   Copyright (c) 2017-2024 The XYZ Project.
#   Copyright (c) 1999 Kitware Inc.
#
# Examples that fail:
#   Copyright (c) Oslo University Hospital. All rights reserved.
#   (no Copyright line at all)
#
# Pre-commit invokes this script with the list of staged files that
# match the `files:` regex in .pre-commit-config.yaml.  Only those
# files are checked — old, untouched files keep their year-less form
# until the bulk reformat (issue #338) lands.  Bypass with
# `git commit --no-verify` only if you have a reason; CI re-runs the
# same hook on the PR diff.
#
set -euo pipefail

if [ "$#" -lt 1 ]; then
  # Pre-commit may invoke with no files when nothing matches; treat
  # that as success.
  exit 0
fi

failed=()

for f in "$@"; do
  if [ ! -f "$f" ]; then
    # File removed in the staged change set; skip.
    continue
  fi

  # Scan only the first 30 lines — copyright headers always live at
  # the top of the file.  Avoids scanning multi-MB generated files.
  if ! head -n 30 "$f" | grep -E -q 'Copyright \(c\) [12][0-9]{3}'; then
    failed+=("$f")
  fi
done

if [ "${#failed[@]}" -gt 0 ]; then
  cat >&2 <<EOF

✗ Copyright header missing a year on the following staged file(s):

$(printf '    %s\n' "${failed[@]}")

Slicer-Liver source files must carry a year-bearing copyright line in
the file header.  Match the legacy in-project precedent on
LiverResections/MRML/vtkMRMLLiverResectionNode.cxx (2017):

    Copyright (c) YYYY, The Intervention Centre, Oslo University Hospital. All rights reserved.

For files spanning multiple years, ranges are fine:

    Copyright (c) 2017-2024, The Intervention Centre, Oslo University Hospital. All rights reserved.

The check looks only at the first 30 lines of each touched file and
fires the regex:

    Copyright \(c\) [12][0-9]{3}

Existing year-less files in the tree are NOT touched by this hook;
they migrate when the bulk-reformat in issue #338 lands.  Only files
you are currently staging are validated.

To bypass for an exceptional commit (rare; CI re-checks):
    git commit --no-verify

EOF
  exit 1
fi

exit 0
