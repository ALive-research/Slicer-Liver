#!/usr/bin/env bash
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Stage a captured visual-regression baseline bundle for upload to the
# ALive-research/ALiveResearchTestingData repository (SlicerTestingData
# mirror pattern) and rotate the matching ``.sha512`` content-hash
# stubs in the Slicer-Liver repo.
#
# ALiveResearchTestingData's convention (per its README):
#
#   * One release per hash algorithm, named ``<HASHALGO>`` (``SHA256``,
#     ``SHA512``, etc.).
#   * Release assets are named by their ``<hashsum>`` — no
#     per-purpose prefix, no per-bundle tag.
#   * A sibling ``<HASHALGO>.csv`` in the repo root maps
#     ``<hashsum>;<filename>``.
#   * Files are added by dropping them into ``INCOMING/`` and running
#     ``process_release_data.py upload --hashalgo SHA512`` in the
#     testing-data repo working copy.
#
# This script does NOT push directly to the release.  It performs the
# Slicer-Liver-side work (compute hashes, write stubs, stage files for
# the canonical INCOMING upload):
#
#   1. Computes SHA-512 of each staged bundle artefact.
#   2. Writes ``LiverResections/Testing/Data/Baseline/<test>.<ext>.sha512``
#      stubs with the digests.
#   3. Copies the staged artefacts to the path the maintainer points
#      ``ALIVE_TESTING_DATA_INCOMING`` at (typically a local checkout's
#      ``INCOMING/`` directory).
#   4. Prints the canonical next step:
#
#         cd $ALIVE_TESTING_DATA_INCOMING/.. && \\
#           python process_release_data.py upload --hashalgo SHA512 \\
#                                                 --github-token $GH_TOKEN
#
#   The maintainer runs the canonical script + commits the CSV update
#   on the testing-data repo side, then commits the ``.sha512`` stub
#   changes on the Slicer-Liver side.
#
# Usage:
#     ./LiverResections/Testing/Scripts/upload_baseline.sh <test-name>
#
# Where:
#     <test-name>   Matches a scenario module under
#                   LiverResections/Testing/Python/scenarios/
#                   (e.g. BezierSurface4x4Planning).
#
# Environment:
#     ALIVE_TESTING_DATA_INCOMING  Path to a local checkout of
#         ALive-research/ALiveResearchTestingData's INCOMING/
#         directory.  Required.
#
# Preconditions:
#   * The capture flow (``capture_baseline.py``) has written all four
#     bundle artefacts to
#     ``Testing/baselines-staging/<test-name>.{png,mrml,camera.json,viewport.json}``.
#
# Postconditions:
#   * Bundle-completeness pre-flight passed (all four sidecars present).
#   * ``.sha512`` stubs written / overwritten with the new content
#     hashes.
#   * Bundle artefacts copied to ``$ALIVE_TESTING_DATA_INCOMING``.
#
# The script does NOT commit the .sha512 changes — the maintainer
# inspects the diff and commits in a follow-up step.

set -euo pipefail

if [ "$#" -ne 1 ]; then
  cat >&2 <<EOF
usage: $0 <test-name>

Set ALIVE_TESTING_DATA_INCOMING to the local INCOMING/ directory of
a checkout of github.com/ALive-research/ALiveResearchTestingData
before running.
EOF
  exit 2
fi

TEST_NAME="$1"

if [ -z "${ALIVE_TESTING_DATA_INCOMING:-}" ]; then
  cat >&2 <<EOF
error: ALIVE_TESTING_DATA_INCOMING is not set.

Point it at the INCOMING/ directory of a local checkout of
github.com/ALive-research/ALiveResearchTestingData, e.g.

    export ALIVE_TESTING_DATA_INCOMING=~/src/ALiveResearchTestingData/INCOMING

See LiverResections/Testing/README.md §"Bootstrapping a local
testing-data clone" for the one-time setup.
EOF
  exit 1
fi

if [ ! -d "${ALIVE_TESTING_DATA_INCOMING}" ]; then
  echo "error: ALIVE_TESTING_DATA_INCOMING does not exist: ${ALIVE_TESTING_DATA_INCOMING}" >&2
  exit 1
fi

if ! command -v sha512sum >/dev/null 2>&1; then
  echo "error: 'sha512sum' not found on PATH" >&2
  exit 1
fi

# Resolve repo root from this script's location.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../../.." && pwd )"

STAGING_DIR="${REPO_ROOT}/Testing/baselines-staging"
STUB_DIR="${REPO_ROOT}/LiverResections/Testing/Data/Baseline"

