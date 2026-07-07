# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Locator PRODUCER core (ADR-0025 Slice B) -- the GL-free pixel -> (u,v) -> world -> node chain.

ADR-0025 §"Producer -- exact 1:1 (u, v) mapping (no picker)" establishes that the
resectogram IS the Bezier (u, v) parameter-domain image, so a resectogram pixel
maps EXACTLY to a Bezier surface world point by direct surface evaluation -- there
is NO ``vtkCellPicker`` in the producer path (ADR-0025 §Alternatives A).  The
producer composes three pure steps:

    pixel (2)
      -> vtkLiverResectogramPixelMapping.PixelToUV -> (u, v)
      -> vtkMRMLBezierSurfaceNode.EvaluateSurface(u, v) -> 1-point vtkPolyData
      -> result.GetPoint(0) -> world point
      -> vtkMRMLLocatorNode.SetPickedPositionWorld(world)

This file pins the GL-free producer core in three invariants (all launched,
no render window):

  1. **Surface evaluation** (ADR-0025 §Conformance [test]: "Bezier surface
     evaluation at a known (u, v) matches the expected world-space point").
     On a KNOWN affine 4x4 control grid, ``EvaluateSurface(u, v)`` returns a
     1-point polydata whose ``GetPoint(0)`` matches the hand-computed Bezier
     world point.  The (u,v) = (0,0) and (1,1) corners are exact anchors (the
     grid corner control points); an interior point checks the tensor product.
  2. **Pixel -> UV** (pure static ``vtkLiverResectogramPixelMapping.PixelToUV``,
     ADR-0025 §Producer): a known pixel + viewport + matRatio maps to the
     expected (u, v) -- viewport-centre -> (0.5, 0.5) for ANY ratio (the
     scaling fixed point, ADR-0025 §Context), off-centre divides out the ratio.
  3. **Producer composition** (``ResectogramLocatorProducer.produce``): a pixel
     is composed through steps 2 then 1 to a world point, written onto the
     resolved ``vtkMRMLLocatorNode``'s ``PickedPositionWorld`` and returned; a
     degenerate input (zero-extent viewport) is a no-op-safe path returning
     ``None`` and leaving the node's picked position unchanged.

SCOPE (explicitly OUT): the Qt event-filter click sourcing in
``ResectionPlanningWidget`` and the click -> marker end-to-end are the
INTERACTION layer, verified on the interactive ``:0`` pass (ADR-0025
§Click-to-reslice; the full producer -> node -> consumer chain is the
consumer-side [test], ADR-0025 Slice C).  This file pins ONLY the GL-free
pixel -> (u,v) -> world -> node kernel.

-- VERIFIED API (from the merged headers + wrapped-helper usage) --

  * ``vtkLiverResectogramPixelMapping.PixelToUV`` -- STATIC, pure (Algorithm
    library, no MRML/GL -- ADR-0015 §1).  C++:
    ``static void PixelToUV(const double pixel[2], const int viewportSize[2],
    const double matRatio[2], double uvOut[2])``.  The Python wrap follows the
    SAME mutable-out-arg convention the sibling
    ``vtkLiverResectogramAspectRatio.ComputeAspectRatio(..., ratioOut)`` helper
    uses (see FlattenedSurfaceRepresentation._compute_mat_ratio): the trailing
    fixed-size non-const ``double[2]`` is a preallocated 2-list mutated IN
    PLACE, and the call is on the CLASS (static), not an instance:
        uv_out = [0.0, 0.0]
        vtkLiverResectogramPixelMapping.PixelToUV(pixel, viewport, ratio, uv_out)
    Reachable via the ``vtk`` or ``slicer`` namespace inside a launched Slicer.
  * ``vtkMRMLBezierSurfaceNode.EvaluateSurface(u, v)`` -> a 1-point
    ``vtkPolyData``; the world point is ``result.GetPoint(0)`` (Bernstein-samples
    the control grid at the single (u, v), vtkMRMLBezierSurfaceNode.cxx).
  * ``vtkMRMLBezierSurfaceNode.SetControlPoint(row, col, x, y, z)`` -- the
    Python-wrappable per-point grid seam (the flat ``SetControlGrid(const
    double*)`` is not Python-wrappable); round-trips via ``GetControlGridVector``.
  * ``vtkMRMLLocatorNode.SetPickedPositionWorld(x, y, z)`` /
    ``GetPickedPositionWorld()`` -- TRANSIENT double[3] RAS world point.
  * Carrier minted via
    ``slicer.modules.liverresections.logic().CreateResectionPlan(name)
    .GetGeometryNode()`` (a ``vtkMRMLBezierSurfaceNode``), the resection-plan
    create-API.

-- THE PRODUCER ENTITY THIS PINS (so the implementer matches) --

  ``LiverResectionsLib.ResectogramLocatorProducer.ResectogramLocatorProducer``
  (standalone Python, ADR-0004; ADR-0025 §Producer).  API shape pinned here:

    * constructor takes the surface carrier + the target ``vtkMRMLLocatorNode``:
        ResectogramLocatorProducer(surface_node, locator_node)
    * ``produce(pixel, viewport_size, mat_ratio) -> tuple | None`` -- composes
      PixelToUV -> EvaluateSurface -> GetPoint(0) -> locator.SetPickedPositionWorld,
      returns the world point tuple, or ``None`` on a degenerate/out-of-range
      input (no-op-safe: the node is left unchanged).

  ``pixel`` / ``mat_ratio`` are 2-sequences of floats; ``viewport_size`` a
  2-sequence of ints (matching the C++ ``const int viewportSize[2]``).

-- WHY LAUNCHED-SLICER --

The wrapped ``vtkLiverResectogramPixelMapping`` / ``vtkMRMLBezierSurfaceNode`` /
``vtkMRMLLocatorNode`` + the ``CreateResectionPlan`` create-API are reachable
only inside a launched Slicer with the module loaded; a bare ``PythonSlicer -m
pytest`` has ``slicer.mrmlScene is None`` and those classes off the path, so
every test here SKIPS CLEANLY via the shared ``slicer_pytest_support`` guards.
All GL-free: the producer needs no render window (that is the whole point of the
1:1 (u,v) mapping vs a picker).

-- RUN-VS-SKIP DISCIPLINE --

Under a launched Slicer, invariants 1 + 2 (the wrapped Algorithm + MRML classes
that ARE merged) must actually RUN; invariant 3 is skip-pending on the
``ResectogramLocatorProducer`` producer entity (import + ``produce`` method) per
ADR-0027 -- the skip lifts at the implementation commit.  Verify run-vs-skip in
the CI log, never trust overall green (the launched harness is
green-but-skipping prone).

See also:
  * Docs/adr/0025-locator-architecture.md §Producer, §Context, §Conformance
  * Docs/adr/0015-algorithm-library.md §1  (pure-VTK, no MRML/GL)
  * Docs/adr/0013-layerdm-pipeline-pattern.md §5, §6
  * Docs/adr/0004-python-cpp-boundary.md  (producer is Python)
  * Docs/adr/0027-invariant-test-first.md  (RED / skip-pending discipline)
  * LiverResections/Algorithm/vtkLiverResectogramPixelMapping.h
  * LiverResections/MRML/vtkMRMLBezierSurfaceNode.cxx  (EvaluateSurface)
  * LiverResections/Testing/Python/test_bezier_planning_locator_consumer.py
  * LiverResections/Testing/Python/test_pipeline_control_point_edit.py
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
LOCATOR_NODE_CLASS = "vtkMRMLLocatorNode"
PIXEL_MAPPING_CLASS = "vtkLiverResectogramPixelMapping"

# The producer entity (ADR-0025 Slice B).  Invariant 3 skips-pending on its absence.
PRODUCER_MODULE = "LiverResectionsLib.ResectogramLocatorProducer"
PRODUCER_CLASS = "ResectogramLocatorProducer"

# World-point float tolerance (the carrier stores double; Bernstein sums
# accumulate rounding).  Loose enough for the summation, tight enough that a
# wrong (u, v) ordering or a factor error fails.
WORLD_TOL = 1e-6
UV_TOL = 1e-9


# --------------------------------------------------------------------------- #
# Skip-guards (mirror test_pipeline_control_point_edit.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _wrapped_class_or_skip(slicer, name):
    """Resolve a wrapped LiverResections Algorithm class.

    The Algorithm-library classes are NOT surfaced on the ``slicer`` / ``vtk``
    namespaces even inside a launched Slicer; they live in the loadable module's
    Python wrapping ``vtkSlicerLiverResectionsModuleAlgorithmPython`` (on
    ``sys.path`` via the module search path).  Resolve there first, then fall
    back to the namespaces defensively.  Skips cleanly when off the path (bare
    pytest / a build without the module), never errors at collection.
    """
    import vtk

    factory = None
    try:
        import vtkSlicerLiverResectionsModuleAlgorithmPython as _algo

        factory = getattr(_algo, name, None)
    except ImportError:
        factory = None
    if factory is None:
        factory = getattr(vtk, name, None)
    if factory is None:
        factory = getattr(slicer, name, None)
    if factory is None:
        pytest.skip(
            f"{name} not reachable (Algorithm wrapping / vtk / slicer) -- the "
            "wrapped class is not present in this build."
        )
    return factory


def _resection_logic_or_skip(slicer):
    """Return ``vtkSlicerLiverResectionsLogic`` with the create-API, or skip."""
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered in this build.")
    logic = module.logic()
    if logic is None:
        pytest.skip("liverresections module has no logic singleton.")
    if not hasattr(logic, "CreateResectionPlan"):
        pytest.skip(
            "vtkSlicerLiverResectionsLogic has no CreateResectionPlan -- the "
            "resection-plan create-API is not in this build."
        )
    return logic


def _make_affine_carrier_or_skip(slicer, name):
    """Mint a carrier and seed the KNOWN affine 4x4 control grid.

    Grid ``P[r][c] = (x = c*10, y = r*10, z = 0)``.  For a deg-3 tensor Bezier
    this makes the surface EXACTLY affine in (u, v):
        x = 30 * v,  y = 30 * u,  z = 0
    (the index-linear control net Bezier reproduces the affine map; verified by
    hand -- see the module docstring).  So the corners and any interior point
    have a trivially hand-computable expected world point.
    """
    logic = _resection_logic_or_skip(slicer)
    plan = logic.CreateResectionPlan(name)
    if plan is None:
        pytest.skip("CreateResectionPlan returned None -- carrier not minted.")
    carrier = plan.GetGeometryNode()
    if carrier is None or carrier.GetClassName() != BEZIER_NODE_CLASS:
        pytest.skip(
            "plan geometry node is not a vtkMRMLBezierSurfaceNode carrier -- "
            "cannot exercise EvaluateSurface."
        )
    if not hasattr(carrier, "SetControlPoint"):
        pytest.skip(
            "carrier has no SetControlPoint -- the Python grid seam (slice 1d) "
            "is not in this build."
        )
    if not hasattr(carrier, "EvaluateSurface"):
        pytest.skip(
            "carrier has no EvaluateSurface -- the parametric-surface evaluator "
            "is not in this build."
        )
    rows = int(carrier.GetRows())
    cols = int(carrier.GetCols())
    if rows * cols != 16:
        pytest.skip(f"expected a default 4x4 grid, got {rows}x{cols}.")
    for r in range(rows):
        for c in range(cols):
            carrier.SetControlPoint(r, c, float(c) * 10.0, float(r) * 10.0, 0.0)
    return carrier


def _expected_world_for_uv(u, v):
    """The hand-computed world point of the affine grid at (u, v).

    x = 30 * v, y = 30 * u, z = 0 (see ``_make_affine_carrier_or_skip``).  NOTE
    the ordering: EvaluateSurface(u, v) samples Bernstein(i, degU, u) over ROWS
    (y = r*10) and Bernstein(j, degV, v) over COLS (x = c*10), so u drives y and
    v drives x.  Pinning this ordering guards a u/v swap in the producer.
    """
    return (30.0 * v, 30.0 * u, 0.0)


def _eval_world(carrier, u, v):
    """Evaluate the carrier at (u, v) and return ``GetPoint(0)`` as a tuple."""
    poly = carrier.EvaluateSurface(u, v)
    assert poly is not None, "EvaluateSurface must return a non-null vtkPolyData."
    assert poly.GetNumberOfPoints() >= 1, (
        "EvaluateSurface must emit at least the single sampled point "
        f"(got {poly.GetNumberOfPoints()})."
    )
    return tuple(poly.GetPoint(0))


def _pixel_to_uv(mapping, pixel, viewport, ratio):
    """Call the static PixelToUV via the mutable-out-arg wrap; return (u, v).

    Mirrors ``vtkLiverResectogramAspectRatio.ComputeAspectRatio(..., ratioOut)``:
    the trailing fixed-size ``double[2]`` is a preallocated 2-list mutated in
    place (see FlattenedSurfaceRepresentation._compute_mat_ratio).  Should the
    wrap instead surface it as a return, fall back to that.
    """
    uv_out = [0.0, 0.0]
    result = mapping.PixelToUV(list(pixel), list(viewport), list(ratio), uv_out)
    # Prefer the mutated out-arg (the confirmed convention); tolerate a
    # returning variant if this build wraps it that way.
    if result is not None:
        try:
            return (float(result[0]), float(result[1]))
        except (TypeError, IndexError, ValueError):
            pass
    return (float(uv_out[0]), float(uv_out[1]))


def _make_producer_or_skip(slicer, carrier, locator):
    """Construct a ``ResectogramLocatorProducer`` or skip-pending (ADR-0027).

    RED == the producer module/class or its ``produce`` method is absent; the
    skip lifts at the producer implementation commit.
    """
    try:
        module = __import__(PRODUCER_MODULE, fromlist=[PRODUCER_CLASS])
        producer_cls = getattr(module, PRODUCER_CLASS)
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"{PRODUCER_CLASS} not importable ({exc!r}) -- the ADR-0025 locator "
            "producer has not landed.  Skip lifts at the implementation "
            "commit (ADR-0027)."
        )
    producer = producer_cls(carrier, locator)
    if not hasattr(producer, "produce"):
        pytest.skip(
            f"{PRODUCER_CLASS} has no produce() method -- the producer "
            "composition seam has not landed.  Skip lifts at the "
            "implementation commit (ADR-0027)."
        )
    return producer


