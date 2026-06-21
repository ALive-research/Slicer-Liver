/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2017-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions
  are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

  * Neither the name of Kitware, Inc. nor the names of Contributors
    may be used to endorse or promote products derived from this
    software without specific prior written permission.

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

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef __qSlicerLiverResectionsModuleWidget_h
#define __qSlicerLiverResectionsModuleWidget_h

// Slicer includes
#include "qSlicerAbstractModuleWidget.h"

#include "qSlicerLiverResectionsModuleExport.h"

class qMRMLNodeComboBox;
class qMRMLThreeDView;
class qMRMLThreeDWidget;
class QLabel;
class vtkMRMLNode;
class vtkMRMLViewNode;
class vtkMRMLMarkupsBezierSurfaceNode;
class qSlicerLiverResectionsModuleWidgetPrivate;

/// \brief The Stage-4 "Resection Planning" surface (ADR-0023 §Stage-4).
///
/// LiverResections' first GUI: a resection-surface selector plus a
/// collapsible "Resectogram" drawer.  Selecting a
/// ``vtkMRMLMarkupsBezierSurfaceNode`` that carries a distance map
/// auto-populates the drawer -- no explicit action: the widget ensures exactly
/// one ``vtkMRMLResectogramDisplayNode`` on the surface and ensures the
/// singleton resectogram view node via the Python ``ResectogramViewManager``
/// (LiverResectionsLib).  No custom displayable manager (ADR-0013 §5).
///
/// Auto-population also embeds a single ``qMRMLThreeDWidget`` bound to that
/// singleton view node inside the drawer (the SlicerHyperProbe
/// ``create_three_d_widget`` precedent), so the LayerDM ``ResectogramPipeline``
/// composites the flattened strip in a panel-local view rather than a
/// main-area Slicer layout (ADR-0023 §Stage-4).  Idempotent: re-selecting a
/// valid surface re-targets the existing widget instead of adding a second.
///
/// When the selected surface is invalid (none, or no distance map) the drawer
/// shows a short hint INSTEAD of an edge-on / blank view (ADR-0009
/// §"explainable state").  Re-evaluated on selection change AND on scene/node
/// modified events, so computing a distance map auto-populates the drawer.
class Q_SLICER_QTMODULES_LIVERRESECTIONS_EXPORT qSlicerLiverResectionsModuleWidget : public qSlicerAbstractModuleWidget
{
  Q_OBJECT
public:
  typedef qSlicerAbstractModuleWidget Superclass;
  qSlicerLiverResectionsModuleWidget(QWidget* parent = nullptr);
  ~qSlicerLiverResectionsModuleWidget() override;

  /// The active-resection selector (objectName ``ResectionSurfaceComboBox``).
  Q_INVOKABLE qMRMLNodeComboBox* resectionSurfaceComboBox() const;

  /// The collapsible resectogram drawer (objectName ``ResectogramDrawer``).
  Q_INVOKABLE QWidget* resectogramDrawer() const;

  /// The hint shown in the drawer when no valid resectogram is available
  /// (objectName ``ResectogramHintLabel``).
  Q_INVOKABLE QLabel* resectogramHintLabel() const;

  /// Select ``node`` as the active resection (thin Python-accessible setter).
  Q_INVOKABLE void setActiveResectionNode(vtkMRMLNode* node);

public slots:
  void setMRMLScene(vtkMRMLScene*) override;

protected slots:
  /// Re-evaluate the drawer state on selection change.
  void onActiveResectionChanged(vtkMRMLNode* node);
  /// Re-evaluate the drawer state on scene/node modified events (so computing
  /// a distance map auto-populates the drawer live).
  void refreshResectogramDrawer();

  /// Repaint the embedded resectogram view.  Wired to the active surface's
  /// PointModifiedEvent / ModifiedEvent so a control-point edit updates the
  /// flattened strip live (the standalone embedded view does not repaint on
  /// the Pipeline's RequestRender on its own; ADR-0023 §Stage-4).
  void scheduleResectogramRender();

