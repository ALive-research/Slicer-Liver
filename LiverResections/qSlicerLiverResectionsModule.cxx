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

#include "qSlicerLiverResectionsModule.h"

// Qt includes
#include <QDebug>

// Liver Resections Logic includes
#include "vtkSlicerLiverResectionsLogic.h"

// Liver Resections MRML includes
#include "qSlicerLiverResectionsWriter.h"
#include "qSlicerLiverResectionsReader.h"

#include <qSlicerModuleManager.h>
#include <qSlicerCoreApplication.h>
#include <qSlicerIOManager.h>

//-----------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_ExtensionTemplate
class qSlicerLiverResectionsModulePrivate
{
public:
  qSlicerLiverResectionsModulePrivate();
};

//-----------------------------------------------------------------------------
// qSlicerLiverResectionsModulePrivate methods

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModulePrivate::qSlicerLiverResectionsModulePrivate()
{
}

//-----------------------------------------------------------------------------
// qSlicerLiverResectionsModule methods

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModule::qSlicerLiverResectionsModule(QObject* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverResectionsModulePrivate)
{
}

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModule::~qSlicerLiverResectionsModule()
{
}

bool qSlicerLiverResectionsModule::isHidden() const
{
    return true;
}

//-----------------------------------------------------------------------------
QString qSlicerLiverResectionsModule::helpText() const
{
  return "This module contains fundamental markups to be used in the Slicer-Liver extension.";
}

//-----------------------------------------------------------------------------
QString qSlicerLiverResectionsModule::acknowledgementText() const
{
  return "This work has been partially funded by The Research Council of Norway (grant nr. 311393)";
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsModule::contributors() const
{
  QStringList moduleContributors;
  moduleContributors << QString("Rafael Palomar (Oslo University Hospital / NTNU) ");
  moduleContributors << QString("Ole Vegard Solberg (SINTEF) ");
  moduleContributors << QString("Geir Arne Tangen (SINTEF) ");
  return moduleContributors;
}

//-----------------------------------------------------------------------------
QIcon qSlicerLiverResectionsModule::icon() const
{
  return QIcon(":/Icons/LiverResections.png");
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsModule::categories() const
{
  return QStringList() << "Liver";
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsModule::dependencies() const
{
  return QStringList() << "LiverMarkups";
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModule::setup()
{
  this->Superclass::setup();

  auto logic = vtkSlicerLiverResectionsLogic::SafeDownCast(this->logic());
  if (!logic)
    {
    qCritical() << Q_FUNC_INFO << ": cannot get Markups logic.";
    return;
    }

  // Register IO
  qSlicerIOManager* ioManager = qSlicerApplication::application()->ioManager();
  qSlicerLiverResectionsReader *markupsReader = new qSlicerLiverResectionsReader(logic, this);
  ioManager->registerIO(markupsReader);
  ioManager->registerIO(new qSlicerLiverResectionsWriter(this));
}

//-----------------------------------------------------------------------------
qSlicerAbstractModuleRepresentation* qSlicerLiverResectionsModule
::createWidgetRepresentation()
{
    return nullptr;
}

//-----------------------------------------------------------------------------
vtkMRMLAbstractLogic* qSlicerLiverResectionsModule::createLogic()
{
  return vtkSlicerLiverResectionsLogic::New();
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsModule::associatedNodeTypes() const
{
  return QStringList() << "vtkMRMLLiverResectionNode";
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModule::setMRMLScene(vtkMRMLScene* scene)
{
  Superclass::setMRMLScene(scene);
  vtkSlicerLiverResectionsLogic* logic =
    vtkSlicerLiverResectionsLogic::SafeDownCast(this->logic());
  if (!logic)
    {
    qCritical() << Q_FUNC_INFO << " failed: logic is invalid";
    return;
    }
}
