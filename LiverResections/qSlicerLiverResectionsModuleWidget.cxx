/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2017-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Kitware, Inc. nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
  HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

// LiverResections Widgets includes
#include "qSlicerLiverResectionsModuleWidget.h"
#include "ui_qSlicerLiverResectionsModuleWidget.h"

// LiverMarkups MRML includes
#include "vtkMRMLMarkupsBezierSurfaceNode.h"

// LiverResections MRML includes
#include "vtkMRMLResectogramDisplayNode.h"

// Slicer includes
#include <qMRMLNodeComboBox.h>
#include <qMRMLThreeDView.h>
#include <qMRMLThreeDViewControllerWidget.h>
#include <qMRMLThreeDWidget.h>
#include <qSlicerApplication.h>
#include <qSlicerPythonManager.h>

// CTK includes
#include <ctkCollapsibleButton.h>

// MRML includes
#include <vtkMRMLScalarVolumeNode.h>
#include <vtkMRMLScene.h>
#include <vtkMRMLViewNode.h>

// VTK includes
#include <vtkCamera.h>
#include <vtkRenderer.h>

// Qt includes
#include <QGridLayout>
#include <QLabel>
#include <QLayout>
#include <QPointer>
#include <QSizePolicy>
#include <QString>

namespace
{
/// The singleton tag the dedicated resectogram view node carries.  Mirrors
/// the source-of-truth literal ``RESECTOGRAM_VIEW_SINGLETON_TAG`` in
/// ``LiverResectionsLib/ResectogramViewManager.py``: the Python manager mints
/// the node (ADR-0004 keeps the view-manager class on the Python side); this
/// widget only resolves the already-minted node back from the scene by its
/// singleton tag to bind the embedded view widget.  Kept in lockstep with the
/// Python constant.
const char* const RESECTOGRAM_VIEW_SINGLETON_TAG = "LiverResectogram";

/// Flattened-quad camera pose + flat background pushed straight onto the
/// embedded view's renderer.  The standalone qMRMLThreeDWidget is not managed
/// by the layout manager, so it does NOT honour the MRML camera node or the
/// view-node background; these are applied at the renderer level (mirroring the
/// arena's ``_apply_camera_and_background`` and the proven scenario constants
/// in scenarios/Resectogram4x4BlurOff.py).  They frame the FIXED flattened
/// (u, v) quad, independent of the resection's patient-space pose.
const double RESECTOGRAM_CAMERA_POSITION[3] = { 0.0, 60.0, 300.0 };
const double RESECTOGRAM_CAMERA_FOCAL_POINT[3] = { 0.0, 60.0, 0.0 };
const double RESECTOGRAM_CAMERA_VIEW_UP[3] = { 0.0, 1.0, 0.0 };
const double RESECTOGRAM_CAMERA_PARALLEL_SCALE = 70.0;
const double RESECTOGRAM_CAMERA_VIEW_ANGLE = 45.0;
const double RESECTOGRAM_CAMERA_CLIPPING_RANGE[2] = { 10.0, 800.0 };
const double RESECTOGRAM_BACKGROUND_RGB[3] = { 0.0, 0.0, 0.0 };
} // namespace

//-----------------------------------------------------------------------------
class qSlicerLiverResectionsModuleWidgetPrivate : public Ui_qSlicerLiverResectionsModuleWidget
{
public:
  qSlicerLiverResectionsModuleWidgetPrivate() = default;

  /// The active resection surface currently observed for the gating
  /// predicate (so computing a distance map re-fires the state update).
  vtkWeakPointer<vtkMRMLMarkupsBezierSurfaceNode> ActiveResectionNode;

  /// The single embedded view widget bound to the singleton resectogram view
  /// node (created once on first open; shown/raised on re-open).  Parented
  /// into the module panel layout, so Qt owns its lifetime.
  QPointer<qMRMLThreeDWidget> ResectogramWidget;

  /// The surface currently observed for the resectogram-render hook (its
  /// control-point edits repaint the embedded strip).  Distinct from
  /// ``ActiveResectionNode`` (which observes for the gating predicate): the
  /// render hook is wired only once the embedded view exists, and is
  /// re-targeted on re-open, so it is tracked separately for symmetric
  /// RemoveObserver.
  vtkWeakPointer<vtkMRMLMarkupsBezierSurfaceNode> RenderObservedNode;
};

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModuleWidget::qSlicerLiverResectionsModuleWidget(QWidget* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverResectionsModuleWidgetPrivate)
{
}

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModuleWidget::~qSlicerLiverResectionsModuleWidget() = default;

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::setup()
{
  Q_D(qSlicerLiverResectionsModuleWidget);
  this->Superclass::setup();
  d->setupUi(this);

  this->connect(d->ResectionSurfaceComboBox, SIGNAL(currentNodeChanged(vtkMRMLNode*)), this, SLOT(onActiveResectionChanged(vtkMRMLNode*)));

  this->refreshResectogramDrawer();
}

