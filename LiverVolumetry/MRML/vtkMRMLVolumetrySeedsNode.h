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

#ifndef __vtkmrmlvolumetryseedsnode_h_
#define __vtkmrmlvolumetryseedsnode_h_

#include "vtkSlicerLiverVolumetryModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorableNode.h>

// VTK includes
#include <vtkWrappingHints.h>

// STD includes
#include <array>
#include <string>
#include <vector>

class vtkMRMLStorageNode;

/**
 * \class vtkMRMLVolumetrySeedsNode
 *
 * \brief Data carrier for the LiverVolumetry region-growing seeds, moved
 *        OFF Slicer markups per the ADR-0038-amendment seeds-off-markups
 *        migration (``volumetry-seeds-layerdm-plan.md`` §3a).
 *
 * A volumetry seed is a labelled in-volume point.  Each seed carries:
 *
 *   - a RAS coordinate (the interior voxel the surgeon dropped);
 *   - a LABEL string that becomes the generated segment name
 *     (``GenerateSegmentsLabelMap`` reads it, ADR-0038 §Conformance); and
 *   - an RGB display colour.
 *
 * The seeds are FLAT and ORDERED: no grouping, no edges.  The three
 * per-seed attributes ride PARALLEL vectors keyed by placement index so a
 * label / colour write never perturbs a coordinate and vice versa (the
 * geometry slot is independent of the display / label slot).  This node
 * replaces the v1 ``vtkMRMLMarkupsFiducialNode`` ``ROIMarkersList``; it
 * holds NO markups reference anywhere (ADR-0014 §"Fourth layer", the
 * off-markups invariant).
 *
 * The carrier is storable via ``vtkMRMLVolumetrySeedsStorageNode`` (a
 * ``.vsd.json`` document), mirroring the resection-plan / territory-carrier
 * rooted-persistence wiring (ADR-0014 §"Fourth layer").
 *
 * \par Field roster (parallel per-seed vectors)
 *
 *   - ``Seeds``       — ordered RAS coordinates.
 *   - ``SeedLabels``  — per-seed segment-name label.
 *   - ``SeedColors``  — per-seed RGB display colour.
 */
class VTK_SLICER_LIVERVOLUMETRY_MODULE_MRML_EXPORT vtkMRMLVolumetrySeedsNode : public vtkMRMLStorableNode
{
public:
  static vtkMRMLVolumetrySeedsNode* New();
  vtkTypeMacro(vtkMRMLVolumetrySeedsNode, vtkMRMLStorableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "VolumetrySeeds"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Ordered seed carrier (ADR-0038 §"Consumers ledger", flat/no-edges)
  //--------------------------------------------------------------------------

  /// Append a seed at RAS ``(x, y, z)`` with an empty label + the module
  /// default colour; returns its placement index.  Fires ONE ModifiedEvent.
  int AddSeed(double x, double y, double z);

  /// Number of seeds currently carried.
  int GetNumberOfSeeds();

  /// The i-th seed's RAS coordinate (placement order), returned as a
  /// 3-tuple in Python (``VTK_SIZEHINT``).  An out-of-range index returns
  /// the origin.  The pointer aliases an internal scratch buffer valid
  /// until the next call — copy before re-calling.
  const double* GetNthSeed(int i) VTK_SIZEHINT(3);

  /// Relocate the i-th seed in place.  Fires ONE ModifiedEvent; a no-op
  /// (no event) for an out-of-range index.
  void SetNthSeed(int i, double x, double y, double z);

  /// Remove the i-th seed; the tail (coordinate + label + colour) shifts up
  /// in order.  Fires ONE ModifiedEvent; a no-op for an out-of-range index.
  /// Returns true iff a seed was removed.
  bool RemoveNthSeed(int i);

  //--------------------------------------------------------------------------
  // Per-seed label (becomes the generated segment name, ADR-0038 §Conformance)
  //--------------------------------------------------------------------------

  /// Set the i-th seed's LABEL (the generated segment name).  Fires ONE
  /// ModifiedEvent; a no-op for an out-of-range index.  Does NOT touch the
  /// coordinate.
  void SetNthSeedLabel(int i, const std::string& label);

  /// The i-th seed's LABEL (empty string for an out-of-range index).
  std::string GetNthSeedLabel(int i);

  //--------------------------------------------------------------------------
  // Per-seed display colour
  //--------------------------------------------------------------------------

  /// Set the i-th seed's RGB display colour (components in [0, 1]).  Fires
  /// ONE ModifiedEvent; a no-op for an out-of-range index.  Does NOT touch
  /// the coordinate.
  void SetNthSeedColor(int i, double r, double g, double b);

  /// The i-th seed's RGB display colour as a 3-tuple in Python
  /// (``VTK_SIZEHINT``).  An out-of-range index returns the module default
  /// (opaque white).  The pointer aliases an internal scratch buffer valid
  /// until the next call — copy before re-calling.
  const double* GetNthSeedColor(int i) VTK_SIZEHINT(3);

  //--------------------------------------------------------------------------
  // Storage
  //--------------------------------------------------------------------------

  /// The seed carrier's default storage node
  /// (``vtkMRMLVolumetrySeedsStorageNode``), mirroring the resection plan's
  /// rooted-persistence wiring (ADR-0014 §"Fourth layer").
  vtkMRMLStorageNode* CreateDefaultStorageNode() override;

protected:
  vtkMRMLVolumetrySeedsNode();
  ~vtkMRMLVolumetrySeedsNode() override;
  vtkMRMLVolumetrySeedsNode(const vtkMRMLVolumetrySeedsNode&) = delete;
  void operator=(const vtkMRMLVolumetrySeedsNode&) = delete;

  /// True iff ``i`` indexes an existing seed.
  bool IsValidIndex(int i) const;

  /// Ordered per-seed attributes on PARALLEL vectors keyed by placement
  /// index: a remove shifts all three in lockstep so the label + colour
  /// stay bound to their coordinate (ADR-0038 §"Consumers ledger").
  std::vector<std::array<double, 3>> Seeds;
  std::vector<std::string> SeedLabels;
  std::vector<std::array<double, 3>> SeedColors;

  /// Scratch buffers backing the size-hinted 3-tuple returns (the
  /// ``GetNthAnnotationPoint`` idiom): a stable address to alias so the
  /// wrapped 3-tuple does not point at a temporary.
  double SeedScratch[3] = { 0.0, 0.0, 0.0 };
  double SeedColorScratch[3] = { 1.0, 1.0, 1.0 };
};

#endif // __vtkmrmlvolumetryseedsnode_h_
