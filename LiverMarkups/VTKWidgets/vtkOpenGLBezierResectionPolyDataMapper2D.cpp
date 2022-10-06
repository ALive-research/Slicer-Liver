//
// Created by ruoyan on 18.06.22.
//

#include "vtkOpenGLBezierResectionPolyDataMapper2D.h"
// This module VTK includes

// VTK includes
#include <vtkCellData.h>
#include <vtkFloatArray.h>
#include <vtkImageData.h>
#include <vtkMatrix4x4.h>
#include <vtkObjectFactory.h>
#include <vtkOpenGLError.h>
#include <vtkOpenGLRenderWindow.h>
#include <vtkOpenGLVertexBufferObject.h>
#include <vtkOpenGLVertexBufferObjectGroup.h>
#include <vtkPointData.h>
#include <vtkPolyData.h>
#include <vtkProperty.h>
#include <vtkRenderer.h>
#include <vtkSmartPointer.h>
#include <vtkShaderProgram.h>
#include <vtkTextureObject.h>
#include <vtkTransform.h>
#include "vtkOpenGLCamera.h"
#include "vtkOpenGLActor.h"

//------------------------------------------------------------------------------
class vtkOpenGLBezierResectionPolyDataMapper2D::vtkInternal
{
public:
    vtkInternal(vtkOpenGLBezierResectionPolyDataMapper2D* parent)
            : Parent(parent), DistanceMapTextureObject(nullptr),
              RasToIjkMatrixT(nullptr), IjkToTextureMatrixT(nullptr),
              ResectionMargin(0.0f), UncertaintyMargin(0.0f),
              ResectionMarginColor{1.0f, 0.0f, 0.0f},
              UncertaintyMarginColor{1.0f, 1.0f, 0.0f},
              ResectionColor{1.0f,1.0f, 1.0f},
              ResectionGridColor{0.0f,0.0f, 0.0f},
              ResectionOpacity(1.0f),
              InterpolatedMargins(false), ResectionClipOut(false)
    {
        this->RasToIjkMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
        this->IjkToTextureMatrixT = vtkSmartPointer<vtkMatrix4x4>::New();
    }

    vtkWeakPointer<vtkOpenGLBezierResectionPolyDataMapper2D> Parent;
    vtkSmartPointer<vtkTextureObject> DistanceMapTextureObject;
    vtkSmartPointer<vtkMatrix4x4> RasToIjkMatrixT;
    vtkSmartPointer<vtkMatrix4x4> IjkToTextureMatrixT;
    float ResectionMargin;
    float UncertaintyMargin;
    float ResectionMarginColor[3];
    float UncertaintyMarginColor[3];
    float ResectionColor[3];
    float ResectionGridColor[3];
    float ResectionOpacity;
    bool  InterpolatedMargins;
    bool  ResectionClipOut;
    unsigned int GridDivisions;
    float GridThicknessFactor;
};

//------------------------------------------------------------------------------
vtkStandardNewMacro(vtkOpenGLBezierResectionPolyDataMapper2D);


//------------------------------------------------------------------------------
vtkOpenGLBezierResectionPolyDataMapper2D::vtkOpenGLBezierResectionPolyDataMapper2D()
        :Impl(nullptr)
{
    this->Impl = std::make_unique<vtkInternal>(this);
}

