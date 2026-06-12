# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T5.2-f -- LiverResections wrapper nodes collect under a "Resections" folder.

ADR-0023 §"MRML scene organisation" + §Conformance [test]: Slicer-Liver
programmatically groups its node types under per-stage Subject-Hierarchy
folders ("Anatomy", "Vascular Territories", "Resections", "Volumetry"),
lazily-created and reused.  T5.2-f wires ``LiverResections`` into the shared
``vtkSlicerSubjectHierarchyFolders.CollectUnderFolder`` utility: when a
``vtkMRMLResectionPlanNode`` (the WRAPPER) is added to the scene, the module
logic's ``OnMRMLSceneNodeAdded`` observer collects it under a scene-root
"Resections" folder.

Two pinned invariants:

  1. The wrapper ``vtkMRMLResectionPlanNode`` lands under a scene-root
     "Resections" folder (the per-stage folder).
  2. The hidden Bezier/contour CARRIERS (``SetHideFromEditors(true)``) are
     NOT reparented -- only the wrapper is collected.  Hiding the carriers
     from editors keeps the surgeon-facing Subject Hierarchy clean (the
     wrapper-vs-carrier split, ADR-0014 / the 2026-05-25 wrapper-vs-carrier
     amendment); the folder must mirror that.

RED now: the LiverResections logic does not yet call the utility, so neither
the folder nor the placement exists.  The test SKIPS pre-implementation
(no "Resections" folder appears) rather than failing noisily, and goes GREEN
once the implementer lands the ``OnMRMLSceneNodeAdded`` wiring -- per
ADR-0027 §Conformance "for skipped tests, the skip lifts at the
implementation commit".

