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

// Qt includes
#include <QAbstractButton>
#include <QGridLayout>
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
  this->connect(d->OpenResectogramViewButton, SIGNAL(clicked()), this, SLOT(openResectogramView()));

  this->updateOpenActionState();
}

//-----------------------------------------------------------------------------
qMRMLNodeComboBox* qSlicerLiverResectionsModuleWidget::resectionSurfaceComboBox() const
{
  Q_D(const qSlicerLiverResectionsModuleWidget);
  return d->ResectionSurfaceComboBox;
}

//-----------------------------------------------------------------------------
QAbstractButton* qSlicerLiverResectionsModuleWidget::openResectogramViewButton() const
{
  Q_D(const qSlicerLiverResectionsModuleWidget);
  return d->OpenResectogramViewButton;
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
  this->updateOpenActionState();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::onActiveResectionChanged(vtkMRMLNode* node)
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  vtkMRMLMarkupsBezierSurfaceNode* surface = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(node);

  // Re-observe the active surface so computing a distance map (which
  // mutates the surface node) re-fires the gating predicate live.
  this->qvtkDisconnect(d->ActiveResectionNode, vtkCommand::ModifiedEvent, this, SLOT(updateOpenActionState()));
  d->ActiveResectionNode = surface;
  if (surface)
  {
    this->qvtkConnect(surface, vtkCommand::ModifiedEvent, this, SLOT(updateOpenActionState()));
  }

  this->updateOpenActionState();
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::updateOpenActionState()
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  vtkMRMLMarkupsBezierSurfaceNode* surface = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(d->ResectionSurfaceComboBox->currentNode());

  // ADR-0023 §Stage-4 gating predicate: enabled iff a Bezier surface is
  // selected AND it carries a distance map.  State-orthogonal: the gate
  // does NOT consult the ADR-0019 ResectionState.
  bool hasSurface = (surface != nullptr);
  bool hasDistanceMap = hasSurface && (surface->GetDistanceMapVolumeNode() != nullptr);
  bool enabled = hasSurface && hasDistanceMap;

  d->OpenResectogramViewButton->setEnabled(enabled);

  // ADR-0009 §"explainable disabled state": a disabled affordance says why.
  if (!hasSurface)
  {
    d->OpenResectogramViewButton->setToolTip(tr("Select a resection surface."));
  }
  else if (!hasDistanceMap)
  {
    d->OpenResectogramViewButton->setToolTip(tr("Compute the distance map first."));
  }
  else
  {
    d->OpenResectogramViewButton->setToolTip(tr("Open the resectogram view for the selected resection surface."));
  }
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::openResectogramView()
{
  Q_D(qSlicerLiverResectionsModuleWidget);

  vtkMRMLMarkupsBezierSurfaceNode* surface = vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(d->ResectionSurfaceComboBox->currentNode());
  if (!surface || surface->GetDistanceMapVolumeNode() == nullptr)
  {
    // Gate not satisfied; nothing to open.
    return;
  }

  vtkMRMLScene* scene = this->mrmlScene();
  if (!scene)
  {
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
  this->showResectogramWidget(viewNode);
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModuleWidget::showResectogramWidget(vtkMRMLViewNode* viewNode)
{
  Q_D(qSlicerLiverResectionsModuleWidget);

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
    // Fill the panel rather than sit left-aligned + letterboxed: an Expanding
    // size policy in both axes lets the embedded view claim the panel width,
    // and a non-trivial minimum height makes it read as a square-ish strip
    // panel matching the square (u, v) domain (the mapper's MatRatio handles
    // intrinsic anisotropy inside it) -- ADR-0023 §Stage-4 layout.
    widget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    widget->setMinimumHeight(250);
    widget->setMRMLScene(this->mrmlScene());
    widget->setMRMLViewNode(viewNode);
    d->ResectogramWidget = widget;

    // Place it below the gated action in the Resection Planning panel grid
    // (row 2 under the combo + button rows, spanning both columns).  Drop the
    // competing outer vertical spacer so the grid gives its stretch to the
    // view widget instead of an empty filler, letting the strip fill the
    // panel -- ADR-0023 §Stage-4.
    if (QGridLayout* grid = qobject_cast<QGridLayout*>(d->ResectionPlanningCollapsibleButton->layout()))
    {
      grid->addWidget(widget, 2, 0, 1, 2);
      grid->setRowStretch(2, 1);
    }
    else if (QLayout* layout = d->ResectionPlanningCollapsibleButton->layout())
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
}