  /// Replay the initial render kick when the resectogram view's
  /// maximized/restored state changes.  A double-click maximize hands the
  /// singleton resectogram view node to the Slicer layout manager, which
  /// realises a FRESH layout-managed view + LayerDM ``ResectogramPipeline``;
  /// that pipeline needs the same surface ``Modified()`` feed kick the embedded
  /// panel got, or the maximized view renders white-but-empty.  Wired to the
  /// scene's layout node ``ModifiedEvent``; idempotent (ADR-0023 §Stage-4).
  void onLayoutModified();

protected:
  void setup() override;

  /// Embed (create once) the single ``qMRMLThreeDWidget`` bound to the
  /// resectogram singleton ``viewNode`` inside the drawer, then show/raise it.
  /// Idempotent: re-invoking re-targets and re-shows the existing widget
  /// rather than adding a second.
  void showResectogramWidget(vtkMRMLViewNode* viewNode);

  /// Push the flattened-quad camera pose + flat background straight onto the
  /// embedded view's renderer.  The standalone qMRMLThreeDWidget is not
  /// managed by the layout manager, so it does NOT honour the MRML camera /
  /// view-node background; the renderer push is the load-bearing framing
  /// (mirrors the arena's ``_apply_camera_and_background``; ADR-0023 §Stage-4).
  void poseEmbeddedRenderer();

  /// Lock the embedded view's ROTATION: remap the camera widget's
  /// trackball-rotate event translations to WidgetEventNone so the fixed
  /// flattened (u, v) image cannot be orbited (pan / zoom AND the double-click
  /// focus/maximize stay, so the strip can still be enlarged into the main
  /// layout).  Config-only on the upstream camera widget -- no custom
  /// DisplayableManager (ADR-0013 §5; ADR-0023 §Stage-4).
  void lockEmbeddedViewInteraction();

  /// Deferred (next event-loop turn) initial render of the auto-populated
  /// strip: kicks the observed surface's Modified() once to drive the same
  /// observer -> UpdatePipeline -> RequestRender path a manual edit uses, so
  /// the strip is visible on auto-populate with no edit -- after the embedded
  /// widget has been shown/realised (ADR-0023 §Stage-4).
  void kickInitialResectogramRender();

  /// (Re)attach the reactivity observer so editing ``surface``'s control
  /// points repaints the embedded strip.  Symmetric removal on re-target /
  /// teardown so no stale observer fires.
  void observeSurfaceForRender(vtkMRMLMarkupsBezierSurfaceNode* surface);

  /// (Re)attach the observer on the scene's layout node so a double-click
  /// maximize/restore of the resectogram view replays the render feed kick
  /// (``onLayoutModified``).  Symmetric removal on scene change so no stale
  /// observer fires.
  void observeLayoutNode();

  /// Whether a realized GL context is available (a shown main window).  The
  /// embed binding + renderer push + forced render all drive the distance-map
  /// 3D texture upload, which dereferences live GL entry points and crashes
  /// without one (the --no-main-window launched harness); the framing is the
  /// orchestrator's interactive :0 eyeball pass (ADR-0023 §Stage-4).
  bool hasRealizedGLContext() const;

  /// The embedded resectogram view, gated on the embed having happened: returns
  /// the ``qMRMLThreeDView`` only when the widget exists AND a realized GL
  /// context is present (the embed never happens under ``--no-main-window``),
  /// else ``nullptr``.  Centralises the embed-gate preamble the renderer push /
  /// interaction lock / forced render all share (ADR-0023 §Stage-4).
  qMRMLThreeDView* embeddedThreeDView() const;

protected:
  QScopedPointer<qSlicerLiverResectionsModuleWidgetPrivate> d_ptr;

private:
  Q_DECLARE_PRIVATE(qSlicerLiverResectionsModuleWidget);
  Q_DISABLE_COPY(qSlicerLiverResectionsModuleWidget);
};

#endif
