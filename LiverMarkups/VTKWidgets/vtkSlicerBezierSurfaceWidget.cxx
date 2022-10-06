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

#include "vtkSlicerBezierSurfaceWidget.h"

// Liver Markups VTKWidgets include
#include "vtkMRMLMarkupsSlicingContourNode.h"
#include "vtkSlicerBezierSurfaceRepresentation3D.h"

// VTK includes
#include <vtkObjectFactory.h>

// Markups VTKWidgets includes
#include <vtkSlicerLineRepresentation2D.h>

// MRML includes
#include <vtkMRMLMarkupsBezierSurfaceNode.h>

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkSlicerBezierSurfaceWidget);

//------------------------------------------------------------------------------
vtkSlicerBezierSurfaceWidget::vtkSlicerBezierSurfaceWidget()
{

}

//------------------------------------------------------------------------------
vtkSlicerBezierSurfaceWidget::~vtkSlicerBezierSurfaceWidget() = default;

//------------------------------------------------------------------------------
void vtkSlicerBezierSurfaceWidget::CreateDefaultRepresentation(vtkMRMLMarkupsDisplayNode* markupsDisplayNode,
                                                                vtkMRMLAbstractViewNode* viewNode,
                                                                vtkRenderer* renderer)
{
  vtkSmartPointer<vtkSlicerMarkupsWidgetRepresentation> rep = nullptr;
  if (vtkMRMLSliceNode::SafeDownCast(viewNode))
    {
    rep = vtkSmartPointer<vtkSlicerLineRepresentation2D>::New();
    }
  else
    {
    rep = vtkSmartPointer<vtkSlicerBezierSurfaceRepresentation3D>::New();
    rep->Print(std::cout);
    }
  this->SetRenderer(renderer);
  this->SetRepresentation(rep);
  rep->SetViewNode(viewNode);
  rep->SetMarkupsDisplayNode(markupsDisplayNode);
  rep->UpdateFromMRML(nullptr, 0); // full update
}

//------------------------------------------------------------------------------
vtkSlicerMarkupsWidget* vtkSlicerBezierSurfaceWidget::CreateInstance() const
{
  vtkObject* ret = vtkObjectFactory::CreateInstance("vtkSlcierBezierSurfaceWidget");
  if(ret)
    {
    return static_cast<vtkSlicerBezierSurfaceWidget*>(ret);
    }

  vtkSlicerBezierSurfaceWidget* result = new vtkSlicerBezierSurfaceWidget;
#ifdef VTK_HAS_INITIALIZE_OBJECT_BASE
  result->InitializeObjectBase();
#endif
  return result;
}

//------------------------------------------------------------------------------
bool vtkSlicerBezierSurfaceWidget::ProcessInteractionEvent(vtkMRMLInteractionEventData* eventData)
{
  auto markupsNode = this->GetMarkupsNode();

  unsigned long widgetEvent = this->TranslateInteractionEventToWidgetEvent(eventData);

  bool processedEvent = false;
  switch (widgetEvent)
  {
  case WidgetEventControlPointMoveStart:
    this->SetWidgetState(WidgetStateTranslateControlPoint);
    this->StartWidgetInteraction(eventData);
    markupsNode->InvokeEvent(vtkCommand::StartInteractionEvent);
    processedEvent = true;
    break;

  case WidgetEventMouseMove:
    processedEvent = Superclass::ProcessMouseMove(eventData);
    break;

  case WidgetEventControlPointMoveEnd:
    this->EndWidgetInteraction();
    this->SetWidgetState(WidgetStateOnWidget);
    markupsNode->InvokeEvent(vtkCommand::EndInteractionEvent);
    processedEvent = true;
    break;
  }

  if (!processedEvent)
    {
    processedEvent = Superclass::ProcessInteractionEvent(eventData);
    }

  return processedEvent;
}

//----------------------------------------------------------------------
vtkMRMLMarkupsBezierSurfaceNode* vtkSlicerBezierSurfaceWidget::GetMRMLMarkupsNode()
{
  auto representation = this->GetMarkupsRepresentation();
  if (!representation)
    {
    return nullptr;
    }

  return vtkMRMLMarkupsBezierSurfaceNode::SafeDownCast(representation->GetMarkupsNode());
}
