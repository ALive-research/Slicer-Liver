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
node``): the WIDGET owns the QTimer and publishes the highlighted seed's
STABLE ID onto the shared display node's TRANSIENT ``HighlightSeedID``
member (``vtkMRMLVolumetrySeedsDisplayNode``, the ``TransientPoint``
precedent -- NOT a node attribute: ``SetAttribute`` values serialize into
the scene XML, so an attribute-borne highlight froze into orphan stripes on
scene reload).  The LayerDM-created slice pipeline reads the member back on
the display node's ``ModifiedEvent`` and renders.  The stripe PHASE never
touches MRML at all: the widget's timer fires ``STRIPE_TICK_EVENT`` (a
custom VTK event -- ``InvokeEvent`` neither serializes nor implies
Modified), and each pipeline advances its OWN local phase (the
SegmentEditorThresholdEffect precedent: preview animation with zero MRML
writes per tick).

This module holds the PURE pieces both sides share (bare-testable, numpy
only -- ADR-0027):

* ``resample_mask_to_plane`` -- the carved 3D mask cut to the slice plane
  (an affine XY->IJK sampling; computed once per (seed, slice), NOT per tick).
* ``stripe_segments`` -- the diagonal stripe line segments clipped to the
  2D mask at a given phase (the only per-tick work: the phase shifts the
  stripe family, the mask is reused).
* the ``HighlightSeedID`` member helpers + the stripe-tick event + the
  legacy-attribute sanitation.

References
----------
* ``VisibilityCarve`` -- the effective-region carve the mask encodes.
* ``feedback_layerdm_state_on_display_node`` -- widget state rides the
  display node, not a pipeline instance.
* ``vtkMRMLVolumetrySeedsDisplayNode`` -- the transient (never-serialized)
  ``HighlightSeedID`` / ``TransientPoint`` members.
"""

from __future__ import annotations

from typing import Any

#: Stripe spacing (px) along the diagonal normal.  One full phase cycle
#: translates the family by one period, so the march loops seamlessly.
STRIPE_PERIOD_PX = 12

#: The widget timer interval (ms): ~25 ticks/s at 1 px per tick reads as a
#: steady, calm march (~2 periods per second).
STRIPE_TICK_MS = 40

#: The stripe-tick event id the widget's timer fires on the shared display
#: node (``InvokeEvent`` -- no serialization, no Modified) and the slice
#: pipelines observe to advance their LOCAL phase.  Offset from
#: ``vtkCommand::UserEvent`` (1000); the fallback keeps this module
#: importable without vtk (the bare unit layer, ADR-0027).
try:  # pragma: no cover - exercised once per import environment
    from vtkmodules.vtkCommonCore import vtkCommand as _vtkCommand

    _USER_EVENT = int(_vtkCommand.UserEvent)
except ImportError:  # bare fallback: vtkCommand::UserEvent is the stable 1000
    _USER_EVENT = 1000
STRIPE_TICK_EVENT = _USER_EVENT + 61

#: The hover-PREVIEW marker on the shared ``HighlightSeedID`` member: while
#: the surgeon hovers an UNPINNED seed's Pin button, the widget publishes
#: ``preview:<seedID>`` instead of the bare ID.  The slice pipelines parse
#: the marker and render the preview STATIC (phase frozen -- the widget
#: also stops ticking) and DIMMED, so a glance never reads as the pin.
#: One transient member carries both states (a second member was overkill);
#: hover-out restores the pinned ID (or clears).
PREVIEW_PREFIX = "preview:"

#: The preview stripes' dimmed opacity (the pinned stripes render opaque).
PREVIEW_STRIPE_OPACITY = 0.4

#: LEGACY display-node ATTRIBUTES from the retired attribute-borne highlight
#: channel.  Node attributes serialize into the scene XML, so an old scene can
#: carry a frozen highlight/phase; ``clear_legacy_highlight_attributes``
#: scrubs them on module enter / scene load.  Kept ONLY for that sanitation.
_LEGACY_HIGHLIGHT_SEED_ATTRIBUTE = "LiverVolumetry.highlightSeed"
_LEGACY_STRIPE_PHASE_ATTRIBUTE = "LiverVolumetry.stripePhase"


# --------------------------------------------------------------------------- #
# Highlight state on the shared display node (transient member, never XML)
# --------------------------------------------------------------------------- #


def set_highlight_seed_id(displayNode: Any, seedID: str) -> None:
    """Publish the highlighted seed's STABLE ID (empty / ``None`` clears).

    Writes the display node's transient ``HighlightSeedID`` member (fires
    ModifiedEvent, excluded from scene serialization).
    """
    setter = getattr(displayNode, "SetHighlightSeedID", None)
    if setter is None:
        return
    setter(str(seedID) if seedID else "")


def get_highlight_seed_id(displayNode: Any) -> str:
    """The raw highlight member value (empty string when none).

    May carry the ``preview:`` marker; renderers go through
    ``parse_highlight_value`` to split the seed ID from the preview flag.
    """
    getter = getattr(displayNode, "GetHighlightSeedID", None)
    if getter is None:
        return ""
    return getter() or ""


def set_preview_seed_id(displayNode: Any, seedID: str) -> None:
    """Publish a hover-PREVIEW highlight for ``seedID`` (static + dimmed).

    Writes ``preview:<seedID>`` onto the same transient member the pin
    uses; an empty / ``None`` seed clears the member entirely.
    """
    set_highlight_seed_id(displayNode, f"{PREVIEW_PREFIX}{seedID}" if seedID else "")


def parse_highlight_value(value: str) -> tuple:
    """Split a raw highlight member value into ``(seedID, is_preview)``."""
    value = value or ""
    if value.startswith(PREVIEW_PREFIX):
        return value[len(PREVIEW_PREFIX):], True
    return value, False


def invoke_stripe_tick(displayNode: Any) -> None:
    """Fire the stripe-tick event on the shared display node.

    ``InvokeEvent`` does not serialize and does not imply Modified -- the
    tick wakes ONLY the pipelines observing ``STRIPE_TICK_EVENT``, never the
    whole ModifiedEvent audience (the 25 Hz Modified-storm fix).
    """
    invoke = getattr(displayNode, "InvokeEvent", None)
    if invoke is None:
        return
    invoke(STRIPE_TICK_EVENT)


def clear_legacy_highlight_attributes(displayNode: Any) -> bool:
    """Scrub the retired attribute-borne highlight channel off ``displayNode``.

    Old scenes serialized ``LiverVolumetry.highlightSeed`` /
    ``LiverVolumetry.stripePhase`` node ATTRIBUTES; on reload they render as
    frozen orphan stripes no widget owns.  Returns True iff anything was
    removed.
    """
    if displayNode is None:
        return False
    cleared = False
    for name in (_LEGACY_HIGHLIGHT_SEED_ATTRIBUTE, _LEGACY_STRIPE_PHASE_ATTRIBUTE):
        if displayNode.GetAttribute(name) is not None:
            displayNode.RemoveAttribute(name)
            cleared = True
    return cleared


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