# --------------------------------------------------------------------------- #
# Invariant 1 -- surface evaluation at a KNOWN (u, v) (ADR-0025 §Conformance)
# --------------------------------------------------------------------------- #


def test_evaluate_surface_corners_are_grid_corner_control_points():
    """Invariant 1a: the (0,0) and (1,1) corners are exact anchors.

    On the affine 4x4 grid, EvaluateSurface(0, 0) is P[0][0] = (0, 0, 0) and
    EvaluateSurface(1, 1) is P[3][3] = (30, 30, 0) -- the Bezier endpoint
    interpolation property.  These are the exact-arithmetic anchors of the 1:1
    mapping the producer relies on (ADR-0025 §Conformance [test]).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "LocatorProducerEvalCorners")

    got00 = _eval_world(carrier, 0.0, 0.0)
    assert got00 == pytest.approx(_expected_world_for_uv(0.0, 0.0), abs=WORLD_TOL), (
        "EvaluateSurface(0, 0) must interpolate the (0, 0) corner control point "
        f"P[0][0] = (0, 0, 0); got {got00}."
    )

    got11 = _eval_world(carrier, 1.0, 1.0)
    assert got11 == pytest.approx(_expected_world_for_uv(1.0, 1.0), abs=WORLD_TOL), (
        "EvaluateSurface(1, 1) must interpolate the (1, 1) corner control point "
        f"P[3][3] = (30, 30, 0); got {got11}."
    )


def test_evaluate_surface_interior_matches_hand_computed_point():
    """Invariant 1b: an interior (u, v) matches the hand-computed world point.

    EvaluateSurface(0.25, 0.75) on the affine grid must be (30*0.75, 30*0.25, 0)
    = (22.5, 7.5, 0).  A non-corner point exercises the full tensor-product
    Bernstein sum AND pins the u->y / v->x ordering the producer must preserve
    (ADR-0025 §Producer: the exact 1:1 mapping).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "LocatorProducerEvalInterior")

    u, v = 0.25, 0.75
    got = _eval_world(carrier, u, v)
    assert got == pytest.approx(_expected_world_for_uv(u, v), abs=WORLD_TOL), (
        f"EvaluateSurface({u}, {v}) must be the hand-computed affine world point "
        f"{_expected_world_for_uv(u, v)} (x = 30*v, y = 30*u); got {got}.  A "
        "u/v swap or a Bernstein-weight error fails here."
    )


