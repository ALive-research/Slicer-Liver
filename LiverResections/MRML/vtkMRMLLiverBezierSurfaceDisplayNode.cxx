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

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0013 §8 and ADR-0014 §1).

==============================================================================*/

// This module MRML includes
#include "vtkMRMLLiverBezierSurfaceDisplayNode.h"

// MRML includes
#include <vtkMRMLNodePropertyMacros.h>

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLLiverBezierSurfaceDisplayNode);

//------------------------------------------------------------------------------
vtkMRMLLiverBezierSurfaceDisplayNode::vtkMRMLLiverBezierSurfaceDisplayNode()
  : ResectionColor{ 1.0f, 1.0f, 1.0f }
  , ResectionGridColor{ 0.0f, 0.0f, 0.0f }
  , ResectionMarginColor{ 1.0f, 0.0f, 0.0f }
  , UncertaintyMarginColor{ 1.0f, 1.0f, 0.0f }
  , ResectionOpacity(1.0f)
  , GridVisibility(false)
  , GridDivisions(0.0f)
  , GridThickness(0.0f)
  , Grid3DVisibility(true)
  , Grid2DVisibility(false)
  , WidgetVisibility(true)
  , ClipOut(false)
  , InterpolatedMargins(false)
  , ShowResection2D(false)
  , MirrorDisplay(false)
{
}

//------------------------------------------------------------------------------
vtkMRMLLiverBezierSurfaceDisplayNode::~vtkMRMLLiverBezierSurfaceDisplayNode() = default;

