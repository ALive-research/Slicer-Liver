# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Normalize + remap coverage-py.xml paths, merging duplicate file records.

coverage.py's [paths] aliasing is directory-prefix-only, so the launched leg's
flat scripted modules (qt-scripted-modules/<Module>.py) survive as build-tree
paths.  Normalize every filename to repo-relative, rewrite staged flat modules
to their source location (<dir>/<Module>.py discovered dynamically), and merge
duplicate records by per-line max hits.

Usage: fix_coverage_paths.py <coverage-py.xml> <repo-root>.
"""

import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

xml_path = sys.argv[1]
root_dir = os.path.abspath(sys.argv[2])
STAGED = re.compile(r".*qt-scripted-modules/([A-Za-z_]+\.py)$")


def source_for(basename):
    """Repo-relative source path of a staged flat module, or None."""
    hits = [
        p
        for p in glob.glob(os.path.join(root_dir, "*", basename))
        if "build" not in p and "Testing" not in p
    ]
    return os.path.relpath(hits[0], root_dir) if len(hits) == 1 else None


tree = ET.parse(xml_path)
root = tree.getroot()
by_name = {}
for pkg in root.iter("package"):
    for classes in pkg.iter("classes"):
        for cls in list(classes):
            fn = cls.get("filename")
            if os.path.isabs(fn):
                fn = os.path.relpath(fn, root_dir)
            staged = STAGED.match(fn)
            if staged:
                src = source_for(staged.group(1))
                if src:
                    fn = src
            cls.set("filename", fn)
            if fn in by_name:
                keep = {ln.get("number"): ln for ln in by_name[fn].find("lines")}
                for ln in cls.find("lines"):
                    number = ln.get("number")
                    if number in keep:
                        merged = max(int(keep[number].get("hits")), int(ln.get("hits")))
                        keep[number].set("hits", str(merged))
                    else:
                        by_name[fn].find("lines").append(ln)
                classes.remove(cls)
            else:
                by_name[fn] = cls

tot_hits = 0
tot_lines = 0
for fn, cls in by_name.items():
    lines = cls.find("lines")
    n_lines = len(lines)
    n_hits = sum(1 for ln in lines if int(ln.get("hits")) > 0)
    cls.set("line-rate", str(n_hits / n_lines if n_lines else 0))
    tot_hits += n_hits
    tot_lines += n_lines
root.set("line-rate", str(tot_hits / tot_lines if tot_lines else 0))

for sources in root.iter("sources"):
    for child in list(sources):
        sources.remove(child)

tree.write(xml_path, xml_declaration=True)
print(
    f"fixed: {len(by_name)} files, overall "
    f"{100 * tot_hits / max(tot_lines, 1):.1f}% ({tot_hits}/{tot_lines})"
)
