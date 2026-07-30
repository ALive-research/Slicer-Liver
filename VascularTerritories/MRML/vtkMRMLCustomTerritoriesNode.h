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
#include <vtkWrappingHints.h>

// STD includes
#include <array>
#include <map>
#include <string>
#include <vector>

class vtkMRMLMarkupsFiducialNode;
class vtkMRMLModelNode;
class vtkMRMLStorageNode;
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
 *   - ``CenterlineRefs``     — references to centerline model nodes
 *                               (output of VMTK ExtractCenterline).
 *   - ``AnnotationPoints``   — ordered, surface-snapped annotation
 *                               points, keyed per surgeon-named
 *                               territory, seeding the centerline
 *                               extractor.  Per ADR-0037 §Decision 1
 *                               these live in an OWN point carrier on
 *                               this node — NOT on a
 *                               ``vtkMRMLMarkupsFiducialNode`` — the
 *                               module's transition off markups.  The
 *                               VMTK feed (Stage 3) builds a transient
 *                               fiducial node from these points inside
 *                               the extraction call and discards it.
 *   - ``Groupings``          — map from centerline ID to surgeon-named
 *                               segment ID.
 *   - ``SegmentNames``       — surgeon-defined segment labels.
 *
 * Segment masks live on the referenced ``vtkMRMLSegmentationNode``
 * (the ``segments`` node-reference role on the abstract base), not on
 * this wrapper.  Module logic computes the segmentation from
 * centerlines + groupings and assigns it to the reference.
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
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLCustomTerritoriesNode : public vtkMRMLAbstractTerritoriesNode
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

  //--------------------------------------------------------------------------
  // Annotation-point carrier (ADR-0037 §Decision 1 + ADR-0014 §"Fourth
  // layer")
  //--------------------------------------------------------------------------
  //
  // Ordered, surface-snapped annotation points, keyed per surgeon-named
  // territory id (the same std::string idiom as ``SetGrouping`` /
  // ``GetGrouping``).  Replaces the never-implemented ``EndpointRefs``
  // markups slot with an OWN point store — no markups reference anywhere
  // on the annotation path.  Round-trips through MRML XML + the
  // ``vtkMRMLCustomTerritoriesStorageNode`` ``.vta.json`` schema.

  /// Append a point to ``territoryId``'s ordered list; returns its index
  /// within that territory.  Fires ONE ModifiedEvent.
  int AddAnnotationPoint(const std::string& territoryId, double x, double y, double z);

  /// Number of annotation points in ``territoryId`` (0 for an unknown
  /// territory).
  int GetNumberOfAnnotationPoints(const std::string& territoryId);

  /// The i-th annotation point of ``territoryId`` (placement order),
  /// returned as a 3-tuple in Python (``VTK_SIZEHINT``).  An out-of-range
  /// index returns the origin.  The pointer aliases an internal scratch
  /// buffer valid until the next call — copy before re-calling.
  const double* GetNthAnnotationPoint(const std::string& territoryId, int i) VTK_SIZEHINT(3);

  /// Relocate the i-th annotation point of ``territoryId`` in place.
  /// Fires ONE ModifiedEvent; a no-op (no event) for an out-of-range
  /// index.
  void SetNthAnnotationPoint(const std::string& territoryId, int i, double x, double y, double z);

  /// Remove the i-th annotation point of ``territoryId``; the tail shifts
  /// up in order.  Fires ONE ModifiedEvent; a no-op for an out-of-range
  /// index.  Returns true iff a point was removed.
  bool RemoveNthAnnotationPoint(const std::string& territoryId, int i);

  /// Empty ``territoryId``'s list only, leaving siblings intact.  Fires
  /// ONE ModifiedEvent for a non-empty territory.
  void ClearAnnotationPoints(const std::string& territoryId);

  /// Remove ``territoryId`` wholesale — its annotation points AND its
  /// per-territory display slot (colour / label / visibility) — leaving
  /// siblings intact.  Fires ONE ModifiedEvent iff something was removed.
  /// Returns true iff the territory carried any geometry or display slot.
  /// A territory with zero seeds is still removable (its display slot alone
  /// makes it present), which is the affordance an empty territory needs.
  bool RemoveTerritory(const std::string& territoryId);

  /// The surgeon-named territory ids that currently carry at least one
  /// annotation point, in a deterministic (sorted) order.  Used by the
  /// storage node to enumerate the per-territory point lists.
  std::vector<std::string> GetAnnotationTerritoryIds() const;

  //--------------------------------------------------------------------------
  // Per-territory display-attribute slot (ADR-0037 §Decision 3 / §3 table)
  //--------------------------------------------------------------------------
  //
  // The table row carries a per-territory colour swatch, display label, and
  // visibility toggle.  These live in an OWN per-territoryId slot on this
  // carrier, mirroring the ``AnnotationPoints`` std::map idiom and keyed on
  // the same surgeon-named territory id.  The display slot is INDEPENDENT of
  // the geometry slot: a display write never touches ``AnnotationPoints``.
  // Round-trips through MRML XML + the ``.vta.json`` storage node.  Each
  // write fires ONE ModifiedEvent so the table's observer rebuilds.

  /// Set territory ``territoryId``'s display colour (RGB in [0, 1]).  Fires
  /// ONE ModifiedEvent.  Does NOT touch the annotation-point geometry.
  void SetTerritoryColor(const std::string& territoryId, double r, double g, double b);

  /// Territory ``territoryId``'s display colour as a 3-tuple in Python
  /// (``VTK_SIZEHINT``).  An unset territory returns the module default
  /// (opaque white).  The pointer aliases an internal scratch buffer valid
  /// until the next call — copy before re-calling.
  const double* GetTerritoryColor(const std::string& territoryId) VTK_SIZEHINT(3);

  /// Set territory ``territoryId``'s display label.  Fires ONE
  /// ModifiedEvent.  Does NOT touch the annotation-point geometry.
  void SetTerritoryLabel(const std::string& territoryId, const std::string& label);

  /// Territory ``territoryId``'s display label (empty string if unset).
  std::string GetTerritoryLabel(const std::string& territoryId) const;

  /// Set territory ``territoryId``'s display visibility.  Fires ONE
  /// ModifiedEvent.  Does NOT touch the annotation-point geometry.
  void SetTerritoryVisibility(const std::string& territoryId, bool visible);

  /// Territory ``territoryId``'s display visibility (defaults to true for an
  /// unset territory).
  bool GetTerritoryVisibility(const std::string& territoryId) const;

  /// The territory ids that currently carry a display attribute (colour,
  /// label, or visibility), in a deterministic (sorted) order.  Used by the
  /// storage node to enumerate the per-territory display slots.
  std::vector<std::string> GetDisplayTerritoryIds() const;

  //--------------------------------------------------------------------------
  // Storage
  //--------------------------------------------------------------------------

  /// The annotation carrier's default storage node
  /// (``vtkMRMLCustomTerritoriesStorageNode``), mirroring the resection
  /// plan's rooted-persistence wiring (ADR-0014 §"Fourth layer").
  vtkMRMLStorageNode* CreateDefaultStorageNode() override;

