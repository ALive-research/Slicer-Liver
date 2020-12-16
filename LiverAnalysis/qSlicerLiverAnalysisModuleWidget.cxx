/*==============================================================================

  Program: 3D Slicer

  Portions (c) Copyright Brigham and Women's Hospital (BWH) All Rights Reserved.

  See COPYRIGHT.txt
  or http://www.slicer.org/copyright/copyright.txt for details.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

==============================================================================*/

// Qt includes
#include <QDebug>

// Slicer includes
#include "qSlicerLiverAnalysisModuleWidget.h"
#include "ui_qSlicerLiverAnalysisModuleWidget.h"

//-----------------------------------------------------------------------------
/// \ingroup Slicer_QtModules_ExtensionTemplate
class qSlicerLiverAnalysisModuleWidgetPrivate: public Ui_qSlicerLiverAnalysisModuleWidget
{
public:
  qSlicerLiverAnalysisModuleWidgetPrivate();
};

//-----------------------------------------------------------------------------
// qSlicerLiverAnalysisModuleWidgetPrivate methods

//-----------------------------------------------------------------------------
qSlicerLiverAnalysisModuleWidgetPrivate::qSlicerLiverAnalysisModuleWidgetPrivate()
{
}

//-----------------------------------------------------------------------------
// qSlicerLiverAnalysisModuleWidget methods

//-----------------------------------------------------------------------------
qSlicerLiverAnalysisModuleWidget::qSlicerLiverAnalysisModuleWidget(QWidget* _parent)
  : Superclass( _parent )
  , d_ptr( new qSlicerLiverAnalysisModuleWidgetPrivate )
{
}

//-----------------------------------------------------------------------------
qSlicerLiverAnalysisModuleWidget::~qSlicerLiverAnalysisModuleWidget()
{
}

//-----------------------------------------------------------------------------
void qSlicerLiverAnalysisModuleWidget::setup()
{
  Q_D(qSlicerLiverAnalysisModuleWidget);
  d->setupUi(this);
  this->Superclass::setup();
}
