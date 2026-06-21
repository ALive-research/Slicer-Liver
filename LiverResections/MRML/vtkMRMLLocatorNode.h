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

#ifndef __vtkmrmllocatornode_h_
#define __vtkmrmllocatornode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayableNode.h>

// VTK includes
#include <vtkSetGet.h>

/**
 * \class vtkMRMLLocatorNode
 *
 * \brief Data-only MRML carrier for the v2.0 locator picked point.
 *
 * Per [ADR-0025](../../Docs/adr/0025-locator-architecture.md)
 * §"The node" the locator is a single new C++ data-only carrier
 * (ADR-0014 discipline): it holds the picked-point state and a
 * reference to its display node, carrying NO display or interaction
 * logic on the node itself.  A producer maps a resectogram interaction
 * to a ``(u, v)`` parameter and a world point and writes it onto this
 * node; consumers (the resection-surface shader, click-to-reslice)
 * observe the node.
 *
 * \par Persistence = presence, NOT live position
 *
 * Mirroring ``vtkMRMLCrosshairNode``, ``Copy`` / ``WriteXML`` /
 * ``ReadXMLAttributes`` round-trip the *presence* of a locator (the
 * ``LocatorActive`` flag) and its display config — NOT the live
 * picked position.  Reloading a scene restores that a locator exists;
 * the live position (``PickedPositionWorld``) is re-derived from
 * interaction and is deliberately transient: it is not written to XML
 * and not read back from XML.
 *
 * \par Field roster
 *
 *   - ``PickedPositionWorld`` — TRANSIENT live picked world position
 *     (RAS).  Get/Set; NOT persisted (absent from WriteXML /
 *     ReadXMLAttributes).
 *   - ``LocatorActive`` — PERSISTED presence flag ("a locator
 *     exists / is shown").  Round-trips through Copy / WriteXML /
 *     ReadXMLAttributes.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLLocatorNode : public vtkMRMLDisplayableNode
{
public:
  static vtkMRMLLocatorNode* New();
  vtkTypeMacro(vtkMRMLLocatorNode, vtkMRMLDisplayableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "Locator"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  /// Creates a single vtkMRMLLocatorDisplayNode and wires it as this
  /// node's display node (ADR-0025 §"The node" — one display node for
  /// v2.0).  Idempotent.
  void CreateDefaultDisplayNodes() override;

  //--------------------------------------------------------------------------
  // Locator field roster (ADR-0025 §"The node")
  //--------------------------------------------------------------------------

  /// TRANSIENT live picked world position (RAS).  Deliberately NOT
  /// persisted — re-derived from interaction.  See the class-level
  /// "Persistence = presence, NOT live position" note.
  vtkSetVector3Macro(PickedPositionWorld, double);
  vtkGetVector3Macro(PickedPositionWorld, double);

  /// PERSISTED presence flag — "a locator exists / is shown".
  /// Round-trips through Copy / WriteXML / ReadXMLAttributes.
  vtkSetMacro(LocatorActive, bool);
  vtkGetMacro(LocatorActive, bool);

protected:
  vtkMRMLLocatorNode();
  ~vtkMRMLLocatorNode() override;

private:
  vtkMRMLLocatorNode(const vtkMRMLLocatorNode&) = delete;
  void operator=(const vtkMRMLLocatorNode&) = delete;

  double PickedPositionWorld[3];
  bool LocatorActive;
};

#endif // __vtkmrmllocatornode_h_
