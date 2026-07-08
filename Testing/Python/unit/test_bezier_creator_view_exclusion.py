# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""View-exclusion pin for the Bezier surface-family pipeline creators.

The resectogram singleton view is owned solely by the
``ResectogramPipeline`` (its strip + locator click seam, ADR-0023
§Stage-4): surface-family pipelines leaking into it put deformable,
interactive actors inside the flattened 2D strip.  The Bezier creator
matched ANY ``vtkMRMLViewNode``, so the 3D surface pipeline was
instantiated inside the resectogram view too — the strip appeared to
deform (and host surface interaction) during Planning drags.

Pinned here, GL-free: the module-level ``_is_resectogram_view``
predicate the creator's ``tryCreate`` consults recognises the
resectogram singleton view by its MRML ``SingletonTag`` and nothing
else.  (The creator closure itself needs ``slicer``-namespace classes,
so its wiring is exercised on the launched/interactive rows.)

References
----------
* ADR-0013 §5 — pipeline-creator registration.
* ADR-0023 §Stage-4 — the dedicated resectogram view.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytest.importorskip("LayerDMLib")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


@pytest.fixture
def pipeline_module():
    import LiverBezierSurfacePipeline as mod

    return mod


class _TaggedView:
    def __init__(self, tag):
        self._tag = tag

    def GetSingletonTag(self):  # noqa: N802 - VTK verb
        return self._tag


class _UntaggedView:
    """A view node shape without ``GetSingletonTag`` (defensive path)."""


def test_resectogram_singleton_view_is_recognised(pipeline_module):
    from ResectogramViewManager import RESECTOGRAM_VIEW_SINGLETON_TAG

    assert (
        pipeline_module._is_resectogram_view(
            _TaggedView(RESECTOGRAM_VIEW_SINGLETON_TAG)
        )
        is True
    ), (
        "the Bezier creator must recognise (and decline) the resectogram "
        "singleton view -- the 3D surface pipeline deforming inside the "
        "flattened strip is the leak this pin guards."
    )


def test_ordinary_views_are_not_excluded(pipeline_module):
    assert pipeline_module._is_resectogram_view(_TaggedView(None)) is False
    assert pipeline_module._is_resectogram_view(_TaggedView("Default")) is False
    assert pipeline_module._is_resectogram_view(_UntaggedView()) is False
    assert pipeline_module._is_resectogram_view(None) is False
