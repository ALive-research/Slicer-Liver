# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0038 -- the 3D volumetry pipeline RENDERS a glyph per carrier seed.

The shared ``SurfacePointPlacementPipeline3D`` base iterates the provider
only for hit-testing; it draws nothing.  So the volumetry 3D client
(``VolumetrySeedPipeline3D``) must render the placed-seed glyphs itself --
mirroring the territory client's ``_rebuild_seed_actor`` (a ``vtkPolyData``
of seed points glyphed by a ``vtkSphereSource`` into a ``vtkActor``,
coloured per the provider's per-point colour).  Without it a placed
volumetry seed is invisible in the 3D view.

This file pins that contract at the data level (GL-free): a carrier with N
seeds yields a seed-glyph point set of N points, rebuilt on the carrier's
``Modified`` (the placement / edit trigger), coloured from the carrier's
per-seed colour.  The seeds are an INDEPENDENT glyph actor -- not tied to a
liver/model surface -- so they render with no model loaded; the live
:0-view verification of that (a visible glyph with no model shown) rides the
interactive walkthrough, not this bare-data assertion.

HARNESS: launched Slicer.  Needs LayerDMLib (the base) + the wrapped
``vtkMRMLVolumetrySeedsNode`` carrier / display node; a bare
``PythonSlicer -m pytest`` SKIPS CLEANLY via the ``slicer_pytest_support``
guards.  Verify run-vs-skip in the CI log -- never trust overall green.

References
----------
* ADR-0038 -- §Decision (the base client seam) + §"Consumers ledger"
  (LiverVolumetry client renders its own seed glyphs).
* VascularTerritoriesLib/TerritoryPlacementPipeline.py -- the
  ``_rebuild_seed_actor`` pattern this mirrors (minus the territory grouping
  + vessel-visibility gate; volumetry is flat).
* ADR-0013 §5 -- rendering through the scripted Pipeline, no custom DM.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

vtk = pytest.importorskip("vtk")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
for candidate in (
    REPO_ROOT / "SlicerLiverInteractionLib",
    REPO_ROOT / "LiverVolumetry" / "LiverVolumetryLib",
    REPO_ROOT / "LiverVolumetry",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _import_pipeline_or_skip():
    try:
        from VolumetrySeedPipeline import (
            VolumetrySeedPipeline3D,
            VOLUMETRY_NAMESPACE,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"VolumetrySeedPipeline3D not importable ({exc!r}) -- the ADR-0038 "
            "volumetry 3D client / LayerDMLib base is not reachable here."
        )
    return VolumetrySeedPipeline3D, VOLUMETRY_NAMESPACE


def _bind_carrier(slicer, namespace):
    """A carrier + display node with the carrier bound as the shared reference."""
    from PointPlacementState import PointPlacementState

    carrier = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "GlyphSeeds")
    display = slicer.mrmlScene.AddNewNodeByClass(DISPLAY_NODE_CLASS, "GlyphDisplay")
    if carrier is None or display is None or not hasattr(carrier, "AddSeed"):
        pytest.skip(f"{SEEDS_NODE_CLASS}/{DISPLAY_NODE_CLASS} not registered.")
    PointPlacementState(namespace).set_carrier(display, carrier)
    return carrier, display


def _wired_pipeline(Pipeline, display):
    """A 3D pipeline resolving its carrier from the shared display node."""
    pipeline = Pipeline()
    pipeline.SetDisplayNode(display)
    # UpdatePipeline is LayerDM's post-carrier-bind hook: it re-resolves the
    # provider from the display node AND attaches the seed-glyph observer.
    pipeline.UpdatePipeline()
    if not hasattr(pipeline, "GetSeedPolyData"):
        pytest.skip(
            "VolumetrySeedPipeline3D has no GetSeedPolyData seam -- the seed-glyph "
            "rendering has not landed."
        )
    return pipeline


