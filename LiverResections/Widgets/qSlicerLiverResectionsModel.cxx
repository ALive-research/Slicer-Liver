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

#include "qSlicerLiverResectionsModel.h"
#include "qSlicerLiverResectionsModel_p.h"

// MRML includes
#include <vtkMRMLLiverResectionNode.h>
#include <vtkMRMLScene.h>

//Qt includes
#include <QStringList>
#include <QIcon>
#include <QDebug>

//------------------------------------------------------------------------------
qSlicerLiverResectionsModelPrivate::qSlicerLiverResectionsModelPrivate(qSlicerLiverResectionsModel &object)
  : q_ptr(&object),
    UpdatingItemFromResectionNode(false),
    NameColumn(-1),
    VisibilityColumn(-1),
    ResectionMarginColumn(-1),
    StatusColumn(-1),
    MRMLScene(nullptr)

{
  this->Callback = vtkSmartPointer<vtkCallbackCommand>::New();

  this->HiddenIcon = QIcon(":Icons/VisibleOff.png");
  this->VisibleIcon = QIcon(":Icons/VisibleOn.png");

  this->InitializationIcon = QIcon(":Icons/NotStarted.png");
  this->DeformationIcon = QIcon(":Icons/InProgress.png");
  this->CompletedIcon = QIcon(":Icons/Completed.png");

  qRegisterMetaType<QStandardItem*>("QStandardItem*");
}


//------------------------------------------------------------------------------
qSlicerLiverResectionsModelPrivate::~qSlicerLiverResectionsModelPrivate()
{

}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModelPrivate::init()
{
  Q_Q(qSlicerLiverResectionsModel);

  this->Callback->SetClientData(q);
  this->Callback->SetCallback(qSlicerLiverResectionsModel::onEvent);

  QObject::connect(q, SIGNAL(itemChanged(QStandardItem*)), q, SLOT(onItemChanged(QStandardItem*)));

  q->setVisibilityColumn(0);
  q->setNameColumn(1);
  q->setResectionMarginColumn(2);
  q->setStatusColumn(3);

  QStringList columnLabels;
  for (int i=0; i<q->columnCount(); ++i)
    {
      if (i == q->visibilityColumn())
        {
          columnLabels << "Visibility";
        }
      else if (i == q->nameColumn())
        {
          columnLabels << "Name";
        }
      else if (i == q->resectionMarginColumn())
        {
          columnLabels << "Resection Margin";
        }
      else if (i == q->statusColumn())
        {
          columnLabels << "Status";
        }
    }

  q->setHorizontalHeaderLabels(columnLabels);

  // q->horizontalHeaderItem(q->nameColumn())->setToolTip(qSlicerLiverResectionsModel::tr("Resection Name"));
  // q->horizontalHeaderItem(q->visibilityColumn())->setToolTip(qSlicerLiverResectionsModel::tr("Resection Visibility"));
  // q->horizontalHeaderItem(q->resectionMarginColumn())->setToolTip(qSlicerLiverResectionsModel::tr("Resection Margin"));
  // q->horizontalHeaderItem(q->statusColumn())->setToolTip(qSlicerLiverResectionsModel::tr("Resection Status"));

  //q->horizontalHeaderItem(q->visibilityColumn())->setIcon(QIcon(":/Icons/Small/SlicerVisibleInvisible.png"));

}

//------------------------------------------------------------------------------
// qSlicerLiverResectionsModel
//------------------------------------------------------------------------------
qSlicerLiverResectionsModel::qSlicerLiverResectionsModel(QObject *_parent)
  :QStandardItemModel(_parent)
  , d_ptr(new qSlicerLiverResectionsModelPrivate(*this))
{
  Q_D(qSlicerLiverResectionsModel);
  d->init();
}

//------------------------------------------------------------------------------
qSlicerLiverResectionsModel::qSlicerLiverResectionsModel(qSlicerLiverResectionsModelPrivate* pimpl, QObject* parent)
  : QStandardItemModel(parent)
  , d_ptr(pimpl)
{
  Q_D(qSlicerLiverResectionsModel);
  d->init();
}

//------------------------------------------------------------------------------
qSlicerLiverResectionsModel::~qSlicerLiverResectionsModel() = default;

