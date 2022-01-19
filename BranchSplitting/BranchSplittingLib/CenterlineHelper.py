import slicer
import vtk

class CenterlineHelper:

  def __init__(self):

    #
    # Member variables related to  centerline extraction
    #
    self.__FlipNormals = 0
    self.__CapDisplacement = 0.0
    self.__RadiusArrayName = 'MaximumInscribedSphereRadius'
    self.__CostFunction = '1/R'
    self.__AppendEndPoints = 0
    self.__CheckNonManifold = 0
    self.__Resampling = 0
    self.__ResamplingStepLength = 1.0
    self.__SimplifyVoronoi = 0
    self.__EikonalSolutionArrayName = 'EikonalSolution'
    self.__EdgeArrayName = 'EdgeArray'
    self.__EdgePCoordArrayName = 'EdgePCoordArray'
    self.__CostFunctionArrayName = 'CostFunctionArray'
    self.__UseTetGen = 0
    self.__TetGenDetectInter = 1
    self.__DelaunayTessellation = None
    self.__VoronoiDiagram = None
    self.__PoleIds = None
    self.__DelaunayTolerance = 0.001

    #
    # Member variables related to the geometric participating on the computation
    # of the centerline
    #
    self.__centerline = None
    self.__inputVesselModel = None
    self.__originMarkupsFiducialNode = None
    self.__targetsMarkupsFiducialNode = None
    self.__markupsCurveNode = None
    self.__originIds = list()
    self.__targetsIds = list()
    self.__segmentId = 0
    self.__originFiducialsCount = 0 # This is for labels naming
    self.__targetFiducialsCount = 0 # This is for labels naming

    # self.__initializeOriginMarkups()
    # self.__initializeTargetMarkups()
    self.__initializeCurveMarkups()

  # def __initializeOriginMarkups(self):

  #   if self.__originMarkupsFiducialNode is None:

  #     self.__originMarkupsDisplayNode = slicer.vtkMRMLMarkupsDisplayNode()
  #     self.__originMarkupsDisplayNode.SetGlyphScale(5)
  #     color = [0]*4
  #     self.__originMarkupsDisplayNode.SetSelectedColor(color[:3])
  #     self.__originMarkupsDisplayNode.SetColor(color[:3])
  #     # self.__originMarkupsDisplayNode.Visibility2DOff()

  #     slicer.mrmlScene.AddNode(self.__originMarkupsDisplayNode)

  #     self.__originMarkupsFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
  #     self.__originMarkupsFiducialNode.SetAndObserveDisplayNodeID(self.__originMarkupsDisplayNode.GetID())
  #     self.__originMarkupsFiducialNode.LockedOn()
  #     # self.__originMarkupsFiducialNode.HideFromEditorsOn()

  #     slicer.mrmlScene.AddNode(self.__originMarkupsFiducialNode)

  # def __initializeTargetMarkups(self):

  #   if self.__targetsMarkupsFiducialNode is None:

  #     self.__targetsMarkupsDisplayNode = slicer.vtkMRMLMarkupsDisplayNode()
  #     self.__targetsMarkupsDisplayNode.SetGlyphScale(5)
  #     color = [0]*4
  #     self.__targetsMarkupsDisplayNode.SetSelectedColor(color[:3])
  #     self.__targetsMarkupsDisplayNode.SetColor(color[:3])
  #     # self.__targetsMarkupsDisplayNode.Visibility2DOff()

  #     slicer.mrmlScene.AddNode(self.__targetsMarkupsDisplayNode)

  #     self.__targetsMarkupsFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
  #     self.__targetsMarkupsFiducialNode.SetAndObserveDisplayNodeID(self.__targetsMarkupsDisplayNode.GetID())
  #     self.__targetsMarkupsFiducialNode.LockedOn()
  #     # self.__targetsMarkupsFiducialNode.HideFromEditorsOn()

  #     slicer.mrmlScene.AddNode(self.__targetsMarkupsFiducialNode)

  def __initializeCurveMarkups(self):

    if self.__markupsCurveNode is None:

      self.__markupsCurveDisplayNode = slicer.vtkMRMLMarkupsDisplayNode()
      slicer.mrmlScene.AddNode(self.__markupsCurveDisplayNode)
      self.__markupsCurveDisplayNode.SetGlyphScale(5.0)

      self.__markupsCurveNode = slicer.vtkMRMLMarkupsCurveNode()
      slicer.mrmlScene.AddNode(self.__markupsCurveNode)

      self.__markupsCurveNode.SetAndObserveDisplayNodeID(self.__markupsCurveDisplayNode.GetID())

  @property
  def centerline(self):
    return self.__centerline

  @property
  def inputVesselModel(self):
    return self.__inputVesselModel

  @inputVesselModel.setter
  def inputVesselModel(self, value):
    if type(value) is not vtk.vtkPolyData:
      raise TypeError("Value should be of type vtkPolyData")
    self.__inputVesselModel = value

  @property
  def segmentId(self):
    return self.__segmentId

  @segmentId.setter
  def segmentId(self, value):
    if type(value) is not int:
      raise TypeError("value should be of type int.")
    if value < 0:
      raise ValueError("value should be positive.")
    self.__segmentId = value

  def appendOriginId(self, pointId):

    if type(pointId) is not int:
      raise TypeError("pointId should be of type int")
    if pointId < 0:
      raise ValueError("value of pointId should be positive.")

    if self.__inputVesselModel is None:
      return

    # point = self.__inputVesselModel.GetPoint(pointId)
    # self.__originFiducialsCount += 1
    # label = "Origin_"+ str(self.__originFiducialsCount)
    # self.__originMarkupsFiducialNode.AddFiducial(point[0],\
    #                                               point[1],\
    #                                               point[2],\
                                                  # label)
    self.__originIds.append(pointId)

  def popOriginId(self):

    controlPoints = self.__originMarkupsFiducialNode.GetNumberOfControlPoints()
    if controlPoints > 0:
      self.__originMarkupsFiducialNode.RemoveNthControlPoint(controlPoints-1)
      self.__targetsIds.pop()

  def appendTargetId(self, pointId):

    if type(pointId) is not int:
      raise TypeError("pointId should be of type int")
    if pointId < 0:
      raise ValueError("value of pointId should be positive.")
    if self.__inputVesselModel is None:
      return

    # point = self.__inputVesselModel.GetPoint(pointId)
    # self.__targetFiducialsCount += 1
    # label = "Target_"+ str(self.__targetFiducialsCount)
    # self.__targetsMarkupsFiducialNode.AddFiducial(point[0],\
    #                                               point[1],\
    #                                               point[2],\
                                                  # label)
    self.__targetsIds.append(pointId)

  def popTargetId(self):
    controlPoints = self.__targetsMarkupsFiducialNode.GetNumberOfControlPoints()
    if controlPoints > 0:
      self.__targetsMarkupsFiducialNode.RemoveNthControlPoint(controlPoints-1)
      self.__targetsIds.pop()
      
  def setColor(self, color):

    self.__markupsCurveDisplayNode.SetSelectedColor(color[:3])


  def update(self):

    try:
        import vtkvmtkComputationalGeometryPython as vtkvmtkComputationalGeometry
    except ImportError:
        raise ImportError("VMTK library is not found")

    originList = vtk.vtkIdList()
    targetList = vtk.vtkIdList()
    originList.Initialize()
    targetList.Initialize()

    for i in self.__originIds:
      originList.InsertNextId(i)

    for i in self.__targetsIds:
      targetList.InsertNextId(i)

    centerlineFilter = vtkvmtkComputationalGeometry.vtkvmtkPolyDataCenterlines()
    #centerlineFilter.GlobalWarningDisplayOn()
    #centerlineFilter.DebugOn()
    centerlineFilter.SetInputData(self.__inputVesselModel)
    centerlineFilter.SetSourceSeedIds(originList)
    centerlineFilter.SetTargetSeedIds(targetList)
    centerlineFilter.SetRadiusArrayName(self.__RadiusArrayName)
    centerlineFilter.SetCostFunction(self.__CostFunction)
    centerlineFilter.SetFlipNormals(self.__FlipNormals)
    centerlineFilter.SetAppendEndPointsToCenterlines(self.__AppendEndPoints)
    centerlineFilter.SetSimplifyVoronoi(self.__SimplifyVoronoi)
    centerlineFilter.SetStopFastMarchingOnReachingTarget(1)
    centerlineFilter.SetCenterlineResampling(self.__Resampling)
    centerlineFilter.SetResamplingStepLength(self.__ResamplingStepLength)
    centerlineFilter.Update()

    centerlinePolyData = centerlineFilter.GetOutput()

    parametricSpline = vtk.vtkParametricSpline()
    parametricSpline.SetPoints(centerlinePolyData.GetPoints())
    
    parametricSource = vtk.vtkParametricFunctionSource()
    parametricSource.SetParametricFunction(parametricSpline)
    parametricSource.SetUResolution(30)
    parametricSource.SetVResolution(30)
    parametricSource.SetWResolution(30)
    parametricSource.Update()

    splineCenterline = parametricSource.GetOutput()

    idArray = vtk.vtkIntArray()
    idArray.SetName("GroupIds")
    idArray.SetNumberOfComponents(1)
    for i in range(splineCenterline.GetNumberOfCells()):
      idArray.InsertNextValue(self.__segmentId)
    splineCenterline.GetCellData().AddArray(idArray)
      
    self.__centerline = splineCenterline

    for i in range(self.__centerline.GetNumberOfPoints()):
      (x,y,z) = self.__centerline.GetPoint(i)
      self.__markupsCurveNode.AddControlPoint(vtk.vtkVector3d(x,y,z),'')
      self.__markupsCurveNode.SetNthControlPointVisibility(i,False)
