# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Characterisation tests for the Bezier-fitting and EFD Python math in
``Liver/Liver.py`` (task T1-A).

Per ADR-0003 (testability invariant) and the forthcoming ADR-0015 (C++
algorithm-library lift), these tests pin the **current** numerical output
of four pure-NumPy methods on ``LiverLogic`` *before* any lift code lands.
They are the safety net the lift inverts assertions against: any commit
that changes a captured value is flagged immediately, and a reviewer
decides whether the change is intentional (and the EXPECTED constant
updated in the same PR) or a regression to be reverted.

Functions characterised
-----------------------
1. ``LiverLogic.fit_bezier_surface``         — Liver/Liver.py:1914 (verified
                                                2026-05-15 against preview
                                                HEAD).
2. ``LiverLogic.elliptic_fourier_descriptors`` — Liver/Liver.py:1287.
3. ``LiverLogic.inverse_transform``          — Liver/Liver.py:1343.
4. ``LiverLogic.calculate_dc_coefficients``  — Liver/Liver.py:1396.

Deferred (out of scope for this PR — flagged for follow-up)
-----------------------------------------------------------
* ``runSurfacefromCurve`` / ``runSurfacefromEFD`` — end-to-end pipeline
  methods.  Require constructing synthetic MRML resection nodes, closed
  curve nodes, distance maps, and liver model polydata.  Deferred to a
  module-layer test PR per the brief.
* ``extract_points``, ``optimized_path``, ``compute_simple_pca``,
  ``Nyquist``, ``FourierPower`` — small helpers; not yet pinned, but
  the discipline is the same when they need it.

Capture provenance
------------------
EXPECTED_* arrays below were captured on **2026-05-15** by replaying the
verbatim function bodies (transcribed by hand and visually diffed against
the source) under **NumPy 2.3.1** in a plain Python environment, *not*
inside a Slicer Python.  The methods on ``LiverLogic`` use no ``self``-state
(verified by inspection — they call only ``numpy`` operators and, when
``normalize=False``, no other instance methods), so the replay is
byte-equivalent to calling the method on a constructed ``LiverLogic()``
inside Slicer's Python.  If a future maintainer updates these constants,
they must (a) document the Slicer + NumPy versions in this docstring and
(b) explain the behaviour change in the PR body, per ADR-0003 §1.

Bezier degree correction (2026-05-16)
-------------------------------------
The original capture (PR #330) pinned ``EXPECTED_BEZIER_CONTROL_POINTS``
against a **degree-4** Bernstein basis (5x5 → 25 control points), but
both production callers of ``fit_bezier_surface`` evaluate the basis at
**degree 3** (4x4 → 16 control points):

* ``LiverLogic.runSurfacefromCurve`` — ``Liver/Liver.py:2010``
  (``bezier_basis = self.evaluate_basis_bezier(u[i], 3)``).
* ``LiverLogic.runSurfacefromEFD`` — ``Liver/Liver.py:2163``
  (same call at degree 3).

A characterisation pin that does not match what production actually
runs is not a regression net for production — it is a net for a
hypothetical degree-4 path nobody uses.  ADR-0014 §3 commits to a
16-control-point ring (corners 4 + edges 8 + interior 4) and the legacy
``vtkMRMLMarkupsBezierSurfaceNode::RequiredNumberOfControlPoints = 16``
corroborates the 4x4 truth.  This file's helper, fixture, EXPECTED
constants, and shape assertions have all been re-captured at
**degree 3** as of this PR.  The downstream C++ algorithm fixtures
(``vtkLiverAlgorithmTestFixtures.h``) and the new MRML node from
PR #341 were both inherited from PR #330's wrong capture; the former
is fixed in this same PR and the latter will be amended in a
follow-up.

When run in a plain Python environment (no Slicer), the
``pytest.importorskip("slicer")`` at the top of each test gates the
suite cleanly — the tests are *registered* but skipped, matching the
discipline used by ``Testing/Python/unit/test_terminology_assets.py``.
In CI inside Slicer's bundled Python (per ADR-0008 §6 and PR #316's
``pytest_scaffold`` CTest entry), the import succeeds, the class is
constructed, and the assertions run.

References
----------
* ADR-0003 — testability invariant (Docs/adr/0003-testability-invariant.md)
* ADR-0008 — testing strategy (Docs/adr/0008-testing-strategy.md), §7
  on characterisation discipline + §2 on layered taxonomy (unit layer).
