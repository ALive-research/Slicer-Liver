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

#include "vtkSlicerBezierSurfaceRepresentation3D.h"

#include "vtkMRMLMarkupsBezierSurfaceNode.h"
#include "vtkMRMLMarkupsBezierSurfaceDisplayNode.h"
#include "vtkBezierSurfaceSource.h"
#include "vtkMRMLScalarVolumeNode.h"
#include "vtkSlicerMarkupsWidgetRepresentation.h"
#include "vtkOpenGLBezierResectionPolyDataMapper.h"
#include "vtkOpenGLResection2DPolyDataMapper.h"
#include "vtkMultiTextureObjectHelper.h"


// MRML includes
#include <qMRMLThreeDWidget.h>
#include <vtkMRMLDisplayableManagerGroup.h>
#include <vtkMRMLModelDisplayableManager.h>

// Slicer includes
#include <qSlicerApplication.h>
#include <qSlicerLayoutManager.h>

// VTK-Addon includes
#include <vtkAddonMathUtilities.h>

// VTK includes
#include "vtkRenderer.h"
#include <vtkActor.h>
#include <vtkOpenGLCamera.h>
#include <vtkCollection.h>
#include <vtkImageData.h>
#include <vtkNew.h>
#include <vtkOpenGLActor.h>
#include <vtkOpenGLRenderWindow.h>
#include <vtkOpenGLVertexBufferObjectGroup.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkPlaneSource.h>
#include <vtkPointData.h>
#include <vtkPolyDataMapper.h>
#include <vtkPolyDataNormals.h>
#include <vtkPolyLine.h>
#include <vtkProperty.h>
#include <vtkRenderWindow.h>
#include <vtkSetGet.h>
#include <vtkShaderProperty.h>
#include <vtkSmartPointer.h>
#include <vtkTexture.h>
#include <vtkTextureObject.h>
#include <vtkUniforms.h>
#include <vtkMatrix3x3.h>
#include "vtkRendererCollection.h"
#include <vtkNamedColors.h>
#include <vtkTypeFloat32Array.h>
#include <vtkImageCast.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerBezierSurfaceRepresentation3D);
static const int RENDERER_LAYER = 1;
//------------------------------------------------------------------------------
vtkSlicerBezierSurfaceRepresentation3D::vtkSlicerBezierSurfaceRepresentation3D() {
    this->BezierSurfaceSource = vtkSmartPointer<vtkBezierSurfaceSource>::New();
    this->BezierSurfaceSource->SetResolution(20, 20);



    // Set the initial position of the bezier surface
    auto planeSource = vtkSmartPointer<vtkPlaneSource>::New();
    planeSource->SetResolution(3, 3);
    planeSource->Update();

    this->BezierSurfaceNormals = vtkSmartPointer<vtkPolyDataNormals>::New();
    this->BezierSurfaceNormals->SetInputConnection(this->BezierSurfaceSource->GetOutputPort());

    this->BezierPlane = vtkSmartPointer<vtkBezierSurfaceSource>::New();
    this->BezierPlane->SetResolution(20,20);
    auto PlaneControlPoints = vtkSmartPointer<vtkPoints>::New();

    for(int i=0;i<4;i++){
        PlaneControlPoints->InsertNextPoint(-60,(i*40),0);
        PlaneControlPoints->InsertNextPoint(-20,(i*40),0);
        PlaneControlPoints->InsertNextPoint(20,(i*40),0);
        PlaneControlPoints->InsertNextPoint(60,(i*40),0);

    }

    this->BezierPlane->SetControlPoints(PlaneControlPoints);
    this->BezierPlane->Update();

    auto BezierPlanePoints = BezierPlane->GetOutput()->GetPoints()->GetData();
    BezierPlanePoints->SetName("BSPlanePoints");
    this->BezierSurfaceNormals->GetOutput()->GetPointData()->AddArray(BezierPlanePoints);


    this->BezierSurfaceControlPoints = vtkSmartPointer<vtkPoints>::New();
    this->BezierSurfaceControlPoints->SetNumberOfPoints(16);
    this->BezierSurfaceControlPoints->DeepCopy(planeSource->GetOutput()->GetPoints());;

    this->BezierSurfaceResectionMapper = vtkSmartPointer<vtkOpenGLBezierResectionPolyDataMapper>::New();
    this->BezierSurfaceResectionMapper->SetInputConnection(this->BezierSurfaceNormals->GetOutputPort());
    this->BezierSurfaceActor = vtkSmartPointer<vtkOpenGLActor>::New();
    this->BezierSurfaceActor->SetMapper(this->BezierSurfaceResectionMapper);

//    this->BezierSurfaceResectionMapper2D = vtkSmartPointer<vtkOpenGLBezierResectionPolyDataMapper2D>::New();
//    this->BezierSurfaceResectionMapper2D->SetInputConnection(this->BezierSurfaceNormals->GetOutputPort());
////    this->BezierSurfaceResectionMapper2D->SetInputConnection(BezierPlane->GetOutputPort());
//
//    this->BezierSurfaceActor2D = vtkSmartPointer<vtkOpenGLActor>::New();
//    this->BezierSurfaceActor2D->SetMapper(this->BezierSurfaceResectionMapper2D);

    //----------------------------
    this->BezierSurfaceResectionMapper2D = vtkSmartPointer<vtkOpenGLResection2DPolyDataMapper>::New();
    this->BezierSurfaceResectionMapper2D->SetInputConnection(BezierPlane->GetOutputPort());
//    this->BezierSurfaceResectionMapper2D->SetInputConnection(BezierPlane->GetOutputPort());

    this->BezierSurfaceActor2D = vtkSmartPointer<vtkOpenGLActor>::New();
    this->BezierSurfaceActor2D->SetMapper(this->BezierSurfaceResectionMapper2D);

    //==========================================================


    this->ControlPolygonPolyData = vtkSmartPointer<vtkPolyData>::New();
    this->ControlPolygonTubeFilter = vtkSmartPointer<vtkTubeFilter>::New();
    this->ControlPolygonTubeFilter->SetInputData(this->ControlPolygonPolyData.GetPointer());
    this->ControlPolygonTubeFilter->SetRadius(1);
    this->ControlPolygonTubeFilter->SetNumberOfSides(20);

    this->ControlPolygonMapper = vtkSmartPointer<vtkPolyDataMapper>::New();
    this->ControlPolygonMapper->SetInputConnection(this->ControlPolygonTubeFilter->GetOutputPort());

    this->ControlPolygonActor = vtkSmartPointer<vtkActor>::New();
    this->ControlPolygonActor->SetMapper(this->ControlPolygonMapper);

    this->DistanceMapVolumeNode = nullptr;

}

