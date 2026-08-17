# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""territory-usability -- the per-VOLUME LiverVolumetry seeds table.

A carrier-backed table over the grouped ``vtkMRMLVolumetrySeedsNode`` seed
carrier, the volumetry sibling of the VascularTerritories
``TerritoriesTableWidget``.  Where the territory table nests seed points under
their surgeon-named TERRITORY, this table nests region-growing seeds under their
surgeon-named VOLUME: the surgeon adds a named volume, arms placement into the
ACTIVE volume (a per-volume Place toggle publishing the active volume onto the
shared display node), and placed seeds nest under that volume.

It is a Python-composed ``qt.QWidget`` (ADR-0004) that OWNS a two-level
``qt.QTreeWidget`` (VOLUMES top-level, seeds child rows), mirroring the
territory tree.  The prior FLAT per-seed table (ADR-0038) is subsumed: seed rows
keep every per-seed control, and the per-SEED getters stay keyed by the seed's
GLOBAL placement INDEX (``labelEdit`` / ``colourButton`` / ``targetCombo`` /
``deleteAction`` / ``setSeedColor`` / ``setSeedLabel`` / ``deleteSeed`` /
``retargetSeed``), so the existing seed→segment binding + retarget contract
is preserved on top of the grouping.

Each VOLUME (top-level) row carries a horizontal strip, addressed by NAME:

* a per-volume Place toggle (``qt.QToolButton``, checkable) that arms placement
  into THIS volume exclusively (publishes the active volume + armed flag onto
  the shared display node via the base ``PointPlacementState``);
* a COLOUR swatch (``ctk.ctkColorPickerButton``) writing ``SetVolumeColor``;
* an editable LABEL (``qt.QLineEdit``) writing ``SetVolumeLabel``;
* an overflow "..." menu holding "Remove volume..." (confirming when seeds
  would go with it) -- the destructive action sits out of the misclick path.

Each SEED (child) row shows at most FOUR controls (the row diet): the PIN
toggle, a COLOUR swatch, an editable LABEL (the generated segment name,
ADR-0038 §Conformance), and the cue/chip text -- plus an overflow "..."
menu holding "Retarget" (the seed→segment binding + retarget submenu,
``territory-usability`` §"Seed→label capture"), "Restore placement view",
and "Delete seed" (confirming when the seed carries a snapshot).  Each
composite row widget covers its whole tree item, so a press anywhere on the row
lands on a CHILD control (the stretch line edit under most of it), which
consumes the press -- the tree item itself would never be selected by a real
click.  A row-select event filter on every row child selects the row FIRST and
does not consume the press, so a click on a row both selects it and still
drives the clicked control.  Selection is PLAIN row UX with NO side effects:
the rows are dense with actionable controls, so tying visibility or the
stripes to selection made every stray click a state change.

The carved-region stripes have exactly TWO drivers instead:

* PLACEMENT -- a one-seed carrier append publishes the new seed's highlight
  directly (the surgeon always sees the just-measured region striped at once,
  no row interaction).  Placement restores no visibility context: the seed's
  snapshot equals the live visibility at that moment.
* the per-seed PIN toggle (exclusive, checkable ``qt.QToolButton``) --
  checking it raises the seed's stripes; unchecking clears them.  The pin is
  STRIPES ONLY: it NEVER touches the segment visibility.

RESTORING a seed's placement-time visibility snapshot is its own explicit
affordance ("Restore placement view", reachable from the seed row's overflow
menu and the divergence chip), fully decoupled from the pin.  The restore is
symmetric and depth ONE: entering a restored context first captures the
CURRENT visibility as "my view" (one widget-side slot); "Return to my view"
puts it back, restoring a DIFFERENT seed reuses the same capture (a switch),
and a MANUAL eye-list change simply ENDS the restored context -- the user
took over, and the widget never re-asserts visibility against them.  While a
restored context is active a banner line on the panel names it in text
(ADR-0010) with the inline return button.  A snapshot whose intersection
with the segmentation's CURRENT segment IDs is empty REFUSES the restore
("no longer exists") -- the view is never blanked.

Either driver highlights the seed's EFFECTIVE (carved) region in the 2D slices
with slowly MARCHING diagonal stripes: this widget owns the march ``qt.QTimer``
and publishes the highlighted seed's STABLE ID onto the shared display node's
transient ``HighlightSeedID`` member (``CarvedRegionStripes``; never a node
attribute -- attributes serialize into the scene XML).  Each timer tick fires
``STRIPE_TICK_EVENT`` on the display node (``InvokeEvent`` -- no MRML write,
no Modified storm); the LayerDM slice pipelines observe it and advance their
own local phase.  Seeds are addressed by their carrier-minted stable ID
(``GetNthSeedID``), so a pinned highlight survives deleting a DIFFERENT seed
and retires only when its own seed goes.  The highlight is persistent while
toggled (no opacity flashing) and is paired with the row's text naming the
owner + context (ADR-0010, never colour/animation alone).

CARRIER IS THE MODEL.  The table reads/writes the carrier and OBSERVES its
``vtkCommand::ModifiedEvent`` to rebuild.  ``cleanup()`` detaches the observer +
stops the stripe timer so a parentless widget does not survive to app shutdown
holding a MRML observer (``feedback_launched_widget_teardown_crash``).

The arm state / active volume ride the shared ``vtkMRMLVolumetrySeedsDisplayNode``
(not a Python pipeline instance LayerDM does not drive,
``feedback_layerdm_state_on_display_node``) via the base ``PointPlacementState``
``LiverVolumetry.*`` channel -- the SAME channel the slice pipeline reads at
placement time (``_assign_active_volume``).

See also:
  * VascularTerritories/VascularTerritoriesLib/TerritoriesTableWidget.py -- the
    two-level tree idiom this mirrors.
  * Docs/adr/0038 -- the seeds-off-markups migration + §Conformance.
  * Docs/adr/0014-*.md §"Fourth layer" -- a display edit must not touch geometry.
  * Docs/adr/0010-accessibility-and-i18n.md -- glyph/text pairing.
  * Docs/adr/0004-*.md -- panels are Python.