* ADR-0015 — C++ algorithm-library lift (forthcoming).  These tests are
  the inversion target of that ADR's lift commits.
* Closes #307.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest


# --------------------------------------------------------------------------- #
# Repo geometry — locate Liver/Liver.py without relying on Slicer's module
# path setup.  ``REPO_ROOT`` matches the convention used in
# ``test_terminology_assets.py``.
# --------------------------------------------------------------------------- #

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LIVER_PY = REPO_ROOT / "Liver" / "Liver.py"


# --------------------------------------------------------------------------- #
# Module-scoped fixture — load ``LiverLogic`` from source.
#
# We deliberately do not rely on Slicer's module-path discovery to pick up
# ``Liver.py``: the tests run from a generic pytest invocation and may not
# be inside a Slicer launcher.  The ``importorskip("slicer")`` gates
# everything below it; once slicer is importable, the rest of Liver.py's
# dependency stack (vtk, qt, ctk, ScriptedLoadableModule) is too.
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def liver_logic():
    """Construct ``LiverLogic`` from the in-repo ``Liver/Liver.py``.

    Skips if ``slicer`` (and thus the Liver module's ``import vtk, qt,
    ctk, slicer`` line) is unavailable.  Returns a fresh ``LiverLogic()``
    instance; the methods under test are stateless, so module scope is
    safe.
    """
    pytest.importorskip(
        "slicer",
        reason=(
            "Liver.py imports vtk/qt/ctk/slicer at module top; "
            "characterisation requires Slicer's Python."
        ),
    )

    # Ensure the in-repo Liver/ directory is on sys.path so Liver.py's
    # ``import VascularTerritories`` / ``import LiverVolumetry`` resolve
    # to the sibling source trees.
    liver_dir = str(REPO_ROOT / "Liver")
    if liver_dir not in sys.path:
        sys.path.insert(0, liver_dir)
    for sibling in ("VascularTerritories", "LiverVolumetry"):
        sibling_dir = str(REPO_ROOT / sibling / sibling)
        if (REPO_ROOT / sibling / sibling).is_dir() and sibling_dir not in sys.path:
            sys.path.insert(0, sibling_dir)

    spec = importlib.util.spec_from_file_location("Liver", str(LIVER_PY))
    if spec is None or spec.loader is None:  # pragma: no cover — defensive
        pytest.skip(f"could not build importlib spec for {LIVER_PY}")
    Liver = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(Liver)
    except Exception as exc:  # pragma: no cover — surfaces only in broken env
        pytest.skip(f"failed to load Liver.py: {exc}")

    return Liver.LiverLogic()


# --------------------------------------------------------------------------- #
# Fixture helpers — deterministic synthetic inputs.
#
# Kept module-private (small ``_make_*`` functions, not pytest fixtures)
# so they can also be re-invoked by the EXPECTED-value re-capture script
# if a maintainer needs to refresh the constants below.
# --------------------------------------------------------------------------- #

def _bernstein_degree_3(t: float) -> np.ndarray:
    """Bernstein basis B_{3,0..3}(t) — degree-3 polynomials in [0, 1].

    Matches the basis order used by ``LiverLogic.evaluate_basis_bezier``
    when called at ``degree=3`` from the production callers
    ``runSurfacefromCurve`` (``Liver/Liver.py:2010``) and
    ``runSurfacefromEFD`` (``Liver/Liver.py:2163``).
    """
    return np.array(
        [
            (1 - t) ** 3,
            3 * t * (1 - t) ** 2,
            3 * t ** 2 * (1 - t),
            t ** 3,
        ]
    )


def _make_bezier_fixture():
    """A 4x4x3 grid of saddle-surface points plus matching 4x4 Bernstein bases.

    The control-net is the bilinear surface ``z = u*v`` sampled on a
    uniform 4x4 ``(u, v)`` grid; the basis matrices evaluate
    Bernstein-3 polynomials at the same sample locations.  Because the
    basis matrices are square (4x4), ``transpose(B)*B`` is invertible
    in exact arithmetic — the pseudo-inverse formulation collapses to
    the exact inverse, which is what makes the captured EXPECTED stable
    across NumPy versions for a characterisation pin.

    Degree 3 (4x4 = 16 control points) is what both production callers
    of ``fit_bezier_surface`` use; see the module docstring's
    "Bezier degree correction" section for the history of why this
    helper used to build at degree 4.
    """
    u_samples = np.linspace(0.0, 1.0, 4)
    v_samples = np.linspace(0.0, 1.0, 4)
    basis_u = np.stack([_bernstein_degree_3(t) for t in u_samples], axis=0)
    basis_v = np.stack([_bernstein_degree_3(t) for t in v_samples], axis=0)

    points = np.zeros((4, 4, 3), dtype=np.float64)
    for i, u in enumerate(u_samples):
        for j, v in enumerate(v_samples):
            points[i, j, 0] = u
            points[i, j, 1] = v
            points[i, j, 2] = u * v
    return points, basis_u, basis_v


