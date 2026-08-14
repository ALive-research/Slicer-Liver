# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2023-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
#   * Neither the name of Oslo University Hospital nor the names
#     of Contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#   HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#   THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#   This file was originally developed by Ruoyan Meng (NTNU) through the
#   ALive project (grant nr. 311393).
#
# ==============================================================================

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern



import logging
import time

import vtk
import qt
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

# The seed carrier / display node the placement writes to (ADR-0038-amendment
# seeds-off-markups migration); the interaction state rides the display node via
# the shared PointPlacementState namespaced ``LiverVolumetry.*``
# (feedback_layerdm_state_on_display_node).
SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
SEEDS_DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"
SEEDS_STORAGE_NODE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"
VOLUMETRY_NAMESPACE = "LiverVolumetry"

# The module-owned results table (data-first redesign §3.3): auto-created on
# first Compute, shown via the ``showTable`` layout switch, and cleared +
# recomputed each run (no cross-run append).
RESULTS_TABLE_NAME = "Volumetry"
# The per-run partition total row's label (data-first redesign §3.5): a stable
# surgeon term, never the transient fiducial node's name.
PARTITION_TOTAL_LABEL = "All pieces"
# The "% of total" DENOMINATOR made explicit (territory-usability): every
# results run ends with a Total volume row naming what the percentages are
# measured against, its mL, and 100%.  The TICKED segments in the "Total
# volume segments" section define that total (the denominator); seeds/volumes
# are the measurement.  The denominator SEMANTICS are unchanged -- the
# rasterized tick selection (all segments when none is ticked) on the classic
# path, the whole segmentation on the per-volume path -- only its VISIBILITY
# changed.  The per-volume path derives its label from the segmentation's
# name ("Total volume (<segmentation name>)").
TOTAL_SELECTED_SEGMENTS_LABEL = "Total volume (ticked segments)"
# The generated leftover segment's NEUTRAL name (territory-usability §"pure
# neutral tools"): volumetry is a measuring instrument, not a resection
# planner, so the region no seed claimed is "Unassigned" -- never a
# resection-planning term.
UNSEEDED_SEGMENT_LABEL = "Unassigned"

# The placement requirements messages (territory-usability): placement is a
# per-volume row control, so the requirements line -- not a standalone Place
# button -- guides the surgeon to select a segmentation and add a volume first.
_NEEDS_SEGMENTATION_MESSAGE = "Select a segmentation."
_NEEDS_VOLUME_MESSAGE = "Add a volume to place seeds."


#
# LiverVolumetry
#