# --------------------------------------------------------------------------- #
# Invariant 2 -- pixel -> (u, v) (pure static PixelToUV, ADR-0025 §Producer)
# --------------------------------------------------------------------------- #


def test_pixel_to_uv_centre_is_half_for_any_ratio():
    """Invariant 2a: the viewport centre maps to (0.5, 0.5) for ANY matRatio.

    ADR-0025 §Context: matRatio scales the flattened quad about the viewport
    centre, so the centre is the scaling FIXED POINT -- it maps to (0.5, 0.5)
    for both the isotropic (1, 1) and an anisotropic (2, 0.5) ratio.
    """
    slicer = _slicer_or_skip()
    mapping = _wrapped_class_or_skip(slicer, PIXEL_MAPPING_CLASS)

    viewport = [256, 256]
    centre = [128.0, 128.0]

    for ratio in ([1.0, 1.0], [2.0, 0.5]):
        u, v = _pixel_to_uv(mapping, centre, viewport, ratio)
        assert u == pytest.approx(0.5, abs=UV_TOL) and v == pytest.approx(
            0.5, abs=UV_TOL
        ), (
            "the viewport-centre pixel is the matRatio scaling fixed point and "
            f"must map to (0.5, 0.5) for ratio {ratio} (ADR-0025 §Context); got "
            f"({u}, {v})."
        )


