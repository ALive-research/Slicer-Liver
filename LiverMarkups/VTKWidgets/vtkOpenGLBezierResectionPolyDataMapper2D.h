//
// Created by ruoyan on 18.06.22.
//

#ifndef SLICERLIVER_VTKOPENGLBEZIERRESECTIONPOLYDATAMAPPER2D_H
#define SLICERLIVER_VTKOPENGLBEZIERRESECTIONPOLYDATAMAPPER2D_H

// VTK includes
#include <vtkOpenGLPolyDataMapper.h>
#include <vtkRenderingOpenGL2Module.h>

//STD includes
#include <memory>

//-------------------------------------------------------------------------------
class vtkTextureObject;

//-------------------------------------------------------------------------------
class VTKRENDERINGOPENGL2_EXPORT vtkOpenGLBezierResectionPolyDataMapper2D : public vtkOpenGLPolyDataMapper
{
public:
    static vtkOpenGLBezierResectionPolyDataMapper2D *New();
vtkTypeMacro(vtkOpenGLBezierResectionPolyDataMapper2D, vtkOpenGLPolyDataMapper);
    void PrintSelf(ostream& os, vtkIndent indent) override;

    /// Get distance map
    vtkTextureObject* GetDistanceMapTextureObject() const;

    /// Set distance map
    void SetDistanceMapTextureObject(vtkTextureObject* node);

    /// Set RAS - IKJ matrix
    void SetRasToIjkMatrix(const vtkMatrix4x4*);
    /// Set RAS - IKJ matrix transposed
    void SetRasToIjkMatrixT(const vtkMatrix4x4*);
    /// Get RAS - IJK matrix transposed
    vtkMatrix4x4 const* GetRasToIjkMatrixT() const;

    /// Set IKJ - Texture space matrix
    void SetIjkToTextureMatrix(const vtkMatrix4x4*);
    /// Set IJK - Texture space matrix transposed
    void SetIjkToTextureMatrixT(const vtkMatrix4x4*);
    /// Get IJK - Texture matrixj
    vtkMatrix4x4 const* GetIjkToTextureMatrixT() const;

    /// Get the resection margin
    float GetResectionMargin() const;
    /// Set the resection margin
    void SetResectionMargin(float margin);

    /// Get the uncertainty margin
    float GetUncertaintyMargin() const;
    /// Set the resection margin
    void SetUncertaintyMargin(float margin);

    /// Get the interpolated margin
    float const* GetResectionMarginColor() const;
    /// Set the resection margin
    void SetResectionMarginColor(float color[3]);
    /// Set the resection margin
    void SetResectionMarginColor(float red, float green, float blue);

    /// Get the interpolated margin
    float const* GetUncertaintyMarginColor() const;
    /// Set the resection margin
    void SetUncertaintyMarginColor(float color[3]);
    /// Set the resection margin
    void SetUncertaintyMarginColor(float red, float green, float blue);

    /// Get the resection color
    float const* GetResectionColor() const;
    /// Set the resection color
    void SetResectionColor(float color[3]);
    /// Set the resection color
    void SetResectionColor(float red, float green, float blue);

    /// Get the resection grid color
    float const* GetResectionGridColor() const;
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

protected:
    vtkOpenGLBezierResectionPolyDataMapper2D();
    ~vtkOpenGLBezierResectionPolyDataMapper2D();

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
    vtkOpenGLBezierResectionPolyDataMapper2D(const vtkOpenGLBezierResectionPolyDataMapper2D&) = delete;
    void operator=(const vtkOpenGLBezierResectionPolyDataMapper2D&) = delete;
};

#endif //SLICERLIVER_VTKOPENGLBEZIERRESECTIONPOLYDATAMAPPER2D_H
