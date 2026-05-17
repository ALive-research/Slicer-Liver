/*==============================================================================

 Distributed under the OSI-approved BSD 3-Clause License.

  Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.

  Tests for vtkMRMLLiverBezierSurfaceDisplayableManager3D — the C++
  displayable manager landed by T2.6-DM (ADR-0014 §3).  Per ADR-0008 §2
  these are ctkTest-driver tests: no Slicer launch, no Qt, no real
  view, no interactor binding (the DM constructs widgets headlessly;
  SetInteractor is only invoked if the renderer + interactor are
  non-null, which they are not in this headless harness).

  Coverage:

   - NodeAdded spawn: adding a vtkMRMLBezierSurfaceNode causes the DM
     registry to gain exactly one entry.
   - NodeRemoved teardown: removing the node empties the registry.
   - Scene swap rebuild: clearing the scene + re-importing rebuilds
     the registry (OnMRMLSceneEndImport reconcile path).
   - Multiple nodes: adding three nodes yields three registry entries.

==============================================================================*/

// LiverResections MRMLDM includes
#include "vtkMRMLLiverBezierSurfaceDisplayableManager3D.h"

// LiverResections VTKWidgets includes
#include "vtkLiverBezierWidget.h"

// LiverResections MRML includes
#include "vtkMRMLBezierSurfaceNode.h"

// MRML includes
#include "vtkMRMLCoreTestingMacros.h"
#include "vtkMRMLScene.h"

// VTK includes
#include <vtkNew.h>
#include <vtkSmartPointer.h>

// STD includes
#include <iostream>

namespace
{

/// Build a minimal scene + DM pair.  The DM observes the scene via
/// SetMRMLScene — the same code path the displayable-manager group
/// drives in a real view.
vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> makeDM(vtkMRMLScene* scene)
{
  vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> dm = vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D>::New();
  dm->SetMRMLScene(scene);
  return dm;
}

int testNodeAddedSpawn()
{
  vtkNew<vtkMRMLScene> scene;
  vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> dm = makeDM(scene);
  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 0);

  vtkNew<vtkMRMLBezierSurfaceNode> node;
  scene->AddNode(node);

  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 1);
  vtkLiverBezierWidget* widget = dm->GetWidget(node);
  CHECK_NOT_NULL(widget);
  CHECK_POINTER(widget->GetBezierNode(), node.GetPointer());
  return EXIT_SUCCESS;
}

int testNodeRemovedTeardown()
{
  vtkNew<vtkMRMLScene> scene;
  vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> dm = makeDM(scene);

  vtkNew<vtkMRMLBezierSurfaceNode> node;
  scene->AddNode(node);
  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 1);

  scene->RemoveNode(node);
  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 0);
  CHECK_NULL(dm->GetWidget(node));
  return EXIT_SUCCESS;
}

int testSceneSwapRebuild()
{
  vtkNew<vtkMRMLScene> scene;
  vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> dm = makeDM(scene);

  // Seed the scene with two Bezier-surface nodes outside of the
  // DM's normal NodeAdded path — emulate a fresh scene populated
  // by an importer that fired EndImport at the end.
  scene->StartState(vtkMRMLScene::ImportState);
  vtkNew<vtkMRMLBezierSurfaceNode> nodeA;
  vtkNew<vtkMRMLBezierSurfaceNode> nodeB;
  scene->AddNode(nodeA);
  scene->AddNode(nodeB);
  scene->EndState(vtkMRMLScene::ImportState);

  // After EndImport reconcile, both nodes must have widgets.
  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 2);
  CHECK_NOT_NULL(dm->GetWidget(nodeA));
  CHECK_NOT_NULL(dm->GetWidget(nodeB));

  // Clear the scene — every widget tears down via EndClose.
  scene->StartState(vtkMRMLScene::CloseState);
  scene->Clear(1);
  scene->EndState(vtkMRMLScene::CloseState);
  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 0);
  return EXIT_SUCCESS;
}

int testMultipleNodes()
{
  vtkNew<vtkMRMLScene> scene;
  vtkSmartPointer<vtkMRMLLiverBezierSurfaceDisplayableManager3D> dm = makeDM(scene);

  vtkNew<vtkMRMLBezierSurfaceNode> nodeA;
  vtkNew<vtkMRMLBezierSurfaceNode> nodeB;
  vtkNew<vtkMRMLBezierSurfaceNode> nodeC;
  scene->AddNode(nodeA);
  scene->AddNode(nodeB);
  scene->AddNode(nodeC);

  CHECK_INT(static_cast<int>(dm->GetNumberOfWidgets()), 3);
  CHECK_NOT_NULL(dm->GetWidget(nodeA));
  CHECK_NOT_NULL(dm->GetWidget(nodeB));
  CHECK_NOT_NULL(dm->GetWidget(nodeC));

  // Each widget must reference its own data node.
  CHECK_POINTER(dm->GetWidget(nodeA)->GetBezierNode(), nodeA.GetPointer());
  CHECK_POINTER(dm->GetWidget(nodeB)->GetBezierNode(), nodeB.GetPointer());
  CHECK_POINTER(dm->GetWidget(nodeC)->GetBezierNode(), nodeC.GetPointer());
  return EXIT_SUCCESS;
}

} // namespace

//------------------------------------------------------------------------------
int vtkMRMLLiverBezierSurfaceDisplayableManager3DTest1(int, char*[])
{
  CHECK_EXIT_SUCCESS(testNodeAddedSpawn());
  CHECK_EXIT_SUCCESS(testNodeRemovedTeardown());
  CHECK_EXIT_SUCCESS(testSceneSwapRebuild());
  CHECK_EXIT_SUCCESS(testMultipleNodes());

  std::cout << "vtkMRMLLiverBezierSurfaceDisplayableManager3DTest1 completed successfully" << std::endl;
  return EXIT_SUCCESS;
}
