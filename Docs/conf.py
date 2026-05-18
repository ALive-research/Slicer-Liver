#!/usr/bin/env python3
#
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Slicer-Liver documentation build configuration.
#
# Per ADR-0017 the configuration mirrors Slicer-core's `Docs/conf.py`
# verbatim where possible — same MyST extension set, same Sphinx
# extensions, same theme — so contributors familiar with the
# upstream's docs setup do not have to relearn anything.  Slicer-Liver
# specifics (project name, version extraction) replace the
# Slicer-core specifics.

import os
import re
import sys
from datetime import date

# Add Slicer-Liver's Python lib package(s) to the autodoc path so the
# v2.0.0 `LiverResectionsLib` sub-package can be introspected once the
# autodoc surface is opted in (deferred until post-migration).
_DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_DOCS_DIR, ".."))
sys.path.insert(0, os.path.join(_REPO_ROOT, "LiverResections"))


# -- Project information ------------------------------------------------------

project = "Slicer-Liver"
copyright_year = date.today().year
copyright = (
    f"2017-{copyright_year}, The Intervention Centre, Oslo University Hospital "
    "and contributors"
)
author = "Slicer-Liver contributors"


def _extract_version_from_cmakelists():
    """Best-effort `<major>.<minor>` extraction from the top-level
    CMakeLists.txt.  Returns "0.0" if no SET_TARGET_PROPERTIES /
    project VERSION clause is present (Slicer-Liver's top-level CMake
    does not pin a project version today — the version lives in
    extension metadata)."""
    cmake_path = os.path.join(_REPO_ROOT, "CMakeLists.txt")
    try:
        with open(cmake_path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return "0.0"
    match = re.search(r"project\([^)]*VERSION\s+(\d+)\.(\d+)", content)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return "0.0"


version = _extract_version_from_cmakelists()
release = version


# -- General configuration ----------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "myst_parser",
    "sphinx_markdown_tables",
    "notfound.extension",
    "sphinx_rtd_theme",
    "sphinx-jsonschema",
    "sphinx_reredirects",
    "sphinx_design",
    # Mermaid diagrams in the architecture chapter + state-machine
    # diagrams in ADR-0019.  Added by ADR-0018's scaffold extension.
    "sphinxcontrib.mermaid",
]

# Mocks for autodoc — `LiverResectionsLib` imports from the Slicer
# runtime, which is not importable inside a plain Sphinx build.
autodoc_mock_imports = [
    "ctk",
    "qt",
    "vtk",
    "slicer",
    "LayerDMLib",
]

# Suppress MyST warnings the project intentionally accepts.
suppress_warnings = [
    # Splitting long docs across `:include:`-d files commonly yields
    # "Document headings start at H2, not H1".
    "myst.header",
]

# Page redirects — fill in as documents move during the migration PR.
redirects = {}

myst_enable_extensions = [
    "attrs_inline",
    "colon_fence",
    "dollarmath",
    "linkify",
]

# Auto-generate header anchors up to level 6 so MyST cross-document
# links can target sub-section headings without manual anchor tags.
myst_heading_anchors = 6

# Block math with equation-label syntax.
myst_dmath_allow_labels = True

templates_path = ["_templates"]
# Scaffold scope (ADR-0017 PR 1): only `index.md` and the ADR ledger
# are wired into the build.  The architecture diagrams, dependency
# notes, and the older ADRs ship pre-existing Markdown features (raw
# Mermaid fences, cross-doc links into the repo root) that need
# small touch-ups before they compile under `-W`.  Each chapter
# rejoins `exclude_patterns` removal in the migration follow-up
# per ADR-0017's rollout plan.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "architecture/**",
    "dependencies/**",
    # ADRs are admitted *individually* via the index toctree so the
    # scaffold compiles without dragging in unmigrated cross-refs.
    "adr/000*.md",
    "adr/001[0-6]*.md",
    "adr/README.md",
]
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
master_doc = "index"
language = "en"


# -- HTML output --------------------------------------------------------------

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "titles_only": False,
}
html_static_path = ["_static"]
# A `_static/` directory is required by Sphinx; populated later.

html_title = f"{project} {release}"
html_short_title = project


# -- LaTeX / PDF output -------------------------------------------------------

latex_elements = {
    "papersize": "a4paper",
    "pointsize": "11pt",
}

latex_documents = [
    (master_doc, "Slicer-Liver.tex", "Slicer-Liver documentation", author, "manual"),
]


# -- epub output --------------------------------------------------------------

epub_show_urls = "footnote"
