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

// MRML includes
#include <vtkMRMLScene.h>

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

    void startApp(int argc, char * argv[] )
    {
        //Using code example from qSlicerModelsModuleWidgetTest1

        qMRMLWidget::preInitializeApplication();
    //    QApplication app(argc, argv);
//        app = qSlicerApplication(argc, argv);
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

    vtkMRMLAbstractLogic* createLogic()
    {
        return qSlicerLiverMarkupsModule::createLogic();
    }
};

//-----------------------------------------------------------------------------
int qSlicerLiverMarkupsModuleTest(int argc, char * argv[] )
{
    markupsModuleTest markupsModule = markupsModuleTest(argc, argv);
    markupsModule.startApp(argc, argv);

	if(!markupsModule.isHidden())
		return 1;

    vtkSmartPointer<vtkMRMLScene> scene = vtkSmartPointer<vtkMRMLScene>::New();

//    markupsModule.setup();// Use initialize instead

//    vtkNew<vtkSlicerApplicationLogic> appLogic;
    vtkSlicerApplicationLogic* appLogic = markupsModule.app.applicationLogic();

    markupsModule.loadModules();

    qDebug() << "initialize start";
//    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
    // Set path just to avoid a runtime warning at module initialization
    markupsModule.setPath(markupsModule.app.slicerHome() + '/' + markupsModule.app.slicerSharePath() + "/qt-loadable-modules/LiverMarkups");
    markupsModule.initialize(appLogic);
//    markupsModule.initialize(nullptr);
//    TESTING_OUTPUT_ASSERT_WARNINGS_END(); // warning due to using 0 as application logic

    //vtkMRMLAbstractLogic* logic = markupsModule.logic();
    vtkSlicerLiverMarkupsLogic* logic = vtkSlicerLiverMarkupsLogic::SafeDownCast(markupsModule.logic());
    if(!logic) {
        qCritical() << "No logic";
        return 1;
    }
    qDebug() << "initialize finished";

    qDebug() <<"setMRMLScene start";

    markupsModule.setMRMLScene(scene.GetPointer());
    //qDebug() << "GetSelectionNodeID: " << logic->GetSelectionNodeID().c_str();
    qDebug() << "setMRMLScene finish";

    return markupsModule.runApp(argc, argv);

//	return 0;
}
