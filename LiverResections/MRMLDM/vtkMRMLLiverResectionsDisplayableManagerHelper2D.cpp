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

#include "vtkMRMLLiverResectionsDisplayableManagerHelper2D.h"


//Liver resection module includes
#include <vtkMRMLLiverResectionNode.h>
#include <vtkMRMLMarkupsBezierSurfaceNode.h>
#include <vtkMRMLMarkupsBezierSurfaceDisplayNode.h>
#include "vtkBezierSurfaceSource.h"

//MRMLNodes
#include <vtkMRMLSliceNode.h>

//VTK includes
#include <vtkObjectFactory.h>
#include <vtkRenderWindowInteractor.h>
#include <vtkRenderer.h>
#include <vtkSmartPointer.h>
#include <vtkCallbackCommand.h>
#include <vtkMatrix4x4.h>
#include <vtkPlane.h>
#include <vtkCutter.h>
#include <vtkTransform.h>
#include <vtkTransformPolyDataFilter.h>
#include <vtkPolyDataMapper2D.h>
#include <vtkActor2D.h>
#include <vtkProperty2D.h>
#include <vtkColorTransferFunction.h>
#include <vtkDistancePolyDataFilter.h>
#include <vtkPoints.h>

vtkStandardNewMacro (vtkMRMLLiverResectionsDisplayableManagerHelper2D);

//---------------------------------------------------------------------------
vtkMRMLLiverResectionsDisplayableManagerHelper2D::
vtkMRMLLiverResectionsDisplayableManagerHelper2D()
{
  SliceNode = nullptr;
}

//---------------------------------------------------------------------------
vtkMRMLLiverResectionsDisplayableManagerHelper2D::
~vtkMRMLLiverResectionsDisplayableManagerHelper2D()
{

}


//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D::
PrintSelf(ostream &os,
          vtkIndent indent)
{
    this->vtkObject::PrintSelf(os, indent);
}

//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::DisplaySurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node,
                        vtkMRMLSliceNode *sliceNode,
                        vtkRenderer *renderer)

{
  if(node == 0 || renderer == 0)
    {
    return;
    }

  this->SliceNode = sliceNode;

  // Compute the slice normal
  auto sliceToRASMatrix = sliceNode->GetSliceToRAS();
  double slicePlaneNormal[3];
  slicePlaneNormal[0] = sliceToRASMatrix->GetElement(0,2);
  slicePlaneNormal[1] = sliceToRASMatrix->GetElement(1,2);
  slicePlaneNormal[2] = sliceToRASMatrix->GetElement(2,2);

  //Set up the cutter

  vtkSmartPointer<vtkPlane> cutPlane =
    vtkSmartPointer<vtkPlane>::New();
  cutPlane->SetNormal(slicePlaneNormal);

  this->BezierSource = vtkSmartPointer<vtkBezierSurfaceSource>::New();
  this->BezierSource->SetResolution(20,20);
  this->BezierSurfaceControlPoints = vtkSmartPointer<vtkPoints>::New();
  this->BezierSurfaceControlPoints->SetNumberOfPoints(16);
  GetBezierSurfaceControlPoints(node);
  this->BezierSource->SetControlPoints(this->BezierSurfaceControlPoints);
  this->BezierSource->Update();

  this->Cutter = vtkSmartPointer<vtkCutter>::New();
  this->Cutter->SetInputConnection(this->BezierSource->GetOutputPort());
  this->Cutter->SetCutFunction(cutPlane);
  this->Cutter->GenerateValues(1,
                               this->SliceNode->GetSliceOffset(),
                               this->SliceNode->GetSliceOffset());
  this->Cutter->GenerateCutScalarsOff();
  this->Cutter->GenerateTrianglesOn();

  //Set up transformation (3d to 2d)
  this->InvertedRASToXYMatrix = vtkSmartPointer<vtkMatrix4x4>::New();
  this->InvertedRASToXYMatrix->DeepCopy(sliceNode->GetXYToRAS());
  this->InvertedRASToXYMatrix->Invert();
  this->RASToXYTransform = vtkSmartPointer<vtkTransform>::New();
  this->RASToXYTransform->SetMatrix(this->InvertedRASToXYMatrix.GetPointer());

  //Set up transformation filter (3d to 2d)
  auto transformFilter = vtkSmartPointer<vtkTransformPolyDataFilter>::New();
  transformFilter->SetInputConnection(this->Cutter->GetOutputPort());
  transformFilter->SetTransform(this->RASToXYTransform.GetPointer());

  //Set up the color transfer function
  // vtkSmartPointer<vtkColorTransferFunction> colorTable =
  //   vtkSmartPointer<vtkColorTransferFunction>::New();
  // colorTable->AddRGBPoint(0.0, 1.0, 0.0, 0.0);
  // colorTable->AddRGBPoint(node->GetSafetyMargin(), 1.0, 0.0, 0.0);
  // colorTable->AddRGBPoint(node->GetSafetyMargin() + 0.00001, 0.7, 0.7, 1.0);
  // colorTable->AddRGBPoint(100.0, 0.7, 0.7, 1.0);

  //Set up mapper and actor for the contour
  vtkSmartPointer<vtkPolyDataMapper2D> mapper = vtkSmartPointer<vtkPolyDataMapper2D>::New();
  mapper->SetInputConnection(transformFilter->GetOutputPort());
  // mapper->SetLookupTable(colorTable);
  // mapper->ScalarVisibilityOn();
  //mapper->SetScalarModeToUsePointData();
  //mapper->SetColorModeToMapScalars();
  //mapper->SetScalarRange(0,100);

  this->ContourActor = vtkSmartPointer<vtkActor2D>::New();
  this->ContourActor->SetMapper(mapper);
  this->ContourActor->GetProperty()->SetLineWidth(3);
  //actor->GetProperty()->SetLineWidth(2.0);
  renderer->AddActor2D(this->ContourActor.GetPointer());
  std::cout<<"Add actor: "<<this->ContourActor.GetPointer()<<endl;

  this->UpdateCommand = vtkSmartPointer<vtkCallbackCommand>::New();
  this->UpdateCommand->SetCallback(vtkMRMLLiverResectionsDisplayableManagerHelper2D::UpdateSurfaceContour);
  this->UpdateCommand->SetClientData(this);
  sliceNode->AddObserver(vtkCommand::ModifiedEvent, this->UpdateCommand.GetPointer());
}

