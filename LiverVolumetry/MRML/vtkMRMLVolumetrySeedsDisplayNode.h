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

  This file was developed for the Slicer-Liver extension as part of the
  ADR-0038-amendment volumetry seeds-off-markups migration (ADR-0013
  Pipeline pattern, ADR-0025 display-node/pipeline template, ADR-0033 hover
  discipline; volumetry-seeds-layerdm-plan.md §3a).

==============================================================================*/

#ifndef __vtkmrmlvolumetryseedsdisplaynode_h_
#define __vtkmrmlvolumetryseedsdisplaynode_h_

#include "vtkSlicerLiverVolumetryModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

/**
 * \class vtkMRMLVolumetrySeedsDisplayNode
 *
 * \brief Data-only MRML display node carrying the volumetry seed-placement
 *        interaction state (ADR-0038-amendment §3a).
 *
 * Following the ADR-0025/0033 data-only display-node shape, this node
 * CARRIES the seed-placement interaction state but does NO rendering
 * itself: the LayerDM Pipeline renders (ADR-0013 §5 forbids a per-module
 * displayable manager).  The arm / hover / grab state living on the SHARED
 * display node — not on a Python pipeline instance LayerDM does not drive —
 * is the hard-won LayerDM lesson (``feedback_layerdm_state_on_display_node``);
 * the shared base's ``PointPlacementState`` accessors read/write that state
 * through the generic ``SetAttribute`` / ``GetAttribute`` channel
 * (namespaced ``LiverVolumetry.*``), so this class does not re-declare it.
 *
 * \par Field roster
 *
 *   - ``TransientPoint`` — TRANSIENT adhering point (RAS) under the cursor
 *     (the hover preview the Pipeline renders without a carrier mutation).
 *     Get/Set; NOT persisted.
 *   - ``Radius`` — marker glyph radius (mm).  Persisted.
 *   - the surface the pick resolves against is referenced through the
 *     ``pickSurface`` node-reference role (generic
 *     ``SetNodeReferenceID`` / ``GetNodeReference``).
 *   - ``Color`` and ``Visibility`` inherited from ``vtkMRMLDisplayNode``.
 *
 * The node exposes NO rendering machinery (no actor, no mapper, no
 * displayable-manager class of its own) — an absence pinned by the
 * data-only conformance test because the v1 markups display node DID
 * render.
 */
class VTK_SLICER_LIVERVOLUMETRY_MODULE_MRML_EXPORT vtkMRMLVolumetrySeedsDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLVolumetrySeedsDisplayNode* New();
  vtkTypeMacro(vtkMRMLVolumetrySeedsDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "VolumetrySeedsDisplay"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Interaction-state fields (ADR-0025/0033 data-only shape)
  //--------------------------------------------------------------------------

  /// TRANSIENT adhering point (RAS) under the cursor (the hover preview).
  /// Deliberately NOT persisted — re-derived from interaction every hover.
  void SetTransientPoint(double x, double y, double z);
  vtkGetVector3Macro(TransientPoint, double);

  /// Marker glyph radius (mm).  Persisted.  Colour and visibility are
  /// inherited from vtkMRMLDisplayNode (Get/SetColor, Get/SetVisibility).
  vtkSetMacro(Radius, double);
  vtkGetMacro(Radius, double);

  //--------------------------------------------------------------------------
  // Pick-surface reference (the surface the pick resolves against; ADR-0025
  // data-only reference).
  //--------------------------------------------------------------------------

  /// Reference role name for the surface the seed pick resolves against.
  /// Namespaced ``LiverVolumetry.*`` to match the interaction-state attribute
  /// channel.
  static const char* GetPickSurfaceReferenceRole() { return "LiverVolumetry.pickSurface"; }

  /// Reference the surface the pick resolves against.  ``nullptr`` clears
  /// the reference.
  void SetAndObservePickSurfaceNodeID(const char* surfaceNodeID);

  /// Resolve the referenced pick surface, or ``nullptr`` when none is wired.
  vtkMRMLNode* GetPickSurfaceNode();

  //--------------------------------------------------------------------------
  // Structure-source reference (the segmentation the seed→label capture
  // resolves touched candidates against; ``territory-usability``
  // §"Seed→label capture").  Distinct from the pick surface (a rasterized
  // labelmap): the capture needs the SEGMENTATION so it can read each
  // segment's binary labelmap + layer index at the clicked voxel.
  //--------------------------------------------------------------------------

  /// Reference role name for the structure-source segmentation the seed→label
  /// capture scans.  Namespaced ``LiverVolumetry.*`` to match the interaction-
  /// state attribute channel.
  static const char* GetStructureSourceReferenceRole() { return "LiverVolumetry.structureSource"; }

  /// Reference the structure-source segmentation.  ``nullptr`` clears the
  /// reference.
  void SetAndObserveStructureSourceNodeID(const char* segmentationNodeID);

  /// Resolve the referenced structure-source segmentation, or ``nullptr``
  /// when none is wired.
  vtkMRMLNode* GetStructureSourceNode();

protected:
  vtkMRMLVolumetrySeedsDisplayNode();
  ~vtkMRMLVolumetrySeedsDisplayNode() override;

private:
  vtkMRMLVolumetrySeedsDisplayNode(const vtkMRMLVolumetrySeedsDisplayNode&) = delete;
  void operator=(const vtkMRMLVolumetrySeedsDisplayNode&) = delete;

  double TransientPoint[3];
  double Radius;
};

#endif // __vtkmrmlvolumetryseedsdisplaynode_h_