def _make_contour_fixture():
    """A closed 3D contour with ~30 points and non-trivial energy on each axis.

    The contour is an inclined ellipse with a small additional harmonic
    on each axis, ensuring all six EFD coefficient channels
    (a, b, c, d, e, f) carry meaningful non-zero content for every
    harmonic up to order 8 (so the captured EXPECTED arrays are not
    dominated by floating-point dust).  The last point repeats the
    first so ``np.diff`` closes the loop.
    """
    n_pts = 30
    theta = np.linspace(0.0, 2.0 * np.pi, n_pts, endpoint=False)
    contour = np.zeros((n_pts, 3), dtype=np.float64)
    contour[:, 0] = 3.0 * np.cos(theta) + 0.5 * np.cos(3 * theta)
    contour[:, 1] = 2.0 * np.sin(theta) + 0.3 * np.sin(2 * theta)
    contour[:, 2] = 1.0 * np.sin(2 * theta) + 0.2 * np.cos(theta)
    return np.vstack([contour, contour[0:1, :]])


# --------------------------------------------------------------------------- #
# EXPECTED_* constants — captured 2026-05-15 against preview HEAD by
# replaying verbatim method bodies under NumPy 2.3.1.  See module
# docstring for capture provenance and refresh discipline.
# --------------------------------------------------------------------------- #

# fit_bezier_surface: shape (4, 4, 3).  Recall the control net was the
# bilinear z = u*v on a uniform (u, v) grid — and because the Bernstein
# bases on a uniform 4-sample grid form a non-singular square matrix,
# the recovered control points reproduce the input lattice nearly
# exactly (modulo ~1e-18 floating-point dust on entries that are
# mathematically zero, and ~1e-15 relative error on the non-zero
# entries from the matrix-inverse round-trip).  Captured at full
# float64 precision so the assertion can run at ``rtol=1e-12``.
#
# Re-captured 2026-05-16 at the production-correct Bernstein degree-3
# (4x4 = 16 control points); see the module docstring's
# "Bezier degree correction" section.
EXPECTED_BEZIER_CONTROL_POINTS = np.array(
    [
        [
            [4.6259292692714846e-18, -1.1993149957370571e-18, -5.5479463418562525e-36],
            [4.6259292692714869e-18, 3.3333333333333387e-01, 1.5419764230904974e-18],
            [4.6259292692714907e-18, 6.6666666666666718e-01, 3.0839528461809933e-18],
            [4.6259292692714853e-18, 1.0000000000000002e+00, 4.6259292692714853e-18],
        ],
        [
            [3.3333333333333365e-01, -1.1993149957370510e-18, -3.9977166524568520e-19],
            [3.3333333333333370e-01, 3.3333333333333370e-01, 1.1111111111111140e-01],
            [3.3333333333333431e-01, 6.6666666666666785e-01, 2.2222222222222271e-01],
            [3.3333333333333370e-01, 1.0000000000000000e+00, 3.3333333333333370e-01],
        ],
        [
            [6.6666666666666730e-01, -1.1993149957370633e-18, -7.9954333049137040e-19],
            [6.6666666666666741e-01, 3.3333333333333437e-01, 2.2222222222222279e-01],
            [6.6666666666666863e-01, 6.6666666666666841e-01, 4.4444444444444542e-01],
            [6.6666666666666741e-01, 1.0000000000000020e+00, 6.6666666666666741e-01],
        ],
        [
            [1.0000000000000002e+00, -1.1993149957370633e-18, -1.1993149957370633e-18],
            [1.0000000000000009e+00, 3.3333333333333381e-01, 3.3333333333333381e-01],
            [1.0000000000000022e+00, 6.6666666666666741e-01, 6.6666666666666741e-01],
            [1.0000000000000004e+00, 1.0000000000000004e+00, 1.0000000000000004e+00],
        ],
    ]
)

