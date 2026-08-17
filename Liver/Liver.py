# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
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
#   This file was originally developed by Rafael Palomar (Oslo University
#   Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
#   Research Council of Norway through the ALive project (grant nr. 311393).
#
# ==============================================================================

"""Liver — Slicer-Liver shell module.

The Liver scripted module is the surgeon-facing entry point for the
Slicer-Liver extension.  Per ADR-0023 §"Shell composition (Option H)"
it composes — but does not compute — six surgeon-facing stages on a
vertical sidebar driving a content stack:

  1. Case Setup            (shell-owned page; ADR-0029)
  2. Anatomy Definition    (LiverSegmentation.widgetRepresentation();
                            degrades gracefully when the module is
                            absent from the build per Stage 2
                            graceful-degradation)
  3. Vascular Territories  (VascularTerritories.widgetRepresentation())
  4. Resection Planning    (LiverResections.widgetRepresentation())
  5. Volumetry             (LiverVolumetry.widgetRepresentation())
  6. Export                (shell-owned page)

Per-stage completion is queried via ``IsStageComplete()`` on the C++
logic of stages 3/4 and ``isStageComplete()`` on the Python logic of
stage 5.  Stages 1 and 6 own their predicates on ``LiverWidget``
itself (no companion module exists).  The shell observes MRML scene
events via ``VTKObservationMixin`` and re-paints the sidebar
indicators (✓ done / ● current / ○ pending) on every change.
"""

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern


import logging
import os

import slicer
import qt
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# Liver
#

class Liver(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)

    self.parent.title = "Liver"

    self.parent.categories = ["IGT"]

    self.parent.dependencies = ["LiverResections", "VascularTerritories"]

    self.parent.contributors = ["Rafael Palomar (Oslo University Hospital / NTNU)",
                                "Ole Vegard Solberg (SINTEF)",
                                "Geir Arne Tangen (SINTEF)",
                                "Egidijus Pelanis (Oslo University Hospital)",
                                "Davit Aghayan (Oslo University Hospital)",
                                "Gabriella D'Albenzio (Oslo University Hospital)",
                                "Ruoyan Meng (NTNU)",
                                "Javier Pérez-de-Frutos (SINTEF)",
                                "Héctor Mártinez (Universidad de Córdoba)",
                                "Francisco Javier Rodríguez Lozano (Universidad de Córdoba)",
                                "Joaquín Olivares Bueno (Universidad de Córdoba)",
                                "José Manuel Palomares Muñoz (Universidad de Córdoba)"]

    self.parent.acknowledgementText = """
    This work was funded by The Research Council of
    Norway through the project ALive (grant nr. 311393).
    """
    self.parent.helpText = """
    This module offers tools for liver perfusion analysis and resection planning.
    """

    # Additional initialization step after application startup is complete
    slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

def registerSampleData():
  """
  Add data sets to Sample Data module.
  """
  import SampleData
  iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

  aliveDataURL = 'https://github.com/alive-research/aliveresearchtestingdata/releases/download/'

  # Liver dataset
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverVolume000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverVolume000.png'),
    uris=aliveDataURL + 'SHA256/5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    fileNames='LiverVolume000.nrrd',
    checksums='SHA256:5df79d9077b1cf2b746ff5cf9268e0bc4d440eb50fa65308b47bde094640458a',
    nodeNames='LiverVolume000',
    loadFileType='VolumeFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegmentation000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris=aliveDataURL + 'SHA256/56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    fileNames='LiverSegmentation000.seg.nrrd',
    checksums='SHA256:56aa9ee4658904dfae5cca514f594fa6c5b490376514358137234e22d57452a4',
    nodeNames='LiverSegmentation000',
    loadFileType='SegmentationFile'
  )

  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category='Liver',
    sampleName='LiverSegments000',
    thumbnailFileName=os.path.join(iconsPath, 'LiverSegments000.png'),
    uris=aliveDataURL + 'SHA256/101d3903a8b27eb2e7ee3ceb8ddd15f288aeb69960a1606db64d5ae3180e251b',
    fileNames='LiverSegments000.seg.nrrd',
    checksums='SHA256:101d3903a8b27eb2e7ee3ceb8ddd15f288aeb69960a1606db64d5ae3180e251b',
    nodeNames='LiverSements000',
    loadFileType='SegmentationFile'
  )

  #if developerMode is True:
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Development',
    sampleName ='3D-IRCADb-01_08',
    thumbnailFileName = os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris = aliveDataURL+'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    fileNames ='3D-IRCADb-01_08.nrrd',
    checksums = 'SHA256:2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    nodeNames ='3D-IRCADb-01_08',
    loadFileType = 'SegmentationFile'
  )

  #if developerMode is True:
  SampleData.SampleDataLogic.registerCustomSampleDataSource(
    category ='Development',
    sampleName ='3D-IRCADb-01_08',
    thumbnailFileName = os.path.join(iconsPath, 'LiverSegmentation000.png'),
    uris = aliveDataURL+'SHA256/2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    fileNames ='3D-IRCADb-01_08.nrrd',
    checksums = 'SHA256:2e25b8ce2c70cc2e1acd9b3356d0b1291b770274c16fcd0e2a5b69a4587fbf74',
    nodeNames ='3D-IRCADb-01_08',
    loadFileType = 'SegmentationFile'
  )

