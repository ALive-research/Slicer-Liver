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
  part of the v2.0.0 unified surgeon workflow (ADR-0023 §"Class
  abstraction for territories") and the associated
  Docs/architecture/territories-class-hierarchy.md UML.

==============================================================================*/

#ifndef __vtkmrmlabstractterritoriesnode_h_
#define __vtkmrmlabstractterritoriesnode_h_

#include "vtkSlicerVascularTerritoriesModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLDisplayableNode.h>

// VTK includes
#include <vtkNew.h>
#include <vtkSetGet.h>

class vtkImageData;
class vtkMRMLSegmentationNode;
class vtkStringArray;

/**
 * \class vtkMRMLAbstractTerritoriesNode
 *
 * \brief Abstract base for the Stage-3 territories node family
 *        (Couinaud-auto vs surgeon-custom) per
 *        Docs/architecture/territories-class-hierarchy.md.
 *
 * Stage-3 of the ADR-0023 six-stage workflow exposes Auto (one-shot AI
 * Couinaud labelling) and Manual (centerline + grouping watershed)
 * paths whose data shapes are genuinely different but whose downstream
 * consumers (Stage 4 classification overlay, Stage 5 per-segment
 * volumetry) need only a polymorphic interface.  This class is that
 * interface; subclasses ``vtkMRMLStdCouinaudTerritoriesNode`` (Auto)
 * and ``vtkMRMLCustomTerritoriesNode`` (Manual) carry the
 * subtype-specific state.
 *
 * \par Polymorphic interface
 *
 * The interface table is fixed by the architecture doc's "Polymorphic
 * interface" table.  Downstream consumers must use only these methods
 * on a base-class pointer; ``dynamic_cast`` to the concrete subclass
 * is not in the contract.
 *
 *   - ``GetSegments()``         — segment-name list for the active subtype.
 *   - ``GetSegmentColor(int)``  — RGB triple per segment index.
 *   - ``GetLabelMap()``         — territories labelmap (subtype-specific source).
 *   - ``GetSegmentationNode()`` — companion segmentation-node reference.
 *   - ``GetMethod()``           — discriminator: "standard-couinaud" or "custom".
 *   - ``GetSCTCode(int)``       — SCT triple per segment (ADR-0011).
 *
 * \par Abstract-ness
 *
 * The class is abstract by construction: ``New()`` is overridden to
 * return ``nullptr`` (a runtime sentinel) and the polymorphic methods
 * are pure-virtual.  Direct instantiation via
 * ``vtkMRMLAbstractTerritoriesNode::New()`` produces ``nullptr`` so a
 * caller that forgets to pick a concrete subclass crashes loudly
 * rather than silently constructing a partially-initialised node.  We
 * intentionally do not use the no-``New()`` link-error variant of the
 * idiom — VTK's Python wrapping pipeline expects every exported
 * concrete ``vtkObject`` subclass to resolve a ``New`` symbol, and the
 * runtime sentinel keeps the class wrappable.
 *
 * \par Python / C++ boundary
 *
 * Per ADR-0004 these nodes are C++ data-only.  No business logic on
 * the node — segment-extraction kernels, AI orchestration, and
 * groupings algorithms live in Python module Logic classes.
 *
 * \par See also
 *
 *  - ADR-0023 §"Class abstraction for territories"
 *  - ADR-0004 (Python/C++ boundary)
 *  - ADR-0011 (SCT terminology dispatch)
 *  - Docs/architecture/territories-class-hierarchy.md
 */
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLAbstractTerritoriesNode : public vtkMRMLDisplayableNode
{
public:
  /// Runtime sentinel: returns ``nullptr``.  The class is abstract,
  /// but a ``New()`` symbol is still defined so VTK's Python wrapping
  /// machinery resolves it for the exported class (it never invokes
  /// the result).  Concrete subclasses ``vtkMRMLStdCouinaudTerritoriesNode``
  /// and ``vtkMRMLCustomTerritoriesNode`` supply real ``New()``
  /// implementations via ``vtkStandardNewMacro``.
  static vtkMRMLAbstractTerritoriesNode* New();

  vtkTypeMacro(vtkMRMLAbstractTerritoriesNode, vtkMRMLDisplayableNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  //--------------------------------------------------------------------------
  // Polymorphic interface (territories-class-hierarchy.md "Polymorphic
  // interface" table).
  //--------------------------------------------------------------------------

  /// Segment-name list — order matches the labelmap's value ordering.
  /// Subclasses own the storage; the returned pointer is valid for the
  /// lifetime of the node.  Never nullptr (empty array is the
  /// uninitialised case).
  virtual vtkStringArray* GetSegments() = 0;

  /// RGB colour for the segment at ``index``.  Writes into ``rgb[3]``
  /// (caller-owned 3-double buffer).  Subclasses define the colour
  /// table — Couinaud has a canonical 8 / 10-colour palette, Custom
  /// inherits from the SCT terminology binding (per ADR-0011) when
  /// the surgeon opts in.
  virtual void GetSegmentColor(int index, double rgb[3]) = 0;

  /// Territories labelmap.  Source differs by subtype: Auto stores it
  /// directly (AI output); Custom computes it from the groupings.
  /// Subclasses may return nullptr while uninitialised.
  virtual vtkImageData* GetLabelMap() = 0;

  /// Companion segmentation node (for the Stage 4 overlay that renders
  /// in 3D + slice views).  Created and maintained by the module Logic.
  virtual vtkMRMLSegmentationNode* GetSegmentationNode() = 0;

  /// Discriminator string per ADR-0023's `.lrp.json` schema v3 +
  /// territories-class-hierarchy.md.  Returns ``"standard-couinaud"``
  /// for ``vtkMRMLStdCouinaudTerritoriesNode`` and ``"custom"`` for
  /// ``vtkMRMLCustomTerritoriesNode``.  Never nullptr.
  virtual const char* GetMethod() = 0;

  /// SCT triple per segment index (ADR-0011 §1 contract).  Format:
  /// canonical SCT code identifier as a string (e.g., ``"71133005"``
  /// for Couinaud Segment I / Caudate).  Returns empty string when the
  /// subtype carries no SCT tagging — ``vtkMRMLCustomTerritoriesNode``
  /// returns empty by default unless the surgeon opted in.
  virtual const char* GetSCTCode(int index) = 0;

protected:
  vtkMRMLAbstractTerritoriesNode();
  ~vtkMRMLAbstractTerritoriesNode() override;
  vtkMRMLAbstractTerritoriesNode(const vtkMRMLAbstractTerritoriesNode&) = delete;
  void operator=(const vtkMRMLAbstractTerritoriesNode&) = delete;
};

#endif // __vtkmrmlabstractterritoriesnode_h_
