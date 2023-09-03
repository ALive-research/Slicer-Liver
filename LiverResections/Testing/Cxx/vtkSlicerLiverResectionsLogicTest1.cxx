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

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

// NOTE: This file is inspired in vtkSlicerMarkupsLogicTest1.cxx from 3D Slicer

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTKSlicer includes
#include "vtkSlicerLiverResectionsLogic.h"
#include <vtkMRMLLiverResectionNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtkSphereSource.h>

// STD includes
#include <cstdlib>

namespace
{
    void checkAddAndGetNode(vtkSmartPointer<vtkMRMLScene> scene, const char* ClassName)
    {
        auto node = scene->GetFirstNodeByClass(ClassName);
        assert(node == nullptr);

        std::string newNodeName = ClassName;
        newNodeName.append("_Test");
        scene->AddNewNodeByClass(ClassName, newNodeName);
        node = scene->GetFirstNodeByClass(ClassName);
        assert(node != nullptr);

        auto node2 = scene->GetNodeByID(node->GetID());
        assert(node2 != nullptr);
        assert(node == node2);
    }
}

int vtkSlicerLiverResectionsLogicTest1(int, char * [])
{
  auto scene = vtkSmartPointer<vtkMRMLScene>::New();

  vtkNew<vtkSlicerLiverResectionsLogic> logic1;

  logic1->SetMRMLScene(scene);

  //Add and get nodes
  checkAddAndGetNode(scene, "vtkMRMLLiverResectionNode");
  checkAddAndGetNode(scene, "vtkMRMLLiverResectionCSVStorageNode");

  vtkNew<vtkMRMLModelNode> targetOrgan;
  vtkNew<vtkSphereSource> source;
  targetOrgan->SetPolyDataConnection(source->GetOutputPort());


  return EXIT_SUCCESS;
}
