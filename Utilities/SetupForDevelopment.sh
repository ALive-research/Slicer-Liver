#!/usr/bin/env bash
#
# Set up local git hooks for Slicer-Liver development.
#
# Mirrors Slicer's developer-setup pattern (per ADR-0016) but builds
# on top of the modern pre-commit framework rather than Slicer-core's
# legacy `hooks` branch.  All hook chains — pre-commit (clang-format,
# ruff, trailing-whitespace, …) and commit-msg (Slicer-strict subject
# regex) — are owned by `pre-commit` and configured in
# .pre-commit-config.yaml at the repo root.
#
# Usage:
#   ./Utilities/SetupForDevelopment.sh
#
# After running, every `git commit` in this clone runs the hook chain
# locally — catching style + commit-subject issues BEFORE push instead
# of on the CI gate.  CI re-checks regardless.
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

printErrorAndExit() {
  echo "✗ Setup failed: $*" 1>&2
  echo "  See https://pre-commit.com/#install" 1>&2
  exit 1
}

# 1. Verify pre-commit is installed.
if ! command -v pre-commit >/dev/null 2>&1; then
  cat <<'EOF' 1>&2
✗ pre-commit is not installed.

Install before running this script:

  # pipx (recommended, isolates pre-commit + its deps):
  pipx install pre-commit

  # or pip --user:
  pip install --user pre-commit

  # or a system package manager that ships it:
  #   apt:    sudo apt install pre-commit
  #   brew:   brew install pre-commit
  #   guix:   guix install python-pre-commit

Then re-run:
  ./Utilities/SetupForDevelopment.sh
EOF
  exit 1
fi

# 2. Confirm we're inside the Slicer-Liver clone.
if [ ! -f .pre-commit-config.yaml ]; then
  printErrorAndExit ".pre-commit-config.yaml not found in $ROOT (are you inside the Slicer-Liver clone?)"
fi

# 3. Make sure the local hook scripts are executable
#    (git mv / fresh clones may strip the +x bit on some filesystems).
chmod +x Utilities/Hooks/check-commit-message.sh
chmod +x Utilities/Hooks/check-copyright.sh

# 4. Install hooks (pre-commit + commit-msg stages).
echo "Installing pre-commit hooks (pre-commit + commit-msg stages)..."
pre-commit install --hook-type pre-commit --hook-type commit-msg

# 5. Record the setup version so we can prompt the developer to re-run
#    if this script (or the hook list) materially changes.  Mirrors
#    Slicer-core's `git config hooks.SetupForDevelopment` pattern.
SetupForDevelopment_VERSION=1
git config hooks.SetupForDevelopment "${SetupForDevelopment_VERSION}"

cat <<'EOF'

✓ Done.  Future `git commit` runs:
  - pre-commit hooks (clang-format, ruff, trailing-whitespace,
    end-of-file-fixer, mixed-line-ending, jsonschema, prettier, …)
  - commit-msg hook (Slicer-strict subject regex
    ^(ENH|PERF|BUG|STYLE|DOC|COMP): ([A-Z])+)
  - copyright-year hook on staged source files
    (.cpp .cxx .h .hpp .hxx .txx .py — old files untouched)

Run all hooks against every file ad-hoc (e.g. before a PR):
  pre-commit run --all-files

Run hooks against only the staged change set:
  pre-commit run

Bypass hooks for an exceptional commit (rare; CI re-checks):
  git commit --no-verify

See CONTRIBUTING.md → "Development setup" for the full convention
decoder ring (prefix mapping, first-word rule, etc.).
EOF