//------------------------------------------------------------------------------
vtkSlicerBezierSurfaceRepresentation3D::~vtkSlicerBezierSurfaceRepresentation3D() = default;

//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::UpdateFromMRML(vtkMRMLNode *caller, unsigned long event,
                                                            void *callData /*=nullptr*/) {

    this->Superclass::UpdateFromMRML(caller, event, callData);

    auto liverMarkupsBezierSurfaceNode =
            vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(this->GetMarkupsNode());
    if (!liverMarkupsBezierSurfaceNode || !this->IsDisplayable()) {
        this->VisibilityOff();
        return;
    }

    this->UpdateBezierSurfaceGeometry(liverMarkupsBezierSurfaceNode);
    this->UpdateBezierSurfaceDisplay(liverMarkupsBezierSurfaceNode);
    this->UpdateControlPolygonGeometry(liverMarkupsBezierSurfaceNode);
    this->UpdateControlPolygonDisplay(liverMarkupsBezierSurfaceNode);

    double diameter = (this->MarkupsDisplayNode->GetCurveLineSizeMode() == vtkMRMLMarkupsDisplayNode::UseLineDiameter ?
                       this->MarkupsDisplayNode->GetLineDiameter() : this->ControlPointSize *
                                                                     this->MarkupsDisplayNode->GetLineThickness());
    this->ControlPolygonTubeFilter->SetRadius(diameter * 0.5);

    int controlPointType = Active;
    if (this->MarkupsDisplayNode->GetActiveComponentType() != vtkMRMLMarkupsDisplayNode::ComponentLine) {
        controlPointType = this->GetAllControlPointsSelected() ? Selected : Unselected;
    }
    this->ControlPolygonActor->SetProperty(this->GetControlPointsPipeline(controlPointType)->Property);

    // Update the Vascular Segments as 3D texture (if changed)
    std::cout<<"-ok 0-----------ok till here "<<endl;
    auto VascularSegments = liverMarkupsBezierSurfaceNode->GetVascularSegmentsVolumeNode();
    if (this->VascularSegmentsVolumeNode != VascularSegments) {
        std::cout<<"-ok 1-----------ok till here "<<endl;
        this->CreateAndTransferVascularSegmentsTexture(VascularSegments);
        std::cout<<"-ok 2-----------ok till here "<<endl;
        this->VascularSegmentsVolumeNode = VascularSegments;
    }
    // Update the distance map as 3D texture (if changed)
    auto distanceMap = liverMarkupsBezierSurfaceNode->GetDistanceMapVolumeNode();
    auto BezierSurfaceDisplayNode = vtkMRMLMarkupsBezierSurfaceDisplayNode::SafeDownCast(liverMarkupsBezierSurfaceNode->GetDisplayNode());

    if (this->DistanceMapVolumeNode != distanceMap) {
        this->CreateAndTransferDistanceMapTexture(distanceMap, BezierSurfaceDisplayNode->GetTextureNumComps());

        // Update transformation matrices
        auto imageData = distanceMap ? distanceMap->GetImageData() : nullptr;
        if (imageData) {
            auto rasToIjkT = vtkSmartPointer<vtkMatrix4x4>::New();
            auto ijkToTextureT = vtkSmartPointer<vtkMatrix4x4>::New();

            auto dimensions = imageData->GetDimensions();

            distanceMap->GetRASToIJKMatrix(rasToIjkT);
            rasToIjkT->Transpose();

            auto scaling = vtkSmartPointer<vtkTransform>::New();
            scaling->Scale(1.0 / dimensions[0], 1.0 / dimensions[1], 1.0 / dimensions[2]);
            scaling->GetTranspose(ijkToTextureT);

            this->BezierSurfaceResectionMapper->SetRasToIjkMatrixT(rasToIjkT);
            this->BezierSurfaceResectionMapper->SetIjkToTextureMatrixT(ijkToTextureT);

            this->BezierSurfaceResectionMapper2D->SetRasToIjkMatrixT(rasToIjkT);
            this->BezierSurfaceResectionMapper2D->SetIjkToTextureMatrixT(ijkToTextureT);
        }

        this->DistanceMapVolumeNode = distanceMap;
    }

    //------------------- add new renderer here ----------------------//
    auto renderWindow1 = vtkRenderWindow::SafeDownCast(this->GetRenderer()->GetRenderWindow());
    auto renderers = renderWindow1->GetRenderers();

    if(BezierSurfaceDisplayNode->GetShowResection2D()){
        if(renderers->GetNumberOfItems()!=5){
            std::cout<<"-------------------add new renderer------------------"<<endl;
            double yViewport[4] = {0, 0.6, 0.3, 1.0};

            if (renderWindow1->GetNumberOfLayers() < RENDERER_LAYER+1)
            {
                renderWindow1->SetNumberOfLayers( RENDERER_LAYER+1 );
            }
            auto CoRenderer2D = vtkSmartPointer<vtkRenderer>::New();
            CoRenderer2D->SetLayer(RENDERER_LAYER);
            CoRenderer2D->InteractiveOff();
            CoRenderer2D->AddActor(this->BezierSurfaceActor2D);
            CoRenderer2D->SetViewport(yViewport);
            renderWindow1->AddRenderer(CoRenderer2D);
            renderWindow1->Render();
        }
    }
    this->NeedToRenderOn();
}

