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

// This file was based on qSlicerMarkupsReader.cxx in 3D Slicer
//

// Qt includes
#include <QFileInfo>

// Slicer includes
#include "qSlicerLiverResectionsReader.h"

// Logic includes
#include <vtkSlicerApplicationLogic.h>
#include "vtkSlicerLiverResectionsLogic.h"

// MRML includes
#include "vtkMRMLAbstractParametricSurfaceNode.h"
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLMessageCollection.h"
#include "vtkMRMLResectionPlanNode.h"
#include "vtkMRMLResectionPlanStorageNode.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkCommand.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtksys/SystemTools.hxx>

//-----------------------------------------------------------------------------
class qSlicerLiverResectionsReaderPrivate
{
public:
  vtkSmartPointer<vtkSlicerLiverResectionsLogic> LiverResectionsLogic;
};

//-----------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_Annotations
//-----------------------------------------------------------------------------
qSlicerLiverResectionsReader::qSlicerLiverResectionsReader(QObject* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverResectionsReaderPrivate)
{
}

qSlicerLiverResectionsReader::qSlicerLiverResectionsReader(vtkSlicerLiverResectionsLogic* logic, QObject* _parent)
  : Superclass(_parent)
  , d_ptr(new qSlicerLiverResectionsReaderPrivate)
{
  this->setLiverResectionsLogic(logic);
}

//-----------------------------------------------------------------------------
qSlicerLiverResectionsReader::~qSlicerLiverResectionsReader() = default;

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsReader::setLiverResectionsLogic(vtkSlicerLiverResectionsLogic* logic)
{
  Q_D(qSlicerLiverResectionsReader);
  d->LiverResectionsLogic = logic;
}

//-----------------------------------------------------------------------------
vtkSlicerLiverResectionsLogic* qSlicerLiverResectionsReader::liverResectionsLogic() const
{
  Q_D(const qSlicerLiverResectionsReader);
  return d->LiverResectionsLogic.GetPointer();
}

//-----------------------------------------------------------------------------
QString qSlicerLiverResectionsReader::description() const
{
  return "LiverResections";
}

