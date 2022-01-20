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

  This file was originally developed by Rafael Palomar (The Intervention Centre,
  Oslo University Hospital) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef __vtkslicerbeziersurfacewidgetrepresentation3d_h_
#define __vtkslicerbeziersurfacewidgetrepresentation3d_h_

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// Markups VTKWidgets includes
#include "vtkSlicerMarkupsWidgetRepresentation3D.h"

// MRML includes
#include <vtkMRMLModelNode.h>

// VTK includes
#include <vtkWeakPointer.h>
#include <vtkSmartPointer.h>

//------------------------------------------------------------------------------
class vtkBezierSurfaceSource;
class vtkPolyData;
class vtkPolyDataNormals;
class vtkPoints;
class vtkTextureObject;
class vtkTubeFilter;

//------------------------------------------------------------------------------
class vtkMRMLMarkupsBezierSurfaceNode;
class vtkMRMLScalarVolumeNode;

//------------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkSlicerBezierSurfaceRepresentation3D
: public vtkSlicerMarkupsWidgetRepresentation3D
{
public:
  static vtkSlicerBezierSurfaceRepresentation3D* New();
  vtkTypeMacro(vtkSlicerBezierSurfaceRepresentation3D, vtkSlicerMarkupsWidgetRepresentation3D);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  void UpdateFromMRML(vtkMRMLNode* caller, unsigned long event, void* callData=nullptr) override;

  /// Methods to make this class behave as a vtkProp.
  void GetActors(vtkPropCollection *) override;
  void ReleaseGraphicsResources(vtkWindow *) override;
  int RenderOverlay(vtkViewport *viewport) override;
  int RenderOpaqueGeometry(vtkViewport *viewport) override;
  int RenderTranslucentPolygonalGeometry(vtkViewport *viewport) override;
  vtkTypeBool HasTranslucentPolygonalGeometry() override;

  /// Return the bounds of the representation
  double *GetBounds() override;

protected:
  // Bezier surface releated elements
  vtkSmartPointer<vtkBezierSurfaceSource> BezierSurfaceSource;
  vtkSmartPointer<vtkPoints> BezierSurfaceControlPoints;
  vtkSmartPointer<vtkPolyDataMapper> BezierSurfaceMapper;
  vtkSmartPointer<vtkActor> BezierSurfaceActor;
  vtkSmartPointer<vtkPolyDataNormals> BezierSurfaceNormals;

  // Control polygon related elements
  vtkSmartPointer<vtkPolyData> ControlPolygonPolyData;
  vtkSmartPointer<vtkTubeFilter> ControlPolygonTubeFilter;
  vtkSmartPointer<vtkPolyDataMapper> ControlPolygonMapper;
  vtkSmartPointer<vtkActor> ControlPolygonActor;

  vtkSmartPointer<vtkTextureObject> DistanceMapTexture;
  vtkWeakPointer<vtkMRMLScalarVolumeNode> DistanceMap;

protected:
  vtkSlicerBezierSurfaceRepresentation3D();
  ~vtkSlicerBezierSurfaceRepresentation3D() override;

  void UpdateControlPolygon(vtkMRMLMarkupsBezierSurfaceNode*);
  void UpdateBezierSurface(vtkMRMLMarkupsBezierSurfaceNode*);

private:
  vtkSlicerBezierSurfaceRepresentation3D(const vtkSlicerBezierSurfaceRepresentation3D&) = delete;
  void operator=(const vtkSlicerBezierSurfaceRepresentation3D&) = delete;
};

#endif // __vtkslicerbeziersurfacewidgetrepresentation3d_h_
