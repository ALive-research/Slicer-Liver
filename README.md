## Table of content
- [Introduction](#introduction)
    - [Installing the extension](#installing-the-extension)
    - [Sample Data](#sample-data)
- [Slicer-Liver Extension Usage](#slicer-liver-extension-usage)
    - [Distance Map Computation](#distance-map-computation)
    - [Resections](#resections)
    - [Liver Segments](#liver-segments)
    - [Video Tutorial](#video-tutorial)
- [Developers](#developers)
    - [Compilation](#compilation)
    - [Testing](#testing)
    
## Introduction

SlicerLiver is an extension for the medical research software [3D Slicer](https://slicer.org "3D Slicer") providing tools for analysis, quantification and therapy planning for hepatic interventions.

The extension provides a fast and accurate solution for:

- Computation and visualization of liver vascular territories (liver segments).
- Definition of surgical resection in 3D using deformable surfaces, as well as the visualization of resection margins (risk areas).

### Installing the extension

1.  Download and install 3D Slicer according to your operating system from here : https://download.slicer.org/.
2.  Open Slicer.
3.  Press Ctrl+4 to open the extension manager. Or click the blue upper-right icon with the letter `E`.
4.  Once the Extension Manager pops up, make sure to select the `Install Extensions` tab.
5.  On the upper-right search box write *"Liver"*
6.  Click `Install` and give okay to install other extensions if asked.
7.  Restart Slicer.
8.  Once 3D Slicer restarts, click the search icon on the left of the module selector and write 'Liver'. Click `Switch to module`.

![Slicer-Liver_screenshot_10](https://github.com/dalbenzioG/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_10.jpg?raw=true)

### Sample Data

To test the extension, the LiverVolume and LiverSementation data can be loaded from the Sample Data module, after installing Slicer-Liver. To properly load the data in the plugin, it is advised to first open the extension and afterwards to navigate to the Sample module and to load the data.

![Slicer-Liver_screenshot_9](https://github.com/dalbenzioG/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_9.jpg?raw=true)

## Slicer-Liver Extension Usage

The extension is separated in the following three sections:

- Distance Map Computation: projection of the safety margins in real-time onto the resection surface, which allows the user to modify the resection proposal until the safety requirement are met.
- Resections: computation of the first approximation (planar Bézier) of the resection surface which can be subsequently modified through 16 control points.
- Liver Segments: calculation and visualization of liver vascular territories (liver segments).

Each section is oriented towards one part of the liver resection planning workflow but, if desired, can work independently of the other ones.
At the end of the workflow, the distance map, resection plan and liver segments can be saved to a given output directory.

### Distance Map Computation

The computation of the Distance Map can be done using the following steps:

1.  Select the `Reference Volume` CT data.
2.  Select the `Segmentation` , i.e the binary labelmap representation which stores the segmentation of the liver, tumour and vascular territories.
3.  Select the `Tumor` segmentation.
4.  Select the `Liver` segmentation.
5.  Create new *VectorVolume* for `Output Distance Map`.
6.  Finally, click on `Compute Distance Map`.

### Resections

The liver resection can be planned through the following process:

1.  Create a new *Liver Resection* for `Resection`.
2.  Select the labelmap (the same used in step 2 for the Distance Map Computation) for `Liver Segmentation`.
3.  Select the `Liver` segmentation.
4.  Optional: the user has the possibility to select the *Distance Map* computed at the end of the first section thought the collapsible button `Distance Map`.
5.  In the 3D View, slide the contour surrounding the liver in the desired position through the *MarkupSlidingContour*.
6.  The initial resection plane will appear after dropping the mouse.
7.  The resection can be deformed using the control points (4x4). It is also possible to modify the `Resection grid`, `Resection margin` and `Uncertainty margin` as desired.
8.  Check `Preview resection` checkbox if you want to visualize the final resection plan.

![Slicer-Liver_screenshot_11](https://github.com/dalbenzioG/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_11.jpg?raw=true)

![Slicer-Liver_screenshot_12](https://github.com/dalbenzioG/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_12.jpg?raw=true)


There are multiple options to create visualizations for the resection (color, opacity, configurable grid, etc).

![Liver planning visualization](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_04.png?raw=true)

### Liver Segments

Our approach to liver segments definition consist of the defintion of a segment by the centerline connecting user-defined sets of points. These centerlines will be the base for computation of liver segments in image space. The computation is based on shortest-distance mapping.
The Liver segments can be defined using the following steps:

1.  Select the `Segmentation`.
2.  Select the hepatic/portal segmentation for `Segment`.
3.  You can hide the liver segmentation for better visibility in the 3D view by going to: Modules > search for Data > click on Switch to Module > Click on the eye botton next to the liver segmentation.
4.  Switch to *Liver* module again.
5.  Create a *new Point List* for `Vessels points`.
6.  Click the arrow button next to `Vessel points`," and place fixed landmark points on the hepatic/portal segmentation. These points will be useful for extracting the centralines of user-defined vessel branches.
7.  Once all the points are placed, Click `Add Vessel Centerline Segments`.
8.  Repeat steps 5 and 6 for creating *new Point List*, i.e extracting new centerlines.
9.  Click on `Calculate Vascular Segments`.

![Liver segments -- placing fiducials](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_06.png?raw=true)

![Liver segments -- placing fiducials](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_08.png?raw=true)

10. If you want to visualize the liver segments in the 3D view:
	1. Click the search icon on the left of the module selector and write 'Data'. Click switch to module.
	2. Select the created *VascularSegments* labelmap and right click to `Convert label map to segmentation node`.
	3. Click again the search icon and go to `Segmentations` module.
	4. Select the new *VascularSegmentations* as `Active segmentation`.
	5. Click on `Show 3D`.
 
 ![Slicer-Liver_screenshot_14](https://github.com/dalbenzioG/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_14.jpg?raw=true)
 
## Video Tutorial
[Slicer-Liver tutorial](https://www.youtube.com/watch?v=oRu624mtQZE)

## Developers

### Compilation

Slicer-Liver depends on the VMTK which can be installed in Slicer3D using the [extension manager]( https://slicer.readthedocs.io/en/latest/user_guide/extensions_manager.html#install-extensions) or built following the steps for developers here: https://github.com/vmtk/SlicerExtension-VMTK#for-developers.

`SLICER_BUILD_DIR=/path/to/Slicer-SuperBuild`
```
git clone https://github.com/ALive-research/Slicer-Liver.git
cmake -DSlicer_DIR:PATH=SLICER_BUILD_DIR/Slicer-build -S ../Slicer-Liver
make -j5
make package
```
### Testing

-  To enable the developer mode go to :
    - Edit > Application Settings > Developer
    
- Then check the `Enable developer mode` check box. The application may need to be restarted for this modification to be taken into account.
    
- To run the unit tests, open the Slicer-Liver extension, expand the `Reload & Test` menu and click on the `Reload and Test` button.
    
- To visualize the test results, open the Python console by going to: View > Python Interactor.
    
- The number and the result of the tests will be displayed in the console. Should any of the test fail, please don't hesitate to [open an issue](https://github.com/ALive-research/Slicer-Liver/issues/new/choose) or contact us through the [Slicer forum](https://discourse.slicer.org).
    
## Authors

- Rafael Palomar (Oslo University Hospital / NTNU, Norway)
- Ole Vegard Solberg (SINTEF, Norway)
- Geir Arne Tangen (SINTEF, Norway)
- Gabriella D'Albenzio (Oslo University Hospital)
- Ruoyan Meng (NTNU)
- Javier Pérez de Frutos (SINTEF, Norway)
- Héctor Martínez (Universidad de Córdoba)
- Francisco Javier Rodríguez Lozano (Universidad de Córdoba)
- Joaquín Olivares Bueno (Universidad de Córdoba)
- José Manuel Palomares Muñoz (Universidad de Córdoba) 

Contact: [rafael.palomar@ous-research.no](mailto:rafael.palomar@ous-research.no)

## License

 This software is open source distributed under the [3-Clause BSD License](https://github.com/ALive-research/Slicer-Liver/blob/31278dadf0f0f8351c82eb8f7c548ee4f9da1397/LICENSE "3-Clause BSD License")

## Acknowledgements

This software has partially been funded by The Research Council of Norway through the ALive project (grant nr. 311393).
