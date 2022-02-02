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

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLLiverResectionNode.h"
#include "vtkMRMLModelNode.h"
#include "vtkMRMLScalarVolumeNode.h"
#include "vtkMRMLScene.h"


// VTK includes
#include <vtkNew.h>
#include <vtkType.h>

//------------------------------------------------------------------------------
int vtkMRMLLiverResectionNodeTest1(int, char *[])
{
  vtkNew<vtkMRMLLiverResectionNode> node1;
  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLModelNode> modelNode;
  vtkNew<vtkMRMLScalarVolumeNode> volumeNode;

  EXERCISE_ALL_BASIC_MRML_METHODS(node1.GetPointer());

  // Test value setting/getting in resection margin
  TEST_SET_GET_DOUBLE_RANGE(node1, ResectionMargin, 1.0, VTK_DOUBLE_MAX);

  // Test value setting/getting in resection state
  TEST_SET_GET_VALUE(node1, State, vtkMRMLLiverResectionNode::Initialization);
  TEST_SET_GET_VALUE(node1, State, vtkMRMLLiverResectionNode::Deformation);
  TEST_SET_GET_VALUE(node1, State, vtkMRMLLiverResectionNode::Completed);

  // Test value setting/getting in organ model
  TEST_SET_GET_VALUE(node1, TargetOrganModelNode, modelNode.GetPointer());

  // Test value setting/getting in distance map
  TEST_SET_GET_VALUE(node1, DistanceMapVolumeNode, volumeNode.GetPointer());

  // Test value setting/getting in distance map
  TEST_SET_GET_VALUE(node1, InitMode, vtkMRMLLiverResectionNode::Flat);
  TEST_SET_GET_VALUE(node1, InitMode, vtkMRMLLiverResectionNode::Curved);
  // Test value setting/getting in distance map

  return EXIT_SUCCESS;
}
