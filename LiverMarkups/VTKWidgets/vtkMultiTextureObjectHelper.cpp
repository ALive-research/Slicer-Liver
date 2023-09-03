//
// Created by ruoyan on 06.10.22.
//

#include "vtkMultiTextureObjectHelper.h"
#include "vtk_glew.h"

#include "vtkObjectFactory.h"

#include "vtkNew.h"
#include "vtkOpenGLBufferObject.h"
#include "vtkOpenGLError.h"
#include "vtkOpenGLFramebufferObject.h"
#include "vtkOpenGLRenderWindow.h"
#include "vtkOpenGLResourceFreeCallback.h"
#include "vtkOpenGLShaderCache.h"
#include "vtkOpenGLState.h"
#include "vtkOpenGLTexture.h"
#include "vtkOpenGLVertexArrayObject.h"
#include "vtkPixelBufferObject.h"
#include "vtkRenderer.h"
#include "vtkShaderProgram.h"
#include "vtkOpenGLHelper.h"

#include <cassert>

void vtkMultiTextureObjectHelper::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os, indent);
}
vtkStandardNewMacro(vtkMultiTextureObjectHelper);

bool vtkMultiTextureObjectHelper::CreateSeq2DFromRaw(
  unsigned int width, unsigned int height, int numComps, int dataType, void* data,  int texSeq)
{
  assert(this->Context);

  // Now determine the texture parameters using the arguments.
  this->GetDataType(dataType);
  this->GetInternalFormat(dataType, numComps, false);
  this->GetFormat(dataType, numComps, false);

  if (!this->InternalFormat || !this->Format || !this->Type)
    {
    vtkErrorMacro("Failed to determine texture parameters. IF="
                    << this->InternalFormat << " F=" << this->Format << " T=" << this->Type);
    return false;
    }

  GLenum target = GL_TEXTURE_2D;
  this->Target = target;
  this->Components = numComps;
  this->Width = width;
  this->Height = height;
  this->Depth = 1;
  this->NumberOfDimensions = 2;

  GLint texunit = texSeq;
  this->Context->GetState()->vtkglActiveTexture(GL_TEXTURE0+texunit);
  this->CreateSeqTexture(texSeq);
  this->Bind();

  // Source texture data from the PBO.
  this->Context->GetState()->vtkglPixelStorei(GL_UNPACK_ALIGNMENT, 1);
  glTexStorage2D(GL_TEXTURE_2D, 1, this->InternalFormat, static_cast<GLsizei>(this->Width),
                 static_cast<GLsizei>(this->Height));
  glTexSubImage2D(this->Target, 0,0,0, static_cast<GLsizei>(this->Width),
                  static_cast<GLsizei>(this->Height), this->Format, this->Type,
                  static_cast<const GLvoid*>(data));
  vtkOpenGLCheckErrorMacro("failed at glTexImage2D");

  this->Deactivate();
  return true;
}

bool vtkMultiTextureObjectHelper::CreateSeq3DFromRaw(unsigned int width, unsigned int height, unsigned int depth,
                                                     int numComps, int dataType, void* data, int texSeq) {

  assert(this->Context);
  vtkOpenGLClearErrorMacro();

  // Now, determine texture parameters using the arguments.
  this->GetDataType(dataType);
  this->GetInternalFormat(dataType, numComps, false);
  this->GetFormat(dataType, numComps, false);

  if (!this->InternalFormat || !this->Format || !this->Type)
    {
    vtkErrorMacro("Failed to determine texture parameters.");
    return false;
    }

  this->Target = GL_TEXTURE_3D;
  this->Components = numComps;
  this->Width = width;
  this->Height = height;
  this->Depth = depth;
  this->NumberOfDimensions = 3;

  GLint texunit = texSeq;
  this->Context->GetState()->vtkglActiveTexture(GL_TEXTURE0+texunit);
  this->CreateSeqTexture(texSeq);
  this->Bind();

  // Source texture data from the PBO.
  this->Context->GetState()->vtkglPixelStorei(GL_UNPACK_ALIGNMENT, 1);

  glTexImage3D(this->Target, 0, this->InternalFormat, static_cast<GLsizei>(this->Width),
               static_cast<GLsizei>(this->Height), static_cast<GLsizei>(this->Depth), 0, this->Format,
               this->Type, static_cast<const GLvoid*>(data));

  this->Deactivate();

  return vtkOpenGLCheckErrors("Failed to allocate 3D texture.");
}

void vtkMultiTextureObjectHelper::CreateSeqTexture(int texSeq)
{
  assert(this->Context);

  this->ResourceCallback->RegisterGraphicsResources(this->Context);

  // reuse the existing handle if we have one
  if (!this->Handle)
    {
    GLuint tex = texSeq;
    glGenTextures(1, &tex);
    this->OwnHandle = true;
    vtkOpenGLCheckErrorMacro("failed at glGenTextures");
    this->Handle = tex;

#if defined(GL_TEXTURE_BUFFER)
    if (this->Target && this->Target != GL_TEXTURE_BUFFER)
#else
      if (this->Target)
#endif
      {
      glBindTexture(this->Target, this->Handle);
      vtkOpenGLCheckErrorMacro("failed at glBindTexture");

      // See: http://www.opengl.org/wiki/Common_Mistakes#Creating_a_complete_texture
      // turn off mip map filter or set the base and max level correctly. here
      // both are done.
#ifdef GL_TEXTURE_2D_MULTISAMPLE
      if (this->Target != GL_TEXTURE_2D_MULTISAMPLE)
#endif
        {
        glTexParameteri(this->Target, GL_TEXTURE_MIN_FILTER,
                        this->GetMinificationFilterMode(this->MinificationFilter));
        glTexParameteri(this->Target, GL_TEXTURE_MAG_FILTER,
                        this->GetMagnificationFilterMode(this->MagnificationFilter));

        glTexParameteri(this->Target, GL_TEXTURE_WRAP_S, this->GetWrapSMode(this->WrapS));
        glTexParameteri(this->Target, GL_TEXTURE_WRAP_T, this->GetWrapTMode(this->WrapT));

#if defined(GL_TEXTURE_3D)
        if (this->Target == GL_TEXTURE_3D)
          {
          glTexParameteri(this->Target, GL_TEXTURE_WRAP_R, this->GetWrapRMode(this->WrapR));
          }
#endif
        }

      if (this->Target == GL_TEXTURE_2D) // maybe expand later on
        {
        glTexParameteri(this->Target, GL_TEXTURE_BASE_LEVEL, this->BaseLevel);
        glTexParameteri(this->Target, GL_TEXTURE_MAX_LEVEL, this->MaxLevel);
        }

      glBindTexture(this->Target, 0);
      }
    }
}
