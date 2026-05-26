# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""LiverLib — Python helpers for the Liver scripted module.

Mirrors the ``LiverResectionsLib/`` convention.  Files in this
subdirectory are installed alongside the ``Liver`` scripted module as
a Python sub-package; Slicer's scripted-module loader sweeps the
parent ``Liver/`` directory only — subdirectory ``.py`` files are NOT
loaded as Slicer modules and therefore do NOT trigger the
"class <FileName> not found" loader error that would otherwise fire
for helper files named with a leading underscore.

Per the T5.2-d shell rewrite, the orphaned distance-maps + resection
+ Bezier-bridge code that previously lived inside ``Liver/Liver.py``
moved here as ``LiverLib.legacy_logic`` — pending full relocation
into ``LiverResections/`` per the v2.0.0 follow-up tracker.
"""
