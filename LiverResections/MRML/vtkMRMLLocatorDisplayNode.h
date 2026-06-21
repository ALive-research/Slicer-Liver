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
  part of the v2.0 locator work (see ADR-0025 §"The node").

==============================================================================*/

#ifndef __vtkmrmllocatordisplaynode_h_
#define __vtkmrmllocatordisplaynode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

/**
 * \class vtkMRMLLocatorDisplayNode
 *
 * \brief Display-only MRML node for the v2.0 locator.
 *
 * Per [ADR-0025](../../Docs/adr/0025-locator-architecture.md)
 * §"The node" the locator carries no display or interaction logic on
 * the carrier itself (ADR-0014 data-only discipline); the visual
 * configuration lives here.  A single display node serves v2.0; any
 * per-view / per-representation split is deferred to v2.1.
 *
 * \par Field roster
 *
 *   - ``Radius`` — locator sphere radius (also feeds the
 *     ``uLocatorRadius`` shader uniform of the resection-surface
 *     mapper, ADR-0025 §"The shader").  Persisted here.
 *   - ``Color`` and ``Visibility`` are inherited from
 *     ``vtkMRMLDisplayNode``, which already persists them; the
 *     constructor only seeds a sensible locator default colour.
 *
 * ``Radius`` persists through WriteXML / ReadXMLAttributes /
 * CopyContent, mirroring the structure of
 * ``vtkMRMLResectogramDisplayNode``.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLLocatorDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLLocatorDisplayNode* New();
  vtkTypeMacro(vtkMRMLLocatorDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).
  const char* GetNodeTagName() override { return "LocatorDisplay"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content (excludes basic data, such as name and node references).
  /// \sa vtkMRMLNode::CopyContent
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Locator display fields (ADR-0025 §"The node")
  //--------------------------------------------------------------------------

  /// Locator sphere radius; also feeds the ``uLocatorRadius`` shader
  /// uniform of the resection-surface mapper.  Colour and visibility
  /// are inherited from vtkMRMLDisplayNode (Get/SetColor,
  /// Get/SetVisibility).
  vtkSetMacro(Radius, double);
  vtkGetMacro(Radius, double);

protected:
  vtkMRMLLocatorDisplayNode();
  ~vtkMRMLLocatorDisplayNode() override;

private:
  vtkMRMLLocatorDisplayNode(const vtkMRMLLocatorDisplayNode&) = delete;
  void operator=(const vtkMRMLLocatorDisplayNode&) = delete;

  double Radius;
};

#endif //__vtkmrmllocatordisplaynode_h_