//------------------------------------------------------------------------------
vtkOpenGLBezierResectionPolyDataMapper2D::~vtkOpenGLBezierResectionPolyDataMapper2D(){}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::PrintSelf(ostream& os, vtkIndent indent)
{
    Superclass::PrintSelf(os, indent);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::BuildBufferObjects(vtkRenderer* ren, vtkActor* act)
{

    if (this->CurrentInput && this->HaveTCoords(this->CurrentInput))
    {
        auto renWin = vtkOpenGLRenderWindow::SafeDownCast(ren->GetRenderWindow());
        vtkOpenGLVertexBufferObjectCache* cache = renWin->GetVBOCache();
        auto tcoords = this->CurrentInput->GetPointData()->GetTCoords();
        this->VBOs->CacheDataArray("uvCoords", tcoords, cache, VTK_FLOAT);
        if(this->CurrentInput->GetPointData()->GetArray("BSPlanePoints")){
            auto vertexMC2D = this->CurrentInput->GetPointData()->GetArray("BSPlanePoints");
            this->VBOs->CacheDataArray("vertexMC2D", vertexMC2D, cache, VTK_FLOAT);
        }
    }
    Superclass::BuildBufferObjects(ren, act);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::ReplaceShaderValues(
        std::map<vtkShader::Type, vtkShader*> shaders, vtkRenderer* ren, vtkActor* actor)
{
    std::string VSSource = shaders[vtkShader::Vertex]->GetSource();
    std::string FSSource = shaders[vtkShader::Fragment]->GetSource();
    vtkShaderProgram::Substitute(
            VSSource, "//VTK::PositionVC::Dec",
            "//VTK::PositionVC::Dec\n"
            "out vec4 vertexMCVSOutput;\n"
            "out vec4 vertexWCVSOutput;\n"
            "in vec2 uvCoords;\n"
            "out vec2 uvCoordsOutput;\n"
            "uniform mat4 MCDCMatrix2d;\n"
            "uniform mat4 uShiftScale;\n"
            "uniform mat4 uRasToIjk;\n"
            "uniform mat4 uIjkToTexture;\n"
            "in vec4 vertexMC2D;\n");

    vtkShaderProgram::Substitute(
            VSSource, "//VTK::PositionVC::Impl",
            "//VTK::PositionVC::Impl\n"
            "vertexMCVSOutput = vertexMC;\n"
            "uvCoordsOutput = uvCoords;\n"
            "vertexWCVSOutput = uIjkToTexture*uRasToIjk*uShiftScale*vertexMC;\n"
            "vertexVCVSOutput = MCVCMatrix * vertexMC2D;\n"
            "mat4 m = mat4(1.0);\n"
            "gl_Position = MCDCMatrix2d *m* vertexMC2D;\n");

    vtkShaderProgram::Substitute(
            FSSource, "//VTK::PositionVC::Dec",
            "//VTK::PositionVC::Dec\n"
            "#define M_PI 3.1415926535897932384626433832795\n"
            "uniform sampler3D distanceTexture;\n");

    vtkShaderProgram::Substitute(
            FSSource, "//VTK::Color::Dec",
            "//VTK::Color::Dec\n"
            "uniform float uResectionMargin;\n"
            "uniform float uUncertaintyMargin;\n"
            "uniform float uResectionOpacity;\n"
            "uniform vec3 uResectionMarginColor;\n"
            "uniform vec3 uUncertaintyMarginColor;\n"
            "uniform vec3 uResectionColor;\n"
            "uniform vec3 uResectionGridColor;\n"
            "uniform int uResectionClipOut;\n"
            "uniform int uInterpolatedMargins;\n"
            "uniform int uGridDivisions;\n"
            "uniform float uGridThickness;\n"
            "in vec2 uvCoordsOutput;\n"
            "in vec4 vertexWCVSOutput;\n"
            "vec4 fragPositionMC = vertexWCVSOutput;\n");

    vtkShaderProgram::Substitute(
            FSSource, "//VTK::Color::Impl",
            "//VTK::Color::Impl\n"
            "vec4 dist = texture(distanceTexture, fragPositionMC.xyz);\n"
            "float lowMargin = uResectionMargin - uUncertaintyMargin;\n"
            "float highMargin = uResectionMargin + uUncertaintyMargin;\n"
            "if(uResectionClipOut == 1 && dist[1] > 2.0){\n"
            "  discard;\n"
            "}\n"
            "if(tan(uvCoordsOutput.x*M_PI*uGridDivisions)>10.0-uGridThickness || tan(uvCoordsOutput.y*M_PI*uGridDivisions)>10.0-uGridThickness){\n"
            "   ambientColor = uResectionGridColor;\n"
            "   diffuseColor = vec3(0.0);\n"
            "}\n"
            "else{\n"
            "  if(dist[0] < lowMargin){\n"
            "    ambientColor = uResectionMarginColor;\n"
            "    diffuseColor = vec3(0.0);\n"
            "  }\n"
            "  else if(dist[0] < highMargin-(highMargin-lowMargin)*0.1){\n"
            "    if(uInterpolatedMargins == 0){\n"
            "     ambientColor = uUncertaintyMarginColor;\n"
            "     diffuseColor = vec3(0.0);\n"
            "    }\n"
            "    else{\n"
            "     ambientColor = mix(uResectionMarginColor, uUncertaintyMarginColor, "
            "     (dist[0]-lowMargin)/(highMargin-lowMargin));\n"
            "     ambientColor = ambientColor;\n"
            "     diffuseColor = vec3(0.0);\n"
            "    }\n"
            "  }\n"
            "  else if(dist[0] < highMargin){\n"
            "   ambientColor = vec3(0.0);\n"
            "   diffuseColor = vec3(0.0);\n"
            "  }\n"
            "  else{\n"
            "    ambientColor = uResectionColor;\n"
            "    diffuseColor = vec3(0.6);\n"
            "  }\n"
            "}\n");

    vtkShaderProgram::Substitute(
            FSSource, "//VTK::Light::Impl",
            "//VTK::Light::Impl\n"
            "fragOutput0 = vec4(ambientColor+vec3(uvCoordsOutput,0.0)*0.00001  + diffuse + specular, uResectionOpacity);\n");


    shaders[vtkShader::Vertex]->SetSource(VSSource);
    shaders[vtkShader::Fragment]->SetSource(FSSource);
    Superclass::ReplaceShaderValues(shaders, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetCameraShaderParameters(
        vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor)
{
    vtkOpenGLVertexBufferObject* vvbo = this->VBOs->GetVBO("vertexMC");

    // TODO: maybe cache this?
    auto transform = vtkSmartPointer<vtkTransform>::New();
    transform->Identity();
    auto transformMatrix = vtkSmartPointer<vtkMatrix4x4>::New();

    if (vvbo && vvbo->GetCoordShiftAndScaleEnabled())
    {
        auto shift = vvbo->GetShift();
        auto scale = vvbo->GetScale();
        transform->Translate(shift[0], shift[1], shift[2]);
        transform->Scale(1.0/scale[0], 1.0/scale[1], 1.0/scale[2]);
        transform->GetTranspose(transformMatrix);
    }

    if (cellBO.Program->IsUniformUsed("uShiftScale"))
    {
        cellBO.Program->SetUniformMatrix("uShiftScale", transformMatrix);
    }

    //----------------------------------
    TempMatrix4 = vtkMatrix4x4::New();
    vtkOpenGLCamera* cam = (vtkOpenGLCamera*)(ren->GetActiveCamera());
    vtkMatrix4x4* wcdc;
    vtkMatrix4x4* wcvc;
    vtkMatrix3x3* norms;
    vtkMatrix4x4* vcdc;
    cam->GetKeyMatrices(ren, wcvc, norms, vcdc, wcdc);

    vtkOpenGLVertexBufferObject* vvbo2d = this->VBOs->GetVBO("vertexMC2D");

    auto transform2D = vtkSmartPointer<vtkTransform>::New();
    transform2D->Identity();
    auto transformMatrix2D = vtkSmartPointer<vtkMatrix4x4>::New();

    if (vvbo2d && vvbo2d->GetCoordShiftAndScaleEnabled())
    {
        auto shift = vvbo2d->GetShift();
        auto scale = vvbo2d->GetScale();
        transform2D->Translate(shift[0], shift[1], shift[2]);
        transform2D->Scale(1.0/scale[0], 1.0/scale[1], 1.0/scale[2]);
        transform2D->GetTranspose(transformMatrix2D);

        if (!actor->GetIsIdentity()){
            vtkMatrix4x4* mcwc;
            vtkMatrix3x3* anorms;
            static_cast<vtkOpenGLActor*>(actor)->GetKeyMatrices(mcwc, anorms);
            vtkMatrix4x4::Multiply4x4(transformMatrix2D, mcwc, TempMatrix4);
            vtkMatrix4x4::Multiply4x4(TempMatrix4, wcdc, TempMatrix4);
            cellBO.Program->SetUniformMatrix("MCDCMatrix2d", TempMatrix4);
        }else{
            vtkMatrix4x4::Multiply4x4(transformMatrix2D, wcdc, TempMatrix4);
            cellBO.Program->SetUniformMatrix("MCDCMatrix2d", TempMatrix4);
        }
    }



    Superclass::SetCameraShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetMapperShaderParameters(
        vtkOpenGLHelper& cellBO, vtkRenderer* ren, vtkActor* actor)
{


    if (cellBO.Program->IsUniformUsed("uRasToIjk"))
    {
        cellBO.Program->SetUniformMatrix("uRasToIjk", this->Impl->RasToIjkMatrixT);
    }

    if (cellBO.Program->IsUniformUsed("uIjkToTexture"))
    {
        cellBO.Program->SetUniformMatrix("uIjkToTexture", this->Impl->IjkToTextureMatrixT);
    }

    if (cellBO.Program->IsUniformUsed("uResectionMargin"))
    {
        cellBO.Program->SetUniformf("uResectionMargin", this->Impl->ResectionMargin);
    }

    if (cellBO.Program->IsUniformUsed("uUncertaintyMargin"))
    {
        cellBO.Program->SetUniformf("uUncertaintyMargin", this->Impl->UncertaintyMargin);
    }

    if (cellBO.Program->IsUniformUsed("uInterpolatedMargins"))
    {
        cellBO.Program->SetUniformi("uInterpolatedMargins", this->Impl->InterpolatedMargins);
    }

    if (cellBO.Program->IsUniformUsed("uResectionMarginColor"))
    {
        cellBO.Program->SetUniform3f("uResectionMarginColor", this->Impl->ResectionMarginColor);
    }

    if (cellBO.Program->IsUniformUsed("uUncertaintyMarginColor"))
    {
        cellBO.Program->SetUniform3f("uUncertaintyMarginColor", this->Impl->UncertaintyMarginColor);
    }

    if (cellBO.Program->IsUniformUsed("uResectionColor"))
    {
        cellBO.Program->SetUniform3f("uResectionColor", this->Impl->ResectionColor);
    }

    if (cellBO.Program->IsUniformUsed("uResectionGridColor"))
    {
        cellBO.Program->SetUniform3f("uResectionGridColor", this->Impl->ResectionGridColor);
    }

    if (cellBO.Program->IsUniformUsed("uResectionOpacity"))
    {
        cellBO.Program->SetUniformf("uResectionOpacity", this->Impl->ResectionOpacity);
    }

    if (cellBO.Program->IsUniformUsed("uResectionClipOut"))
    {
        cellBO.Program->SetUniformi("uResectionClipOut", this->Impl->ResectionClipOut);
    }

    if (cellBO.Program->IsUniformUsed("uGridDivisions"))
    {
        cellBO.Program->SetUniformi("uGridDivisions", this->Impl->GridDivisions);
    }

    if (cellBO.Program->IsUniformUsed("uGridThickness"))
    {
        cellBO.Program->SetUniformf("uGridThickness", this->Impl->GridThicknessFactor);
    }

    Superclass::SetMapperShaderParameters(cellBO, ren, actor);
}

//------------------------------------------------------------------------------
vtkTextureObject* vtkOpenGLBezierResectionPolyDataMapper2D::GetDistanceMapTextureObject() const
{
    return this->Impl->DistanceMapTextureObject;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetDistanceMapTextureObject(vtkTextureObject* object)
{
    if (this->Impl->DistanceMapTextureObject == object)
    {
        return;
    }

    this->Impl->DistanceMapTextureObject = object;
    if (object)
    {
        object->Register(this);
    }

    this->Modified();
}

//------------------------------------------------------------------------------
vtkMatrix4x4 const* vtkOpenGLBezierResectionPolyDataMapper2D::GetRasToIjkMatrixT() const
{
    return this->Impl->RasToIjkMatrixT;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetRasToIjkMatrixT(const vtkMatrix4x4* matrix)
{
    if (matrix == nullptr)
    {
        return;
    }

    this->Impl->RasToIjkMatrixT->DeepCopy(matrix);
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetRasToIjkMatrix(const vtkMatrix4x4* matrix)
{
    if (matrix == nullptr)
    {
        return;
    }

    this->Impl->RasToIjkMatrixT->DeepCopy(matrix);
    this->Impl->RasToIjkMatrixT->Transpose();
    this->Modified();
}

//------------------------------------------------------------------------------
vtkMatrix4x4 const* vtkOpenGLBezierResectionPolyDataMapper2D::GetIjkToTextureMatrixT() const
{
    return this->Impl->IjkToTextureMatrixT;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetIjkToTextureMatrixT(const vtkMatrix4x4* matrix)
{
    if (matrix == nullptr)
    {
        return;
    }

    this->Impl->IjkToTextureMatrixT->DeepCopy(matrix);
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetIjkToTextureMatrix(const vtkMatrix4x4* matrix)
{
    if (matrix == nullptr)
    {
        return;
    }

    this->Impl->IjkToTextureMatrixT->DeepCopy(matrix);
    this->Impl->IjkToTextureMatrixT->Transpose();
    this->Modified();
}
//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionMargin() const
{
    return this->Impl->ResectionMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionMargin(float margin)
{
    this->Impl->ResectionMargin = margin;
    this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper2D::GetUncertaintyMargin() const
{
    return this->Impl->UncertaintyMargin;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetUncertaintyMargin(float margin)
{
    this->Impl->UncertaintyMargin = margin;
    this->Modified();
}


//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionMarginColor() const
{
    return this->Impl->ResectionMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionMarginColor(float color[3])
{
    this->Impl->ResectionMarginColor[0] = color[0];
    this->Impl->ResectionMarginColor[1] = color[1];
    this->Impl->ResectionMarginColor[2] = color[2];
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionMarginColor(float red, float green, float blue)
{
    this->Impl->ResectionMarginColor[0] = red;
    this->Impl->ResectionMarginColor[1] = green;
    this->Impl->ResectionMarginColor[2] = blue;
    this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper2D::GetUncertaintyMarginColor() const
{
    return this->Impl->UncertaintyMarginColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetUncertaintyMarginColor(float color[3])
{
    this->Impl->UncertaintyMarginColor[0] = color[0];
    this->Impl->UncertaintyMarginColor[1] = color[1];
    this->Impl->UncertaintyMarginColor[2] = color[2];
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetUncertaintyMarginColor(float red, float green, float blue)
{
    this->Impl->UncertaintyMarginColor[0] = red;
    this->Impl->UncertaintyMarginColor[1] = green;
    this->Impl->UncertaintyMarginColor[2] = blue;
    this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionColor() const
{
    return this->Impl->ResectionColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionColor(float color[3])
{
    this->Impl->ResectionColor[0] = color[0];
    this->Impl->ResectionColor[1] = color[1];
    this->Impl->ResectionColor[2] = color[2];
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionColor(float red, float green, float blue)
{
    this->Impl->ResectionColor[0] = red;
    this->Impl->ResectionColor[1] = green;
    this->Impl->ResectionColor[2] = blue;
    this->Modified();
}

//------------------------------------------------------------------------------
float const* vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionGridColor() const
{
    return this->Impl->ResectionGridColor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionGridColor(float color[3])
{
    this->Impl->ResectionGridColor[0] = color[0];
    this->Impl->ResectionGridColor[1] = color[1];
    this->Impl->ResectionGridColor[2] = color[2];
    this->Modified();
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionGridColor(float red, float green, float blue)
{
    this->Impl->ResectionGridColor[0] = red;
    this->Impl->ResectionGridColor[1] = green;
    this->Impl->ResectionGridColor[2] = blue;
    this->Modified();
}


//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionOpacity() const
{
    return this->Impl->ResectionOpacity;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionOpacity(float margin)
{
    this->Impl->ResectionOpacity = margin;
    this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLBezierResectionPolyDataMapper2D::GetResectionClipOut() const
{
    return this->Impl->ResectionClipOut;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetResectionClipOut(bool clipOut)
{
    this->Impl->ResectionClipOut = clipOut;
    this->Modified();
}

//------------------------------------------------------------------------------
bool vtkOpenGLBezierResectionPolyDataMapper2D::GetInterpolatedMargins() const
{
    return this->Impl->InterpolatedMargins;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetInterpolatedMargins(bool clipOut)
{
    this->Impl->InterpolatedMargins = clipOut;
    this->Modified();
}

//------------------------------------------------------------------------------
unsigned int vtkOpenGLBezierResectionPolyDataMapper2D::GetGridDivisions() const
{
    return this->Impl->GridDivisions;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetGridDivisions(unsigned int divisions)
{
    this->Impl->GridDivisions = divisions;
    this->Modified();
}

//------------------------------------------------------------------------------
float vtkOpenGLBezierResectionPolyDataMapper2D::GetGridThicknessFactor() const
{
    return this->Impl->GridThicknessFactor;
}

//------------------------------------------------------------------------------
void vtkOpenGLBezierResectionPolyDataMapper2D::SetGridThicknessFactor(float thickness)
{
    this->Impl->GridThicknessFactor = thickness;
    this->Modified();
}