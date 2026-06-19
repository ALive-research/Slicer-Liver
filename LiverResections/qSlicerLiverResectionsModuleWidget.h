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
class qMRMLThreeDWidget;
class QAbstractButton;
class vtkMRMLNode;
class vtkMRMLViewNode;
class vtkMRMLMarkupsBezierSurfaceNode;
class qSlicerLiverResectionsModuleWidgetPrivate;

/// \brief The Stage-4 "Resection Planning" surface (ADR-0023 §Stage-4).
///
/// LiverResections' first GUI: a resection-surface selector plus a gated
/// [Open resectogram view] action.  The action is enabled iff the selected
/// ``vtkMRMLMarkupsBezierSurfaceNode`` carries a distance map; triggering it
/// ensures exactly one ``vtkMRMLResectogramDisplayNode`` on the surface and
/// ensures the singleton resectogram view node via the Python
/// ``ResectogramViewManager`` (LiverResectionsLib).  No custom displayable
/// manager (ADR-0013 §5).
///
/// Triggering also embeds a single ``qMRMLThreeDWidget`` bound to that
/// singleton view node into this module's side panel (the SlicerHyperProbe
/// ``create_three_d_widget`` precedent), so the LayerDM ``ResectogramPipeline``
/// composites the flattened strip in a panel-local view rather than a
/// main-area Slicer layout (ADR-0023 §Stage-4).  Idempotent: re-triggering
/// shows/raises the existing widget instead of adding a second.
class Q_SLICER_QTMODULES_LIVERRESECTIONS_EXPORT qSlicerLiverResectionsModuleWidget : public qSlicerAbstractModuleWidget
{
  Q_OBJECT
public:
  typedef qSlicerAbstractModuleWidget Superclass;
  qSlicerLiverResectionsModuleWidget(QWidget* parent = nullptr);
  ~qSlicerLiverResectionsModuleWidget() override;

  /// The active-resection selector (objectName ``ResectionSurfaceComboBox``).
  Q_INVOKABLE qMRMLNodeComboBox* resectionSurfaceComboBox() const;

  /// The gated [Open resectogram view] action button
  /// (objectName ``OpenResectogramViewButton``).
  Q_INVOKABLE QAbstractButton* openResectogramViewButton() const;

  /// Select ``node`` as the active resection (thin Python-accessible setter).
  Q_INVOKABLE void setActiveResectionNode(vtkMRMLNode* node);

public slots:
  void setMRMLScene(vtkMRMLScene*) override;

  /// Trigger the gated open-resectogram-view action: ensure a resectogram
  /// display node on the active surface (idempotent) and ensure the
  /// singleton resectogram view node.
  void openResectogramView();

protected slots:
  /// Re-evaluate the gating predicate on selection change.
  void onActiveResectionChanged(vtkMRMLNode* node);
  /// Re-evaluate the gating predicate on scene/node modified events (so
  /// computing a distance map flips the button live).
  void updateOpenActionState();

protected:
  void setup() override;

  /// Embed (create once) the single ``qMRMLThreeDWidget`` bound to the
  /// resectogram singleton ``viewNode`` into this module's panel, then
  /// show/raise it.  Idempotent: re-invoking re-targets and re-shows the
  /// existing widget rather than adding a second.
  void showResectogramWidget(vtkMRMLViewNode* viewNode);

protected:
  QScopedPointer<qSlicerLiverResectionsModuleWidgetPrivate> d_ptr;

private:
  Q_DECLARE_PRIVATE(qSlicerLiverResectionsModuleWidget);
  Q_DISABLE_COPY(qSlicerLiverResectionsModuleWidget);
};

#endif
