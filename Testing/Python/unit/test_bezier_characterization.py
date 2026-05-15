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
the source) under **NumPy 2.3.1** in a plain Guix shell, *not* inside a
Slicer Python.  The methods on ``LiverLogic`` use no ``self``-state
(verified by inspection — they call only ``numpy`` operators and, when
``normalize=False``, no other instance methods), so the replay is
byte-equivalent to calling the method on a constructed ``LiverLogic()``
inside Slicer's Python.  If a future maintainer updates these constants,
they must (a) document the Slicer + NumPy versions in this docstring and
(b) explain the behaviour change in the PR body, per ADR-0003 §1.

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
    # ``import LiverSegments`` / ``import LiverVolumetry`` resolve to the
    # sibling source trees.
    liver_dir = str(REPO_ROOT / "Liver")
    if liver_dir not in sys.path:
        sys.path.insert(0, liver_dir)
    for sibling in ("LiverSegments", "LiverVolumetry"):
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

def _bernstein_degree_4(t: float) -> np.ndarray:
    """Bernstein basis B_{4,0..4}(t) — degree-4 polynomials in [0, 1]."""
    return np.array(
        [
            (1 - t) ** 4,
            4 * t * (1 - t) ** 3,
            6 * t ** 2 * (1 - t) ** 2,
            4 * t ** 3 * (1 - t),
            t ** 4,
        ]
    )


def _make_bezier_fixture():
    """A 5x5x3 grid of saddle-surface points plus matching 5x5 Bernstein bases.

    The control-net is the bilinear surface ``z = u*v`` sampled on a
    uniform 5x5 ``(u, v)`` grid; the basis matrices evaluate
    Bernstein-4 polynomials at the same sample locations.  Because the
    basis matrices are square (5x5), ``transpose(B)*B`` is invertible
    in exact arithmetic — the pseudo-inverse formulation collapses to
    the exact inverse, which is what makes the captured EXPECTED stable
    across NumPy versions for a characterisation pin.
    """
    u_samples = np.linspace(0.0, 1.0, 5)
    v_samples = np.linspace(0.0, 1.0, 5)
    basis_u = np.stack([_bernstein_degree_4(t) for t in u_samples], axis=0)
    basis_v = np.stack([_bernstein_degree_4(t) for t in v_samples], axis=0)

    points = np.zeros((5, 5, 3), dtype=np.float64)
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

# fit_bezier_surface: shape (5, 5, 3).  Recall the control net was the
# bilinear z = u*v on a uniform (u, v) grid — and because the Bernstein
# bases on a uniform 5-sample grid form a non-singular square matrix,
# the recovered control points reproduce the input lattice nearly
# exactly (modulo ~1e-17 floating-point dust on entries that are
# mathematically zero, and ~1e-15 relative error on the non-zero
# entries from the matrix-inverse round-trip).  Captured at full
# float64 precision so the assertion can run at ``rtol=1e-12``.
EXPECTED_BEZIER_CONTROL_POINTS = np.array(
    [
        [
            [2.1335056041739302e-17, -3.1679032227310840e-18, -6.7587392791774200e-35],
            [2.1335056041739311e-17, 2.4999999999999936e-01, 5.3337640104348109e-18],
            [2.1335056041739191e-17, 4.9999999999999800e-01, 1.0667528020869609e-17],
            [2.1335056041739308e-17, 7.5000000000000111e-01, 1.6001292031304480e-17],
            [2.1335056041739296e-17, 9.9999999999999989e-01, 2.1335056041739296e-17],
        ],
        [
            [2.5000000000000366e-01, -3.1679032227311156e-18, -7.9197580568278295e-19],
            [2.5000000000000372e-01, 2.5000000000000161e-01, 6.2500000000000819e-02],
            [2.5000000000000255e-01, 5.0000000000000377e-01, 1.2500000000000114e-01],
            [2.5000000000000366e-01, 7.5000000000000733e-01, 1.8750000000000328e-01],
            [2.5000000000000361e-01, 1.0000000000000095e+00, 2.5000000000000361e-01],
        ],
        [
            [4.9999999999999045e-01, -3.1679032227310162e-18, -1.5839516113655116e-18],
            [4.9999999999999040e-01, 2.4999999999999487e-01, 1.2499999999999707e-01],
            [4.9999999999998856e-01, 4.9999999999998579e-01, 2.4999999999999478e-01],
            [4.9999999999999045e-01, 7.4999999999998757e-01, 3.7499999999999245e-01],
            [4.9999999999999040e-01, 9.9999999999997924e-01, 4.9999999999999040e-01],
        ],
        [
            [7.5000000000000355e-01, -3.1679032227311033e-18, -2.3759274170483255e-18],
            [7.5000000000000422e-01, 2.5000000000000050e-01, 1.8750000000000042e-01],
            [7.5000000000000056e-01, 5.0000000000000244e-01, 3.7500000000000100e-01],
            [7.5000000000000411e-01, 7.5000000000000444e-01, 5.6250000000000278e-01],
            [7.5000000000000333e-01, 1.0000000000000060e+00, 7.5000000000000333e-01],
        ],
        [
            [9.9999999999999978e-01, -3.1679032227310833e-18, -3.1679032227310833e-18],
            [9.9999999999999967e-01, 2.4999999999999906e-01, 2.4999999999999908e-01],
            [9.9999999999999523e-01, 4.9999999999999833e-01, 4.9999999999999833e-01],
            [9.9999999999999956e-01, 7.5000000000000000e-01, 7.5000000000000000e-01],
            [9.9999999999999967e-01, 9.9999999999999978e-01, 9.9999999999999967e-01],
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

    assert cps.shape == (5, 5, 3), (
        f"fit_bezier_surface returned shape {cps.shape}, expected (5, 5, 3)"
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
