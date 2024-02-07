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

#ifndef __vtkMRMLLiverResectionsDisplayableManager2D_h
#define __vtkMRMLLiverResectionsDisplayableManager2D_h

// MarkupsModule includes
#include "vtkSlicerLiverResectionsModuleMRMLDisplayableManagerExport.h"

// MarkupsModule/MRMLDisplayableManager includes
#include "vtkMRMLLiverResectionsDisplayableManagerHelper2D.h"

// MRMLDisplayableManager includes
#include <vtkMRMLAbstractSliceViewDisplayableManager.h>

// VTK includes
#include <vtkSlicerMarkupsWidget.h>

//VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

//STD includes
#include <map>
#include <vector>

//-------------------------------------------------------------------------------
class vtkMRMLMarkupsBezierSurfaceNode;
class vtkMRMLLiverResectionsDisplayableManagerHelper2D;
class vtkCollection;

//-------------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_MRMLDISPLAYABLEMANAGER_EXPORT
vtkMRMLLiverResectionsDisplayableManager2D
  :public vtkMRMLAbstractSliceViewDisplayableManager
{
 public:

// Description:
// VTK-specific functions for object creation and class hierarchy
  static vtkMRMLLiverResectionsDisplayableManager2D *New();
 vtkTypeMacro(vtkMRMLLiverResectionsDisplayableManager2D,
              vtkMRMLAbstractSliceViewDisplayableManager);

// Description:
// VTK-specific function for print out information
  void PrintSelf(ostream& os, vtkIndent indent) override;

 protected:

// Description:
// Constructor & destructor
  vtkMRMLLiverResectionsDisplayableManager2D();
  virtual ~vtkMRMLLiverResectionsDisplayableManager2D();


// Description:
// MRML virtual functions
  virtual void SetMRMLSceneInternal(vtkMRMLScene *newScene) override;
  virtual void ProcessMRMLNodesEvents(vtkObject *caller, unsigned long event, void *callData) override;
  virtual void OnMRMLSceneNodeAdded(vtkMRMLNode *node) override;
  virtual void OnMRMLNodeModified(vtkMRMLNode *node) override;
  virtual void OnMRMLSceneNodeRemoved(vtkMRMLNode *node) override;
  virtual void OnMRMLSceneEndClose() override;

 protected:

// Description:
// Copy constructor and assignment operator
  vtkMRMLLiverResectionsDisplayableManager2D(const vtkMRMLLiverResectionsDisplayableManager2D&);
//Not implemented
  void operator=(const vtkMRMLLiverResectionsDisplayableManager2D&);
//Not implemented


// Description:
// Map relating resection nodes with helpers
  std::map<char*, vtkSmartPointer<vtkMRMLLiverResectionsDisplayableManagerHelper2D>> ResectionNodeHelperMap;
// Description:
// Deferred nodes
  vtkNew<vtkCollection> DeferredNodes;

  static void AddDeferredNodes(vtkObject *caller, unsigned long event, void *clientData, void *callData);

};

#endif
