//
// Created by ruoyan on 06.10.22.
//

#ifndef SLICERLIVER_VTKMULTITEXTUREOBJECTHELPER_H
#define SLICERLIVER_VTKMULTITEXTUREOBJECTHELPER_H

// VTK includes
#include <vtkTextureObject.h>

class vtkOpenGLHelper;

class VTKRENDERINGOPENGL2_EXPORT vtkMultiTextureObjectHelper : public vtkTextureObject {
 public:
  static vtkMultiTextureObjectHelper* New();
 vtkTypeMacro(vtkMultiTextureObjectHelper, vtkTextureObject);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  bool CreateSeq3DFromRaw(unsigned int width, unsigned int height, unsigned int depth,
                          int numComps, int dataType, void* data, int texSeq=0);
  bool CreateSeq2DFromRaw(unsigned int width, unsigned int height, int numComps, int dataType, void* data,  int texSeq);

  void CreateSeqTexture(int texSeq=0);

};

#endif //SLICERLIVER_VTKMULTITEXTUREOBJECTHELPER_H
