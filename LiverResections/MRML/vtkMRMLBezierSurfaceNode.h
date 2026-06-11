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

  This file was originally developed for the Slicer-Liver extension
  as part of the T2 LiverResections all-in migration (Stack 2 of the
  v2.0.0 release tracker — see ADR-0013 §8 and ADR-0014 §1).

==============================================================================*/

#ifndef __vtkmrmlbeziersurfacenode_h_
#define __vtkmrmlbeziersurfacenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// This module MRML includes
#include "vtkMRMLAbstractParametricSurfaceNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>

class vtkPolyData;
class vtkMRMLModelNode;

/**
 * \class vtkMRMLBezierSurfaceNode
 *
 * \brief Concrete parametric-surface MRML node carrying a Bezier
 *        control polygon, the state machine (Init / Planning /
 *        Confirmed), and a Bernstein polynomial evaluator.
 *
 * Per the 2026-05-25 wrapper-vs-carrier amendment to ADR-0023
 * §"Class abstraction for surfaces" + ADR-0018 amendment of the same
 * date, this node inherits from
 * ``vtkMRMLAbstractParametricSurfaceNode`` — the shared abstract base
 * carries the (Rows, Cols, ControlGrid, InitMode, slicing-plane +
 * spheroid subordinates) roster.  The Bezier subclass keeps:
 *
 *   - The ADR-0019 state machine (``Init`` / ``Planning`` /
 *     ``Confirmed``).
 *   - The Bernstein polynomial evaluator dispatch
 *     (``EvaluateSurface(u, v)``).
 *   - The ``GetSurfaceType()`` discriminator returning ``"Bezier"``.
 *   - The ADR-0014 §4 read-only-after-Init guard on the inherited
 *     init-mode subordinate setters.
 *
 * \par Persistence
 *
 * The Bezier surface is non-storable (per the abstract base — see its
 * docstring §"Non-storable").  Persistence flows through the wrapping
 * ``vtkMRMLResectionPlanNode``'s storage node.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLBezierSurfaceNode : public vtkMRMLAbstractParametricSurfaceNode
{
public:
  static vtkMRMLBezierSurfaceNode* New();
  vtkTypeMacro(vtkMRMLBezierSurfaceNode, vtkMRMLAbstractParametricSurfaceNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Resection state machine (per ADR-0019).
  ///
  /// Three-state automaton:
  ///
  /// \verbatim
  ///   [*] -> Init -> Planning <-> Confirmed
  /// \endverbatim
  ///
  /// Init data becomes read-only audit data the moment the node
  /// transitions to ``Planning``.  See ``SetState`` for the full
  /// transition matrix.
  enum ResectionState
  {
    Init = 0,
    Planning = 1,
    Confirmed = 2,
    ResectionState_Last
  };

  //--------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------
  vtkMRMLNode* CreateNodeInstance() override;

  const char* GetNodeTagName() override { return "BezierSurface"; }

  void ReadXMLAttributes(const char** atts) override;
  void WriteXML(ostream& of, int indent) override;
  void CopyContent(vtkMRMLNode* anode, bool deepCopy = true) override;

  /// Spawn a ``vtkMRMLParametricSurfaceDisplayNode`` and observe it as
  /// this data node's default display node.  No-op if a display node
  /// is already attached.
  void CreateDefaultDisplayNodes() override;

  //--------------------------------------------------------------------------
  // Polymorphic dispatch (vtkMRMLAbstractParametricSurfaceNode contract)
  //--------------------------------------------------------------------------

  const char* GetSurfaceType() override { return "Bezier"; }

  /// Sample the Bezier surface at (u, v) ∈ [0, 1]^2 by Bernstein
  /// polynomial evaluation.  Returns a newly-allocated
  /// ``vtkPolyData`` carrying the sampled points.  Caller owns the
  /// returned object (wrap in ``vtkSmartPointer::Take``).
  vtkPolyData* EvaluateSurface(double u, double v) override;

  //--------------------------------------------------------------------------
  // State machine
  //--------------------------------------------------------------------------

  vtkGetMacro(State, int);
  void SetState(int state);

  vtkGetMacro(LoadingFromXML, bool);
  vtkSetMacro(LoadingFromXML, bool);

  /// Enum string converters — required by the XML enum macros.
  static const char* GetStateAsString(int state);
  static int GetStateFromString(const char* name);

  //--------------------------------------------------------------------------
  // Read-only-after-Init guarded overrides (ADR-0014 §4 / ADR-0019)
  //--------------------------------------------------------------------------

  bool SetSlicingPlaneInitPoint(int index, const double point[3]) override;
  void SetSlicingPlaneOrigin(double x, double y, double z) override;
  using Superclass::SetSlicingPlaneOrigin; // expose vec3 overload
  void SetSlicingPlaneNormal(double x, double y, double z) override;
  using Superclass::SetSlicingPlaneNormal;

  void SetNumberOfDistanceSpheroidInitPoints(int n) override;
  bool SetDistanceSpheroidInitPoint(int index, const double point[3]) override;
  void SetDistanceSpheroidCenter(double x, double y, double z) override;
  using Superclass::SetDistanceSpheroidCenter;
  void SetDistanceSpheroidRadiusX(double r) override;
  void SetDistanceSpheroidRadiusY(double r) override;
  void SetDistanceSpheroidRadiusZ(double r) override;

  //--------------------------------------------------------------------------
  // Target organ-model node reference (ADR-0014 §1)
  //--------------------------------------------------------------------------

  /// Canonical, single-source-of-truth role string for the weak
  /// reference to the target organ (liver) model node.  Mirrors the
  /// ``geometry`` role convention on ``vtkMRMLResectionPlanNode``
  /// (closed-vocabulary naming — no ``Liver`` prefix).
  static const char* GetTargetReferenceRole() { return "target"; }

  /// Resolve the weakly-referenced target organ model node, or
  /// nullptr when none is wired / the target has left the scene.
  vtkMRMLModelNode* GetTargetModelNode();

  /// Wire (or, with nullptr, clear) the weak reference to the target
  /// organ model node.  The reference is non-owning and non-observing
  /// per ADR-0014 §1 — see the role registration in the constructor.
  /// The T2 ring-extraction work (TODO(T2-target-mesh-weakref)) is the
  /// downstream consumer.
  void SetAndObserveTargetModelNode(vtkMRMLModelNode* target);

protected:
  vtkMRMLBezierSurfaceNode();
  ~vtkMRMLBezierSurfaceNode() override;

private:
  vtkMRMLBezierSurfaceNode(const vtkMRMLBezierSurfaceNode&) = delete;
  void operator=(const vtkMRMLBezierSurfaceNode&) = delete;

  int State;

  /// Internal flag — set to true for the duration of
  /// ``ReadXMLAttributes`` so the ADR-0014 §4 read-only guards on the
  /// init-mode setters do not reject XML-driven loads.
  bool LoadingFromXML;
};

#endif //__vtkmrmlbeziersurfacenode_h_
