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
#include "qSlicerLiverResectionsReader.h"

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerCoreApplication.h>
#include <qSlicerCoreIOManager.h>
#include <qSlicerIOManager.h>
#include <qSlicerModuleManager.h>
#include <qSlicerNodeWriter.h>
#include <qSlicerPythonManager.h>

// LayerDM includes — ADR-0013 §5 calls 2 + 3 wiring.  The Pipeline
// creator (call 3) is registered from Python — see
// ``LiverResectionsLib.registerPipelineCreator`` — to keep the
// scripted-pipeline class identity on the Python side per ADR-0004.
#include <vtkMRMLLayerDisplayableManager.h>

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
  // ADR-0013 §5 call 2 — register the upstream LayerDM-aware
  // generic displayable manager with the 2D + 3D view factories.
  // Idempotent: ``vtkMRMLLayerDisplayableManager::RegisterInFactory``
  // guards on ``IsRegisteredInFactory`` and is a no-op when another
  // LayerDM-aware module already registered the DM for a given
  // factory, so multiple LayerDM-aware modules can coexist without
  // conflict.  ``RegisterInDefaultViews`` covers both view factories
  // in one call — the equivalent invocation in upstream
  // ``qSlicerLayerDMModule::setup()`` is the canonical precedent.
  vtkMRMLLayerDisplayableManager::RegisterInDefaultViews();

  // ADR-0013 §5 call 3 — register the LayerDM Pipeline creator for
  // ``vtkMRMLParametricSurfaceDisplayNode`` via the
  // scripted-creator bridge.  The creator lambda is defined in
  // ``LiverResectionsLib.LiverBezierSurfacePipeline`` (per ADR-0004
  // §1 the Pipeline class is Python; per ADR-0013 §1 there is exactly
  // one Pipeline per display-node type).  Delegating the call to the
  // Python side via ``qSlicerPythonManager::executeString`` keeps the
  // ``vtkMRMLLayerDMPipelineScriptedCreator``'s
  // ``SetPythonCallback`` argument as a Python callable — the upstream
  // ``CustomVR`` example sets the same precedent.  Idempotent via the
  // module-level ``_REGISTERED`` flag inside
  // ``registerPipelineCreator()``: the factory's
  // ``ContainsPipelineCreator`` compares creators by smart-pointer
  // identity, and a fresh scripted-creator is constructed on each
  // call, so the Python-side flag is the load-bearing idempotency
  // guard (factory-side guard cannot short-circuit our pointer-fresh
  // duplicates).
  //
  // Defensive wrapping: in test harnesses that launch Slicer without
  // the upstream LayerDM extension on the module path (notably the
  // CTest-generated ``qSlicerLiverResectionsModuleGenericTest``,
  // which uses the bare Slicer launcher rather than
  // ``SlicerWithSlicerLiver``), the import of ``LayerDMLib`` fails
  // because ``vtkMRMLLayerDMPipelineI`` is not reachable from
  // ``slicer``.  We catch the ImportError narrowly and emit at
  // ``logging.critical`` rather than ``warning``: ADR-0002 commits
  // LayerDM as a hard runtime dependency, so a missing LayerDM in a
  // production launch is a real configuration error that should be
  // loud in the log.  The test harness emits the same critical log
  // (CTest does not fail on log level by default), and the rest of
  // ``setup()`` continues so IO registration etc. still run.
  if (qSlicerApplication* app = qSlicerApplication::application())
  {
    if (qSlicerPythonManager* pythonManager = app->pythonManager())
    {
      pythonManager->executeString("try:\n"
                                   "    import LiverResectionsLib\n"
                                   "    LiverResectionsLib.registerPipelineCreator()\n"
                                   "    LiverResectionsLib.registerResectogramPipelineCreator()\n"
                                   "    LiverResectionsLib.registerControlPolygonPipelineCreator()\n"
                                   "except ImportError as exc:\n"
                                   "    import logging\n"
                                   "    logging.critical('LiverResections: LayerDM Pipeline creator not registered (%s)'\n"
                                   "                     ' — vtkMRMLBezierSurfaceNode rendering disabled in this'\n"
                                   "                     ' session.  Loading the SlicerLayerDisplayableManager'\n"
                                   "                     ' extension is required for the Pipeline path.', exc)\n");
    }
  }

  // Register IO
  qSlicerIOManager* ioManager = qSlicerApplication::application()->ioManager();
  qSlicerLiverResectionsReader* markupsReader = new qSlicerLiverResectionsReader(logic, this);
  ioManager->registerIO(markupsReader);

  // Resection-plan storage I/O (2026-05-25 wrapper-vs-carrier amendment
  // to ADR-0014 §"Fourth layer" + ADR-0023 §"Persistence").  The plan
  // node is the rooted storable; the storage node serialises both the
  // plan's clinical fields AND the referenced surface's geometry in a
  // single ``.lrp.json`` document.  A dedicated ``qSlicerNodeWriter``
  // registers the write path with the Save Data dialog and binds it
  // to the plan-node class.  The ``qSlicerLiverResectionsReader``
  // (registered above) dispatches ``.lrp.json`` to the same path.
  qSlicerCoreIOManager* coreIOManager = qSlicerCoreApplication::application()->coreIOManager();
  if (coreIOManager)
  {
    coreIOManager->registerIO(new qSlicerNodeWriter("ResectionPlan",
                                                    QString("ResectionPlanFile"),
                                                    QStringList() << "vtkMRMLResectionPlanNode",
                                                    /*supportUseCompression=*/true,
                                                    this));
  }
}

//-----------------------------------------------------------------------------
qSlicerAbstractModuleRepresentation* qSlicerLiverResectionsModule ::createWidgetRepresentation()
{
  // ADR-0004 — the Stage-4 "Resection Planning" GUI is Python
  // (LiverResectionsLib.ResectionPlanningWidget), composed directly by
  // Liver/Liver.py.  This loadable module is data-only (MRML nodes + logic +
  // I/O) and ships no C++ widget representation.
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
  return QStringList() << "vtkMRMLResectionPlanNode";
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
