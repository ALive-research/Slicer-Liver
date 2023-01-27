// Qt includes
#include <QApplication>
#include <QDebug>
#include <QTimer>
#include <vtkSlicerApplicationLogic.h>

// Slicer includes
#include "qSlicerLiverMarkupsModule.h"
#include <qSlicerApplication.h>

// MRML includes
#include <vtkMRMLScene.h>

// VTK includes
#include "qMRMLWidget.h"
#include <vtkTestingOutputWindow.h>

class markupsModuleTest: public qSlicerLiverMarkupsModule
{
public:

	void setup()
    {
        qSlicerLiverMarkupsModule::setup();
	}
};

//-----------------------------------------------------------------------------
int qSlicerLiverMarkupsModuleTest(int argc, char * argv[] )
{
    //Using code example from qSlicerModelsModuleWidgetTest1

    qMRMLWidget::preInitializeApplication();
//    QApplication app(argc, argv);
    qSlicerApplication app(argc, argv);
    qMRMLWidget::postInitializeApplication();

	markupsModuleTest markupsModule = markupsModuleTest();

	if(!markupsModule.isHidden())
		return 1;

    vtkSmartPointer<vtkMRMLScene> scene = vtkSmartPointer<vtkMRMLScene>::New();

//    markupsModule.setup();// Use initialize instead

//    vtkNew<vtkSlicerApplicationLogic> appLogic;
    vtkSlicerApplicationLogic* appLogic = app.applicationLogic();

    qDebug() << "initialize start";
//    TESTING_OUTPUT_ASSERT_WARNINGS_BEGIN();
    // Set path just to avoid a runtime warning at module initialization
    markupsModule.setPath(app.slicerHome() + '/' + app.slicerSharePath() + "/qt-loadable-modules/LiverMarkups");
    markupsModule.initialize(appLogic);
//    markupsModule.initialize(nullptr);
//    TESTING_OUTPUT_ASSERT_WARNINGS_END(); // warning due to using 0 as application logic

    vtkMRMLAbstractLogic* logic = markupsModule.logic();
    if(!logic) {
        qCritical() << "No logic";
        return 1;
    }
    qDebug() << "initialize finished";

    qDebug() <<"setMRMLScene start";
    markupsModule.setMRMLScene(scene.GetPointer());
    qDebug() << "setMRMLScene finish";

    if (argc < 2 || QString(argv[1]) != "-I")
    {
        QTimer::singleShot(100, &app, SLOT(quit()));
    }
    return app.exec();
//	return 0;
}
