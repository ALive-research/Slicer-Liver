#include "vtkMRMLLiverMarkupsSlicingContourNode.h"

// VTK includes
#include <vtkNew.h>
#include <vtkObjectFactory.h>

//--------------------------------------------------------------------------------
vtkMRMLNodeNewMacro(vtkMRMLLiverMarkupsSlicingContourNode);

//--------------------------------------------------------------------------------
vtkMRMLLiverMarkupsSlicingContourNode::vtkMRMLLiverMarkupsSlicingContourNode()
{
}

//--------------------------------------------------------------------------------
vtkMRMLLiverMarkupsSlicingContourNode::~vtkMRMLLiverMarkupsSlicingContourNode()=default;

//----------------------------------------------------------------------------
void vtkMRMLLiverMarkupsSlicingContourNode::PrintSelf(ostream& os, vtkIndent indent)
{
  Superclass::PrintSelf(os,indent);
}