//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModel::setMRMLScene(vtkMRMLScene *scene)
{
  Q_D(qSlicerLiverResectionsModel);

  if(d->MRMLScene == scene)
    {
      return;
    }
  d->MRMLScene = scene;

  if(!d->MRMLScene)
    {
      return;
    }

  d->MRMLScene->AddObserver(vtkMRMLScene::NodeAddedEvent, d->Callback, 10);
  d->MRMLScene->AddObserver(vtkMRMLScene::NodeRemovedEvent, d->Callback, 10);
}


//-----------------------------------------------------------------------------
void qSlicerLiverResectionsModel::onEvent(vtkObject* caller,
                                          unsigned long event,
                                          void* clientData,
                                          void* callData )
{
  // Verify it is a correct call
  vtkMRMLScene *mrmlScene = reinterpret_cast<vtkMRMLScene*>(caller);
  qSlicerLiverResectionsModel *model = reinterpret_cast<qSlicerLiverResectionsModel*>(clientData);

  if (!model || !mrmlScene)
    {
     qCritical() << Q_FUNC_INFO << ": Invalid event parameters.";
     return;
    }

  // Check associated data (node ID)
  vtkMRMLNode *node= nullptr;
  if (callData && (event == vtkMRMLScene::NodeAddedEvent
                   || event == vtkMRMLScene::NodeRemovedEvent))
    {
      node = reinterpret_cast<vtkMRMLLiverResectionNode*>(callData);
    }

  vtkMRMLLiverResectionNode *resectionNode =
    vtkMRMLLiverResectionNode::SafeDownCast(node);

  // Test it referes to a vtkMRMLLiverResectionNode
  if (!resectionNode)
    {
      return;
    }

  // Take action on the events
  switch(event)
    {
      case vtkMRMLScene::NodeAddedEvent:
        model->onResectionNodeAdded(resectionNode);
        break;
      case vtkMRMLScene::NodeRemovedEvent:
        model->onResectionNodeRemoved(resectionNode);
        break;
    }
}
//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::onItemChanged(QStandardItem* item)
{
  Q_D(qSlicerLiverResectionsModel);
  this->updateResectionNodeFromItem(this->resectionNodeIDFromItem(item), item);
}

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModel::nameColumn() const
{
  Q_D(const qSlicerLiverResectionsModel);
  return d->NameColumn;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::setNameColumn(int column)
{
  Q_D(qSlicerLiverResectionsModel);
  d->NameColumn = column;
  this->updateColumnCount();
}

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModel::visibilityColumn() const
{
  Q_D(const qSlicerLiverResectionsModel);
  return d->VisibilityColumn;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::setVisibilityColumn(int column)
{
  Q_D(qSlicerLiverResectionsModel);
  d->VisibilityColumn = column;
  this->updateColumnCount();
}

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModel::resectionMarginColumn() const
{
  Q_D(const qSlicerLiverResectionsModel);
  return d->ResectionMarginColumn;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::setResectionMarginColumn(int column)
{
  Q_D(qSlicerLiverResectionsModel);
  d->ResectionMarginColumn = column;
  this->updateColumnCount();
}

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModel::statusColumn() const
{
  Q_D(const qSlicerLiverResectionsModel);
  return d->StatusColumn;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::setStatusColumn(int column)
{
  Q_D(qSlicerLiverResectionsModel);
  d->StatusColumn = column;
  this->updateColumnCount();
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::updateColumnCount()
{
  Q_D(const qSlicerLiverResectionsModel);

  int max = this->maxColumnId();
  int oldColumnCount = this->columnCount();
  this->setColumnCount(max + 1);
  // if (oldColumnCount == 0)
  //   {
  //   this->rebuildFromSegments();
  //   }
  // else
  //   {
  //   // Update all items
  //   if (!d->SegmentationNode)
  //     {
  //     return;
  //     }
  //   std::vector<std::string> resectionNodeIDs;
  //   d->SegmentationNode->GetSegmentation()->GetSegmentIDs(resectionNodeIDs);
  //   for (std::vector<std::string>::iterator itemIt= resectionNodeIDs.begin(); itemIt!= resectionNodeIDs.end(); ++itemIt)
  //     {
  //     this->updateItemsFromSegmentID(itemIt->c_str());
  //     }
  //   }
}

//------------------------------------------------------------------------------
int qSlicerLiverResectionsModel::maxColumnId()const
{
  Q_D(const qSlicerLiverResectionsModel);
  int maxId = -1;
  maxId = qMax(maxId, d->NameColumn);
  maxId = qMax(maxId, d->VisibilityColumn);
  maxId = qMax(maxId, d->ResectionMarginColumn);
  maxId = qMax(maxId, d->StatusColumn);
  return maxId;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::updateResectionNodeFromItem(const QString &resectionNodeID, const QStandardItem* item)
{
  Q_D(qSlicerLiverResectionsModel);
  //MRMLNodeModify segmentationNodeModify(d->SegmentationNode);//TODO: Add feature to item if there are performance issues
  // Calling StartModfiy/EndModify will cause the calldata to be erased, causing the whole table to be updated
  this->updateResectionNodeFromItemData(resectionNodeID, item);
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::updateResectionNodeFromItemData(const QString &resectionNodeID, const QStandardItem* item)
{
  // Q_D(qSlicerLiverResectionsModel);
  // if (!d->SegmentationNode)
  //   {
  //   qCritical() << Q_FUNC_INFO << ": Invalid segmentation node";
  //   return;
  //   }

  // if (!item)
  //   {
  //   qCritical() << Q_FUNC_INFO << ": Invalid item";
  //   return;
  //   }

  // // Name column
  // if (item->column() == this->nameColumn())
  //   {
  //   vtkSegment* segment = d->SegmentationNode->GetSegmentation()->GetSegment(resectionNodeID.toStdString());
  //   if (!segment)
  //     {
  //     qCritical() << Q_FUNC_INFO << ": Segment with ID '" << resectionNodeID << "' not found in segmentation node " << d->SegmentationNode->GetName();
  //     return;
  //     }
  //   std::string name = item->text().toStdString();
  //   emit segmentAboutToBeModified(resectionNodeID);
  //   segment->SetName(name.c_str());
  //   if (!d->UpdatingItemFromSegment)
  //     {
  //     segment->SetNameAutoGenerated(false);
  //     }
  //   }
  // else if (item->column() == this->statusColumn())
  //   {
  //   vtkSegment* segment = d->SegmentationNode->GetSegmentation()->GetSegment(resectionNodeID.toStdString());
  //   if (!segment)
  //     {
  //     qCritical() << Q_FUNC_INFO << ": Segment with ID '" << resectionNodeID << "' not found in segmentation node " << d->SegmentationNode->GetName();
  //     return;
  //     }
  //   int status = item->data(StatusRole).toInt();
  //   vtkSlicerSegmentationsModuleLogic::SetSegmentStatus(segment, status);
  //   }
  // else
  //   {
  //   // For all other columns we need the display node
  //   vtkMRMLSegmentationDisplayNode* displayNode = vtkMRMLSegmentationDisplayNode::SafeDownCast(
  //     d->SegmentationNode->GetDisplayNode());
  //   if (!displayNode)
  //     {
  //     qCritical() << Q_FUNC_INFO << ": No display node for segmentation!";
  //     return;
  //     }
  //   // Get display properties
  //   bool displayPropertyChanged = false;
  //   vtkMRMLSegmentationDisplayNode::SegmentDisplayProperties properties;
  //   displayNode->GetSegmentDisplayProperties(resectionNodeID.toStdString(), properties);

  //   // Visibility column
  //   if (item->column() == this->visibilityColumn() && !item->data(VisibilityRole).isNull())
  //     {
  //     vtkMRMLSegmentationDisplayNode* displayNode = vtkMRMLSegmentationDisplayNode::SafeDownCast(d->SegmentationNode->GetDisplayNode());
  //     bool visible = item->data(VisibilityRole).toBool();
  //     displayNode->SetSegmentVisibility(resectionNodeID.toStdString(), visible);
  //     }
  //   // Color column
  //   else if (item->column() == this->colorColumn())
  //     {
  //     vtkSegment* segment = d->SegmentationNode->GetSegmentation()->GetSegment(resectionNodeID.toStdString());
  //     if (!segment)
  //       {
  //       qCritical() << Q_FUNC_INFO << ": Segment with ID '" << resectionNodeID << "' not found in segmentation node " << d->SegmentationNode->GetName();
  //       return;
  //       }

  //     // Set terminology information to segment as tag
  //     QString terminologyString = item->data(qSlicerTerminologyItemDelegate::TerminologyRole).toString();
  //     segment->SetTag(vtkSegment::GetTerminologyEntryTagName(), terminologyString.toUtf8().constData());

  //     // Set color to segment if it changed
  //     QColor color = item->data(Qt::DecorationRole).value<QColor>();
  //     double* oldColorArray = segment->GetColor();
  //     QColor oldColor = QColor::fromRgbF(oldColorArray[0], oldColorArray[1], oldColorArray[2]);
  //     if (oldColor != color)
  //       {
  //       segment->SetColor(color.redF(), color.greenF(), color.blueF());
  //       }
  //     // Set color auto-generated flag
  //     segment->SetColorAutoGenerated(
  //       item->data(qSlicerTerminologyItemDelegate::ColorAutoGeneratedRole).toBool());

  //     // Set name if it changed
  //     QString nameFromColorItem = item->data(qSlicerTerminologyItemDelegate::NameRole).toString();
  //     if (nameFromColorItem.compare(segment->GetName()))
  //       {
  //       emit segmentAboutToBeModified(resectionNodeID);
  //       segment->SetName(nameFromColorItem.toUtf8().constData());
  //       }
  //     // Set name auto-generated flag
  //     segment->SetNameAutoGenerated(
  //       item->data(qSlicerTerminologyItemDelegate::NameAutoGeneratedRole).toBool());

  //     // Update tooltip
  //     item->setToolTip(qSlicerLiverResectionsTableView::terminologyTooltipForSegment(segment));
  //     }
  //   // Opacity changed
  //   else if (item->column() == this->opacityColumn())
  //     {
  //     QString opacity = item->data(Qt::EditRole).toString();
  //     QString currentOpacity = QString::number(properties.Opacity3D, 'f', 2);
  //     if (opacity != currentOpacity)
  //       {
  //       // Set to all kinds of opacities as they are combined on the UI
  //       properties.Opacity3D = opacity.toDouble();
  //       displayPropertyChanged = true;
  //       }
  //     }
  //   // Set changed properties to segmentation display node if a value has actually changed
  //   if (displayPropertyChanged)
  //     {
  //     displayNode->SetSegmentDisplayProperties(resectionNodeID.toStdString(), properties);
  //     }
  //   }
}

//------------------------------------------------------------------------------
QString qSlicerLiverResectionsModel::resectionNodeIDFromItem(QStandardItem const* item)const
{
  // Q_D(const qSlicerLiverResectionsModel);
  // if (!d->ResectionNode || !item)
  //   {
  //   return "";
  //   }
  // QVariant ResectionNodeID = item->data(qSlicerResectionsModel::ResectionNodeIDRole);
  // if (!ResectionNodeID.isValid())
  //   {
  //   return "";
  //   }
  // return item->data(qMRMLResectionNodesModel::ResectionNodeIDRole).toString();
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::onResectionNodeAdded(vtkMRMLLiverResectionNode* node)
{

  // Check if it is a valid node
  if (!node)
    {
      qCritical() << Q_FUNC_INFO << ": Invalid resection node";
      return;
    }

  if (!node->GetSegmentationNode())
    {
      return;
    }

  QList<QStandardItem*> items;

  // Update each of the columns for the item
  for (int col=0; col < this->columnCount(); ++col)
    {
      QStandardItem* newItem = new QStandardItem();
      this->updateItemFromResectionNode(newItem, node, col);
      items.append(newItem);
    }

  this->appendRow(items);

}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::onResectionNodeRemoved(vtkMRMLLiverResectionNode* node)
{
  if (node)
    std::cout << "Resection Removed" << std::endl;
}

//------------------------------------------------------------------------------
void qSlicerLiverResectionsModel::updateItemFromResectionNode(QStandardItem *item,
                                                              vtkMRMLLiverResectionNode *resectionNode,
                                                              int column)
{
  Q_D(qSlicerLiverResectionsModel);

  if (!resectionNode)
    {
      qCritical() << Q_FUNC_INFO << ": Invalid resection node";
      return;
    }

  if (column == this->visibilityColumn())
    {
      std::cout << "Test" << std::endl;
      item->setText("test");
    }

}
