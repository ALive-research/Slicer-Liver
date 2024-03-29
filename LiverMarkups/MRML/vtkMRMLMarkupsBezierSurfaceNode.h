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

#ifndef __vtkmrmlmarkupsbeziersurfacenode_h_
#define __vtkmrmlmarkupsbeziersurfacenode_h_

#include "vtkSlicerLiverMarkupsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLMarkupsNode.h>
#include <vtkMRMLModelNode.h>

//VTK includes
#include <vtkSetGet.h>
#include <vtkWeakPointer.h>
#include <vtkMRMLScalarVolumeNode.h>

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_MRML_EXPORT vtkMRMLMarkupsBezierSurfaceNode
: public vtkMRMLMarkupsNode
{
public:
  static vtkMRMLMarkupsBezierSurfaceNode* New();
  vtkTypeMacro(vtkMRMLMarkupsBezierSurfaceNode, vtkMRMLMarkupsNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------------
  const char* GetIcon() override {return ":/Icons/MarkupsBezierSurface.png";}
  const char* GetAddIcon() override {return ":/Icons/MarkupsBezierSurfaceMouseModePlace.png";}
  const char* GetPlaceAddIcon() override {return ":/Icons/MarkupsBezierSurfaceMouseModePlaceAdd.png";}

  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model)
  const char* GetNodeTagName() override {return "MarkupsBezierSurface";}

  /// Get markup name
  const char* GetMarkupType() override {return "BezierSurface";}

  // Get markup type GUI display name
  const char* GetTypeDisplayName() override {return "Bezier Surface";};

  /// Get markup short name
  const char* GetDefaultNodeNamePrefix() override {return "BS";}

  /// Set the distance map
  void SetDistanceMapVolumeNode(vtkMRMLScalarVolumeNode* volumeNode)
  {this->DistanceMap = volumeNode; this->Modified();}

  /// Get the distance map
  vtkMRMLScalarVolumeNode* GetDistanceMapVolumeNode() const
  {return this->DistanceMap;}

  /// Set the Vascular Segments
  void SetVascularSegmentsVolumeNode(vtkMRMLScalarVolumeNode* volumeNode)
  {this->VascularSegments = volumeNode; this->Modified();}

  /// Get the Vascular Segments
  vtkMRMLScalarVolumeNode* GetVascularSegmentsVolumeNode() const
  {return this->VascularSegments;}

  /// Get the distance map margin
  vtkGetMacro(ResectionMargin, double);

  /// Set the distance map margin
  vtkSetMacro(ResectionMargin, double);

  /// Get the distance map margin
  vtkGetMacro(UncertaintyMargin, double);

  /// Set the distance map margin
  vtkSetMacro(UncertaintyMargin, double);

  /// Get the distance map margin
  vtkGetMacro(HepaticContourThickness, double);

  /// Set the distance map margin
  vtkSetMacro(HepaticContourThickness, double);

  /// Get the distance map margin
  vtkGetMacro(PortalContourThickness, double);

  /// Set the distance map margin
  vtkSetMacro(PortalContourThickness, double);

  /// \sa vtkMRMLNode::CopyContent
  vtkMRMLCopyContentDefaultMacro(vtkMRMLMarkupsBezierSurfaceNode);

  void CreateDefaultDisplayNodes() override;

protected:
  vtkMRMLMarkupsBezierSurfaceNode();
  ~vtkMRMLMarkupsBezierSurfaceNode() override = default;

private:
 vtkWeakPointer<vtkMRMLModelNode> Target;
 vtkWeakPointer<vtkMRMLScalarVolumeNode> DistanceMap;
 vtkWeakPointer<vtkMRMLScalarVolumeNode> VascularSegments;
 double ResectionMargin;
 double UncertaintyMargin;
 double HepaticContourThickness;
 double PortalContourThickness;

private:
 vtkMRMLMarkupsBezierSurfaceNode(const vtkMRMLMarkupsBezierSurfaceNode&);
 void operator=(const vtkMRMLMarkupsBezierSurfaceNode&);
};

#endif //__vtkmrmlmarkupsbeziersurfacenode_h_
