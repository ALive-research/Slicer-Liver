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

#ifndef __vtkslicersubjecthierarchyfolders_h_
#define __vtkslicersubjecthierarchyfolders_h_

#include "vtkSlicerSubjectHierarchyFoldersExport.h"

// VTK includes
#include <vtkObject.h>

class vtkMRMLNode;
class vtkMRMLScene;

/**
 * \class vtkSlicerSubjectHierarchyFolders
 *
 * \brief Standalone utility centralising per-stage Subject-Hierarchy
 * folder placement for Slicer-Liver.
 *
 * ADR-0023 §"Subject Hierarchy management convention" mandates that each
 * node-creating stage groups its node types under a per-stage
 * Subject-Hierarchy folder ("Anatomy", "Vascular Territories",
 * "Resections", "Volumetry"), lazily created on first arrival and reused
 * thereafter.  Three consumers (VascularTerritories, LiverResections,
 * LiverSegmentation) call \ref CollectUnderFolder instead of each
 * open-coding the lookup / lazy-create / reparent dance, so the four
 * modules stay in lockstep on a single binary-identical implementation.
 *
 * The kit name carries no ``Liver`` prefix per the closed-vocabulary
 * convention (the T2.7 rename family).  This is a pure utility, not a
 * MRML node, so it derives from ``vtkObject`` (wrapped, but not a
 * ``vtkMRMLNode`` subclass).  It links MRMLCore only -- the
 * Subject-Hierarchy node + plugin machinery lives there, reachable from a
 * plain ``vtkMRMLScene`` with no Qt or module-Logic dependency
 * (ADR-0003 testability invariant; ADR-0008 §2 "C++ low-level").
 *
 * ADR-0004 reasoned exception: ADR-0004 makes Python the default for
 * orchestration glue, but this utility is wrapped C++ because only a
 * wrapped C++ implementation gives both the C++ callers (the two module
 * logics) AND the Python caller (LiverSegmentation) one binary-identical
 * code path; a Python helper would be unreachable from C++.  See the
 * ADR-0023 §"Subject Hierarchy management convention" amendment.
 */
class VTK_SLICER_SUBJECTHIERARCHYFOLDERS_EXPORT vtkSlicerSubjectHierarchyFolders : public vtkObject
{
public:
  static vtkSlicerSubjectHierarchyFolders* New();
  vtkTypeMacro(vtkSlicerSubjectHierarchyFolders, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /**
   * Reparent \p node under a scene-root Subject-Hierarchy folder named
   * \p folderName, lazily creating the folder on first use and reusing it
   * thereafter.
   *
   * The folder is scoped to *direct children of the scene root* so a
   * same-named folder nested under a Patient/Study/Series subtree is not
   * silently reused (ADR-0023 §"Subject Hierarchy management convention":
   * per-stage scene-root folders).
   *
   * Headless-safe: returns false with no side effect when the scene has
   * no resolvable Subject-Hierarchy node, so a missing SH plugin never
   * breaks the caller's node creation.  Null \p scene / \p node /
   * \p folderName return false cleanly.
   *
   * \return true on success; false on null arguments or absent SH node.
   */
  static bool CollectUnderFolder(vtkMRMLScene* scene, vtkMRMLNode* node, const char* folderName);

  /// Per-stage folder names -- the single source of truth.  Consumers
  /// reference these accessors instead of open-coding the literals so the
  /// four modules stay in lockstep (ADR-0023 §"Subject Hierarchy
  /// management convention" string table).
  static const char* GetAnatomyFolderName();
  static const char* GetVascularTerritoriesFolderName();
  static const char* GetResectionsFolderName();
  static const char* GetVolumetryFolderName();

protected:
  vtkSlicerSubjectHierarchyFolders();
  ~vtkSlicerSubjectHierarchyFolders() override;

private:
  vtkSlicerSubjectHierarchyFolders(const vtkSlicerSubjectHierarchyFolders&) = delete;
  void operator=(const vtkSlicerSubjectHierarchyFolders&) = delete;
};

#endif // __vtkslicersubjecthierarchyfolders_h_
