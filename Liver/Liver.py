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

  1. Case Setup            (shell-owned placeholder; ADR-0029)
  2. Anatomy Definition    (LiverSegmentation; gated on the v2.1
                            LiverSegmentation deliverable -- disabled
                            until then per Stage 2 graceful-degradation)
  3. Vascular Territories  (VascularTerritories.widgetRepresentation())
  4. Resection Planning    (LiverResections.widgetRepresentation())
  5. Volumetry             (LiverVolumetry.widgetRepresentation())
  6. Export                (shell-owned placeholder)

Per-stage completion is queried via ``IsStageComplete()`` on the C++
logic of stages 3/4 and ``isStageComplete()`` on the Python logic of
stage 5.  Stages 1 and 6 own their predicates on ``LiverWidget``
itself (no companion module exists).  The shell observes MRML scene
events via ``VTKObservationMixin`` and re-paints the sidebar
indicators (✓ done / ● current / ○ pending) on every change.

Domain algorithm bridges historically embedded here (signed-Maurer
distance maps, Bezier surface fitting, elliptic Fourier descriptors)
were relocated to ``LiverLib/legacy_logic.py`` -- a Python sub-package
sibling to the scripted module per the ``LiverResectionsLib/``
convention -- in T5.2-d.  Slicer's scripted-module loader does not
sweep subdirectories, so the sub-package is importable Python without
being mis-instantiated as a Slicer module.  The full move to the
per-stage modules these helpers actually belong to is tracked as the
orphaned-domain-code relocation follow-up.
"""

# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern


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

    self.parent.dependencies = ["LiverResections", "LiverMarkups", "VascularTerritories"]

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

  def setup(self):
    """Build the six-stage navigation shell.

    No domain logic; no per-module widget wiring beyond the
    composition step.  Stages 2-5 reach into their owning module's
    ``widgetRepresentation()`` cache; stages 1 and 6 ship shell-owned
    placeholders (real UIs land in follow-up tasks — see ADR-0023
    §Stage 1 / §Stage 6 + ADR-0029).
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

  # ------------------------------------------------------------------ #
  # Liver-shell sidebar — composition + navigation (ADR-0023 Option H)
  #
  # Six stages, each one tab in a vertical QTabWidget (TabPosition=West):
  #
  #   0  Case Setup            (shell-owned)
  #   1  Anatomy Definition    (LiverSegmentation widgetRepresentation;
  #                             gated on the v2.1 LiverSegmentation
  #                             deliverable — disabled until then)
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
  # (LiverSegmentation) is gated on the v2.1 LiverSegmentation
  # deliverable and currently routed to the shell-owned graceful-
  # degradation stub.
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
    owning Slicer module; stages 1 and 6 host shell-owned placeholders.
    Stage 2 (LiverSegmentation) degrades gracefully when the module is
    absent (v2.1 deliverable): tab disabled-greyed; predicate returns
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
    self._refreshStageIndicators()

  def _resolveStagePage(self, index):
    """Return ``(page_widget, is_available)`` for stage ``index``.

    Stages 1 and 6 return shell-owned placeholders; stages 2-5 return
    the cached ``widgetRepresentation()`` of the matching Slicer
    module, or a "module not available" placeholder when the module
    is not registered.
    """
    if index == 0:
      return self._buildStage1Page(), True
    if index == 5:
      return self._buildStage6Page(), True

    module = getattr(slicer.modules, self._STAGE_MODULE[index], None)
    rep = None
    if module is not None and hasattr(module, "widgetRepresentation"):
      try:
        rep = module.widgetRepresentation()
      except Exception:  # pragma: no cover — surfaces only on broken module loads
        rep = None
    if rep is None:
      return self._buildUnavailablePage(self._STAGE_NAMES[index]), False
    return rep, True

  def _buildStage1Page(self):
    """Shell-owned Case Setup placeholder (ADR-0023 §Stage 1 / ADR-0029).

    The functional UI for Stage 1 lands in a follow-up task (planner
    §"Stage 1"); for T5.2-d the shell only reserves the page so the
    sidebar contract is satisfied.
    """
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel("Case Setup — load volumes and tag roles (Stage 1)."))
    layout.addStretch(1)
    return page

  def _buildStage6Page(self):
    """Shell-owned Export placeholder (ADR-0023 §Stage 6).

    Real Export UI lands in a follow-up; T5.2-d ships only the page
    placeholder + the "last write OK" predicate.
    """
    page = qt.QWidget()
    layout = qt.QVBoxLayout(page)
    layout.addWidget(qt.QLabel("Export — save the resection plan to disk (Stage 6)."))
    layout.addStretch(1)
    return page

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

    The QTabWidget already swaps the visible page on its own; this
    slot only refreshes the per-tab indicators so the 'current'
    marker tracks selection.
    """
    self._refreshStageIndicators()

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
    """
    scene = slicer.mrmlScene
    volumes = scene.GetNodesByClass("vtkMRMLScalarVolumeNode")
    if volumes is None:
      return False
    for i in range(volumes.GetNumberOfItems()):
      node = volumes.GetItemAsObject(i)
      if node is not None and node.GetAttribute("LiverRole"):
        return True
    return False

  def _stage2IsComplete(self):
    """Stage 2 — graceful-degradation stub while LiverSegmentation is absent.

    Per planner §"Stage 2 stub strategy" (locked decision): the
    LiverSegmentation module is a v2.1 deliverable.  Until it lands,
    the predicate returns ``False`` and the sidebar row is
    disabled-greyed.
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
    scene = slicer.mrmlScene
    if scene is None:
      return False
    nodes = scene.GetNodesByClass("vtkMRMLScriptedModuleNode")
    for i in range(nodes.GetNumberOfItems()):
      node = nodes.GetItemAsObject(i)
      if node.GetModuleName() == "Liver" and node.GetName() == "LiverShellState":
        return node.GetParameter("Stage6.LastWriteOK") == "True"
    return False

  def _stageIsComplete(self, row):
    """Return the completion bool for stage ``row``.

    Routes to the per-stage owner: shell methods for shell-owned
    stages (0, 1, 5 — the last two until the v2.1 LiverSegmentation
    deliverable lands), module-logic ``IsStageComplete()`` for the
    rest.  Test mode
    short-circuits via ``_injectedStageCompletion`` (set by
    ``_injectStageCompletionForTesting``).
    """
    injected = self._injectedStageCompletion
    if injected is not None and 0 <= row < len(injected):
      return bool(injected[row])

    shellPredicate = {
      0: self._stage1IsComplete,
      1: self._stage2IsComplete,  # Stage 2 stub — LiverSegmentation is a v2.1 deliverable.
      5: self._stage6IsComplete,
    }.get(row)
    if shellPredicate is not None:
      return shellPredicate()

    moduleName = self._STAGE_MODULE.get(row)
    if moduleName is None:
      return False
    module = getattr(slicer.modules, moduleName, None)
    if module is None:
      return False
    try:
      logic = module.logic()
    except Exception:  # pragma: no cover — defensive
      return False
    if logic is None:
      return False

    # C++ logic exposes ``IsStageComplete`` (VTK convention);
    # Python logic exposes ``isStageComplete`` (Python convention).
    for attr in ("IsStageComplete", "isStageComplete"):
      query = getattr(logic, attr, None)
      if callable(query):
        try:
          return bool(query())
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
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    pass

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    pass


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
