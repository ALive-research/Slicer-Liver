# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""CreateResectionPlan auto-attaches the scene's computed distance map (#538).

Stage-2 accept (the canonical import) computes a distance-map volume tagged
``DistanceMap='True'`` / ``Computed='True'``.  For Planning to open ready, a
freshly created resection plan must reference it without a manual step:
``vtkSlicerLiverResectionsLogic::CreateResectionPlan`` resolves the scene's
single computed distance map and wires it via
``SetAndObserveDistanceMapVolumeNode`` (ADR-0031 -- the distance map lives on
the plan wrapper).  When no computed map exists, the plan is created with no
distance-map reference, exactly as before.

Scene-needing + wrapped-C++ (launched ``pytest_launched`` row); skips cleanly
under bare pytest.  RED until the auto-attach lands in the logic (ADR-0027 --
C++ cannot skip-pending, so this fails red on the pre-implementation tree).
"""

from __future__ import annotations

import pytest


def _logic_or_skip():
    # The shared support module, not `conftest`: with multiple pytest roots the
    # first root's conftest wins the name and the underscore re-exports differ.
    from slicer_pytest_support import import_slicer_or_skip, require_mrml_scene

    require_mrml_scene()
    slicer = import_slicer_or_skip()
    module = getattr(slicer.modules, "liverresections", None)
    if module is None:
        pytest.skip("liverresections module not registered in this build.")
    return slicer, module.logic()


def _computed_map(slicer, name="DistanceMap"):
    import numpy as np

    volume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode", name)
    slicer.util.updateVolumeFromArray(
        volume, np.zeros((8, 8, 8, 2), dtype=np.float32)
    )
    volume.SetAttribute("DistanceMap", "True")
    volume.SetAttribute("Computed", "True")
    return volume


def test_create_resection_plan_attaches_computed_distance_map():
    """A computed map in the scene reaches the new plan's wrapper reference."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    dmap = _computed_map(slicer)
    plan = logic.CreateResectionPlan("AutoAttach")
    assert plan is not None

    attached = plan.GetDistanceMapVolumeNode()
    assert attached is not None and attached.GetID() == dmap.GetID(), (
        "CreateResectionPlan must auto-attach the scene's computed distance "
        "map (DistanceMap='True' + Computed='True') so Planning opens ready "
        "(#538 / ADR-0031)."
    )


def test_create_resection_plan_without_map_leaves_reference_unset():
    """No computed map in the scene -> the plan reference stays unset."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    plan = logic.CreateResectionPlan("NoMap")
    assert plan is not None
    assert plan.GetDistanceMapVolumeNode() is None, (
        "with no computed distance map in the scene the plan must be created "
        "with no distance-map reference (previous behaviour)."
    )


def test_create_resection_plan_ignores_untagged_vector_volumes():
    """A vector volume WITHOUT the computed tags must not be attached."""
    slicer, logic = _logic_or_skip()
    slicer.mrmlScene.Clear(0)

    import numpy as np

    stray = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVectorVolumeNode", "Stray")
    slicer.util.updateVolumeFromArray(
        stray, np.zeros((4, 4, 4, 2), dtype=np.float32)
    )

    plan = logic.CreateResectionPlan("IgnoresStray")
    assert plan is not None
    assert plan.GetDistanceMapVolumeNode() is None, (
        "only a volume tagged DistanceMap='True' + Computed='True' may be "
        "auto-attached; arbitrary vector volumes must be ignored."
    )
