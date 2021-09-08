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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

  ==============================================================================*/
#ifndef qSlicerLiverResectionsModel_h_
#define qSlicerLiverResectionsModel_h_

// CTK includes
#include <ctkVTKObject.h>

// Qt includes
#include <QStandardItemModel>

// Segments includes
#include "qSlicerLiverResectionsModuleWidgetsExport.h"

//------------------------------------------------------------------------------
class qSlicerLiverResectionsModelPrivate;

//------------------------------------------------------------------------------
class Q_SLICER_MODULE_LIVERRESECTIONS_WIDGETS_EXPORT qSlicerLiverResectionsModel
  : public QStandardItemModel
{
  Q_OBJECT;
  QVTK_OBJECT;

  Q_PROPERTY(int nameColumn READ nameColumn WRITE setNameColumn);
  Q_PROPERTY(int visibilityColumn READ visibilityColumn WRITE setVisibilityColumn);
  Q_PROPERTY(int statusColumn READ statusColumn WRITE setStatusColumn);

 public:
  typedef QStandardItemModel Superclass;
  qSlicerLiverResectionsModel(QObject *parent=nullptr);
  ~qSlicerLiverResectionsModel() override;

  int nameColumn() const;
  void setNameColumn(int column);
  int visibilityColumn() const;
  void setVisibilityColumn(int column);
  int resectionMarginColumn() const;
  void setResectionMarginColumn(int column);
  int statusColumn() const;
  void setStatusColumn(int column);

  /// Returns the resection node id from a given index
  QString resectionNodeIDFromIndex(const QModelIndex &index) const;
  /// Returns the resection node id from a given item
  QString resectionNodeIDFromItem(QStandardItem const* item) const;
  /// Returns the index from a given node id (and column)
  QModelIndex indexFromResectionNodeID(const QString &resectionNodeID, int column=0) const;
  /// Returns the item for a givens egment id (and column)
  QStandardItem* itemFromresectionNodeID(const QString &resectionNodeID, int column=0)  const;

  /// Returns all the QModelIndex (all columns) for a given segment ID
  QModelIndexList indexes(const QString &resectionNodeID) const;

signals:
  /// Emitted when a property is about to be changed.
  /// It can be used to capture the current state of the resection, before it is modified.
  void resectionAboutToBeModified(const QString &resectionNodeID);

  /// Signal requesting selecting items in the table
  void requestSelectItems(QList<vtkIdType> &itemIDs);

protected slots:
  /// Invoked when an item in the model is changed
  virtual void onItemChanged(QStandardItem *item);

protected:
 qSlicerLiverResectionsModel(qSlicerLiverResectionsModelPrivate *impl,
                              QObject *parent=nullptr);

  /// Update QStandardItem associated using resectionNodeID and column
  void updateItemFromResection(QStandardItem &item,
                                 const QString &resectionNodeID,
                                 int column) const;

  void updateResectionNodeFromItemData(const QString &segmentID, const QStandardItem* item);


  /// Update QstandardItem data associated using resectionNodeID and column.
  void updateItemDataFromResectionNode(QStandardItem &item,
                                       const QString &resectionNodeID,
                                       int column) const;
  /// Update MRML node using the associated QstandardItem
  void updateResectionNodeFromItem(const QString &resectionNodeID,
                                   const QStandardItem *item);

  /// Update all the QStandardItem associated to a column
  void updateItemsFromColumnIndex(const int column);

  /// Update all of the QStandardItem associated with a resection node
  void updateItemsFromResectionNode(const QString &resectionNodeID);

  void updateColumnCount();

  int maxColumnId() const;

  /// Invoked when the segmentation node is modified with one of these events:
  /// vtkSegmentation::SegmentAdded,
  /// vtkSegmentation::SegmentRemoved,
  /// vtkSegmentation::SegmentModified,
  /// vtkSegmentation::SegmentsOrderModified
  static void onEvent(vtkObject* caller, unsigned long event, void* clientData, void* callData);

  void onResectionNodeAdded(const QString &resectionNodeID);
  void onResectionNodeRemoved(const QString &resectionNodeID);
  void onResectionNodeModified(const QString &resectionNodeID);

protected:
  QScopedPointer<qSlicerLiverResectionsModelPrivate> d_ptr;

private:
  Q_DECLARE_PRIVATE(qSlicerLiverResectionsModel);
  Q_DISABLE_COPY(qSlicerLiverResectionsModel);
};

#endif // qSlicerLiverResectionsModel_h_
