/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2021-2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

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

==============================================================================*/

// Pins that the liver segment is resolved by its SNOMED-CT structure tag
// (ADR-0011 liver code 10200004), NOT by the segment name "liver" -- so the
// canonical segmentation Stage 2 produces (SCT-tagged, arbitrary segment names)
// feeds Stage 3.  A decoy segment literally named "liver" but WITHOUT the SCT
// tag must be ignored; the SCT-tagged segment (differently named) must win.

#include "vtkSlicerVascularTerritoriesLogic.h"

#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"
#include <vtkMRMLSegmentationNode.h>

#include <vtkNew.h>
#include <vtkSegmentation.h>
#include <vtkSegment.h>
#include <vtkOrientedImageData.h>

#include <string>

namespace
{
// A TerminologyEntry tag whose type triple carries the SCT liver code, in the
// shape LiverSegmentation.tagSegmentWithSct writes (SCT^<code>^<meaning>).
const char* LIVER_TERMINOLOGY_TAG = "Segmentation category and type - DICOM master list"
                                    "~SCT^85756007^Tissue"
                                    "~SCT^10200004^Liver"
                                    "~^^~Anatomic codes - DICOM master list~^^~^^";
} // namespace

int vtkSlicerVascularTerritoriesLogicLiverSegmentIdTest(int vtkNotUsed(argc), char* vtkNotUsed(argv)[])
{
  vtkNew<vtkSlicerVascularTerritoriesLogic> logic;

  // Null input is a no-op returning an empty id (not a crash).
  CHECK_STD_STRING(logic->GetLiverSegmentId(nullptr), "");

  vtkNew<vtkMRMLScene> scene;
  vtkNew<vtkMRMLSegmentationNode> segmentationNode;
  scene->AddNode(segmentationNode);
  vtkSegmentation* segmentation = segmentationNode->GetSegmentation();
  const std::string masterRep = "Binary labelmap";
  segmentation->SetSourceRepresentationName(masterRep);

  // Each segment carries a minimal binary-labelmap representation so AddSegment
  // need not construct one (GetLiverSegmentId reads only names + tags, but the
  // test-driver's error-output check trips on a construction ERR).
  vtkNew<vtkOrientedImageData> decoyLabelmap;
  decoyLabelmap->SetExtent(0, 1, 0, 1, 0, 1);
  decoyLabelmap->AllocateScalars(VTK_UNSIGNED_CHAR, 1);
  vtkNew<vtkSegment> decoy;
  decoy->SetName("liver"); // named "liver" but NO SCT tag -- the old name lookup's trap
  decoy->AddRepresentation(masterRep, decoyLabelmap);
  segmentation->AddSegment(decoy, "decoy");

  vtkNew<vtkOrientedImageData> liverLabelmap;
  liverLabelmap->SetExtent(0, 1, 0, 1, 0, 1);
  liverLabelmap->AllocateScalars(VTK_UNSIGNED_CHAR, 1);
  vtkNew<vtkSegment> liver;
  liver->SetName("Segment_1"); // a DIFFERENT name, carrying the SCT liver tag
  liver->AddRepresentation(masterRep, liverLabelmap);
  liver->SetTag("TerminologyEntry", LIVER_TERMINOLOGY_TAG);
  segmentation->AddSegment(liver, "parenchyma");

  const std::string decoyId = "decoy";
  const std::string liverId = "parenchyma";
  const std::string resolved = logic->GetLiverSegmentId(segmentationNode);
  CHECK_STD_STRING(resolved, liverId);
  CHECK_BOOL(resolved == decoyId, false);

  return EXIT_SUCCESS;
}