def test_pixel_to_uv_isotropic_is_plain_linear():
    """Invariant 2b: for isotropic (1, 1) the map is plain linear pixel/extent.

    ADR-0025 §Context: an isotropic ratio gives u = pixel.x / width,
    v = pixel.y / height.  The origin -> (0, 0), the top-right -> (1, 1), a
    quarter pixel -> (0.25, 0.75).  This is exactly the (u, v) the interior
    evaluation test consumes, so 2b + 1b compose into invariant 3.
    """
    slicer = _slicer_or_skip()
    mapping = _wrapped_class_or_skip(slicer, PIXEL_MAPPING_CLASS)

    viewport = [256, 256]
    ratio = [1.0, 1.0]

    cases = [
        ([0.0, 0.0], (0.0, 0.0)),
        ([256.0, 256.0], (1.0, 1.0)),
        ([64.0, 192.0], (0.25, 0.75)),
    ]
    for pixel, want in cases:
        u, v = _pixel_to_uv(mapping, pixel, viewport, ratio)
        assert (u, v) == pytest.approx(want, abs=UV_TOL), (
            f"isotropic PixelToUV({pixel}) must be plain linear -> {want} "
            f"(ADR-0025 §Context); got ({u}, {v})."
        )


# --------------------------------------------------------------------------- #
# Invariant 3 -- producer composition (skip-pending on the producer entity)
# --------------------------------------------------------------------------- #


