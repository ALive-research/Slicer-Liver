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
  as part of the v2.1 NURBS rollout (NURBS-1 deliverable, see
  ADR-0022 §"Decision 2 — Schema v3").

==============================================================================*/

#ifndef __vtkmrmlnurbssurfacestoragenode_h_
#define __vtkmrmlnurbssurfacestoragenode_h_

#include "vtkSlicerLiverResectionsModuleMRMLExport.h"

// This module MRML includes
#include "vtkMRMLBezierSurfaceStorageNode.h"

/**
 * \class vtkMRMLNurbsSurfaceStorageNode
 *
 * \brief Thin subclass of ``vtkMRMLBezierSurfaceStorageNode`` that
 *        exists so each surface data-node family has a dedicated
 *        default-storage class (matching Slicer-core's
 *        ``CreateDefaultStorageNode`` convention) while sharing the
 *        underlying schema-v3 ``.lrp.json`` read / write
 *        implementation.
 *
 * Per ADR-0022 §"Decision 2 — Schema v3" the on-disk schema is
 * unified: a single ``.lrp.json`` shape carries both Bezier and
 * NURBS surfaces, dispatched on the top-level ``surfaceType``
 * discriminator.  This subclass overrides only the node-tag-name
 * + ``CreateNodeInstance`` plumbing; the read / write paths,
 * validation, and JSON layout all live on the Bezier base class.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRML_EXPORT vtkMRMLNurbsSurfaceStorageNode : public vtkMRMLBezierSurfaceStorageNode
{
public:
  static vtkMRMLNurbsSurfaceStorageNode* New();
  vtkTypeMacro(vtkMRMLNurbsSurfaceStorageNode, vtkMRMLBezierSurfaceStorageNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  vtkMRMLNode* CreateNodeInstance() override;

  /// Get node XML tag name.  ``NurbsSurfaceStorage`` matches the
  /// ``BezierSurfaceStorage`` precedent on the base class — no
  /// ``Liver`` prefix, mirroring the data-node naming convention.
  const char* GetNodeTagName() override { return "NurbsSurfaceStorage"; }

protected:
  vtkMRMLNurbsSurfaceStorageNode();
  ~vtkMRMLNurbsSurfaceStorageNode() override;

private:
  vtkMRMLNurbsSurfaceStorageNode(const vtkMRMLNurbsSurfaceStorageNode&) = delete;
  void operator=(const vtkMRMLNurbsSurfaceStorageNode&) = delete;
};

#endif //__vtkmrmlnurbssurfacestoragenode_h_
