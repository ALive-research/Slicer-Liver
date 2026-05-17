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

#include "qSlicerLiverResectionsModule.h"

// Qt includes
#include <QDebug>

// Liver Resections Logic includes
#include "vtkSlicerLiverResectionsLogic.h"

// Liver Resections MRML includes
#include "qSlicerLiverResectionsWriter.h"
#include "qSlicerLiverResectionsReader.h"

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerCoreApplication.h>
#include <qSlicerCoreIOManager.h>
#include <qSlicerIOManager.h>
#include <qSlicerModuleManager.h>
#include <qSlicerNodeWriter.h>

// MRMLDisplayableManager includes
#include <vtkMRMLSliceViewDisplayableManagerFactory.h>
#include <vtkMRMLThreeDViewDisplayableManagerFactory.h>

// DisplayableManager initialization
#include <vtkAutoInit.h>
VTK_MODULE_INIT(vtkSlicerLiverResectionsModuleMRMLDisplayableManager)

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
qSlicerLiverResectionsModulePrivate::qSlicerLiverResectionsModulePrivate() {}

//-----------------------------------------------------------------------------
// qSlicerLiverResectionsModule methods

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModule::qSlicerLiverResectionsModule(QObject* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverResectionsModulePrivate)
{
}

//-----------------------------------------------------------------------------
qSlicerLiverResectionsModule::~qSlicerLiverResectionsModule() {}

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
  return QStringList() << "LiverMarkups" << "Markups";
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
  // Register displayable managers (same displayable manager handles both slice and 3D views)
  vtkMRMLSliceViewDisplayableManagerFactory::GetInstance()->RegisterDisplayableManager("vtkMRMLLiverResectionsDisplayableManager2D");

  // TODO(T2.6-DM): Register the LayerDM-aware widget displayable
  // manager for ``vtkMRMLBezierSurfaceNode`` once
  // ``vtkMRMLLiverBezierSurfaceDisplayableManager3D`` lands (ADR-0014
  // §3, ADR-0013 §5).  The DM is the C++ glue that observes the
  // scene for Bezier-surface nodes, spawns one
  // ``vtkLiverBezierWidget`` instance per (data node, view) pair,
  // and wires it to the view's interactor.  Until then the legacy
  // ``vtkSlicerMarkupsWidget`` path still drives Bezier interaction
  // via the in-tree ``vtkMRMLLiverResectionsDisplayableManager2D``
  // registered above.
  //
  // TODO(T2.6-LayerDM-Pipeline): Register the LayerDM Pipeline
  // creator for ``vtkMRMLBezierSurfaceDisplayNode`` once
  // ``LiverBezierSurfacePipeline.py`` has Python install rules + a
  // ``LayerDMLib`` runtime path (ADR-0013 §4, §5).  The registration
  // belongs in this ``setup()`` per ADR-0013's "user-facing module
  // hosts the registration" pattern — either via a
  // ``app->pythonManager()->executeString("import LiverResectionsLib")``
  // call (Markups precedent at ``qSlicerMarkupsModule::setup()``)
  // that delegates to a ``LiverResectionsLib`` Python module's
  // ``registerPipelineCreator()``, or directly via
  // ``vtkMRMLLayerDMPipelineScriptedCreator`` if the C++ headers
  // become reachable from this build.  Tracked as task T2.6-LayerDM
  // alongside the Python install glue and the soft-import → hard-
  // require swap in ``LiverBezierSurfacePipeline.py``.

  // Register IO
  qSlicerIOManager* ioManager = qSlicerApplication::application()->ioManager();
  qSlicerLiverResectionsReader* markupsReader = new qSlicerLiverResectionsReader(logic, this);
  ioManager->registerIO(markupsReader);
  ioManager->registerIO(new qSlicerLiverResectionsWriter(this));

  // T2 LiverResources storage I/O (ADR-0014 §5).  The new
  // ``vtkMRMLBezierSurfaceStorageNode`` reads + writes ``.lrp.json``
  // (and reads legacy ``.lrp.fcsv`` for migration).  A dedicated
  // ``qSlicerNodeWriter`` registers the write path with the Save Data
  // dialog and binds it to the new data node class.  The legacy
  // ``qSlicerLiverResectionsReader`` (registered above) grew a
  // ``.lrp.json`` dispatch branch so the Add Data dialog opens new
  // plans into a ``vtkMRMLBezierSurfaceNode``.
  qSlicerCoreIOManager* coreIOManager = qSlicerCoreApplication::application()->coreIOManager();
  if (coreIOManager)
  {
    coreIOManager->registerIO(new qSlicerNodeWriter("BezierSurface",
                                                    QString("BezierSurfaceFile"),
                                                    QStringList() << "vtkMRMLBezierSurfaceNode",
                                                    /*supportUseCompression=*/true,
                                                    this));
  }
}

//-----------------------------------------------------------------------------
qSlicerAbstractModuleRepresentation* qSlicerLiverResectionsModule ::createWidgetRepresentation()
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
  vtkSlicerLiverResectionsLogic* logic = vtkSlicerLiverResectionsLogic::SafeDownCast(this->logic());
  if (!logic)
  {
    qCritical() << Q_FUNC_INFO << " failed: logic is invalid";
    return;
  }
}
