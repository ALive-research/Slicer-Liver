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

//Module includes
#include <vtkSlicerLiverMarkupsLogic.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>
#include <vtkMRMLMarkupsDistanceContourNode.h>
#include <vtkMRMLMarkupsSlicingContourNode.h>

// MRML includes
#include <vtkMRMLScene.h>
#include <vtkMRMLMarkupsNode.h>

// VTK includes
#include "qMRMLWidget.h"
#include <vtkTestingOutputWindow.h>

class markupsModuleTest: public qSlicerLiverMarkupsModule
{
public:
    qSlicerApplication app;
    markupsModuleTest(int argc, char * argv[]) :
        app(argc, argv)
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
            QTimer::singleShot(100, &app, SLOT(quit()));
        }
        return app.exec();
    }
	void setup()
    {
        qSlicerLiverMarkupsModule::setup();
	}

    void loadModules()
    {
        // copied from generated qSlicerLiverMarkupsModuleGenericTest
        if (!dependencies().isEmpty())
          {
          qSlicerModuleFactoryManager * moduleFactoryManager = app.moduleManager()->factoryManager();
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

    int checkMarkupNodes()
    {
        vtkSlicerApplicationLogic* appLogic = app.applicationLogic();
        vtkSlicerMarkupsLogic* markupsLogic = vtkSlicerMarkupsLogic::SafeDownCast(appLogic->GetModuleLogic("Markups"));
        if(!markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsSlicingContourNode"))
        {
            qCritical() << Q_FUNC_INFO<< "vtkMRMLMarkupsSlicingContourNode isn't registered";
            return 1;
        }
        if(!markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsDistanceContourNode"))
        {
            qCritical() << Q_FUNC_INFO<< "vtkMRMLMarkupsDistanceContourNode isn't registered";
            return 1;
        }
        if(!markupsLogic->IsMarkupsNodeRegistered("vtkMRMLMarkupsBezierSurfaceNode"))
        {
            qCritical() << Q_FUNC_INFO << "vtkMRMLMarkupsBezierSurfaceNode isn't registered";
            return 1;
        }
        return 0;
    }

    int checkDisplayNodes()
    {
        auto bezierSurfaceNode = vtkSmartPointer<vtkMRMLMarkupsBezierSurfaceNode>::New();
        auto distanceContourNode = vtkSmartPointer<vtkMRMLMarkupsDistanceContourNode>::New();
        auto slicingContourNode = vtkSmartPointer<vtkMRMLMarkupsSlicingContourNode>::New();

        int retval = 0;
        retval = retval || checkDisplayNode(bezierSurfaceNode, "vtkMRMLMarkupsBezierSurfaceDisplayNode");
        retval = retval || checkDisplayNode(distanceContourNode, "vtkMRMLMarkupsDistanceContourDisplayNode");
        retval = retval || checkDisplayNode(slicingContourNode, "vtkMRMLMarkupsSlicingContourDisplayNode");
        return retval;
    }

    int checkDisplayNode(vtkMRMLMarkupsNode* markupsNode, const char* displayClassName)
    {
        markupsNode->SetScene(app.mrmlScene());
        markupsNode->CreateDefaultDisplayNodes();
        if(!app.mrmlScene()->GetFirstNodeByClass(displayClassName))
        {
            qCritical() << Q_FUNC_INFO << displayClassName << " isn't added";
            return 1;
        }
        return 0;
    }
};

//-----------------------------------------------------------------------------
int qSlicerLiverMarkupsModuleTest(int argc, char * argv[] )
{
    markupsModuleTest markupsModule = markupsModuleTest(argc, argv);
    markupsModule.startApp();

	if(!markupsModule.isHidden())
		return 1;

    vtkSmartPointer<vtkMRMLScene> scene = markupsModule.app.mrmlScene();
    vtkSlicerApplicationLogic* appLogic = markupsModule.app.applicationLogic();

    markupsModule.loadModules();

    qDebug() << "initialize qSlicerLiverMarkupsModule";
//    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
    // Set path just to avoid a runtime warning at module initialization
    markupsModule.setPath(markupsModule.app.slicerHome() + '/' + markupsModule.app.slicerSharePath() + "/qt-loadable-modules/LiverMarkups");
    markupsModule.initialize(appLogic);
//    markupsModule.initialize(nullptr);
//    TESTING_OUTPUT_ASSERT_WARNINGS_END(); // warning due to using 0 as application logic

    vtkSlicerLiverMarkupsLogic* logic = vtkSlicerLiverMarkupsLogic::SafeDownCast(markupsModule.logic());
    if(!logic) {
        qCritical() << "No logic";
        return 1;
    }

    qDebug() <<"setMRMLScene start";
    markupsModule.setMRMLScene(scene.GetPointer());

    qDebug() <<"Check Markup Nodes";
    int retval = markupsModule.checkMarkupNodes();
    qDebug() <<"Check Markup Display Nodes";
    retval = retval || markupsModule.checkDisplayNodes();

    if(retval != 0)
        return retval;

    return markupsModule.runApp(argc, argv);

//	return 0;
}
