#ifndef __vtkmrmllivermarkupsslicingcontournode_h_
#define __vtkmrmllivermarkupsslicingcontournode_h_

#include <vtkMRMLMarkupsLineNode.h>

#include "vtkSlicerLiverMarkupsModuleMRMLExport.h"

//-----------------------------------------------------------------------------
class VTK_SLICER_LIVERMARKUPS_MODULE_MRML_EXPORT vtkMRMLLiverMarkupsSlicingContourNode
: public vtkMRMLMarkupsLineNode
{
public:
  static vtkMRMLLiverMarkupsSlicingContourNode* New();
  vtkTypeMacro(vtkMRMLLiverMarkupsSlicingContourNode, vtkMRMLMarkupsLineNode);
  void PrintSelf(ostream& os, vtkIndent indent) override;

  const char* GetIcon() override {return "";}
  const char* GetPlacementIcon() override {return "";}

  //--------------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------------

  vtkMRMLNode* CreateNodeInstance() override;
  /// Get node XML tag name (like Volume, Model)
  ///
  const char* GetNodeTagName() override {return "MarkupsSlicingContour";}

  /// Get markup name
  const char* GetMarkupName() override {return "SlicingContour";}

  /// Get markup short name
  const char* GetMarkupShortName() override {return "SC";}

  /// \sa vtkMRMLNode::CopyContent
  vtkMRMLCopyContentDefaultMacro(vtkMRMLLiverMarkupsSlicingContourNode);

protected:
  vtkMRMLLiverMarkupsSlicingContourNode();
  ~vtkMRMLLiverMarkupsSlicingContourNode() override;
  vtkMRMLLiverMarkupsSlicingContourNode(const vtkMRMLLiverMarkupsSlicingContourNode&);
  void operator=(const vtkMRMLLiverMarkupsSlicingContourNode&);
};

#endif //__vtkmrmllivermarkupsslicingcontournode_h_
