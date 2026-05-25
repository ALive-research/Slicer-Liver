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
#include "vtkMRMLBezierSurfaceNode.h"
#include "vtkMRMLBezierSurfaceStorageNode.h"
#include "vtkMRMLMessageCollection.h"
#include "vtkMRMLScene.h"

// VTK includes
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

  // Dispatch on extension.  ``.lrp.json`` is the v1 format committed by
  // T2.5 / ADR-0014 §5; loading routes through the new
  // ``vtkMRMLBezierSurfaceStorageNode`` directly.  ``.lrp.fcsv`` (and
  // any other legacy extension) falls through to the existing
  // logic-side loader that produces a ``vtkMRMLLiverResectionNode``.
  const QString lowerName = fileName.toLower();
  if (lowerName.endsWith(".lrp.json"))
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

    auto surfaceNode = vtkMRMLBezierSurfaceNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLBezierSurfaceNode", nodeNameStr));
    auto storageNode = vtkMRMLBezierSurfaceStorageNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLBezierSurfaceStorageNode"));
    if (!surfaceNode || !storageNode)
    {
      if (surfaceNode)
      {
        scene->RemoveNode(surfaceNode);
      }
      if (storageNode)
      {
        scene->RemoveNode(storageNode);
      }
      this->setLoadedNodes(QStringList());
      return false;
    }
    storageNode->SetFileName(fileName.toUtf8().constData());
    surfaceNode->SetAndObserveStorageNodeID(storageNode->GetID());

    const int readResult = storageNode->ReadData(surfaceNode);
    if (!readResult)
    {
      this->userMessages()->AddMessages(storageNode->GetUserMessages());
      scene->RemoveNode(surfaceNode);
      scene->RemoveNode(storageNode);
      this->setLoadedNodes(QStringList());
      return false;
    }

    // ADR-0013 §8 — the display-side decoration (margin / grid /
    // colour) lives on a separate display node.  Neither
    // ``vtkMRMLBezierSurfaceStorageNode::ReadDataInternal`` nor the
    // base ``vtkMRMLStorageNode::ReadData`` create a display node.
    // Without this call the loaded surface lands with no display
    // node attached; the eventual LayerDM Pipeline (registered when
    // the SlicerLayerDM library is reachable in the build, per
    // ADR-0013 §5's three-call registration contract) needs a
    // display node to drive the actor pipeline from.
    surfaceNode->CreateDefaultDisplayNodes();

    this->setLoadedNodes(QStringList() << QString(surfaceNode->GetID()));
    return true;
  }

  // Legacy ``.lrp.fcsv`` (and any other recognised extension) — delegate
  // to the existing logic-side loader (load-only migration; ADR-0014
  // §5 retires writes of this format).
  char* nodeIDs = d->LiverResectionsLogic->LoadLiverResection(std::string(fileName.toUtf8()), std::string(name.toUtf8()), this->userMessages());
  if (nodeIDs)
  {
    // returned a comma separated list of ids of the nodes that were loaded
    QStringList nodeIDList;
    char* ptr = strtok(nodeIDs, ",");

    while (ptr)
    {
      nodeIDList.append(ptr);
      ptr = strtok(nullptr, ",");
    }
    this->setLoadedNodes(nodeIDList);
  }
  else
  {
    this->setLoadedNodes(QStringList());
    return false;
  }

  return nodeIDs != nullptr;
}
