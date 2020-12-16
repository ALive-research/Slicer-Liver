/*==============================================================================

  Program: 3D Slicer

  Copyright (c) Kitware Inc.

  See COPYRIGHT.txt
  or http://www.slicer.org/copyright/copyright.txt for details.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
  and was partially funded by NIH grant 3P41RR013218-12S1

==============================================================================*/

// FooBar Widgets includes
#include "qSlicerLiverAnalysisFooBarWidget.h"
#include "ui_qSlicerLiverAnalysisFooBarWidget.h"

//-----------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_LiverAnalysis
class qSlicerLiverAnalysisFooBarWidgetPrivate
  : public Ui_qSlicerLiverAnalysisFooBarWidget
{
  Q_DECLARE_PUBLIC(qSlicerLiverAnalysisFooBarWidget);
protected:
  qSlicerLiverAnalysisFooBarWidget* const q_ptr;

public:
  qSlicerLiverAnalysisFooBarWidgetPrivate(
    qSlicerLiverAnalysisFooBarWidget& object);
  virtual void setupUi(qSlicerLiverAnalysisFooBarWidget*);
};

// --------------------------------------------------------------------------
qSlicerLiverAnalysisFooBarWidgetPrivate
::qSlicerLiverAnalysisFooBarWidgetPrivate(
  qSlicerLiverAnalysisFooBarWidget& object)
  : q_ptr(&object)
{
}

// --------------------------------------------------------------------------
void qSlicerLiverAnalysisFooBarWidgetPrivate
::setupUi(qSlicerLiverAnalysisFooBarWidget* widget)
{
  this->Ui_qSlicerLiverAnalysisFooBarWidget::setupUi(widget);
}

//-----------------------------------------------------------------------------
// qSlicerLiverAnalysisFooBarWidget methods

//-----------------------------------------------------------------------------
qSlicerLiverAnalysisFooBarWidget
::qSlicerLiverAnalysisFooBarWidget(QWidget* parentWidget)
  : Superclass( parentWidget )
  , d_ptr( new qSlicerLiverAnalysisFooBarWidgetPrivate(*this) )
{
  Q_D(qSlicerLiverAnalysisFooBarWidget);
  d->setupUi(this);
}

//-----------------------------------------------------------------------------
qSlicerLiverAnalysisFooBarWidget
::~qSlicerLiverAnalysisFooBarWidget()
{
}
