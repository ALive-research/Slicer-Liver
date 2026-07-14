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
  part of the vessel-adhering-highlight feature (ADR-0013 Pipeline
  pattern, ADR-0025 display-node/pipeline template, ADR-0033 hover
  discipline).

==============================================================================*/

#ifndef __vtkmrmlterritorieshighlightdisplaynode_h_
#define __vtkmrmlterritorieshighlightdisplaynode_h_

#include "vtkSlicerVascularTerritoriesModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

class vtkMRMLSegmentationNode;

/**
 * \class vtkMRMLTerritoriesHighlightDisplayNode
 *
 * \brief Data-only MRML display node for the vessel-adhering highlight.
 *
 * The vessel-adhering highlight paints a marker glyph that clings to the
 * input segmentation's closed-surface mesh under the cursor while a
 * territory annotation is being placed.  Following the ADR-0025 locator
 * template (a SEPARATE instance — this does NOT reuse
 * ``vtkMRMLLocatorNode``) the node is data-only per ADR-0013 §5: it
 * carries the transient adhering point + the reference to the input
 * segmentation whose surface is picked, and holds NO rendering logic.
 * The rendering lives in the Python LayerDM Pipeline
 * (``VascularTerritoriesLib.VesselHighlightPipeline``) keyed on this
 * display-node type (ADR-0013 §1: one Pipeline per display-node type).
 *
 * \par Persistence = presence, NOT live position
 *
 * Mirroring ``vtkMRMLLocatorNode``: the live adhering position is
 * TRANSIENT (re-derived from the cursor every hover) and is deliberately
 * NOT written to XML; only the display styling the base node already
 * persists (Color, Visibility) and the ``Radius`` round-trip.
 *
 * \par Field roster
 *
 *   - ``AdheringPointWorld`` — TRANSIENT live adhering world position
 *     (RAS) under the cursor.  Get/Set; NOT persisted.
 *   - ``Adhering`` — TRANSIENT flag: the cursor ray currently resolves to
 *     an on-surface point (marker shown) vs off-surface (marker hidden).
 *     Get/Set; NOT persisted.
 *   - ``Radius`` — marker glyph radius (mm).  Persisted.
 *   - the input segmentation whose closed surface is picked is referenced
 *     through the ``pickSurface`` node-reference role (Get/Set helpers
 *     below).
 *   - ``Color`` and ``Visibility`` inherited from ``vtkMRMLDisplayNode``.
 */
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLTerritoriesHighlightDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLTerritoriesHighlightDisplayNode* New();
  vtkTypeMacro(vtkMRMLTerritoriesHighlightDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "TerritoriesHighlightDisplay"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Highlight display fields (ADR-0025 §"The node" template)
  //--------------------------------------------------------------------------

  /// TRANSIENT live adhering world position (RAS) under the cursor.
  /// Deliberately NOT persisted — re-derived from interaction.
  vtkSetVector3Macro(AdheringPointWorld, double);
  vtkGetVector3Macro(AdheringPointWorld, double);

  /// TRANSIENT flag: the cursor ray resolves to an on-surface point
  /// (marker shown) vs off-surface (marker hidden).  NOT persisted.
  vtkSetMacro(Adhering, bool);
  vtkGetMacro(Adhering, bool);

  /// Marker glyph radius (mm).  Persisted.  Colour and visibility are
  /// inherited from vtkMRMLDisplayNode (Get/SetColor, Get/SetVisibility).
  vtkSetMacro(Radius, double);
  vtkGetMacro(Radius, double);

  //--------------------------------------------------------------------------
  // Pick-surface reference (the input segmentation whose closed surface is
  // picked; ADR-0013 §5 data-only reference).
  //--------------------------------------------------------------------------

  /// Reference role name for the input segmentation whose closed surface
  /// the highlight adheres to.
  static const char* GetPickSurfaceReferenceRole() { return "pickSurface"; }

  /// Reference the input segmentation whose closed-surface mesh is the
  /// pick target.  ``nullptr`` clears the reference.
  void SetAndObservePickSurfaceNodeID(const char* segmentationNodeID);

  /// Resolve the referenced input segmentation, or ``nullptr`` when none
  /// is wired / the referenced node is not a segmentation.
  vtkMRMLSegmentationNode* GetPickSurfaceNode();

protected:
  vtkMRMLTerritoriesHighlightDisplayNode();
  ~vtkMRMLTerritoriesHighlightDisplayNode() override;

private:
  vtkMRMLTerritoriesHighlightDisplayNode(const vtkMRMLTerritoriesHighlightDisplayNode&) = delete;
  void operator=(const vtkMRMLTerritoriesHighlightDisplayNode&) = delete;

  double AdheringPointWorld[3];
  bool Adhering;
  double Radius;
};

#endif // __vtkmrmlterritorieshighlightdisplaynode_h_
