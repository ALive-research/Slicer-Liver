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
  the plan-rooted storage layer of the 2026-05-25 wrapper-vs-carrier
  amendment to ADR-0014 §"Fourth layer" and ADR-0023 §"Persistence".

==============================================================================*/

#ifndef __vtkmrmlresectionplanstoragenode_h_
#define __vtkmrmlresectionplanstoragenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorageNode.h>

// STD includes
#include <string>

class vtkMRMLResectionPlanNode;
class vtkMRMLAbstractParametricSurfaceNode;

/**
 * \class vtkMRMLResectionPlanStorageNode
 *
 * \brief Plan-rooted ``.lrp.json`` storage node — schema v2 (trimmed).
 *
 * Per the 2026-05-25 wrapper-vs-carrier amendment to ADR-0014 + ADR-0023,
 * the resection plan is the rooted persistence target; the surface
 * geometry persists as a polymorphic ``surface`` block inside the
 * plan document.
 *
 * Schema shape (trimmed v2):
 *
 * \code
 * {
 *   "schemaVersion": 2,
 *   "name": "Right hemihepatectomy",
 *   "safetyMargin_mm": 10.0,
 *   "riskMargin_mm": 5.0,
 *   "orderIndex": 0,
 *   "state": "Planning",
 *   "surface": {
 *     "type": "Bezier",
 *     "rows": 4, "cols": 4,
 *     "controlGrid": [<48 doubles>],
 *     "initMode": "SlicingPlane",
 *     "slicingPlane": { "origin": [...], "normal": [...], "initPointsFlat": [...] },
 *     "distanceSpheroid": { "center": [...], "radius": {"x":...,"y":...,"z":...},
 *                            "numberOfInitPoints": 0, "initPointsFlat": [...] }
 *   },
 *   "metadata": {}
 * }
 * \endcode
 *
 * See ``Docs/design/resection-plan-architecture/05-lrp-json-schema.md``
 * for the canonical schema description.
 *
 * \par Optional-field tolerance
 *
 * The reader accepts missing optional fields and applies documented
 * defaults (margins = 0.0, orderIndex = -1, state = "Init").
 * Unknown fields are silently ignored — this is how legacy ``scene.*``
 * blocks from earlier preview-tracking deployments load cleanly.
 * Writer NEVER emits the retired ``scene.*`` block.
 *
 * \par Legacy ``.lrp.fcsv``
 *
 * The reader migrates a v1 ``.lrp.fcsv`` seamlessly on load.  The v1
 * format is a 15-column Markups-fiducial CSV carrying only the 16
 * Bezier control points (LPS).  ``ReadDataInternal`` delegates such a
 * file to ``ReadFcsv``, which parses the points through the legacy
 * ``vtkMRMLLiverResectionCSVStorageNode`` (read-only parse vehicle;
 * LPS -> the markups RAS convention), materialises a
 * ``vtkMRMLBezierSurfaceNode`` carrier under the plan
 * (wrapper-vs-carrier per ADR-0014 §"Fourth layer"), and applies the
 * documented v2 defaults for every legacy-absent field
 * (``safetyMargin_mm`` = 0.0, ``riskMargin_mm`` = 0.0,
 * ``orderIndex`` = -1, ``state`` = ``Init``).  Because those defaults
 * are not recoverable from the legacy file, the migration records a
 * loud warning on ``GetUserMessages()`` naming the defaulted fields.
 * The write path always emits ``.lrp.json``; ``.lrp.fcsv`` is
 * read-only.  See ``Docs/migrations/v1-to-v2.md``.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLResectionPlanStorageNode : public vtkMRMLStorageNode
{
public:
  static vtkMRMLResectionPlanStorageNode* New();
  vtkTypeMacro(vtkMRMLResectionPlanStorageNode, vtkMRMLStorageNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Current JSON schema version emitted by ``WriteDataInternal``.
  static constexpr int SchemaVersion = 2;

  /// Lowest schema version the reader admits.  Equal to
  /// ``SchemaVersion`` — v2 is the only released schema; v1 was
  /// preview-only.
  static constexpr int MinReadableSchemaVersion = 2;

  vtkMRMLNode* CreateNodeInstance() override;

  const char* GetNodeTagName() override { return "ResectionPlanStorage"; }

  /// Returns true iff ``refNode`` is a ``vtkMRMLResectionPlanNode``.
  bool CanReadInReferenceNode(vtkMRMLNode* refNode) override;

  /// Returns true iff ``refNode`` is a ``vtkMRMLResectionPlanNode``.
  bool CanWriteFromReferenceNode(vtkMRMLNode* refNode) override;

  const char* GetDefaultWriteFileExtension() override { return "lrp.json"; }

protected:
  void InitializeSupportedReadFileTypes() override;
  void InitializeSupportedWriteFileTypes() override;

  int ReadDataInternal(vtkMRMLNode* refNode) override;
  int WriteDataInternal(vtkMRMLNode* refNode) override;

protected:
  vtkMRMLResectionPlanStorageNode();
  ~vtkMRMLResectionPlanStorageNode() override;

private:
  vtkMRMLResectionPlanStorageNode(const vtkMRMLResectionPlanStorageNode&) = delete;
  void operator=(const vtkMRMLResectionPlanStorageNode&) = delete;

  /// Write the trimmed v2 ``.lrp.json`` for the given plan to
  /// ``filePath``.  Returns 1 on success, 0 on failure.
  int WriteJson(const std::string& filePath, vtkMRMLResectionPlanNode* plan);

  /// Read the v2 ``.lrp.json`` from ``filePath`` into ``plan``.
  /// Returns 1 on success, 0 on failure.
  int ReadJson(const std::string& filePath, vtkMRMLResectionPlanNode* plan);

  /// Migrate a legacy v1 ``.lrp.fcsv`` from ``filePath`` into ``plan``:
  /// parse the 16 Bezier control points through the legacy CSV parse
  /// vehicle, materialise a ``vtkMRMLBezierSurfaceNode`` carrier under
  /// the plan, apply the documented v2 defaults for every legacy-absent
  /// field, and record a loud user message naming the defaulted fields.
  /// Returns 1 on success, 0 on failure.  See the class docstring
  /// §"Legacy `.lrp.fcsv`".
  int ReadFcsv(const std::string& filePath, vtkMRMLResectionPlanNode* plan);
};

#endif // __vtkmrmlresectionplanstoragenode_h_
