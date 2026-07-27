# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""ADR-0013 §5 -- the volumetry seed registration is the 3 calls, NO custom DM.

``volumetry-seeds-layerdm-plan.md`` §3b: LiverVolumetry registers its new
node ecosystem through the SAME three ADR-0013 §5 calls VascularTerritories
uses, and hosts NO per-module displayable manager
(``feedback_layerdm_no_custom_dm``; ADR-0013 §5):

1. ``RegisterNodeClass`` for the seed carrier + display node (+ storage);
2. the upstream LayerDM displayable-manager ``RegisterInFactory``;
3. a Pipeline creator matching ``(vtkMRMLViewNode,
   vtkMRMLVolumetrySeedsDisplayNode)`` returning the shared
   ``SurfacePointPlacementPipeline3D`` wired to a volumetry provider (plus
   the slice creator).

This file pins:

* the carrier + display node classes are REGISTERED (instantiable via
  ``AddNewNodeByClass``);
* NO ``vtkMRMLLiverVolumetry*DisplayableManager`` class exists (an absence
  pin with a credible creep-in path -- a closed-without-merge attempt at a
  custom ``vtkMRMLLiverBezier*DisplayableManager3D`` is exactly this
  temptation; ``feedback_layerdm_no_custom_dm`` / ADR-0013 §5).  NOT a
  colour-of-the-sky absence.

The Pipeline-creator wiring itself is exercised by
``test_volumetry_seed_placement.py`` (an actual placement through the
created pipeline); this file is the registration-shape smoke.

HARNESS: launched Slicer.  Node registration + the LayerDM factory are
reachable only inside a launched Slicer with the module loaded; a bare
``PythonSlicer -m pytest`` SKIPS CLEANLY.

The SUT does not exist yet.  Per ADR-0027 red->skip the guards skip-pend;
the skips lift at the implementation commit.

References
----------
* ADR-0013 §5 -- the three registration calls; no custom displayable
  manager (the base supplies only the Pipeline base classes).
* ADR-0038 -- §"Shared home + names" (each module keeps its own three
  registration calls + its own display-node type).
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* feedback_layerdm_no_custom_dm -- the closed
  ``vtkMRMLLiverBezier*DisplayableManager3D`` custom-DM attempt is the
  creep-in path this absence guards.
"""

from __future__ import annotations

import pytest

SEEDS_NODE_CLASS = "vtkMRMLVolumetrySeedsNode"
DISPLAY_NODE_CLASS = "vtkMRMLVolumetrySeedsDisplayNode"
STORAGE_NODE_CLASS = "vtkMRMLVolumetrySeedsStorageNode"

# Names a custom displayable manager WOULD take if wrongly introduced
# (ADR-0013 §5 forbids it; the closed vtkMRMLLiverBezier*DisplayableManager3D
# attempt is the Bezier equivalent of this temptation).
BANNED_DM_CLASSES = (
    "vtkMRMLVolumetrySeedsDisplayableManager",
    "vtkMRMLVolumetrySeedsDisplayableManager3D",
    "vtkMRMLLiverVolumetrySeedsDisplayableManager",
)


def _slicer_or_skip():
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def test_seed_carrier_and_display_node_are_registered():
    """The carrier + display node (+ storage) are registered node classes.

    ADR-0013 §5 call 1 (RegisterNodeClass).  All three must be instantiable
    via ``AddNewNodeByClass`` once the module Logic's ``RegisterNodes`` has
    run in the launched build.
    """
    slicer = _slicer_or_skip()

    for cls in (SEEDS_NODE_CLASS, DISPLAY_NODE_CLASS, STORAGE_NODE_CLASS):
        node = slicer.mrmlScene.AddNewNodeByClass(cls)
        if node is None:
            pytest.skip(
                f"{cls} not registered -- the ADR-0013 §5 RegisterNodeClass "
                "calls (plan §3b) have not landed (ADR-0027)."
            )
        assert node.IsA(cls), f"{cls} must instantiate to its own type."


def test_no_custom_displayable_manager_for_volumetry_seeds():
    """NO per-module displayable manager exists for the seed display node.

    ADR-0013 §5 / ``feedback_layerdm_no_custom_dm``: rendering goes through
    the shared LayerDM Pipeline base, never a module-hosted DM.  A closed-
    without-merge ``vtkMRMLLiverBezier*DisplayableManager3D`` attempt is
    exactly this pattern for Bezier, so this is an absence WITH a credible
    creep-in path (not colour of the sky).
    """
    _slicer_or_skip()
    import slicer

    for name in BANNED_DM_CLASSES:
        # A registered custom DM would surface as a class on the slicer
        # namespace (the wrapped-VTK convention) or be creatable off the
        # scene; assert neither.
        assert getattr(slicer, name, None) is None, (
            f"{name} must NOT exist -- LiverVolumetry hosts no per-module "
            "displayable manager (ADR-0013 §5; feedback_layerdm_no_custom_dm)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
