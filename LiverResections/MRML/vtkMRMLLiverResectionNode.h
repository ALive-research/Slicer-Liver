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

#ifndef __vtkmrmlliverresectionnode_h_
#define __vtkmrmlliverresectionnode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLModelNode.h>

//VTK includes
#include <vtkWeakPointer.h>
#include <vtkCollection.h>

//STD includes
#include <set>
#include <string>

//-----------------------------------------------------------------------------
class vtkMRMLSegmentationNode;

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLLiverResectionNode
: public vtkMRMLNode
{
public:
  static vtkMRMLLiverResectionNode* New();
  vtkTypeMacro(vtkMRMLLiverResectionNode, vtkMRMLNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  // Possible resection states
  enum ResectionStatus
    {
      Initialization,
      Deformation,
      Completed
    };

  //--------------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model)
  const char* GetNodeTagName() override {return "LiverResection";}

  /// \sa vtkMRMLNode::CopyContent
  vtkMRMLCopyContentDefaultMacro(vtkMRMLLiverResectionNode);

  /// Get a pointer to the target organ
  std::string GetTargetOrganID() const {return this->TargetOrganID;}
  /// Set the target organ
  void SetTargetOrganID(const std::string targetOrganID)
  {this->TargetOrganID = targetOrganID; this->Modified();}

  /// Get the resection status
  ResectionStatus GetResectionStatus() const {return this->Status;}
  /// Get the resection status
  void SetResectionstatus(ResectionStatus status)
  {this->Status = status; this->Modified();}

  /// Get target lesions identifiers
  std::set<std::string> GetTargetLesionsIDs() const {return this->TargetLesionsIDs;}
  /// Add a new lesion identifier
  void AddTargetLesionID(const std::string& lesionID)
  {this->TargetLesionsIDs.insert(lesionID); this->Modified();}
  /// Remove a lesion identifier
  void RemoveTargetLesionID(const std::string& lesionID)
  {this->TargetLesionsIDs.erase(lesionID); this->Modified();}

  // Get resection margin
  vtkGetMacro(ResectionMargin, float);
  // Get resection margin
  vtkSetMacro(ResectionMargin, float);

protected:
  vtkMRMLLiverResectionNode();
  ~vtkMRMLLiverResectionNode() override = default;

private:
  vtkWeakPointer<vtkMRMLSegmentationNode> SegmentationNode;
  std::string TargetOrganID;
  std::set<std::string> TargetLesionsIDs;
  ResectionStatus Status;
  float ResectionMargin; //Resection margin in mm

private:
 vtkMRMLLiverResectionNode(const vtkMRMLLiverResectionNode&);
 void operator=(const vtkMRMLLiverResectionNode&);
};

#endif //__vtkmrmlliverresectionnode_h_
