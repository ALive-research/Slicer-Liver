import vtk
import slicer

class BranchPointerHelper:

    def __init__(self, view, interactor, renderer):

        """This is the constructor of the class. It initializes the member variables and
        creates the visualization pipeline for the pointer"""


        self.__pointSource = None
        self.__pointMapper = None
        self.__pointActor = None
        self.__pointLocator = None
        self.lastClosest = None
        self.lastClosestId = None

        self.__targetModel = None
        self.__distance  = vtk.reference(10.0) # This initial value should be larger than self.threshold
        self.__threshold = 5.0

        self.__mouseMoveObserver = None
        self.__interactor = interactor
        self.__renderer = renderer
        self.__view = view
        self.__pointerVisibility = True

        self.__createVisualizationPipeline()

        self.__addObservers()

    def __createVisualizationPipeline(self):

        """This function obtains the renderer and sets up a visualization pipeline
        to display the position of the locator projected on a given geometry."""


        # Create the visualizatio pipeline
        self.__pointSource = vtk.vtkPointSource()
        self.__pointMapper = vtk.vtkPolyDataMapper()
        self.__pointMapper.SetInputConnection(self.__pointSource.GetOutputPort())
        self.__pointActor = vtk.vtkActor()
        self.__pointActor.VisibilityOff()
        self.__pointActor.GetProperty().SetPointSize(15)
        self.__pointActor.SetMapper(self.__pointMapper)
        self.__pointLocator = vtk.vtkOctreePointLocator()
        self.__renderer.AddActor(self.__pointActor)

    def __addObservers(self):
        
        if self.__mouseMoveObserver is not None:
            return 

        self.__mouseMoveObserver =  self.__interactor.AddObserver("MouseMoveEvent",
                                                              self.__onMouseMove, 1.0)

    def __removeObservers(self):

        if self.__mouseMoveObserver is None:
            return

        self.__interactor.RemoveObserver(self.__mouseMoveObserver)
        self.__mouseMoveObserver = None


    def __onMouseMove(self, obj, event):

        if self.__targetModel is not None:
            self.__drawPointer()



    def setTargetModel(self, polyData):
        if polyData:
            self.__pointLocator.SetDataSet(polyData)
            self.__pointLocator.AutomaticOn()
            self.__pointLocator.BuildLocator()
            self.__targetModel = polyData


    def __drawPointer(self):

        """This function projects a pointer on the target model if the distance of the mouse pointer
        is less than the given threshold"""

        if self.__interactor is None:
            return 

        picker = self.__interactor.GetPicker()
        if picker is None:
          return

        (x,y) = self.__interactor.GetLastEventPosition()
        picker.Pick(x, y, 0, self.__renderer)

        picked = picker.GetPickPosition()

        closestId = self.__pointLocator.FindClosestPoint(picked[0],
                                                       picked[1],
                                                       picked[2],
                                                       self.__distance)
        closest = self.__targetModel.GetPoint(closestId)

        if self.__distance < self.__threshold and self.__pointerVisibility:
          self.__pointSource.SetCenter(closest)
          self.__pointSource.Update()
          self.__pointActor.VisibilityOn()
          self.lastClosest = closest
          self.lastClosestId = closestId
        else:
          self.__pointActor.VisibilityOff()
          self.lastClosest = None

        self.__view.forceRender()

    def enablePointerVisibility(self):
        self.__pointerVisibility = True
        if self.__distance < self.__threshold:
            self.__pointActor.VisibilityOn()

    def disablePointerVisibility(self):
        self.__pointerVisibility = False
        self.__pointActor.VisibilityOff()
