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

#ifndef vtkopengldistancecontourpolydatamapper_h_
#define vtkopengldistancecontourpolydatamapper_h_

#include "vtkSlicerLiverMarkupsModuleVTKWidgetsExport.h"

// VTK includes
#include <vtkOpenGLPolyDataMapper.h>
#include <vtkRenderingOpenGL2Module.h>

//STD includes
#include <memory>
#include <array>

//-------------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_VTKWIDGETS_EXPORT vtkOpenGLSlicingContourPolyDataMapper : public vtkOpenGLPolyDataMapper
{
public:
  static vtkOpenGLSlicingContourPolyDataMapper *New();
  vtkTypeMacro(vtkOpenGLSlicingContourPolyDataMapper, vtkOpenGLPolyDataMapper);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Get the slicing plane position
  std::array<float, 4> GetPlanePosition() const;

  /// Set the slicing plane position
  void SetPlanePosition(const std::array<float, 4>& planePosition);

  /// Get the slicing plane normal
  std::array<float, 4> GetPlaneNormal() const;

  /// Set the slicing plane normal
  void SetPlaneNormal(const std::array<float, 4>& planeNormal);

  /// Get the contour thickness
  float GetContourThickness() const;

  /// Get the contour thickness
  void SetContourThickness(float contourThickness);

  /// Get the contour visibility
  bool GetContourVisibility() const;

  /// Get the contour visibility
  void SetContourVisibility(bool contourVisibility);

protected:
  vtkOpenGLSlicingContourPolyDataMapper();
  ~vtkOpenGLSlicingContourPolyDataMapper();

  void BuildBufferObjects(vtkRenderer* ren, vtkActor* act) override;

  // Perform string replacements on the shader templates
  void ReplaceShaderValues(std::map<vtkShader::Type, vtkShader*> shaders,
                           vtkRenderer* ren,
                           vtkActor* act) override;

  void SetMapperShaderParameters(vtkOpenGLHelper& cellBO,
                                 vtkRenderer* ren,
                                 vtkActor* actor) override;

  // Set CameraShaderParameters
  void SetCameraShaderParameters(vtkOpenGLHelper& cellBO,
                                 vtkRenderer* ren,
                                 vtkActor* actor) override;
private:
  class vtkInternal;
  std::unique_ptr<vtkInternal> Impl;

private:
  vtkOpenGLSlicingContourPolyDataMapper(const vtkOpenGLSlicingContourPolyDataMapper&) = delete;
  void operator=(const vtkOpenGLSlicingContourPolyDataMapper&) = delete;
};

#endif // vtkopenglresectionsurfacepolydatamapper_h_
