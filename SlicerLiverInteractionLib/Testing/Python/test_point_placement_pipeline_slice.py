# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 -- the shared slice-view control-point projection + fade base.

ADR-0038 §Decision extracts a shared ``SurfacePointPlacementPipelineSlice``
base (the slice complement of the 3D base) from the mature resection slice
pipeline; VascularTerritories/volumetry become clients.  The base owns the
slice projection into XY (``inverse(XYToRAS)``), the distance-graded alpha
fade, the signed above/below side tint, and the HARD presence cutoff (2D
alpha is unreliable) -- named explicitly as duplicated in ADR-0038
§Context.

This file pins the PURE-MATH half of the slice base -- the projection /
signed distance / fade / side tint / presence cutoff -- which is plain
geometry given a slice node exposing ``GetXYToRAS`` / ``GetSliceToRAS``.
It mirrors the bare-math assertions in
``VascularTerritories/Testing/Python/test_territories_slice_pipeline.py``
so the extracted helper is pinned to the SAME behaviour it had at its
territory origin.  The launched snap / arm-gate / decline invariants of
the slice base ride the 3D-base + client suites; this file is the bare
geometry contract.

HARNESS: bare ``PythonSlicer -m pytest``.  The projection math needs no
LayerDM, no GL, no scene -- a FAKE slice node (pure matrices) drives it --
so it RUNS bare AND launched.  The proposed home is a pure-math helper
module beside the base (``SlicerLiverInteractionLib/SlicePointProjection.py``,
generalising ``TerritorySliceProjection``); the base pipeline imports it.

The SUT does not exist yet.  Per ADR-0027 red->skip the import is guarded
and every test SKIP-PENDINGs on ``ImportError``; the skips lift at the
extraction commit.

References
----------
* ADR-0038 -- §Context names the slice projection + fade + side tint +
  presence cutoff as the duplicated surface the base owns; §Decision
  extracts them once.
* ADR-0033 -- the slice-polygon presence-cutoff + side-tint discipline
  (2D alpha unreliable).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/VascularTerritoriesLib/TerritorySliceProjection.py --
  the origin these assertions mirror.
* VascularTerritories/Testing/Python/test_territories_slice_pipeline.py --
  the client suite's bare-math half.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))


def _import_projection_or_skip():
    """Import the shared slice-projection helper, or skip-pend (ADR-0027).

    PROPOSED seam (sharpen at landing): a pure-math module generalising
    ``TerritorySliceProjection`` with the SAME public surface --
    ``project_ras_to_xy``, ``signed_distance_to_slice``, ``is_present``,
    ``fade_alpha``, ``side_tint``, ``normal_ray`` -- plus the constants
    ``PICK_RANGE_MM`` / ``FADE_DISTANCE_MM``.
    """
    try:
        import SlicePointProjection as proj
    except ImportError:
        pytest.skip(
            "SlicePointProjection not importable -- the ADR-0038 shared slice "
            "projection helper has not landed (ADR-0027 red->skip)."
        )
    return proj


def _identity_scaled(fov_mm_per_px=1.0):
    """A 4x4 mapping XY pixels to RAS with a uniform mm-per-pixel scale."""
    m = vtk.vtkMatrix4x4()
    m.Identity()
    m.SetElement(0, 0, fov_mm_per_px)
    m.SetElement(1, 1, fov_mm_per_px)
    return m


class _FakeSliceNode:
    """An axial slice at ``z = z0``: normal +z, pixels 1 mm apart in x/y."""

    def __init__(self, z0=0.0, fov_mm_per_px=1.0):
        self._slice_to_ras = vtk.vtkMatrix4x4()
        self._slice_to_ras.Identity()
        self._slice_to_ras.SetElement(2, 3, z0)
        self._xy_to_ras = _identity_scaled(fov_mm_per_px)
        self._xy_to_ras.SetElement(2, 3, z0)

    def GetSliceToRAS(self):  # noqa: N802 - VTK verb
        return self._slice_to_ras

    def GetXYToRAS(self):  # noqa: N802 - VTK verb
        return self._xy_to_ras

    def IsA(self, cls):  # noqa: N802 - VTK verb
        return cls == "vtkMRMLSliceNode"


