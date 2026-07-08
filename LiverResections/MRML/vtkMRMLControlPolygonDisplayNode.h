/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

  This file was originally developed for the Slicer-Liver extension as
  part of the control-polygon display aspect (see ADR-0033).

==============================================================================*/

#ifndef __vtkmrmlcontrolpolygondisplaynode_h_
#define __vtkmrmlcontrolpolygondisplaynode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

/**
 * \class vtkMRMLControlPolygonDisplayNode
 *
 * \brief Display node for the parametric surface's control polygon.
 *
 * Per ADR-0033 the control polygon — the ``Rows x Cols`` control-point
 * handles plus their connecting edges — is a first-class display aspect
 * of the parametric-surface carrier, distinct from the surface itself:
 * it has its own visual properties, hosts the per-point drag
 * interaction, and is shown/hidden independently of the surface.  The
 * carrier's ``CreateDefaultDisplayNodes`` therefore mints TWO display
 * nodes (MRML's one-displayable-many-display-nodes pattern): the
 * ``vtkMRMLParametricSurfaceDisplayNode`` keying the surface Pipeline
 * and THIS node keying the ``ControlPolygonPipeline``
 * (ADR-0013 §1: one LayerDM Pipeline per display-node type).
 *
 * \par Field roster
 *
 *   - ``HandleRadius`` — control-point handle sphere radius in world
 *     units (default 2.5, matching the retired v1 widget's glyph
 *     radius).
 *   - ``HandleColor`` — handle sphere colour.
 *   - ``EdgeColor`` — polygon edge colour.
 *   - ``EdgeWidth`` — polygon edge line width in pixels.
 *
 * Base ``vtkMRMLDisplayNode`` supplies the independent ``Visibility``
 * and per-view ``ViewNodeIDs`` (ADR-0033 §Decision 1).
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLControlPolygonDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLControlPolygonDisplayNode* New();
  vtkTypeMacro(vtkMRMLControlPolygonDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).
  const char* GetNodeTagName() override { return "ControlPolygonDisplay"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content (excludes basic data, such as name and node references).
  /// \sa vtkMRMLNode::CopyContent
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Control-polygon display fields (ADR-0033)
  //--------------------------------------------------------------------------

  /// Control-point handle sphere radius, world units.
  vtkSetMacro(HandleRadius, double);
  vtkGetMacro(HandleRadius, double);

  /// Control-point handle colour.
  vtkSetVector3Macro(HandleColor, double);
  vtkGetVector3Macro(HandleColor, double);

  /// Polygon edge colour.
  vtkSetVector3Macro(EdgeColor, double);
  vtkGetVector3Macro(EdgeColor, double);

  /// Polygon edge line width, pixels.
  vtkSetMacro(EdgeWidth, double);
  vtkGetMacro(EdgeWidth, double);

protected:
  vtkMRMLControlPolygonDisplayNode();
  ~vtkMRMLControlPolygonDisplayNode() override;

private:
  vtkMRMLControlPolygonDisplayNode(const vtkMRMLControlPolygonDisplayNode&) = delete;
  void operator=(const vtkMRMLControlPolygonDisplayNode&) = delete;

  double HandleRadius;
  double HandleColor[3];
  double EdgeColor[3];
  double EdgeWidth;
};

#endif //__vtkmrmlcontrolpolygondisplaynode_h_
