/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2018-2026, Oslo University Hospital. All rights reserved.

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

#ifndef vtkopenglresectionbezierpolydatamapper_h_
#define vtkopenglresectionbezierpolydatamapper_h_

#include "vtkSlicerLiverResectionsModuleVTKWidgetsExport.h"

// VTK includes
#include <vtkOpenGLPolyDataMapper.h>
#include <vtkRenderingOpenGL2Module.h>

// STD includes
#include <memory>

class vtkTextureObject;

//-------------------------------------------------------------------------------
class VTK_SLICER_LIVERRESECTIONS_MODULE_VTKWIDGETS_EXPORT vtkOpenGLBezierResectionPolyDataMapper : public vtkOpenGLPolyDataMapper
{
public:
  static vtkOpenGLBezierResectionPolyDataMapper* New();
  vtkTypeMacro(vtkOpenGLBezierResectionPolyDataMapper, vtkOpenGLPolyDataMapper);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  /// Set RAS - IKJ matrix
  void SetRasToIjkMatrix(const vtkMatrix4x4*);
  /// Set RAS - IKJ matrix transposed
  void SetRasToIjkMatrixT(const vtkMatrix4x4*);
  /// Get RAS - IJK matrix transposed
  const vtkMatrix4x4* GetRasToIjkMatrixT() const;

  /// Set IKJ - Texture space matrix
  void SetIjkToTextureMatrix(const vtkMatrix4x4*);
  /// Set IJK - Texture space matrix transposed
  void SetIjkToTextureMatrixT(const vtkMatrix4x4*);
  /// Get IJK - Texture matrixj
  const vtkMatrix4x4* GetIjkToTextureMatrixT() const;

  /// Get the resection margin
  float GetResectionMargin() const;
  /// Set the resection margin
  void SetResectionMargin(float margin);

  /// Get the uncertainty margin
  float GetUncertaintyMargin() const;
  /// Set the resection margin
  void SetUncertaintyMargin(float margin);

  /// Get the interpolated margin
  const float* GetResectionMarginColor() const;
  /// Set the resection margin
  void SetResectionMarginColor(float color[3]);
  /// Set the resection margin
  void SetResectionMarginColor(float red, float green, float blue);

  /// Get the interpolated margin
  const float* GetUncertaintyMarginColor() const;
  /// Set the resection margin
  void SetUncertaintyMarginColor(float color[3]);
  /// Set the resection margin
  void SetUncertaintyMarginColor(float red, float green, float blue);

  /// Get the resection color
  const float* GetResectionColor() const;
  /// Set the resection color
  void SetResectionColor(float color[3]);
  /// Set the resection color
  void SetResectionColor(float red, float green, float blue);

  /// Get the resection grid color
  const float* GetResectionGridColor() const;
  /// Set the resection gird color
  void SetResectionGridColor(float color[3]);
  /// Set the resection grid color
  void SetResectionGridColor(float red, float green, float blue);

  /// Get the uncertainty margin
  float GetResectionOpacity() const;
  /// Set the resection margin
  void SetResectionOpacity(float margin);

  /// Get the interpolated margin
  bool GetResectionClipOut() const;
  /// Set the resection margin
  void SetResectionClipOut(bool interpolated);

  /// Get the interpolated margin
  bool GetInterpolatedMargins() const;
  /// Set the resection margin
  void SetInterpolatedMargins(bool interpolated);

  /// Get the number of divisions for the grid (both u,v directions)
  unsigned int GetGridDivisions() const;
  /// Set the number of divisions for the grid (both u,v directions)
  void SetGridDivisions(unsigned int divisions);

  /// Get thickness factor for the grid
  float GetGridThicknessFactor() const;
  /// Set the thickness factor for the grid
  void SetGridThicknessFactor(float thicknessFactor);

  /// Set the 3D distance-map texture object the fragment shader samples.
  ///
  /// The representation (vtkSlicerBezierSurfaceRepresentation3D) owns the
  /// texture object and threads it here so the mapper can Activate() it at
  /// draw time and bind the ``sampler3D distanceTexture`` uniform to the
  /// unit the texture actually lands on.  Without this the sampler is left
  /// pointing at a texture unit with no live GL_TEXTURE_3D bound on a
  /// subsequent render (the offscreen-render abort root cause; ADR-0003).
  void SetDistanceMapTextureObject(vtkTextureObject* texture);
  /// Get the distance-map texture object set by the representation.
  vtkTextureObject* GetDistanceMapTextureObject() const;

protected:
  vtkOpenGLBezierResectionPolyDataMapper();
  ~vtkOpenGLBezierResectionPolyDataMapper();

  void BuildBufferObjects(vtkRenderer* ren, vtkActor* act) override;

  // Perform string replacements on the shader templates
  void ReplaceShaderValues(std::map<vtkShader::Type, vtkShader*> shaders, vtkRenderer* ren, vtkActor* act) override;

  void SetMapperShaderParameters(vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor) override;

  // Set CameraShaderParameters
  void SetCameraShaderParameters(vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor) override;

  // Deactivate the distance-map texture after the draw so its texture unit
  // is released back to the render window's texture-unit manager — mirrors
  // how the base mapper releases its own textures (ADR-0003).
  void RenderPieceFinish(vtkRenderer* ren, vtkActor* act) override;

private:
  class vtkInternal;
  std::unique_ptr<vtkInternal> Impl;

private:
  vtkOpenGLBezierResectionPolyDataMapper(const vtkOpenGLBezierResectionPolyDataMapper&) = delete;
  void operator=(const vtkOpenGLBezierResectionPolyDataMapper&) = delete;
};

#endif // vtkopenglresectionsurfacepolydatamapper_h_
