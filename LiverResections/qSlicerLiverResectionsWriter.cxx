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

// This file was based on qSlicerMarkupsWriter.cxx in 3D Slicer

// Qt includes
#include <QDebug>

// QtGUI includes
#include "qSlicerLiverResectionsWriter.h"

// QTCore includes
#include "qSlicerCoreApplication.h"
#include "qSlicerCoreIOManager.h"

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLSceneViewNode.h>
#include "vtkMRMLLiverResectionCSVStorageNode.h"

#include <vtkMRMLStorageNode.h>

// VTK includes
#include <vtkStdString.h>
#include <vtkStringArray.h>

//----------------------------------------------------------------------------
qSlicerLiverResectionsWriter::qSlicerLiverResectionsWriter(QObject* parentObject)
  : qSlicerNodeWriter("LiverResections", QString("LiverResectionFile"), QStringList() << "vtkMRMLLiverResectionNode", true, parentObject)
{
}

//----------------------------------------------------------------------------
qSlicerLiverResectionsWriter::~qSlicerLiverResectionsWriter() = default;

//----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsWriter::extensions(vtkObject* vtkNotUsed(object))const
{
  QStringList supportedExtensions;

  // vtkNew<vtkMRMLLiverResectionsJsonStorageNode> jsonStorageNode;
  // const int formatCount = jsonStorageNode->GetSupportedWriteFileTypes()->GetNumberOfValues();
  // for (int formatIt = 0; formatIt < formatCount; ++formatIt)
  //   {
  //   vtkStdString format = jsonStorageNode->GetSupportedWriteFileTypes()->GetValue(formatIt);
  //   supportedExtensions << QString::fromStdString(format);
  //   }

  vtkNew<vtkMRMLLiverResectionCSVStorageNode> fcsvStorageNode;
  const int fidsFormatCount = fcsvStorageNode->GetSupportedWriteFileTypes()->GetNumberOfValues();
  for (int formatIt = 0; formatIt < fidsFormatCount; ++formatIt)
    {
    vtkStdString format = fcsvStorageNode->GetSupportedWriteFileTypes()->GetValue(formatIt);
    supportedExtensions << QString::fromStdString(format);
    }

  return supportedExtensions;
}

//----------------------------------------------------------------------------
void qSlicerLiverResectionsWriter::setStorageNodeClass(vtkMRMLStorableNode* storableNode, const QString& storageNodeClassName)
{
  if (!storableNode)
    {
    qCritical() << Q_FUNC_INFO << " failed: invalid storable node";
    return;
    }
  vtkMRMLScene* scene = storableNode->GetScene();
  if (!scene)
    {
    qCritical() << Q_FUNC_INFO << " failed: invalid scene";
    return;
    }

  vtkMRMLStorageNode* currentStorageNode = storableNode->GetStorageNode();
  std::string storageNodeClassNameStr = storageNodeClassName.toStdString();
  if (currentStorageNode != nullptr && currentStorageNode->IsA(storageNodeClassNameStr.c_str()))
    {
    // requested storage node class is the same as current class, there is nothing to do
    return;
    }

  // Create and use new storage node of the correct class
  vtkMRMLStorageNode* newStorageNode = vtkMRMLStorageNode::SafeDownCast(scene->AddNewNodeByClass(storageNodeClassNameStr));
  if (!newStorageNode)
    {
    qCritical() << Q_FUNC_INFO << " failed: cannot create new storage node of class " << storageNodeClassName;
    return;
    }
  storableNode->SetAndObserveStorageNodeID(newStorageNode->GetID());

  // Remove old storage node
  if (currentStorageNode)
    {
    scene->RemoveNode(currentStorageNode);
    }
}

//----------------------------------------------------------------------------
bool qSlicerLiverResectionsWriter::write(const qSlicerIO::IOProperties& properties)
{
  vtkMRMLStorableNode* node = vtkMRMLStorableNode::SafeDownCast(this->getNodeByID(properties["nodeID"].toString().toUtf8().data()));
  std::string fileName = properties["fileName"].toString().toStdString();

  vtkNew<vtkMRMLLiverResectionCSVStorageNode> fcsvStorageNode;
  std::string fcsvCompatibleFileExtension = fcsvStorageNode->GetSupportedFileExtension(fileName.c_str(), false, true);
  if (!fcsvCompatibleFileExtension.empty())
    {
    // fcsv file needs to be written
    this->setStorageNodeClass(node, "vtkMRMLLiverResectionCSVStorageNode");
    }
  // else
  //   {
  //   // json file needs to be written
  //   this->setStorageNodeClass(node, "vtkMRMLLiverResectionsJsonStorageNode");
  //   }

  return Superclass::write(properties);
}