void vtkSlicerBezierSurfaceRepresentation3D::GetActors(vtkPropCollection *pc) {
    this->Superclass::GetActors(pc);
    this->BezierSurfaceActor->GetActors(pc);
    this->ControlPolygonActor->GetActors(pc);


}

//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::ReleaseGraphicsResources(
        vtkWindow *win) {
    this->Superclass::ReleaseGraphicsResources(win);
    this->BezierSurfaceActor->ReleaseGraphicsResources(win);
    this->BezierSurfaceActor2D->ReleaseGraphicsResources(win);
    this->ControlPolygonActor->ReleaseGraphicsResources(win);
}

//----------------------------------------------------------------------
int vtkSlicerBezierSurfaceRepresentation3D::RenderOverlay(vtkViewport *viewport) {
    int count = 0;
    count = this->Superclass::RenderOverlay(viewport);
    if (this->BezierSurfaceActor->GetVisibility()) {
        count += this->BezierSurfaceActor->RenderOverlay(viewport);
        count += this->ControlPolygonActor->RenderOverlay(viewport);
    }
    return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerBezierSurfaceRepresentation3D::RenderOpaqueGeometry(
        vtkViewport *viewport) {
    int count = 0;
    count = this->Superclass::RenderOpaqueGeometry(viewport);
    if (this->BezierSurfaceActor->GetVisibility()) {
        count += this->BezierSurfaceActor->RenderOpaqueGeometry(viewport);
    }
    if (this->ControlPolygonActor->GetVisibility()) {
        double diameter = (this->MarkupsDisplayNode->GetCurveLineSizeMode() ==
                           vtkMRMLMarkupsDisplayNode::UseLineDiameter ?
                           this->MarkupsDisplayNode->GetLineDiameter() : this->ControlPointSize *
                                                                         this->MarkupsDisplayNode->GetLineThickness());
        this->ControlPolygonTubeFilter->SetRadius(diameter * 0.5);
        count += this->ControlPolygonActor->RenderOpaqueGeometry(viewport);
    }
    return count;
}

//-----------------------------------------------------------------------------
int vtkSlicerBezierSurfaceRepresentation3D::RenderTranslucentPolygonalGeometry(
        vtkViewport *viewport) {
    int count = 0;
    count = this->Superclass::RenderTranslucentPolygonalGeometry(viewport);
    if (this->BezierSurfaceActor->GetVisibility()) {
        // The internal actor needs to share property keys.
        // This eBasiclynsures the mapper state is consistent and allows depth peeling to work as expected.
        this->BezierSurfaceActor->SetPropertyKeys(this->GetPropertyKeys());
        count += this->BezierSurfaceActor->RenderTranslucentPolygonalGeometry(viewport);
    }
    if (this->ControlPolygonActor->GetVisibility()) {
        // The internal actor needs to share property keys.
        // This ensures the mapper state is consistent and allows depth peeling to work as expected.
        this->ControlPolygonActor->SetPropertyKeys(this->GetPropertyKeys());
        count += this->ControlPolygonActor->RenderTranslucentPolygonalGeometry(viewport);
    }
    return count;
}

//-----------------------------------------------------------------------------
vtkTypeBool vtkSlicerBezierSurfaceRepresentation3D::HasTranslucentPolygonalGeometry() {
    if (this->Superclass::HasTranslucentPolygonalGeometry()) {
        return true;
    }
    if (this->BezierSurfaceActor->GetVisibility() && this->BezierSurfaceActor->HasTranslucentPolygonalGeometry()) {
        return true;
    }
    if (this->BezierSurfaceActor2D->GetVisibility() && this->BezierSurfaceActor2D->HasTranslucentPolygonalGeometry()) {
        return true;
    }
    if (this->ControlPolygonActor->GetVisibility() && this->ControlPolygonActor->HasTranslucentPolygonalGeometry()) {
        return true;
    }
    return false;
}

//----------------------------------------------------------------------
double *vtkSlicerBezierSurfaceRepresentation3D::GetBounds() {
    vtkBoundingBox boundingBox;
    const std::vector<vtkProp *> actors({
                                                this->BezierSurfaceActor,
//                                                this->BezierSurfaceActor2D,
                                                this->ControlPolygonActor});
    this->AddActorsBounds(boundingBox, actors, Superclass::GetBounds());
    boundingBox.GetBounds(this->Bounds);
    return this->Bounds;
}


//-----------------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::PrintSelf(ostream &os, vtkIndent indent) {
    //Superclass typedef defined in vtkTypeMacro() found in vtkSetGet.h
    this->Superclass::PrintSelf(os, indent);

    if (this->BezierSurfaceActor) {
        os << indent << "BezierSurface Visibility: " << this->BezierSurfaceActor->GetVisibility() << "\n";
    } else {
        os << indent << "BezierSurface Visibility: (none)\n";
    }
    if (this->BezierSurfaceActor2D) {
        os << indent << "BezierSurface2D Visibility: " << this->BezierSurfaceActor2D->GetVisibility() << "\n";
    } else {
        os << indent << "BezierSurface2D Visibility: (none)\n";
    }
    if (this->ControlPolygonActor) {
        os << indent << "ControlPolygon Visibility: " << this->ControlPolygonActor->GetVisibility() << "\n";
    } else {
        os << indent << "ControlPolygon Visibility: (none)\n";
    }
}



