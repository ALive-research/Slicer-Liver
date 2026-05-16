# Distributed under the OSI-approved BSD 3-Clause License.
# Copyright (c) Oslo University Hospital. All rights reserved.
#
# Representations sub-package for the LayerDM Pipeline pattern landing
# under ADR-0013 §6 and ADR-0014 §2.  Each module under this package
# defines exactly one Representation class: a small, unit-testable VTK
# assembly (actor + mapper(s) + per-frame state) that a Pipeline
# composes.
#
# Currently populated:
#
# * ``BezierPlanningRepresentation`` — active in (state=Planning, *);
#   renders the 4×4 Bezier control surface.
#
# Reserved for the remaining T2.2 stack iterations (slot names defined
# as constants on ``LiverBezierSurfacePipeline``):
#
# * ``SlicingPlaneInitRepresentation`` — active in
#   (state=Init, mode=SlicingPlane); renders two control points + the
#   plane + the ring on the target liver surface.
# * ``DistanceSpheroidInitRepresentation`` — active in
#   (state=Init, mode=DistanceSpheroid); renders the spheroid control
#   points + the spheroid + the ring.