# elliptic_fourier_descriptors at order=8: shape (8, 6).
EXPECTED_EFD_COEFFS = np.array(
    [
        [3.0696780014396787e+00, 5.1239779468424333e-02, -2.9789149140810579e-02,
         1.9514873662662355e+00, 2.2036188853356678e-01, 4.2702746974910076e-02],
        [-2.6309229837804714e-02, -6.4267881945438213e-02, 6.6786943662647752e-03,
         2.2418342923058746e-01, -4.0019158286106520e-02, 1.0054240564985091e+00],
        [3.5070359011478724e-01, 2.3751119059978693e-02, 5.7765748378587360e-03,
         -3.1926498794324062e-02, 1.8841777989148448e-02, -6.3265267683567286e-02],
        [-5.9072088792485336e-02, -2.8677448082430942e-03, -4.4021774738493948e-03,
         -2.4910202986012455e-02, -2.2814268970371837e-03, -3.8266183368038165e-02],
        [1.4297493082861342e-02, 3.8157120315777809e-03, -5.1047708828664178e-03,
         3.5915138362602329e-02, -4.0701176860480524e-03, -1.1736870556792744e-02],
        [-3.7731670425895304e-03, -2.1498528837345801e-03, 3.2019220293054503e-03,
         4.9367515048579389e-03, -3.1462453950325381e-03, 3.6203948075069090e-02],
        [2.7504669785076315e-02, 2.9615241918178881e-03, 3.7673554870742667e-04,
         2.9205527446133943e-03, 5.4285520231319266e-03, -3.6534590699282741e-03],
        [-8.0002053361613468e-03, -3.0729534019550858e-03, -4.8578519669361986e-04,
         -3.2105247026203479e-03, -1.4167817826331423e-03, 2.8554590182290700e-03],
    ]
)

# calculate_dc_coefficients on the same contour.
EXPECTED_DC = (
    0.1051885444410785,
    0.02454548704630012,
    0.006326034387983737,
)

# inverse_transform of EXPECTED_EFD_COEFFS at locus=(0.1, 0.2, 0.3),
# n_coords=12, harmonic=8.  Shape (1, 3, 12) — the leading singleton
# comes from the ``(1, -1)`` reshape inside the function.  Captured at
# full float64 precision to keep the assertion at ``rtol=1e-12``.
EXPECTED_INVERSE_TRANSFORM = np.array(
    [
        [
            [3.46502906341336292, 2.62631914676115930, 1.06997026875380863,
             -0.15691976181966613, -1.47373468829598275, -3.02584017448850640,
             -3.18716291312130418, -1.69327787626239701, -0.24848273167857418,
             1.08391744585535688, 2.64018222088274346, 3.46502906341336292],
            [0.17625204408791639, 1.39967211550582804, 2.14059855311727887,
             2.10083953176494642, 1.42746946521858908, 0.69220634387038882,
             -0.23353674636938754, -0.97530931821845668, -1.70506186210775468,
             -1.78630424944057942, -1.03682587742876775, 0.17625204408791581],
            [0.49369848849898967, 1.30367892816921649, 1.27201090631539571,
             0.08585781080290544, -0.79477791740439296, -0.55165977874586325,
             0.64330272029724767, 1.13483868058486026, 0.55744055447150265,
             -0.48298935193040421, -0.36140104105945753, 0.49369848849898923],
        ]
    ]
)


# --------------------------------------------------------------------------- #
# Tolerance defaults — characterisation pins prefer the tightest tolerance
# the math actually supports.  These methods are pure-NumPy floating-point
# pipelines with no Slicer-side variability, so the captured values should
# be bit-stable on a given NumPy build.  ``rtol=1e-12`` leaves headroom
# for cross-platform BLAS dispatch variation (Slicer's bundled NumPy on
# Windows/Linux/macOS may pick different LAPACK kernels for
# ``np.linalg.inv``); ``rtol=1e-7`` is the looser fallback for any single
# assertion that turns out to be sensitive in practice — none currently
# needed at the time of capture.
# --------------------------------------------------------------------------- #

