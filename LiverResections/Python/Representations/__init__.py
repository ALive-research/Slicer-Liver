# Distributed under the OSI-approved BSD 3-Clause License.
# Copyright (c) Oslo University Hospital. All rights reserved.
#
# Representations sub-package for the LayerDM Pipeline pattern landing
# under ADR-0013 §6 and ADR-0014 §2.  Each module under this package
# defines exactly one Representation class: a small, unit-testable VTK
# assembly (actor + mapper(s) + per-frame state) that a Pipeline
# composes.
#
# Members of this PR:
#
# * ``BezierPlanningRepresentation`` — active in (state=Planning, *);
#   renders the 4×4 Bezier control grid and the fitted surface.
#
# To land in the two follow-up PRs of the T2.2 stack:
#
# * ``SlicingPlaneInitRepresentation`` — active in
#   (state=Init, mode=SlicingPlane); renders two control points + the
#   plane + the ring on the target liver surface.
# * ``DistanceSpheroidInitRepresentation`` — active in
#   (state=Init, mode=DistanceSpheroid); renders the spheroid control
#   points + the spheroid + the ring.