//------------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayNode::WriteXML(ostream& of, int nIndent)
{
  Superclass::WriteXML(of, nIndent);

  vtkMRMLWriteXMLBeginMacro(of);
  vtkMRMLWriteXMLVectorMacro(resectionColor, ResectionColor, float, 3);
  vtkMRMLWriteXMLVectorMacro(resectionGridColor, ResectionGridColor, float, 3);
  vtkMRMLWriteXMLVectorMacro(resectionMarginColor, ResectionMarginColor, float, 3);
  vtkMRMLWriteXMLVectorMacro(uncertaintyMarginColor, UncertaintyMarginColor, float, 3);
  vtkMRMLWriteXMLFloatMacro(resectionOpacity, ResectionOpacity);
  vtkMRMLWriteXMLBooleanMacro(gridVisibility, GridVisibility);
  vtkMRMLWriteXMLFloatMacro(gridDivisions, GridDivisions);
  vtkMRMLWriteXMLFloatMacro(gridThickness, GridThickness);
  vtkMRMLWriteXMLBooleanMacro(grid3DVisibility, Grid3DVisibility);
  vtkMRMLWriteXMLBooleanMacro(grid2DVisibility, Grid2DVisibility);
  vtkMRMLWriteXMLBooleanMacro(widgetVisibility, WidgetVisibility);
  vtkMRMLWriteXMLBooleanMacro(clipOut, ClipOut);
  vtkMRMLWriteXMLBooleanMacro(interpolatedMargins, InterpolatedMargins);
  vtkMRMLWriteXMLBooleanMacro(showResection2D, ShowResection2D);
  vtkMRMLWriteXMLBooleanMacro(mirrorDisplay, MirrorDisplay);
  vtkMRMLWriteXMLEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayNode::ReadXMLAttributes(const char** atts)
{
  int disabledModify = this->StartModify();

  Superclass::ReadXMLAttributes(atts);

  vtkMRMLReadXMLBeginMacro(atts);
  vtkMRMLReadXMLVectorMacro(resectionColor, ResectionColor, float, 3);
  vtkMRMLReadXMLVectorMacro(resectionGridColor, ResectionGridColor, float, 3);
  vtkMRMLReadXMLVectorMacro(resectionMarginColor, ResectionMarginColor, float, 3);
  vtkMRMLReadXMLVectorMacro(uncertaintyMarginColor, UncertaintyMarginColor, float, 3);
  vtkMRMLReadXMLFloatMacro(resectionOpacity, ResectionOpacity);
  vtkMRMLReadXMLBooleanMacro(gridVisibility, GridVisibility);
  vtkMRMLReadXMLFloatMacro(gridDivisions, GridDivisions);
  vtkMRMLReadXMLFloatMacro(gridThickness, GridThickness);
  vtkMRMLReadXMLBooleanMacro(grid3DVisibility, Grid3DVisibility);
  vtkMRMLReadXMLBooleanMacro(grid2DVisibility, Grid2DVisibility);
  vtkMRMLReadXMLBooleanMacro(widgetVisibility, WidgetVisibility);
  vtkMRMLReadXMLBooleanMacro(clipOut, ClipOut);
  vtkMRMLReadXMLBooleanMacro(interpolatedMargins, InterpolatedMargins);
  vtkMRMLReadXMLBooleanMacro(showResection2D, ShowResection2D);
  vtkMRMLReadXMLBooleanMacro(mirrorDisplay, MirrorDisplay);
  vtkMRMLReadXMLEndMacro();

  this->EndModify(disabledModify);
}

//------------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayNode::CopyContent(vtkMRMLNode* anode,
                                                       bool deepCopy /*=true*/)
{
  MRMLNodeModifyBlocker blocker(this);
  Superclass::CopyContent(anode, deepCopy);

  vtkMRMLCopyBeginMacro(anode);
  vtkMRMLCopyVectorMacro(ResectionColor, float, 3);
  vtkMRMLCopyVectorMacro(ResectionGridColor, float, 3);
  vtkMRMLCopyVectorMacro(ResectionMarginColor, float, 3);
  vtkMRMLCopyVectorMacro(UncertaintyMarginColor, float, 3);
  vtkMRMLCopyFloatMacro(ResectionOpacity);
  vtkMRMLCopyBooleanMacro(GridVisibility);
  vtkMRMLCopyFloatMacro(GridDivisions);
  vtkMRMLCopyFloatMacro(GridThickness);
  vtkMRMLCopyBooleanMacro(Grid3DVisibility);
  vtkMRMLCopyBooleanMacro(Grid2DVisibility);
  vtkMRMLCopyBooleanMacro(WidgetVisibility);
  vtkMRMLCopyBooleanMacro(ClipOut);
  vtkMRMLCopyBooleanMacro(InterpolatedMargins);
  vtkMRMLCopyBooleanMacro(ShowResection2D);
  vtkMRMLCopyBooleanMacro(MirrorDisplay);
  vtkMRMLCopyEndMacro();
}

//------------------------------------------------------------------------------
void vtkMRMLLiverBezierSurfaceDisplayNode::PrintSelf(ostream& os, vtkIndent indent)
{
  this->Superclass::PrintSelf(os, indent);

  vtkMRMLPrintBeginMacro(os, indent);
  vtkMRMLPrintVectorMacro(ResectionColor, float, 3);
  vtkMRMLPrintVectorMacro(ResectionGridColor, float, 3);
  vtkMRMLPrintVectorMacro(ResectionMarginColor, float, 3);
  vtkMRMLPrintVectorMacro(UncertaintyMarginColor, float, 3);
  vtkMRMLPrintFloatMacro(ResectionOpacity);
  vtkMRMLPrintBooleanMacro(GridVisibility);
  vtkMRMLPrintFloatMacro(GridDivisions);
  vtkMRMLPrintFloatMacro(GridThickness);
  vtkMRMLPrintBooleanMacro(Grid3DVisibility);
  vtkMRMLPrintBooleanMacro(Grid2DVisibility);
  vtkMRMLPrintBooleanMacro(WidgetVisibility);
  vtkMRMLPrintBooleanMacro(ClipOut);
  vtkMRMLPrintBooleanMacro(InterpolatedMargins);
  vtkMRMLPrintBooleanMacro(ShowResection2D);
  vtkMRMLPrintBooleanMacro(MirrorDisplay);
  vtkMRMLPrintEndMacro();
}
