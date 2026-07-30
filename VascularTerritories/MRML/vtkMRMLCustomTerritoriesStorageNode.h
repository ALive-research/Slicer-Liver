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

  This file was developed for the Slicer-Liver extension as the
  annotation-carrier storage layer of ADR-0037 (VascularTerritories off
  markups), mirroring vtkMRMLResectionPlanStorageNode (the 2026-05-25
  wrapper-vs-carrier amendment to ADR-0014 §"Fourth layer").

==============================================================================*/

#ifndef __vtkmrmlcustomterritoriesstoragenode_h_
#define __vtkmrmlcustomterritoriesstoragenode_h_

#include "vtkSlicerVascularTerritoriesModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorageNode.h>

// STD includes
#include <string>

class vtkMRMLCustomTerritoriesNode;
class vtkMRMLJsonElement;

/**
 * \class vtkMRMLCustomTerritoriesStorageNode
 *
 * \brief ``.vta.json`` storage node for the custom-territories annotation
 *        carrier — the ordered, surface-snapped per-territory annotation
 *        points on ``vtkMRMLCustomTerritoriesNode`` (ADR-0037 §Decision 1).
 *
 * Mirrors ``vtkMRMLResectionPlanStorageNode``: a rooted persistence
 * target for a wrapper/carrier node.  The annotation points are the
 * transition off Slicer markups (ADR-0014 §"Fourth layer"), so this
 * storage node is what round-trips them to disk.
 *
 * Schema shape (v1):
 *
 * \code
 * {
 *   "schemaVersion": 1,
 *   "annotationPoints": {
 *     "SegmentVII":  [ { "xyz": [x, y, z] }, { "xyz": [x, y, z] }, ... ],
 *     "SegmentVIII": [ { "xyz": [x, y, z] }, ... ]
 *   },
 *   "territoryDisplay": {
 *     "SegmentVII": { "color": [r, g, b], "label": "…", "visibility": true,
 *                     "status": "Completed" }
 *   }
 * }
 * \endcode
 *
 * The ``territoryDisplay`` object carries the per-territory display slot
 * (colour / label / visibility / status) ADR-0037 §Decision 3 + the
 * "Per-territory status + derived edit-lock" amendment add; it is optional
 * and additive to the v1 schema (a document without it reads back with the
 * carrier's display defaults, and a document without the ``status`` field
 * reads back ``NotStarted``).  The edit-lock is DERIVED from the status on
 * read, so no lock field is persisted.
 *
 * The per-territory arrays are ORDERED — placement order round-trips
 * identically (ADR-0037 §Conformance [test]).  The storage node is typed
 * to ``vtkMRMLCustomTerritoriesNode`` and rejects any other node (e.g.
 * the Auto/Couinaud ``vtkMRMLStdCouinaudTerritoriesNode``, which carries
 * no annotation points).
 */
class VTK_SLICER_VASCULARTERRITORIES_MODULE_MRML_EXPORT vtkMRMLCustomTerritoriesStorageNode : public vtkMRMLStorageNode
{
public:
  static vtkMRMLCustomTerritoriesStorageNode* New();
  vtkTypeMacro(vtkMRMLCustomTerritoriesStorageNode, vtkMRMLStorageNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Current JSON schema version emitted by ``WriteDataInternal``.
  static constexpr int SchemaVersion = 1;

  /// Lowest schema version the reader admits.
  static constexpr int MinReadableSchemaVersion = 1;

  vtkMRMLNode* CreateNodeInstance() override;

  const char* GetNodeTagName() override { return "CustomTerritoriesStorage"; }

  /// Returns true iff ``refNode`` is a ``vtkMRMLCustomTerritoriesNode``.
  bool CanReadInReferenceNode(vtkMRMLNode* refNode) override;

  /// Returns true iff ``refNode`` is a ``vtkMRMLCustomTerritoriesNode``.
  bool CanWriteFromReferenceNode(vtkMRMLNode* refNode) override;

  const char* GetDefaultWriteFileExtension() override { return "vta.json"; }

protected:
  void InitializeSupportedReadFileTypes() override;
  void InitializeSupportedWriteFileTypes() override;

  int ReadDataInternal(vtkMRMLNode* refNode) override;
  int WriteDataInternal(vtkMRMLNode* refNode) override;

protected:
  vtkMRMLCustomTerritoriesStorageNode();
  ~vtkMRMLCustomTerritoriesStorageNode() override;

private:
  vtkMRMLCustomTerritoriesStorageNode(const vtkMRMLCustomTerritoriesStorageNode&) = delete;
  void operator=(const vtkMRMLCustomTerritoriesStorageNode&) = delete;

  /// Write the v1 ``.vta.json`` for ``carrier`` to ``filePath``.  Returns
  /// 1 on success, 0 on failure.
  int WriteJson(const std::string& filePath, vtkMRMLCustomTerritoriesNode* carrier);

  /// Read the v1 ``.vta.json`` from ``filePath`` into ``carrier``.
  /// Returns 1 on success, 0 on failure.
  int ReadJson(const std::string& filePath, vtkMRMLCustomTerritoriesNode* carrier);

  /// Read the per-territory display slot (colour / label / visibility) from
  /// the parsed ``territoryDisplay`` object into ``carrier``.  A no-op when
  /// the document carries no display slot.
  void ReadDisplay(vtkMRMLJsonElement* root, vtkMRMLCustomTerritoriesNode* carrier, const std::string& filePath);
};

#endif // __vtkmrmlcustomterritoriesstoragenode_h_
