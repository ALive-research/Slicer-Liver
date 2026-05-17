# Distributed under the OSI-approved BSD 3-Clause License.
# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
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
# * ``SlicingPlaneInitRepresentation`` — active in
#   (state=Init, mode=SlicingPlane); renders two control points + the
#   plane (ring on the target liver surface deferred per
#   TODO(T2-target-mesh-weakref) until the data node gains a target
#   mesh reference).
#
# Reserved for the remaining T2.2 stack iteration (slot name defined
# as a constant on ``LiverBezierSurfacePipeline``):
#
# * ``DistanceSpheroidInitRepresentation`` — active in
#   (state=Init, mode=DistanceSpheroid); renders the spheroid control
#   points + the spheroid + the ring.
