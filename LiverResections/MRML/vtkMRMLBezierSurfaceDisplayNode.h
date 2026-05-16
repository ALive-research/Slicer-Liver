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

#ifndef __vtkmrmlbeziersurfacedisplaynode_h_
#define __vtkmrmlbeziersurfacedisplaynode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayNode.h>

// VTK includes
#include <vtkSetGet.h>

// STD includes
#include <string>

/**
 * \class vtkMRMLBezierSurfaceDisplayNode
 *
 * \brief Display-only MRML node carrying decoration state for a
 *        ``vtkMRMLBezierSurfaceNode``.
 *
 * Per [ADR-0013 §8](../../Docs/adr/0013-layerdm-pipeline-pattern.md),
 * the LayerDM Pipeline pattern moves display fields off the data node
 * onto a dedicated display node.  This node owns colour, opacity,
 * grid visibility, widget-visibility, and the related decoration
 * state previously hosted by ``vtkMRMLLiverResectionNode``.  The
 * matching Pipeline (T2.2, out of scope here) observes this node and
 * activates the appropriate Representation per ADR-0014 §2.
 *
 * \par MRML node shape
 *
 *   - ``vtkMRMLBezierSurfaceNode`` — \b data: geometry + state
 *     machine + init-mode audit trail.
 *   - ``vtkMRMLBezierSurfaceDisplayNode`` (this class) —
 *     \b display: all decoration fields (per ADR-0013 §8).
 *
 * The field roster mirrors the display-side block of
 * ``vtkMRMLLiverResectionNode`` (header lines 212-303) so the Pipeline
 * migration is a pure relocation, not a behaviour change.  Fields
 * whose interpretation depends on the active Representation (e.g.
 * ``GridVisibility``) are honoured by the Pipeline only when the
 * (state, mode) tuple selects a Representation that uses them.
 *
 * \par Defaults
 *
 * The defaults below are deliberately chosen to match the legacy
 * ``vtkMRMLLiverResectionNode`` constructor (see its .cxx, lines
 * 56-66) so a side-by-side comparison of the two paths starts from
 * an identical visual baseline.  Any divergence is documented in
 * test comments per the characterisation discipline of ADR-0003.
 *
 * \par Coexistence with the legacy node
 *
 * During v2.0.0 this node coexists with ``vtkMRMLLiverResectionNode``,
 * which retains its display fields (T2 is *additive*).  T2.7 will
 * collapse the legacy node and retire its display fields.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLBezierSurfaceDisplayNode : public vtkMRMLDisplayNode
{
public:
  static vtkMRMLBezierSurfaceDisplayNode* New();
  vtkTypeMacro(vtkMRMLBezierSurfaceDisplayNode, vtkMRMLDisplayNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Volume, Model).
  const char* GetNodeTagName() override { return "BezierSurfaceDisplay"; }

  /// Read node attributes from XML.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content (excludes basic data, such as name and node references).
  /// \sa vtkMRMLNode::CopyContent
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Colour-side decoration (float[3] in [0,1])
  //--------------------------------------------------------------------------

  /// Base resection-surface colour.
  vtkSetVector3Macro(ResectionColor, float);
  vtkGetVector3Macro(ResectionColor, float);

  /// Control-grid line colour.
  vtkSetVector3Macro(ResectionGridColor, float);
  vtkGetVector3Macro(ResectionGridColor, float);

  /// Resection-margin band colour.
  vtkSetVector3Macro(ResectionMarginColor, float);
  vtkGetVector3Macro(ResectionMarginColor, float);

  /// Uncertainty-margin band colour.
  vtkSetVector3Macro(UncertaintyMarginColor, float);
  vtkGetVector3Macro(UncertaintyMarginColor, float);

  /// Surface opacity, clamped to [0, 1].
  vtkGetMacro(ResectionOpacity, float);
  vtkSetClampMacro(ResectionOpacity, float, 0.0f, 1.0f);

  //--------------------------------------------------------------------------
  // Grid + widget visibility
  //--------------------------------------------------------------------------

  /// Whether the 4×4 Bezier control grid is rendered as glyphs/edges.
  vtkSetMacro(GridVisibility, bool);
  vtkGetMacro(GridVisibility, bool);

  /// Subdivision count for the rendered Bezier surface (controls the
  /// triangle density of the sampled surface).
  vtkSetMacro(GridDivisions, float);
  vtkGetMacro(GridDivisions, float);

  /// Visual thickness of the rendered control-grid lines.
  vtkSetMacro(GridThickness, float);
  vtkGetMacro(GridThickness, float);

  /// Whether the control-grid glyphs render in 3D views.
  vtkSetMacro(Grid3DVisibility, bool);
  vtkGetMacro(Grid3DVisibility, bool);

  /// Whether the control-grid glyphs render in 2D slice views.
  vtkSetMacro(Grid2DVisibility, bool);
  vtkGetMacro(Grid2DVisibility, bool);

  /// Master visibility flag for the interactive widget (separate from
  /// the underlying display-node ``Visibility`` because the widget may
  /// be hidden even while the rendered surface is shown).
  vtkSetMacro(WidgetVisibility, bool);
  vtkGetMacro(WidgetVisibility, bool);

  //--------------------------------------------------------------------------
  // Resection-surface behaviour flags
  //--------------------------------------------------------------------------

  /// Whether the resection clips the underlying liver model (boolean
  /// half-space cut vs visualisation overlay).  Honoured by the
  /// BezierPlanningRepresentation only.
  vtkSetMacro(ClipOut, bool);
  vtkGetMacro(ClipOut, bool);

  /// Whether resection / uncertainty margins are rendered with
  /// per-pixel interpolation or as hard bands.
  vtkSetMacro(InterpolatedMargins, bool);
  vtkGetMacro(InterpolatedMargins, bool);

  /// Whether the resection surface renders in 2D slice views as a
  /// resectogram strip.
  vtkSetMacro(ShowResection2D, bool);
  vtkGetMacro(ShowResection2D, bool);

  /// Whether the resection is mirrored to a partner display (e.g.
  /// resectogram side panel).
  vtkSetMacro(MirrorDisplay, bool);
  vtkGetMacro(MirrorDisplay, bool);

  //--------------------------------------------------------------------------
  // SCT terminology reference (ADR-0011 + ADR-0013 §3)
  //--------------------------------------------------------------------------

  /// Serialised SNOMED-CT terminology triple (Category, Type,
  /// optional Modifier) describing the clinical concept this display
  /// node decorates.  The canonical wire format is Slicer's standard
  /// terminology-entry string,
  /// ``{CategoryCodingScheme}^{CategoryCode}^{CategoryMeaning}~``
  /// ``{TypeCodingScheme}^{TypeCode}^{TypeMeaning}~``
  /// ``{ModifierCodingScheme}^{ModifierCode}^{ModifierMeaning}``
  /// (e.g. ``SCT^123037004^Anatomical Structure~SCT^10200004^Liver~^^``
  /// for the liver anatomical concept).
  ///
  /// Empty string = no terminology assigned; rendering uses pure-vector
  /// defaults (``ResectionColor`` etc.).  When set, the LayerDM
  /// Pipeline (T2.2, out of scope here) uses the SCT triple to derive
  /// colour, label, and badge presentation per
  /// [ADR-0011](../../Docs/adr/0011-sct-terminology-dispatch.md) and
  /// [ADR-0013 §3](../../Docs/adr/0013-layerdm-pipeline-pattern.md);
  /// this node only stores the string — it does not depend on the
  /// Terminologies module for parsing.
  vtkSetMacro(TerminologyEntry, std::string);
  vtkGetMacro(TerminologyEntry, std::string);

protected:
  vtkMRMLBezierSurfaceDisplayNode();
  ~vtkMRMLBezierSurfaceDisplayNode() override;

private:
  vtkMRMLBezierSurfaceDisplayNode(const vtkMRMLBezierSurfaceDisplayNode&) = delete;
  void operator=(const vtkMRMLBezierSurfaceDisplayNode&) = delete;

  float ResectionColor[3];
  float ResectionGridColor[3];
  float ResectionMarginColor[3];
  float UncertaintyMarginColor[3];
  float ResectionOpacity;
  bool GridVisibility;
  float GridDivisions;
  float GridThickness;
  bool Grid3DVisibility;
  bool Grid2DVisibility;
  bool WidgetVisibility;
  bool ClipOut;
  bool InterpolatedMargins;
  bool ShowResection2D;
  bool MirrorDisplay;
  std::string TerminologyEntry;
};

#endif //__vtkmrmlbeziersurfacedisplaynode_h_
