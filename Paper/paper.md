---
title: 'Slicer-Liver: A 3D Slicer Extension for Liver Surgery Planning'
tags:
  - Python
  - C++
  - Image-Guided Surgery
  - Liver Surgery Planning
  - Visualization
  - Geometric Modeling
authors:
  - name: Ruoyan Meng
    orcid: 0000-0003-0246-0011
    equal-contrib: true
    affiliation: 2
  - name: Gabriella D'Albenzio
    orcid: 0000-0000-0000-0000
    equal-contrib: true # (This is how you can denote equal contributions between multiple authors)
    affiliation: 1
  - name: Ole V. Solberg
    orcid: 0009-0004-9488-3621
    affiliation: 3
  - name: Geir Arne Tangen
    orcid: 0000-0003-0032-8500
    affiliation: 3
  - name: Rafael Palomar
    orcid: 0000-0002-9136-4154
    corresponding: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
affiliations:
 - name: The Intervention Centre, Oslo University Hospital, Oslo, Norway
   index: 1
 - name: Computer Science Department, NTNU, Gjøvik, Norway
   index: 2
 - name: Department of Health Research, SINTEF Digital, Trondheim, Norway 
   index: 3
date: 15 March 2024
bibliography: bibliography.bib
---

# Summary

This article introduces Slicer-Liver, an extension for the 3D Slicer image computing platform [@Kikinis:2013] (https://slicer.org). The software aims to address challenges in liver surgery planning by leveraging geometric modeling and visualization techniques. More specifically, Slicer-Liver enables integral liver surgery plans including virtual resections, vascular territories, as well as volumetry analysis. Progress and preliminary results obtained with Slicer-Liver show the potential of the software to be used for improving the state-of-the-art approaches in definition of virtual resections, visualization of resection plans, as well as classification of the liver in segments. These contributions hold promise on enhancing liver surgery planning and potentially improving liver surgery outcomes. Slicer-Liver is intended for research use within the fields of biomedicine and computer science.

# Statement of need

Liver cancer, both primary and metastatic (e.g., from colorectal cancer), is a global health concern with increasing incidence rates [@Siegel:2023] and surgical resection remains the most potentially curative treatment for some of these patients [@Petrowsky:2020]. The evolution of computer-assisted surgical systems over the past two decades has significantly improved tumor localization and surgeons confidence during surgery [@Hansen:2014, @Lamata:2010]. Despite these advances, systematic use of computer-assisted systems for planning liver resections remains a challenge.

Thanks to the latest advances in artificial intelligence, generation of 3D ptient-specific models for surgical planning is increasingly becoming a reality in the clinical routine, however, surgical planning with the use of these models remains a complex and  manual process. Planning of surgery is particularly important for complex cases (e.g., those presenting multiple tumors or those where the location and size of the tumor poses a challenge for the surgery practice). Furthermore, precise surgical planning should not only account for the liver geometry, but also for the blood supply to various liver regions (segments) [@Warmann:2016, @Bismuth:2013]. Furthermore, visualization of 3D liver models and resections a difficult task, where occlusions can prevent the effective understanding of the surgical plan. In addition, there is no broad consensus on the definition of a good resection plan, which is partly due to the lack of formal methods to specify and communicate resection plans, and partly due to the different surgery cultures and practices in different hospitals.

All these challenges support the advancing on the integration of computer-aided systems for surgical planning into the clinical reality. In response to these challenges, Slicer-Liver provides functionality for modeling of resections and vascular territories, visualization of virtual resections in lower dimensions and volumetry analysis. In addition, Slicer-Liver serves as a research sandbox for integration of new liver therapy planning methods (e.g., liver ablations) and can be extended to planning of therapies in organs other than the liver.

# Overview of Slicer-Liver

Slicer-Liver is a 3D Slicer extension that can be installed directly through the 3D Slicer Extension Manager [@3DSlicerExtensionsManager:2024]. Slicer-Liver is intended for research purposes and is distributed through an MIT license. The software architecture is based on 3D Slicer modules (both C++ and Python) and follows common patterns found in other 3D Slicer extensions. The software provides 4 bodies of functionality that can be used independently or in conjunction as described in the following. 

**Definition of Virtual Resections**
Slicer-Liver has integrated different geometric modeling techniques to model virtual resetions (deformable Bézier with planar initialization [@Palomar:2017], NURBS and contour-initialized resections). The implementation of these methods include visualization of the resection margin, adaptive grid visualization and clipping of the resection excess. Thanks to the computation of distance maps between anatomical structures, resection margin visualization operates in real-time as the user modifies the resection.

**Resectograms**
As an additional visualization object, Slicer-Liver implements the use of resectograms [@meng2023resectograms], which benefit from the computation of distance maps to extend the real-time visualization of the information along the resection trajectory. Resectograms help the user understand information subject to occlusions in the 3D Scene, as well as serve as indicator of validity of resections (e.g., making possible detection of malformed resections or violations of margins).

**Liver Segments Classification**
Slicer-Liver leverages the method for computing liver vascular territories and segments classification utilized in [@{d'Albenzio:2023}]. The method uses the liver morphology, the interior vascular network, and user-defined landmarks to provide enhanced flexibility in marker placement, distinguishing it from other methods. One of the advantages of this approach is that vascular territories participated by both portal and hepatic vessel systems can be computed. The liver segments computed can be visualized and processed as segmentation objects or 3D models, by the rest of the tools provided in 3D Slicer.

**Resection Volumetry**
In the same line as for the liver segments classification, Slicer-Liver implements a tool for marking liver regions (with and without consideration to resections or liver segments) in a way that allows the user to perform liver resection volumetry analysis.

# Preliminary results

**Definition of Virtual Resections**
Slicer-Liver provides computer-aided preoperative planning systems, streamlining the resection planning process and introducing real-time 3D cutting path visualization [@Aghayan:2023], shown in \autoref{fig:1}. The presented approach empowers users to make decisions based on individual patient needs, enhancing outcomes for both atypical and anatomical resections. Notably, the proposed new resection methods aim to obtain better liver remnant preservation compared to existing methods.

![Specification of a virtual resection with visualization of safety margins.\label{fig:1}](Screenshots/Slicer-Liver_screenshot_04.png)

**Visualization of Virtual Resections Using Resectograms**
Adding resectograms to Slicer-Liver, allows a real-time 2D representation of resections as shown in \autoref{fig:2}, where the resectogram provides an intuitive and occlusion-free visualization of the virtual resection with three components: resection intersection with liver, vessels and anatomical segments, as well as safety margins. The use of resectograms enables an effective identification and characterization of invalid resection types due to inadequate visualization in the 3D view during planning. 

![Virtual 3D resection with corresponding 2D resectogram.\label{fig:2}](Screenshots/resectograms-overview.svg){ width=100% }

**Classification of Liver Segments**
By departing from the standardized Couinaud classification of the liver in segments, the implemented approach our approach enables a more individualized representation of liver segmental distribution \autoref{fig:3}. Particularly noteworthy is the method’s accurate estimation of the challenging Segment 1, resulting in a comprehensive and precise segmentation of the caudate lobe. While improvements, particularly in automating the landmark marking process, are needed, the approach holds promise for improving liver surgery planning and has the potential to optimize surgical outcomes.

![Visualizing liver segments based on annotated hepatic and portal vessel segments around the tumor.\label{fig:3}](Screenshots/JossFigure3.png)

# Acknowledgements
This work was conducted as part of the ALive project, funded by the Research Council of Norway under the IKTPLUSS research program (grant nr. 311393).

# References