//-----------------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::UpdateBezierSurfaceGeometry(vtkMRMLMarkupsBezierSurfaceNode *node) {
    if (!node) {
        return;
    }

    if (node->GetNumberOfControlPoints() == 16) {
        for (int i = 0; i < 16; i++) {
            double point[3];
            node->GetNthControlPointPosition(i, point);
            this->BezierSurfaceControlPoints->SetPoint(i,
                                                       static_cast<float>(point[0]),
                                                       static_cast<float>(point[1]),
                                                       static_cast<float>(point[2]));
        }

        this->BezierSurfaceSource->SetControlPoints(this->BezierSurfaceControlPoints);
        this->BezierSurfaceSource->Update();
        this->p = this->BezierSurfaceSource->GetOutput()->GetPoints()->GetData();
        this->p->SetName("BSPoints");
        if(this->BezierPlane->GetOutput()->GetPointData()->GetArray("BSPoints")){
            this->BezierPlane->GetOutput()->GetPointData()->RemoveArray("BSPoints");
            this->BezierPlane->GetOutput()->GetPointData()->AddArray(this->p);
        }else{
            this->BezierPlane->GetOutput()->GetPointData()->AddArray(this->p);
        }
    }
}

//-----------------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::UpdateControlPolygonGeometry(vtkMRMLMarkupsBezierSurfaceNode *node) {
    if (node->GetNumberOfControlPoints() == 16) {
        //Generate topology;
        vtkSmartPointer<vtkCellArray> planeCells =
                vtkSmartPointer<vtkCellArray>::New();
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                vtkSmartPointer<vtkPolyLine> polyLine = vtkSmartPointer<vtkPolyLine>::New();
                polyLine->GetPointIds()->SetNumberOfIds(5);
                polyLine->GetPointIds()->SetId(0, i * 4 + j);
                polyLine->GetPointIds()->SetId(1, i * 4 + j + 1);
                polyLine->GetPointIds()->SetId(2, (i + 1) * 4 + j + 1);
                polyLine->GetPointIds()->SetId(3, (i + 1) * 4 + j);
                polyLine->GetPointIds()->SetId(4, i * 4 + j);
                planeCells->InsertNextCell(polyLine);
            }
        }

        this->ControlPolygonPolyData->SetPoints(this->BezierSurfaceControlPoints);
        this->ControlPolygonPolyData->SetLines(planeCells);
    }
}

