# SlicerLiver extension for 3D Slicer

SlicerLiver is an extension for the medical research software [3D
Slicer](https://slicer.org "3D Slicer") providing tools for analysis,
quantification and therapy planning for hepatic interventions.

The extension is currently under development features:

- Computation and visualization of liver vascular territories (liver segments).
- Definition of surgical resection in 3D using deformable surfaces, as well as the visualization of resection margins (risk areas).

## Liver resection planning

Slicer-Liver can specify liver resections using deformable surfaces. The first step is the surface initializiation as a plane that cuts the liver.

![Liver planning initialization](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_01.png?raw=true)

Then, the resection can be deformed usig the control points (4x4). It is also possible to apply global transformations such as rotations and translations to better position the surface.

![Liver planning modification](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_02.png?raw=true)

There are multiple options to create visualizations for the resection (color, opacity, configurable grid, etc).

![Liver planning visualization](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_04.png?raw=true)

## Liver vasculature analysis

Our approach to liver segments definition consist of the defintion of a segment by the centerline connecting user-defined sets of points.

![Liver segments -- placing fiducials](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_06.png?raw=true)

These centerlines will be the base for computation of liver segments in image space. The computation is based on shortest-distance mapping

![Liver segments -- placing fiducials](https://github.com/ALive-research/Slicer-Liver/blob/master/Screenshots/Slicer-Liver_screenshot_08.png?raw=true)


# Authors

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

# License

 This software is open source distributed under the [3-Clause BSD License](https://github.com/ALive-research/Slicer-Liver/blob/31278dadf0f0f8351c82eb8f7c548ee4f9da1397/LICENSE "3-Clause BSD License")

# Acknowledgements

This software has partially been funded by The Research Council of Norway through the ALive project (grant nr. 311393).
