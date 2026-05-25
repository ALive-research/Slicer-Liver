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

#ifndef __vtkmrmlstdcouinaudterritoriesnode_h_
#define __vtkmrmlstdcouinaudterritoriesnode_h_

#include "vtkSlicerVascularTerritoriesModuleMRMLExport.h"

// This module MRML includes
#include "vtkMRMLAbstractTerritoriesNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>
#include <vtkSmartPointer.h>

// STD includes
#include <string>

class vtkMRMLScalarVolumeNode;
class vtkStringArray;

/**
 * \class vtkMRMLStdCouinaudTerritoriesNode
 *
 * \brief Concrete territories node carrying the Stage-3 Auto-tab
 *        result — a one-shot AI-inferred Couinaud labelmap.
 *
 * Per Docs/architecture/territories-class-hierarchy.md the Auto path
 * holds:
 *
 *   - ``SourceImageRef``       — the Portal-venous volume the AI ran on.
 *   - ``AIBackendIdentifier``  — opaque string naming the AI tool +
 *                                version (e.g., "TotalSegmentator-2.0.0").
 *   - ``Subdivision``          — enum: ``I_VIII`` (8 segments) or
 *                                ``I_VIII_with_IVab`` (10, splitting IVa/IVb).
 *   - ``ComputedAt``           — ISO-8601 timestamp of the AI run.
 *   - ``LabelMap``             — the AI-output labelmap (territories).
 *
 * \par SCT codes
 *
 * ``GetSCTCode(int)`` returns one of the 10 Couinaud SCT triples per
 * ADR-0011 §2.  The ordering is canonical:
 *
 *   | index | segment | SCT code   |
 *   | ----- | ------- | ---------- |
 *   | 0     | I       | 71133005   |
 *   | 1     | II      | 277956007  |
 *   | 2     | III     | 277957003  |
 *   | 3     | IV      | 277958008  |  // only when Subdivision == I_VIII
 *   | 3     | IVa     | 871688003  |  // when Subdivision == I_VIII_with_IVab
 *   | 4     | IVb     | 871689006  |  // (8-segment case: index 4 -> V; see below)
 *   | 4 / 5 | V       | 277959000  |
 *   | 5 / 6 | VI      | 277960005  |
 *   | 6 / 7 | VII     | 277961009  |
 *   | 7 / 8 | VIII    | 277962002  |
 *
 * The exact subdivision-dependent ordering is fixed by the
 * test-skeleton invariants below; the implementer step pins it.
 */
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLStdCouinaudTerritoriesNode : public vtkMRMLAbstractTerritoriesNode
{
public:
  static vtkMRMLStdCouinaudTerritoriesNode* New();
  vtkTypeMacro(vtkMRMLStdCouinaudTerritoriesNode, vtkMRMLAbstractTerritoriesNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Subdivision enum (territories-class-hierarchy.md "Why two subtypes…").
  ///
  /// - ``I_VIII``           — 8-segment Couinaud (the canonical clinical case).
  /// - ``I_VIII_with_IVab`` — 10-segment Couinaud splitting IV into IVa/IVb.
  enum Subdivision
  {
    I_VIII = 0,
    I_VIII_with_IVab = 1,
    Subdivision_Last
  };

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "StdCouinaudTerritories"; }

  /// Read node attributes from XML (Subdivision, AIBackendIdentifier,
  /// ComputedAt; references via standard MRML reference machinery).
  /// To be implemented by the follow-up commit.
  void ReadXMLAttributes(const char** atts) override;

  /// Write this node's information to a MRML file in XML format.
  /// To be implemented by the follow-up commit.
  void WriteXML(ostream& of, int indent) override;

  /// Copy node content.  To be implemented by the follow-up commit.
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  //--------------------------------------------------------------------------
  // Polymorphic interface (vtkMRMLAbstractTerritoriesNode contract)
  //--------------------------------------------------------------------------

  vtkStringArray* GetSegments() override;
  void GetSegmentColor(int index, double rgb[3]) override;

  /// Returns the literal ``"standard-couinaud"`` (subtype discriminator
  /// per ADR-0023 §"Persistence" + territories-class-hierarchy.md).
  const char* GetMethod() override { return "standard-couinaud"; }

  /// SCT code by segment index — see the class docstring table.
  /// Implementation pinned by the test-skeleton invariants.
  const char* GetSCTCode(int index) override;

  //--------------------------------------------------------------------------
  // Subtype-specific state
  //--------------------------------------------------------------------------

  /// Subdivision (``I_VIII`` vs ``I_VIII_with_IVab``).  Drives the
  /// segment count returned by ``GetNumberOfSegments()`` and the SCT
  /// ordering of ``GetSCTCode(int)``.  Setter clamps the input to
  /// the enum range so a stray value from ``ReadXMLAttributes`` (or
  /// programmatic mis-use) falls back to ``I_VIII`` deterministically
  /// rather than silently behaving as ``I_VIII`` while reporting the
  /// out-of-range raw integer.
  vtkGetMacro(Subdivision, int);
  void SetSubdivision(int subdivision);

  /// Segment count for the current ``Subdivision``: 8 for ``I_VIII``,
  /// 9 for ``I_VIII_with_IVab`` (IVa+IVb replace IV).  Invariant 9.
  int GetNumberOfSegments();

  /// AI-tool identifier string (e.g., "TotalSegmentator-2.0.0").
  vtkSetStringMacro(AIBackendIdentifier);
  vtkGetStringMacro(AIBackendIdentifier);

  /// ISO-8601 timestamp of the AI run.
  vtkSetStringMacro(ComputedAt);
  vtkGetStringMacro(ComputedAt);

protected:
  vtkMRMLStdCouinaudTerritoriesNode();
  ~vtkMRMLStdCouinaudTerritoriesNode() override;
  vtkMRMLStdCouinaudTerritoriesNode(const vtkMRMLStdCouinaudTerritoriesNode&) = delete;
  void operator=(const vtkMRMLStdCouinaudTerritoriesNode&) = delete;

  int Subdivision{ I_VIII };
  char* AIBackendIdentifier{ nullptr };
  char* ComputedAt{ nullptr };

  /// Cached segment-name array — owned by the node, rebuilt by
  /// ``GetSegments()`` from the canonical ``Subdivision``-keyed name
  /// table.  Kept as a smart pointer so the returned raw pointer
  /// stays valid for the node's lifetime per the abstract-base
  /// contract.
  vtkSmartPointer<vtkStringArray> Segments;
};

#endif // __vtkmrmlstdcouinaudterritoriesnode_h_