//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::CreateAndTransferDistanceMapTexture(vtkMRMLScalarVolumeNode *node, int numComps) {

    auto renderWindow = vtkOpenGLRenderWindow::SafeDownCast(this->GetRenderer()->GetRenderWindow());
    this->DistanceMapTexture = vtkSmartPointer<vtkMultiTextureObjectHelper>::New();
    this->DistanceMapTexture->SetContext(renderWindow);

    if (!node) {
        vtkWarningMacro("vtkSlicerBezierSurfaceRepresentation::CreateAndTransferDistanceMap:"
                        "There is no distance map node associated. Texture won't be generated.");
        return;
    }

    auto imageData = node->GetImageData();
    if (!imageData) {
        vtkWarningMacro("vtkSlicerBezierSurfaceRepresentation::CreateAndTransferDistanceMap:"
                        "There is no image data in the specified scalar volume node.");
        return;
    }
    auto dimensions = imageData->GetDimensions();
    this->DistanceMapTexture->SetWrapS(vtkTextureObject::ClampToBorder);
    this->DistanceMapTexture->SetWrapT(vtkTextureObject::ClampToBorder);
    this->DistanceMapTexture->SetWrapR(vtkTextureObject::ClampToBorder);
    this->DistanceMapTexture->SetMinificationFilter(vtkTextureObject::Linear);
    this->DistanceMapTexture->SetMagnificationFilter(vtkTextureObject::Linear);
    this->DistanceMapTexture->SetBorderColor(1000.0f, 1000.0f, 0.0f, 0.0f);
    this->DistanceMapTexture->CreateSeq3DFromRaw(dimensions[0], dimensions[1], dimensions[2], numComps, VTK_FLOAT,
                                              imageData->GetScalarPointer(), 0);
}