//-----------------------------------------------------------------------------
qSlicerIO::IOFileType qSlicerLiverResectionsReader::fileType() const
{
  return QString("LiverResectionsFile");
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsReader::extensions() const
{
  // ``.lrp.json`` is the v1 schema landed by the prior T2.5 commit
  // (ADR-0014 §5).  The Add Data filter entry was previously
  // withheld pending T2.6-LayerDM — without a Pipeline registered
  // for ``vtkMRMLParametricSurfaceDisplayNode``, a user-driven Add Data
  // → ``.lrp.json`` would load silently with no rendering.  T2.6-
  // LayerDM closes that gap: ``qSlicerLiverResectionsModule::setup()``
  // now performs ADR-0013 §5's three-call contract, so the upstream
  // ``vtkMRMLLayerDisplayableManager`` instantiates the
  // ``LiverBezierSurfacePipeline`` for every Bezier-surface display
  // node in the scene.  Re-enabling the filter here lets Add Data
  // round-trip to a visible surface.
  //
  // The legacy ``.lrp.fcsv`` stays for load-only migration; writes
  // always emit ``.lrp.json`` via the dedicated ``qSlicerNodeWriter``
  // registered in ``qSlicerLiverResectionsModule::setup()``.
  return QStringList() << "Liver resection plan (*.lrp.json)"
                       << "LiverResections CSV (*.lrp.fcsv)";
}

//-----------------------------------------------------------------------------
bool qSlicerLiverResectionsReader::load(const IOProperties& properties)
{
  Q_D(qSlicerLiverResectionsReader);

  // get the properties
  Q_ASSERT(properties.contains("fileName"));
  QString fileName = properties["fileName"].toString();

  QString name;
  if (properties.contains("name"))
  {
    name = properties["name"].toString();
  }

  if (d->LiverResectionsLogic.GetPointer() == nullptr)
  {
    return false;
  }

  this->userMessages()->ClearMessages();

  // Dispatch on extension.  ``.lrp.json`` is the plan-rooted v2
  // format introduced by the 2026-05-25 wrapper-vs-carrier amendment
  // to ADR-0014 §"Fourth layer" + ADR-0023 §"Persistence"; loading
  // creates a ``vtkMRMLResectionPlanNode`` and routes through the
  // plan storage node.  The storage node's reader walks the
  // ``surface.type`` discriminator and instantiates the right
  // concrete surface subclass into the scene.
  // A legacy v1 ``.lrp.fcsv`` is migrated seamlessly through the same
  // plan-storage path: ``vtkMRMLResectionPlanStorageNode::ReadData``
  // detects the legacy extension and lifts the 16 Bezier control points
  // into a v2 plan + carrier (see that node's §"Legacy `.lrp.fcsv`"
  // and Docs/migrations/v1-to-v2.md).  Both extensions therefore yield
  // a ``vtkMRMLResectionPlanNode`` that the LayerDM Pipeline renders.
  const QString lowerName = fileName.toLower();
  if (lowerName.endsWith(".lrp.json") || lowerName.endsWith(".lrp.fcsv"))
  {
    vtkMRMLScene* scene = d->LiverResectionsLogic->GetMRMLScene();
    if (!scene)
    {
      this->setLoadedNodes(QStringList());
      return false;
    }

    const std::string nodeNameStr = name.isEmpty()
                                      ? vtksys::SystemTools::GetFilenameWithoutExtension(vtksys::SystemTools::GetFilenameWithoutExtension(std::string(fileName.toUtf8())))
                                      : std::string(name.toUtf8());

    auto planNode = vtkMRMLResectionPlanNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLResectionPlanNode", nodeNameStr));
    auto storageNode = vtkMRMLResectionPlanStorageNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLResectionPlanStorageNode"));
    if (!planNode || !storageNode)
    {
      if (planNode)
      {
        scene->RemoveNode(planNode);
      }
      if (storageNode)
      {
        scene->RemoveNode(storageNode);
      }
      this->setLoadedNodes(QStringList());
      return false;
    }
    storageNode->SetFileName(fileName.toUtf8().constData());
    planNode->SetAndObserveStorageNodeID(storageNode->GetID());

    const int readResult = storageNode->ReadData(planNode);
    if (!readResult)
    {
      this->userMessages()->AddMessages(storageNode->GetUserMessages());
      vtkMRMLAbstractParametricSurfaceNode* createdSurface = planNode->GetGeometryNode();
      if (createdSurface != nullptr)
      {
        scene->RemoveNode(createdSurface);
      }
      scene->RemoveNode(planNode);
      scene->RemoveNode(storageNode);
      this->setLoadedNodes(QStringList());
      return false;
    }

    // Display-side decoration (margin / grid / colour) lives on a
    // separate display node per ADR-0013 §8.  The storage path does
    // not synthesise display nodes; trigger the surface's default
    // display-node creation now so the LayerDM Pipeline (registered
    // in qSlicerLiverResectionsModule::setup per ADR-0013 §5) picks
    // up the loaded surface.
    vtkMRMLAbstractParametricSurfaceNode* surfaceNode = planNode->GetGeometryNode();
    if (surfaceNode != nullptr)
    {
      surfaceNode->CreateDefaultDisplayNodes();
    }

    this->setLoadedNodes(QStringList() << QString(planNode->GetID()));
    return true;
  }

  // No other extension is advertised by supportedFileTypes(); both the
  // v2 ``.lrp.json`` and the legacy v1 ``.lrp.fcsv`` route through the
  // plan-storage path above.  The old vtkMRMLLiverResectionNode-family
  // loader is intentionally no longer reached from here.
  this->userMessages()->AddMessage(vtkCommand::ErrorEvent, (QString("Unsupported file extension for '%1'").arg(fileName)).toUtf8().constData());
  this->setLoadedNodes(QStringList());
  return false;
}
