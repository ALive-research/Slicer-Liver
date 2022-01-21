/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#include "qSlicerLiverResectionsTableView.h"

#include "ui_qSlicerLiverResectionsTableView.h"

// Slicer includes
#include "qSlicerApplication.h"
#include "qSlicerLiverResectionsModel.h"

#include <QDebug>

//-----------------------------------------------------------------------------
class qSlicerLiverResectionsTableViewPrivate: public Ui_qSlicerLiverResectionsTableView
{
  Q_DECLARE_PUBLIC(qSlicerLiverResectionsTableView);

protected:
  qSlicerLiverResectionsTableView* const q_ptr;
public:
  qSlicerLiverResectionsTableViewPrivate(qSlicerLiverResectionsTableView& object);
  void init();

  /// Sets table message and takes care of the visibility of the label
  void setMessage(const QString& message);

public:
  // /// Resection MRML node containing shown segments
  // vtkWeakPointer<vtkMRMLResectionNode> ResectionNode;

  // /// Flag determining whether the long-press per-view segment visibility options are available
  // bool AdvancedSegmentVisibility;

  /// Currently, if we are requesting segment display information from the
  /// segmentation display node,  the display node may emit modification events.
  /// We make sure these events do not interrupt the update process by setting
  /// IsUpdatingWidgetFromMRML to true when an update is already in progress.
  bool IsUpdatingWidgetFromMRML;

  bool IsFilterBarVisible;

  qSlicerLiverResectionsModel* Model;

  // QIcon StatusIcons[vtkSlicerLiverResectionsLogic::LastStatus];
  QPushButton* ShowStatusButtons[vtkSlicerLiverResectionsLogic::LastStatus];
  // QTimer FilterParameterChangedTimer;

  // bool JumpToSelectedSegmentEnabled;
};

//-----------------------------------------------------------------------------
qSlicerLiverResectionsTableViewPrivate::qSlicerLiverResectionsTableViewPrivate(qSlicerLiverResectionsTableView& object)
  : q_ptr(&object)
  // , ResectionNode(nullptr)
  // , AdvancedSegmentVisibility(false)
  // , IsUpdatingWidgetFromMRML(false)
  // , IsFilterBarVisible(false)
  // , Model(nullptr)
  // , SortFilterModel(nullptr)
  // , JumpToSelectedSegmentEnabled(false)
{
  for (int status = 0; status < vtkSlicerLiverResectionsLogic::LastStatus; ++status)
    {
    this->ShowStatusButtons[status] = nullptr;
    }
}

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsTableViewPrivate::init()
{
  Q_Q(qSlicerLiverResectionsTableView);

  this->setupUi(q);

  this->Model = new qSlicerLiverResectionsModel(this->ResectionsTable);
  this->ResectionsTable->setModel(this->Model);

  this->ResectionsTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
  this->ResectionsTable->horizontalHeader()->setSectionResizeMode(this->Model->nameColumn(), QHeaderView::Stretch);
  this->ResectionsTable->horizontalHeader()->setStretchLastSection(false);
  this->ResectionsTable->verticalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);

  // Select rows
  this->ResectionsTable->setSelectionBehavior(QAbstractItemView::SelectRows);

  // Unset read-only by default (edit triggers are double click and edit key press)
  //q->setReadOnly(false);
}

//-----------------------------------------------------------------------------
qSlicerLiverResectionsTableView::qSlicerLiverResectionsTableView(QWidget* _parent)
  : qMRMLWidget(_parent)
  , d_ptr(new qSlicerLiverResectionsTableViewPrivate(*this))
{
  Q_D(qSlicerLiverResectionsTableView);
  d->init();
}

//---------------------------------------------------------------------------
qSlicerLiverResectionsTableView::~qSlicerLiverResectionsTableView() = default;

//---------------------------------------------------------------------------
void qSlicerLiverResectionsTableView::setMRMLScene(vtkMRMLScene* newScene)
{
  Q_D(qSlicerLiverResectionsTableView);

  Superclass::setMRMLScene(newScene);

  if (d->Model)
    {
      d->Model->setMRMLScene(newScene);
    }
}
//------------------------------------------------------------------------------
bool qSlicerLiverResectionsTableView::eventFilter(QObject* target, QEvent* event)
{
  return false;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsTableView::contextMenuEvent(QContextMenuEvent* event)
{
}
