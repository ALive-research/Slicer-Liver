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
# * ``DistanceSpheroidInitRepresentation`` — active in
#   (state=Init, mode=DistanceSpheroid); renders the spheroid control
#   points + the spheroid + the ring.
# * ``ConfirmedRepresentation`` — active in (state=Confirmed, *) per
#   ADR-0019.  Renders the fitted Bezier surface with the parenchyma-
#   trim shader on (``uResectionClipOut == 1``) and hides the control
#   polygon + widget.  The trim-shader wiring is gated on
#   T2-mapper-relocation (the relocated
#   ``vtkOpenGLBezierResectionPolyDataMapper`` is the
#   ``SetResectionClipOut`` host); until that lands the Representation
#   renders the surface without the trim, matching the ADR-0019
#   §"Rollout plan" "land WITHOUT a working trim shader" fallback.
