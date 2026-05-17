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
  v2.0.0 release tracker — see ADR-0014 §3).

==============================================================================*/

#ifndef __vtkMRMLLiverBezierSurfaceDisplayableManager3D_h
#define __vtkMRMLLiverBezierSurfaceDisplayableManager3D_h

// LiverResections MRMLDM includes
#include "vtkSlicerLiverResectionsModuleMRMLDisplayableManagerExport.h"

// MRMLDisplayableManager includes
#include <vtkMRMLAbstractThreeDViewDisplayableManager.h>

// VTK includes
#include <vtkSmartPointer.h>
#include <vtkWeakPointer.h>

// STD includes
#include <map>
#include <string>

class vtkLiverBezierWidget;
class vtkMRMLBezierSurfaceNode;
class vtkMRMLNode;

/**
 * \class vtkMRMLLiverBezierSurfaceDisplayableManager3D
 *
 * \brief Displayable manager for ``vtkMRMLBezierSurfaceNode`` in 3D
 *        views.
 *
 * Observes ``vtkMRMLScene`` and spawns one ``vtkLiverBezierWidget``
 * (+ ``vtkLiverBezierRepresentation``) per (data node, view) pair so
 * the Bezier-surface resection plan is interactive in every 3D view
 * registered with the displayable-manager factory.
 *
 * Architectural role (ADR-0013 / ADR-0014):
 *
 *   - The **LayerDM Pipeline** (Python, per-view actor pipeline —
 *     ``LiverBezierSurfacePipeline.py``) draws the surface +
 *     decorations *passively*: it consumes display-node fields and
 *     produces actors.  It does NOT own interactive state.
 *   - This **displayable manager** is the C++ glue that owns the
 *     *interactive* widget per view.  It observes the scene for
 *     ``vtkMRMLBezierSurfaceNode`` add / remove, builds the widget,
 *     wires it to the view's renderer + interactor, and tears it down
 *     on remove / scene close.
 *
 * Both layers are needed: a passive LayerDM Pipeline alone cannot
 * mutate the data node from picks / drags (no interactor binding);
 * a DM-spawned widget alone cannot share the surface-decoration
 * pipeline across views (no per-view actor cache).
 *
 * Slice-view (2D) coverage is out of scope for this stack iteration —
 * see ``TODO(T2.6-DM-2D)`` in ``qSlicerLiverResectionsModule::setup()``.
 * The existing ``vtkLiverBezierRepresentation`` is 3D-only and a
 * slice-intersection contour requires a separate representation class.
 *
 * \par Widget registry
 *
 * Keyed by the data node's MRML ID (``std::string``) — not by raw
 * pointer — so the registry survives a scene swap (``EndImportEvent``
 * fires AFTER all nodes have new addresses but stable IDs).
 *
 * \par Test discipline (ADR-0008 §2)
 *
 * Lifecycle is exercised headlessly by
 * ``vtkMRMLLiverBezierSurfaceDisplayableManager3DTest1``: construct
 * the DM, attach a scene, add / remove / re-import Bezier-surface
 * nodes, assert the registry tracks each transition.
 */
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRMLDISPLAYABLEMANAGER_EXPORT vtkMRMLLiverBezierSurfaceDisplayableManager3D : public vtkMRMLAbstractThreeDViewDisplayableManager
{
public:
  static vtkMRMLLiverBezierSurfaceDisplayableManager3D* New();
  vtkTypeMacro(vtkMRMLLiverBezierSurfaceDisplayableManager3D, vtkMRMLAbstractThreeDViewDisplayableManager);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Number of widgets currently tracked.  Provided primarily for the
  /// ctkTest driver — the production code path uses ``GetWidget``.
  std::size_t GetNumberOfWidgets() const { return this->Widgets.size(); }

  /// Look up the widget associated with a data node, or nullptr if
  /// none.  Used by tests and by the registration-point probe in
  /// ``qSlicerLiverResectionsModule::setup()``.
  vtkLiverBezierWidget* GetWidget(vtkMRMLBezierSurfaceNode* node);

protected:
  vtkMRMLLiverBezierSurfaceDisplayableManager3D();
  ~vtkMRMLLiverBezierSurfaceDisplayableManager3D() override;

  /// Hook scene observation: wire ``NodeAddedEvent``,
  /// ``NodeRemovedEvent``, ``EndImportEvent``, ``EndCloseEvent``.
  void SetMRMLSceneInternal(vtkMRMLScene* newScene) override;

  /// Per-node lifecycle.  ``OnMRMLSceneNodeAdded`` filters to
  /// ``vtkMRMLBezierSurfaceNode``; ``OnMRMLSceneNodeRemoved`` symmetric.
  void OnMRMLSceneNodeAdded(vtkMRMLNode* node) override;
  void OnMRMLSceneNodeRemoved(vtkMRMLNode* node) override;

  /// Scene-level lifecycle.  EndImport rebuilds the registry from
  /// scratch (the scene may carry pre-existing Bezier-surface nodes
  /// loaded from disk); EndClose tears every widget down.
  void OnMRMLSceneEndImport() override;
  void OnMRMLSceneEndClose() override;

  /// Build the widget for a freshly-tracked node.  Idempotent —
  /// re-registering an already-tracked node tears the old widget down
  /// first.  Returns true on success.
  bool AddBezierSurfaceNode(vtkMRMLBezierSurfaceNode* node);

  /// Drop the widget for a node.  No-op if the node is not tracked.
  void RemoveBezierSurfaceNode(vtkMRMLBezierSurfaceNode* node);

  /// Drop every widget.  Called from ``OnMRMLSceneEndClose`` and from
  /// the destructor.
  void RemoveAllWidgets();

  /// Widget registry.  Keyed by MRML node ID — survives a scene swap
  /// where node addresses change but IDs are preserved.
  std::map<std::string, vtkSmartPointer<vtkLiverBezierWidget>> Widgets;

private:
  vtkMRMLLiverBezierSurfaceDisplayableManager3D(const vtkMRMLLiverBezierSurfaceDisplayableManager3D&) = delete;
  void operator=(const vtkMRMLLiverBezierSurfaceDisplayableManager3D&) = delete;
};

#endif
