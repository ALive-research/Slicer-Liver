/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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

#include "qSlicerLiverMarkupsModule.h"

// MRML includes
#include "vtkMRMLMarkupsBezierSurfaceNode.h"
#include "vtkMRMLMarkupsSlicingContourNode.h"
#include "vtkMRMLMarkupsDistanceContourNode.h"

// Qt includes
#include <QDebug>

// Liver Markups Logic includes
#include "vtkSlicerLiverMarkupsLogic.h"

// Markups Logic includes
#include <vtkSlicerMarkupsLogic.h>

// Markups VTKWidgets includes
#include <vtkSlicerLineWidget.h>

// Liver Markups VTKWidgets includes
#include "vtkSlicerSlicingContourWidget.h"
#include "vtkSlicerDistanceContourWidget.h"
#include "vtkSlicerBezierSurfaceWidget.h"

// Slicer includes
#include <qSlicerModuleManager.h>
#include <qSlicerCoreApplication.h>
#include <qSlicerIOManager.h>

// Qt includes
#include <QDebug>
#include <QSettings>

//-----------------------------------------------------------------------------
class qSlicerLiverMarkupsModulePrivate
{
public:
  qSlicerLiverMarkupsModulePrivate();
};

//-----------------------------------------------------------------------------
// qSlicerLiverMarkupsModulePrivate methods

//-----------------------------------------------------------------------------
qSlicerLiverMarkupsModulePrivate::qSlicerLiverMarkupsModulePrivate()
{
}

//-----------------------------------------------------------------------------
// qSlicerLiverMarkupsModule methods

//-----------------------------------------------------------------------------
qSlicerLiverMarkupsModule::qSlicerLiverMarkupsModule(QObject* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverMarkupsModulePrivate)
{
}

//-----------------------------------------------------------------------------
qSlicerLiverMarkupsModule::~qSlicerLiverMarkupsModule()
{
}

bool qSlicerLiverMarkupsModule::isHidden() const
{
    return true;
}

//-----------------------------------------------------------------------------
QString qSlicerLiverMarkupsModule::helpText() const
{
  return "This module contains fundamental markups to be used in the Slicer-Liver extension.";
}

//-----------------------------------------------------------------------------
QString qSlicerLiverMarkupsModule::acknowledgementText() const
{
  return "This work has been partially funded by The Research Council of Norway (grant nr. 311393)";
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverMarkupsModule::contributors() const
{
  QStringList moduleContributors;
  moduleContributors << QString("Rafael Palomar (Oslo University Hospital / NTNU) ");
  moduleContributors << QString("Ole Vegard Solberg (SINTEF) ");
  moduleContributors << QString("Geir Arne Tangen (SINTEF) ");
  return moduleContributors;
}

//-----------------------------------------------------------------------------
QIcon qSlicerLiverMarkupsModule::icon() const
{
  return QIcon(":/Icons/LiverMarkups.png");
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverMarkupsModule::categories() const
{
  return QStringList() << "Liver";
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverMarkupsModule::dependencies() const
{
  return QStringList() << "Markups";
}

//-----------------------------------------------------------------------------
void qSlicerLiverMarkupsModule::setup()
{
  this->Superclass::setup();

  vtkSlicerApplicationLogic *appLogic = this->appLogic();
  if (!appLogic) {
    qCritical() << Q_FUNC_INFO << " : invalid application logic.";
    return;
  }

  auto markupsLogic =
      vtkSlicerMarkupsLogic::SafeDownCast(appLogic->GetModuleLogic("Markups"));
  if (!markupsLogic) {
    qCritical() << Q_FUNC_INFO << " : invalid markups logic.";
    return;
  }

  bool createPushButton = false;
  if (qSlicerApplication::application()->userSettings()->value("Developer/DeveloperMode") .toBool())
    {
    createPushButton = true; // Ephimeral markups should not create a push button unless in developer mode.
    }

  // Register markups
  vtkNew<vtkMRMLMarkupsSlicingContourNode> slicingContourNode;
  vtkNew<vtkSlicerSlicingContourWidget> slicingContourWidget;
  markupsLogic->RegisterMarkupsNode(slicingContourNode, slicingContourWidget, createPushButton);

  vtkNew<vtkMRMLMarkupsDistanceContourNode> distanceContourNode;
  vtkNew<vtkSlicerDistanceContourWidget> distanceContourWidget;
  markupsLogic->RegisterMarkupsNode(distanceContourNode, distanceContourWidget, createPushButton);

  vtkNew<vtkMRMLMarkupsBezierSurfaceNode> bezierSurfaceNode;
  vtkNew<vtkSlicerBezierSurfaceWidget> bezierSurfaceWidget;
  markupsLogic->RegisterMarkupsNode(bezierSurfaceNode, bezierSurfaceWidget);
}

//-----------------------------------------------------------------------------
qSlicerAbstractModuleRepresentation* qSlicerLiverMarkupsModule
::createWidgetRepresentation()
{
    return nullptr;
}

//-----------------------------------------------------------------------------
vtkMRMLAbstractLogic* qSlicerLiverMarkupsModule::createLogic()
{
  return vtkSlicerLiverMarkupsLogic::New();
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverMarkupsModule::associatedNodeTypes() const
{
  return QStringList()
    << "vtkMRMLMarkupsSlicingContourNode"
    << "vtkMRMLMarkupsDistanceContourNode"
    << "vtkMRMLMarkupsBezierSurfaceNode";
}

//-----------------------------------------------------------------------------
void qSlicerLiverMarkupsModule::setMRMLScene(vtkMRMLScene* scene)
{
  Superclass::setMRMLScene(scene);
  vtkSlicerLiverMarkupsLogic* logic =
    vtkSlicerLiverMarkupsLogic::SafeDownCast(this->logic());
  if (!logic)
    {
    qCritical() << Q_FUNC_INFO << " failed: logic is invalid";
    return;
    }
}
