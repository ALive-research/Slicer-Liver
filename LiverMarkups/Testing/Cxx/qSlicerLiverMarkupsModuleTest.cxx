// Qt includes
#include <QApplication>
#include <QDebug>
#include <QTimer>

#include "qSlicerLiverMarkupsModule.h"

// MRML includes
#include <vtkMRMLScene.h>

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
	markupsModuleTest markupsModule = markupsModuleTest();

	if(!markupsModule.isHidden())
		return 1;

	vtkSmartPointer<vtkMRMLScene> scene = vtkSmartPointer<vtkMRMLScene>::New();

	markupsModule.setup();


	return 0;

	//Copied from qMRMLAnnotationROIWidgetTest1.cxx

//  qMRMLWidget::preInitializeApplication();
//  QApplication app(argc, argv);
//  qMRMLWidget::postInitializeApplication();

//  vtkSmartPointer<vtkMRMLScene> scene =
//	vtkSmartPointer<vtkMRMLScene>::New();
//  vtkSmartPointer<vtkMRMLAnnotationROINode> roi =
//	vtkSmartPointer<vtkMRMLAnnotationROINode>::New();
//  scene->AddNode(roi);

//  qMRMLAnnotationROIWidget widget;
//  widget.setMRMLAnnotationROINode(roi);

//  qDebug() << "start edit";

//  roi->SetXYZ(1, 1, 1);

//  qDebug() << "end edit";

//  widget.show();

//  if (argc < 2 || QString(argv[1]) != "-I")
//	{
//	QTimer::singleShot(100, &app, SLOT(quit()));
//	}

//  return app.exec();
}
