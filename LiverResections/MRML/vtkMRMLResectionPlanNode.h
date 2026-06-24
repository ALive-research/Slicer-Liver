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
  the clinical-layer (wrapper) of the 2026-05-25 wrapper-vs-carrier
  amendment to ADR-0014 (§"Fourth layer: clinical/method wrapper")
  and ADR-0023 (§"Class abstraction for surfaces").

==============================================================================*/

#ifndef __vtkmrmlresectionplannode_h_
#define __vtkmrmlresectionplannode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorableNode.h>

// VTK includes
#include <vtkSetGet.h>

class vtkMRMLAbstractParametricSurfaceNode;
class vtkMRMLScalarVolumeNode;

/**
 * \class vtkMRMLResectionPlanNode
 *
 * \brief Clinical-layer MRML node representing one resection plan.
 *
 * Per the 2026-05-25 wrapper-vs-carrier amendment to
 * [ADR-0014](../../Docs/adr/0014-livermarkups-dissolution.md)
 * §"Fourth layer" and
 * [ADR-0023](../../Docs/adr/0023-unified-gui-stage-workflow.md)
 * §"Class abstraction for surfaces", the plan node is the clinical
 * wrapper: it carries the surgeon-facing fields (name, margins,
 * operative-sequence order, plan state) and references a parametric-
 * surface "carrier" via the typed ``geometry`` node-reference role.
 *
 * \par Field roster
 *
 *   - ``Name`` (inherited from vtkMRMLNode) — surgeon-facing plan name.
 *   - ``SafetyMargin_mm`` — clinical safety margin in millimetres.
 *   - ``RiskMargin_mm`` — clinical risk margin in millimetres.
 *   - ``OrderIndex`` — zero-based position in the operative sequence
 *     (sentinel ``-1`` = unordered).  Migrated from the surface node
 *     by the wrapper-vs-carrier landing.
 *   - ``State`` — plan-level state machine (Init / Planning /
 *     Confirmed); runs in parallel with the surface's own ADR-0019
 *     state machine.
 *
 * \par Node references
 *
 *   - ``geometry`` — typed reference to a
 *     ``vtkMRMLAbstractParametricSurfaceNode`` (Bezier or NURBS).
 *     The plan does NOT reference territories or volumetry
 *     partitions — those are scene-level concepts with their own
 *     MRML nodes (see ADR-0023 amendment).
 *
 * \par Persistence
 *
 * The plan is storable (CreateDefaultStorageNode returns a
 * ``vtkMRMLResectionPlanStorageNode`` instance); the referenced
 * surface persists through the same storage node, polymorphically
 * via a ``surface.type`` discriminator (Bezier today; NURBS in
 * v2.1).  See
 * ``Docs/design/resection-plan-architecture/03-storage-ownership.md``.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLResectionPlanNode : public vtkMRMLStorableNode
{
public:
  static vtkMRMLResectionPlanNode* New();
  vtkTypeMacro(vtkMRMLResectionPlanNode, vtkMRMLStorableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Plan-level state machine.
  ///
  ///   - ``Init``      — plan exists, no geometry committed yet.
  ///   - ``Planning``  — geometry is being authored / adjusted.
  ///   - ``Confirmed`` — plan is locked, awaiting clinical approval.
  enum PlanState
  {
    Init = 0,
    Planning = 1,
    Confirmed = 2,
    PlanState_Last
  };

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;
  const char* GetNodeTagName() override { return "ResectionPlan"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  /// Storable invariant — returns a freshly-constructed
  /// ``vtkMRMLResectionPlanStorageNode``.
  vtkMRMLStorageNode* CreateDefaultStorageNode() override;

  //--------------------------------------------------------------------------
  // Clinical field roster
  //--------------------------------------------------------------------------

  vtkGetMacro(SafetyMargin_mm, double);
  vtkSetMacro(SafetyMargin_mm, double);

  vtkGetMacro(RiskMargin_mm, double);
  vtkSetMacro(RiskMargin_mm, double);

  /// Operative-sequence position (zero-based).  Default ``-1`` =
  /// unordered.  Migrated from the surface node by the
  /// 2026-05-25 wrapper-vs-carrier amendment.
  vtkGetMacro(OrderIndex, int);
  vtkSetMacro(OrderIndex, int);

  vtkGetMacro(State, int);
  vtkSetMacro(State, int);

  /// Enum string converters (used by XML enum macros and JSON storage).
  static const char* GetStateAsString(int state);
  static int GetStateFromString(const char* name);

  //--------------------------------------------------------------------------
  // Node references
  //--------------------------------------------------------------------------

  /// Typed accessor for the ``geometry`` reference to the surface
  /// carrier.  Returns nullptr when no surface is wired.
  vtkMRMLAbstractParametricSurfaceNode* GetGeometryNode();

  /// Set the ``geometry`` reference to the surface carrier (Bezier or
  /// NURBS).  Accepts the abstract-base pointer so future NURBS
  /// instances work via the same call site.
  void SetAndObserveGeometryNode(vtkMRMLAbstractParametricSurfaceNode* surface);

  /// Reference role name — exposed as a constant so the storage node
  /// + Logic share a single literal.
  static const char* GetGeometryReferenceRole() { return "geometry"; }

  /// Typed accessor for the ``distanceMap`` reference to the scalar
  /// volume the resection margins are measured against.  Returns
  /// nullptr when no distance map is wired (ADR-0031).  The distance
  /// map is a path-specific INPUT of the plan, not a property of the
  /// surface carrier — per ADR-0014 §"Fourth layer" inputs live on the
  /// wrapper.
  vtkMRMLScalarVolumeNode* GetDistanceMapVolumeNode();

  /// Set the ``distanceMap`` reference to the distance-map scalar volume
  /// (ADR-0031).  Passing nullptr clears it (the graceful
  /// no-distance-map fallback the render path preserves).
  void SetAndObserveDistanceMapVolumeNode(vtkMRMLScalarVolumeNode* distanceMap);

  /// Reference role name — exposed as a constant so the storage node,
  /// the Pipeline, and the render Representation share a single literal.
  static const char* GetDistanceMapReferenceRole() { return "distanceMap"; }

protected:
  vtkMRMLResectionPlanNode();
  ~vtkMRMLResectionPlanNode() override;

private:
  vtkMRMLResectionPlanNode(const vtkMRMLResectionPlanNode&) = delete;
  void operator=(const vtkMRMLResectionPlanNode&) = delete;

  double SafetyMargin_mm;
  double RiskMargin_mm;
  int OrderIndex;
  int State;
};

#endif // __vtkmrmlresectionplannode_h_
