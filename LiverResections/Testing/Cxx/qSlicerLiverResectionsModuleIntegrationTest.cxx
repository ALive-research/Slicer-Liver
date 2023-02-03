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

//Module includes
#include <qSlicerLiverResectionsModule.h>
#include <vtkMRMLLiverResectionNode.h>
#include "qSlicerLiverResectionsReader.h"
#include <vtkSlicerLiverResectionsLogic.h>
#include <vtkSlicerMarkupsLogic.h>
//#include <qSlicerLiverMarkupsModule.h>//Cannot find this include

#include <vtkMRMLMarkupsSlicingContourNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLMarkupsNode.h>
#include <vtkSlicerSlicingContourWidget.h>

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
}

class liverResectionsModuleIntegrationTest: public qSlicerLiverResectionsModule
{
public:
    qSlicerApplication* app = nullptr;
    liverResectionsModuleIntegrationTest(int argc, char * argv[]) :
        app(new qSlicerApplication(argc, argv))
    {}

    void startApp()
    {
        //Using code example from qSlicerModelsModuleWidgetTest1

        qMRMLWidget::preInitializeApplication();
        qMRMLWidget::postInitializeApplication();
    }
    int runApp(int argc, char * argv[])
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
          qSlicerModuleFactoryManager * moduleFactoryManager = app->moduleManager()->factoryManager();
          qSlicerApplicationHelper::setupModuleFactoryManager(moduleFactoryManager);
          moduleFactoryManager->setExplicitModules(dependencies());

          moduleFactoryManager->registerModules();
          qDebug() << "Number of registered modules:"
                   << moduleFactoryManager->registeredModuleNames().count();

          moduleFactoryManager->instantiateModules();
          qDebug() << "Number of instantiated modules:"
                   << moduleFactoryManager->instantiatedModuleNames().count();

          // Load all available modules
          foreach(const QString& name, moduleFactoryManager->instantiatedModuleNames())
            {
            Q_ASSERT(!name.isNull());
            moduleFactoryManager->loadModule(name);
            }
          }
    }
};

//-----------------------------------------------------------------------------
int qSlicerLiverResectionsModuleIntegrationTest(int argc, char * argv[] )
{

    liverResectionsModuleIntegrationTest module(argc, argv);

    if(!module.isHidden())
        return 1;


//    module.startApp();
    Q_ASSERT(module.app);
    vtkSmartPointer<vtkMRMLScene> scene = module.app->mrmlScene();
    Q_ASSERT(scene);
    vtkSlicerApplicationLogic* appLogic = module.app->applicationLogic();
    Q_ASSERT(appLogic);
    // Set path just to avoid a runtime warning at module initialization
    module.setPath(module.app->slicerHome() + '/' + module.app->slicerSharePath() + "/qt-loadable-modules/LiverResections");

    module.loadModules(); // adding "Markups" to qSlicerLiverResectionsModule::dependencies() fixes the next line - Not sure why this is nee
    module.initialize(appLogic);
    module.setMRMLScene(scene);

    //Add and get nodes
    checkAddAndGetNode(scene, "vtkMRMLLiverResectionNode");
    checkAddAndGetNode(scene, "vtkMRMLLiverResectionCSVStorageNode");

    vtkMRMLLiverResectionNode* liverResectionNode = vtkMRMLLiverResectionNode::SafeDownCast(scene->GetFirstNodeByClass("vtkMRMLLiverResectionNode"));
    Q_ASSERT(liverResectionNode);

    vtkSlicerLiverResectionsLogic* liverResectionsLogic = vtkSlicerLiverResectionsLogic::SafeDownCast(module.logic());
    Q_ASSERT(liverResectionsLogic);


    // Register markups
    vtkSlicerMarkupsLogic* markupsLogic = vtkSlicerMarkupsLogic::SafeDownCast(appLogic->GetModuleLogic("Markups"));
    Q_ASSERT(markupsLogic);
    vtkNew<vtkMRMLMarkupsSlicingContourNode> slicingContourNode;
    Q_ASSERT(slicingContourNode);

    //All commented out code below is testing that don't yet work
    //***********************************************************

    //Don't work - Needs to be registered, and it seems like the LiverMarkups module isn't available from this module
//    vtkNew<vtkSlicerSlicingContourWidget> slicingContourWidget;
//    markupsLogic->RegisterMarkupsNode(slicingContourNode, slicingContourWidget);
    //Including qSlicerLiverMarkupsModule fails
//    qSlicerLiverMarkupsModule* markupsModule = new qSlicerLiverMarkupsModule();
//    markupsModule.initialize(appLogic);

    vtkNew<vtkMRMLModelNode> targetOrgan;
    vtkNew<vtkSphereSource> source;
    targetOrgan->SetPolyDataConnection(source->GetOutputPort());

    //Needs to register vtkMRMLMarkupsSlicingContourNode, vtkMRMLMarkupsBezierSurfceNode, vtkMRMLMarkupsBezierSurfaceNode before this line:
//    liverResectionNode->SetTargetOrganModelNode(targetOrgan);
//    liverResectionsLogic->AddResectionPlane(liverResectionNode);


    //Cannot get these back from qSlicerIOManager with public functions?
//    qSlicerLiverResectionsReader *markupsReader;
//    qSlicerLiverResectionsWriter *markupsWriter;

//    EXERCISE_ALL_BASIC_MRML_METHODS(slicingContourNode.GetPointer());


//    return module.runApp(argc, argv);//fails - just delete app instead
    delete module.app;

    return 0;
}
