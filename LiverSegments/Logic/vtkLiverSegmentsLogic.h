/*===============================================================================

  Project: LiverSegments
  Module: vtkSegmentClassificationLogic.h

  Copyright (c) 2019,  Oslo University Hospital

  All rights reserved. This is propietary software. In no event shall the author
  be liable for any claim or damages 

  ===============================================================================*/


#ifndef __vtkLiverSegmentsLogic_h
#define __vtkLiverSegmentsLogic_h

#include "vtkSlicerLiverSegmentsModuleLogicExport.h"

#include <vtkObject.h>
#include <vtkSmartPointer.h>

// Forward delcarations
class vtkPolyData;
class vtkKdTreePointLocator;
class vtkMRMLLabelMapVolumeNode;
class vtkSegment;
class vtkMRMLSegmentationNode;
class vtkMRMLModelNode;


class VTK_SLICER_LIVERSEGMENTS_MODULE_LOGIC_EXPORT
vtkLiverSegmentsLogic : public vtkObject
{
 private:
    vtkSmartPointer<vtkKdTreePointLocator> locator;

 public:
  static vtkLiverSegmentsLogic *New();
  vtkTypeMacro(vtkLiverSegmentsLogic, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

 public:
  void SegmentClassification(vtkPolyData *centerlines,
                             vtkMRMLLabelMapVolumeNode *labelMap);
  void markSegmentWithID(vtkMRMLModelNode *segment, int segmentId);
  void addSegmentToCenterlineModel(vtkMRMLModelNode *summedCenterline, vtkMRMLModelNode *segmentCenterline);
  int  SegmentClassificationProcessing(vtkMRMLModelNode *centerlineModel, vtkMRMLLabelMapVolumeNode *labelMap);
  void initializeCenterlineSearchModel(vtkMRMLModelNode *summedCenterline);

 protected:
  vtkLiverSegmentsLogic();
  ~vtkLiverSegmentsLogic() override;
  vtkLiverSegmentsLogic(const vtkLiverSegmentsLogic&);
  void operator=(const vtkLiverSegmentsLogic&);

};

#endif

