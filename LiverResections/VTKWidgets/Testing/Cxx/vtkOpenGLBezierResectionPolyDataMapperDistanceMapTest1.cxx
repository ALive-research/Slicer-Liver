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

// LiverResections VTKWidgets includes
#include "vtkOpenGLBezierResectionPolyDataMapper.h"

// MRML includes (ctkTest assertion macros)
#include "vtkMRMLCoreTestingMacros.h"

// VTK includes
#include <vtkImageData.h>
#include <vtkNew.h>

// STD includes
#include <iostream>

// ADR-0031 §Conformance — the GL-free half of "the distance-map input reaches
// the mapper".  Pins the SetDistanceMapImageData / GetDistanceMapImageData
// accessor surface: the default no-distance-map state, the image round-trip,
// and that passing nullptr clears both the image and the (lazily built)
// texture so MRML state and GL state cannot diverge (ADR-0003).
//
// The actual GL texture upload (Create3DFromRaw in BuildBufferObjects) needs a
// live render window and is exercised by the interactive :0 eyeball /
// launched-GL pass — OUT OF SCOPE for this no-GL, no-Slicer unit test.

namespace
{

int testDistanceMapImageDefaultState()
{
  vtkNew<vtkOpenGLBezierResectionPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());

  // No distance map by default — the sampler falls back to the
  // no-distance-map path.
  CHECK_NULL(mapper->GetDistanceMapImageData());
  CHECK_NULL(mapper->GetDistanceMapTextureObject());

  return EXIT_SUCCESS;
}

int testDistanceMapImageRoundTripAndClear()
{
  vtkNew<vtkOpenGLBezierResectionPolyDataMapper> mapper;

  vtkNew<vtkImageData> image;
  image->SetDimensions(4, 4, 4);
  image->AllocateScalars(VTK_FLOAT, 1);

  mapper->SetDistanceMapImageData(image.GetPointer());
  CHECK_POINTER(mapper->GetDistanceMapImageData(), image.GetPointer());
  // GL-free: the texture is built only at render, so it stays null here even
  // though the image is set.
  CHECK_NULL(mapper->GetDistanceMapTextureObject());

  // Clearing the image drops both the image and any built texture.
  mapper->SetDistanceMapImageData(nullptr);
  CHECK_NULL(mapper->GetDistanceMapImageData());
  CHECK_NULL(mapper->GetDistanceMapTextureObject());

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkOpenGLBezierResectionPolyDataMapperDistanceMapTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testDistanceMapImageDefaultState());
  CHECK_EXIT_SUCCESS(testDistanceMapImageRoundTripAndClear());

  std::cout << "vtkOpenGLBezierResectionPolyDataMapperDistanceMapTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}
