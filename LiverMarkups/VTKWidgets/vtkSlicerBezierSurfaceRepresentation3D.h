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
  Hospital and NTNU) and was supported by The Research Council of Norway
  through the ALive project (grant nr. 311393).

==============================================================================*/

#ifndef __vtkslicerbeziersurfacewidgetrepresentation3d_h_
#define __vtkslicerbeziersurfacewidgetrepresentation3d_h_

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// Markups VTKWidgets includes
#include "vtkMultiTextureObjectHelper.h"
#include "vtkSlicerMarkupsWidgetRepresentation3D.h"

// MRML includes
#include <vtkMRMLModelNode.h>

// VTK includes
#include <vtkActor2D.h>
#include <vtkCamera.h>
#include <vtkOpenGLPolyDataMapper2D.h>
#include <vtkSmartPointer.h>
#include <vtkWeakPointer.h>

//------------------------------------------------------------------------------
class vtkBezierSurfaceSource;
class vtkGaussianBlurPass;
class vtkOpenGLActor;
class vtkOpenGLBezierResectionPolyDataMapper;
class vtkOpenGLResection2DPolyDataMapper;
class vtkPlaneSource;
class vtkPoints;
class vtkPolyData;
class vtkPolyDataNormals;
class vtkRenderStepsPass;
class vtkTextureObject;
class vtkTubeFilter;

//------------------------------------------------------------------------------
class vtkMRMLMarkupsBezierSurfaceNode;
class vtkMRMLScalarVolumeNode;

//------------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkSlicerBezierSurfaceRepresentation3D
: public vtkSlicerMarkupsWidgetRepresentation3D
{

static const int RENDERER_LAYER = 2;

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
  void SetRenderer(vtkRenderer *ren) override;

protected:
  /// TransferDistanceMap
  void CreateAndTransferDistanceMapTexture(vtkMRMLScalarVolumeNode* node, int numComps);
  void CreateAndTransferVascularSegmentsTexture(vtkMRMLScalarVolumeNode *node);
  void Ratio(bool flexibleBoundery);
  void ResectogramPlaneCenter(bool mirror);

 protected:
  //k Bezier surface releated elements
  vtkSmartPointer<vtkBezierSurfaceSource> BezierSurfaceSource;
  vtkSmartPointer<vtkPoints> BezierSurfaceControlPoints;
  vtkSmartPointer<vtkOpenGLBezierResectionPolyDataMapper> BezierSurfaceResectionMapper;
  vtkSmartPointer<vtkOpenGLActor> BezierSurfaceActor;
  vtkSmartPointer<vtkPolyDataNormals> BezierSurfaceNormals;
  vtkSmartPointer<vtkOpenGLActor> ResectogramActor;
  vtkSmartPointer<vtkOpenGLResection2DPolyDataMapper> ResectogramMapper;
  vtkSmartPointer<vtkPlaneSource> ResectogramPlaneSource;
  vtkSmartPointer<vtkDataArray> BezierSurfaceSourcePointsArray;
  vtkSmartPointer<vtkCamera> ResectogramCamera;


  // Control polygon related elements
  vtkSmartPointer<vtkPolyData> ControlPolygonPolyData;
  vtkSmartPointer<vtkTubeFilter> ControlPolygonTubeFilter;
  vtkSmartPointer<vtkPolyDataMapper> ControlPolygonMapper;
  vtkSmartPointer<vtkActor> ControlPolygonActor;

  // Distance mapping related elements
  vtkSmartPointer<vtkMultiTextureObjectHelper> DistanceMapTexture;
  vtkWeakPointer<vtkMRMLScalarVolumeNode> DistanceMapVolumeNode;
  vtkNew<vtkMatrix4x4> VBOShiftScale;
  vtkNew<vtkTransform> VBOInverseTransform;
  vtkWeakPointer<vtkShaderProperty> ShaderProperty;

  // create the basic VTK render steps
  vtkSmartPointer<vtkRenderStepsPass> ResectogramRenderPasses;
  vtkSmartPointer<vtkRenderer> ResectogramRenderer;
  vtkSmartPointer<vtkGaussianBlurPass> ResectogramBlurPass;


  // Vascular Segments related elements
  vtkSmartPointer<vtkMultiTextureObjectHelper> VascularSegmentsTexture;
  vtkWeakPointer<vtkMRMLScalarVolumeNode> VascularSegmentsVolumeNode;


protected:
  vtkSlicerBezierSurfaceRepresentation3D();
  ~vtkSlicerBezierSurfaceRepresentation3D() override;

  void UpdateControlPolygonGeometry(vtkMRMLMarkupsBezierSurfaceNode*);
  void UpdateControlPolygonDisplay(vtkMRMLMarkupsBezierSurfaceNode*);
  void UpdateBezierSurfaceGeometry(vtkMRMLMarkupsBezierSurfaceNode*);
  void UpdateBezierSurfaceDisplay(vtkMRMLMarkupsBezierSurfaceNode*);

private:
  vtkSlicerBezierSurfaceRepresentation3D(const vtkSlicerBezierSurfaceRepresentation3D&) = delete;
  void operator=(const vtkSlicerBezierSurfaceRepresentation3D&) = delete;
};

#endif // __vtkslicerbeziersurfacewidgetrepresentation3d_h_
