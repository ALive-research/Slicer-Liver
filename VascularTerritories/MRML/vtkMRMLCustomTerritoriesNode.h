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

==============================================================================*/

#ifndef __vtkmrmlcustomterritoriesnode_h_
#define __vtkmrmlcustomterritoriesnode_h_

#include "vtkSlicerVascularTerritoriesModuleMRMLExport.h"

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>
#include <vtkSmartPointer.h>

// STD includes
#include <map>
#include <string>

class vtkImageData;
class vtkMRMLMarkupsFiducialNode;
class vtkMRMLModelNode;
class vtkMRMLSegmentationNode;
class vtkStringArray;

/**
 * \class vtkMRMLCustomTerritoriesNode
 *
 * \brief Concrete territories node carrying the Stage-3 Manual-tab
 *        result — VMTK-extracted centerlines grouped into surgeon-named
 *        territories.
 *
 * Per Docs/architecture/territories-class-hierarchy.md the Manual path
 * holds:
 *
 *   - ``CenterlineRefs``  — references to centerline model nodes
 *                            (output of VMTK ExtractCenterline).
 *   - ``EndpointRefs``    — references to fiducial nodes seeding the
 *                            centerline extractor.
 *   - ``Groupings``       — map from centerline ID to surgeon-named
 *                            segment ID.
 *   - ``SegmentNames``    — surgeon-defined segment labels.
 *   - ``LabelMap``        — derived labelmap (computed by the module
 *                            logic from centerlines + groupings).
 *
 * \par SCT codes — surgeon-opt-in only
 *
 * Unlike ``vtkMRMLStdCouinaudTerritoriesNode``, the custom segments
 * are surgeon-defined and may not correspond to any SCT-coded anatomy.
 * ``GetSCTCode(int)`` returns the empty string by default; the
 * surgeon can attach SCT triples per segment via the Stage 3 Manual
 * tab's ``[⋯ → Tag with SCT…]`` action (per ADR-0011 §2 + the
 * architecture doc's "SCT terminology binding" section).
 */
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLCustomTerritoriesNode
  : public vtkMRMLAbstractTerritoriesNode
{
public:
  static vtkMRMLCustomTerritoriesNode* New();
  vtkTypeMacro(vtkMRMLCustomTerritoriesNode, vtkMRMLAbstractTerritoriesNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "CustomTerritories"; }

  /// Read groupings + segment names + references from XML.  Implementer.
  void ReadXMLAttributes(const char** atts) override;

  /// Write groupings + segment names + references to XML.  Implementer.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content.  Implementer.
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Polymorphic interface (vtkMRMLAbstractTerritoriesNode contract)
  //--------------------------------------------------------------------------

  vtkStringArray* GetSegments() override;
  void GetSegmentColor(int index, double rgb[3]) override;
  vtkImageData* GetLabelMap() override;
  vtkMRMLSegmentationNode* GetSegmentationNode() override;

  /// Returns the literal ``"custom"`` (subtype discriminator per
  /// ADR-0023 §"Persistence").
  const char* GetMethod() override { return "custom"; }

  /// Returns the surgeon-tagged SCT triple, or empty string if the
  /// surgeon did not opt in to SCT tagging for segment ``index``.
  /// See ADR-0011 §2 + architecture-doc §"SCT terminology binding".
  const char* GetSCTCode(int index) override;

  //--------------------------------------------------------------------------
  // Subtype-specific state
  //--------------------------------------------------------------------------

  /// Groupings map: centerline node ID -> segment ID.  The full set of
  /// segment IDs reachable through the map's range matches ``SegmentNames``.
  /// Implementer: round-trips through MRML XML and ``.lrp.json`` schema v3.
  void SetGrouping(const std::string& centerlineId, const std::string& segmentId);
  std::string GetGrouping(const std::string& centerlineId) const;
  std::size_t GetNumberOfGroupings() const;
  void ClearGroupings();

  /// Optional surgeon-opt-in SCT triples per segment.  Empty string
  /// means "no SCT tagging" (the default).
  void SetSegmentSCTCode(int index, const std::string& sctCode);

protected:
  vtkMRMLCustomTerritoriesNode();
  ~vtkMRMLCustomTerritoriesNode() override;
  vtkMRMLCustomTerritoriesNode(const vtkMRMLCustomTerritoriesNode&) = delete;
  void operator=(const vtkMRMLCustomTerritoriesNode&) = delete;

  std::map<std::string, std::string> Groupings;
  std::map<int, std::string> OptInSCTCodes;

  /// Surgeon-defined segment-label list.  Owned by the node; written
  /// to / read from MRML XML via the ``segmentNames`` attribute.
  /// Always non-null per the abstract-base contract; empty when the
  /// surgeon has not yet named any segments.
  vtkSmartPointer<vtkStringArray> SegmentNames;
};

#endif // __vtkmrmlcustomterritoriesnode_h_
