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

  //--------------------------------------------------------------------------------
  // MRMLNode methods
  //--------------------------------------------------------------------------------
  const char* GetIcon() override {return ":/Icons/MarkupsGeneric.png";}
  const char* GetAddIcon() override {return ":/Icons/MarkupsGenericMouseModePlace.png";}
  const char* GetPlaceAddIcon() override {return ":/Icons/MarkupsGenericMouseModePlaceAdd.png";}

  vtkMRMLNode* CreateNodeInstance() override;
  /// Get node XML tag name (like Volume, Model)
  ///
  const char* GetNodeTagName() override {return "MarkupsSlicingContour";}

  /// Get markup name
  const char* GetMarkupType() override {return "SlicingContour";}

  /// Get markup short name
  const char* GetDefaultNodeNamePrefix() override {return "SC";}

  /// \sa vtkMRMLNode::CopyContent
  vtkMRMLCopyContentDefaultMacro(vtkMRMLLiverMarkupsSlicingContourNode);

  vtkPolyData* GetTargetOrgan() const {return this->TargetOrgan;}
  void SetTargetOrgan(vtkPolyData* targetOrgan) {this->TargetOrgan = targetOrgan;}

protected:
  vtkMRMLLiverMarkupsSlicingContourNode();
  ~vtkMRMLLiverMarkupsSlicingContourNode() override;
  vtkMRMLLiverMarkupsSlicingContourNode(const vtkMRMLLiverMarkupsSlicingContourNode&);
  void operator=(const vtkMRMLLiverMarkupsSlicingContourNode&);

private:
  vtkPolyData *TargetOrgan = nullptr;
};

#endif //__vtkmrmllivermarkupsslicingcontournode_h_