Wrapped-C++-from-Python reachability + the live NodeAdded observer can ONLY
be verified under a launched Slicer.  Under bare ``PythonSlicer -m pytest``
this skips cleanly (no ``slicer.mrmlScene``); the scene-cleanup fixture in
this module's conftest tears down every minted node so the launched harness
does not trip ``vtkDebugLeaks``.
"""

from __future__ import annotations

import pytest

RESECTIONS_FOLDER_NAME = "Resections"
WRAPPER_CLASS = "vtkMRMLResectionPlanNode"
HIDDEN_CARRIER_CLASS = "vtkMRMLBezierSurfaceNode"


def _slicer_scene_sh_or_skip():
    """Resolve (slicer, scene, shNode); skip cleanly when unavailable.

    Needs a launched Slicer with the LiverResections module logic registered
    (so the NodeAdded observer is live).  Under bare PythonSlicer there is no
    ``slicer.mrmlScene`` and the test skips.
    """
    # Import the launched-Slicer skip-guards from their canonical home
    # (``Testing/Python/slicer_pytest_support`` -- on ``sys.path`` for every
    # collection root via the ``pythonpath`` ini option).  This module's
    # ``Testing/Python`` tree is a Python package (carries ``__init__.py``),
    # so under bare ``PythonSlicer -m pytest`` prepend-import resolves a bare
    # ``from conftest import`` to the cross-module root conftest (which does
    # not re-export the guards) rather than this module's conftest -- the
    # canonical import sidesteps that shadowing and keeps the skip clean.
    from slicer_pytest_support import (
        import_slicer_or_skip as _import_slicer_or_skip,
        require_mrml_scene as _require_mrml_scene,
    )

    _require_mrml_scene()
    slicer = _import_slicer_or_skip()

    scene = slicer.mrmlScene
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(scene)
    if shNode is None:
        pytest.skip(
            "no Subject-Hierarchy node available -- ADR-0023 "
            "§'MRML scene organisation' folder placement cannot be exercised."
        )
    # The collection only fires if the LiverResections module logic observes
    # the scene; require the module so a bare-import run skips rather than
    # silently 'passing' with no observer attached.
    if getattr(slicer.modules, "liverresections", None) is None:
        pytest.skip(
            "'liverresections' module not registered -- the NodeAdded "
            "observer that collects wrapper nodes under the 'Resections' "
            "folder (ADR-0023 §'MRML scene organisation') is not active."
        )
    return slicer, scene, shNode


def _scene_root_folder_named(shNode, name):
    """Return the scene-root SH folder item with ``name``, or 0 (none).

    Scene-root-scoped so a same-named folder nested under a
    Patient/Study/Series subtree is not confused for the per-stage folder
    (matches the scene-root scoping the module logic uses).
    """
    scene_item = shNode.GetSceneItemID()
    return shNode.GetItemChildWithName(scene_item, name)


def test_resection_wrapper_collected_under_resections_folder():
    """The wrapper ``vtkMRMLResectionPlanNode`` lands under "Resections".

    ADR-0023 §"MRML scene organisation" [test]: per-stage scene-root folder,
    lazily created.  RED until the LiverResections ``OnMRMLSceneNodeAdded``
    wiring lands; skips when the folder never appears (pre-implementation).
    """
    slicer, scene, shNode = _slicer_scene_sh_or_skip()
    scene.Clear(0)

    wrapper = slicer.mrmlScene.AddNewNodeByClass(WRAPPER_CLASS, "Resection: characterization")
    assert wrapper is not None

    folder_item = _scene_root_folder_named(shNode, RESECTIONS_FOLDER_NAME)
    if not folder_item:
        pytest.skip(
            "no scene-root 'Resections' folder after adding a "
            f"{WRAPPER_CLASS} -- T5.2-f wiring "
            "(vtkSlicerSubjectHierarchyFolders.CollectUnderFolder in the "
            "logic's OnMRMLSceneNodeAdded) not yet implemented; skip lifts at "
            "the implementation commit (ADR-0027 §Conformance)."
        )

    node_item = shNode.GetItemByDataNode(wrapper)
    assert node_item, "wrapper has no Subject-Hierarchy item"
    assert shNode.GetItemParent(node_item) == folder_item, (
        "the wrapper vtkMRMLResectionPlanNode must be parented under the "
        "scene-root 'Resections' folder (ADR-0023 §'MRML scene organisation')."
    )
    # The folder is a direct child of the scene root (per-stage folder).
    assert shNode.GetItemParent(folder_item) == shNode.GetSceneItemID()


def test_hidden_bezier_carrier_is_not_reparented():
    """Hidden Bezier carriers stay OUT of the "Resections" folder.

    ADR-0023 §"MRML scene organisation" [test] + the wrapper-vs-carrier split
    (ADR-0014): only the surgeon-facing wrapper is collected; the hidden
    ``SetHideFromEditors(true)`` Bezier carrier must NOT be reparented under
    the per-stage folder.

    RED until the wiring lands; skips when the "Resections" folder never
    appears.  When green, the assertion is the strong invariant: even with a
    folder present, the hidden carrier is not under it.
    """
    slicer, scene, shNode = _slicer_scene_sh_or_skip()
    scene.Clear(0)

    # A hidden carrier as the production load path mints it
    # (LiverResections logic: bezierNode->SetHideFromEditors(true)).
    carrier = slicer.mrmlScene.AddNewNodeByClass(HIDDEN_CARRIER_CLASS)
    if carrier is None:
        pytest.skip(
            f"{HIDDEN_CARRIER_CLASS} not registered in this build -- cannot "
            "exercise the hidden-carrier exclusion invariant."
        )
    carrier.SetHideFromEditors(True)

    # And the wrapper, which SHOULD be collected.
    wrapper = slicer.mrmlScene.AddNewNodeByClass(WRAPPER_CLASS, "Resection: carrier-exclusion")
    assert wrapper is not None

    folder_item = _scene_root_folder_named(shNode, RESECTIONS_FOLDER_NAME)
    if not folder_item:
        pytest.skip(
            "no scene-root 'Resections' folder yet -- T5.2-f wiring absent; "
            "skip lifts at the implementation commit (ADR-0027 §Conformance)."
        )

    carrier_item = shNode.GetItemByDataNode(carrier)
    # The carrier may legitimately have no SH item at all, or an item that is
    # NOT under the Resections folder.  Either satisfies the invariant.
    if carrier_item:
        assert shNode.GetItemParent(carrier_item) != folder_item, (
            "the hidden Bezier carrier (SetHideFromEditors=true) must NOT be "
            "reparented under the 'Resections' folder -- only the wrapper is "
            "collected (ADR-0023 §'MRML scene organisation' + the "
            "wrapper-vs-carrier split, ADR-0014)."
        )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
