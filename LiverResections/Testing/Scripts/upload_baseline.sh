#!/usr/bin/env bash
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Upload a captured visual-regression baseline bundle to the
# AliveTestingData release and rotate the matching `.sha512` content
# hash stubs in the Slicer-Liver repo.
#
# Usage:
#     ./LiverResections/Testing/Scripts/upload_baseline.sh <test-name> [tag]
#
# Where:
#     <test-name>   Matches a scenario module under
#                   LiverResections/Testing/Python/scenarios/
#                   (e.g. BezierSurface4x4Planning).
#     [tag]         Optional release tag override.  Defaults to
#                   ``liver-test-baselines-v1``.  Bump (-v2, -v3) when
#                   re-capturing all baselines after a Slicer/VTK/image
#                   bump (see ADR-0020 §"Rollout plan" §7).
#
# Preconditions:
#   * ``gh`` CLI authenticated with write access to
#     github.com/ALive-research/AliveTestingData.
#   * The capture flow (``capture_baseline.py``) has written
#     ``Testing/baselines-staging/<test-name>.{png,mrml,camera.json,viewport.json}``.
#
# Postconditions:
#   * Each staged file is uploaded as a release asset (named by its
#     SHA-512 hash).
#   * ``LiverResections/Testing/Data/Baseline/<test-name>.<ext>.sha512``
#     stubs are written / overwritten with the new content hashes.
#
# The script does NOT commit the .sha512 changes — the maintainer
# inspects the diff and commits in a follow-up step.

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  cat >&2 <<EOF
usage: $0 <test-name> [release-tag]
EOF
  exit 2
fi

TEST_NAME="$1"
RELEASE_TAG="${2:-liver-test-baselines-v1}"
REPO="ALive-research/AliveTestingData"

# Resolve repo root from this script's location.  The script lives at
# LiverResections/Testing/Scripts/upload_baseline.sh; the repo root is
# three levels up.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../../.." && pwd )"

STAGING_DIR="${REPO_ROOT}/Testing/baselines-staging"
STUB_DIR="${REPO_ROOT}/LiverResections/Testing/Data/Baseline"

BUNDLE_EXTS=(png mrml camera.json viewport.json)

# --------------------------------------------------------------------------- #
# Sanity checks
# --------------------------------------------------------------------------- #

if ! command -v gh >/dev/null 2>&1; then
  echo "error: 'gh' CLI not found on PATH" >&2
  exit 1
fi

if ! command -v sha512sum >/dev/null 2>&1; then
  echo "error: 'sha512sum' not found on PATH" >&2
  exit 1
fi

if [ ! -d "${STAGING_DIR}" ]; then
  cat >&2 <<EOF
error: no staging directory at ${STAGING_DIR}.
       Run capture_baseline.py first to produce the bundle.
EOF
  exit 1
fi

# Verify the release exists.  Print a helpful hint if it doesn't —
# bootstrapping the release is a one-time setup step described in
# Testing/README.md.
if ! gh release view "${RELEASE_TAG}" --repo "${REPO}" >/dev/null 2>&1; then
  cat >&2 <<EOF
error: release '${RELEASE_TAG}' not found on ${REPO}.
       Bootstrap with:
           gh release create ${RELEASE_TAG} --repo ${REPO} \\
             --title "Slicer-Liver visual-regression test baselines vN" \\
             --notes "Backing store for Testing/Data/Baseline/*.sha512 fixtures."
       See LiverResections/Testing/README.md §"Bootstrapping the release".
EOF
  exit 1
fi

mkdir -p "${STUB_DIR}"

# --------------------------------------------------------------------------- #
# Upload + stub-rotation loop
# --------------------------------------------------------------------------- #

for ext in "${BUNDLE_EXTS[@]}"; do
  src="${STAGING_DIR}/${TEST_NAME}.${ext}"
  if [ ! -f "${src}" ]; then
    echo "warning: staged file missing: ${src} — skipping ${ext}" >&2
    continue
  fi

  # Compute SHA-512 of the *content*; this is what CMake's
  # ExternalData resolves the .sha512 stub against.
  digest="$( sha512sum "${src}" | awk '{print $1}' )"

  # Release-asset filename is the digest itself — matches the URL
  # template wired in LiverResections/Testing/Python/CMakeLists.txt:
  #
  #     https://github.com/.../releases/download/<tag>/SHA512/<digest>
  #
  # ExternalData's default URL scheme places the algorithm directory
  # one level above the digest filename.  Slicer-core does the same.
  asset_name="${digest}"

  # Upload (--clobber so re-captures overwrite cleanly).  gh accepts
  # ``<localpath>#<assetname>`` to remap the asset name on upload.
  gh release upload "${RELEASE_TAG}" "${src}#${asset_name}" \
    --repo "${REPO}" --clobber

  # Write the stub.  Format is a single line: the digest (lowercase
  # hex).  Matches the CMake ExternalData expectation for ``.sha512``
  # stubs.
  echo "${digest}" > "${STUB_DIR}/${TEST_NAME}.${ext}.sha512"

  echo "  uploaded ${TEST_NAME}.${ext} (sha512=${digest:0:16}…)"
done

cat <<EOF

Fixture updated for ${TEST_NAME}.  Stubs rotated under:
    ${STUB_DIR}/

Next step: review the .sha512 diff and commit, e.g.

    git add LiverResections/Testing/Data/Baseline/${TEST_NAME}.*.sha512
    git commit -m "ENH: Capture ${TEST_NAME} visual-regression baseline"
EOF
