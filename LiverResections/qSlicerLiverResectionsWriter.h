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

// This file was based on qSlicerMarkupsWriter.h in 3D Slicer
//
#ifndef __qslicerliverresectionswriter_h
#define __qslicerliverresectionswriter_h


// QtCore includes
#include "qSlicerLiverResectionsModuleExport.h"
#include "qSlicerNodeWriter.h"

class vtkMRMLNode;
class vtkMRMLStorableNode;

/// Utility class that offers writing of markups in both json format, regardless of the current storage node.
class Q_SLICER_QTMODULES_LIVERRESECTIONS_EXPORT qSlicerLiverResectionsWriter
  : public qSlicerNodeWriter
{
  Q_OBJECT
public:
  typedef qSlicerNodeWriter Superclass;
  qSlicerLiverResectionsWriter(QObject* parent);
  ~qSlicerLiverResectionsWriter() override;

  QStringList extensions(vtkObject* object)const override;

  bool write(const qSlicerIO::IOProperties& properties) override;

  void setStorageNodeClass(vtkMRMLStorableNode* storableNode, const QString& storageNodeClassName);

private:
  Q_DISABLE_COPY(qSlicerLiverResectionsWriter);
};

#endif // __qslicerliverresectionswriter_h
