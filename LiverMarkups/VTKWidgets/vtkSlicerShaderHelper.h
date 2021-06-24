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

  * Neither the name of Oslo University Hospital nor the names
    of Contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef vtkslicershaderhelper_h_
#define vtkslicershaderhelper_h_

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// MRML includes
#include <vtkMRMLModelNode.h>

// VTK includes
#include <vtkActor.h>
#include <vtkCollection.h>
#include <vtkObject.h>
#include <vtkWeakPointer.h>

//------------------------------------------------------------------------------
class vtkCollection;
class vtkMRMLModelNode;
class vtkShaderProperty;

//------------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkSlicerShaderHelper
: public vtkObject
{
public:
  static vtkSlicerShaderHelper* New();
  vtkTypeMacro(vtkSlicerShaderHelper, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  void SetTargetModelNode(vtkMRMLModelNode* modelNode){this->TargetModelNode = modelNode;}
  vtkMRMLModelNode* GetTargetModelNode(){return this->TargetModelNode;}
  vtkCollection* GetTargetModelVertexVBOs(){return this->TargetModelVertexVBOs;}
  vtkCollection* GetTargetActors(){return this->TargetModelActors;}
  void AttachContourShader();

protected:
  vtkWeakPointer<vtkMRMLModelNode> TargetModelNode;
  vtkNew<vtkCollection> TargetModelVertexVBOs;
  vtkNew<vtkCollection> TargetModelActors;

protected:
  vtkSlicerShaderHelper();
  ~vtkSlicerShaderHelper() = default;

private:
  void getShaderProperties(vtkCollection* propertiesCollection);

private:
  vtkSlicerShaderHelper(const vtkSlicerShaderHelper&) = delete;
  void operator=(const vtkSlicerShaderHelper&) = delete;
};

#endif // vtkslicershaderhelper_h_