//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::CreateAndTransferVascularSegmentsTexture(vtkMRMLScalarVolumeNode *node) {

    auto renderWindow = vtkOpenGLRenderWindow::SafeDownCast(this->GetRenderer()->GetRenderWindow());
    this->VascularSegmentsTexture = vtkSmartPointer<vtkMultiTextureObjectHelper>::New();
    this->VascularSegmentsTexture->SetContext(renderWindow);

    if (!node) {
        vtkWarningMacro("vtkSlicerBezierSurfaceRepresentation::CreateAndTransferDistanceMap:"
                        "There is no distance map node associated. Texture won't be generated.");
        return;
    }

    auto imageData = node->GetImageData();
    if (!imageData) {
        vtkWarningMacro("vtkSlicerBezierSurfaceRepresentation::CreateAndTransferDistanceMap:"
                        "There is no image data in the specified scalar volume node.");
        return;
    }

    vtkNew<vtkImageCast> cast;
    cast->SetInputData(imageData);
    cast->SetOutputScalarTypeToFloat();
    cast->Update();
    cast->GetOutput()->Print(std::cout);

    auto dimensions = imageData->GetDimensions();

    this->VascularSegmentsTexture->SetWrapS(vtkTextureObject::ClampToBorder);
    this->VascularSegmentsTexture->SetWrapT(vtkTextureObject::ClampToBorder);
    this->VascularSegmentsTexture->SetWrapR(vtkTextureObject::ClampToBorder);
    this->VascularSegmentsTexture->SetMinificationFilter(vtkTextureObject::Linear);
    this->VascularSegmentsTexture->SetMagnificationFilter(vtkTextureObject::Linear);
    this->VascularSegmentsTexture->SetBorderColor(1000.0f, 1000.0f, 0.0f, 0.0f);
    this->VascularSegmentsTexture->CreateSeq3DFromRaw(dimensions[0], dimensions[1], dimensions[2], 1, VTK_FLOAT,
                                                      cast->GetOutput()->GetScalarPointer(), 1);
}