#
# LiverWidget
#

class LiverWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Liver-module shell (compose-only) per ADR-0023 §"Shell composition".

  The widget owns no domain logic: it composes the six surgeon-facing
  stages (Case Setup → Anatomy Definition → Vascular Territories →
  Resection Planning → Volumetry → Export) on a vertical sidebar
  driving a content stack.  Each stage's data model + queries live in
  the matching Slicer module (or, for Stages 1/6, on this shell —
  there is no companion module to delegate to).

  Per-stage completion is queried via ``IsStageComplete()`` on the
  C++ logic of stages 3/4 and ``isStageComplete()`` on the Python
  logic of stage 5.  The shell observes scene events via
  ``VTKObservationMixin`` and re-runs every predicate on change.
  """

  def __init__(self, parent=None):
    """Initialise shell state.  No domain work happens here."""
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)

    # Liver-shell sidebar (ADR-0023 Option H) — populated in
    # ``_buildShellSidebar`` from ``setup()``.  Kept ``None`` here so
    # any pre-setup call to ``_refreshStageIndicators`` short-circuits
    # cleanly instead of NPE'ing.
    self._stageTabs = None
    self._stagePages = []
    self._shellHost = None
    self._injectedStageCompletion = None

    # Stage-1 Case Setup table (built in ``_buildStage1Page``); ``None``
    # here so a pre-build ``_refreshCaseSetupTable`` short-circuits.
    self._caseSetupTable = None

    # Stage-6 Export widgets (built in ``_buildStage6Page``).
    self._exportPlanCombo = None
    self._exportStatusLabel = None

    # Stage-lifecycle bookkeeping (see §"Stage lifecycle forwarding"):
    # which stage row is showing, and whether the shell itself is the
    # module the application currently shows.  Both are needed to forward
    # ``enter()`` / ``exit()`` to exactly one hosted stage panel.
    self._currentStageIndex = None
    self._shellEntered = False

  def setup(self):
    """Build the six-stage navigation shell.

    No domain logic; no per-module widget wiring beyond the
    composition step.  Stages 2-5 reach into their owning module's
    ``widgetRepresentation()`` cache; stages 1 and 6 ship shell-owned
    pages (Case Setup per ADR-0029; Export per ADR-0023 §Stage 6).
    """
    ScriptedLoadableModuleWidget.setup(self)

    self._buildShellSidebar()

    # Observe MRML scene events so the per-stage indicators stay in
    # sync with the underlying data — adding a confirmed resection
    # plan, for instance, flips Stage 4 from pending to complete
    # without surgeon-visible delay.  Hybrid state source per planner
    # §"State source": logic owns the query, the shell observes.
    scene = slicer.mrmlScene
    self.addObserver(scene, scene.NodeAddedEvent, self._onSceneChanged)
    self.addObserver(scene, scene.NodeRemovedEvent, self._onSceneChanged)
    self.addObserver(scene, scene.EndImportEvent, self._onSceneChanged)
    self.addObserver(scene, scene.EndCloseEvent, self._onSceneChanged)

  def _onSceneChanged(self, caller=None, event=None):
    """Refresh per-stage indicators in response to scene events."""
    self._refreshStageIndicators()
    # Newly loaded/removed volumes should appear in the Case Setup role table.
    self._refreshCaseSetupTable()

  # ------------------------------------------------------------------ #
  # Liver-shell sidebar — composition + navigation (ADR-0023 Option H)
  #
  # Six stages, each one tab in a vertical QTabWidget (TabPosition=West):
  #
  #   0  Case Setup            (shell-owned)
  #   1  Anatomy Definition    (LiverSegmentation widgetRepresentation;
  #                             degrades gracefully — disabled when the
  #                             module is absent from the build)
  #   2  Vascular Territories  (VascularTerritories widgetRepresentation)
  #   3  Resection Planning    (LiverResections widgetRepresentation)
  #   4  Volumetry             (LiverVolumetry widgetRepresentation)
  #   5  Export                (shell-owned)
  #
  # Per-row state-indicator semantics (ADR-0023 §"Shell composition"):
  #   ✓  complete  — stage's IsStageComplete() returns True
  #   ●  current   — sidebar's selected row (overrides 'complete')
  #   ○  pending   — neither complete nor current
  #
  # State source is hybrid (T5.2-d planner §"State source"): each
  # module's logic owns the query; the shell observes scene events via
  # VTKObservationMixin and re-runs every predicate on change.
  # ------------------------------------------------------------------ #

  # Tab labels — kept short to fit the vertical tab strip without
  # truncation.  Canonical long-form names live in ADR-0023 §"Decision".
  _STAGE_NAMES = (
    "Case",
    "Anatomy",
    "Territories",
    "Planning",
    "Volumetry",
    "Export",
  )

  _INDICATOR_COMPLETE = "✓"  # check mark
  _INDICATOR_CURRENT = "●"   # filled circle
  _INDICATOR_PENDING = "○"   # empty circle

  # Stage index → Slicer module name owning that stage's
  # widgetRepresentation() + IsStageComplete() query.  Stages 0 (Case
  # Setup) and 5 (Export) are shell-owned and omitted; stage 1
  # (LiverSegmentation) is routed to the shell-owned graceful-
  # degradation stub when the module is absent from the build.
  _STAGE_MODULE = {
    1: "liversegmentation",
    2: "vascularterritories",
    3: "liverresections",
    4: "livervolumetry",
  }

  def _buildShellSidebar(self):
    """Construct the vertical-tab shell (single QTabWidget, TabPosition=West).

    Idempotent — calling twice replaces the previous widget cleanly.
    Stages 2-5 surface the cached widgetRepresentation() of their
    owning Slicer module; stages 1 and 6 host shell-owned pages.
    Stage 2 (LiverSegmentation) degrades gracefully when the module is
    absent from the build: tab disabled-greyed; predicate returns
    False.

    Mechanism choice: ADR-0023 §"Shell composition (Option H)" pinned
    the contract (vertical strip, six stages, state indicators,
    cached-widget content panel) but not the widget.  QTabWidget(West)
    collapses sidebar + content stack into one widget — more compact
    than a QListWidget + QStackedWidget split, and still a vertical
    strip per the rejected-horizontal-tabs ADR rationale.
    """
    self._stageTabs = qt.QTabWidget()
    self._stageTabs.setObjectName("LiverShellStageTabs")
    self._stageTabs.setTabPosition(qt.QTabWidget.West)

    # Reset the test-time injection bag every time we rebuild.
    self._injectedStageCompletion = None
    # Cached module widget references kept here so the lifetime is the
    # shell's, not the QTabWidget's child-ownership cycle.
    self._stagePages = []

    for index, name in enumerate(self._STAGE_NAMES):
      page, available = self._resolveStagePage(index)
      self._stagePages.append(page)
      self._stageTabs.addTab(page, f"{self._INDICATOR_PENDING}  {name}")
      if not available:
        # Greyed-disabled signals "module not registered in this build";
        # see Stage 2 graceful-degradation contract (ADR-0023 §Stage 2).
        self._stageTabs.setTabEnabled(index, False)

    self._stageTabs.connect("currentChanged(int)", self._onStageRowChanged)

    self._shellHost = qt.QWidget()
    hostLayout = qt.QHBoxLayout(self._shellHost)
    hostLayout.setContentsMargins(0, 0, 0, 0)
    hostLayout.addWidget(self._stageTabs, 1)
    self.layout.addWidget(self._shellHost)

    self._stageTabs.setCurrentIndex(0)
    self._currentStageIndex = self._stageTabs.currentIndex
    self._refreshStageIndicators()

  def _resolveStagePage(self, index):
    """Return ``(page_widget, is_available)`` for stage ``index``.

    Stages 1 and 6 return shell-owned pages; stages 2-5 return
    the cached ``widgetRepresentation()`` of the matching Slicer
    module, or a "module not available" placeholder when the module
    is not registered.
    """
    if index == 0:
      return self._buildStage1Page(), True
    if index == 5:
      return self._buildStage6Page(), True
    if index == 3:
      # Stage 4 "Resection Planning" GUI is Python (ADR-0004): build the
      # Python ResectionPlanningWidget directly rather than routing through
      # the LiverResections loadable module's widgetRepresentation().  The
      # IsStageComplete() query path still reads the C++ module logic
      # (see _stageIsComplete) -- only the widget surface moved to Python.
      return self._buildResectionPlanningPage()

    module = getattr(slicer.modules, self._STAGE_MODULE[index], None)
    rep = None
    if module is not None and hasattr(module, "widgetRepresentation"):
      try:
        rep = module.widgetRepresentation()
      except Exception:  # pragma: no cover — surfaces only on broken module loads
        rep = None
    if rep is None:
      return self._buildUnavailablePage(self._STAGE_NAMES[index]), False
    self._suppressEmbeddedDeveloperTools(rep)
    return rep, True

  @staticmethod
  def _suppressEmbeddedDeveloperTools(rep):
    """Hide an embedded scripted sub-module's own developer-tools collapsible.

    Each embedded scripted stage widget runs ``ScriptedLoadableModuleWidget.setup``,
    which (with Developer Mode enabled) appends its own "Reload & Test"
    collapsible.  Inside the shell that duplicates the shell's single developer
    section, so the embedded one is hidden here -- the shell owns the one at the
    top.  Loadable (C++) module reps have no such collapsible; the guards make
    this a no-op for them and when Developer Mode is off.
    """
    inner = rep.self() if hasattr(rep, "self") else None
    button = getattr(inner, "reloadCollapsibleButton", None)
    if button is not None:
      button.setVisible(False)

  #: Human-facing dropdown labels for the machine-stable LiverRole values that
  #: aren't already presentable (the stored value is decoupled from the label).
  _CASE_SETUP_ROLE_LABELS = {"PortalVenous": "Portal venous"}

  def _buildStage1Page(self):
    """Shell-owned Case Setup UI (ADR-0023 §Stage 1 / ADR-0029; ADR-0004 Python).

    Load volume(s) via Slicer's Add Data, then tag each with its
    acquisition-phase role DIRECTLY in the volumes table: the Role
    column hosts a per-row combo (default **None**) whose pick writes
    the shared ``LiverRole`` attribute via
    ``LiverSegmentationLib.roles.set_volume_role`` — the SAME vocabulary
    Stage 2 reads to pick its working volume.  Tagging flips the Stage-1
    completion indicator (``_stage1IsComplete`` reads the attribute).
    Degrades to a hint label when the shared roles module is unreachable
    (a build without ``LiverSegmentationLib``).
    """
    try:
      from LiverSegmentationLib import roles  # noqa: F401 — availability gate
    except Exception:  # pragma: no cover — surfaces only when the lib is absent
      page = qt.QWidget()
      layout = qt.QVBoxLayout(page)
      layout.addWidget(qt.QLabel(
        "Case Setup — volume-role tagging unavailable in this build."))
      layout.addStretch(1)
      return page

    # Static panel authored in ``Resources/UI/StageCaseSetupWidget.ui``
    # (designer-editable, the Stage-6 Export pattern); only the runtime
    # wiring -- role population, signals, scene binding, the code-populated
    # volumes-x-roles table refresh -- stays here.
    page = slicer.util.loadUI(self.resourcePath("UI/StageCaseSetupWidget.ui"))
    page.setMRMLScene(slicer.mrmlScene)
    ui = slicer.util.childWidgetVariables(page)

    # The role is picked DIRECTLY in the table (a per-row combo); the
    # former select-volume + pick-role + Assign round-trip is retired.
    table = ui.CaseSetupRoleTable
    table.horizontalHeader().setStretchLastSection(True)

    self._caseSetupTable = table

    self._refreshCaseSetupTable()
    return page

  def _caseSetupRoleLabel(self, value):
    """Human dropdown/table label for a stored ``LiverRole`` value."""
    return self._CASE_SETUP_ROLE_LABELS.get(value, value)

  def _onCaseSetupRolePicked(self, volume, combo):
    """Write the row's picked role onto its volume; None clears the tag.

    Qt-signal boundary: never raises (a combo pick must not throw into
    the event loop).
    """
    try:
      from LiverSegmentationLib import roles

      role = combo.itemData(combo.currentIndex)
      if role is None:
        # The explicit None default: an untagged volume carries no tag.
        volume.SetAttribute("LiverRole", None)
      else:
        roles.set_volume_role(volume, role)
      self._refreshStageIndicators()
    except Exception:  # pragma: no cover — Qt signal boundary must not raise
      logging.exception("Case Setup role pick failed")

  def _refreshCaseSetupTable(self):
    """Rebuild the volumes x role table from the scene's scalar volumes.

    The Role column hosts a QComboBox PER ROW: first entry is the
    explicit **None** default (data ``None`` — a freshly loaded volume
    is untagged until the surgeon chooses), then the shared role
    vocabulary.  Picking writes ``LiverRole`` immediately.
    """
    table = self._caseSetupTable
    if table is None:
      return
    try:
      from LiverSegmentationLib import roles
    except Exception:  # pragma: no cover — surfaces only when the lib is absent
      return
    volumes = list(slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"))
    table.setRowCount(len(volumes))
    for row, volume in enumerate(volumes):
      table.setItem(row, 0, qt.QTableWidgetItem(volume.GetName()))
      combo = qt.QComboBox()
      combo.addItem("None", None)
      for value in roles.LIVER_ROLES:
        combo.addItem(self._caseSetupRoleLabel(value), value)
      current = volume.GetAttribute("LiverRole")
      if current is not None:
        index = combo.findData(current)
        if index >= 0:
          combo.setCurrentIndex(index)
      combo.connect(
        "currentIndexChanged(int)",
        lambda _index, v=volume, c=combo: self._onCaseSetupRolePicked(v, c),
      )
      table.setCellWidget(row, 1, combo)

  def _buildResectionPlanningPage(self):
    """Return ``(page_widget, is_available)`` for the Stage-4 Python widget.

    Build the Stage-4 Resection Planning Python widget (ADR-0004).

    The GUI surface for Stage 4 is Python (ADR-0004: widgets/GUI logic
    are Python; C++ only for data-only MRML nodes + profile-justified
    algorithm libs).  The widget imports ResectogramViewManager directly
    and calls the wrapped C++ nodes/logic without the string bridge the
    retired C++ widget used.  The reference is stored on the shell (in
    ``_stagePages`` by the caller) so its lifetime is the shell's, like
    the other stage pages.  Falls back to the unavailable placeholder
    when the Python lib is not reachable (e.g. a build without the
    LiverResectionsLib scripted package).
    """
    try:
      from LiverResectionsLib.ResectionPlanningWidget import ResectionPlanningWidget
    except Exception:  # pragma: no cover — surfaces only when the lib is absent
      return self._buildUnavailablePage(self._STAGE_NAMES[3]), False
    widget = ResectionPlanningWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    return widget, True

  def _buildStage6Page(self):
    """Shell-owned Export UI (ADR-0023 §Stage 6; ADR-0004 Python).

    The static panel is authored in ``Resources/UI/StageExportWidget.ui`` (a
    designer-editable layout) and loaded here; only the runtime wiring — scene
    binding + the Save signal — stays in code.  Select a resection plan and
    Save it to a ``.lrp.json`` (schema v2, via ``vtkMRMLResectionPlanStorageNode``);
    a successful write records ``Stage6.LastWriteOK`` on the shell state node,
    flipping ``_stage6IsComplete``.
    """
    page = slicer.util.loadUI(self.resourcePath("UI/StageExportWidget.ui"))
    page.setMRMLScene(slicer.mrmlScene)
    ui = slicer.util.childWidgetVariables(page)
    # Bind the selector's scene explicitly -- the root qMRMLWidget's
    # setMRMLScene does not reliably propagate to the child selector at
    # build time (before the page is parented/shown).
    ui.ExportPlanComboBox.setMRMLScene(slicer.mrmlScene)
    ui.ExportSaveButton.connect("clicked()", self._onExportSaveClicked)
    self._exportPlanCombo = ui.ExportPlanComboBox
    self._exportStatusLabel = ui.ExportStatusLabel
    return page

  def _onExportSaveClicked(self):
    """Prompt for a path and export the selected plan (the :0 entry point)."""
    combo = self._exportPlanCombo
    plan = combo.currentNode() if combo is not None else None
    if plan is None:
      if self._exportStatusLabel is not None:
        self._exportStatusLabel.setText("Select a resection plan to export.")
      return
    path = qt.QFileDialog.getSaveFileName(
      None, "Export resection plan", "", "Liver resection plan (*.lrp.json)")
    if not path:
      return
    ok = self._exportResectionPlan(plan, path)
    if self._exportStatusLabel is not None:
      self._exportStatusLabel.setText("Saved." if ok else "Export failed.")
    self._refreshStageIndicators()

  def _liverShellStateNode(self):
    """Get-or-create the shell's scene-level state node (survives save/load).

    A ``vtkMRMLScriptedModuleNode`` named ``LiverShellState`` under module
    ``Liver`` -- the standard pattern for module-owned scene-level state
    (ADR-0023 §"Shell composition (Option H)").
    """
    for node in slicer.util.getNodesByClass("vtkMRMLScriptedModuleNode"):
      if node.GetModuleName() == "Liver" and node.GetName() == "LiverShellState":
        return node
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode", "LiverShellState")
    node.SetModuleName("Liver")
    return node

  def _recordStage6Write(self, ok):
    """Record 'last write OK' so ``_stage6IsComplete`` reflects it."""
    self._liverShellStateNode().SetParameter(
      "Stage6.LastWriteOK", "True" if ok else "False")

  def _exportResectionPlan(self, planNode, path):
    """Write ``planNode`` to ``path`` (.lrp.json); record success.

    Returns ``True`` iff the write succeeded, recording ``Stage6.LastWriteOK``.
    A no-op returning ``False`` on a missing plan / path (does NOT mark the
    stage complete).
    """
    if planNode is None or not path:
      return False
    ok = bool(slicer.util.saveNode(planNode, path))
    if ok:
      self._recordStage6Write(True)
    return ok

  def _buildUnavailablePage(self, stageName):
    """Placeholder shown when a stage's owning module is not registered."""
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel(
      f"{stageName} — module not available in this build."
    ))
    layout.addStretch(1)
    return page

  def _onStageRowChanged(self, row):
    """Slot for ``QTabWidget.currentChanged(int)``.

    The QTabWidget already swaps the visible page on its own; this slot
    refreshes the per-tab indicators so the 'current' marker tracks
    selection, and hands the stage lifecycle over from the outgoing
    stage's panel to the incoming one (§"Stage lifecycle forwarding").
    """
    previous = self._currentStageIndex
    self._currentStageIndex = row
    if self._shellEntered and previous != row:
      self._forwardStageLifecycle(previous, "exit")
      self._forwardStageLifecycle(row, "enter")
    self._refreshStageIndicators()

  # ------------------------------------------------------------------ #
  # Stage lifecycle forwarding
  #
  # The stage panels this shell hosts are NOT modules the application
  # enters.  Slicer calls ``enter()`` / ``exit()`` on the widget of the
  # SELECTED module only, and every stage panel here is either a hidden
  # module's cached ``widgetRepresentation()`` or a shell-built Python
  # widget (ADR-0023 §"Shell composition (Option H)": "the Liver shell
  # holds no domain logic -- only composition + navigation").  So the
  # shell has to relay its own lifecycle:
  #
  #   * shell ``enter()``  -> ``enter()`` on the SHOWING stage's panel;
  #   * shell ``exit()``   -> ``exit()``  on the SHOWING stage's panel;
  #   * stage switch       -> ``exit()`` outgoing, ``enter()`` incoming.
  #
  # Only the showing stage is relayed to: a stage panel's ``enter()``
  # means "this is the panel the surgeon is looking at" (it opens
  # module-scoped interaction gates and raises module-scoped overlays --
  # ADR-0037 §"Module-active gate (extends §Decision 2)", ADR-0038
  # §"Shared home + names"), which is false for the five stages stacked
  # behind the current tab.
  #
  # Without this relay every exit-hygiene body a stage panel owns --
  # overlay retire, highlight-march timer stop, module-active gate close
  # -- is dead code inside the shell.
  # ------------------------------------------------------------------ #

  @staticmethod
  def _stageLifecycleTarget(page):
    """The object carrying stage ``page``'s ``enter()`` / ``exit()`` bodies.

    A scripted stage module's ``widgetRepresentation()`` exposes its Python
    widget via ``self()``, and the lifecycle bodies live THERE.  Relaying to
    that Python object rather than to the C++ representation is deliberate:
    ``qSlicerAbstractModuleWidget::enter()`` / ``exit()`` also maintain an
    ``IsEntered`` flag that is asserted on double-enter and in the
    representation's destructor, and the shell's stage navigation is not the
    application's module lifecycle -- driving that flag from here would
    assert.  Shell-owned pages (Stage 4's Python widget, the Case Setup /
    Export pages, the unavailable placeholder) are returned as themselves;
    the caller skips any target that has no such method.
    """
    if page is None:
      return None
    if hasattr(page, "self"):
      try:
        inner = page.self()
      except Exception:  # pragma: no cover — surfaces only on broken module loads
        inner = None
      if inner is not None:
        return inner
    return page

  def _forwardStageLifecycle(self, row, methodName):
    """Relay ``methodName`` to stage ``row``'s panel; never break navigation.

    A row outside the built page set, a page that never got built, and a
    panel that simply does not define the method are all silently skipped
    (a never-built page has no state to clean up).  The call is wrapped
    because it runs on a Qt signal / module-lifecycle boundary: a raising
    stage panel must not strand shell navigation half-switched.
    """
    pages = self._stagePages or []
    if row is None or not 0 <= row < len(pages):
      return
    target = self._stageLifecycleTarget(pages[row])
    method = getattr(target, methodName, None)
    if not callable(method):
      return
    try:
      method()
    except Exception:  # pragma: no cover — lifecycle boundary must not raise
      logging.exception(
        "Liver shell: stage %s %s() failed", row, methodName)

  # ------------------------------------------------------------------ #
  # Per-stage IsStageComplete() — hybrid: module logic owns the body,
  # the shell merely queries it.  The shell-owned predicates (Stage 1,
  # Stage 6) live here because there is no companion module to delegate
  # to (per planner §"IsStageComplete() contract per stage").
  # ------------------------------------------------------------------ #

  def _stage1IsComplete(self):
    """Stage 1 — done iff at least one volume carries a ``LiverRole`` attribute.

    ADR-0029 §"Stage 1 functional contract" identifies the per-volume
    role tag as Stage 1's commit signal.  Attribute presence (not
    value) is the gate; the surgeon's eyeball judges correctness.

    Uses ``slicer.util.getNodesByClass`` rather than the raw
    ``vtkMRMLScene::GetNodesByClass``: the latter returns a collection
    the caller must ``UnRegister`` (the Python wrapper does not own
    it), and leaking it trips Slicer's VTK_DEBUG_LEAKS gate.  The
    helper unregisters the collection and returns a plain list.
    """
    for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
      if node.GetAttribute("LiverRole"):
        return True
    return False

  def _stage2IsComplete(self):
    """Stage 2 — graceful-degradation stub while LiverSegmentation is absent.

    Per planner §"Stage 2 stub strategy" (locked decision): when the
    LiverSegmentation module is absent from the build, the predicate
    returns ``False`` and the sidebar row is disabled-greyed.
    """
    return False

  def _stage6IsComplete(self):
    """Stage 6 — done iff the scene has logged a successful plan write.

    The shell tracks "last write OK" via a ``vtkMRMLScriptedModuleNode``
    that the Export sub-widget creates and populates on successful
    serialisation (the standard Slicer pattern for module-owned
    scene-level state that survives save/load).  Absence of the node
    — or of the ``Stage6.LastWriteOK`` parameter on it — is treated
    as "not written yet", consistent with the optimistic semantics
    described in ADR-0023 §"Shell composition (Option H)".
    """
    # ``slicer.util.getNodesByClass`` unregisters the underlying
    # collection (the raw ``vtkMRMLScene::GetNodesByClass`` leaks it
    # under the Python wrapper, tripping VTK_DEBUG_LEAKS).
    for node in slicer.util.getNodesByClass("vtkMRMLScriptedModuleNode"):
      if node.GetModuleName() == "Liver" and node.GetName() == "LiverShellState":
        return node.GetParameter("Stage6.LastWriteOK") == "True"
    return False

  def _stageIsComplete(self, row):
    """Return the completion bool for stage ``row``.

    Routes to the per-stage owner: shell methods for shell-owned
    stages (0, 1, 5 — stage 1 while LiverSegmentation is absent from
    the build), module-logic ``IsStageComplete()`` for the rest.  Test
    mode short-circuits via ``_injectedStageCompletion`` (set by
    ``_injectStageCompletionForTesting``).
    """
    injected = self._injectedStageCompletion
    if injected is not None and 0 <= row < len(injected):
      return bool(injected[row])

    shellPredicate = {
      0: self._stage1IsComplete,
      5: self._stage6IsComplete,
    }.get(row)
    if shellPredicate is not None:
      return shellPredicate()

    # Stage 2 (row 1) routes to the LiverSegmentation module's own
    # isStageComplete via the module-logic lookup below when the module is
    # present; when it is absent the lookup returns False (the graceful-
    # degradation semantics _stage2IsComplete documents).  It is NOT pinned to
    # the always-False shell stub here, or a completed anatomy stage would never
    # flip its indicator (ADR-0023 §Stage 2).

    moduleName = self._STAGE_MODULE.get(row)
    if moduleName is None:
      return False
    module = getattr(slicer.modules, moduleName, None)
    if module is None:
      return False

    # C++ stage logics expose their predicate on the wrapped module logic
    # (``IsStageComplete`` VTK convention / ``isStageComplete`` Python).
    try:
      logic = module.logic()
    except Exception:  # pragma: no cover — defensive
      logic = None
    # SCRIPTED modules wrap their C++ stage logic as ``self()._cppLogic``
    # (VascularTerritories): ``module.logic()`` returns the generic
    # ``vtkSlicerScriptedLoadableModuleLogic`` shim, which never carries the
    # predicate -- and the C++ module object refuses new attributes, so the
    # specialized logic cannot be grafted onto it.  Query the Python module
    # instance's ``_cppLogic`` alongside the plain logic.
    candidates = [logic]
    # The scripted module's Python instance registers itself as
    # ``slicer.modules.<ModuleName>Instance`` (the ScriptedLoadableModule
    # convention); ``module.name`` gives the CamelCase module name.
    try:
      instance = getattr(slicer.modules, module.name + "Instance", None)
    except Exception:  # pragma: no cover — defensive
      instance = None
    if instance is not None:
      candidates.append(getattr(instance, "_cppLogic", None))
    for candidate in candidates:
      for attr in ("IsStageComplete", "isStageComplete"):
        query = getattr(candidate, attr, None) if candidate is not None else None
        if callable(query):
          try:
            return bool(query())
          except Exception:  # pragma: no cover — defensive
            return False

    # LiverSegmentation is a SCRIPTED module: its ``isStageComplete`` lives on
    # the Python ``LiverSegmentationLogic``, not the wrapped module logic that
    # ``module.logic()`` returns.  Resolve a fresh instance — it reads the same
    # scene, so no module widget need be built — so a completed anatomy stage
    # flips its indicator instead of being pinned False (ADR-0023 §Stage 2).
    if moduleName == "liversegmentation":
      try:
        import LiverSegmentation
        return bool(LiverSegmentation.LiverSegmentationLogic().isStageComplete())
      except Exception:  # pragma: no cover — defensive
        return False
    return False

  def _stageIndicatorState(self, row):
    """Return ``'complete' | 'current' | 'pending'`` for stage ``row``.

    'current' takes precedence over 'complete' so the surgeon always
    sees which stage is active — even if they've revisited a stage
    they previously completed.  Test contract pinned by
    ``test_state_indicators_reflect_isstagecomplete``.
    """
    if self._stageTabs is not None and self._stageTabs.currentIndex == row:
      return "current"
    if self._stageIsComplete(row):
      return "complete"
    return "pending"

  def _indicatorGlyph(self, state):
    return {
      "complete": self._INDICATOR_COMPLETE,
      "current": self._INDICATOR_CURRENT,
      "pending": self._INDICATOR_PENDING,
    }.get(state, self._INDICATOR_PENDING)

  def _refreshStageIndicators(self):
    """Re-read per-stage completion + repaint the tab labels.

    Cheap to call repeatedly; the predicate side-effects (scene
    iteration) are O(scene-size) per stage but happen at human
    interaction rate.
    """
    if self._stageTabs is None:
      return
    for row in range(self._stageTabs.count):
      state = self._stageIndicatorState(row)
      glyph = self._indicatorGlyph(state)
      name = self._STAGE_NAMES[row]
      self._stageTabs.setTabText(row, f"{glyph}  {name}")

  def _injectStageCompletionForTesting(self, pattern):
    """Mock per-stage completion for invariant tests.

    Pinned by ``test_state_indicators_reflect_isstagecomplete``:
    ``pattern`` is a six-element iterable of booleans; the next
    ``_refreshStageIndicators`` call uses it instead of the real
    predicates.  Pass ``None`` to clear.
    """
    if pattern is None:
      self._injectedStageCompletion = None
      return
    self._injectedStageCompletion = [bool(x) for x in pattern]

  def cleanup(self):
    """Tear down scene observers wired in ``setup()``.

    Without ``removeObservers()`` the VTKObservationMixin keeps the
    scene-change callbacks alive across module reloads, leaking one
    observer per reload.
    """
    # A shell torn down while showing (a module reload) would otherwise
    # leave the showing stage panel's exit hygiene unrun -- its timers
    # still firing and its overlays still on screen with no owner.
    self.exit()
    self.removeObservers()

  def enter(self):
    """Called each time the user opens this module.

    Relays the lifecycle to the showing stage's panel
    (§"Stage lifecycle forwarding").
    """
    self._shellEntered = True
    self._forwardStageLifecycle(self._currentStageIndex, "enter")

  def exit(self):
    """Called each time the user opens a different module.

    Relays the lifecycle to the showing stage's panel so its module-scoped
    overlays / timers / interaction gates retire (§"Stage lifecycle
    forwarding").  Idempotent: relaying happens only while the shell is
    marked as showing.
    """
    if not self._shellEntered:
      return
    self._shellEntered = False
    self._forwardStageLifecycle(self._currentStageIndex, "exit")


#
# LiverTest
#

class LiverTest(ScriptedLoadableModuleTest):
  """Smoke-test entry point for the Liver shell.

  Real coverage lives in the pytest suites under
  ``Liver/Testing/Python/``; this class only satisfies Slicer's
  scripted-module test discovery contract.
  """

  def setUp(self):
    """Reset scene + reload the sample-data sources used by the shell."""
    slicer.mrmlScene.Clear()
    import SampleData
    registerSampleData()
    SampleData.downloadSample('LiverSegmentation000')
    SampleData.downloadSample('LiverVolume000')
    self.delayDisplay('Loaded test data set')

  def runTest(self):
    self.setUp()
    self.test_Liver1()

  def test_Liver1(self):
    self.delayDisplay("Test passed!")