class LiverVolumetry(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Calculate Liver Volumetry"
    self.parent.categories = [""]
    self.parent.dependencies = []
    self.parent.contributors = ["Ruoyan Meng (NTNU)",
                                "Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Rafael Palomar (OUS)",
                                "Javier Pérez de Frutos (SINTEF)"]
    self.parent.helpText = """
    This module provides tools and functionality for calculating Liver Volumetry.
    """
    self.parent.acknowledgementText = """
    """  # TODO: replace with organization, grant and thanks.

    # Register the seed-carrier MRML node classes at module-discovery time
    # (ADR-0013 §5 call 1) so ``slicer.mrmlScene.AddNewNodeByClass(
    # "vtkMRMLVolumetrySeedsNode", ...)`` works from any test, batch-mode
    # script, or other module's setup callback -- not only after the widget is
    # first opened.  The generic ``vtkLiverVolumetryLogic`` is a plain
    # vtkObject with no scene observer (ADR-0015 keeps it unchanged), so the
    # registration lives here in Python, not in a C++ RegisterNodes.
    if not slicer.app.commandOptions().noMainWindow:
      slicer.app.connect("startupCompleted()", self._registerSeedNodeClasses)
    else:
      # ``--no-main-window`` skips Slicer's normal startup sequence so the
      # ``startupCompleted`` signal never fires; register immediately so
      # headless / test invocations still have the classes available.
      self._registerSeedNodeClasses()

    #Hide module, so that it only shows up in the Liver module, and not as a separate module
    parent.hidden = True

  def _registerSeedNodeClasses(self):
    """Register the seed carrier / display / storage node classes (ADR-0013 §5 call 1).

    Instantiates each wrapped C++ prototype and hands it to
    ``RegisterNodeClass`` so ``AddNewNodeByClass`` resolves it.  A launch
    without the module's MRML library on the path (the class import fails)
    degrades gracefully -- the placement feature is disabled that session.
    """
    try:
      from slicer import (
        vtkMRMLVolumetrySeedsNode,
        vtkMRMLVolumetrySeedsDisplayNode,
        vtkMRMLVolumetrySeedsStorageNode,
      )
    except ImportError as exc:
      logging.warning(
        "LiverVolumetry: seed MRML node classes unavailable (%s) -- seed "
        "placement is disabled this session.  This usually means the module "
        "MRML library failed to build or its Python wrapping is not on the "
        "launcher's --additional-module-paths.", exc)
      return
    scene = slicer.mrmlScene
    for cls in (vtkMRMLVolumetrySeedsNode,
                vtkMRMLVolumetrySeedsDisplayNode,
                vtkMRMLVolumetrySeedsStorageNode):
      scene.RegisterNodeClass(cls())


#
# Register sample data sets in Sample Data module
#
class LiverVolumetryWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    # The scene-resident seed carrier + its shared data-only display node
    # (ADR-0038-amendment): the arm state / carrier binding / pick-surface ride
    # the display node, and the LayerDM-driven placement Pipelines read them
    # back (feedback_layerdm_state_on_display_node).  Created lazily; dropped on
    # scene close.
    self._seedsCarrier = None
    self._seedsDisplayNode = None
    # The scene-resident labelmap the in-volume pick resolves interior voxels
    # against (rasterized from the selected input segment(s); the pick needs an
    # image-data node, not the segmentation).  Created lazily on arm; dropped on
    # scene close.  The key records which inputs the labelmap was exported
    # from -- (segmentation ID, segment selection, reference volume ID,
    # segmentation MTime) -- so re-arming with unchanged inputs reuses the
    # cached export instead of re-rasterizing the whole segmentation on the
    # GUI thread (arm must be instant on clinical-size data).
    self._pickLabelmap = None
    self._pickLabelmapKey = None
    # The carrier-backed seeds table (ADR-0038 §Conformance): one row per seed
    # with an editable label (the generated segment name), a colour swatch, and
    # a delete affordance.  Composed into the panel in ``setup`` and bound to
    # the carrier once it exists; dropped on scene close.
    self._seedsTable = None
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Register the LayerDM Pipeline creators (ADR-0013 §5 call 3): ONE 3D +
    # ONE slice pipeline for the seed display-node type, each wired to the flat
    # volumetry provider + the in-volume pick.  No custom displayable manager
    # (ADR-0013 §5 / feedback_layerdm_no_custom_dm).  Idempotent; guarded
    # against an unreachable LayerDMLib.
    self._registerSeedPlacementPipelines()

    # Load widget from .ui file (created by Qt Designer)
    liverVolumetryWidget = slicer.util.loadUI(self.resourcePath('UI/LiverVolumetryWidget.ui'))
    self.layout.addWidget(liverVolumetryWidget)
    # With the outer "Resection Volumetry" collapsible removed (data-first
    # §3.2 -- the Liver shell already headers the stage), the no-parameter-node
    # enable-gate moves onto the loaded panel root.
    self._panelWidget = liverVolumetryWidget

    # Add a spacer at the botton to keep the UI flowing from top to bottom
    spacerItem = qt.QSpacerItem(0,0, qt.QSizePolicy.Minimum, qt.QSizePolicy.MinimumExpanding)
    self.layout.addSpacerItem(spacerItem)

    self.ui = slicer.util.childWidgetVariables(liverVolumetryWidget)

    # The single input control: the segment selector widget owns BOTH the
    # segmentation-node choice (segmentationNodeSelectorVisible) and the
    # segment picker, matching Slicer's Segment-Editor input pattern.  The
    # standalone segmentation combo was removed to end the "which selector?"
    # ambiguity -- everything reads the segmentation off this one widget via
    # ``_inputSegmentationNode``.
    self.nodeSelectors = [
      (self.ui.InputSegmentSelectorWidget, "inputSegmentation")
    ]

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    liverVolumetryWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = LiverVolumetryLogic()
    self.setParameterNode(self.logic.getParameterNode())

    # Connections
    # The single input control drives the segmentation-node handlers: parameter
    # sync, the requirements re-gate, and the Show-3D binding.  The reference-
    # volume, total-volume, and output-table selectors were removed (data-first
    # redesign §3.3); their data now comes from the segmentation selection.
    # The selector's built-in "Segment(s):" caption reads as a generic picker;
    # in this panel the ticked segments DEFINE the total volume, so caption the
    # internal label accordingly (only setHorizontalLayout rewrites it, which
    # this panel never toggles after setup).
    segmentCaption = self.ui.InputSegmentSelectorWidget.findChild(qt.QLabel, "label_Segment")
    if segmentCaption is not None:
      segmentCaption.setText("Total volume: ")
    self.ui.InputSegmentSelectorWidget.connect('currentNodeChanged(vtkMRMLNode*)', self.onVolumetryParameterChanged)
    self.ui.InputSegmentSelectorWidget.connect('currentNodeChanged(bool)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentSelectorWidget.connect('currentNodeChanged(bool)', self.segmentationNodeSelected)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.updateParameterNodeFromGUI)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.onSegmentChanged)
    self.ui.InputSegmentSelectorWidget.connect('segmentSelectionChanged(QStringList)', self.onVolumetryParameterChanged)
    self.ui.ComputeVolumePushButton.connect('clicked(bool)', self.onComputeAdvancedVolumeButtonClicked)
    self.ui.GenerateSegmentsPushButton.connect('clicked(bool)', self.onGenerateSegmentsButtonClicked)
    self.ui.ResectionTargetNodeComboBox.connect('currentNodeChanged(vtkMRMLNode*)', self.onGenerateSegmentsParameterChanged)
    # The refine-by-resection message reads the CHECKED resections (data-first
    # redesign §3.4), so re-gate when the check state changes, not only the
    # current node.
    self.ui.ResectionTargetNodeComboBox.connect('checkedNodesChanged()', self.onGenerateSegmentsParameterChanged)
    # Refine-by-resection is an OPTIONAL sub-control (seeds-first-class model,
    # §3): toggling it enables the resection combo and re-gates so the refine
    # message appears/clears, but it NEVER blocks the plain seed path.
    self.ui.RefineByResectionCheckBox.connect('toggled(bool)', self.onRefineByResectionToggled)
    # ADR-0038-amendment: the ROIMarkersList fiducial selector + place widget
    # are RETIRED.  There is NO standalone Place-seeds toggle either
    # (territory-usability): placement arms from a VOLUME row's per-volume Place
    # toggle in the seeds table (mirroring VascularTerritories), driving the seed
    # carrier through the shared base pipeline into the ACTIVE volume.
    # D3 (critique §2): whole-group "Clear all seeds", the flat-list analogue of
    # the VascularTerritories per-territory Remove.  Clears the carrier through
    # its existing removal so the table + pipeline refresh via the carrier
    # ModifiedEvent observer.
    self.ui.ClearAllSeedsButton.connect('clicked(bool)', self.onClearAllSeeds)

    # Compose the segment show/hide list into the Total-volume-segments
    # section (ADR-0004: the panel is Python).  Visibility is the PRIMARY
    # region-composition instrument (the visibility-composed carve rule): the
    # surgeon shows/hides segments BEFORE placing, so the eye list must live in
    # the module -- composing visibility must not require leaving the panel.
    self._composeVisibilityList(liverVolumetryWidget)

    # Compose the carrier-backed seeds table into the panel (ADR-0004: the
    # panel is Python).  It is bound to the seed carrier lazily -- the carrier
    # is created on first placement -- so it starts empty and repaints on the
    # carrier's ModifiedEvent once bound.
    self._composeSeedsTable(liverVolumetryWidget)

    # D1 (critique §2): an always-visible affirmative requirements surface under
    # the action buttons (Python-composed, ADR-0004; legible a11y text,
    # ADR-0010), enumerating the UNMET preconditions live so a disabled action
    # always tells the surgeon what to do next.  Mirrors the VascularTerritories
    # ``_setupRequirementsLabel`` / ``_actionRequirements`` /
    # ``_updateRequirementsMessage`` idiom.
    #
    # SHARED-EXTRACTION SEAM: this helper trio is a verbatim structural copy of
    # the VascularTerritories requirements surface; a follow-up will hoist a
    # single shared requirements helper both modules (and the future unified
    # planning table) consume.  Do NOT couple to that shared module yet.
    self._setupRequirementsLabel()

    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    # Belt-and-braces sanitation on scene load: old scenes serialized the
    # attribute-borne highlight/phase channel onto the seed display node;
    # scrub it so a reload never renders frozen orphan stripes no widget
    # owns (the highlight now rides the transient HighlightSeedID member,
    # the TransientPoint rule).
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndImportEvent, self.onSceneEndImport)

    # Gate the workflow actions on their real preconditions from the start
    # (D1/D2): with no input segmentation the Place-seeds toggle is disabled and
    # every action reads its unmet list, so the panel self-explains on open.
    self._updateActionEnablement()

    self.initializeParameterNode()

  def _registerSeedPlacementPipelines(self):
    """Register the seed placement LayerDM Pipeline creators (ADR-0013 §5 call 3).

    ONE 3D + ONE slice creator for ``vtkMRMLVolumetrySeedsDisplayNode``, each
    returning the shared ``SurfacePointPlacementPipeline*`` base wired to the
    flat volumetry provider + the in-volume pick.  Idempotent; a missing
    LayerDMLib is a real configuration error under ADR-0002 so it logs at
    ``critical``, but the rest of widget setup continues.
    """
    try:
      from LiverVolumetryLib import (
        registerVolumetrySeedPipeline3DCreator,
        registerVolumetrySeedPipelineSliceCreator,
      )
      if registerVolumetrySeedPipeline3DCreator is None:
        raise ImportError("volumetry seed Pipeline creators unavailable")
      registerVolumetrySeedPipeline3DCreator()
      registerVolumetrySeedPipelineSliceCreator()
    except ImportError as exc:
      logging.critical(
        "LiverVolumetry: seed placement LayerDM Pipeline creators not "
        "registered (%s) -- seed placement is disabled in this session.  "
        "Loading the SlicerLayerDisplayableManager extension is required for "
        "the Pipeline path (ADR-0013/0038).", exc)

  def _composeVisibilityList(self, panelWidget):
    """Compose the segment show/hide eye list into the Total-volume-segments section.

    A ``qMRMLSegmentsTableView`` trimmed to NAME + VISIBILITY (the eye
    column) over the input segmentation -- the same instrument the
    Segmentations module offers, so show/hide reads familiarly.  The eye list
    is how the surgeon COMPOSES the region a seed measures (the
    visibility-composed carve rule): the visible layers carve each other, and
    a dropped seed snapshots exactly this composition.  Read-only names (the
    input is not edited here); bound to the current input by
    ``segmentationNodeSelected``.  Degrades gracefully when the widget class
    is unavailable (the panel simply omits the list).
    """
    self._visibilityList = None
    viewClass = getattr(slicer, "qMRMLSegmentsTableView", None)
    if viewClass is None:
      logging.warning(
        "LiverVolumetry: qMRMLSegmentsTableView unavailable -- the segment "
        "show/hide list is omitted this session.")
      return
    view = viewClass()
    view.setMRMLScene(slicer.mrmlScene)
    # Name + eye only: the list is a visibility instrument, not an editor.
    view.visibilityColumnVisible = True
    view.colorColumnVisible = False
    view.opacityColumnVisible = False
    view.statusColumnVisible = False
    view.headerVisible = False
    view.filterBarVisible = False
    view.readOnly = True
    view.setToolTip(
      "Show/hide list (the carve instrument): show or hide segments to "
      "compose the region a seed measures -- the top visible segment owns "
      "each voxel and carves the ones below; a placed seed remembers this "
      "composition. Separate from the total-volume ticks above, which only "
      "define the percentage denominator.")
    self._visibilityList = view
    grid = self.ui.VisibilityGroupWidget.layout() if hasattr(self.ui, "VisibilityGroupWidget") else None
    if grid is not None and hasattr(grid, "addWidget"):
      grid.addWidget(view, 0, 0)
    else:
      panelWidget.layout().addWidget(view)

  def _bindVisibilityList(self, segmentationNode):
    """Point the show/hide eye list at the current input segmentation."""
    view = getattr(self, "_visibilityList", None)
    if view is None:
      return
    view.setSegmentationNode(segmentationNode)

  def _composeSeedsTable(self, panelWidget):
    """Compose the carrier-backed seeds table into the partition group (ADR-0004).

    Placed in the ``SeedsGroupWidget`` container inside the partition group,
    between the Place/Clear row and the hint -- the seed list belongs with the
    seed controls (data-first redesign §3.2).  A missing widget class (a launch
    without the Lib on the path) degrades gracefully -- the panel simply omits
    the table.
    """
    # The package guards the widget import (Qt/ctk unreachable bare), exposing
    # ``None`` when the class could not be built -- degrade to no table.
    from LiverVolumetryLib import VolumetrySeedsTableWidget
    if VolumetrySeedsTableWidget is None:
      logging.warning(
        "LiverVolumetry: VolumetrySeedsTableWidget unavailable -- the seeds "
        "table is omitted this session.")
      return
    self._seedsTable = VolumetrySeedsTableWidget(carrier=None)
    grid = self.ui.SeedsGroupWidget.layout()
    if grid is not None and hasattr(grid, "addWidget"):
      grid.addWidget(self._seedsTable, 0, 0)
    else:
      panelWidget.layout().addWidget(self._seedsTable)

  def _bindSeedsTable(self, carrier):
    """Rebind the seeds table over ``carrier`` (drops the prior observer).

    Re-parents nothing -- only the carrier binding changes -- so the future
    unified planning table can adopt the same rebind seam.
    """
    if self._seedsTable is not None:
      self._seedsTable.setCarrier(carrier)
      self._bindSeedsTableStructureSource()

  def _bindSeedsTableStructureSource(self):
    """Point the seeds table's retarget menu at the input segmentation.

    The table's Target column recomputes the touched candidates against this
    segmentation (the seed→label capture source), so keep it in step with the
    input selection.  A missing table / seam degrades gracefully.
    """
    if self._seedsTable is None or not hasattr(self._seedsTable, "setStructureSource"):
      return
    self._seedsTable.setStructureSource(self._inputSegmentationNode())

  def _setupRequirementsLabel(self):
    """Tag the always-visible action-requirements status line (ADR-0004).

    The wrapping ``qt.QLabel`` lives in the ``.ui`` (``VolumetryRequirementsLabel``)
    under the action buttons; ``_updateRequirementsMessage`` fills it with the
    live unmet-precondition list.  Legible plain text (ADR-0010) -- never colour
    alone.  Degrades gracefully (no label) if the panel omitted it.

    SHARED-EXTRACTION SEAM: a verbatim structural copy of
    ``VascularTerritoriesWidget._setupRequirementsLabel``; a follow-up hoists a
    shared helper both modules consume.
    """
    label = getattr(self.ui, "VolumetryRequirementsLabel", None)
    if label is not None and hasattr(label, "setWordWrap"):
      label.setWordWrap(True)
    self._requirementsLabel = label

  def _inputSegmentationNode(self):
    """The selected input segmentation, read off the single input control.

    The consolidated ``InputSegmentSelectorWidget`` owns the segmentation-node
    choice (segmentationNodeSelectorVisible); returns a
    ``vtkMRMLSegmentationNode`` or ``None``.
    """
    return self.ui.InputSegmentSelectorWidget.currentNode()

  def _seedCount(self):
    """The number of placed seeds on the carrier (0 when no carrier yet)."""
    carrier = self._seedsCarrier
    if carrier is None or not slicer.mrmlScene.IsNodePresent(carrier):
      return 0
    return carrier.GetNumberOfSeeds()

  def _hasGroupedVolumes(self, carrier):
    """True iff any seed on ``carrier`` is bound within a named volume.

    Gates the compute-per-volume path: only when the surgeon has actually
    grouped a bound seed into a volume does Compute reshape into per-volume rows
    (territory-usability).  A flat / ungrouped seed set keeps the legacy
    per-seed compute, so the seeds-first-class semantics are unchanged.
    """
    if carrier is None or not slicer.mrmlScene.IsNodePresent(carrier):
      return False
    if not hasattr(carrier, "GetVolumeIds"):
      return False
    from LiverVolumetryLib import distinct_bound_segments_per_volume
    return bool(distinct_bound_segments_per_volume(carrier))

  def _hasVolume(self):
    """True iff at least one named volume exists on the carrier (or its table).

    Placement arms into a volume (territory-usability), so "no volume" means
    there is nowhere to place: the requirements line asks the surgeon to add
    one.  Reads the table's live volume order (which includes an empty minted
    volume before any seed lands) with a fall-back to the carrier's enumerated
    volume ids, so a volume added outside the table still counts.
    """
    table = self._seedsTable
    if table is not None and hasattr(table, "volumeIds") and table.volumeIds():
      return True
    carrier = self._seedsCarrier
    if carrier is None or not slicer.mrmlScene.IsNodePresent(carrier):
      return False
    if not hasattr(carrier, "GetVolumeIds"):
      return False
    return bool(list(carrier.GetVolumeIds()))

  def _hasCheckedResection(self):
    """True iff at least one resection is checked in the resection combo."""
    return not self.ui.ResectionTargetNodeComboBox.noneChecked()

  def _refineByResection(self):
    """True iff the optional Refine-by-resection sub-control is enabled."""
    return self.ui.RefineByResectionCheckBox.checked

  def _hasTickedSegment(self):
    """True iff at least one segment is ticked on the input selector.

    A ticked segment is one PEER way to say "measure this" (logic B1); the
    other is a placed seed (logic B2).  "Nothing ticked and no seed" is
    not-yet-ready for Compute -- the user has not said what to measure.
    """
    return len(self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()) > 0

  def _actionRequirements(self):
    """The UNMET preconditions for Place / Compute / Generate / Refine.

    Reads the SAME live state the enablement gates read (D1) so the messaging
    and the enablement cannot diverge -- the enablement is simply "the list is
    empty".  Each entry is a short, actionable, platform-neutral instruction
    (ADR-0010 legible text).

    Returns ``(placeUnmet, computeUnmet, generateUnmet, refineUnmet)`` -- lists
    of human-readable strings; an empty list means the action can run / the
    refinement has effect.

    Seeds are a FIRST-CLASS input (seeds-first-class model, §1/§3): a placed
    seed measures the whole region it sits in (logic B2), so a seed alone --
    with NO resection -- satisfies Compute and Generate.  Resections are an
    OPTIONAL refinement that never blocks the plain seed path.

    SHARED-EXTRACTION SEAM: mirrors ``VascularTerritoriesWidget._actionRequirements``.
    """
    hasSegmentation = self._inputSegmentationNode() is not None
    hasResection = self._hasCheckedResection()
    hasSeeds = self._seedCount() > 0
    hasTicked = self._hasTickedSegment()
    hasVolume = self._hasVolume()

    # Place seeds: placement is a per-volume row control (no standalone Place
    # toggle, territory-usability), so the requirements are (1) a segmentation
    # -- the in-volume pick needs a target region's labelmap, else arming would
    # accept clicks that never land a seed (data-first §3.4) -- and (2) a volume
    # to place into (the Place toggle lives on a volume row; with no volume
    # there is nowhere to arm).  Feeds the requirements line + the volume
    # table's own affordance, not a global button.
    placeUnmet = []
    if not hasSegmentation:
      placeUnmet.append(_NEEDS_SEGMENTATION_MESSAGE)
    elif not hasVolume:
      placeUnmet.append(_NEEDS_VOLUME_MESSAGE)

    # Compute volumes: a segmentation is selected AND the user has said WHAT to
    # measure -- either ticked >=1 segment (B1) OR placed >=1 seed (B2).  The
    # two are peers; neither requires a resection (data-first §3.4).
    computeUnmet = []
    if not (hasSegmentation and (hasTicked or hasSeeds)):
      computeUnmet.append(
        "Select a segmentation, then tick segments or place seeds.")

    # Generate segments materialises the SEEDED regions as a Segmentation, so
    # it needs >=1 seed placed; resections are an optional barrier, never a
    # precondition (seeds-first-class model, §1/§3).
    generateUnmet = []
    if not hasSeeds:
      generateUnmet.append("Place at least one seed.")

    # Refine-by-resection is purely optional: it NEVER blocks Compute.  When ON
    # it wants >=1 resection checked to have effect; the message tells the
    # surgeon so, but the plain seed path still runs regardless.
    refineUnmet = []
    if self._refineByResection() and not hasResection:
      refineUnmet.append("Check a resection to bound the seed regions.")

    return placeUnmet, computeUnmet, generateUnmet, refineUnmet

  def _updateActionEnablement(self):
    """Gate Place / Compute / Generate / Clear on their REAL preconditions (D1/D2).

    Both actions read LIVE state through ``_actionRequirements`` so a surgeon
    cannot arm placement or click an action that cannot yet run, and the
    always-visible requirements line + the button tooltips enumerate what is
    missing (an empty unmet list == the action can run).  Re-evaluated on every
    parameter change, on the carrier ModifiedEvent (seeds add/delete), and after
    clear-all.
    """
    placeUnmet, computeUnmet, generateUnmet, refineUnmet = self._actionRequirements()

    # No standalone Place button (territory-usability): placement is a
    # per-volume row control, so ``placeUnmet`` feeds only the requirements line
    # + tooltips, not a global button gate.
    self.ui.ComputeVolumePushButton.setEnabled(not computeUnmet)
    self.ui.GenerateSegmentsPushButton.setEnabled(not generateUnmet)
    # Generate segments is shown only once seeds exist (§3.2): materialising a
    # partition is meaningless without a seed, so hide the affordance until the
    # surgeon has placed one.  Clear-all is enabled on the same condition
    # (critique D3: something to clear).
    hasSeeds = self._seedCount() > 0
    self.ui.GenerateSegmentsPushButton.setVisible(hasSeeds)
    self.ui.ClearAllSeedsButton.setEnabled(hasSeeds)

    self._updateRequirementsMessage(placeUnmet, computeUnmet, generateUnmet, refineUnmet)

  def _updateRequirementsMessage(self, placeUnmet, computeUnmet, generateUnmet, refineUnmet):
    """Surface the unmet preconditions on the status line + the button tooltips.

    An always-visible label under the buttons enumerates what is missing for
    each action, and each button carries its own per-action unmet list as a
    tooltip (D1; ADR-0004 Python-composed, ADR-0010 legible a11y text).

    SHARED-EXTRACTION SEAM: mirrors ``VascularTerritoriesWidget._updateRequirementsMessage``.
    """
    # Each unmet entry is already a full, punctuated instruction (data-first
    # §3.4), so the tips + status line present them verbatim -- no extra prefix
    # or trailing period.  There is no standalone Place button, so ``placeUnmet``
    # surfaces only on the status line (below), not a button tooltip.
    computeTip = (
      "Compute volumes is ready." if not computeUnmet
      else "Compute volumes needs:\n- " + "\n- ".join(computeUnmet))
    generateTip = (
      "Generate segments is ready." if not generateUnmet
      else "Generate segments needs:\n- " + "\n- ".join(generateUnmet))
    self.ui.ComputeVolumePushButton.setToolTip(computeTip)
    self.ui.GenerateSegmentsPushButton.setToolTip(generateTip)

    label = getattr(self, "_requirementsLabel", None)
    if label is None:
      return
    if not computeUnmet and not refineUnmet:
      label.setText("All requirements met -- compute volumes.")
      return
    # The Compute input requirement leads; the placement requirement (no
    # standalone Place button -- placement is a per-volume row control) guides
    # the surgeon to add a volume when a segmentation is selected but no volume
    # exists yet; the optional refine requirement is only shown when
    # Refine-by-resection is on but no resection is checked (it never blocks
    # Compute -- it only tells the surgeon the refinement has no effect yet).
    lines = []
    if computeUnmet:
      lines.extend(computeUnmet)
    # Surface the "Add a volume to place seeds" guidance only once the
    # segmentation precondition is met (otherwise "Select a segmentation" from
    # Compute already leads, and placement's own "Select a segmentation" would
    # duplicate it).
    if placeUnmet and placeUnmet != [_NEEDS_SEGMENTATION_MESSAGE]:
      lines.extend(placeUnmet)
    if refineUnmet:
      lines.extend(refineUnmet)
    label.setText("\n".join(lines))

  def onClearAllSeeds(self):
    """Remove every seed from the carrier (D3: whole-group clear).

    The flat-list analogue of the VascularTerritories per-territory Remove.
    Routes through the carrier's existing ``RemoveNthSeed`` (the same removal
    the per-row Delete uses) from the top down, so the table + placement
    pipeline refresh via the carrier ModifiedEvent observer.  No confirmation
    modal (critique OQ3): re-placement is the recovery path.  Disabled when
    there are no seeds, so this is a no-op on an empty carrier.
    """
    carrier = self._seedsCarrier
    if carrier is None or not slicer.mrmlScene.IsNodePresent(carrier):
      return
    for index in range(carrier.GetNumberOfSeeds() - 1, -1, -1):
      carrier.RemoveNthSeed(index)
    self._updateActionEnablement()

  # ------------------------------------------------------------------ #
  # Seed carrier + placement arming (ADR-0038-amendment)
  # ------------------------------------------------------------------ #

  def _ensureSeedsCarrier(self):
    """Return the scene-resident seed carrier, creating it once.

    ``None`` when the C++ node class is unavailable (a launch without the
    module's MRML library on the path) -- the caller degrades gracefully.
    """
    node = self._seedsCarrier
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.AddNewNodeByClass(SEEDS_NODE_CLASS, "Volumetry Seeds")
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      node = None
    if node is None:
      logging.warning(
        "LiverVolumetry: %s unavailable -- seed placement disabled this "
        "session.", SEEDS_NODE_CLASS)
      return None
    self._seedsCarrier = node
    # Bind the freshly-created carrier into the panel's seeds table so labels /
    # colours / deletes edit the same carrier the placement writes to.
    self._bindSeedsTable(node)
    # Re-gate the actions whenever the carrier changes (a seed placed via the
    # pipeline, deleted per-row, or cleared): Generate + Clear-all read the live
    # seed count, and the requirements surface must track it (D1/D3).  Removed in
    # cleanup / on scene close.
    if not self.hasObserver(node, vtk.vtkCommand.ModifiedEvent, self._onSeedsCarrierModified):
      self.addObserver(node, vtk.vtkCommand.ModifiedEvent, self._onSeedsCarrierModified)
    return node

  def _onSeedsCarrierModified(self, caller, event):
    """Re-gate actions on a carrier edit (seed placed / deleted / cleared)."""
    del caller, event
    self._updateActionEnablement()

  def _ensureSeedsDisplayNode(self):
    """Return the scene-resident seed display node, creating + binding it once.

    Configures the carrier binding + the pick surface BEFORE AddNode: LayerDM
    consults the Pipeline creators the moment the node enters the scene, and
    each created Pipeline resolves the carrier + labelmap at creation -- so the
    carrier reference (and the pickSurface) must already be on the node
    (the configure-before-AddNode LayerDM discipline).
    """
    node = self._seedsDisplayNode
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      return node
    try:
      node = slicer.mrmlScene.CreateNodeByClass(SEEDS_DISPLAY_NODE_CLASS)
    except Exception:  # noqa: BLE001 - node class not registered in this launch
      node = None
    if node is None:
      logging.warning(
        "LiverVolumetry: %s unavailable -- seed placement disabled this "
        "session.", SEEDS_DISPLAY_NODE_CLASS)
      return None
    node.UnRegister(None)
    node.SetName("Volumetry Seeds Display")
    node.SetVisibility(True)
    carrier = self._ensureSeedsCarrier()
    if carrier is not None:
      from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
      PointPlacementState(VOLUMETRY_NAMESPACE).set_carrier(node, carrier)
    self._aimPickSurface(node)
    self._aimStructureSource(node)
    node = slicer.mrmlScene.AddNode(node)
    self._seedsDisplayNode = node
    # Give the per-volume seeds table the shared display node so its per-volume
    # Place toggle publishes the active volume + armed flag onto it (the same
    # channel the slice placement pipeline reads at placement time).
    if self._seedsTable is not None and hasattr(self._seedsTable, "setDisplayNode"):
      self._seedsTable.setDisplayNode(node)
    return node

  def _aimStructureSource(self, displayNode):
    """Reference the input segmentation as the seed→label capture source.

    The seed→label capture (``territory-usability`` §"Seed→label capture")
    resolves the touched candidates by reading each visible segment's binary
    labelmap + layer index at the clicked voxel, so it needs the SEGMENTATION
    node -- not the rasterized pick labelmap.  ``None`` clears the reference
    when there is no input.
    """
    if displayNode is None or not hasattr(displayNode, "SetAndObserveStructureSourceNodeID"):
      return
    segmentation = self._inputSegmentationNode()
    displayNode.SetAndObserveStructureSourceNodeID(
      segmentation.GetID() if segmentation is not None else None)

  def _aimPickSurface(self, displayNode):
    """Aim the seed display node's pickSurface at the target region's labelmap.

    The in-volume pick (``InVolumePick``) resolves interior voxels by reading
    the pickSurface node's ``GetImageData`` / RAS<->IJK matrices, so the
    pickSurface must be a ``vtkMRMLLabelMapVolumeNode`` -- NOT the input
    ``vtkMRMLSegmentationNode``, which carries no image-data / IJK API (a
    segmentation node makes the pick raise and decline every click).  So we
    rasterize the selected input segment(s) into a scene-resident labelmap
    (the same ``ExportSegmentsToLabelmapNode`` the compute path uses) and aim
    the pick at that.  ``None`` clears the reference when there is no input.
    """
    if displayNode is None or not hasattr(displayNode, "SetAndObservePickSurfaceNodeID"):
      return
    labelmap = self._ensurePickLabelmap()
    displayNode.SetAndObservePickSurfaceNodeID(
      labelmap.GetID() if labelmap is not None else None)

  def _ensurePickLabelmap(self):
    """Rasterize the selected input segment(s) into the pick labelmap, cached.

    The in-volume pick needs a labelmap of the CURRENT target region, but the
    export (``ExportSegmentsToLabelmapNode``) rasterizes the whole segmentation
    synchronously on the GUI thread -- on clinical-size data that reads as a
    frozen application.  So the export runs ONLY when its inputs changed: the
    result is cached keyed on (segmentation ID, segment selection, segmentation
    MTime), and re-arming with unchanged inputs reuses it (arm must be
    instant).  Reuses one owned ``vtkMRMLLabelMapVolumeNode`` so re-arming does
    not litter the scene.  Returns ``None`` (and leaves no labelmap) when there
    is no input segmentation, so the caller clears the pickSurface reference.
    """
    segmentation = self._inputSegmentationNode()
    if segmentation is None or not segmentation.IsA("vtkMRMLSegmentationNode"):
      self._pickLabelmapKey = None
      return None
    segmentIDs = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    inputsKey = (
      segmentation.GetID(),
      tuple(segmentIDs),
    )

    labelmap = self._pickLabelmap
    labelmapValid = (
      labelmap is not None
      and slicer.mrmlScene.IsNodePresent(labelmap)
      and labelmap.GetImageData() is not None)
    if labelmapValid and self._pickLabelmapKey == inputsKey + (segmentation.GetMTime(),):
      return labelmap

    if labelmap is None or not slicer.mrmlScene.IsNodePresent(labelmap):
      labelmap = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLabelMapVolumeNode", "Volumetry Seed Pick Labelmap")
      # Hidden from the subject hierarchy: an internal pick target, not a
      # user-facing result (ADR-0009 -- no clutter in the node lists).
      labelmap.SetHideFromEditors(True)
      self._pickLabelmap = labelmap
    # An empty selection means "all segments" for the export; a null reference
    # volume lets the segmentation's own geometry drive the rasterization
    # (data-first §3.3 -- the reference-volume input was removed).
    started = time.monotonic()
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
      segmentation, segmentIDs, labelmap, None)
    logging.debug(
      "LiverVolumetry: pick labelmap export took %.2f s", time.monotonic() - started)
    if labelmap.GetImageData() is None:
      self._pickLabelmapKey = None
      return None
    # Key the cache on the POST-export segmentation MTime: the export itself
    # may create the binary-labelmap representation (bumping the MTime), and
    # that conversion must not read as "inputs changed" on the next arm.
    self._pickLabelmapKey = inputsKey + (segmentation.GetMTime(),)
    return labelmap

  def _prepareSeedPlacement(self):
    """Ensure the shared display node exists + is aimed for per-volume placement.

    Placement is armed from a VOLUME row's Place toggle (territory-usability),
    which publishes the active volume + armed flag onto the shared display node
    via the base ``PointPlacementState``.  So the display node must exist and
    carry an aimed pick surface / structure source BEFORE a volume row can arm.
    Called when a segmentation is selected (the placement precondition) and
    opens the module-active add-on-click gate so an armed click lands only while
    LiverVolumetry is active.
    """
    node = self._ensureSeedsDisplayNode()
    if node is None:
      return
    # Re-aim at the current input (a cache hit when unchanged, so this stays
    # instant); ``_ensureSeedsDisplayNode`` aimed once at creation, but a
    # re-selection changes the target region.
    self._aimPickSurface(node)
    self._aimStructureSource(node)
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
    PointPlacementState(VOLUMETRY_NAMESPACE).set_module_active(node, True)

  def onGenerateSegmentsParameterChanged(self):
    # Re-gate all actions on their live preconditions + refresh the requirements
    # surface: the refine message reads the checked resection(s), and Generate
    # reads the seed count.
    self._updateActionEnablement()

  def onRefineByResectionToggled(self, refine):
    """Enable/disable the resection combo with the optional refine sub-control.

    Refine-by-resection is off by default (seeds-first-class model, §3): the
    resection combo is only interactive while refine is on.  Re-gates so the
    refine message appears/clears, but Compute is NEVER blocked by this
    toggle (the plain seed path always runs).
    """
    self.ui.ResectionLabel.setEnabled(bool(refine))
    self.ui.ResectionTargetNodeComboBox.setEnabled(bool(refine))
    self._updateActionEnablement()

  def _exportSelectedSegments(self, name):
    """Rasterize the selected input segment(s) into a scratch labelmap.

    The segmentation's own geometry drives the rasterization (a null reference
    volume is legal everywhere -- data-first §3.3); an empty selection means
    "all segments".  Returns the scene-resident scratch node the caller
    removes.
    """
    segmentsVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", name)
    segmentationNode = self._inputSegmentationNode()
    segmentationIds = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
      segmentationNode, segmentationIds, segmentsVolumeNode, None)
    return segmentsVolumeNode

  def onGenerateSegmentsButtonClicked(self):
    resectionNodes = self.getResectionNodes()
    seedsCarrier = self._ensureSeedsCarrier()
    segmentsVolumeNode = self._exportSelectedSegments("segmentVolumeNode")
    try:
      self.logic.generateSegments(resectionNodes, seedsCarrier, segmentsVolumeNode)
    finally:
      slicer.mrmlScene.RemoveNode(segmentsVolumeNode)

  def onVolumetryParameterChanged(self):
    # Re-gate all actions on their live preconditions + refresh the requirements
    # surface: Compute needs a segmentation (an empty segment selection means
    # all segments).
    self._updateActionEnablement()

  def getResectionNodes(self):
    """The Bezier barrier surfaces, ONLY when Refine-by-resection is on (B3).

    Resections are an optional refinement (seeds-first-class model, §1/§3):
    without the refine toggle on, the compute runs the plain seed path (B2 --
    each seed measures the whole region it sits in), so the resections must
    NOT be fed.  Returns ``None`` when refine is off or nothing is checked, so
    ``computeVolume`` takes the no-barrier branch.
    """
    if not self._refineByResection():
      return None
    resectionNodes = vtk.vtkCollection()
    if not self.ui.ResectionTargetNodeComboBox.noneChecked():
      checkedNodes = self.ui.ResectionTargetNodeComboBox.checkedNodes()
      for i in checkedNodes:
        # The checked nodes are now vtkMRMLResectionPlanNode wrappers; their
        # parametric geometry carrier (vtkMRMLBezierSurfaceNode) is the
        # boundary surface used for the volume computation
        # (ADR-0014 wrapper-vs-carrier split).
        bs = i.GetGeometryNode()
        if bs is None:
          continue
        resectionNodes.AddItem(bs)
    else:
      resectionNodes = None
    return resectionNodes

  def onComputeAdvancedVolumeButtonClicked(self):
    """
    This function is for compute volume
    """
    # The wait cursor is wrapped in try/finally so no failure path (a missing
    # image, an empty selection) leaves the cursor stuck (data-first §3.4).
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)

    segmentsVolumeNode = None
    try:
      resectionNodes = self.getResectionNodes()
      # Rasterize the selected input segment(s) once; it feeds both the region
      # measurement AND -- as its own denominator -- the "% of total" column
      # (the % is measured against the selection, data-first §3.3 OQ3).
      segmentsVolumeNode = self._exportSelectedSegments("segmentVolumeNode")
      seedsCarrier = self._ensureSeedsCarrier()
      # The module owns the results table (data-first §3.3): auto-created on
      # first Compute and CLEARED each run so denominators never mix across
      # runs (S8).  A guarded compute path (below) never throws on an
      # empty/missing table -- the old un-gated None raised ValueError.
      outputTable = self._ensureResultsTable()

      # territory-usability compute-per-volume: when the surgeon has grouped
      # seeds into named volumes, report ONE row per volume = the union of the
      # volume's DISTINCT bound segments' regions.  Otherwise fall back to the
      # per-seed / per-segment compute (the seeds-first-class + optional-resection
      # gating is unchanged; grouping only reshapes the rows).
      if resectionNodes is None and self._hasGroupedVolumes(seedsCarrier):
        self.logic.computeVolumePerVolume(
          self._inputSegmentationNode(), seedsCarrier, outputTable)
      else:
        self.logic.computeVolume(
          segmentsVolumeNode, segmentsVolumeNode, self._inputSegmentationNode(),
          outputTable, seedsCarrier, resectionNodes)

      # The wait cursor is the in-progress feedback; the populated volumetry
      # table is the result, so no blocking completion dialog is shown
      # (non-blocking feedback, ADR-0009 UX discipline).
      self.showTable(outputTable)
    finally:
      if segmentsVolumeNode is not None:
        slicer.mrmlScene.RemoveNode(segmentsVolumeNode)
      qt.QApplication.restoreOverrideCursor()

  def _ensureResultsTable(self):
    """Return the module-owned results table, cleared for a fresh run (§3.3).

    Auto-created on first Compute and named ``Volumetry``; each run REMOVES the
    prior columns so a recompute replaces, never appends across runs (S8 --
    mixed denominators).  Reuses the one owned node so recomputing does not
    litter the scene.
    """
    table = slicer.mrmlScene.GetFirstNodeByName(RESULTS_TABLE_NAME)
    if table is None or not table.IsA("vtkMRMLTableNode"):
      table = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", RESULTS_TABLE_NAME)
    else:
      table.RemoveAllColumns()
    return table

  def showTable(self, table):
    """
    Switch to a layout where tables are visible and show the selected table
    """
    # Guard a missing table so the compute path never throws on an empty
    # result (data-first §3.4 -- the old un-gated None raised).
    if table is None or not slicer.mrmlScene.IsNodePresent(table):
      return
    currentLayout = slicer.app.layoutManager().layout
    layoutWithTable = slicer.modules.tables.logic().GetLayoutWithTable(currentLayout)
    slicer.app.layoutManager().setLayout(layoutWithTable)
    slicer.app.applicationLogic().GetSelectionNode().SetActiveTableID(table.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()

  def segmentationNodeSelected(self):
    """Bind Show-3D to the selected segmentation and make the input visible.

    Show-3D (``qMRMLSegmentationShow3DButton``) builds the closed-surface
    representation of the segmentation's VISIBLE segments -- so if we hid every
    segment on selection (the prior behaviour), Show-3D created the surface but
    nothing rendered ("Show 3D shows nothing").  Instead we make the SELECTED
    segment(s) visible (falling back to ALL segments when none is specifically
    picked), matching Slicer's own Show-3D behaviour: the button always has
    something to render.
    """
    self.ui.SegmentationShow3DButton.setEnabled(True)
    segmentationNode = self._inputSegmentationNode()

    if segmentationNode is None:
      logging.warning('No segmentationNode')
      return

    self.ui.SegmentationShow3DButton.setSegmentationNode(segmentationNode)
    # Bind the show/hide eye list (the visibility-composition instrument) to
    # the same input the seeds capture against.
    self._bindVisibilityList(segmentationNode)
    self._applyInputSegmentVisibility(segmentationNode)
    # Keep the seeds-table retarget menu pointed at the current input.
    self._bindSeedsTableStructureSource()
    # Placement is per-volume now (no standalone Place toggle): a segmentation
    # is the placement precondition, so ensure the shared display node exists +
    # its pick surface / structure source are aimed at the current input the
    # moment a segmentation is selected.  This also hands the display node to
    # the seeds table so a volume row's Place toggle can arm.
    self._prepareSeedPlacement()

  def onSegmentChanged(self):
    segmentationNode = self._inputSegmentationNode()
    if segmentationNode is None:
      return
    self._applyInputSegmentVisibility(segmentationNode)
    # Re-aim the pick surface + seed→label capture at the new segment selection
    # so a per-volume Place arms against the current input (the standalone
    # toggle used to re-aim on arm; there is no such toggle now).
    node = getattr(self, "_seedsDisplayNode", None)
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      self._aimPickSurface(node)
      self._aimStructureSource(node)

  def _applyInputSegmentVisibility(self, segmentationNode):
    """Show the selected input segment(s); fall back to ALL when none picked.

    The Show-3D precondition: at least one segment must be visible or the
    closed-surface build renders nothing.  Selected segments are shown and the
    rest hidden; an empty selection shows every segment so the user always sees
    the input region.
    """
    displayNode = segmentationNode.GetDisplayNode()
    if displayNode is None:
      return
    segmentIDs = self.ui.InputSegmentSelectorWidget.segmentIDs()
    selectedIDs = self.ui.InputSegmentSelectorWidget.selectedSegmentIDs()
    # No specific selection == show the whole segmentation (Show-3D needs a
    # visible surface to build).
    visibleIDs = set(selectedIDs) if selectedIDs else set(segmentIDs)
    for id in segmentIDs:
      displayNode.SetSegmentVisibility(id, id in visibleIDs)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
     """
    # Tear down the seeds table's carrier observer so the parentless widget
    # does not survive to app shutdown holding a MRML observer
    # (feedback_launched_widget_teardown_crash).
    if self._seedsTable is not None:
      self._seedsTable.cleanup()
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Open the module-active add-on-click gate (ADR-0038): the LayerDM-created
    # placement Pipelines read this off the shared display node, so an armed
    # click only lands while LiverVolumetry is active.  Entering auto-arms
    # NOTHING -- placement is the explicit Add-seeds toggle.
    self._setModuleActive(True)
    # Scrub any legacy attribute-borne highlight state a loaded scene may
    # carry (belt-and-braces alongside the EndImportEvent sanitation).
    self._sanitizeLegacyHighlightAttributes()
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Retire the stripe highlight + stop its march timer on the way out
    # (timer lifecycle rides module enter/exit): a background module must not
    # keep a 25 Hz timer firing, nor leave frozen stripes on the slices.
    if self._seedsTable is not None and hasattr(self._seedsTable, "stopHighlight"):
      self._seedsTable.stopHighlight()
    # Disarm placement + close the module-active gate on the way out so no view
    # claims an add-on-click while LiverVolumetry is inactive (ADR-0038).  The
    # per-volume Place toggles read the armed flag off this display node, so
    # clearing it disarms them; the table repaints from the shared state (no
    # standalone Place button to un-check anymore, territory-usability).
    node = getattr(self, "_seedsDisplayNode", None)
    if node is not None and slicer.mrmlScene.IsNodePresent(node):
      from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
      state = PointPlacementState(VOLUMETRY_NAMESPACE)
      state.set_armed(node, False)
      state.set_module_active(node, False)
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def _setModuleActive(self, active):
    """Open/close the shared display node's module-active add-on-click gate."""
    node = getattr(self, "_seedsDisplayNode", None)
    if node is None or not slicer.mrmlScene.IsNodePresent(node):
      return
    from SlicerLiverInteractionLib.PointPlacementState import PointPlacementState
    PointPlacementState(VOLUMETRY_NAMESPACE).set_module_active(node, bool(active))

  def onSceneEndImport(self, caller, event):
    """Scrub legacy attribute-borne highlight state off loaded seed display nodes."""
    del caller, event
    self._sanitizeLegacyHighlightAttributes()

  def _sanitizeLegacyHighlightAttributes(self):
    """Remove the retired highlight/phase ATTRIBUTES from every seed display node.

    Old scenes serialized the highlight/phase channel as node attributes
    (``SetAttribute`` values persist into the scene XML); reloading such a
    scene rendered frozen orphan stripes no widget owned.  The live
    highlight now rides the display node's transient
    ``HighlightSeedID`` member, so any surviving attribute is stale by
    definition and is dropped wholesale.
    """
    try:
      from LiverVolumetryLib import clear_legacy_highlight_attributes
    except ImportError:
      return
    for node in slicer.util.getNodesByClass(SEEDS_DISPLAY_NODE_CLASS):
      clear_legacy_highlight_attributes(node)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # The seed carrier + display node were cleared with the scene; drop the
    # stale handles so the next placement re-creates fresh ones.  Detach the
    # carrier observer first so it does not reference a scene-cleared node.
    if self._seedsCarrier is not None and self.hasObserver(
        self._seedsCarrier, vtk.vtkCommand.ModifiedEvent, self._onSeedsCarrierModified):
      self.removeObserver(self._seedsCarrier, vtk.vtkCommand.ModifiedEvent, self._onSeedsCarrierModified)
    self._seedsCarrier = None
    self._seedsDisplayNode = None
    self._pickLabelmap = None
    self._pickLabelmapKey = None
    # Unbind the table from the now-invalid carrier (drops its observer) so it
    # empties and does not observe a scene-cleared node, and drop the stale
    # display-node reference so a per-volume Place toggle cannot arm a gone node.
    self._bindSeedsTable(None)
    if self._seedsTable is not None and hasattr(self._seedsTable, "setDisplayNode"):
      self._seedsTable.setDisplayNode(None)
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    self.setParameterNode(self.logic.getParameterNode())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    # Disable the whole panel if no parameter node is selected (the enable-gate
    # moved to the panel root now the outer collapsible is gone, §3.2).
    parameterNode = self._parameterNode
    if not slicer.mrmlScene.IsNodePresent(parameterNode):
      parameterNode = None
    panel = getattr(self, "_panelWidget", None)
    if panel is not None:
      panel.enabled = parameterNode is not None
    if parameterNode is None:
      return

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    for nodeSelector, roleName in self.nodeSelectors:
      nodeSelector.setCurrentNode(self._parameterNode.GetNodeReference(roleName))
    inputSegmentationNode = self._parameterNode.GetNodeReference("inputSegmentation")
    if inputSegmentationNode and inputSegmentationNode.IsA("vtkMRMLSegmentationNode"):
      self.ui.InputSegmentSelectorWidget.setCurrentSegmentIDs(self._parameterNode.GetParameter("InputSegmentID"))

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    for nodeSelector, roleName in self.nodeSelectors:
      # ``currentNodeID`` is a Q_INVOKABLE method on the segment selector (a
      # bare property on the old node combo), so read the node's ID off the
      # returned node -- robust across both widget shapes.
      currentNode = nodeSelector.currentNode()
      self._parameterNode.SetNodeReferenceID(
        roleName, currentNode.GetID() if currentNode is not None else None)

    # The single InputSegmentSelectorWidget owns the segmentation-node choice
    # and stays visible always (hiding it would leave no way to pick an input);
    # the total-volume picker that used to follow the input was removed
    # (data-first §3.3 -- the % denominator is the input selection itself).


# LiverVolumetryLogic
#

class LiverVolumetryLogic(ScriptedLoadableModuleLogic):

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)

    from vtkSlicerLiverVolumetryModuleLogicPython import vtkLiverVolumetryLogic
    # Create the vtkLiverVolumetryLogic logic
    self.scl = vtkLiverVolumetryLogic()


  def isStageComplete(self) -> bool:
    """Stage-5 completion predicate for the Liver-shell sidebar (T5.2-d).

    Stage 5 (Volumetry) is a pure analytical workbench with no
    verification card in v2.0 (see ADR-0023 §"Decision" item 5 +
    §"What is NOT in v2.0").  v2.0 ships the *soft* semantics:
    Volumetry is "done" iff Stage 4 (Resection Planning) is done —
    the prerequisites are met, so the surgeon has reached the
    analytical workbench.  A future iteration may add a real gate
    (e.g. "at least one partition computation has been executed")
    once the v2.0 surgeon-facing volumetry surface crystallises.

    Pinned by
    ``Liver/Testing/Python/test_liver_shell_isstagecomplete.py``
    (T2 stage-5 symbol existence + T3 semantics).
    """
    import slicer
    resections = getattr(slicer.modules, "liverresections", None)
    if resections is None:
      return False
    try:
      logic = resections.logic()
    except Exception:  # pragma: no cover — defensive
      return False
    if logic is None or not hasattr(logic, "IsStageComplete"):
      return False
    return bool(logic.IsStageComplete())

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """

  def transientFiducialFromSeeds(self, seedsNode):
    """Build a TRANSIENT fiducial from the seed carrier (ADR-0038 §3c).

    Keeps the C++ ``vtkLiverVolumetryLogic`` signatures unchanged (ADR-0015):
    they take a ``vtkMRMLMarkupsFiducialNode*``, so the seeds-off-markups path
    feeds them a transient fiducial built INSIDE the call from the seed carrier,
    with the per-seed LABEL round-tripping into each control-point label so
    ``GenerateSegmentsLabelMap`` still names generated segments correctly.  The
    caller REMOVES the returned node -- no persistent markups survive
    (ADR-0014 §"Fourth layer").  ``None`` when there is no carrier.
    """
    if seedsNode is None:
      return None
    from LiverVolumetryLib import build_transient_fiducial
    return build_transient_fiducial(slicer.mrmlScene, seedsNode)

  def computeVolume(self, segmentsVolumeNode, targetSegmentVolumeNode, segmentationNode, outputTable, seedsNode, resectionNodes):
    statistics = {}
    if outputTable is None:
      raise ValueError("Missing outputTable")

    targetSegmentVolume = 0.0
    if targetSegmentVolumeNode is not None:
      import vtk
      import numpy
      scalars = vtk.util.numpy_support.vtk_to_numpy(targetSegmentVolumeNode.GetImageData().GetPointData().GetScalars())
      spacing = targetSegmentVolumeNode.GetSpacing()
      voxel_count = numpy.count_nonzero(scalars)
      targetSegmentVolume = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001

    # Build the transient fiducial from the seed carrier once and feed it to the
    # unchanged C++ logic (ADR-0038 §3c); remove it afterwards.
    hasSeeds = seedsNode is not None and seedsNode.GetNumberOfSeeds() > 0
    ROIMarkersList = self.transientFiducialFromSeeds(seedsNode) if hasSeeds else None
    try:
      if resectionNodes is None:
        if ROIMarkersList is None:
          import SegmentStatistics
          segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
          segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
          segStatLogic.computeStatistics()
          stats = segStatLogic.getStatistics()
          for segmentId in stats["SegmentIDs"]:
            voxel_count = 0
            volume_cm3 = 0
            if stats[segmentId,"LabelmapSegmentStatisticsPlugin.voxel_count"]:
              voxel_count = stats[segmentId,"LabelmapSegmentStatisticsPlugin.voxel_count"]
              volume_cm3 = stats[segmentId,"LabelmapSegmentStatisticsPlugin.volume_cm3"]
            elif stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.voxel_count"]:
              voxel_count = stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.voxel_count"]
              volume_cm3 = stats[segmentId,"ScalarVolumeSegmentStatisticsPlugin.volume_cm3"]
            segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
            statistics[segmentId] = [segmentName, voxel_count, volume_cm3]
            self.scl.VolumetryTable(segmentName, targetSegmentVolume, voxel_count, volume_cm3,outputTable)
        else:
          import vtk
          import numpy
          ROIvalues = self.scl.GetROIPointsLabelValue(segmentsVolumeNode, ROIMarkersList)
          scalars = vtk.util.numpy_support.vtk_to_numpy(segmentsVolumeNode.GetImageData().GetPointData().GetScalars())
          spacing = segmentsVolumeNode.GetSpacing()
          for i, values in enumerate(ROIvalues):
            voxel_count = numpy.count_nonzero(scalars == values)
            volume_cm3 = voxel_count*spacing[0]*spacing[1]*spacing[2]*0.001
            pointLabel = ROIMarkersList.GetNthControlPointLabel(i)
            statistics[pointLabel] = [pointLabel, voxel_count, volume_cm3]
            self.scl.VolumetryTable(pointLabel, targetSegmentVolume, voxel_count, volume_cm3, outputTable)
      else:
        # The C++ partition path (B3) labels the per-run total row from the
        # fed fiducial's node NAME; name it with the stable surgeon term so the
        # total row reads "All pieces", never the transient node's default name
        # (data-first §3.5).  The C++ side emits the name verbatim.
        if ROIMarkersList is not None:
          ROIMarkersList.SetName(PARTITION_TOTAL_LABEL)
        self.scl.ComputeAdvancedPlanningVolumetry(segmentsVolumeNode, outputTable, ROIMarkersList, resectionNodes, targetSegmentVolume)
      # The explicit % denominator row (territory-usability): every run ends
      # with a Total volume row naming what "% of total" is measured against
      # -- the rasterized tick selection (ticked segments; ALL segments when
      # none is ticked) -- with its mL and 100%.  Same denominator as before,
      # now visible.
      self.scl.VolumetryTable(
        TOTAL_SELECTED_SEGMENTS_LABEL, targetSegmentVolume, 0,
        targetSegmentVolume, outputTable)
      self._describePercentColumn(
        outputTable,
        "Measured against the Total volume row: the ticked total-volume "
        "segments (all segments when none is ticked).")
    finally:
      if ROIMarkersList is not None:
        slicer.mrmlScene.RemoveNode(ROIMarkersList)

  def computeVolumePerVolume(self, segmentationNode, seedsNode, outputTable):
    """Emit ONE results row per VOLUME = the union of its seeds' CARVED regions.

    territory-usability compute-on-carved: each seed's effective region is its
    owning segment MINUS the snapshot segments stacked above it (the
    visibility-composed carve rule, ``VisibilityCarve``), re-derived from the
    seed's placement-time visibility context -- so with Parenchyma + Segment_1
    visible, a seed in Parenchyma outside Segment_1 measures
    ``|Parenchyma \\ Segment_1|`` (the 216-54=162 mL phantom case), never the
    whole parenchyma.  A volume's row is the UNION of its seeds' carved
    regions; a seed with no snapshot contributes its whole bound segment
    (legacy semantics).  Rows are in surgeon terms (mL + % of total); the
    total is the whole segmentation's region so the % reads against the
    organ, and the run ends with an explicit ``Total volume (<segmentation
    name>)`` row carrying that denominator's mL and 100% (territory-usability
    -- the denominator is visible, not implicit).  A volume with no bound seed
    yields no row.  The module owns + clears the table
    (``_ensureResultsTable``), so this only appends rows.
    """
    if outputTable is None:
      raise ValueError("Missing outputTable")
    if segmentationNode is None or seedsNode is None:
      return

    import numpy
    import vtk

    from LiverVolumetryLib import (
      carve_effective_mask,
      effective_regions_per_volume,
      segments_above,
    )
    perVolume = effective_regions_per_volume(seedsNode)
    if not perVolume:
      return

    # ONE reference rasterization: the whole segmentation exported to a
    # labelmap fixes the common grid every per-segment mask is resampled onto
    # (the carve is same-grid boolean algebra) AND is the % denominator (the
    # organ's own region).
    segmentation = segmentationNode.GetSegmentation()
    allIDs = vtk.vtkStringArray()
    for i in range(segmentation.GetNumberOfSegments()):
      allIDs.InsertNextValue(segmentation.GetNthSegmentID(i))
    reference = slicer.mrmlScene.AddNewNodeByClass(
      "vtkMRMLLabelMapVolumeNode", "volumetryCarveReference")
    try:
      slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
        segmentationNode, allIDs, reference, None)
      image = reference.GetImageData()
      if image is None:
        return
      scalars = vtk.util.numpy_support.vtk_to_numpy(image.GetPointData().GetScalars())
      spacing = reference.GetSpacing()
      voxelMl = spacing[0] * spacing[1] * spacing[2] * 0.001
      totalVolumeMl = int(numpy.count_nonzero(scalars)) * voxelMl

      maskCache = {}
      def _segment_mask(segmentID):
        """The segment's binary mask on the reference grid (cached), or None."""
        if segmentID in maskCache:
          return maskCache[segmentID]
        try:
          mask = slicer.util.arrayFromSegmentBinaryLabelmap(
            segmentationNode, segmentID, reference)
        except Exception:  # noqa: BLE001 - a segment without a labelmap measures nothing
          mask = None
        maskCache[segmentID] = mask
        return mask

      dims = image.GetDimensions()
      shape = (dims[2], dims[1], dims[0])

      # One row per volume, in first-seen volume order on the carrier: the
      # union of the volume's distinct (owner, snapshot) carved regions.
      for volumeId in seedsNode.GetVolumeIds():
        entries = perVolume.get(volumeId)
        if not entries:
          continue
        union = numpy.zeros(shape, dtype=bool)
        for ownerSegmentID, context in entries:
          ownerMask = _segment_mask(ownerSegmentID)
          if ownerMask is None:
            continue
          aboveMasks = [
            mask
            for mask in (
              _segment_mask(segmentID)
              for segmentID in segments_above(list(context), ownerSegmentID))
            if mask is not None
          ]
          union |= carve_effective_mask(ownerMask, aboveMasks)
        voxelCount = int(union.sum())
        volumeMl = voxelCount * voxelMl
        rowName = seedsNode.GetVolumeLabel(volumeId) or volumeId
        self.scl.VolumetryTable(rowName, totalVolumeMl, voxelCount, volumeMl, outputTable)

      # The explicit % denominator row (territory-usability): on this path the
      # denominator is the WHOLE segmentation's region (all segments rasterized
      # together), so the Total row names the segmentation and reads 100%.
      totalLabel = f"Total volume ({segmentationNode.GetName()})"
      self.scl.VolumetryTable(
        totalLabel, totalVolumeMl, int(numpy.count_nonzero(scalars)),
        totalVolumeMl, outputTable)
      self._describePercentColumn(
        outputTable,
        f"Measured against the Total volume row: the whole "
        f"'{segmentationNode.GetName()}' segmentation (all segments together).")
    finally:
      slicer.mrmlScene.RemoveNode(reference)

  @staticmethod
  def _describePercentColumn(outputTable, text):
    """State the % denominator's definition on the column (header tooltip).

    The Total row makes the denominator visible in the DATA; the column
    description carries the same definition as the header's tooltip so the
    "% of total" wording is self-explaining (never colour/position alone,
    ADR-0010).  Best-effort: an outputTable without the schema API degrades
    to the Total row alone.
    """
    if outputTable is None or not hasattr(outputTable, "SetColumnDescription"):
      return
    outputTable.SetColumnDescription("% of total", text)

  def generateSegments(self, resectionNodes, seedsNode, segmentsVolumeNode):
    ROIMarkersList = self.transientFiducialFromSeeds(seedsNode)
    if ROIMarkersList is None:
      return
    try:
      generatedSegmentsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
      generatedSegmentsNode.CreateDefaultDisplayNodes()

      self.scl.GenerateSegmentsLabelMap(segmentsVolumeNode, generatedSegmentsNode, resectionNodes, ROIMarkersList)

      seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
      slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(generatedSegmentsNode, seg)

      # Segment names: the leftover (unseeded) region gets the NEUTRAL
      # "Unassigned" label -- volumetry carries no resection-planning
      # vocabulary (territory-usability); the seeded segments take their
      # seeds' labels.
      seg.GetSegmentation().GetNthSegment(0).SetName(UNSEEDED_SEGMENT_LABEL)
      for i in range(ROIMarkersList.GetNumberOfControlPoints()):
        seg.GetSegmentation().GetNthSegment(i+1).SetName(ROIMarkersList.GetNthFiducialLabel(i))

      slicer.mrmlScene.RemoveNode(generatedSegmentsNode)
    finally:
      slicer.mrmlScene.RemoveNode(ROIMarkersList)
