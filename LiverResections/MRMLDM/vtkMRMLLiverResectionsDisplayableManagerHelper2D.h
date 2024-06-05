/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) Oslo University Hospital. All rights reserved.

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

  This file was originally developed by Rafael Palomar (Oslo University
  Hospital and NTNU) and Ruoyan Meng (NTNU), and was supported by The
  Research Council of Norway through the ALive project (grant nr. 311393).

  ==============================================================================*/

#ifndef SLICERLIVER_LIVERRESECTIONS_MRMLDM_VTKMRMLLIVERRESECTIONSDISPLAYABLEMANAGERHELPER2D_H_
#define SLICERLIVER_LIVERRESECTIONS_MRMLDM_VTKMRMLLIVERRESECTIONSDISPLAYABLEMANAGERHELPER2D_H_

//Liver resection module includes
#include "vtkSlicerLiverResectionsModuleMRMLDisplayableManagerExport.h"

//VTK includes
#include <vtkObject.h>
#include <vtkNew.h>
#include <vtkSmartPointer.h>
#include <vtkWeakPointer.h>

//-------------------------------------------------------------------------------
class vtkPoints;
class vtkActor2D;
class vtkRenderWindowInteractor;
class vtkRenderer;
class vtkPolyData;
class vtkObject;
class vtkCutter;
class vtkTransform;
class vtkMRMLMarkupsBezierSurfaceNode;
class vtkMRMLSliceNode;
class vtkMatrix4x4;
class vtkCollection;
class vtkDistancePolyDataFilter;
class vtkCallbackCommand;
class vtkBezierSurfaceSource;

//-------------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRMLDISPLAYABLEMANAGER_EXPORT
vtkMRMLLiverResectionsDisplayableManagerHelper2D
  :public vtkObject
{
 public:

// Description:
// VTK-specific functions for object creation and class hierarchy
  static vtkMRMLLiverResectionsDisplayableManagerHelper2D *New();
 vtkTypeMacro(vtkMRMLLiverResectionsDisplayableManagerHelper2D, vtkObject);

// Description:
// VTK-specific function for printing information
  void PrintSelf(ostream &os, vtkIndent indent) override;

// Description:
// Add surface contour to the 2D views
  void DisplaySurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node,
                             vtkMRMLSliceNode *sliceNode,
                             vtkRenderer *renderer);

  void UpdateSurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node);

// Description:
// Remove surface contour from the 2D views
  void RemoveSurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node,
                            vtkRenderer *renderer);
// Description:
// Remove all surface contours from the 2D views
  void RemoveAllSurfacesContours(vtkRenderer *renderer,
                                 vtkRenderWindowInteractor *interactor);

  void ChangeSurfaceVisibility(vtkMRMLMarkupsBezierSurfaceNode *node,
                               vtkRenderer *renderer);
  void GetBezierSurfaceControlPoints(vtkMRMLMarkupsBezierSurfaceNode *node);


 protected:

// Description:
// Constructor & destructor
  vtkMRMLLiverResectionsDisplayableManagerHelper2D();
  virtual ~vtkMRMLLiverResectionsDisplayableManagerHelper2D();

// Description:
// Callback function to update the surface contour
  static void UpdateSurfaceContour(vtkObject *object,
                                   unsigned long int id,
                                   void *clientData,
                                   void *callerData);
 protected:

// Description:
// Class member variables.
  vtkWeakPointer<vtkMRMLSliceNode> SliceNode;
  vtkSmartPointer<vtkCutter> Cutter;
  vtkSmartPointer<vtkActor2D> ContourActor;
  vtkSmartPointer<vtkTransform> RASToXYTransform;
  vtkSmartPointer<vtkMatrix4x4> InvertedRASToXYMatrix;
  vtkSmartPointer<vtkDistancePolyDataFilter> DistanceFilter;
  vtkSmartPointer<vtkCallbackCommand> UpdateCommand;
  vtkSmartPointer<vtkBezierSurfaceSource> BezierSource;
  vtkSmartPointer<vtkPoints> BezierSurfaceControlPoints;
};

#endif //SLICERLIVER_LIVERRESECTIONS_MRMLDM_VTKMRMLLIVERRESECTIONSDISPLAYABLEMANAGERHELPER2D_H_