//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::UpdateBezierSurfaceDisplay(vtkMRMLMarkupsBezierSurfaceNode *node) {

    auto displayNode = vtkMRMLMarkupsBezierSurfaceDisplayNode::SafeDownCast(node->GetDisplayNode());
    this->BezierSurfaceResectionMapper->SetResectionMargin(node->GetResectionMargin());
    this->BezierSurfaceResectionMapper->SetUncertaintyMargin(node->GetUncertaintyMargin());

    this->BezierSurfaceResectionMapper2D->SetResectionMargin(node->GetResectionMargin());
    this->BezierSurfaceResectionMapper2D->SetUncertaintyMargin(node->GetUncertaintyMargin());
    this->BezierSurfaceResectionMapper2D->SetHepaticContourSize(node->GetHepaticContourSize());
    this->BezierSurfaceResectionMapper2D->SetPortalContourSize(node->GetPortalContourSize());

    if (displayNode) {
        this->BezierSurfaceResectionMapper->SetResectionColor(displayNode->GetResectionColor());
        this->BezierSurfaceResectionMapper->SetResectionGridColor(displayNode->GetResectionGridColor());
        this->BezierSurfaceResectionMapper->SetResectionMarginColor(displayNode->GetResectionMarginColor());
        this->BezierSurfaceResectionMapper->SetUncertaintyMarginColor(displayNode->GetUncertaintyMarginColor());
        this->BezierSurfaceResectionMapper->SetResectionOpacity(displayNode->GetResectionOpacity());
        this->BezierSurfaceResectionMapper->SetResectionClipOut(displayNode->GetClipOut());
        this->BezierSurfaceResectionMapper->SetInterpolatedMargins(displayNode->GetInterpolatedMargins());
        this->BezierSurfaceResectionMapper->SetGridDivisions(displayNode->GetGridDivisions());
        this->BezierSurfaceResectionMapper->SetGridThicknessFactor(displayNode->GetGridThickness());



        this->BezierSurfaceResectionMapper2D->SetResectionColor(displayNode->GetResectionColor());
        this->BezierSurfaceResectionMapper2D->SetResectionGridColor(displayNode->GetResectionGridColor());
        this->BezierSurfaceResectionMapper2D->SetResectionMarginColor(displayNode->GetResectionMarginColor());
        this->BezierSurfaceResectionMapper2D->SetUncertaintyMarginColor(displayNode->GetUncertaintyMarginColor());
        this->BezierSurfaceResectionMapper2D->SetResectionOpacity(displayNode->GetResectionOpacity());
        this->BezierSurfaceResectionMapper2D->SetResectionClipOut(displayNode->GetClipOut());
        this->BezierSurfaceResectionMapper2D->SetInterpolatedMargins(displayNode->GetInterpolatedMargins());
        this->BezierSurfaceResectionMapper2D->SetGridDivisions(displayNode->GetGridDivisions());
        this->BezierSurfaceResectionMapper2D->SetGridThicknessFactor(displayNode->GetGridThickness());

        this->BezierSurfaceResectionMapper2D->SetHepaticContourColor(displayNode->GetHepaticContourColor());
        this->BezierSurfaceResectionMapper2D->SetPortalContourColor(displayNode->GetPortalContourColor());
        this->BezierSurfaceResectionMapper2D->SetTextureNumComps(displayNode->GetTextureNumComps());
    }
}

//----------------------------------------------------------------------
void vtkSlicerBezierSurfaceRepresentation3D::UpdateControlPolygonDisplay(vtkMRMLMarkupsBezierSurfaceNode *node) {
    auto displayNode = vtkMRMLMarkupsBezierSurfaceDisplayNode::SafeDownCast(node->GetDisplayNode());
    if (displayNode) {
        this->ControlPolygonActor->VisibilityOff();
        this->ControlPolygonActor->SetVisibility(displayNode->GetWidgetVisibility());
        for (int type = 0; type < vtkSlicerMarkupsWidgetRepresentation::NumberOfControlPointTypes; ++type) {
            auto controlPoints = reinterpret_cast<ControlPointsPipeline3D *>(this->ControlPoints[type]);
            controlPoints->Actor->SetVisibility(displayNode->GetWidgetVisibility());
        }
    }
}
