add_subdirectory(Cxx)

# Visual-regression test harness (per ADR-0003 + ADR-0020 §"Rollout plan" §7).
#
# Python-driven golden-image tests; baseline bundles are stored as
# release assets on the ALive-research/AliveTestingData repository
# (release tag ``liver-test-baselines-v1``) and resolved lazily via
# CMake ExternalData when the test runs.  See
# ``LiverResections/Testing/README.md`` for the full capture / replay
# workflow and the steps for bumping the baseline tag.
add_subdirectory(Python)
