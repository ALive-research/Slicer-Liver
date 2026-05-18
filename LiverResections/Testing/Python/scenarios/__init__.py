# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
# Visual-regression scenario modules for the LiverResections module.
#
# Each module here exposes the trio (``setup_scene``, ``setup_camera``,
# ``setup_viewport``) that both ``capture_baseline.py`` and
# ``replay_test.py`` consume — the capture flow produces a baseline
# bundle, the replay flow re-runs the same scenario in CI and asserts
# pixel-wise equivalence against the stored bundle.  Sharing the
# scenario module between the two flows is the single source of truth
# for what a baseline represents.
