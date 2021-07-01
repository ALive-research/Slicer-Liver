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

#include "qSlicerApplication.h"

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

  // qSlicerSegmentsModel* Model;
  // qSlicerSortFilterSegmentsProxyModel* SortFilterModel;

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

  QObject::connect(this->AddResectionSlicingContourPushButton, &QPushButton::clicked,
                   q, [q] {q->addResection(vtkSlicerLiverResectionsLogic::SlicingContour);});
  QObject::connect(this->AddResectionContourDistancePushButton, &QPushButton::clicked,
                   q, [q] {q->addResection(vtkSlicerLiverResectionsLogic::DistanceContour);});

  // this->Model = new qSlicerLiverResectionsModel(this->SegmentsTable);
  // this->SortFilterModel = new qMRMLSortFilterSegmentsProxyModel(this->SegmentsTable);
  // this->SortFilterModel->setSourceModel(this->Model);
  // this->SegmentsTable->setModel(this->SortFilterModel);

  // for (int status = 0; status < vtkSlicerSegmentationsModuleLogic::LastStatus; ++status)
  //   {
  //   switch (status)
  //     {
  //     case vtkSlicerSegmentationsModuleLogic::NotStarted:
  //       this->ShowStatusButtons[status] = this->ShowNotStartedButton;
  //       this->StatusIcons[status] = QIcon(":Icons/NotStarted.png");
  //       break;
  //     case vtkSlicerSegmentationsModuleLogic::InProgress:
  //       this->ShowStatusButtons[status] = this->ShowInProgressButton;
  //       this->StatusIcons[status] = QIcon(":Icons/InProgress.png");
  //       break;
  //     case vtkSlicerSegmentationsModuleLogic::Completed:
  //       this->ShowStatusButtons[status] = this->ShowCompletedButton;
  //       this->StatusIcons[status] = QIcon(":Icons/Completed.png");
  //       break;
  //     case vtkSlicerSegmentationsModuleLogic::Flagged:
  //       this->ShowStatusButtons[status] = this->ShowFlaggedButton;
  //       this->StatusIcons[status] = QIcon(":Icons/Flagged.png");
  //       break;
  //     default:
  //       this->ShowStatusButtons[status] = nullptr;
  //       this->StatusIcons[status] = QIcon();
  //     }
  //   if (this->ShowStatusButtons[status])
  //     {
  //     this->ShowStatusButtons[status]->setProperty(STATUS_PROPERTY, status);
  //     }
  //   }

  // // Hide filter bar to simplify default GUI. User can enable to handle many segments
  // q->setFilterBarVisible(false);

  // // Hide layer column
  // q->setLayerColumnVisible(false);

  // this->setMessage(QString());

  // this->SegmentsTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
  // this->SegmentsTable->horizontalHeader()->setSectionResizeMode(this->Model->nameColumn(), QHeaderView::Stretch);
  // this->SegmentsTable->horizontalHeader()->setStretchLastSection(false);
  // this->SegmentsTable->verticalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);

  // // Select rows
  // this->SegmentsTable->setSelectionBehavior(QAbstractItemView::SelectRows);

  // // Unset read-only by default (edit triggers are double click and edit key press)
  // q->setReadOnly(false);

  // // Setup filter parameter changed timer
  // this->FilterParameterChangedTimer.setInterval(500);
  // this->FilterParameterChangedTimer.setSingleShot(true);

  // // Make connections
  // QObject::connect(&this->FilterParameterChangedTimer, &QTimer::timeout, q, &qSlicerLiverResectionsTableView::updateMRMLFromFilterParameters);
  // QObject::connect(this->SegmentsTable->selectionModel(), &QItemSelectionModel::selectionChanged, q, &qSlicerLiverResectionsTableView::onSegmentSelectionChanged);
  // QObject::connect(this->Model, &qSlicerLiverResectionsModel::segmentAboutToBeModified, q, &qSlicerLiverResectionsTableView::segmentAboutToBeModified);
  // QObject::connect(this->SegmentsTable, &QTableView::clicked, q, &qSlicerLiverResectionsTableView::onSegmentsTableClicked);
  // QObject::connect(this->FilterLineEdit, &ctkSearchBox::textEdited, this->SortFilterModel, &qMRMLSortFilterSegmentsProxyModel::setTextFilter);
  // for (QPushButton* button : this->ShowStatusButtons)
  //   {
  //   if (!button)
  //     {
  //     continue;
  //     }
  //   QObject::connect(button, &QToolButton::clicked, q, &qSlicerLiverResectionsTableView::onShowStatusButtonClicked);
  //   }
  // QObject::connect(this->SortFilterModel, &qMRMLSortFilterSegmentsProxyModel::filterModified, q, &qSlicerLiverResectionsTableView::onSegmentsFilterModified);

  // // Set item delegate to handle color and opacity changes
  // this->SegmentsTable->setItemDelegateForColumn(this->Model->colorColumn(), new qSlicerTerminologyItemDelegate(this->SegmentsTable));
  // this->SegmentsTable->setItemDelegateForColumn(this->Model->opacityColumn(), new qMRMLItemDelegate(this->SegmentsTable));
  // this->SegmentsTable->installEventFilter(q);
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
  d->TumorComboBox->setMRMLScene(newScene);
}
//------------------------------------------------------------------------------
bool qSlicerLiverResectionsTableView::eventFilter(QObject* target, QEvent* event)
{
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsTableView::contextMenuEvent(QContextMenuEvent* event)
{

}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsTableView::addResection(vtkSlicerLiverResectionsLogic::InitializationType type)
{

 auto appLogic = qSlicerApplication::application()->applicationLogic();
 if (!appLogic)
   {
   qCritical() << Q_FUNC_INFO << " : invalid application logic.";
   return;
   }

 vtkSlicerLiverResectionsLogic* markupsLogic =
   vtkSlicerLiverResectionsLogic::SafeDownCast(appLogic->GetModuleLogic("LiverResections"));
 if (!markupsLogic)
   {
   qCritical() << Q_FUNC_INFO << " : invalid markups logic.";
   return;
   }
  markupsLogic->AddResection(type);
}
