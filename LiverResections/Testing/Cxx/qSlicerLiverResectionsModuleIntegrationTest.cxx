/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2023-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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
#include <qSlicerApplication.h>
#include <qSlicerModuleFactoryManager.h>
#include <qSlicerModuleManager.h>
#include <qSlicerApplicationHelper.h>

// Module includes
#include <qSlicerLiverResectionsModule.h>
#include <vtkMRMLResectionPlanNode.h>
#include "qSlicerLiverResectionsReader.h"
#include <vtkSlicerLiverResectionsLogic.h>
#include <vtkSlicerMarkupsLogic.h>
#include <qSlicerLiverMarkupsModule.h> //Needed to include qSlicerLiverMarkupsModule_INCLUDE_DIRS to find the files from the LiverMarkupsModule

#include <vtkMRMLBezierSurfaceNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLMarkupsNode.h>
#include <vtkSlicerSlicingContourWidget.h>
#include <vtkMRMLMarkupsSlicingContourNode.h>
#include <vtkMRMLMarkupsSlicingContourDisplayNode.h>

// VTK includes
#include "qMRMLWidget.h"
#include <vtkTestingOutputWindow.h>
#include <vtkSphereSource.h>

#include "vtkMRMLCoreTestingMacros.h"

namespace
{
void checkAddAndGetNode(vtkSmartPointer<vtkMRMLScene> scene, const char* ClassName)
{
  auto node = scene->GetFirstNodeByClass(ClassName);
  assert(node == nullptr);

  std::string newNodeName = ClassName;
  newNodeName.append("_Test");
  scene->AddNewNodeByClass(ClassName, newNodeName);
  node = scene->GetFirstNodeByClass(ClassName);
  assert(node != nullptr);

  auto node2 = scene->GetNodeByID(node->GetID());
  assert(node2 != nullptr);
  assert(node == node2);
}
} // namespace

class liverResectionsModuleIntegrationTest : public qSlicerLiverResectionsModule
{
public:
  qSlicerApplication* app = nullptr;
  liverResectionsModuleIntegrationTest(int argc, char* argv[])
    : app(new qSlicerApplication(argc, argv))
  {
  }

  void startApp()
  {
    // Using code example from qSlicerModelsModuleWidgetTest1

    qMRMLWidget::preInitializeApplication();
    qMRMLWidget::postInitializeApplication();
  }
  int runApp(int argc, char* argv[])
  {
    if (argc < 2 || QString(argv[1]) != "-I")
    {
      QTimer::singleShot(100, app, SLOT(quit()));
    }
    int retval = app->exec();
    delete app;
    return retval;
  }

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
};

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModuleIntegrationTest(int argc, char* argv[])
{

  liverResectionsModuleIntegrationTest module(argc, argv);

  if (!module.isHidden())
  {
    return 1;
  }

  //    module.startApp();
  Q_ASSERT(module.app);
  vtkSmartPointer<vtkMRMLScene> scene = module.app->mrmlScene();
  Q_ASSERT(scene);
  vtkSlicerApplicationLogic* appLogic = module.app->applicationLogic();
  Q_ASSERT(appLogic);
  // Set path just to avoid a runtime warning at module initialization
  module.setPath(module.app->slicerHome() + '/' + module.app->slicerSharePath() + "/qt-loadable-modules/LiverResections");

  module.loadModules(); // adding "Markups" to qSlicerLiverResectionsModule::dependencies() fixes the next line - Not sure why this is needed
  module.initialize(appLogic);
  module.setMRMLScene(scene);

  // Add and get nodes — the v2 resection-plan wrapper + its Bezier
  // carrier (ADR-0014 wrapper-vs-carrier split) are registered by the
  // module logic's RegisterNodes().
  checkAddAndGetNode(scene, "vtkMRMLResectionPlanNode");
  checkAddAndGetNode(scene, "vtkMRMLResectionPlanStorageNode");

  vtkMRMLResectionPlanNode* resectionPlanNode = vtkMRMLResectionPlanNode::SafeDownCast(scene->GetFirstNodeByClass("vtkMRMLResectionPlanNode"));
  Q_ASSERT(resectionPlanNode);

  vtkSlicerLiverResectionsLogic* liverResectionsLogic = vtkSlicerLiverResectionsLogic::SafeDownCast(module.logic());
  Q_ASSERT(liverResectionsLogic);

  // Register markups
  vtkSlicerMarkupsLogic* markupsLogic = vtkSlicerMarkupsLogic::SafeDownCast(appLogic->GetModuleLogic("Markups"));
  Q_ASSERT(markupsLogic);
  vtkNew<vtkMRMLMarkupsSlicingContourNode> slicingContourNode;
  Q_ASSERT(slicingContourNode);
  slicingContourNode->SetScene(scene);

  vtkNew<vtkSlicerSlicingContourWidget> slicingContourWidget;
  Q_ASSERT(slicingContourWidget);
  markupsLogic->RegisterMarkupsNode(slicingContourNode, slicingContourWidget);
  qSlicerLiverMarkupsModule* markupsModule = new qSlicerLiverMarkupsModule();
  Q_ASSERT(markupsModule);
  //    markupsModule->initialize(appLogic);
  delete markupsModule;

  scene->RegisterNodeClass(vtkSmartPointer<vtkMRMLMarkupsSlicingContourDisplayNode>::New());
  // The v1 markups Bezier surface + its display node are retired
  // (ADR-0014 §"Dissolution"; ADR-0032 §"Consequences"); the v2 carrier
  // is exercised below.

  // The v2 plan resolves its geometry through a typed node reference
  // to the Bezier carrier (ADR-0014); exercise that wiring.
  vtkMRMLBezierSurfaceNode* bezierCarrier = vtkMRMLBezierSurfaceNode::SafeDownCast(scene->AddNewNodeByClass("vtkMRMLBezierSurfaceNode"));
  Q_ASSERT(bezierCarrier);
  resectionPlanNode->SetAndObserveGeometryNode(bezierCarrier);
  Q_ASSERT(resectionPlanNode->GetGeometryNode() == bezierCarrier);

  // Cannot get these back from qSlicerIOManager with public functions?
  //    qSlicerLiverResectionsReader *markupsReader;
  //    qSlicerLiverResectionsWriter *markupsWriter;

  // Also test the MRML methods in the nodes
  EXERCISE_ALL_BASIC_MRML_METHODS(slicingContourNode.GetPointer());
  EXERCISE_ALL_BASIC_MRML_METHODS(resectionPlanNode);

  //    return module.runApp(argc, argv);//fails - just delete app instead
  delete module.app;

  return 0;
}