def test_empty_carrier_renders_no_seed_glyph(monkeypatch):
    """An empty carrier yields an empty seed-glyph point set (no stray glyph)."""
    slicer = _slicer_or_skip()
    Pipeline, namespace = _import_pipeline_or_skip()
    _carrier, display = _bind_carrier(slicer, namespace)
    pipeline = _wired_pipeline(Pipeline, display)

    assert pipeline.GetSeedPolyData().GetNumberOfPoints() == 0, (
        "an empty carrier must render no seed glyph."
    )


def test_seed_glyph_has_one_point_per_carrier_seed(monkeypatch):
    """A carrier with N seeds renders a seed-glyph point set of N points.

    The glyph rebuilds on the carrier's ``Modified`` (the placement / edit
    trigger), so a seed placed after the pipeline is wired appears without any
    further call -- the invisible-3D-seed regression is exactly a rebuild that
    never fires (ADR-0038 §"Consumers ledger").
    """
    slicer = _slicer_or_skip()
    Pipeline, namespace = _import_pipeline_or_skip()
    carrier, display = _bind_carrier(slicer, namespace)
    pipeline = _wired_pipeline(Pipeline, display)

    carrier.AddSeed(20.0, 20.0, 10.0)
    assert pipeline.GetSeedPolyData().GetNumberOfPoints() == 1, (
        "a seed placed on the carrier must render one glyph point (rebuilt on "
        "the carrier Modified)."
    )

    carrier.AddSeed(15.0, 15.0, 8.0)
    carrier.AddSeed(25.0, 25.0, 12.0)
    assert pipeline.GetSeedPolyData().GetNumberOfPoints() == 3, (
        "the seed-glyph point count must track the carrier's seed count."
    )

    carrier.RemoveNthSeed(0)
    assert pipeline.GetSeedPolyData().GetNumberOfPoints() == 2, (
        "removing a seed must drop its glyph point."
    )


def test_seed_glyph_colour_follows_the_seed_volume(monkeypatch):
    """Each glyph point carries the seed's VOLUME colour (RGB, 0..255).

    territory-usability: a seed grouped into a named volume takes THAT volume's
    colour (``GetVolumeColor``), the same colour shown on the volume's table row
    and the slice handles -- so differently-coloured volumes read apart in the
    3D view.  Mirrors ``TerritoryPointProvider``'s per-group colour lookup.  A
    seed with no volume falls back to its per-seed colour (the legacy /
    ungrouped seed still renders).
    """
    slicer = _slicer_or_skip()
    Pipeline, namespace = _import_pipeline_or_skip()
    carrier, display = _bind_carrier(slicer, namespace)
    pipeline = _wired_pipeline(Pipeline, display)

    for method in ("SetNthSeedVolume", "SetVolumeColor", "SetNthSeedColor"):
        if not hasattr(carrier, method):
            pytest.skip(f"carrier has no {method} -- cannot pin glyph colour.")

    # A seed grouped into a red volume renders in the VOLUME colour, even when
    # its own per-seed colour differs -- the volume colour wins for a grouped
    # seed (one source of truth per volume).
    grouped = carrier.AddSeed(20.0, 20.0, 10.0)
    carrier.SetNthSeedColor(grouped, 0.0, 1.0, 0.0)  # green per-seed colour
    carrier.SetNthSeedVolume(grouped, "V1")
    carrier.SetVolumeColor("V1", 1.0, 0.0, 0.0)  # red volume colour

    # An UNGROUPED seed keeps its own per-seed colour (the fallback path).
    ungrouped = carrier.AddSeed(30.0, 30.0, 15.0)
    carrier.SetNthSeedColor(ungrouped, 0.0, 0.0, 1.0)  # blue

    scalars = pipeline.GetSeedPolyData().GetPointData().GetScalars()
    assert scalars is not None and scalars.GetNumberOfTuples() == 2
    assert scalars.GetTuple3(0) == pytest.approx((255.0, 0.0, 0.0), abs=1.0), (
        "a grouped seed's glyph colour must follow its VOLUME colour."
    )
    assert scalars.GetTuple3(1) == pytest.approx((0.0, 0.0, 255.0), abs=1.0), (
        "an ungrouped seed's glyph colour falls back to its per-seed colour."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
