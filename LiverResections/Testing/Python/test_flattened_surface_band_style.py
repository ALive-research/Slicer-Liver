# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Resectogram-margins slice 1 -- band STYLE reaches the 2D mapper.

The resectogram's flattened strip classifies its two margin bands in the
``vtkOpenGLResection2DPolyDataMapper`` fragment shader from three STYLE
inputs -- ``uResectionMarginColor``, ``uUncertaintyMarginColor``,
``uInterpolatedMargins``.  Per the target node hierarchy
(Docs/architecture/target-mrml-node-hierarchy.md, "display node carries
margin colors only") these live on the SHARED
``vtkMRMLParametricSurfaceDisplayNode`` -- the same node the 3D
``BezierPlanningRepresentation`` reads -- so the 3D surface and the
resectogram always show identical band colours from one source of truth.

The gap this pins: ``FlattenedSurfaceRepresentation`` threads the margin
SCALARS off the plan wrapper (``_apply_resection_margins``) but pushes NO
style -- the 2D mapper silently rides its compiled-in defaults, and a
user-edited colour or the InterpolatedMargins flag never reaches the strip.

-- GL-FREE VIA A FAKE MAPPER --

Same idiom as ``test_flattened_surface_plan_shading.py``: a fake mapper
records the style setter calls so the threading is asserted without a GL
context.  The actual band render stays on the :0 eyeball checklist of the
resectogram-margins epic.

-- WHY LAUNCHED-SLICER (soft) --

The positive path reads a wrapped ``vtkMRMLParametricSurfaceDisplayNode``;
skips cleanly under bare pytest via the shared ``slicer_pytest_support``
guards + the ``SetSurfaceDisplayNode`` seam gate.

-- WHY RED NOW --

``FlattenedSurfaceRepresentation`` has no ``SetSurfaceDisplayNode`` seam, so
every test SKIPS cleanly.  The skip lifts when slice 1 lands
(ADR-0027 §Conformance).

See also:
  * Docs/adr/0031-distance-map-input-on-resection-plan.md (margins cluster)
  * Docs/architecture/target-mrml-node-hierarchy.md (colour placement)
  * LiverResections/LiverResectionsLib/Representations/FlattenedSurfaceRepresentation.py
  * LiverResections/LiverResectionsLib/Representations/BezierPlanningRepresentation.py
    (the 3D style-threading precedent this ports)
"""

from __future__ import annotations

import pytest

BEZIER_NODE_CLASS = "vtkMRMLBezierSurfaceNode"
RESECTOGRAM_DISPLAY_NODE_CLASS = "vtkMRMLResectogramDisplayNode"
SURFACE_DISPLAY_NODE_CLASS = "vtkMRMLParametricSurfaceDisplayNode"


class _FakeResection2DMapper:
    """GL-free stand-in recording the band-STYLE setter calls.

    ``None`` recorders distinguish "never touched" from an explicit push --
    the defaults invariant below relies on that: with no surface display
    node threaded, NO style setter may fire, so the mapper's compiled-in
    defaults stand and the pre-slice appearance is unchanged.
    """

    def __init__(self):
        self.resection_margin_color = None
        self.uncertainty_margin_color = None
        self.interpolated_margins = None
        self.resection_margin = None
        self.uncertainty_margin = None
        self.distance_map_texture = "sentinel"

    def SetResectionMarginColor(self, r, g, b):  # noqa: N802 - VTK verb
        self.resection_margin_color = (float(r), float(g), float(b))

    def SetUncertaintyMarginColor(self, r, g, b):  # noqa: N802 - VTK verb
        self.uncertainty_margin_color = (float(r), float(g), float(b))

    def SetInterpolatedMargins(self, flag):  # noqa: N802 - VTK verb
        self.interpolated_margins = bool(flag)

    def SetResectionMargin(self, value):  # noqa: N802 - VTK verb
        self.resection_margin = float(value)

    def SetUncertaintyMargin(self, value):  # noqa: N802 - VTK verb
        self.uncertainty_margin = float(value)

    def SetDistanceMapTextureObject(self, texture):  # noqa: N802 - VTK verb
        self.distance_map_texture = texture

    def GetDistanceMapTextureObject(self):  # noqa: N802 - VTK verb
        return None if self.distance_map_texture == "sentinel" else self.distance_map_texture


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _make_representation_or_skip():
    try:
        from LiverResectionsLib.Representations.FlattenedSurfaceRepresentation import (
            FlattenedSurfaceRepresentation,
        )
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            "FlattenedSurfaceRepresentation not importable "
            f"({exc!r}) -- not reachable in this environment."
        )
    return FlattenedSurfaceRepresentation()


def _require_band_style_seam_or_skip(rep):
    """Skip unless the band-style seam (resectogram-margins slice 1) landed.

    RED == the Representation has no ``SetSurfaceDisplayNode`` -- the seam
    that threads the shared parametric-surface display node's margin
    colours + InterpolatedMargins onto the 2D mapper.
    """
    if not hasattr(rep, "SetSurfaceDisplayNode"):
        pytest.skip(
            "FlattenedSurfaceRepresentation has no SetSurfaceDisplayNode -- "
            "the resectogram-margins band-style seam has not landed."
        )


def _inject_fake_mapper(rep):
    fake = _FakeResection2DMapper()
    rep._resection_mapper_2d = fake
    return fake


def _add_or_skip(slicer, node_class):
    node = slicer.mrmlScene.AddNewNodeByClass(node_class)
    if node is None:
        pytest.skip(f"{node_class} not registered in this build.")
    return node


def test_band_style_threads_from_surface_display_node():
    """Non-default colours + the interpolated flag reach the 2D mapper.

    Deliberately NON-default values (green / blue, interpolated on) so the
    assertion cannot pass by the mapper's compiled-in red / yellow defaults.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_band_style_seam_or_skip(rep)

    fake = _inject_fake_mapper(rep)

    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    surface_display = _add_or_skip(slicer, SURFACE_DISPLAY_NODE_CLASS)
    if not hasattr(surface_display, "SetResectionMarginColor"):
        pytest.skip(f"{SURFACE_DISPLAY_NODE_CLASS} has no margin-colour fields.")

    surface_display.SetResectionMarginColor(0.0, 1.0, 0.0)
    surface_display.SetUncertaintyMarginColor(0.0, 0.0, 1.0)
    surface_display.SetInterpolatedMargins(True)

    rep.SetSurfaceDisplayNode(surface_display)
    rep.update(display, data)

    assert fake.resection_margin_color is not None, (
        "the shared display node's ResectionMarginColor must reach the 2D "
        "mapper's SetResectionMarginColor -- no colour was threaded."
    )
    assert all(
        abs(a - b) < 1e-5
        for a, b in zip(fake.resection_margin_color, (0.0, 1.0, 0.0))
    ), f"expected (0,1,0); got {fake.resection_margin_color}."
    assert fake.uncertainty_margin_color is not None and all(
        abs(a - b) < 1e-5
        for a, b in zip(fake.uncertainty_margin_color, (0.0, 0.0, 1.0))
    ), f"expected (0,0,1); got {fake.uncertainty_margin_color}."
    assert fake.interpolated_margins is True, (
        "the shared display node's InterpolatedMargins must reach the 2D "
        f"mapper; got {fake.interpolated_margins!r}."
    )


def test_band_style_untouched_without_surface_display_node():
    """No surface display node -> NO style setter fires.

    The mapper's compiled-in defaults must stand (red / yellow, hard band),
    keeping the pre-slice appearance byte-identical for carriers that have no
    parametric-surface display node (resectogram-only fixtures).
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_band_style_seam_or_skip(rep)

    fake = _inject_fake_mapper(rep)

    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)

    rep.SetSurfaceDisplayNode(None)
    rep.update(display, data)

    assert fake.resection_margin_color is None, (
        "with no surface display node the Representation must NOT touch "
        "SetResectionMarginColor (compiled-in defaults stand); got "
        f"{fake.resection_margin_color!r}."
    )
    assert fake.uncertainty_margin_color is None
    assert fake.interpolated_margins is None


def test_band_style_is_orthogonal_to_the_plan_wrapper():
    """Style threads even with NO plan wrapper wired.

    Colours / interpolation are display state, margins are plan state
    (ADR-0031); a carrier whose plan is not yet resolved must still show the
    user-chosen band style the moment the shader has a band to draw.
    """
    slicer = _slicer_or_skip()
    rep = _make_representation_or_skip()
    _require_band_style_seam_or_skip(rep)

    fake = _inject_fake_mapper(rep)

    data = _add_or_skip(slicer, BEZIER_NODE_CLASS)
    display = _add_or_skip(slicer, RESECTOGRAM_DISPLAY_NODE_CLASS)
    surface_display = _add_or_skip(slicer, SURFACE_DISPLAY_NODE_CLASS)
    if not hasattr(surface_display, "SetResectionMarginColor"):
        pytest.skip(f"{SURFACE_DISPLAY_NODE_CLASS} has no margin-colour fields.")

    surface_display.SetResectionMarginColor(1.0, 0.0, 1.0)

    rep.SetResectionPlanNode(None)
    rep.SetSurfaceDisplayNode(surface_display)
    rep.update(display, data)

    assert fake.resection_margin_color is not None and all(
        abs(a - b) < 1e-5
        for a, b in zip(fake.resection_margin_color, (1.0, 0.0, 1.0))
    ), (
        "band style must thread independently of the plan wrapper; got "
        f"{fake.resection_margin_color!r}."
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
