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

  This file was developed for the Slicer-Liver extension as the seed-carrier
  storage layer of the ADR-0038-amendment seeds-off-markups migration
  (volumetry-seeds-layerdm-plan.md §3a), mirroring
  vtkMRMLCustomTerritoriesStorageNode (ADR-0014 §"Fourth layer").

==============================================================================*/

#ifndef __vtkmrmlvolumetryseedsstoragenode_h_
#define __vtkmrmlvolumetryseedsstoragenode_h_

#include "vtkSlicerLiverVolumetryModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorageNode.h>

// STD includes
#include <string>

class vtkMRMLVolumetrySeedsNode;

/**
 * \class vtkMRMLVolumetrySeedsStorageNode
 *
 * \brief ``.vsd.json`` storage node for the volumetry seed carrier — the
 *        flat, ORDERED per-seed coordinate + label + colour on
 *        ``vtkMRMLVolumetrySeedsNode`` (ADR-0038-amendment §3a).
 *
 * Mirrors ``vtkMRMLCustomTerritoriesStorageNode``: a rooted persistence
 * target for a carrier node moved off Slicer markups (ADR-0014 §"Fourth
 * layer").
 *
 * Schema shape (v1):
 *
 * \code
 * {
 *   "schemaVersion": 1,
 *   "seeds": [
 *     { "xyz": [x, y, z], "label": "SegmentV",  "color": [r, g, b] },
 *     { "xyz": [x, y, z], "label": "SegmentVI", "color": [r, g, b] }
 *   ]
 * }
 * \endcode
 *
 * The ``seeds`` array is ORDERED — placement order + per-seed labels +
 * per-seed colours round-trip identically (ADR-0038 §Conformance, the
 * segment-name fidelity).  The storage node is typed to
 * ``vtkMRMLVolumetrySeedsNode`` and rejects any other node.
 */
class VTK_SLICER_LIVERVOLUMETRY_MODULE_MRML_EXPORT vtkMRMLVolumetrySeedsStorageNode : public vtkMRMLStorageNode
{
public:
  static vtkMRMLVolumetrySeedsStorageNode* New();
  vtkTypeMacro(vtkMRMLVolumetrySeedsStorageNode, vtkMRMLStorageNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Current JSON schema version emitted by ``WriteDataInternal``.
  static constexpr int SchemaVersion = 1;

  /// Lowest schema version the reader admits.
  static constexpr int MinReadableSchemaVersion = 1;

  vtkMRMLNode* CreateNodeInstance() override;

  const char* GetNodeTagName() override { return "VolumetrySeedsStorage"; }

  /// Returns true iff ``refNode`` is a ``vtkMRMLVolumetrySeedsNode``.
  bool CanReadInReferenceNode(vtkMRMLNode* refNode) override;

  /// Returns true iff ``refNode`` is a ``vtkMRMLVolumetrySeedsNode``.
  bool CanWriteFromReferenceNode(vtkMRMLNode* refNode) override;

  const char* GetDefaultWriteFileExtension() override { return "vsd.json"; }

protected:
  void InitializeSupportedReadFileTypes() override;
  void InitializeSupportedWriteFileTypes() override;

  int ReadDataInternal(vtkMRMLNode* refNode) override;
  int WriteDataInternal(vtkMRMLNode* refNode) override;

protected:
  vtkMRMLVolumetrySeedsStorageNode();
  ~vtkMRMLVolumetrySeedsStorageNode() override;

private:
  vtkMRMLVolumetrySeedsStorageNode(const vtkMRMLVolumetrySeedsStorageNode&) = delete;
  void operator=(const vtkMRMLVolumetrySeedsStorageNode&) = delete;

  /// Write the v1 ``.vsd.json`` for ``carrier`` to ``filePath``.  Returns
  /// 1 on success, 0 on failure.
  int WriteJson(const std::string& filePath, vtkMRMLVolumetrySeedsNode* carrier);

  /// Read the v1 ``.vsd.json`` from ``filePath`` into ``carrier``.
  /// Returns 1 on success, 0 on failure.
  int ReadJson(const std::string& filePath, vtkMRMLVolumetrySeedsNode* carrier);
};

#endif // __vtkmrmlvolumetryseedsstoragenode_h_
