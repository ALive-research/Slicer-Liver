/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Implementation of vtkMRMLVolumetrySeedsDisplayNode — the data-only
  interaction-state carrier for the ADR-0038-amendment volumetry seed
  placement (ADR-0025 display-node template, ADR-0033 hover discipline).
  See the class docstring in the header for the field roster.

==============================================================================*/

// This module MRML includes
#include "vtkMRMLVolumetrySeedsDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLVolumetrySeedsDisplayNode);

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsDisplayNode::vtkMRMLVolumetrySeedsDisplayNode()
  // 3 mm reads clearly as a seed marker on a liver-scale surface without
  // occluding the anatomy under it (mirrors the territories highlight node).
  : Radius(3.0)
{
  this->TransientPoint[0] = 0.0;
  this->TransientPoint[1] = 0.0;
  this->TransientPoint[2] = 0.0;
}

//------------------------------------------------------------------------------
vtkMRMLVolumetrySeedsDisplayNode::~vtkMRMLVolumetrySeedsDisplayNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::SetTransientPoint(double x, double y, double z)
{
  // Guard against a redundant Modified() so a hover that lands on the same
  // sub-pixel point does not churn the Pipeline.
  if (this->TransientPoint[0] == x && this->TransientPoint[1] == y && this->TransientPoint[2] == z)
  {
    return;
  }
  this->TransientPoint[0] = x;
  this->TransientPoint[1] = y;
  this->TransientPoint[2] = z;
  this->Modified();
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  // TransientPoint is TRANSIENT (re-derived from the cursor every hover) and
  // is deliberately absent here; only the marker Radius round-trips (Color /
  // Visibility persist on the base).
  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLFloatMacro(radius, Radius);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLFloatMacro(radius, Radius);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::CopyContent(vtkMRMLNode* anode, bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyFloatMacro(Radius);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::SetAndObservePickSurfaceNodeID(const char* surfaceNodeID)
{
  this->SetAndObserveNodeReferenceID(this->GetPickSurfaceReferenceRole(), surfaceNodeID);
}

//------------------------------------------------------------------------------
vtkMRMLNode* vtkMRMLVolumetrySeedsDisplayNode::GetPickSurfaceNode()
{
  return this->GetNodeReference(this->GetPickSurfaceReferenceRole());
}

//------------------------------------------------------------------------------
void vtkMRMLVolumetrySeedsDisplayNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintVectorMacro(TransientPoint, double, 3);
  vtkMRMLPrintFloatMacro(Radius);
  vtkMRMLPrintEndMacro();
}