# Canonical bundle composition.  A baseline is a *reproducible recipe*
# (not just a screenshot): the .png is the comparison target; the
# .mrml + .camera.json + .viewport.json sidecars are the audit
# artefacts that pin what scenario state produced those pixels.  Per
# the project's documented bundle-completeness contract, partial
# bundles are rejected — uploading 2 of 4 leaves the harness pointing
# at a structurally invalid baseline.
BUNDLE_EXTS=(png mrml camera.json viewport.json)

if [ ! -d "${STAGING_DIR}" ]; then
  cat >&2 <<EOF
error: no staging directory at ${STAGING_DIR}.
       Run capture_baseline.py first to produce the bundle.
EOF
  exit 1
fi

# Bundle-completeness pre-flight.  Refuse to proceed on a partial
# bundle (per the /slicer-review GAP-4 finding on PR #384).
missing=()
for ext in "${BUNDLE_EXTS[@]}"; do
  if [ ! -f "${STAGING_DIR}/${TEST_NAME}.${ext}" ]; then
    missing+=("${TEST_NAME}.${ext}")
  fi
done
if [ "${#missing[@]}" -gt 0 ]; then
  cat >&2 <<EOF
error: incomplete bundle for ${TEST_NAME} — missing sidecars:
$(printf '  %s\n' "${missing[@]}")

A baseline must be a complete recipe (PNG + MRML + camera + viewport
sidecars).  Re-run capture_baseline.py and ensure 's' was pressed in
the capture window so every sidecar got written.
EOF
  exit 1
fi

# DRY_RUN=1 short-circuits the destructive operations (hashing, stub
# writes, INCOMING copies) AFTER the pre-flight passes.  Used by the
# harness self-tests under
# ``LiverResections/Testing/Python/test_harness/`` to characterise
# the bundle-completeness gate without polluting the repo's
# ``Data/Baseline/`` directory or the maintainer's INCOMING/.
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "dry-run: bundle complete for ${TEST_NAME}; would stage to ${ALIVE_TESTING_DATA_INCOMING}/"
  exit 0
fi

mkdir -p "${STUB_DIR}"

# --------------------------------------------------------------------------- #
# Two-pass: hash every file first, then stage all atomically.  Per the
# /slicer-review GAP-5 finding, the prior interleaved upload→stub loop
# could leave the bundle internally inconsistent on partial failure;
# the all-or-nothing two-pass shape prevents that.
# --------------------------------------------------------------------------- #

declare -a digests
declare -a srcs
for ext in "${BUNDLE_EXTS[@]}"; do
  src="${STAGING_DIR}/${TEST_NAME}.${ext}"
  digest="$( sha512sum "${src}" | awk '{print $1}' )"
  digests+=("${digest}")
  srcs+=("${src}")
done

# Stage to INCOMING (atomic per file, but the loop is now read-only on
# the staging dir; no half-written state on the testing-data side).
for i in "${!BUNDLE_EXTS[@]}"; do
  ext="${BUNDLE_EXTS[$i]}"
  src="${srcs[$i]}"
  cp -f "${src}" "${ALIVE_TESTING_DATA_INCOMING}/${TEST_NAME}.${ext}"
done

# Write all stubs.
for i in "${!BUNDLE_EXTS[@]}"; do
  ext="${BUNDLE_EXTS[$i]}"
  digest="${digests[$i]}"
  echo "${digest}" > "${STUB_DIR}/${TEST_NAME}.${ext}.sha512"
  printf '  staged %s (sha512=%s…)\n' "${TEST_NAME}.${ext}" "${digest:0:16}"
done

cat <<EOF

Bundle staged for ${TEST_NAME}.

Stubs rotated under:
    ${STUB_DIR}/

Files copied to:
    ${ALIVE_TESTING_DATA_INCOMING}/

Next step — push to the ALiveResearchTestingData SHA512 release:

    cd $( dirname "${ALIVE_TESTING_DATA_INCOMING}" )
    python process_release_data.py upload --hashalgo SHA512 \\
                                          --github-token "\$GH_TOKEN"
    # process_release_data.py: hashes files in INCOMING/, uploads
    # them as release assets named by their hash, appends to
    # SHA512.csv, regenerates SHA512.md.  Commit the CSV update.

Then on the Slicer-Liver side:

    git add LiverResections/Testing/Data/Baseline/${TEST_NAME}.*.sha512
    git commit -m "ENH: Capture ${TEST_NAME} visual-regression baseline"
EOF
