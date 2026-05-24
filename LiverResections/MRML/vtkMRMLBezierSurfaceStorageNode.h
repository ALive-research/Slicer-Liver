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
  as part of task T2.5 of the v2.0.0 release (LiverResources all-in
  migration; see ADR-0014 §5).

==============================================================================*/

#ifndef __vtkmrmlbeziersurfacestoragenode_h_
#define __vtkmrmlbeziersurfacestoragenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// MRML includes
#include <vtkMRMLStorageNode.h>

/**
 * \class vtkMRMLBezierSurfaceStorageNode
 *
 * \brief Storage node for ``vtkMRMLBezierSurfaceNode`` — the new
 *        ``.lrp.json`` "single file per resection plan" format
 *        committed by [ADR-0014 §5](../../Docs/adr/0014-livermarkups-dissolution.md).
 *
 * The new format collects every field currently round-tripped by
 * ``vtkMRMLBezierSurfaceNode::WriteXML`` into a single
 * surgeon-to-surgeon JSON document.  Versioned via an explicit
 * top-level ``schemaVersion`` integer (currently ``1``).  Future
 * schema revisions bump the integer and gain explicit migration
 * branches in ``ReadDataInternal``.
 *
 * \par Legacy ``.lrp.fcsv`` support
 *
 * The pre-LayerDM ``vtkMRMLLiverResectionCSVStorageNode`` wrote a
 * markups-fiducial CSV (15-column standard schema) containing the
 * 16 Bezier control points and nothing else — no state, no
 * init-mode metadata, no plane/spheroid parameters.  The new
 * storage node reads ``.lrp.fcsv`` in load-only migration mode so
 * existing scenes load on first open after the v2.0.0 jump; the
 * surgeon then saves the plan in ``.lrp.json`` on next write.
 *
 * Legacy writes are NOT supported — ``CanWriteFromReferenceNode``
 * returns true only for the new node class, and the supported
 * write file-types list contains ``.lrp.json`` exclusively.  Per
 * ADR-0007's D-class compatibility-break category, the
 * ``.lrp.fcsv`` deprecation is part of the v2.0.0 MAJOR bump.
 *
 * \par JSON schema (v2 — ADR-0023 §"Persistence")
 *
 * See the in-source documentation at the top of
 * ``vtkMRMLBezierSurfaceStorageNode.cxx`` for the canonical
 * schema description.  Briefly:
 *
 *   - ``schemaVersion``: int, currently 2 (writer + reader).  v1
 *     was preview-only and never shipped; the reader rejects it.
 *   - ``state``: "Init" | "Planning" | "Confirmed"
 *   - ``initMode``: "SlicingPlane" | "DistanceSpheroid"
 *   - ``rows`` / ``cols``: control-polygon shape per ADR-0018 §1
 *     (square only; in ``{(3, 3), (4, 4)}``).
 *   - ``controlGrid``: array of ``3 * rows * cols`` doubles
 *     (row-major; 27 for 3×3, 48 for 4×4).
 *   - ``slicingPlane``: {origin, normal, initPointsFlat}
 *   - ``distanceSpheroid``: {center, radius{x,y,z}, initPointsFlat}
 *   - ``metadata``: object (empty for v2.0; reserved for richer
 *     metadata — timestamps, surgeon ID — in a later schema
 *     revision per ADR-0014 §5).
 *   - ``resection``: {name, safetyMargin_mm, riskMargin_mm,
 *     orderIndex} — surgeon-facing field roster (ADR-0023
 *     §"Persistence").  The on-disk margin fields source from the
 *     existing ``vtkMRMLLiverResectionNode::ResectionMargin`` and
 *     ``UncertaintyMargin`` members; the storage path renames them
 *     to surgeon-facing labels without touching the in-memory MRML
 *     class.  See the schema-header comment in the .cxx for the
 *     full mapping table.
 *   - ``scene``: {classification, volumetryPartitions,
 *     stageSelection} — scene-wide context the Liver shell restores
 *     on file open (ADR-0023 §"Persistence" — per-stage last-selection).
 *
 * \par Optional-field tolerance (within v2)
 *
 * The ``resection`` and ``scene`` blocks are optional on read.  A
 * preview-tracking v2 file written before the surgeon-state fields
 * were wired (no such files in the public release contract) loads
 * with documented defaults: name = MRML display name, margins =
 * 0.0, orderIndex = -1, classification absent, volumetry partitions
 * empty, stageSelection absent.  The writer always emits the full
 * v2 shape.
 *
 * \par See also
 *
 *   - ``vtkMRMLBezierSurfaceNode`` — the data node this storage
 *     node serializes (ADR-0014 §1).
 *   - ``vtkMRMLLiverResectionCSVStorageNode`` — the legacy storage
 *     node whose format we read for migration; retired by task
 *     T2.7.
 *   - ``vtkMRMLMarkupsJsonStorageNode`` (Slicer core) — the
 *     in-tree precedent for using ``vtkMRMLJsonReader`` /
 *     ``vtkMRMLJsonWriter``.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLBezierSurfaceStorageNode : public vtkMRMLStorageNode
{
public:
  static vtkMRMLBezierSurfaceStorageNode* New();
  vtkTypeMacro(vtkMRMLBezierSurfaceStorageNode, vtkMRMLStorageNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Current JSON schema version emitted by ``WriteDataInternal``.
  /// Bump this integer in lock-step with any documented schema
  /// extension; ``ReadDataInternal`` MUST grow an explicit branch
  /// for every old version it intends to keep loading.  Per
  /// ADR-0023 §"Persistence" v2 is the unified schema for the
  /// 2026 v2.0.0 release — it carries the variable-size Bezier
  /// shape (``rows`` / ``cols``), the surgeon-facing ``resection``
  /// block (name + Safety/Risk margins + orderIndex), and the
  /// scene-wide ``scene`` block (classification, volumetry
  /// partitions, stage selection).  v1 was preview-only and never
  /// shipped; the reader rejects it.
  static constexpr int SchemaVersion = 2;

  /// Lowest schema version the reader admits.  Equal to
  /// ``SchemaVersion`` for v2.0.0 since v1 was preview-only and is
  /// not part of the released contract.  A future v3 bump should
  /// widen this band to keep v2 files readable.
  static constexpr int MinReadableSchemaVersion = 2;

  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Storage, Model).  No ``Liver``
  /// prefix per the new naming convention landed for the data
  /// node family (vtkMRMLBezierSurfaceNode / DisplayNode).
  const char* GetNodeTagName() override { return "BezierSurfaceStorage"; }

  /// Returns true iff ``refNode`` is a ``vtkMRMLBezierSurfaceNode``.
  bool CanReadInReferenceNode(vtkMRMLNode* refNode) override;

  /// Returns true iff ``refNode`` is a ``vtkMRMLBezierSurfaceNode``.
  bool CanWriteFromReferenceNode(vtkMRMLNode* refNode) override;

  /// Return the default extension emitted by ``WriteDataInternal``
  /// — ``"lrp.json"`` for the new format.
  const char* GetDefaultWriteFileExtension() override { return "lrp.json"; }

protected:
  /// File types registered for the read dialog.  Adds both
  /// ``.lrp.json`` (the new format) AND ``.lrp.fcsv`` (legacy
  /// load-only migration).
  void InitializeSupportedReadFileTypes() override;

  /// File types registered for the write dialog.  ``.lrp.json``
  /// only — legacy writes are not supported (ADR-0014 §5).
  void InitializeSupportedWriteFileTypes() override;

  /// Dispatches on the file extension:
  ///   - ``.lrp.json`` → JSON parse path (current schema).
  ///   - ``.lrp.fcsv`` → legacy migration path (markups-fiducial
  ///                      CSV; control points only).
  int ReadDataInternal(vtkMRMLNode* refNode) override;

  /// Emits a single ``.lrp.json`` document.  Legacy ``.lrp.fcsv``
  /// writes are rejected with a ``vtkErrorMacro`` and a 0 return.
  int WriteDataInternal(vtkMRMLNode* refNode) override;

protected:
  vtkMRMLBezierSurfaceStorageNode();
  ~vtkMRMLBezierSurfaceStorageNode() override;

private:
  vtkMRMLBezierSurfaceStorageNode(const vtkMRMLBezierSurfaceStorageNode&) = delete;
  void operator=(const vtkMRMLBezierSurfaceStorageNode&) = delete;

  /// Read the new-format ``.lrp.json`` from ``filePath`` into
  /// ``surfaceNode``.  Returns 1 on success, 0 on failure (with
  /// errors routed through the storage node's user-messages
  /// collection).
  int ReadJson(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);

  /// Read the legacy ``.lrp.fcsv`` from ``filePath`` into
  /// ``surfaceNode``.  Returns 1 on success, 0 on failure.  See
  /// the implementation for the legacy-field → new-field mapping
  /// table.
  int ReadLegacyFcsv(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);

  /// Write the new-format ``.lrp.json`` for ``surfaceNode`` to
  /// ``filePath``.  Returns 1 on success, 0 on failure.
  int WriteJson(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);
};

#endif //__vtkmrmlbeziersurfacestoragenode_h_