"""

from __future__ import annotations

from typing import Any

import ctk
import qt
import vtk

try:  # pragma: no cover - exercised once per import path
    from .SeedTargetResolution import (
        gather_touched_candidates,
        resolve_touched_candidates,
    )
    from .VisibilityCarve import (
        apply_visibility_context,
        carved_mask_for_seed,
        read_seed_context,
        segment_mask_reader,
        visible_context,
    )
    from .CarvedRegionStripes import (
        STRIPE_TICK_MS,
        invoke_stripe_tick,
        set_highlight_seed_id,
        set_preview_seed_id,
    )
except ImportError:  # top-level import path (the unit layer's sys.path setup)
    from SeedTargetResolution import (  # type: ignore[no-redef]
        gather_touched_candidates,
        resolve_touched_candidates,
    )
    from VisibilityCarve import (  # type: ignore[no-redef]
        apply_visibility_context,
        carved_mask_for_seed,
        read_seed_context,
        segment_mask_reader,
        visible_context,
    )
    from CarvedRegionStripes import (  # type: ignore[no-redef]
        STRIPE_TICK_MS,
        invoke_stripe_tick,
        set_highlight_seed_id,
        set_preview_seed_id,
    )

# The arm / active-volume state rides the shared display node via the base's
# PointPlacementState (the LiverVolumetry.* channel the slice pipeline reads at
# placement time).  Import the same dual-path idiom the placement module uses.
try:  # pragma: no cover - exercised once per import path
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
except ImportError:  # bare / top-level path: add the sibling Lib dir to sys.path
    import pathlib
    import sys as _sys

    _shared_lib = pathlib.Path(__file__).resolve().parents[2] / "SlicerLiverInteractionLib"
    if str(_shared_lib) not in _sys.path:
        _sys.path.insert(0, str(_shared_lib))
    from PointPlacementState import PointPlacementState  # type: ignore[no-redef]

#: The base namespace for the volumetry arm/active-volume state on the shared
#: display node (matches the placement pipeline's ``VOLUMETRY_NAMESPACE``).
VOLUMETRY_NAMESPACE = "LiverVolumetry"

#: The seed / volume default display colour (opaque white), mirroring the
#: carrier's own out-of-range default.
_DEFAULT_SEED_COLOR = (1.0, 1.0, 1.0)

#: A small distinct palette so minted volumes read apart in the swatch (RGB in
#: 0..1).  Cycled by mint order, mirroring the territory palette.
_VOLUME_PALETTE = (
    (0.90, 0.30, 0.24),  # red
    (0.20, 0.60, 0.86),  # blue
    (0.18, 0.80, 0.44),  # green
    (0.95, 0.77, 0.06),  # amber
    (0.61, 0.35, 0.71),  # purple
    (0.90, 0.49, 0.13),  # orange
)

#: The single column the composite row widget lives on (mirrors the territory
#: tree slice-4 amendment): a header-less tree, one composite QWidget per item.
_COMPOSITE_COLUMN = 0
_COLUMN_COUNT = 1

#: The empty-carve cue (ADR-0010 legible text -- silent nothing is not a
#: state): shown on the HIGHLIGHTED seed row (toggle or placement driven)
#: when its effective (carved) region is EMPTY -- the owner segment is fully
#: covered by the snapshot segments above it -- so "no stripes" is named,
#: never mute.  An UNKNOWN carve (an unbound seed / unreadable masks) shows
#: no cue: unknown is not empty.
EMPTY_CARVE_MESSAGE = (
    "Region fully covered by segments above -- hide covering segments or "
    "retarget the seed."
)

#: The divergence chip on the PINNED seed's row (plain text, never a
#: tooltip): shown when the LIVE visibility no longer matches the seed's
#: placement snapshot, so the striped region on screen is being read
#: against a different composition than the one that defined it.  The chip
#: doubles as the entry point: clicking it restores the placement view.
DIVERGENCE_CHIP_TEXT = "View differs from placement snapshot"

#: The stale-snapshot refusal (ADR-0010 legible text): a restore whose
#: snapshot shares NO segment with the segmentation's current segment IDs is
#: REFUSED -- applying it would blank the view.  Shown in the banner slot.
STALE_SNAPSHOT_MESSAGE = (
    "This seed's placement view no longer exists in the segmentation"
)

#: The restored-context banner lead-in (the inline return button follows).
RESTORE_BANNER_PREFIX = "Showing placement view of"

#: Dynamic Qt properties tagging every widget of a composite row with its row
#: key, so the row-select event filter can resolve WHICH tree item a pressed
#: child control belongs to (a press on a child never reaches the tree
#: viewport, so the tree cannot select the row itself).  Seed rows are keyed
#: by the seed's STABLE ID (``GetNthSeedID``), never its shifting index.
_ROW_SEED_PROPERTY = "volumetryRowSeed"
_ROW_VOLUME_PROPERTY = "volumetryRowVolume"

#: Dynamic Qt property tagging each row's PIN button with its seed's stable
#: ID, so the shared event filter can drive the hover-PREVIEW (enter shows
#: the seed's stripes static + dimmed; leave restores the pinned seed's).
_ROW_PIN_PROPERTY = "volumetryPinSeed"

#: Stock icon resources for the icon-only row toggles.  Place rides the
#: markups fiducial place-mode icon every Slicer user already reads as
#: "click to place"; Pin rides the push-pin out/in pair.  Place keeps ONE
#: icon in both states: the ``PlaceAdd`` variant means "add a point" in
#: Slicer, so borrowing it for "placement is armed" misreads -- the toggle's
#: pushed state already carries that, so the glyph must not change meaning
#: under it.  The Pin pair's out/in glyphs DO describe its two states, so
#: they sit on one ``qt.QIcon``'s Off/On states.  Both are resolved at
#: runtime with a text-glyph fallback (``_apply_toggle_icon``) for a harness
#: without the application's compiled-in resources.
_PLACE_ICON_OFF = ":/Icons/MarkupsFiducialMouseModePlace.png"
_PLACE_ICON_ON = _PLACE_ICON_OFF
_PIN_ICON_OFF = ":/Icons/PushPinOut.png"
_PIN_ICON_ON = ":/Icons/PushPinIn.png"


def _apply_toggle_icon(button: Any, offPath: str, onPath: str, fallbackText: str) -> None:
    """Make ``button`` icon-only with an unchecked/checked stock-icon pair.

    The pair rides one ``qt.QIcon``'s Off/On states, so the checked state
    swaps the glyph with no toggle handler -- and survives a signal-blocked
    programmatic ``setChecked`` (the exclusivity re-sync).  Falls back to the
    short ``fallbackText`` when the stock resources are unavailable (a bare
    harness without the application's compiled-in icons), so the toggle never
    renders blank; identity stays on the tooltip + accessible name either way
    (ADR-0010 -- the icon never stands alone).
    """
    if qt.QIcon(offPath).isNull():
        button.setText(fallbackText)
        return
    icon = qt.QIcon()
    icon.addFile(offPath, qt.QSize(), qt.QIcon.Normal, qt.QIcon.Off)
    checkedPath = onPath if not qt.QIcon(onPath).isNull() else offPath
    icon.addFile(checkedPath, qt.QSize(), qt.QIcon.Normal, qt.QIcon.On)
    button.setText("")
    button.setIcon(icon)


class VolumetrySeedsTableWidget(qt.QWidget):
    """Per-volume carrier-backed tree over ``vtkMRMLVolumetrySeedsNode``.

    Constructed over the seed carrier + (optionally) the shared display node::

        VolumetrySeedsTableWidget(carrier=<vtkMRMLVolumetrySeedsNode>,
                                  displayNode=<vtkMRMLVolumetrySeedsDisplayNode>)

    Volumes are top-level rows; seeds nest under their volume.  Per-seed getters
    stay keyed by the seed's global placement index; volume-level getters take
    the volume id.
    """

    def __init__(self, carrier: Any = None, displayNode: Any = None, parent: Any = None) -> None:
        super().__init__(parent)

        self._carrier = carrier
        self._displayNode = displayNode
        self._carrier_observer_tag: int | None = None
        # Guards against the write-back edits re-triggering a rebuild mid-edit.
        self._rebuilding = False
        # The structure-source segmentation the retarget menu recomputes touched
        # candidates against; bound by the module widget via setStructureSource.
        self._structureSource: Any = None
        # Deterministic volume order: minted / seed-bearing / display volumes in
        # first-seen order (so an EMPTY minted volume keeps its top-level row).
        self._volume_order: list[str] = []
        # volumeId -> its top-level QTreeWidgetItem + named controls; rebuilt.
        self._volume_items: dict[str, Any] = {}
        self._volume_rows: dict[str, dict[str, Any]] = {}
        # STABLE seed ID -> the seed composite row's named controls; rebuilt.
        # Keyed by ID (never the placement index): a deletion reshuffles the
        # indices but must not re-key surviving rows.  The public per-seed
        # getters stay index-signed for back-compat and resolve index -> ID.
        self._seed_rows: dict[str, dict[str, Any]] = {}
        # STABLE seed ID -> the seed child QTreeWidgetItem (the row-select
        # event filter's target); rebuilt with the tree.
        self._seed_items: dict[str, Any] = {}
        # Seed count after the last observer-driven rebuild: a +1 step marks a
        # placement, which publishes the new seed's highlight DIRECTLY (no row
        # selection -- selection has no side effects).
        self._known_seed_count: int | None = None
        # Auto-mint counter for "Add volume".
        self._mint_counter = 0

        # The carved-region stripe highlight: THIS widget owns the march timer
        # and publishes the highlighted seed's STABLE ID onto the shared
        # display node's transient HighlightSeedID member (CarvedRegionStripes);
        # each tick fires STRIPE_TICK_EVENT (InvokeEvent -- zero MRML writes
        # per tick, the SegmentEditorThresholdEffect preview-timer precedent)
        # and the LayerDM slice pipelines advance their own local phase.
        # Driven by placement + the per-seed Highlight toggle only; persistent
        # while toggled -- no opacity flashing (the old fade pulse is retired).
        self._stripeTimer = qt.QTimer(self)
        self._stripeTimer.setInterval(STRIPE_TICK_MS)
        self._stripeTimer.connect("timeout()", self._onStripeTick)
        self._highlightedSeedID = ""
        # The hover-PREVIEW: while the cursor rests on an UNPINNED seed's Pin
        # button, that seed's stripes show STATIC (the widget stops ticking;
        # the pipeline freezes the phase) and DIMMED, riding the same
        # transient member under the ``preview:`` marker.  Hover-out
        # restores the pinned seed's stripes (or clears).
        self._previewSeedID = ""
        # Pin persistence hook: the module widget registers a callback
        # (``setPinChangedCallback``) and mirrors the pinned seed's STABLE ID
        # into its parameter node, so a scene save/reload resumes the pin on
        # module enter.  ``stopHighlight`` (module-exit hygiene) suppresses
        # the callback: exiting stops the stripes but must NOT erase the
        # persisted pin.
        self._pinChangedCallback: Any = None
        self._suppressPinCallback = False

        # The restored-context state ("Restore placement view", symmetric,
        # depth ONE): entering a restore captures the CURRENT visibility as
        # "my view" (one slot); returning / switching reuses it; a manual
        # eye-list change ends the context (user takeover -- the widget never
        # re-asserts visibility).  ``_applyingVisibility`` marks the widget's
        # OWN visibility writes so the takeover observer does not read them
        # as the user's; ``_restoredVisibleSet`` is the visible-ID set the
        # restore applied, so unrelated display edits (opacity, colour) are
        # not mistaken for a takeover.
        self._restoredSeedID = ""
        self._myViewContext: list[str] | None = None
        self._restoredVisibleSet: frozenset | None = None
        self._applyingVisibility = False
        self._observedSourceDisplay: Any = None
        self._sourceDisplayObserverTag: int | None = None

        layout = qt.QVBoxLayout(self)

        # The restored-context banner: a visible text line naming the
        # restored placement view (ADR-0010 -- never state without words)
        # with the inline "Return to my view" button.  Hidden while no
        # restored context is active; also carries the stale-snapshot
        # refusal message (then without the return button).
        self._restoreBanner = qt.QWidget()
        bannerLayout = qt.QHBoxLayout(self._restoreBanner)
        bannerLayout.setContentsMargins(2, 1, 2, 1)
        bannerLayout.setSpacing(4)
        self._restoreBannerLabel = qt.QLabel("")
        self._restoreBannerLabel.setWordWrap(True)
        bannerLayout.addWidget(self._restoreBannerLabel, 1)
        self._returnToMyViewButton = qt.QPushButton("Return to my view")
        self._returnToMyViewButton.setToolTip(
            "Put the segment visibility back to how it was before the restore"
        )
        self._returnToMyViewButton.connect(
            "clicked(bool)", lambda _checked: self.returnToMyView()
        )
        bannerLayout.addWidget(self._returnToMyViewButton)
        self._restoreBanner.setVisible(False)
        layout.addWidget(self._restoreBanner)

        # Single-column, header-less two-level tree (volumes -> seeds).
        self._tree = qt.QTreeWidget()
        self._tree.setColumnCount(_COLUMN_COUNT)
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self._tree.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        # Row selection is deliberately NOT connected to anything: selecting a
        # row must have NO side effects on visibility or the stripe highlight
        # (the rows are dense with actionable controls, so a selection-driven
        # highlight fired on every stray click).  The Highlight toggle and
        # placement are the only stripe drivers.
        layout.addWidget(self._tree)

        buttons = qt.QHBoxLayout()
        self._addVolumeButton = qt.QPushButton("Add volume")
        self._addVolumeButton.setToolTip("Add a named volume, then place seeds into it")
        buttons.addWidget(self._addVolumeButton)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._addVolumeButton.connect("clicked(bool)", lambda _checked: self.addVolume())

        # ESC cancels an armed placement (disarm + the Place toggle unchecks
        # on the repaint) -- scoped to this panel's widget tree so a global
        # Escape elsewhere is untouched.  ESC never clears the pin.
        self._escapeShortcut = qt.QShortcut(self)
        self._escapeShortcut.setKey(qt.QKeySequence("Esc"))
        self._escapeShortcut.setContext(qt.Qt.WidgetWithChildrenShortcut)
        self._escapeShortcut.connect("activated()", self.cancelArmedPlacement)

        # Detach-before-callback guard: when a host destroys the Qt tree
        # (the panel this table is composed into dies) while this Python
        # object still holds VTK observers, a later carrier / display edit
        # would drive ``_rebuild`` into destroyed Qt members.  The hook is
        # Qt-free: it drops ONLY the VTK observers + Python-side callbacks
        # (feedback_launched_widget_teardown_crash).
        self.connect("destroyed()", self._onQtDestroyed)

        self._attachCarrierObserver()
        self._rebuild()
        self._known_seed_count = self._seedCount()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def cleanup(self) -> None:
        """Drop the observers + stop the stripe highlight (teardown)."""
        self._clearHighlight()
        self._detachCarrierObserver()
        self._detachSourceDisplayObserver()

    def _onQtDestroyed(self) -> None:
        """The Qt tree died: drop the VTK observers, touching NO Qt member.

        Fired by this widget's own ``destroyed()`` signal (the stripe timer
        is a Qt child, so it died with the tree and cannot tick).  A late
        carrier ``ModifiedEvent`` after this can no longer reach a
        destroyed row widget.
        """
        self._detachCarrierObserver()
        self._detachSourceDisplayObserver()
        self._pinChangedCallback = None

    def setStructureSource(self, segmentationNode: Any) -> None:
        """Bind the structure-source segmentation the retarget menu scans.

        Also re-aims the eye-list observer (the user-takeover detector for a
        restored context) at the new source's display node, and ends any
        restored context minted against the OLD source.
        """
        if segmentationNode is not self._structureSource and self._restoredSeedID:
            self._endRestoredContext()
        self._structureSource = segmentationNode
        self._observeSourceDisplay()
        self._rebuild()

    def setCarrier(self, carrier: Any) -> None:
        """Rebind the table to ``carrier`` (drops the prior observer, rebuilds)."""
        if carrier is self._carrier:
            return
        self._detachCarrierObserver()
        self._carrier = carrier
        self._attachCarrierObserver()
        self._rebuild()
        self._known_seed_count = self._seedCount()

    def setDisplayNode(self, displayNode: Any) -> None:
        """Bind the shared display node the arm / active-volume state rides.

        The per-volume Place toggle publishes the active volume + armed flag onto
        THIS node via the base ``PointPlacementState``; the LayerDM-created slice
        pipeline reads them at placement time (``_assign_active_volume``).  The
        stripe highlight rides the same node, so a rebind clears it off the old
        one first.
        """
        if displayNode is not self._displayNode:
            self._clearHighlight()
        self._displayNode = displayNode
        self._rebuild()

    def _attachCarrierObserver(self) -> None:
        if self._carrier is None or not hasattr(self._carrier, "AddObserver"):
            return
        self._carrier_observer_tag = self._carrier.AddObserver(
            vtk.vtkCommand.ModifiedEvent, self._onCarrierModified
        )

    def _detachCarrierObserver(self) -> None:
        if self._carrier is None or self._carrier_observer_tag is None:
            return
        try:
            self._carrier.RemoveObserver(self._carrier_observer_tag)
        except Exception:  # noqa: BLE001 - teardown is best-effort
            pass
        self._carrier_observer_tag = None

    def _onCarrierModified(self, caller: Any, event: str) -> None:
        del caller, event
        if self._rebuilding:
            return
        previous = self._known_seed_count
        self._rebuild()
        current = self._seedCount()
        self._known_seed_count = current
        if previous is None:
            return
        if current == previous + 1:
            # Exactly one seed appended = a placement: publish the new seed's
            # highlight DIRECTLY so the carved-region stripes show what the
            # seed just measured, with no row interaction.  No visibility
            # restore: the seed's snapshot equals the live visibility at
            # placement, so the restore stays with the explicit toggle.
            self._publishHighlight(self._seedID(current - 1))
        # A removal needs no branch here: the highlight is keyed by STABLE ID,
        # so deleting a DIFFERENT seed leaves the pin resolving (the rebuild
        # re-seats it), and deleting the pinned seed itself retires the pin in
        # ``_syncHighlightAfterRebuild`` (the ID no longer resolves).

    # ------------------------------------------------------------------ #
    # Stable seed-ID addressing (identity survives index shifts)
    # ------------------------------------------------------------------ #

    def _seedID(self, seedIndex: int) -> str:
        """The stable ID of the seed at CURRENT index ``seedIndex`` ("" gone).

        The carrier mints the ID at AddSeed (``GetNthSeedID``).  A carrier
        without the ID slot degrades to a positional pseudo-key so the table
        still renders; identity guarantees need the carrier slot.
        """
        index = int(seedIndex)
        if self._carrier is None or index < 0 or index >= self._seedCount():
            return ""
        if hasattr(self._carrier, "GetNthSeedID"):
            return self._carrier.GetNthSeedID(index) or ""
        return f"index:{index}"

    def _resolveSeedIndex(self, seedID: str) -> int:
        """The CURRENT index of the seed carrying ``seedID`` (-1 when gone)."""
        if not seedID or self._carrier is None:
            return -1
        if hasattr(self._carrier, "GetSeedIndexByID"):
            return self._carrier.GetSeedIndexByID(seedID)
        if seedID.startswith("index:"):
            index = int(seedID[len("index:"):])
            return index if 0 <= index < self._seedCount() else -1
        return -1

    # ------------------------------------------------------------------ #
    # Item-model reader seams
    # ------------------------------------------------------------------ #

    def tree(self) -> Any:
        """The underlying ``qt.QTreeWidget``."""
        return self._tree

    def table(self) -> Any:
        """Back-compat alias for the underlying tree (the flat table's seam)."""
        return self._tree

    def rowCount(self) -> int:
        """The number of SEED rows currently RENDERED (one per carrier seed).

        Counts the built rows, not the live carrier: after ``cleanup``
        detached the carrier observer, a carrier edit must NOT read as a
        rebuilt table (feedback_launched_widget_teardown_crash).
        """
        return len(self._seed_rows)

    def volumeIds(self) -> list[str]:
        """The volume ids of the top-level items, in display order."""
        return list(self._volume_items.keys())

    def volumeItem(self, volumeId: str) -> Any:
        """The top-level ``QTreeWidgetItem`` for ``volumeId`` (or ``None``)."""
        return self._volume_items.get(volumeId)

    def seedIndicesForVolume(self, volumeId: str) -> list[int]:
        """The GLOBAL seed indices assigned to ``volumeId``, in placement order."""
        if self._carrier is None:
            return []
        return [
            i
            for i in range(self._carrier.GetNumberOfSeeds())
            if self._carrier.GetNthSeedVolume(i) == volumeId
        ]

    # -- per-volume control getters (by volume id) --------------------- #

    def _volumeControl(self, volumeId: str, key: str) -> Any:
        row = self._volume_rows.get(volumeId)
        return row[key] if row is not None else None

    def placeButton(self, volumeId: str) -> Any:
        """The checkable Place ``qt.QToolButton`` on the volume row."""
        return self._volumeControl(volumeId, "place")

    def volumeColourButton(self, volumeId: str) -> Any:
        """The ``ctk.ctkColorPickerButton`` on the volume row."""
        return self._volumeControl(volumeId, "colour")

    def volumeLabelEdit(self, volumeId: str) -> Any:
        """The editable label ``qt.QLineEdit`` on the volume row."""
        return self._volumeControl(volumeId, "label")

    def volumeOverflowButton(self, volumeId: str) -> Any:
        """The volume row's "..." overflow ``qt.QToolButton``."""
        return self._volumeControl(volumeId, "overflow")

    def volumeRemoveAction(self, volumeId: str) -> Any:
        """The overflow menu's "Remove volume..." ``qt.QAction``.

        Replaces the retired per-row Remove button (the row diet); the
        action confirms when the volume still carries seeds.
        """
        return self._volumeControl(volumeId, "removeAction")

    # -- per-seed control getters (by GLOBAL index; flat-table contract).
    # The getters stay INDEX-signed for back-compat and resolve index -> the
    # stable-ID row key internally. --------------------------------------- #

    def _seedControl(self, seedIndex: int, key: str) -> Any:
        row = self._seed_rows.get(self._seedID(int(seedIndex)))
        return row[key] if row is not None else None

    def colourButton(self, seedIndex: int) -> Any:
        """The seed row's ``ctk.ctkColorPickerButton`` (keyed by global index)."""
        return self._seedControl(seedIndex, "colour")

    def labelEdit(self, seedIndex: int) -> Any:
        """The seed row's editable label ``qt.QLineEdit`` (keyed by global index)."""
        return self._seedControl(seedIndex, "label")

    def targetCombo(self, seedIndex: int) -> Any:
        """The seed row's retarget control (keyed by global index).

        Historic name kept for the test contract; since the row diet this is
        the overflow menu's Retarget SUBMENU (``qt.QMenu`` -- the touched
        candidates as checkable actions, the bound one checked), no longer a
        ``QComboBox``.  ``retargetMenu`` is the same seam under its real name.
        """
        return self._seedControl(seedIndex, "target")

    def retargetMenu(self, seedIndex: int) -> Any:
        """The overflow menu's Retarget submenu (keyed by global index)."""
        return self._seedControl(seedIndex, "target")

    def overflowButton(self, seedIndex: int) -> Any:
        """The seed row's "..." overflow ``qt.QToolButton`` (keyed by index)."""
        return self._seedControl(seedIndex, "overflow")

    def deleteAction(self, seedIndex: int) -> Any:
        """The overflow menu's "Delete seed" ``qt.QAction`` (keyed by index).

        Replaces the retired per-row delete button (the row diet: the
        destructive action sits behind the overflow, out of the misclick
        path, and confirms when the seed carries a visibility snapshot).
        """
        return self._seedControl(seedIndex, "deleteAction")

    def restoreAction(self, seedIndex: int) -> Any:
        """The overflow menu's "Restore placement view" ``qt.QAction``."""
        return self._seedControl(seedIndex, "restore")

    def statusLabel(self, seedIndex: int) -> Any:
        """The seed row's empty-carve cue ``qt.QLabel`` (keyed by global index)."""
        return self._seedControl(seedIndex, "status")

    def divergenceChip(self, seedIndex: int) -> Any:
        """The seed row's divergence chip (pinned-row live-vs-snapshot text,
        doubling as the Restore placement view entry; keyed by global index)."""
        return self._seedControl(seedIndex, "chip")

    def highlightButton(self, seedIndex: int) -> Any:
        """The seed row's checkable Pin ``qt.QToolButton`` (the stripes'
        dedicated driver -- stripes only, never a visibility change; keyed
        by global index).  Historic getter name kept for the test contract."""
        return self._seedControl(seedIndex, "highlight")

    def pinButton(self, seedIndex: int) -> Any:
        """Alias for ``highlightButton`` under the control's surgeon name."""
        return self.highlightButton(seedIndex)

    # ------------------------------------------------------------------ #
    # Volume lifecycle (add / arm / delete)
    # ------------------------------------------------------------------ #

    def addVolume(self, volumeId: str | None = None) -> str:
        """Mint a volume and arm placement into it (the active-volume seam).

        Returns the (possibly auto-generated) volume id.  Registers a carrier
        display slot so the empty volume's top-level row survives before a seed
        lands, gives it a distinct palette colour, and arms placement into it via
        the shared display node.
        """
        if volumeId is None:
            volumeId = self._mintVolumeId()
        newVolume = volumeId not in self._volume_order
        if newVolume:
            self._volume_order.append(volumeId)
        if self._carrier is not None:
            self._carrier.AddVolume(volumeId)
            if newVolume:
                r, g, b = _VOLUME_PALETTE[
                    (len(self._volume_order) - 1) % len(_VOLUME_PALETTE)
                ]
                self._carrier.SetVolumeColor(volumeId, r, g, b)
        self._armInto(volumeId)
        self._rebuild()
        return volumeId

    def deleteVolume(self, volumeId: str) -> None:
        """Remove a whole volume (its seeds + display slot) via the carrier.

        If the removed volume was the display node's ACTIVE (armed) volume, the
        arm state is cleared first so placement does not target a gone volume.
        """
        if not volumeId or self._carrier is None:
            return
        if self._activeVolume() == volumeId:
            self._disarm()
        self._volume_order = [v for v in self._volume_order if v != volumeId]
        self._carrier.RemoveVolume(volumeId)

    def _mintVolumeId(self) -> str:
        while True:
            self._mint_counter += 1
            candidate = f"Volume {self._mint_counter}"
            if candidate not in self._volume_order and (
                self._carrier is None or candidate not in list(self._carrier.GetVolumeIds())
            ):
                return candidate

    # -- arm state on the shared display node -------------------------- #

    def _state(self) -> Any:
        return PointPlacementState(VOLUMETRY_NAMESPACE)

    def _activeVolume(self) -> str:
        if self._displayNode is None:
            return ""
        return self._state().get_active(self._displayNode) or ""

    def _isArmedInto(self, volumeId: str) -> bool:
        state = self._state()
        return (
            self._displayNode is not None
            and state.is_armed(self._displayNode)
            and state.get_active(self._displayNode) == volumeId
        )

    def _armInto(self, volumeId: str) -> None:
        """Arm placement into ``volumeId`` via the shared display node.

        The placement guard: arming while a RESTORED context is active first
        returns to "my view", so a new seed's snapshot is always minted from
        the surgeon's own composition, never a borrowed placement view.
        """
        if self._restoredSeedID:
            self.returnToMyView()
        if self._displayNode is None:
            return
        state = self._state()
        state.set_active(self._displayNode, volumeId)
        state.set_armed(self._displayNode, True)

    def _disarm(self) -> None:
        if self._displayNode is None:
            return
        self._state().set_armed(self._displayNode, False)

    def cancelArmedPlacement(self) -> None:
        """ESC: cancel an armed placement (disarm + uncheck the Place toggle).

        A no-op when nothing is armed.  Touches ONLY the arm state -- the
        pin, the stripes, and the restored context all stay.
        """
        display = self._displayNode
        if display is None or not self._state().is_armed(display):
            return
        self._disarm()
        self._rebuild()  # repaint unchecks the armed volume's Place toggle

    def _onPlaceToggled(self, volumeId: str, checked: bool) -> None:
        """Arm into ``volumeId`` exclusively on ON; disarm on OFF."""
        if self._rebuilding:
            return
        if checked:
            self._armInto(volumeId)
        else:
            self._disarm()
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Edits (write back to the carrier)
    # ------------------------------------------------------------------ #

    def setVolumeColor(self, volumeId: str, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetVolumeColor(volumeId, float(r), float(g), float(b))

    def setVolumeLabel(self, volumeId: str, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetVolumeLabel(volumeId, str(label))

    def setSeedColor(self, seedIndex: int, r: float, g: float, b: float) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedColor(int(seedIndex), float(r), float(g), float(b))

    def setSeedLabel(self, seedIndex: int, label: str) -> None:
        if self._carrier is not None:
            self._carrier.SetNthSeedLabel(int(seedIndex), str(label))

    def deleteSeed(self, seedIndex: int) -> None:
        """Remove the seed at ``seedIndex`` via the carrier's ``RemoveNthSeed``."""
        if self._carrier is not None:
            self._carrier.RemoveNthSeed(int(seedIndex))

    def retargetSeed(self, seedIndex: int, segmentID: str) -> None:
        """Rebind the seed at ``seedIndex`` to ``segmentID`` + re-name.

        The Target combo is the FALLBACK retarget of the OWNING segment: the
        carve re-derives within the SAME visibility snapshot (the carrier's
        ModifiedEvent invalidates the pipelines' carve cache), so a highlighted
        seed's stripes follow the new owner without touching the context.
        """
        if self._carrier is None or not segmentID:
            return
        source = self._structureSource
        if source is None:
            return
        self._carrier.SetNthSeedBinding(seedIndex, source.GetID(), segmentID)
        segment = source.GetSegmentation().GetSegment(segmentID)
        if segment is not None:
            self.setSeedLabel(seedIndex, segment.GetName())

    def _onVolumeLabelEdited(self, volumeId: str, edit: Any) -> None:
        if self._rebuilding:
            return
        self.setVolumeLabel(volumeId, edit.text)

    def _onVolumeColourChanged(self, volumeId: str, colour: Any) -> None:
        if self._rebuilding:
            return
        self.setVolumeColor(volumeId, colour.redF(), colour.greenF(), colour.blueF())

    def _onLabelEdited(self, seedID: str, edit: Any) -> None:
        if self._rebuilding:
            return
        index = self._resolveSeedIndex(seedID)
        if index >= 0:
            self.setSeedLabel(index, edit.text)

    def _onColourChanged(self, seedID: str, colour: Any) -> None:
        if self._rebuilding:
            return
        index = self._resolveSeedIndex(seedID)
        if index >= 0:
            self.setSeedColor(index, colour.redF(), colour.greenF(), colour.blueF())

    def _onHighlightToggled(self, seedID: str, checked: bool) -> None:
        """The dedicated stripe driver (the row's Pin toggle).

        Checking raises the seed's marching-stripes highlight; the toggles
        are exclusive, so this retires any other seed's highlight.
        Unchecking clears the highlight.  The pin is STRIPES ONLY -- it
        NEVER touches the segment visibility; restoring the placement view
        is the explicit "Restore placement view" affordance instead.  Keyed
        by the seed's STABLE ID: the toggle keeps naming its seed even after
        other rows' deletions reshuffle the indices.
        """
        if self._rebuilding:
            return
        if checked:
            if self._resolveSeedIndex(seedID) < 0:
                return
            self._publishHighlight(seedID)
        else:
            self._retireHighlight()

    # ------------------------------------------------------------------ #
    # Restore placement view (explicit, symmetric, depth ONE)
    # ------------------------------------------------------------------ #

    def _seedVisibilityContext(self, seedIndex: int) -> list[str]:
        """The seed's ordered (top-first) visibility snapshot off the carrier."""
        return read_seed_context(self._carrier, seedIndex)

    def restoredSeedID(self) -> str:
        """The seed whose placement view is currently restored ("" none)."""
        return self._restoredSeedID

    def restoreBanner(self) -> Any:
        """The restored-context banner widget (introspection seam)."""
        return self._restoreBanner

    def restoreBannerLabel(self) -> Any:
        """The banner's text label (introspection seam)."""
        return self._restoreBannerLabel

    def returnToMyViewButton(self) -> Any:
        """The banner's inline return button (introspection seam)."""
        return self._returnToMyViewButton

    def restorePlacementView(self, seedID: str) -> bool:
        """Flip the visibility to ``seedID``'s placement snapshot (depth one).

        Entering a restored context first captures the CURRENT visibility as
        "my view" (one slot); restoring ANOTHER seed while restored is a
        SWITCH that reuses the same capture.  A snapshot sharing NO segment
        with the segmentation's current segment IDs is REFUSED (the
        stale-snapshot hard-guard: the view is never blanked) -- the banner
        names the refusal.  Returns True iff the restore was applied.
        """
        source = self._structureSource
        index = self._resolveSeedIndex(seedID)
        if source is None or not hasattr(source, "GetSegmentation") or index < 0:
            return False
        context = self._seedVisibilityContext(index)
        if not set(context) & set(self._allSegmentIDs()):
            self._showBanner(STALE_SNAPSHOT_MESSAGE, withReturn=False)
            return False
        if not self._restoredSeedID:
            # Entering the restored context: capture the surgeon's own
            # composition ONCE; a switch to another seed reuses it.
            self._myViewContext = visible_context(source, source.GetDisplayNode())
        self._restoredSeedID = seedID
        self._applyContext(context)
        self._showBanner(self._restoreBannerText(index), withReturn=True)
        # The widget's own write is guarded off the observer; re-derive the
        # pinned row's divergence chip here instead.
        self._updateDivergenceChips()
        return True

    def returnToMyView(self) -> None:
        """Put the visibility back to the pre-restore capture + end the context."""
        context = self._myViewContext
        if context:
            self._applyContext(context)
        self._endRestoredContext()
        self._updateDivergenceChips()

    def _endRestoredContext(self) -> None:
        """Drop the restored context + its capture and hide the banner.

        Never touches visibility itself -- the return path applies the
        capture BEFORE calling this; a user takeover / module exit ends the
        context with the view exactly as the user left it.
        """
        self._restoredSeedID = ""
        self._myViewContext = None
        self._restoredVisibleSet = None
        self._hideBanner()

    def _allSegmentIDs(self) -> list[str]:
        """Every segment ID on the structure source ([] when unbound)."""
        source = self._structureSource
        if source is None or not hasattr(source, "GetSegmentation"):
            return []
        segmentation = source.GetSegmentation()
        return [
            segmentation.GetNthSegmentID(n)
            for n in range(segmentation.GetNumberOfSegments())
        ]

    def _applyContext(self, context: list[str]) -> None:
        """Show exactly ``context``'s segments on the structure source.

        Marks the write as the widget's OWN (``_applyingVisibility``) so the
        takeover observer does not read it as the user's, and records the
        applied visible set for the takeover comparison.
        """
        source = self._structureSource
        if source is None or not hasattr(source, "GetSegmentation"):
            return
        self._applyingVisibility = True
        try:
            apply_visibility_context(
                source.GetDisplayNode(), self._allSegmentIDs(), context
            )
        finally:
            self._applyingVisibility = False
        self._restoredVisibleSet = frozenset(
            visible_context(source, source.GetDisplayNode())
        )

    def _restoreBannerText(self, seedIndex: int) -> str:
        """The banner line naming the restored seed + its volume in text."""
        label = self._seedLabel(seedIndex) or f"Seed {seedIndex + 1}"
        volumeLabel = ""
        if self._carrier is not None and hasattr(self._carrier, "GetNthSeedVolume"):
            volumeId = self._carrier.GetNthSeedVolume(seedIndex)
            if volumeId:
                volumeLabel = self._carrier.GetVolumeLabel(volumeId) or volumeId
        if volumeLabel:
            return f"{RESTORE_BANNER_PREFIX} {label} ({volumeLabel})"
        return f"{RESTORE_BANNER_PREFIX} {label}"

    def _showBanner(self, text: str, withReturn: bool) -> None:
        self._restoreBannerLabel.setText(text)
        self._returnToMyViewButton.setVisible(bool(withReturn))
        self._restoreBanner.setVisible(True)

    def _hideBanner(self) -> None:
        self._restoreBannerLabel.setText("")
        self._restoreBanner.setVisible(False)

    # -- user-takeover detection (the eye list wins) -------------------- #

    def _observeSourceDisplay(self) -> None:
        """(Re)attach the takeover observer to the source's display node."""
        source = self._structureSource
        display = (
            source.GetDisplayNode()
            if source is not None and hasattr(source, "GetDisplayNode")
            else None
        )
        if display is self._observedSourceDisplay:
            return
        self._detachSourceDisplayObserver()
        if display is None or not hasattr(display, "AddObserver"):
            return
        self._observedSourceDisplay = display
        self._sourceDisplayObserverTag = display.AddObserver(
            vtk.vtkCommand.ModifiedEvent, self._onSourceDisplayModified
        )

    def _detachSourceDisplayObserver(self) -> None:
        display = self._observedSourceDisplay
        if display is not None and self._sourceDisplayObserverTag is not None:
            try:
                display.RemoveObserver(self._sourceDisplayObserverTag)
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass
        self._observedSourceDisplay = None
        self._sourceDisplayObserverTag = None

    def _onSourceDisplayModified(self, caller: Any, event: str) -> None:
        """React to an eye-list change: takeover check + divergence chip.

        The widget's own restore writes are marked (``_applyingVisibility``)
        and skipped; an unrelated display edit (opacity, colour) leaves the
        visible set unchanged and is ignored by the takeover check.  A real
        takeover ends the restored context WITHOUT re-asserting anything:
        the user's toggles win.  The pinned row's divergence chip re-derives
        on every change either way.
        """
        del caller, event
        if self._applyingVisibility:
            return
        if self._restoredSeedID:
            source = self._structureSource
            if source is not None:
                current = frozenset(
                    visible_context(source, source.GetDisplayNode())
                )
                if (
                    self._restoredVisibleSet is None
                    or current != self._restoredVisibleSet
                ):
                    self._endRestoredContext()
        self._updateDivergenceChips()

    # ------------------------------------------------------------------ #
    # Divergence chip (live visibility vs the pinned seed's snapshot)
    # ------------------------------------------------------------------ #

    def _updateDivergenceChips(self) -> None:
        """Show the chip on exactly the PINNED row when live != snapshot.

        Compares the SETS of visible segment IDs vs the seed's snapshot (the
        top-first order derives from the layer indices, which the eye list
        does not move).  Hidden when unpinned, matching, snapshotless (a
        legacy seed has nothing to diverge from), or sourceless.
        """
        pinnedID = self._highlightedSeedID
        diverges = False
        if pinnedID:
            source = self._structureSource
            index = self._resolveSeedIndex(pinnedID)
            if source is not None and index >= 0:
                snapshot = self._seedVisibilityContext(index)
                if snapshot:
                    live = visible_context(source, source.GetDisplayNode())
                    diverges = set(live) != set(snapshot)
        for rowID, row in self._seed_rows.items():
            chip = row.get("chip")
            if chip is not None:
                chip.setVisible(diverges and rowID == pinnedID)

    # ------------------------------------------------------------------ #
    # Repaint
    # ------------------------------------------------------------------ #

    def _seedCount(self) -> int:
        if self._carrier is None:
            return 0
        return self._carrier.GetNumberOfSeeds()

    def _volumes(self) -> list[str]:
        """The volumes to render, in a stable first-seen order.

        Union of the local minted order and the carrier's enumerated volumes
        (seed-bearing + display-slot), so a volume added outside the table (a
        pipeline click into a fresh volume) still gets a top-level row and an
        empty minted volume keeps its row.
        """
        order = list(self._volume_order)
        seen = set(order)
        if self._carrier is not None:
            for volumeId in self._carrier.GetVolumeIds():
                if volumeId not in seen:
                    seen.add(volumeId)
                    order.append(volumeId)
        self._volume_order = order
        return order

    def _rebuild(self) -> None:
        self._rebuilding = True
        try:
            self._tree.clear()
            self._volume_items = {}
            self._volume_rows = {}
            self._seed_rows = {}
            self._seed_items = {}
            # Seeds grouped by volume; ungrouped seeds ride a synthetic
            # "Ungrouped" bucket so a legacy / pre-volume seed still shows.
            grouped: dict[str, list[int]] = {}
            ungrouped: list[int] = []
            for i in range(self._seedCount()):
                volumeId = self._carrier.GetNthSeedVolume(i)
                if volumeId:
                    grouped.setdefault(volumeId, []).append(i)
                else:
                    ungrouped.append(i)
            for volumeId in self._volumes():
                self._appendVolumeItem(volumeId, grouped.get(volumeId, []))
            if ungrouped:
                self._appendUngroupedSeeds(ungrouped)
            self._tree.expandAll()
        finally:
            self._rebuilding = False
        self._syncHighlightAfterRebuild()

    def _appendVolumeItem(self, volumeId: str, seedIndices: list[int]) -> None:
        item = qt.QTreeWidgetItem(self._tree)
        self._volume_items[volumeId] = item
        rowWidget = self._buildVolumeRow(volumeId)
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, rowWidget)
        self._installRowSelectFilter(rowWidget, _ROW_VOLUME_PROPERTY, volumeId)
        for seedIndex in seedIndices:
            self._appendSeedItem(item, seedIndex)

    def _appendUngroupedSeeds(self, seedIndices: list[int]) -> None:
        item = qt.QTreeWidgetItem(self._tree)
        label = qt.QLabel("Ungrouped seeds")
        self._tree.setItemWidget(item, _COMPOSITE_COLUMN, label)
        for seedIndex in seedIndices:
            self._appendSeedItem(item, seedIndex)

    def _buildVolumeRow(self, volumeId: str) -> Any:
        """Compose a volume row's horizontal control strip: Place / colour /
        label / delete (ADR-0010 glyph + text)."""
        color = _DEFAULT_SEED_COLOR
        label = volumeId
        if self._carrier is not None:
            rgb = self._carrier.GetVolumeColor(volumeId)
            color = (rgb[0], rgb[1], rgb[2])
            label = self._carrier.GetVolumeLabel(volumeId) or volumeId

        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        placeButton = qt.QToolButton()
        placeButton.setAutoRaise(True)
        placeButton.setCheckable(True)
        _apply_toggle_icon(placeButton, _PLACE_ICON_OFF, _PLACE_ICON_ON, "Place")
        placeButton.setToolTip("Arm placement into this volume (exclusive)")
        placeButton.setAccessibleName("Place seeds into this volume")
        placeButton.setChecked(self._isArmedInto(volumeId))
        placeButton.connect(
            "toggled(bool)",
            lambda checked, v=volumeId: self._onPlaceToggled(v, checked),
        )
        rowLayout.addWidget(placeButton)

        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.setToolTip(f"{label} colour")
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, v=volumeId: self._onVolumeColourChanged(v, c),
        )
        rowLayout.addWidget(colourButton)

        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.setPlaceholderText(volumeId)
        labelEdit.setToolTip("Label for this volume")
        labelEdit.connect(
            "editingFinished()",
            lambda v=volumeId, e=labelEdit: self._onVolumeLabelEdited(v, e),
        )
        rowLayout.addWidget(labelEdit, 1)

        # The volume overflow "..." (the row diet): Remove sits one
        # deliberate step away and confirms when seeds would go with it.
        overflowButton = qt.QToolButton()
        overflowButton.setAutoRaise(True)
        overflowButton.setText("...")
        overflowButton.setToolTip("More actions for this volume")
        overflowButton.setPopupMode(qt.QToolButton.InstantPopup)
        menu = qt.QMenu(overflowButton)
        removeAction = menu.addAction("Remove volume...")
        removeAction.connect(
            "triggered()", lambda v=volumeId: self._onRemoveVolumeAction(v)
        )
        overflowButton.setMenu(menu)
        rowLayout.addWidget(overflowButton)

        self._volume_rows[volumeId] = {
            "widget": rowWidget,
            "place": placeButton,
            "colour": colourButton,
            "label": labelEdit,
            "overflow": overflowButton,
            "removeAction": removeAction,
        }
        return rowWidget

    def _onRemoveVolumeAction(self, volumeId: str) -> None:
        """Remove via the overflow menu, confirming when seeds go with it.

        A volume with N > 0 seeds names them in the confirm; an empty volume
        removes one-click.  The programmatic ``deleteVolume`` seam stays
        confirm-free for scripted callers.
        """
        seedCount = len(self.seedIndicesForVolume(volumeId))
        if seedCount > 0:
            label = volumeId
            if self._carrier is not None:
                label = self._carrier.GetVolumeLabel(volumeId) or volumeId
            noun = "seed" if seedCount == 1 else "seeds"
            if not self._confirmDestructive(
                f'Remove "{label}" and its {seedCount} {noun}?'
            ):
                return
        self.deleteVolume(volumeId)

    def _appendSeedItem(self, parentItem: Any, seedIndex: int) -> None:
        child = qt.QTreeWidgetItem(parentItem)
        # Carry the CURRENT global seed index on the item for positional
        # introspection (tests walk rows by index); the row-keying itself is
        # the stable ID below.
        child.setData(0, qt.Qt.UserRole, seedIndex)
        seedID = self._seedID(seedIndex)
        self._seed_items[seedID] = child
        rowWidget = self._buildSeedRow(seedIndex)
        self._tree.setItemWidget(child, _COMPOSITE_COLUMN, rowWidget)
        self._installRowSelectFilter(rowWidget, _ROW_SEED_PROPERTY, seedID)

    # ------------------------------------------------------------------ #
    # Row-select event filter (a press anywhere on a composite row selects
    # the row FIRST, without consuming the press)
    # ------------------------------------------------------------------ #

    def _installRowSelectFilter(self, rowWidget: Any, propertyName: str, key: Any) -> None:
        """Tag the row widget + every descendant and watch their mouse presses.

        The composite row widget covers the whole tree item, so a press on
        "the row" always lands on a child control (mostly the stretch line
        edit) and is CONSUMED there -- the tree viewport never sees it and
        the item would never read selected on a real click.  Tagging rides a
        dynamic Qt property (stable across PythonQt wrapper identities); the
        filter resolves it back to the tree item and selects, then lets the
        press continue into the control.  Selection is PLAIN row UX -- it
        drives no visibility or highlight state.
        """
        # Manual descendant walk: PythonQt does not reliably wrap the template
        # ``findChildren`` (the ``slicer.util.findChildren`` precedent).
        stack = [rowWidget]
        while stack:
            widget = stack.pop()
            widget.setProperty(propertyName, key)
            if hasattr(widget, "installEventFilter"):
                widget.installEventFilter(self)
            stack.extend(widget.children())

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt virtual
        try:
            eventType = event.type()
            if eventType == qt.QEvent.MouseButtonPress:
                self._selectRowForWidget(watched)
            elif eventType in (qt.QEvent.Enter, qt.QEvent.Leave):
                pinSeedID = watched.property(_ROW_PIN_PROPERTY)
                if pinSeedID:
                    if eventType == qt.QEvent.Enter:
                        self._startHoverPreview(str(pinSeedID))
                    else:
                        self._endHoverPreview()
        except Exception:  # noqa: BLE001 - an event filter must never raise
            pass
        return False  # never consume: the watched control still works

    def _selectRowForWidget(self, widget: Any) -> None:
        """Select the tree row the pressed row-child ``widget`` belongs to.

        Resolves the row key off the widget's dynamic property (stable seed ID
        or volume id) and makes that item the current selection.  Selection is
        plain row UX with NO side effects -- the stripes and the visibility
        restore belong to the Highlight toggle + placement.  A no-op for
        untagged widgets or during a rebuild.
        """
        if self._rebuilding or widget is None:
            return
        item = None
        seedID = widget.property(_ROW_SEED_PROPERTY)
        if seedID:
            item = self._seed_items.get(str(seedID))
        else:
            volumeId = widget.property(_ROW_VOLUME_PROPERTY)
            if volumeId:
                item = self._volume_items.get(str(volumeId))
        if item is None or item.isSelected():
            return
        self._tree.setCurrentItem(item)

    def _seedColor(self, seedIndex: int) -> tuple[float, float, float]:
        if self._carrier is None:
            return _DEFAULT_SEED_COLOR
        rgb = self._carrier.GetNthSeedColor(seedIndex)
        return (rgb[0], rgb[1], rgb[2])

    def _seedLabel(self, seedIndex: int) -> str:
        if self._carrier is None:
            return ""
        return self._carrier.GetNthSeedLabel(seedIndex)

    def _buildSeedRow(self, seedIndex: int) -> Any:
        """Compose one seed row: highlight toggle, colour swatch, label,
        target combo, delete.

        Every control callback captures the seed's STABLE ID and resolves the
        current index at fire time, so an edit landing after another row's
        deletion still writes to the seed it was built for.
        """
        seedID = self._seedID(seedIndex)
        color = self._seedColor(seedIndex)
        label = self._seedLabel(seedIndex)

        rowWidget = qt.QWidget()
        rowLayout = qt.QHBoxLayout(rowWidget)
        rowLayout.setContentsMargins(2, 1, 2, 1)
        rowLayout.setSpacing(4)

        # The DEDICATED stripe driver: one small checkable button whose only
        # job is the stripes (exclusive across seeds; NEVER a visibility
        # change).  Icon-only push-pin (out/in on the toggle) with the name
        # riding the tooltip + accessible name per ADR-0010 -- the icon
        # never stands alone.
        highlightButton = qt.QToolButton()
        highlightButton.setAutoRaise(True)
        highlightButton.setCheckable(True)
        _apply_toggle_icon(highlightButton, _PIN_ICON_OFF, _PIN_ICON_ON, "Pin")
        highlightButton.setToolTip(
            "Show this seed's measured region as a striped overlay"
        )
        highlightButton.setAccessibleName("Pin this seed's measured region")
        highlightButton.setChecked(bool(seedID) and seedID == self._highlightedSeedID)
        highlightButton.connect(
            "toggled(bool)",
            lambda checked, s=seedID: self._onHighlightToggled(s, checked),
        )
        # Tag the Pin button for the hover-PREVIEW (the shared event filter
        # resolves Enter/Leave back to this seed).
        highlightButton.setProperty(_ROW_PIN_PROPERTY, seedID)
        rowLayout.addWidget(highlightButton)

        colourButton = ctk.ctkColorPickerButton()
        colourButton.displayColorName = False
        colourButton.setColor(
            qt.QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
        )
        colourButton.setToolTip(f"Seed {seedIndex + 1} colour")
        colourButton.connect(
            "colorChanged(QColor)",
            lambda c, s=seedID: self._onColourChanged(s, c),
        )
        rowLayout.addWidget(colourButton)

        labelEdit = qt.QLineEdit()
        labelEdit.setText(label)
        labelEdit.setPlaceholderText(f"Seed {seedIndex + 1} label")
        labelEdit.setToolTip("Label for this seed (becomes the generated segment name)")
        labelEdit.connect(
            "editingFinished()",
            lambda s=seedID, e=labelEdit: self._onLabelEdited(s, e),
        )
        rowLayout.addWidget(labelEdit, 1)

        # The empty-carve cue label: hidden until THIS row is highlighted
        # (toggle or placement) and its carved region turns out empty
        # (``EMPTY_CARVE_MESSAGE``).  Plain row text (ADR-0010) right where
        # the surgeon is looking -- the stripes' absence is named, never a
        # silent nothing.
        statusLabel = qt.QLabel("")
        statusLabel.setVisible(False)
        rowLayout.addWidget(statusLabel)

        # The divergence chip (PINNED row only): plain text naming that the
        # live visibility differs from the seed's placement snapshot, and
        # the click-through entry point to Restore placement view.
        divergenceChip = qt.QToolButton()
        divergenceChip.setAutoRaise(True)
        divergenceChip.setText(DIVERGENCE_CHIP_TEXT)
        divergenceChip.setToolTip(
            "The current show/hide composition is not the one this seed was "
            "measured under. Click to restore the placement view."
        )
        divergenceChip.setVisible(False)
        divergenceChip.connect(
            "clicked(bool)",
            lambda _checked, s=seedID: self.restorePlacementView(s),
        )
        rowLayout.addWidget(divergenceChip)

        # The overflow "..." menu (the row diet: at most four visible
        # controls; the occasional actions -- retarget, restore, delete --
        # sit one deliberate step away, out of the misclick path).
        overflowButton, retargetMenu, restoreAction, deleteAction = (
            self._buildSeedOverflow(seedIndex, seedID)
        )
        rowLayout.addWidget(overflowButton)

        # a11y: name the owning segment + the visibility context in TEXT on
        # the row (ADR-0010 -- never colour/animation alone).  "Restore
        # placement view" shows this snapshot; the tooltip says what it is.
        rowWidget.setToolTip(self._seedContextToolTip(seedIndex))

        self._seed_rows[seedID] = {
            "widget": rowWidget,
            "highlight": highlightButton,
            "colour": colourButton,
            "label": labelEdit,
            "target": retargetMenu,
            "overflow": overflowButton,
            "restore": restoreAction,
            "deleteAction": deleteAction,
            "status": statusLabel,
            "chip": divergenceChip,
        }
        return rowWidget

    def _buildSeedOverflow(self, seedIndex: int, seedID: str) -> tuple:
        """Compose the seed row's "..." overflow: Retarget / Restore / Delete.

        Returns ``(button, retargetMenu, restoreAction, deleteAction)``.  The
        retarget submenu carries the touched candidates top-first with the
        BOUND segment checked (the former Target combo's model); Delete goes
        through the snapshot-aware confirm.
        """
        overflowButton = qt.QToolButton()
        overflowButton.setAutoRaise(True)
        overflowButton.setText("...")
        overflowButton.setToolTip("More actions for this seed")
        overflowButton.setPopupMode(qt.QToolButton.InstantPopup)
        menu = qt.QMenu(overflowButton)

        retargetMenu = menu.addMenu("Retarget")
        retargetMenu.setToolTip(
            "The structure this seed is bound to (pick another to retarget)"
        )
        boundSegmentID = self._seedBindingSegmentID(seedIndex)
        candidates = self._touchedCandidates(seedIndex)
        if boundSegmentID and boundSegmentID not in candidates:
            candidates = [boundSegmentID] + candidates
        if candidates:
            for segmentID in candidates:
                action = retargetMenu.addAction(
                    self._segmentName(segmentID) or segmentID
                )
                action.setCheckable(True)
                action.setChecked(segmentID == boundSegmentID)
                action.connect(
                    "triggered()",
                    lambda s=seedID, seg=segmentID: self._onRetargetAction(s, seg),
                )
        else:
            unbound = retargetMenu.addAction("Unbound")
            unbound.setEnabled(False)

        restoreAction = menu.addAction("Restore placement view")
        restoreAction.connect(
            "triggered()", lambda s=seedID: self.restorePlacementView(s)
        )

        deleteAction = menu.addAction("Delete seed")
        deleteAction.connect(
            "triggered()", lambda s=seedID: self._onDeleteSeedAction(s)
        )

        overflowButton.setMenu(menu)
        return overflowButton, retargetMenu, restoreAction, deleteAction

    def _onRetargetAction(self, seedID: str, segmentID: str) -> None:
        """Route a retarget-submenu pick into ``retargetSeed`` (ID-keyed)."""
        if self._rebuilding:
            return
        index = self._resolveSeedIndex(seedID)
        if index >= 0 and segmentID:
            self.retargetSeed(index, segmentID)

    def _onDeleteSeedAction(self, seedID: str) -> None:
        """Delete via the overflow menu, confirming a snapshot-bearing seed.

        A seed WITH a visibility snapshot carries a placement view worth a
        pause; a plain snapshotless delete stays one click (re-placement is
        the recovery path).  The programmatic ``deleteSeed`` seam stays
        confirm-free for scripted callers.
        """
        index = self._resolveSeedIndex(seedID)
        if index < 0:
            return
        if self._seedVisibilityContext(index):
            label = self._seedLabel(index) or f"Seed {index + 1}"
            if not self._confirmDestructive(
                f'Delete seed "{label}"? Its placement view snapshot is '
                "deleted with it."
            ):
                return
        self.deleteSeed(index)

    def _confirmDestructive(self, text: str) -> bool:
        """The one destructive-action confirm seam (tests stub this)."""
        return (
            qt.QMessageBox.question(self, "Liver Volumetry", text)
            == qt.QMessageBox.Yes
        )

    def _seedContextToolTip(self, seedIndex: int) -> str:
        """The seed's owner + snapshot named in text (the a11y companion)."""
        owner = self._seedBindingSegmentID(seedIndex)
        ownerName = self._segmentName(owner) or owner or "unbound"
        context = self._seedVisibilityContext(seedIndex)
        if not context:
            return f"Structure: {ownerName} (no visibility snapshot)"
        contextNames = ", ".join(
            self._segmentName(segmentID) or segmentID for segmentID in context
        )
        return (
            f"Structure: {ownerName}. Visible at placement: {contextNames}. "
            "Restore placement view shows that view again."
        )

    # ------------------------------------------------------------------ #
    # Binding + candidate readers (the target column's model)
    # ------------------------------------------------------------------ #

    def _seedBindingSegmentID(self, seedIndex: int) -> str:
        if self._carrier is None or not hasattr(self._carrier, "GetNthSeedBindingSegmentID"):
            return ""
        return self._carrier.GetNthSeedBindingSegmentID(seedIndex)

    def _touchedCandidates(self, seedIndex: int) -> list[str]:
        source = self._structureSource
        if source is None or self._carrier is None:
            return []
        coord = self._carrier.GetNthSeed(seedIndex)
        ras = (float(coord[0]), float(coord[1]), float(coord[2]))
        touched = gather_touched_candidates(source, source.GetDisplayNode(), ras)
        ordered, _top = resolve_touched_candidates(touched)
        return ordered

    def _segmentName(self, segmentID: str) -> str:
        source = self._structureSource
        if source is None or not segmentID:
            return ""
        segment = source.GetSegmentation().GetSegment(segmentID)
        return segment.GetName() if segment is not None else ""

    # ------------------------------------------------------------------ #
    # Carved-region stripe highlight (CarvedRegionStripes; replaces the old
    # opacity-fade pulse -- persistent while toggled, never a blink)
    # ------------------------------------------------------------------ #

    def _highlightSeed(self, seedID: str) -> None:
        """Publish the highlight + start the march timer.

        The highlight state rides the shared display node
        (``feedback_layerdm_state_on_display_node``): this widget writes the
        seed's STABLE ID onto the transient ``HighlightSeedID`` member (never
        a node attribute -- attributes serialize into the scene XML) and the
        LayerDM slice pipelines render the stripes.  Persistent while the
        Highlight toggle stays on.
        """
        if not seedID:
            return
        # The pin BOOKKEEPING (the toggle state, the cue, the persistence
        # callback) is table state and holds with or without a display node;
        # only the stripes publish + the march need the shared node.  Without
        # this split, a display-less pin desynced the toggle (the sync
        # unchecked it) and the next uncheck never fired -- the cue stuck.
        self._highlightedSeedID = str(seedID)
        if self._displayNode is None:
            return
        set_highlight_seed_id(self._displayNode, self._highlightedSeedID)
        # March for as long as the pin is up: a frozen stripe texture reads as
        # a rendering fault and cannot be told apart from a stuck view, so the
        # motion IS the "this is live" signal and must not time out.
        if not self._stripeTimer.isActive():
            self._stripeTimer.start()

    def _clearHighlight(self) -> None:
        """Stop the march + clear the highlight off the display node."""
        if self._stripeTimer.isActive():
            self._stripeTimer.stop()
        if self._highlightedSeedID or self._previewSeedID:
            set_highlight_seed_id(self._displayNode, "")
        self._highlightedSeedID = ""
        self._previewSeedID = ""

    def _onStripeTick(self) -> None:
        """Fire one march tick (the calm, continuous stripe advance).

        The tick is a plain ``InvokeEvent`` on the shared display node
        (``invoke_stripe_tick``): no MRML write, no ModifiedEvent -- only the
        slice pipelines observing ``STRIPE_TICK_EVENT`` wake, advance their
        OWN local phase, and re-render (the SegmentEditorThresholdEffect
        widget-owned preview-timer precedent).  Held while a hover PREVIEW
        is up (the preview is static by contract), and UNBOUNDED otherwise:
        the march runs for the pin's whole life so the overlay always reads
        as live.  Module ``exit()`` stops the timer (nothing ticks in the
        background), which is what bounds it.
        """
        if self._displayNode is None or not self._highlightedSeedID:
            self._clearHighlight()
            return
        if self._previewSeedID:
            return
        invoke_stripe_tick(self._displayNode)

    # ------------------------------------------------------------------ #
    # Hover-preview (static + dimmed stripes on an unpinned seed's Pin)
    # ------------------------------------------------------------------ #

    def previewSeedID(self) -> str:
        """The seed previewed by the current Pin-button hover ("" none)."""
        return self._previewSeedID

    # ------------------------------------------------------------------ #
    # Pin persistence seams (parameter-node mirroring by the module widget)
    # ------------------------------------------------------------------ #

    def pinnedSeedID(self) -> str:
        """The pinned seed's stable ID ("" when nothing is pinned)."""
        return self._highlightedSeedID

    def setPinChangedCallback(self, callback: Any) -> None:
        """Register ``callback(seedID)`` fired on every REAL pin change.

        Fired for the toggle, placement auto-pin, and pin retirement --
        never for the hover preview (transient) and never from
        ``stopHighlight`` (module exit must keep the persisted pin).
        """
        self._pinChangedCallback = callback

    def pinSeed(self, seedID: str) -> bool:
        """Raise the pin on ``seedID`` (the enter()-time resume seam).

        Returns True iff the pin actually raised (the ID resolves on the
        carrier); anything less leaves the caller free to clear its
        persistence.  The stripes publish only when the shared display node
        is bound -- the pin bookkeeping itself never needs it.
        """
        if not seedID or self._resolveSeedIndex(seedID) < 0:
            return False
        self._publishHighlight(seedID)
        return self._highlightedSeedID == seedID

    def _firePinChanged(self, seedID: str) -> None:
        if self._suppressPinCallback or self._pinChangedCallback is None:
            return
        try:
            self._pinChangedCallback(seedID)
        except Exception:  # noqa: BLE001 - a persistence hook must not break the UI
            pass

    def _startHoverPreview(self, seedID: str) -> None:
        """Show ``seedID``'s stripes static + dimmed while its Pin is hovered.

        Only for an UNPINNED seed (hovering the pinned seed's own button is
        not a preview) and only when the seed still resolves.  No visibility
        change ever; the pinned highlight (if any) resumes on hover-out.
        """
        if self._rebuilding or self._displayNode is None:
            return
        if not seedID or seedID == self._highlightedSeedID:
            return
        if self._resolveSeedIndex(seedID) < 0:
            return
        self._previewSeedID = seedID
        set_preview_seed_id(self._displayNode, seedID)

    def _endHoverPreview(self) -> None:
        """Drop the preview; the pinned seed's stripes (if any) resume."""
        if not self._previewSeedID:
            return
        self._previewSeedID = ""
        set_highlight_seed_id(self._displayNode, self._highlightedSeedID or "")

    def _updateEmptyCarveCue(self, seedID: str | None) -> None:
        """Name an EMPTY carve on the highlighted seed row; hide other cues.

        Runs once per highlight change (never per stripe tick).  ``None`` /
        empty (highlight cleared) hides all cues.  Only a PRESENT-but-empty
        carve shows the message: an unknown carve (unbound seed, unreadable
        masks) stays cueless -- unknown is not empty.
        """
        for rowID, row in self._seed_rows.items():
            status = row.get("status")
            if status is not None and rowID != seedID:
                status.setVisible(False)
        if not seedID:
            return
        row = self._seed_rows.get(seedID)
        status = row.get("status") if row is not None else None
        if status is None:
            return
        index = self._resolveSeedIndex(seedID)
        empty = index >= 0 and self._carvedRegionIsEmpty(index)
        status.setText(EMPTY_CARVE_MESSAGE if empty else "")
        status.setVisible(bool(empty))

    def _carvedRegionIsEmpty(self, seedIndex: int) -> bool:
        """True iff the seed's carved region is PRESENT and empty.

        Re-derives the owner-minus-above fold (``carved_mask_for_seed``, the
        same fold the stripes pipeline renders) with every mask resampled onto
        the display node's pick-surface labelmap grid.  ``False`` when the
        carve is UNKNOWN -- no structure source / reference / binding -- so the
        cue never claims full coverage it cannot establish.
        """
        source = self._structureSource
        display = self._displayNode
        if source is None or display is None or not hasattr(display, "GetPickSurfaceNode"):
            return False
        reference = display.GetPickSurfaceNode()
        if reference is None:
            return False
        mask = carved_mask_for_seed(
            self._carrier, seedIndex, segment_mask_reader(source, reference)
        )
        return mask is not None and not mask.any()

    def _publishHighlight(self, seedID: str) -> None:
        """Point the highlight at ``seedID`` (the toggle/placement drivers).

        Publishes the stripes, names an empty carve on the row, and re-checks
        the toggles so exactly this seed's Highlight button reads on.  No
        visibility restore here -- that stays with the explicit toggle.
        """
        if not seedID:
            return
        self._previewSeedID = ""  # a pin change supersedes any hover preview
        self._highlightSeed(seedID)
        self._updateEmptyCarveCue(seedID)
        self._updateDivergenceChips()
        self._syncHighlightToggles()
        self._firePinChanged(seedID)

    def _retireHighlight(self) -> None:
        """Clear the highlight + its cue/chip and uncheck every Pin toggle."""
        self._clearHighlight()
        self._updateEmptyCarveCue(None)
        self._updateDivergenceChips()
        self._syncHighlightToggles()
        self._firePinChanged("")

    def stopHighlight(self) -> None:
        """Retire the highlight + stop the march timer (module-exit hygiene).

        Called by the module widget on ``exit()`` so no timer keeps firing --
        and no frozen stripes linger -- while LiverVolumetry is inactive.
        Also ends a restored context (the banner clears on module exit)
        WITHOUT touching the visibility the surgeon is looking at.  The pin
        PERSISTENCE callback is suppressed: exiting retires the live
        stripes, not the persisted pin ``enter()`` resumes from.
        """
        if self._restoredSeedID:
            self._endRestoredContext()
        self._suppressPinCallback = True
        try:
            self._retireHighlight()
        finally:
            self._suppressPinCallback = False

    def _syncHighlightToggles(self) -> None:
        """Check exactly the highlighted seed's toggle (exclusivity, silent).

        Signals are blocked so re-checking the buttons never re-enters
        ``_onHighlightToggled`` (a programmatic sync is not a driver).
        """
        for rowID, row in self._seed_rows.items():
            button = row.get("highlight")
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(bool(rowID) and rowID == self._highlightedSeedID)
            button.blockSignals(False)

    def _syncHighlightAfterRebuild(self) -> None:
        """Re-seat the highlight on the fresh rows after a rebuild.

        The rows (toggles + cue labels) are rebuilt from scratch, so a
        persisting highlight (a label edit / retarget / OTHER-seed deletion
        rebuild) gets its cue re-derived on the surviving row -- the pin is
        keyed by stable ID, so it stays pinned through index shifts.  A
        highlight whose OWN seed is gone (the ID no longer resolves) is
        retired.
        """
        if self._restoredSeedID and self._resolveSeedIndex(self._restoredSeedID) < 0:
            # The restored seed itself is gone: end the context (banner
            # clears) without touching the visibility the surgeon sees.
            self._endRestoredContext()
        # The rebuild replaced every row widget, so a hovered Pin button's
        # Leave may never arrive: drop any preview (the pin resumes).
        self._endHoverPreview()
        if not self._highlightedSeedID:
            return
        if self._resolveSeedIndex(self._highlightedSeedID) < 0:
            self._retireHighlight()
            return
        self._updateEmptyCarveCue(self._highlightedSeedID)
        self._updateDivergenceChips()
        self._syncHighlightToggles()
