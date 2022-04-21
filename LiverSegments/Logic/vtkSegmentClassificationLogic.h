/*===============================================================================

  Project: LiverSegments
  Module: vtkSegmentClassificationLogic.h

  Copyright (c) 2019,  Oslo University Hospital

  All rights reserved. This is propietary software. In no event shall the author
  be liable for any claim or damages 

  ===============================================================================*/


#ifndef __vtkSegmentClassificationLogic_h
#define __vtkSegmentClassificationLogic_h

#include "vtkSlicerLiverSegmentsModuleLogicExport.h"

#include <vtkObject.h>

// Forward delcarations
class vtkPolyData;
class vtkMRMLLabelMapVolumeNode;


// Class vtkSegmentClassificationLogic
class VTK_SLICER_LIVERSEGMENTS_MODULE_LOGIC_EXPORT
vtkSegmentClassificationLogic : public vtkObject
{

 public:
  static vtkSegmentClassificationLogic *New();
  vtkTypeMacro(vtkSegmentClassificationLogic, vtkObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

 public:
//  void SegmentClassification(vtkPolyData *centerlines,
//			     vtkMRMLLabelMapVolumeNode *inputLabelmap,
//			     vtkMRMLLabelMapVolumeNode *outputLabelmap);
  void SegmentClassification(vtkPolyData *centerlines);

 protected:
  vtkSegmentClassificationLogic();
  ~vtkSegmentClassificationLogic() override;
  vtkSegmentClassificationLogic(const vtkSegmentClassificationLogic&);
  void operator=(const vtkSegmentClassificationLogic&);

};

#endif

