# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

# Slicer-driven Python wrapper test for the v2.0.0 territories node
# hierarchy (ADR-0023 §"Class abstraction for territories").  Pins the
# Python-side polymorphic dispatch + Subject Hierarchy folder
# placement invariants; the C++ low-level tests pin the rest.

slicer_add_python_unittest(SCRIPT TerritoriesNodeWrapperTest.py)