def test_producer_writes_picked_position_from_pixel():
    """Invariant 3a: produce() composes pixel -> (u,v) -> world -> node.

    A pixel (64, 192) in a 256x256 viewport at isotropic ratio maps to
    (u, v) = (0.25, 0.75) (invariant 2b), which evaluates to world
    (22.5, 7.5, 0) (invariant 1b).  ``produce`` must write THAT world point onto
    the locator node's PickedPositionWorld and RETURN it (ADR-0025 §Producer:
    the exact 1:1 mapping delivered to the vtkMRMLLocatorNode).
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "LocatorProducerComposePos")
    locator = slicer.mrmlScene.AddNewNodeByClass(LOCATOR_NODE_CLASS)
    if locator is None:
        pytest.skip(f"{LOCATOR_NODE_CLASS} not registered in this build.")

    producer = _make_producer_or_skip(slicer, carrier, locator)

    pixel = [64.0, 192.0]
    viewport = [256, 256]
    ratio = [1.0, 1.0]
    expected = _expected_world_for_uv(0.25, 0.75)  # (22.5, 7.5, 0.0)

    returned = producer.produce(pixel, viewport, ratio)

    assert returned is not None, (
        "produce() must return the composed world point for an in-range pixel; "
        "got None."
    )
    assert tuple(returned) == pytest.approx(expected, abs=WORLD_TOL), (
        f"produce({pixel}) must return the world point pixel maps to {expected} "
        f"(pixel -> (0.25, 0.75) -> world); got {tuple(returned)}."
    )
    written = tuple(locator.GetPickedPositionWorld())
    assert written == pytest.approx(expected, abs=WORLD_TOL), (
        "produce() must write the composed world point onto the locator node's "
        f"PickedPositionWorld (ADR-0025 §Producer); got {written}, expected "
        f"{expected}."
    )


def test_producer_degenerate_input_is_no_op_returning_none():
    """Invariant 3b: a degenerate input is a no-op returning None.

    A zero-extent viewport (width/height 0) has no valid pixel->(u,v) inversion;
    ``produce`` must return ``None`` and leave the locator node's
    PickedPositionWorld UNCHANGED (no false pick fed to the consumer).  Pinned by
    first seeding a known picked position, then confirming the degenerate call
    does not disturb it.
    """
    slicer = _slicer_or_skip()
    carrier = _make_affine_carrier_or_skip(slicer, "LocatorProducerDegenerate")
    locator = slicer.mrmlScene.AddNewNodeByClass(LOCATOR_NODE_CLASS)
    if locator is None:
        pytest.skip(f"{LOCATOR_NODE_CLASS} not registered in this build.")

    producer = _make_producer_or_skip(slicer, carrier, locator)

    sentinel = (11.0, 22.0, 33.0)
    locator.SetPickedPositionWorld(*sentinel)

    returned = producer.produce([10.0, 10.0], [0, 0], [1.0, 1.0])

    assert returned is None, (
        "produce() must return None for a degenerate (zero-extent) viewport "
        f"rather than a bogus world point; got {returned!r}."
    )
    after = tuple(locator.GetPickedPositionWorld())
    assert after == pytest.approx(sentinel, abs=WORLD_TOL), (
        "a degenerate produce() must not disturb the locator node's picked "
        f"position; it changed from {sentinel} to {after}."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
