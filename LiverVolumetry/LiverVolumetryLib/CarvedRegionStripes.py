# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the carved-region marching-stripes highlight (pure core).

While a volumetry seed is HIGHLIGHTED -- right after its placement, or while
its row's dedicated Highlight toggle is on -- its EFFECTIVE (carved) region is
overlaid in the 2D slices with slowly MARCHING diagonal stripes -- a calm,
continuous "bars moving" cue (never an opacity blink; this replaces the
placement fade).  The stripes stay while the highlight holds and clear on
untoggle / placement of another seed.  Row SELECTION is not a driver.

Split per the LayerDM state discipline (``feedback_layerdm_state_on_display_
node``): the WIDGET owns the QTimer and publishes ``highlightSeed`` +
``stripePhase`` onto the shared display node; the LayerDM-created slice
pipeline reads them back on the display node's ``ModifiedEvent`` and renders.
This module holds the PURE pieces both sides share (bare-testable, numpy
only -- ADR-0027):

* ``resample_mask_to_plane`` -- the carved 3D mask cut to the slice plane
  (an affine XY->IJK sampling; computed once per (seed, slice), NOT per tick).
* ``stripe_segments`` -- the diagonal stripe line segments clipped to the
  2D mask at a given phase (the only per-tick work: the phase shifts the
  stripe family, the mask is reused).
* the ``highlightSeed`` / ``stripePhase`` display-node attribute helpers.

References
----------
* ``VisibilityCarve`` -- the effective-region carve the mask encodes.
* ``feedback_layerdm_state_on_display_node`` -- widget state rides the
  display node, not a pipeline instance.
"""

from __future__ import annotations

from typing import Any

#: The shared display-node attribute carrying the highlighted seed's GLOBAL
#: placement index ("-1" / absent == no highlight).  Written by the seeds
#: table at placement / on the Highlight toggle; read by the slice pipelines.
HIGHLIGHT_SEED_ATTRIBUTE = "LiverVolumetry.highlightSeed"

#: The shared display-node attribute carrying the stripe phase (px along the
#: stripe normal).  The widget's timer advances it; each write fires the
#: display node's ModifiedEvent, which is the pipelines' render tick.
STRIPE_PHASE_ATTRIBUTE = "LiverVolumetry.stripePhase"

#: Stripe spacing (px) along the diagonal normal.  One full phase cycle
#: translates the family by one period, so the march loops seamlessly.
STRIPE_PERIOD_PX = 12

#: The widget timer interval (ms): ~25 ticks/s at 1 px per tick reads as a
#: steady, calm march (~2 periods per second).
STRIPE_TICK_MS = 40


# --------------------------------------------------------------------------- #
# Highlight state on the shared display node
# --------------------------------------------------------------------------- #


def set_highlight_seed(displayNode: Any, seedIndex: int) -> None:
    """Publish the highlighted seed's global index (-1 clears)."""
    if displayNode is None:
        return
    displayNode.SetAttribute(HIGHLIGHT_SEED_ATTRIBUTE, str(int(seedIndex)))


def get_highlight_seed(displayNode: Any) -> int:
    """The highlighted seed's global index (-1 when none)."""
    if displayNode is None:
        return -1
    value = displayNode.GetAttribute(HIGHLIGHT_SEED_ATTRIBUTE)
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def set_stripe_phase(displayNode: Any, phase: int) -> None:
    """Publish the stripe phase (px; the widget timer's tick)."""
    if displayNode is None:
        return
    displayNode.SetAttribute(STRIPE_PHASE_ATTRIBUTE, str(int(phase)))


def get_stripe_phase(displayNode: Any) -> int:
    """The stripe phase (0 when unset)."""
    if displayNode is None:
        return 0
    value = displayNode.GetAttribute(STRIPE_PHASE_ATTRIBUTE)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------- #
# Mask cut + stripe geometry (pure numpy)
# --------------------------------------------------------------------------- #


def resample_mask_to_plane(mask: Any, xy_to_ijk: Any, width: int, height: int) -> Any:
    """Cut a 3D boolean mask to a slice plane: a (height, width) 2D mask.

    ``mask`` is indexed ``[k, j, i]`` (the ``arrayFromSegmentBinaryLabelmap``
    convention); ``xy_to_ijk`` is the 4x4 affine taking homogeneous slice-XY
    ``(x, y, 0, 1)`` to IJK ``(i, j, k, 1)`` (nearest-neighbour sampling).
    Out-of-bounds pixels are False.  Computed ONCE per (seed, slice pose) --
    the per-tick stripe work reuses the result.
    """
    import numpy as np

    mask = np.asarray(mask, dtype=bool)
    m = np.asarray(xy_to_ijk, dtype=float)
    xs, ys = np.meshgrid(np.arange(width), np.arange(height))
    i = np.rint(m[0, 0] * xs + m[0, 1] * ys + m[0, 3]).astype(int)
    j = np.rint(m[1, 0] * xs + m[1, 1] * ys + m[1, 3]).astype(int)
    k = np.rint(m[2, 0] * xs + m[2, 1] * ys + m[2, 3]).astype(int)
    kd, jd, id_ = mask.shape
    valid = (0 <= i) & (i < id_) & (0 <= j) & (j < jd) & (0 <= k) & (k < kd)
    out = np.zeros((height, width), dtype=bool)
    out[valid] = mask[k[valid], j[valid], i[valid]]
    return out


def stripe_segments(mask2d: Any, period: int = STRIPE_PERIOD_PX, phase: int = 0) -> list:
    """Diagonal stripe line segments clipped to a 2D mask.

    Stripes are the anti-diagonals ``x + y = c`` with ``c ≡ phase (mod
    period)``: advancing ``phase`` translates the family along the diagonal
    normal -- the marching cue.  Each stripe is clipped to the mask's True
    runs, yielding ``((x0, y0), (x1, y1))`` endpoint pairs in pixel
    coordinates (a single-pixel run degenerates to a zero-length segment;
    the renderer pads it).  Only this runs per tick; the mask is reused.
    """
    import numpy as np

    mask2d = np.asarray(mask2d, dtype=bool)
    height, width = mask2d.shape
    segments: list = []
    if period <= 0:
        return segments
    first = int(phase) % period
    for c in range(first, width + height - 1, period):
        x_lo = max(0, c - height + 1)
        x_hi = min(width - 1, c)
        if x_lo > x_hi:
            continue
        xs = np.arange(x_lo, x_hi + 1)
        ys = c - xs
        hits = np.flatnonzero(mask2d[ys, xs])
        if hits.size == 0:
            continue
        # Split the hit indices into consecutive runs (breaks where the mask
        # is False along the stripe).
        breaks = np.flatnonzero(np.diff(hits) > 1)
        starts = np.concatenate(([0], breaks + 1))
        ends = np.concatenate((breaks, [hits.size - 1]))
        for s, e in zip(starts, ends):
            a, b = hits[s], hits[e]
            segments.append(
                ((float(xs[a]), float(ys[a])), (float(xs[b]), float(ys[b])))
            )
    return segments
