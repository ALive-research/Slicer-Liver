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
  part of the T3 ResectogramPipeline work (see ADR-0013 §1 + §5 and
  ADR-0025 §Context).

==============================================================================*/

#ifndef __vtkmrmlresectogramdisplaynode_h_
#define __vtkmrmlresectogramdisplaynode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

/**
 * \class vtkMRMLResectogramDisplayNode
 *
 * \brief Display-only MRML node that keys the ResectogramPipeline.
 *
 * Per [ADR-0013 §1](../../Docs/adr/0013-layerdm-pipeline-pattern.md)
 * there is exactly ONE LayerDM Pipeline per display-node TYPE.  The 3D
 * Bezier-surface Pipeline already owns
 * ``vtkMRMLParametricSurfaceDisplayNode``; keying a second Pipeline on
 * that same type would violate §1.  The resectogram — the flattened 2D
 * image of the Bezier ``(u, v)`` parameter domain (ADR-0025 §Context) —
 * therefore gets its OWN display-node type, and the
 * ``ResectogramPipeline`` is keyed on THIS class via the
 * ``AddPipelineCreator`` registration of ADR-0013 §5.
 *
 * \par Field roster
 *
 * The fields are the resectogram-relevant subset of the legacy
 * ``vtkMRMLMarkupsBezierSurfaceDisplayNode`` that the v1 monolith
 * ``vtkSlicerBezierSurfaceRepresentation3D`` reads when driving the 2D
 * mapper (``vtkOpenGLResection2DPolyDataMapper``):
 *
 *   - ``ShowResection2D`` — whether the resectogram strip renders.
 *   - ``MirrorDisplay`` — whether the resectogram is mirrored to the
 *     partner side panel (drives ``ResectogramPlaneCenter``).
 *   - ``EnableFlexibleBoundary`` — whether the anisotropic aspect-ratio
 *     scaling is applied (drives ``vtkLiverResectogramAspectRatio`` /
 *     the v1 ``Ratio(bool)`` toggle); ``false`` forces the isotropic
 *     ``{1, 1}``.
 *   - ``TextureNumComps`` — number of components in the distance-map
 *     texture the 2D mapper samples (the v1 ``SetTextureNumComps``
 *     feed).
 *   - ``BlurEnabled`` — whether the net-new v2.0 Gaussian-blur post-pass
 *     is engaged on the resectogram overlay renderer.  No legacy field
 *     corresponds; the ``FlattenedSurfaceRepresentation`` attaches a
 *     ``vtkGaussianBlurPass`` to its renderer when this is ``true``
 *     (ADR-0013 §6).
 *   - ``BlurRadius`` — the Gaussian-blur kernel extent in pixels driving
 *     that post-pass.
 *
 * \par Defaults
 *
 * Defaults match the legacy ``vtkMRMLMarkupsBezierSurfaceDisplayNode``
 * constructor so a side-by-side comparison of the v1 monolith and the
 * v2.0 ResectogramPipeline starts from an identical visual baseline
 * (characterisation discipline, ADR-0003).
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLResectogramDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLResectogramDisplayNode* New();
  vtkTypeMacro(vtkMRMLResectogramDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).
  const char* GetNodeTagName() override { return "ResectogramDisplay"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content (excludes basic data, such as name and node references).
  /// \sa vtkMRMLNode::CopyContent
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Resectogram display fields (subset of the legacy markups display node
  // read by vtkOpenGLResection2DPolyDataMapper)
  //--------------------------------------------------------------------------

  /// Whether the resection renders as a 2D resectogram strip.
  vtkSetMacro(ShowResection2D, bool);
  vtkGetMacro(ShowResection2D, bool);

  /// Whether the resectogram is mirrored to a partner display.
  vtkSetMacro(MirrorDisplay, bool);
  vtkGetMacro(MirrorDisplay, bool);

  /// Whether the anisotropic aspect-ratio scaling is applied (drives
  /// ``vtkLiverResectogramAspectRatio``); ``false`` forces ``{1, 1}``.
  vtkSetMacro(EnableFlexibleBoundary, bool);
  vtkGetMacro(EnableFlexibleBoundary, bool);

  /// Number of components in the distance-map texture the resectogram
  /// mapper samples.
  vtkSetMacro(TextureNumComps, int);
  vtkGetMacro(TextureNumComps, int);

  /// Whether the net-new v2.0 Gaussian-blur post-pass is engaged on the
  /// resectogram overlay renderer (drives the ``vtkGaussianBlurPass`` the
  /// ``FlattenedSurfaceRepresentation`` attaches; ADR-0013 §6).
  vtkSetMacro(BlurEnabled, bool);
  vtkGetMacro(BlurEnabled, bool);

  /// Gaussian-blur kernel extent, in pixels, for that post-pass.
  vtkSetMacro(BlurRadius, double);
  vtkGetMacro(BlurRadius, double);

protected:
  vtkMRMLResectogramDisplayNode();
  ~vtkMRMLResectogramDisplayNode() override;

private:
  vtkMRMLResectogramDisplayNode(const vtkMRMLResectogramDisplayNode&) = delete;
  void operator=(const vtkMRMLResectogramDisplayNode&) = delete;

  bool ShowResection2D;
  bool MirrorDisplay;
  bool EnableFlexibleBoundary;
  int TextureNumComps;
  bool BlurEnabled;
  double BlurRadius;
};

#endif //__vtkmrmlresectogramdisplaynode_h_
