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
#include <vtkNew.h>

// STD includes
#include <iostream>

// ADR-0025 §Conformance — the GL-free half of "the chain delivers the
// world point to the mapper as uLocatorPosition".  This pins the locator
// shader-uniform accessor surface on vtkOpenGLBezierResectionPolyDataMapper:
// the default off state (LocatorRadius == 0, LocatorPosition == origin) and
// the round-trip of a RAS world point + radius through the public setters.
//
// The GLSL marker rendering itself (uLocatorRadius > 0 draws a white
// sphere at uLocatorPosition) is GPU/visual-regression and is OUT OF SCOPE
// for this no-GL, no-Slicer unit test.

namespace
{

int testLocatorUniformAccessorsDefaultOffState()
{
  vtkNew<vtkOpenGLBezierResectionPolyDataMapper> mapper;
  CHECK_NOT_NULL(mapper.GetPointer());

  // Off state: radius 0 means no marker drawn (ADR-0025).
  CHECK_DOUBLE(mapper->GetLocatorRadius(), 0.0);

  const float* position = mapper->GetLocatorPosition();
  CHECK_NOT_NULL(position);
  CHECK_DOUBLE(position[0], 0.0);
  CHECK_DOUBLE(position[1], 0.0);
  CHECK_DOUBLE(position[2], 0.0);

  return EXIT_SUCCESS;
}

int testLocatorUniformAccessorsRoundTrip()
{
  vtkNew<vtkOpenGLBezierResectionPolyDataMapper> mapper;

  mapper->SetLocatorPosition(1.5f, -2.5f, 3.0f);
  mapper->SetLocatorRadius(4.0f);

  const float* position = mapper->GetLocatorPosition();
  CHECK_NOT_NULL(position);
  CHECK_DOUBLE(position[0], 1.5);
  CHECK_DOUBLE(position[1], -2.5);
  CHECK_DOUBLE(position[2], 3.0);

  CHECK_DOUBLE(mapper->GetLocatorRadius(), 4.0);

  // The array setter overload must agree with the scalar one.
  float other[3] = { -1.0f, 0.25f, 7.0f };
  mapper->SetLocatorPosition(other);
  const float* position2 = mapper->GetLocatorPosition();
  CHECK_DOUBLE(position2[0], -1.0);
  CHECK_DOUBLE(position2[1], 0.25);
  CHECK_DOUBLE(position2[2], 7.0);

  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkOpenGLBezierResectionPolyDataMapperLocatorTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testLocatorUniformAccessorsDefaultOffState());
  CHECK_EXIT_SUCCESS(testLocatorUniformAccessorsRoundTrip());

  std::cout << "vtkOpenGLBezierResectionPolyDataMapperLocatorTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}