_RTOL_TIGHT = 1e-12
_ATOL_TIGHT = 1e-12


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_fit_bezier_surface_matches_pinned_control_points(liver_logic):
    """``fit_bezier_surface`` round-trip on a square Bernstein basis.

    With a square non-singular basis matrix the pseudo-inverse
    formulation degenerates to an exact inverse, and the recovered
    control points should reproduce the sampled control net.  The
    captured EXPECTED therefore consists almost entirely of the input
    lattice; the few ~1e-17 entries are floating-point dust from the
    matmul.  Any drift here flags a change in NumPy's BLAS routing or
    in the function body itself — both are exactly the regressions
    this test exists to catch.
    """
    points, basis_u, basis_v = _make_bezier_fixture()
    cps = liver_logic.fit_bezier_surface(points, basis_u, basis_v)

    assert cps.shape == (4, 4, 3), (
        f"fit_bezier_surface returned shape {cps.shape}, expected (4, 4, 3)"
    )
    np.testing.assert_allclose(
        cps,
        EXPECTED_BEZIER_CONTROL_POINTS,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


def test_elliptic_fourier_descriptors_matches_pinned_coefficients(liver_logic):
    """``elliptic_fourier_descriptors`` on a closed 3D contour, order=8.

    Pins the unnormalised Kuhl-Giardina 3D EFD output for the synthetic
    inclined-ellipse contour built by :func:`_make_contour_fixture`.
    The ``normalize=False`` path is exercised so the test does not also
    depend on ``normalize_efd3d`` — that helper deserves its own pin
    once it has a defined contract.
    """
    contour = _make_contour_fixture()
    coeffs = liver_logic.elliptic_fourier_descriptors(
        contour, order=8, normalize=False
    )
    assert coeffs.shape == (8, 6), (
        f"elliptic_fourier_descriptors returned shape {coeffs.shape}, "
        "expected (8, 6)"
    )
    np.testing.assert_allclose(
        coeffs,
        EXPECTED_EFD_COEFFS,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


def test_calculate_dc_coefficients_matches_pinned_values(liver_logic):
    """``calculate_dc_coefficients`` returns the EFD DC triple ``(A0, C0, E0)``.

    These are the locus offsets used by ``inverse_transform`` to place
    the reconstructed contour back at its true centroid.  The
    characterisation pins the exact triple for the synthetic contour.
    """
    contour = _make_contour_fixture()
    a0, c0, e0 = liver_logic.calculate_dc_coefficients(contour)
    np.testing.assert_allclose(
        (float(a0), float(c0), float(e0)),
        EXPECTED_DC,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


def test_inverse_transform_matches_pinned_reconstruction(liver_logic):
    """``inverse_transform`` reconstructs a contour from EFD coefficients.

    The pinned output uses the EXPECTED EFD coefficients directly (not
    a re-computation), so this test is independent of
    ``elliptic_fourier_descriptors`` drift: it catches changes in the
    inverse path alone.  A locus offset of ``(0.1, 0.2, 0.3)``
    distinguishes "did the locus parameter get applied" from "did the
    Fourier sum compute correctly" — both feed the same EXPECTED so a
    bug in either path is visible.
    """
    coeffs = EXPECTED_EFD_COEFFS  # use the pinned coefficients, not a
                                   # re-computation, so this test only
                                   # exercises the inverse path.
    recon = liver_logic.inverse_transform(
        coeffs, locus=(0.1, 0.2, 0.3), n_coords=12, harmonic=8
    )
    assert recon.shape == (1, 3, 12), (
        f"inverse_transform returned shape {recon.shape}, "
        "expected (1, 3, 12)"
    )
    np.testing.assert_allclose(
        recon,
        EXPECTED_INVERSE_TRANSFORM,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


# --------------------------------------------------------------------------- #
# C++ wrapper parallel tests — T2 Stack 1 / ADR-0015.
#
# The C++ algorithm library introduced by ADR-0015 hosts the same four
# numerical paths as a Python-wrapped VTK module
# (``vtkSlicerLiverResectionsModuleAlgorithm``).  Each test below
# re-asserts the same EXPECTED_* characterisation pin against the C++
# implementation, so a single PR-test run covers both paths.
#
# Tolerance: the C++ side uses Eigen's ``MatrixXd::inverse()`` rather
# than LAPACK's ``np.linalg.inv``, which may dispatch a different small-
# matrix kernel and produce last-bit-of-double differences on the 4x4
# inversion.  The Bezier wrapper assertion below therefore relaxes to
# ``rtol=1e-10`` — documented in the C++ test file as well, per
# ADR-0015 §Consequences ("Numerical tolerance is documented per test
# case where bit-equivalence is not achievable").  The EFD / DC /
# inverse-transform paths are direct closed-form sums and *do* hold at
# the tight ``rtol=1e-12`` against the C++ implementation.
#
# The whole block skips cleanly when the wrapped module is unavailable
# (incremental local builds where only Liver/ has been touched, CI
# stages that run pytest before the C++ build, etc.).
# --------------------------------------------------------------------------- #

_RTOL_LOOSE_BEZIER = 1e-10  # Eigen vs LAPACK dispatch noise on 4x4 inverse
_ATOL_LOOSE_BEZIER = 1e-12


@pytest.fixture(scope="module")
def algorithm_module():
    """Import the C++ Algorithm wrapper, skipping if unavailable.

    The wrapped Python module is named with the ``Python`` suffix as
    produced by ``SlicerMacroPythonWrapModuleVTKLibrary`` (matching the
    convention used by ``VascularTerritories`` and ``LiverVolumetry``).
    """
    return pytest.importorskip(
        "vtkSlicerLiverResectionsModuleAlgorithmPython",
        reason=(
            "vtkSlicerLiverResectionsModuleAlgorithm not built / not on "
            "sys.path; skip the C++ side of the dual-mode characterisation."
        ),
    )


def _to_double_array(flat):
    """Convert a flat float iterable to a vtkDoubleArray (1 component)."""
    import vtk

    arr = vtk.vtkDoubleArray()
    arr.SetNumberOfComponents(1)
    arr.SetNumberOfTuples(len(flat))
    for i, value in enumerate(flat):
        arr.SetValue(i, float(value))
    return arr


def _points_polydata(points_flat_nu_nv_3):
    """Pack an iterable of Nu*Nv*3 floats into a vtkPolyData with points.

    Row-major (u, v) ordering, matching the C++ contour parameterizer +
    Bezier fitter port-0 input contract introduced by issue #339.
    """
    import vtk

    flat = list(points_flat_nu_nv_3)
    n_points = len(flat) // 3
    pts = vtk.vtkPoints()
    pts.SetDataTypeToDouble()
    pts.SetNumberOfPoints(n_points)
    for i in range(n_points):
        pts.SetPoint(i, flat[i * 3 + 0], flat[i * 3 + 1], flat[i * 3 + 2])
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    return pd


def _basis_table(basis_2d):
    """Pack a 2D numpy array (n_rows x M) into a vtkTable with M columns."""
    import vtk

    n_rows, n_cols = basis_2d.shape
    table = vtk.vtkTable()
    for j in range(n_cols):
        col = vtk.vtkDoubleArray()
        col.SetNumberOfComponents(1)
        col.SetNumberOfTuples(n_rows)
        for i in range(n_rows):
            col.SetValue(i, float(basis_2d[i, j]))
        table.AddColumn(col)
    return table


def test_cxx_bezier_fitter_matches_pinned_control_points(algorithm_module):
    """C++ ``vtkLiverBezierFitter`` against the same EXPECTED control points.

    Tolerance is relaxed to ``rtol=1e-10`` to absorb Eigen-vs-LAPACK
    last-bit-of-double dispatch noise on the 4x4 inverse; see the
    module docstring and the matching C++ test for the rationale.

    Reads the fitted grid back through the polydata output (which is the
    Python-wrappable surface) rather than ``GetControlPoints()`` (which
    returns a const std::vector reference VTK does not wrap).

    Uses the post-#339 input-port surface: points on port 0 as a
    ``vtkPolyData``, BasisU/BasisV on ports 1/2 as ``vtkTable``.
    """
    points, basis_u, basis_v = _make_bezier_fixture()
    fitter = algorithm_module.vtkLiverBezierFitter()
    fitter.SetNumberOfSamples(4, 4)
    fitter.SetInputData(0, _points_polydata(points.flatten().tolist()))
    fitter.SetInputData(1, _basis_table(basis_u))
    fitter.SetInputData(2, _basis_table(basis_v))
    fitter.Update()

    out_points = fitter.GetOutput().GetPoints()
    assert out_points.GetNumberOfPoints() == 16
    cps = np.zeros((4, 4, 3), dtype=np.float64)
    for i in range(4):
        for j in range(4):
            p = out_points.GetPoint(i * 4 + j)
            cps[i, j, 0] = p[0]
            cps[i, j, 1] = p[1]
            cps[i, j, 2] = p[2]
    np.testing.assert_allclose(
        cps,
        EXPECTED_BEZIER_CONTROL_POINTS,
        rtol=_RTOL_LOOSE_BEZIER,
        atol=_ATOL_LOOSE_BEZIER,
    )


def test_cxx_elliptic_fourier_descriptors_matches_pinned_coefficients(
    algorithm_module,
):
    """C++ ``vtkLiverContourParameterizer::ComputeEFDCoefficients`` parity."""
    contour = _make_contour_fixture()
    contour_arr = _to_double_array(contour.flatten().tolist())
    coeffs_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeEFDCoefficients(
            contour_arr, 8
        )
    )
    n = coeffs_arr.GetNumberOfTuples()
    coeffs_flat = [coeffs_arr.GetValue(i) for i in range(n)]
    coeffs = np.array(coeffs_flat).reshape(8, 6)
    np.testing.assert_allclose(
        coeffs,
        EXPECTED_EFD_COEFFS,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


def test_cxx_calculate_dc_coefficients_matches_pinned_values(algorithm_module):
    """C++ ``vtkLiverContourParameterizer::ComputeDCCoefficients`` parity."""
    contour = _make_contour_fixture()
    contour_arr = _to_double_array(contour.flatten().tolist())
    dc_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeDCCoefficients(
            contour_arr
        )
    )
    dc = tuple(dc_arr.GetValue(i) for i in range(3))
    np.testing.assert_allclose(
        dc,
        EXPECTED_DC,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


def test_cxx_inverse_transform_matches_pinned_reconstruction(algorithm_module):
    """C++ ``vtkLiverContourParameterizer::InverseTransform`` parity.

    Uses the *pinned* EFD coefficients directly so this test isolates
    the inverse-transform path from any drift in the forward EFD.
    """
    coeffs_arr = _to_double_array(EXPECTED_EFD_COEFFS.flatten().tolist())
    recon_arr = (
        algorithm_module.vtkLiverContourParameterizer.InverseTransform(
            coeffs_arr, 8, 0.1, 0.2, 0.3, 12
        )
    )
    n = recon_arr.GetNumberOfTuples()
    recon_flat = [recon_arr.GetValue(i) for i in range(n)]
    recon = np.array(recon_flat).reshape(1, 3, 12)
    np.testing.assert_allclose(
        recon,
        EXPECTED_INVERSE_TRANSFORM,
        rtol=_RTOL_TIGHT,
        atol=_ATOL_TIGHT,
    )


# --------------------------------------------------------------------------- #
# Edge-case stress tests — issue #335.
#
# Drive the C++ Algorithm wrapper with degenerate / extreme inputs and
# assert either a defined output OR a defined failure mode (graceful
# vtkErrorMacro return).  The fixtures are deliberately small Python
# constructs so the test bodies stay readable and ctest output is
# self-documenting.  All assertions live behind the same
# ``algorithm_module`` fixture as the parity tests above, so the
# whole block skips cleanly when the wrapped Algorithm library is
# unavailable.
#
# Findings landed via this block are mirrored in the C++ ctkTest
# driver under LiverResections/Algorithm/Testing/Cxx/*EdgeCasesTest.cxx
# (same fixtures, same acceptance, same #335 traceability).  Whichever
# stage is faster to iterate wins for the day-to-day add-a-fixture loop.
# --------------------------------------------------------------------------- #


def _planar_circle(n, radius=1.0):
    """Return an (n+1) x 3 closed planar ring at z=0."""
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    pts = np.zeros((n + 1, 3), dtype=np.float64)
    pts[:n, 0] = radius * np.cos(theta)
    pts[:n, 1] = radius * np.sin(theta)
    pts[n] = pts[0]
    return pts


def test_cxx_efd_short_ring_above_nyquist(algorithm_module):
    """EFD with order > Nyquist on a 6-point ring: defined finite output."""
    ring = _planar_circle(6)
    coeffs_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeEFDCoefficients(
            _to_double_array(ring.flatten().tolist()), 8
        )
    )
    n = coeffs_arr.GetNumberOfTuples()
    coeffs = np.array([coeffs_arr.GetValue(i) for i in range(n)]).reshape(8, 6)
    assert coeffs.shape == (8, 6)
    assert np.all(np.isfinite(coeffs)), (
        "EFD coefficients on a 6-point ring must remain finite"
    )


def test_cxx_efd_duplicated_consecutive_points(algorithm_module):
    """Zero-length segment -> NaN propagation (known fragile behaviour).

    Pinned per ADR-0003: the current implementation divides each
    segment displacement by its arc-length without guarding against
    zero, so a duplicated consecutive point yields NaN coefficients.
    The C++ test surfaces the same behaviour via a sub-issue; this
    Python wrapper test is the dual-mode characterisation pin.
    """
    ring = _planar_circle(20)
    # Splice a duplicate of row 5.
    dup = np.insert(ring, 6, ring[5], axis=0)
    coeffs_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeEFDCoefficients(
            _to_double_array(dup.flatten().tolist()), 8
        )
    )
    n = coeffs_arr.GetNumberOfTuples()
    coeffs = np.array([coeffs_arr.GetValue(i) for i in range(n)])
    # ADR-0003 characterisation pin for issue #355
    # (https://github.com/ALive-research/Slicer-Liver/issues/355): the
    # current implementation divides each segment displacement by its
    # arc-length without guarding against zero, so a duplicated point
    # yields NaN coefficients.  Pinning has_nan == True gives CI a loud
    # signal the day a future fix lands — the assertion fails, the
    # fixer flips it to `assert not np.any(...)` and closes #355.
    has_nan = bool(np.any(np.isnan(coeffs)))
    assert has_nan, (
        "Characterisation pin inverted: zero-length-segment path no longer "
        "NaN-propagates.  If this is intentional (issue #355 fixed), invert "
        "the assertion to `assert not np.any(np.isnan(coeffs))` and close #355."
    )
    # TODO(#355): invert assertion to `assert not has_nan` when fixed.


def test_cxx_efd_planar_circle_round_trip(algorithm_module):
    """EFD-8 reconstruction of a 60-point unit circle approximates it."""
    ring = _planar_circle(60)
    coeffs_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeEFDCoefficients(
            _to_double_array(ring.flatten().tolist()), 8
        )
    )
    dc_arr = (
        algorithm_module.vtkLiverContourParameterizer.ComputeDCCoefficients(
            _to_double_array(ring.flatten().tolist())
        )
    )
    recon_arr = (
        algorithm_module.vtkLiverContourParameterizer.InverseTransform(
            coeffs_arr,
            8,
            dc_arr.GetValue(0),
            dc_arr.GetValue(1),
            dc_arr.GetValue(2),
            24,
        )
    )
    n = recon_arr.GetNumberOfTuples()
    recon = np.array(
        [recon_arr.GetValue(i) for i in range(n)], dtype=np.float64
    ).reshape(3, 24)
    radius = np.sqrt(recon[0] ** 2 + recon[1] ** 2)
    np.testing.assert_allclose(radius, 1.0, atol=5e-3)


def test_cxx_bezier_fitter_flat_surface(algorithm_module):
    """Flat z=0 input: control points must all sit on z=0."""
    u = np.linspace(0.0, 1.0, 4)
    v = np.linspace(0.0, 1.0, 4)
    points = np.zeros((4, 4, 3))
    for i in range(4):
        for j in range(4):
            points[i, j] = (u[i], v[j], 0.0)

    def bern3(t):
        t1 = 1.0 - t
        return np.array(
            [t1**3, 3.0 * t * t1**2, 3.0 * t**2 * t1, t**3]
        )

    basis_u = np.stack([bern3(t) for t in u])
    basis_v = np.stack([bern3(t) for t in v])

    fitter = algorithm_module.vtkLiverBezierFitter()
    fitter.SetNumberOfSamples(4, 4)
    fitter.SetInputData(0, _points_polydata(points.flatten().tolist()))
    fitter.SetInputData(1, _basis_table(basis_u))
    fitter.SetInputData(2, _basis_table(basis_v))
    fitter.Update()

    out_points = fitter.GetOutput().GetPoints()
    assert out_points.GetNumberOfPoints() == 16
    z_max = 0.0
    for k in range(16):
        z_max = max(z_max, abs(out_points.GetPoint(k)[2]))
    assert z_max < 1e-10, (
        "flat-input control points off z=0: max |z| = " + str(z_max)
    )