//-----------------------------------------------------------------------------
qMRMLNodeComboBox* qSlicerLiverResectionsModuleWidget::resectionSurfaceComboBox() const
{
  Q_D(const qSlicerLiverResectionsModuleWidget);
  return d->ResectionSurfaceComboBox;
}

//-----------------------------------------------------------------------------
QWidget* qSlicerLiverResectionsModuleWidget::resectogramDrawer() const
{
  Q_D(const qSlicerLiverResectionsModuleWidget);
  return d->ResectogramDrawer;
}

//-----------------------------------------------------------------------------
QLabel* qSlicerLiverResectionsModuleWidget::resectogramHintLabel() const
{
  Q_D(const qSlicerLiverResectionsModuleWidget);
  return d->ResectogramHintLabel;
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::setActiveResectionNode(vtkMRMLNode* node)
{
  Q_D(qSlicerLiverResectionsModuleWidget);
  d->ResectionSurfaceComboBox->setCurrentNode(node);
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::setMRMLScene(vtkMRMLScene* scene)
{
  Q_D(qSlicerLiverResectionsModuleWidget);
  this->Superclass::setMRMLScene(scene);
  d->ResectionSurfaceComboBox->setMRMLScene(scene);
  this->refreshResectogramDrawer();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::onActiveResectionChanged(vtkMRMLNode* node)
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  vtkMRMLMarkupsBezierSurfaceNode* surface = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(node);

  // Re-observe the active surface so computing a distance map (which mutates
  // the surface node) re-evaluates the drawer state live -- this is the
  // auto-populate path: a distance map appearing on the selected surface fills
  // the drawer without any explicit user action (ADR-0023 §Stage-4).
  this->qvtkDisconnect(d->ActiveResectionNode, vtkCommand::ModifiedEvent, this, SLOT(refreshResectogramDrawer()));
  d->ActiveResectionNode = surface;
  if (surface)
  {
    this->qvtkConnect(surface, vtkCommand::ModifiedEvent, this, SLOT(refreshResectogramDrawer()));
  }

  this->refreshResectogramDrawer();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::refreshResectogramDrawer()
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  vtkMRMLMarkupsBezierSurfaceNode* surface = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(d->ResectionSurfaceComboBox->currentNode());

  // ADR-0023 §Stage-4 auto-populate predicate: a resectogram is available iff
  // a Bezier surface is selected AND it carries a distance map.
  // State-orthogonal: the predicate does NOT consult the ADR-0019
  // ResectionState.
  bool hasSurface = (surface != nullptr);
  bool hasDistanceMap = hasSurface && (surface->GetDistanceMapVolumeNode() != nullptr);
  vtkMRMLScene* scene = this->mrmlScene();

  if (!hasDistanceMap || !scene)
  {
    // ADR-0009 §"explainable state": show a hint INSTEAD of an edge-on / blank
    // view, and stop observing any stale surface for render so a deselected
    // surface no longer repaints the strip.
    if (d->ResectogramWidget)
    {
      d->ResectogramWidget->hide();
    }
    this->observeSurfaceForRender(nullptr);
    if (d->ResectogramHintLabel)
    {
      d->ResectogramHintLabel->setText(!hasSurface ? tr("Select a resection with a computed distance map.") : tr("Compute the distance map for this resection first."));
      d->ResectogramHintLabel->show();
    }
    return;
  }

  // Ensure EXACTLY ONE resectogram display node on the surface
  // (idempotent): reuse an existing one, create one only when absent.
  vtkMRMLResectogramDisplayNode* displayNode = nullptr;
  for (int index = 0; index < surface->GetNumberOfDisplayNodes(); ++index)
  {
    displayNode = vtkMRMLResectogramDisplayNode::SafeDownCast(surface->GetNthDisplayNode(index));
    if (displayNode)
    {
      break;
    }
  }
  if (!displayNode)
  {
    displayNode = vtkMRMLResectogramDisplayNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLResectogramDisplayNode"));
    if (displayNode)
    {
      surface->AddAndObserveDisplayNodeID(displayNode->GetID());
    }
  }

  // Ensure the singleton resectogram view node AND present the flattened
  // strip alone in it (display-node + view-node + camera configuration; no
  // custom DisplayableManager, ADR-0013 §5).  Both live on the Python
  // ResectogramViewManager (LiverResectionsLib), the source of truth for the
  // singleton-by-tag view node; ADR-0004 keeps the view-manager class on the
  // Python side.  Delegate via the application's Python manager, mirroring the
  // Pipeline-creator registration in ``qSlicerLiverResectionsModule::setup()``.
  // The surface + resectogram display node are passed by MRML node ID and
  // resolved back inside Python so no live C++ pointers cross the bridge.
  if (qSlicerApplication* app = qSlicerApplication::application())
  {
    if (qSlicerPythonManager* pythonManager = app->pythonManager())
    {
      QString surfaceID = surface->GetID();
      QString displayID = displayNode ? QString(displayNode->GetID()) : QString();
      // GetNodeByID("") resolves to None, so an absent display node needs no
      // separate guard on the Python side.
      pythonManager->executeString(QString("import slicer\n"
                                           "from LiverResectionsLib.ResectogramViewManager import ResectogramViewManager\n"
                                           "_mgr = ResectogramViewManager()\n"
                                           "_view = _mgr.ensureViewNode()\n"
                                           "_surface = slicer.mrmlScene.GetNodeByID('%1')\n"
                                           "_display = slicer.mrmlScene.GetNodeByID('%2')\n"
                                           "_mgr.configureView(_view, _display, _surface)\n")
                                     .arg(surfaceID, displayID));
    }
  }

  // Resolve the just-ensured singleton view node back from the scene by its
  // tag (the Python manager is the source of truth for minting it) and embed
  // a single qMRMLThreeDWidget bound to it in this module's panel.  The
  // LayerDM ResectogramPipeline — registered to fire only for this tagged
  // view — composites the flattened strip into this panel-local view rather
  // than a main-area Slicer layout (ADR-0023 §Stage-4; the SlicerHyperProbe
  // create_three_d_widget precedent).
  vtkMRMLViewNode* viewNode = vtkMRMLViewNode::SafeDownCast(scene->GetSingletonNode(RESECTOGRAM_VIEW_SINGLETON_TAG, "vtkMRMLViewNode"));
  if (!viewNode)
  {
    return;
  }

  // The resectogram is available: hide the explanatory hint and show the view
  // in its place.  showResectogramWidget self-gates on a realized GL context
  // (hasRealizedGLContext); under --no-main-window the node-ensure +
  // configureView invariants above still ran, but the embed + framing is the
  // orchestrator's interactive :0 eyeball pass (ADR-0023 §Stage-4).
  if (d->ResectogramHintLabel)
  {
    d->ResectogramHintLabel->hide();
  }
  this->showResectogramWidget(viewNode);

  // Repaint the embedded strip whenever the selected surface's control points
  // move.  The MRML displayable managers honour the ViewNodeIDs restriction,
  // but the STANDALONE embedded view does not repaint on the Pipeline's
  // RequestRender, so observe the surface here and force a render on edit
  // (ADR-0023 §Stage-4).
  this->observeSurfaceForRender(surface);
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::showResectogramWidget(vtkMRMLViewNode* viewNode)
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  // Binding the singleton view node to the embedded qMRMLThreeDWidget
  // (setMRMLViewNode) synchronously attaches the LayerDM displayable manager,
  // which uploads the distance-map 3D texture for the gate-satisfied surface.
  // That upload needs a realized GL context (see hasRealizedGLContext): under
  // --no-main-window it would hard-crash, so skip the embed there.  The
  // display-node + view-node ensure (the headless invariants) already ran in
  // refreshResectogramDrawer before this call; the embed + framing is the
  // orchestrator's interactive :0 eyeball pass (ADR-0023 §Stage-4).
  if (!this->hasRealizedGLContext())
  {
    return;
  }

  // Create the embedded view widget exactly once (idempotent re-open).  Bind
  // it to the singleton view node; the controller chrome is hidden so the
  // panel reads as the flattened resectogram image (the Hyperprobe precedent
  // hides threeDController() the same way).
  if (!d->ResectogramWidget)
  {
    qMRMLThreeDWidget* widget = new qMRMLThreeDWidget(this);
    widget->setObjectName("ResectogramThreeDWidget");
    if (qMRMLThreeDViewControllerWidget* controller = widget->threeDController())
    {
      controller->hide();
    }
    // Fill the drawer rather than sit left-aligned + letterboxed: an Expanding
    // size policy in both axes lets the embedded view claim the drawer width,
    // and a non-trivial minimum height makes it read as a square-ish strip
    // panel matching the square (u, v) domain (the mapper's MatRatio handles
    // intrinsic anisotropy inside it) -- ADR-0023 §Stage-4 layout.
    widget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    widget->setMinimumHeight(250);
    widget->setMRMLScene(this->mrmlScene());
    widget->setMRMLViewNode(viewNode);
    d->ResectogramWidget = widget;

    // Place it inside the resectogram drawer, below the hint label (row 1 of
    // the drawer grid), so it fills the drawer width and claims its stretch --
    // ADR-0023 §Stage-4.
    if (QGridLayout* grid = qobject_cast<QGridLayout*>(d->ResectogramDrawer->layout()))
    {
      grid->addWidget(widget, 1, 0);
      grid->setRowStretch(1, 1);
    }
    else if (QLayout* layout = d->ResectogramDrawer->layout())
    {
      layout->addWidget(widget);
    }
  }
  else
  {
    // Re-open: keep ONE widget; re-target the (singleton) view node and the
    // current scene defensively, then show/raise it.
    d->ResectogramWidget->setMRMLScene(this->mrmlScene());
    d->ResectogramWidget->setMRMLViewNode(viewNode);
  }

  d->ResectogramWidget->show();
  d->ResectogramWidget->raise();

  // The standalone embedded view is not managed by the layout manager, so it
  // ignores the MRML camera node + view-node background the Python
  // configureView set.  Push the flattened-quad pose + flat background onto
  // the renderer directly (mirrors the arena), then repaint.
  this->poseEmbeddedRenderer();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::poseEmbeddedRenderer()
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  if (!d->ResectogramWidget || !this->hasRealizedGLContext())
  {
    return;
  }

  qMRMLThreeDView* view = d->ResectogramWidget->threeDView();
  if (!view)
  {
    return;
  }
  vtkRenderer* renderer = view->renderer();
  if (!renderer)
  {
    return;
  }

  // Camera pose onto the renderer's ACTIVE camera (not the MRML camera node,
  // which the standalone view ignores).  Parallel projection framing the fixed
  // flattened (u, v) quad -- independent of the resection's patient-space pose.
  vtkCamera* camera = renderer->GetActiveCamera();
  if (camera)
  {
    camera->SetPosition(RESECTOGRAM_CAMERA_POSITION[0], RESECTOGRAM_CAMERA_POSITION[1], RESECTOGRAM_CAMERA_POSITION[2]);
    camera->SetFocalPoint(RESECTOGRAM_CAMERA_FOCAL_POINT[0], RESECTOGRAM_CAMERA_FOCAL_POINT[1], RESECTOGRAM_CAMERA_FOCAL_POINT[2]);
    camera->SetViewUp(RESECTOGRAM_CAMERA_VIEW_UP[0], RESECTOGRAM_CAMERA_VIEW_UP[1], RESECTOGRAM_CAMERA_VIEW_UP[2]);
    camera->ParallelProjectionOn();
    camera->SetParallelScale(RESECTOGRAM_CAMERA_PARALLEL_SCALE);
    camera->SetViewAngle(RESECTOGRAM_CAMERA_VIEW_ANGLE);
    camera->SetClippingRange(RESECTOGRAM_CAMERA_CLIPPING_RANGE[0], RESECTOGRAM_CAMERA_CLIPPING_RANGE[1]);
  }

  // Flat background onto the renderer (the blue gradient is the default 3D
  // background the standalone view keeps unless overridden here).
  renderer->SetBackground(RESECTOGRAM_BACKGROUND_RGB[0], RESECTOGRAM_BACKGROUND_RGB[1], RESECTOGRAM_BACKGROUND_RGB[2]);
  renderer->SetBackground2(RESECTOGRAM_BACKGROUND_RGB[0], RESECTOGRAM_BACKGROUND_RGB[1], RESECTOGRAM_BACKGROUND_RGB[2]);

  view->forceRender();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::observeSurfaceForRender(vtkMRMLMarkupsBezierSurfaceNode* surface)
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  if (d->RenderObservedNode == surface)
  {
    return;
  }

  // Symmetric removal of the prior observer before re-targeting, so a stale
  // surface never repaints the strip.
  this->qvtkDisconnect(d->RenderObservedNode, vtkCommand::ModifiedEvent, this, SLOT(scheduleResectogramRender()));
  this->qvtkDisconnect(d->RenderObservedNode, vtkMRMLMarkupsNode::PointModifiedEvent, this, SLOT(scheduleResectogramRender()));

  d->RenderObservedNode = surface;
  if (surface)
  {
    this->qvtkConnect(surface, vtkCommand::ModifiedEvent, this, SLOT(scheduleResectogramRender()));
    this->qvtkConnect(surface, vtkMRMLMarkupsNode::PointModifiedEvent, this, SLOT(scheduleResectogramRender()));
  }
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::scheduleResectogramRender()
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  // Same realized-GL-context requirement as the embed (hasRealizedGLContext):
  // forcing a render drives the distance-map texture upload; no live view to
  // repaint without one.
  if (!d->ResectogramWidget || !this->hasRealizedGLContext())
  {
    return;
  }
  if (qMRMLThreeDView* view = d->ResectogramWidget->threeDView())
  {
    view->forceRender();
  }
}

//-----------------------------------------------------------------------------
bool qSlicerLiverResectionsModuleWidget::hasRealizedGLContext() const
{
  qSlicerApplication* app = qSlicerApplication::application();
  return app != nullptr && app->mainWindow() != nullptr;
}
