# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Python unit tests for ``VascularContourRepresentation`` — ADR-0013 §6.

The vascular-contour Representation draws the hepatic / portal vascular
contours on top of the flattened resectogram strip so the surgeon can read
vessel proximity in the 2D ``(u, v)`` image (`ADR-0025`_ §Context).  It owns
the two relocated contour mappers (``vtkOpenGLDistanceContourPolyDataMapper``
/ ``vtkOpenGLSlicingContourPolyDataMapper``, `ADR-0014`_ §3) + their actors.

The invariants pinned here (ADR-0027 — the SPECIFIC invariant):

* **Visibility follows ``ShowResection2D``** — the contour overlays are
  drawn exactly when the resectogram strip is.
* **Strip-geometry feed (T3-c)** — when the data node carries the
  flattened-strip polydata, ``update()`` feeds it into BOTH contour mappers
  (the contours are computed over the same strip the flattened surface
  draws), not discarded.

References
----------
* ADR-0008 §2 — Representation tests, unit layer.
* ADR-0013 §6 — Representations as composable VTK pipelines.
* ADR-0014 §3 — mapper relocation (the contour mappers live under
  ``LiverResections/VTKWidgets/``).
* ADR-0025 §Context — the resectogram and its vascular overlays.
* ADR-0027 — invariant-test-first.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --------------------------------------------------------------------------- #
# Repo geometry — mirrors test_confirmed_representation.py.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "LiverResections" / "LiverResectionsLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


# --------------------------------------------------------------------------- #
# Stub nodes
# --------------------------------------------------------------------------- #


class _StubDisplayNode:
    def __init__(self, show_2d: bool = True) -> None:
        self.show_2d = show_2d

    def GetShowResection2D(self) -> bool:
        return self.show_2d


class _StubStripDataNode:
    """Data node exposing the flattened-strip polydata the contours sit on."""

    def __init__(self, strip) -> None:
        self.strip = strip

    def GetResectogramStripPolyData(self):
        return self.strip


@pytest.fixture
def rep_module():
    from Representations.VascularContourRepresentation import (
        VascularContourRepresentation,
    )

    return VascularContourRepresentation


# --------------------------------------------------------------------------- #
# Pure-Python assertions (run with or without VTK)
# --------------------------------------------------------------------------- #


def test_representation_construct_with_no_renderer(rep_module):
    rep = rep_module()
    assert rep.GetRenderer() is None
    rep.cleanup()


def test_update_tolerates_none_nodes(rep_module):
    rep = rep_module()
    rep.update(display_node=None, data_node=None)
    assert rep.GetUpdateCount() == 1
    rep.cleanup()


# --------------------------------------------------------------------------- #
# Strip-geometry feed (T3-c) — pinned with stub mappers so the wiring is
# exercised without the wrapped C++ contour mappers present locally.
# --------------------------------------------------------------------------- #


class _StubContourMapper:
    def __init__(self) -> None:
        self.input_data = None

    def SetInputData(self, polydata) -> None:
        self.input_data = polydata


def _inject_contour_mappers(rep):
    distance = _StubContourMapper()
    slicing = _StubContourMapper()
    rep._distance_contour_mapper = distance
    rep._slicing_contour_mapper = slicing
    distance_actor = rep.GetDistanceContourActor()
    slicing_actor = rep.GetSlicingContourActor()
    if distance_actor is not None and hasattr(distance_actor, "SetMapper"):
        distance_actor.SetMapper(distance)
    if slicing_actor is not None and hasattr(slicing_actor, "SetMapper"):
        slicing_actor.SetMapper(slicing)
    return distance, slicing


def test_strip_polydata_feeds_both_contour_mappers(rep_module):
    """The flattened-strip polydata is pushed into BOTH contour mappers."""
    rep = rep_module()
    distance, slicing = _inject_contour_mappers(rep)
    strip = object()  # opaque polydata sentinel
    rep.update(_StubDisplayNode(), _StubStripDataNode(strip))
    assert distance.input_data is strip
    assert slicing.input_data is strip
    rep.cleanup()


def test_no_strip_polydata_leaves_inputs_untouched(rep_module):
    """A data node without the strip accessor does not crash and leaves
    the mapper inputs untouched (no spurious feed)."""
    rep = rep_module()
    distance, slicing = _inject_contour_mappers(rep)

    class _NoStripDataNode:
        pass

    rep.update(_StubDisplayNode(), _NoStripDataNode())
    assert distance.input_data is None
    assert slicing.input_data is None
    rep.cleanup()


# --------------------------------------------------------------------------- #
# VTK-mediated assertions
# --------------------------------------------------------------------------- #


@pytest.fixture
def vtk_module():
    return pytest.importorskip(
        "vtk",
        reason="vtk not importable; skip the VTK-mediated Representation tests.",
    )


def test_assembly_builds_two_mappers_and_actors(rep_module, vtk_module):
    rep = rep_module()
    assert rep.GetDistanceContourMapper() is not None
    assert rep.GetSlicingContourMapper() is not None
    assert rep.GetDistanceContourActor() is not None
    assert rep.GetSlicingContourActor() is not None
    rep.cleanup()


def test_contour_visibility_follows_show_resection_2d(rep_module, vtk_module):
    rep = rep_module()
    rep.update(_StubDisplayNode(show_2d=True), None)
    assert rep.GetDistanceContourActor().GetVisibility() == 1
    assert rep.GetSlicingContourActor().GetVisibility() == 1
    rep.update(_StubDisplayNode(show_2d=False), None)
    assert rep.GetDistanceContourActor().GetVisibility() == 0
    assert rep.GetSlicingContourActor().GetVisibility() == 0
    rep.cleanup()