//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::UpdateSurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node)
{
  GetBezierSurfaceControlPoints(node);
  this->BezierSource->SetControlPoints(this->BezierSurfaceControlPoints);
  this->BezierSource->Update();
}



//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::RemoveSurfaceContour(vtkMRMLMarkupsBezierSurfaceNode *node,
                       vtkRenderer *renderer)
{
  if(!node || !renderer)
    {
    return;
    }

  if (this->SliceNode != nullptr)
    {
    this->Cutter->SetInputData(nullptr);
    this->SliceNode->RemoveObserver(this->UpdateCommand.GetPointer());
    renderer->RemoveActor(this->ContourActor.GetPointer());
    }
}

//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::RemoveAllSurfacesContours(vtkRenderer *renderer,
                            vtkRenderWindowInteractor *interactor)
{
  if(!renderer || !interactor)
    {
    return;
    }
}

//---------------------------------------------------------------------------
void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::UpdateSurfaceContour(vtkObject* vtkNotUsed(object),
                       unsigned long int vtkNotUsed(id),
                       void *clientData,
                       void *vtkNotUsed(callData))
{

  vtkMRMLLiverResectionsDisplayableManagerHelper2D *self =
    static_cast<vtkMRMLLiverResectionsDisplayableManagerHelper2D*>
    (clientData);

  self->InvertedRASToXYMatrix->DeepCopy(self->SliceNode->GetXYToRAS());
  self->InvertedRASToXYMatrix->Invert();
  self->RASToXYTransform->SetMatrix(self->InvertedRASToXYMatrix.GetPointer());
  self->Cutter->GenerateValues(1,
                               self->SliceNode->GetSliceOffset(),
                               self->SliceNode->GetSliceOffset());
}

void vtkMRMLLiverResectionsDisplayableManagerHelper2D
::ChangeSurfaceVisibility(vtkMRMLMarkupsBezierSurfaceNode *node,
                          vtkRenderer *renderer)
{
  if(!node || !renderer)
    {
    return;
    }

  if (node->GetDisplayVisibility())
    {
    this->UpdateCommand->SetCallback(vtkMRMLLiverResectionsDisplayableManagerHelper2D::UpdateSurfaceContour);
    this->UpdateCommand->SetClientData(this);
    this->SliceNode->AddObserver(vtkCommand::ModifiedEvent, this->UpdateCommand.GetPointer());
    renderer->AddActor(this->ContourActor.GetPointer());
    }
  else
    {
    this->SliceNode->RemoveObserver(this->UpdateCommand.GetPointer());
    renderer->RemoveActor(this->ContourActor.GetPointer());
    std::cout<<node->GetID()<<endl;
    std::cout<<"remove actor: "<<this->ContourActor.GetPointer()<<endl;
    }

}

void vtkMRMLLiverResectionsDisplayableManagerHelper2D::GetBezierSurfaceControlPoints(vtkMRMLMarkupsBezierSurfaceNode *node){
  if (!node)
    {
    return;
    }

  if (node->GetNumberOfControlPoints() == 16)
    {
    for (int i = 0; i < 16; i++)
      {
      double point[3];
      node->GetNthControlPointPosition(i, point);
      this->BezierSurfaceControlPoints->SetPoint(i,
                                                 static_cast<float>(point[0]),
                                                 static_cast<float>(point[1]),
                                                 static_cast<float>(point[2]));
      }
    }
}

