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
#include "vtkMRMLMessageCollection.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

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
QString qSlicerLiverResectionsReader::description()const
{
  return "LiverResections";
}

//-----------------------------------------------------------------------------
qSlicerIO::IOFileType qSlicerLiverResectionsReader::fileType()const
{
  return QString("LiverResectionsFile");
}

//-----------------------------------------------------------------------------
QStringList qSlicerLiverResectionsReader::extensions()const
{
  return QStringList() << "LiverResections CSV (*.lrp.fcsv)";
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

  // pass to logic to do the loading
  this->userMessages()->ClearMessages();
  char * nodeIDs = d->LiverResectionsLogic->LoadLiverResection(std::string(fileName.toUtf8()),
                                                               std::string(name.toUtf8()),
                                                               this->userMessages());
  if (nodeIDs)
    {
    // returned a comma separated list of ids of the nodes that were loaded
    QStringList nodeIDList;
    char *ptr = strtok(nodeIDs, ",");

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
