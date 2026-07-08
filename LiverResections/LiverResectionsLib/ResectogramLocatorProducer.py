# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Locator producer — resectogram pixel -> (u, v) -> world point (ADR-0025).

The resectogram is the flattened 1:1 image of the Bezier ``(u, v)`` parameter
domain (ADR-0025 §Context), so a resectogram pixel maps to an **exact** Bezier
surface world point by direct evaluation — there is **no** ``vtkCellPicker``
(ADR-0025 Alternative A rejected).  This producer composes the pure mapping:

    pixel -> ``vtkLiverResectogramPixelMapping.PixelToUV`` -> (u, v)
          -> ``vtkMRMLBezierSurfaceNode.EvaluateSurface(u, v)`` (1-point polydata)
          -> world point -> ``vtkMRMLLocatorNode.SetPickedPositionWorld``

The already-merged consumer (the T2 ``LiverBezierSurfacePipeline`` +
``BezierPlanningRepresentation``) then renders the marker off the locator node.

This class is the GL-free producer CORE.  It is invoked with the click pixel by
the ``ResectionPlanningWidget``'s Qt event filter on the embedded resectogram
view (the interaction layer, wired separately); the producer itself needs no
render context — ``PixelToUV`` and ``EvaluateSurface`` are pure CPU maths.  Per
ADR-0004 the producer is Python; per ADR-0013 §5 it is not a displayable
manager — it writes the shared ``vtkMRMLLocatorNode`` the consumer observes.

References
----------
* `ADR-0025`_ §Producer — exact 1:1 ``(u, v)`` mapping, no picker.
* `ADR-0004`_ — the producer is Python.

.. _ADR-0025: ../../Docs/adr/0025-locator-architecture.md
.. _ADR-0004: ../../Docs/adr/0004-python-cpp-boundary.md
"""

from __future__ import annotations

from typing import Any


class ResectogramLocatorProducer:
    """Maps a resectogram pixel to a Bezier world point and writes the locator.

    Constructed with the surface carrier (``vtkMRMLBezierSurfaceNode``) whose
    ``(u, v)`` domain the resectogram images, and the target
    ``vtkMRMLLocatorNode`` the picked point is written onto.
    """

    def __init__(self, surface_node: Any, locator_node: Any) -> None:
        self._surface_node = surface_node
        self._locator_node = locator_node

    def produce(
        self, pixel: Any, viewport_size: Any, mat_ratio: Any
    ) -> tuple[float, float, float] | None:
        """Map ``pixel`` to a world point and write it onto the locator node.

        ``pixel`` / ``mat_ratio`` are 2-sequences of float; ``viewport_size`` a
        2-sequence of int.  Returns the ``(x, y, z)`` world point (also written
        to the locator's ``PickedPositionWorld``), or ``None`` on a degenerate
        input (non-positive viewport, missing surface, or an empty evaluation)
        — a no-op that leaves the locator node untouched.
        """
        surface = self._surface_node
        if surface is None:
            return None
        # A non-positive viewport is degenerate (PixelToUV divides by it).
        if int(viewport_size[0]) <= 0 or int(viewport_size[1]) <= 0:
            return None

        # vtkLiverResectogramPixelMapping is a wrapped-C++ Algorithm class
        # (ADR-0015 §1), reachable only via the module's Python wrapping -- lazily
        # imported so this module stays importable where that wrapping is off the
        # path (the bare-VTK unit layer), the produce() call then a safe no-op.
        try:
            import vtkSlicerLiverResectionsModuleAlgorithmPython as algorithm
        except ImportError:
            return None
        mapping = getattr(algorithm, "vtkLiverResectogramPixelMapping", None)
        if mapping is None:
            return None

        uv_out = [0.0, 0.0]
        mapping.PixelToUV(
            [float(pixel[0]), float(pixel[1])],
            [int(viewport_size[0]), int(viewport_size[1])],
            [float(mat_ratio[0]), float(mat_ratio[1])],
            uv_out,
        )

        return self.produce_from_uv(uv_out[0], uv_out[1])

    def produce_from_uv(self, u: float, v: float) -> tuple[float, float, float] | None:
        """Evaluate ``S(u, v)`` and write the world point onto the locator.

        The UV seam: callers that already know the exact parametric
        coordinates (the camera-based display->world inversion on the
        standalone strip view) skip the window-fraction ``PixelToUV``
        approximation entirely.  Same return/no-op contract as ``produce``.
        """
        surface = self._surface_node
        if surface is None:
            return None
        # The carrier's EvaluateSurface walks ROWS with its FIRST parameter,
        # i.e. it consumes (v, u) in the strip's convention (u = horizontal /
        # column fraction).  Passing (u, v) straight through transposed the
        # pick: a click at the strip's bottom-right corner produced the
        # surface's top-left point (the marker-offset bug found live).
        polydata = surface.EvaluateSurface(float(v), float(u))
        if polydata is None or polydata.GetNumberOfPoints() < 1:
            return None
        world = polydata.GetPoint(0)
        point = (float(world[0]), float(world[1]), float(world[2]))

        if self._locator_node is not None:
            self._locator_node.SetPickedPositionWorld(point[0], point[1], point[2])
        return point