# --------------------------------------------------------------------------- #
# PURE MATH -- projection / signed distance / fade / side tint / presence
# --------------------------------------------------------------------------- #


def test_project_ras_to_xy_round_trips_in_plane_point():
    """A point ON the slice plane projects to its pixel via inverse(XYToRAS).

    With a 1 mm/px axial slice at z=0, RAS ``(3, 4, 0)`` projects to XY
    ``(3, 4)``.  ADR-0038 §Context (slice projection into XY).
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0, fov_mm_per_px=1.0)

    xy = proj.project_ras_to_xy(slice_node, (3.0, 4.0, 0.0))

    assert xy is not None
    assert xy == pytest.approx((3.0, 4.0), abs=1e-6)


def test_signed_distance_is_positive_above_negative_below():
    """Signed distance is + above the plane (along +normal), - below.

    An axial slice at z=0 has normal +z; RAS ``(0, 0, 5)`` is +5 mm,
    ``(0, 0, -5)`` is -5 mm.  ADR-0038 §Context (signed above/below tint).
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0)

    assert proj.signed_distance_to_slice(slice_node, (0.0, 0.0, 5.0)) == pytest.approx(5.0)
    assert proj.signed_distance_to_slice(slice_node, (0.0, 0.0, -5.0)) == pytest.approx(-5.0)
    assert proj.signed_distance_to_slice(slice_node, (2.0, 9.0, 0.0)) == pytest.approx(0.0)


def test_presence_cutoff_is_hard_at_pick_range():
    """Presence is a HARD cutoff at ``PICK_RANGE_MM`` (2D alpha unreliable).

    A seed just inside the range is present; one at / beyond it is ABSENT --
    not merely faded to zero alpha (ADR-0033 slice-polygon rule, owned by
    the base per ADR-0038 §Context).
    """
    proj = _import_projection_or_skip()

    assert proj.is_present(proj.PICK_RANGE_MM - 0.01) is True
    assert proj.is_present(proj.PICK_RANGE_MM) is False
    assert proj.is_present(proj.PICK_RANGE_MM + 5.0) is False
    # The fade is monotone: nearer the plane => more opaque.
    assert proj.fade_alpha(0.0) == pytest.approx(1.0)
    assert proj.fade_alpha(proj.FADE_DISTANCE_MM) == pytest.approx(0.0)
    assert 0.0 < proj.fade_alpha(proj.FADE_DISTANCE_MM / 2.0) < 1.0


def test_side_tint_lightens_above_and_darkens_below():
    """The signed side tint pulls a mid-grey toward white above / black below.

    ADR-0038 §Context (the signed above/below side tint owned by the base).
    """
    proj = _import_projection_or_skip()
    base = [128, 128, 128]

    above = proj.side_tint(base, +proj.FADE_DISTANCE_MM)
    below = proj.side_tint(base, -proj.FADE_DISTANCE_MM)

    assert above[0] > base[0], "above the plane must lighten toward white."
    assert below[0] < base[0], "below the plane must darken toward black."


def test_normal_ray_runs_along_the_slice_normal_through_the_point():
    """The snap ray straddles the RAS point ALONG the slice normal.

    An axial slice's normal is +z, so the ray through ``(1, 2, 0)`` runs
    from ``(1, 2, +extent)`` to ``(1, 2, -extent)`` -- x/y stay fixed.  This
    is the ray the pick provider is fed (surface consumers snap along it;
    volumetry resolves the in-plane point -- the pick step is swappable per
    ADR-0038 §"Base extension").
    """
    proj = _import_projection_or_skip()
    slice_node = _FakeSliceNode(z0=0.0)

    ray = proj.normal_ray(slice_node, (1.0, 2.0, 0.0), extent_mm=50.0)

    assert ray is not None
    p1, p2 = ray
    assert p1 == pytest.approx((1.0, 2.0, 50.0), abs=1e-6)
    assert p2 == pytest.approx((1.0, 2.0, -50.0), abs=1e-6)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