protected:
  vtkMRMLCustomTerritoriesNode();
  ~vtkMRMLCustomTerritoriesNode() override;
  vtkMRMLCustomTerritoriesNode(const vtkMRMLCustomTerritoriesNode&) = delete;
  void operator=(const vtkMRMLCustomTerritoriesNode&) = delete;

  std::map<std::string, std::string> Groupings;
  std::map<int, std::string> OptInSCTCodes;

  /// Ordered, surface-snapped annotation points keyed per territory id
  /// (ADR-0037 §Decision 1).  Each value is the territory's point list in
  /// placement order; a ``std::map`` keyed on the territory id keeps the
  /// lists independent and enumerable in a deterministic order.
  std::map<std::string, std::vector<std::array<double, 3>>> AnnotationPoints;

  /// Scratch buffer backing the ``GetNthAnnotationPoint`` size-hinted
  /// return (the ``GetSlicingPlaneInitPoint`` idiom): a stable address to
  /// alias so the wrapped 3-tuple does not point at a temporary.
  double AnnotationPointScratch[3] = { 0.0, 0.0, 0.0 };

  /// Per-territory display attributes (ADR-0037 §Decision 3).  Keyed on the
  /// same surgeon-named territory id as ``AnnotationPoints`` but kept in
  /// SEPARATE maps so a display write cannot perturb the geometry map.  A
  /// territory with no entry falls back to the module defaults (opaque
  /// white, empty label, visible).
  std::map<std::string, std::array<double, 3>> TerritoryColors;
  std::map<std::string, std::string> TerritoryLabels;
  std::map<std::string, bool> TerritoryVisibilities;

  /// Scratch buffer backing the ``GetTerritoryColor`` size-hinted return
  /// (same idiom as ``AnnotationPointScratch``).
  double TerritoryColorScratch[3] = { 1.0, 1.0, 1.0 };

  /// Surgeon-defined segment-label list.  Owned by the node; written
  /// to / read from MRML XML via the ``segmentNames`` attribute.
  /// Always non-null per the abstract-base contract; empty when the
  /// surgeon has not yet named any segments.
  vtkSmartPointer<vtkStringArray> SegmentNames;
};

#endif // __vtkmrmlcustomterritoriesnode_h_
