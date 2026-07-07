/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2022-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

// Qt includes
#include <QApplication>
#include <QDebug>
#include <QTimer>
#include <vtkSlicerApplicationLogic.h>

// Slicer includes
#include "qSlicerLiverMarkupsModule.h"
#include <qSlicerApplication.h>
#include <qSlicerModuleFactoryManager.h>
#include <qSlicerModuleManager.h>
#include <qSlicerApplicationHelper.h>

// Module includes
#include <vtkSlicerLiverMarkupsLogic.h>
#include <vtkMRMLMarkupsDistanceContourNode.h>
#include <vtkMRMLMarkupsSlicingContourNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLMarkupsNode.h>

class markupsModuleTest : public qSlicerLiverMarkupsModule
{
public:
  qSlicerApplication* app = nullptr;
  markupsModuleTest(int argc, char* argv[])
    : app(new qSlicerApplication(argc, argv))
  {
  }

  void setup() { qSlicerLiverMarkupsModule::setup(); }

  void loadModules()
  {
    // copied from generated qSlicerLiverMarkupsModuleGenericTest
    if (!dependencies().isEmpty())
    {
      qSlicerModuleFactoryManager* moduleFactoryManager = app->moduleManager()->factoryManager();
      qSlicerApplicationHelper::setupModuleFactoryManager(moduleFactoryManager);
      moduleFactoryManager->setExplicitModules(dependencies());

      moduleFactoryManager->registerModules();
      qDebug() << "Number of registered modules:" << moduleFactoryManager->registeredModuleNames().count();

      moduleFactoryManager->instantiateModules();
      qDebug() << "Number of instantiated modules:" << moduleFactoryManager->instantiatedModuleNames().count();

      // Load all available modules
      foreach (const QString& name, moduleFactoryManager->instantiatedModuleNames())
      {
        Q_ASSERT(!name.isNull());
        moduleFactoryManager->loadModule(name);
      }
    }
  }

  int checkMarkupNodes()
  {
    vtkSlicerApplicationLogic* appLogic = app->applicationLogic();
    vtkSlicerMarkupsLogic* markupsLogic = vtkSlicerMarkupsLogic::SafeDownCast(appLogic->GetModuleLogic("Markups"));
    if (!markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsSlicingContourNode"))
    {
      qCritical() << Q_FUNC_INFO << "vtkMRMLMarkupsSlicingContourNode isn't registered";
      return 1;
    }
    if (!markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsDistanceContourNode"))
    {
      qCritical() << Q_FUNC_INFO << "vtkMRMLMarkupsDistanceContourNode isn't registered";
      return 1;
    }
    // The v1 markups Bezier surface is fully retired (ADR-0014
    // §"Dissolution"; ADR-0032 §"Consequences" — v1 render + node + the
    // legacy `.lrp.fcsv` migration are gone).  The sole Bezier render is
    // the v2 LayerDM path (ADR-0013 §5; ADR-0031).  Pin the retirement:
    // the v1 markups Bezier type must NOT be a registered markups type.
    if (markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsBezierSurfaceNode"))
    {
      qCritical() << Q_FUNC_INFO << "vtkMRMLMarkupsBezierSurfaceNode is still registered (v1 retired)";
      return 1;
    }
    return 0;
  }

  int checkDisplayNodes()
  {
    // The v1 markups Bezier surface + its display node are retired
    // (ADR-0014 §"Dissolution"; ADR-0032 §"Consequences").  Only the
    // surviving contour markups are exercised here.
    auto distanceContourNode = vtkSmartPointer<vtkMRMLMarkupsDistanceContourNode>::New();
    auto slicingContourNode = vtkSmartPointer<vtkMRMLMarkupsSlicingContourNode>::New();

    int retval = 0;
    retval = retval || checkDisplayNode(distanceContourNode, "vtkMRMLMarkupsDistanceContourDisplayNode");
    retval = retval || checkDisplayNode(slicingContourNode, "vtkMRMLMarkupsSlicingContourDisplayNode");
    return retval;
  }

  int checkDisplayNode(vtkMRMLMarkupsNode* markupsNode, const char* displayClassName)
  {
    markupsNode->SetScene(app->mrmlScene());
    markupsNode->CreateDefaultDisplayNodes();
    if (!app->mrmlScene()->GetFirstNodeByClass(displayClassName))
    {
      qCritical() << Q_FUNC_INFO << displayClassName << " isn't added";
      return 1;
    }
    return 0;
  }
};

//-----------------------------------------------------------------------------
int qSlicerLiverMarkupsModuleTest(int argc, char* argv[])
{
  markupsModuleTest markupsModule(argc, argv);

  if (!markupsModule.isHidden())
  {
    return 1;
  }

  vtkSmartPointer<vtkMRMLScene> scene = markupsModule.app->mrmlScene();
  vtkSlicerApplicationLogic* appLogic = markupsModule.app->applicationLogic();

  markupsModule.loadModules();

  qDebug() << "initialize qSlicerLiverMarkupsModule";
  //    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
  // Set path just to avoid a runtime warning at module initialization
  markupsModule.setPath(markupsModule.app->slicerHome() + '/' + markupsModule.app->slicerSharePath() + "/qt-loadable-modules/LiverMarkups");
  markupsModule.initialize(appLogic);
  //    TESTING_OUTPUT_ASSERT_WARNINGS_END(); // warning due to using 0 as application logic

  vtkSlicerLiverMarkupsLogic* logic = vtkSlicerLiverMarkupsLogic::SafeDownCast(markupsModule.logic());
  if (!logic)
  {
    qCritical() << "No logic";
    return 1;
  }

  qDebug() << "setMRMLScene start";
  markupsModule.setMRMLScene(scene.GetPointer());

  qDebug() << "Check Markup Nodes";
  int retval = markupsModule.checkMarkupNodes();
  qDebug() << "Check Markup Display Nodes";
  retval = retval || markupsModule.checkDisplayNodes();

  delete markupsModule.app;
  return retval;
}
