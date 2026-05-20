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
 * \par JSON schema (v3 — ADR-0022 §"Decision 2 — Schema v3")
 *
 * See the in-source documentation at the top of
 * ``vtkMRMLBezierSurfaceStorageNode.cxx`` for the canonical
 * schema description.  Briefly:
 *
 *   - ``schemaVersion``: int, currently 3 (writer); reader accepts
 *     v1 + v2 + v3.
 *   - ``surfaceType``: ``"Bezier"`` or ``"NURBS"`` (v3 only; absent
 *     in v1 / v2 → implicit ``"Bezier"``).
 *   - ``state``: "Init" | "Planning" | "Confirmed"
 *   - ``initMode``: "SlicingPlane" | "DistanceSpheroid"
 *   - ``rows`` / ``cols``: control-polygon shape (v2+; v1 implicit
 *     4×4).  For Bezier per ADR-0018 §1 square + in
 *     ``{(3, 3), (4, 4)}``; for NURBS per ADR-0022 §"IVar roster"
 *     ``rows >= degreeU + 1`` and ``cols >= degreeV + 1``.
 *   - ``controlGrid``: array of ``3 * rows * cols`` doubles
 *     (row-major).
 *   - ``slicingPlane``: {origin, normal, initPoints} (Bezier only).
 *   - ``distanceSpheroid``: {center, radius{x,y,z}, initPoints}
 *     (Bezier only).
 *   - NURBS-only: ``degreeU``, ``degreeV`` (int), ``knotsU``,
 *     ``knotsV`` (double arrays), ``weights`` (double array,
 *     all positive).
 *   - ``metadata``: object.
 *
 * \par v1 → v2 → v3 migration
 *
 * - v1 (no ``rows`` / ``cols`` / ``surfaceType``) — implicit 4×4
 *   Bezier per ADR-0018 §1.
 * - v2 (``rows`` + ``cols`` present, no ``surfaceType``) — explicit
 *   Bezier shape.
 * - v3 (``surfaceType`` present) — dispatch on ``Bezier`` vs
 *   ``NURBS``.  Bezier writes include none of the NURBS-only fields;
 *   NURBS writes include all of them.
 *
 * The writer always emits v3 with the most-specific ``surfaceType``
 * and the minimum redundant fields.  Round-trip of a v1 / v2 file
 * produces a v3 file on the next save.
 *
 * \par Sharing the storage class between Bezier and NURBS
 *
 * Per ADR-0022 §"Decision 2 — Schema v3" + the NURBS-1 design note,
 * a single storage class handles both surface types — dispatched on
 * ``surfaceType`` at read time and on the concrete reference-node
 * class at write time.  ``vtkMRMLNurbsSurfaceStorageNode`` is a
 * thin subclass that exists so each data-node family has a
 * dedicated default-storage class (matching Slicer-core's
 * ``CreateDefaultStorageNode`` lookup convention) while sharing the
 * read / write implementation here.
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
  /// ADR-0022 §"Decision 2 — Schema v3" the reader accepts v1
  /// (implicit 4×4 Bezier), v2 (explicit Bezier shape), and v3
  /// (explicit ``surfaceType`` discriminator).
  static constexpr int SchemaVersion = 3;

  /// Lowest schema version the reader admits.  v1 files (no
  /// ``rows`` / ``cols`` / ``surfaceType``) load as 4×4 Bezier per
  /// the ADR-0018 §1 migration path.
  static constexpr int MinReadableSchemaVersion = 1;

  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name (like Storage, Model).  No ``Liver``
  /// prefix per the new naming convention landed for the data
  /// node family (vtkMRMLBezierSurfaceNode / DisplayNode).
  const char* GetNodeTagName() override { return "BezierSurfaceStorage"; }

  /// Returns true iff ``refNode`` is a ``vtkMRMLBezierSurfaceNode``
  /// or a ``vtkMRMLNurbsSurfaceNode`` (per ADR-0022 §"Decision 2 —
  /// Schema v3" the storage class serves both surface types; the
  /// schema-v3 ``surfaceType`` discriminator picks the right read
  /// path).
  bool CanReadInReferenceNode(vtkMRMLNode* refNode) override;

  /// Returns true iff ``refNode`` is a ``vtkMRMLBezierSurfaceNode``
  /// or a ``vtkMRMLNurbsSurfaceNode``.  Same dispatch as
  /// ``CanReadInReferenceNode``.
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

  /// Read a Bezier-typed ``.lrp.json`` from ``filePath`` into
  /// ``surfaceNode``.  Returns 1 on success, 0 on failure.  Used
  /// for v1 / v2 files (implicit Bezier) and for v3 files with
  /// ``surfaceType: "Bezier"``.
  int ReadJsonBezier(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);

  /// Read a NURBS-typed ``.lrp.json`` from ``filePath`` into
  /// ``surfaceNode``.  Returns 1 on success, 0 on failure.  Used
  /// for v3 files with ``surfaceType: "NURBS"``.  Per ADR-0022
  /// §"Validation rules per surface type", validates degree range,
  /// knot lengths, weights positivity, controlGrid length; any
  /// violation aborts with ``vtkErrorMacro``.
  int ReadJsonNurbs(const std::string& filePath, class vtkMRMLNurbsSurfaceNode* surfaceNode);

  /// Read the legacy ``.lrp.fcsv`` from ``filePath`` into
  /// ``surfaceNode``.  Returns 1 on success, 0 on failure.  See
  /// the implementation for the legacy-field → new-field mapping
  /// table.  Legacy CSV is Bezier-only — NURBS predates no legacy
  /// format and the path returns 0 for NURBS sinks.
  int ReadLegacyFcsv(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);

  /// Write the Bezier-typed ``.lrp.json`` for ``surfaceNode`` to
  /// ``filePath``.  Returns 1 on success, 0 on failure.  Always
  /// emits ``schemaVersion: 3`` + ``surfaceType: "Bezier"``.
  int WriteJsonBezier(const std::string& filePath, class vtkMRMLBezierSurfaceNode* surfaceNode);

  /// Write the NURBS-typed ``.lrp.json`` for ``surfaceNode`` to
  /// ``filePath``.  Returns 1 on success, 0 on failure.  Always
  /// emits ``schemaVersion: 3`` + ``surfaceType: "NURBS"`` plus the
  /// NURBS-specific fields (``degreeU``, ``degreeV``, ``knotsU``,
  /// ``knotsV``, ``weights``).
  int WriteJsonNurbs(const std::string& filePath, class vtkMRMLNurbsSurfaceNode* surfaceNode);
};

#endif //__vtkmrmlbeziersurfacestoragenode_h_
