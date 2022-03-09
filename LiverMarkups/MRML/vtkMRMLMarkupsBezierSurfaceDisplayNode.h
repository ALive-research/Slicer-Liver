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

#ifndef __vtkmrmlmarkupsbeziersurfacedisplaynode_h_
#define __vtkmrmlmarkupsbeziersurfacedisplaynode_h_

#include "vtkSlicerLiverMarkupsModuleMRMLExport.h"

#include <vtkMRMLMarkupsDisplayNode.h>

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_MRML_EXPORT vtkMRMLMarkupsBezierSurfaceDisplayNode
: public vtkMRMLMarkupsDisplayNode
{
 public:
  static vtkMRMLMarkupsBezierSurfaceDisplayNode* New();
  vtkTypeMacro(vtkMRMLMarkupsBezierSurfaceDisplayNode, vtkMRMLMarkupsDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------

  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Markups)
  const char* GetNodeTagName() override { return "MarkupsBezierSurfaceDisplay"; };


  //--------------------------------------------------------------------------
  // MarkupsBezierSurfaceDisplay methods
  //--------------------------------------------------------------------------

  /// Set the clipout state variable
  vtkSetMacro(ClipOut, bool);
  /// Get the clipout state variable
  vtkGetMacro(ClipOut, bool);
  /// Get the clipout state variable as integer
  int GetClipOut() const
  { return static_cast<int>(this->ClipOut);}
  /// set the clipout state variable as integer
  void SetClipOut(int value)
  { this->ClipOut = value!=0?1:0; this->Modified();}

  /// Set the clipout state variable
  vtkSetMacro(WidgetVisibility, bool);
  /// Get the clipout state variable
  vtkGetMacro(WidgetVisibility, bool);
  /// Get the clipout state variable as integer
  int GetWidgetVisibility() const
  { return static_cast<int>(this->WidgetVisibility);}
  /// set the clipout state variable as integer
  void SetWidgetVisibility(int value)
  { this->WidgetVisibility = value!=0?1:0; this->Modified();}

protected:
  bool ClipOut;
  bool WidgetVisibility;

protected:
  vtkMRMLMarkupsBezierSurfaceDisplayNode();
  ~vtkMRMLMarkupsBezierSurfaceDisplayNode() override;
  vtkMRMLMarkupsBezierSurfaceDisplayNode( const vtkMRMLMarkupsBezierSurfaceDisplayNode& );
  void operator= ( const vtkMRMLMarkupsBezierSurfaceDisplayNode& );
};


#endif // __vtkmrmlmarkupsbeziersurfacedisplaynode_h_
