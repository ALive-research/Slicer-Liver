---
title: 'SlicerLiver: A 3D Slicer extension for liver surgery planning'
tags:
  - Python
  - Image Guided Surgery
  - Liver surgery planning
  - Liver tumor resection visualization
  - Geometric modelling
authors:
  - name: Rafael Palomar
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    corresponding: true
    affiliation: "1, 2" # (Multiple affiliations must be quoted)
  - name: Ruoyan Meng
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    affiliation: 2
  - name: Gabriella D'Albenzio
    orcid: 0000-0000-0000-0000
    equal-contrib: true # (This is how you can denote equal contributions between multiple authors)
    affiliation: 1
  - name: Ole V. Solberg
    orcid: 0000-0000-0000-0000
    equal-contrib: true # (This is how you can denote equal contributions between multiple authors)
    affiliation: 3
  - name: Geir Arne Tangen
    orcid: 0000-0000-0000-0000
    affiliation: 3
  - given-names: Ludwig
    dropping-particle: van
    surname: Beethoven
    affiliation: 3
affiliations:
 - name: The Intervention Centre, Oslo University Hospital, Oslo, Norway
   index: 1
 - name: Computer Science Department, NTNU, Gjøvik, Norway
   index: 2
 - name: Department of Health Research, SINTEF Digital, Trondheim, Norway 
   index: 3
date: 15 Desember 2023
bibliography: paper.bib

# Optional fields if submitting to a AAS journal too, see this blog post:
# https://blog.joss.theoj.org/2018/12/a-new-collaboration-with-aas-publishing
aas-doi: 10.3847/xxxxx <- update this with the DOI from AAS once you know it.
aas-journal: Astrophysical Journal <- The name of the AAS journal.
---

# Summary

This paper introduces SlicerLiver, a software extension to the 3D Slicer platform.
The ALive project aims to 
address challenges in liver surgery planning by applying geometric modeling and 
artificial intelligence to generate resection plans for complex cases, developing 
parameterized patient-specific vascular models, and creating computational methods 
for resection visualization in 2D. The project’s implementation revolves around 
a software platform based on 3D Slicer, organized into four work packages. Progress 
and preliminary results show improvements in defining virtual resections, visualizing 
resections using Resectograms and classifying liver segments accurately. These 
contributions hold promise in enhancing liver surgery planning and potentially 
improving patient outcomes.

# Statement of need

Liver cancer, both primary and secondary types, is a global health concern with 
increasing incidence rates [1]. Surgical resection is the most effective treatment 
for some of these cancers [2], and the evolution of computer-assisted surgical systems 
over the past two decades has significantly improved tumor localization and surgeons 
confidence during surgery [3], [4]. However, despite these advances, several challenges 
remain in liver surgical practice.
While patient-specific 3D models are systematically generated for surgical planning 
and guidance, surgery planning remains a manual process. This is particularly problematic 
for patients with multiple metastases, where manual surgery planning becomes intricate. 
The current techniques for planning virtual resections, namely, drawing-on-slices and 
deformable surfaces [5], [6], have shown limitations. Therefore, there is a pressing 
need for new algorithms capable of generating precise, rapid, and straightforward 
resection plans, even in complex cases.


# Mathematics

Single dollars ($) are required for inline mathematics e.g. $f(x) = e^{\pi/x}$

Double dollars make self-standing equations:

$$\Theta(x) = \left\{\begin{array}{l}
0\textrm{ if } x < 0\cr
1\textrm{ else}
\end{array}\right.$$

You can also use plain \LaTeX for equations
\begin{equation}\label{eq:fourier}
\hat f(\omega) = \int_{-\infty}^{\infty} f(x) e^{i\omega x} dx
\end{equation}
and refer to \autoref{eq:fourier} from text.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# Acknowledgements

We acknowledge contributions from Brigitta Sipocz, Syrtis Major, and Semyeong
Oh, and support from Kathryn Johnston during the genesis of this project.

# References
