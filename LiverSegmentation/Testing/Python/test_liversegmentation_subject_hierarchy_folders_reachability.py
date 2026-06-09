# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""T5.2-f -- the shared SH-folder utility is reachable from LiverSegmentation.

ADR-0023 §"MRML scene organisation" + §Conformance [test]: each node-creating
module collects its nodes under a per-stage Subject-Hierarchy folder.  T5.2-f
replaces ``LiverSegmentation._collectUnderAnatomyFolder``'s open-coded
lookup/lazy-create/reparent dance with a single wrapped-C++ call::

    from vtkSlicerSubjectHierarchyFoldersPython import vtkSlicerSubjectHierarchyFolders
    vtkSlicerSubjectHierarchyFolders.CollectUnderFolder(
        slicer.mrmlScene, node, vtkSlicerSubjectHierarchyFolders.GetAnatomyFolderName())

Two pinned invariants:

  1. The wrapped utility ``vtkSlicerSubjectHierarchyFolders`` is importable
     from the module name ``vtkSlicerSubjectHierarchyFoldersPython`` and its
     ``CollectUnderFolder`` static method is callable from Python (the
     Python/C++ boundary, ADR-0004).
  2. Anatomy placement still works through the utility: a node collected
     under the Anatomy folder name lands under a scene-root folder of that
     name (behaviour preserved across the ``_collectUnderAnatomyFolder``
     rewrite -- ADR-0003 §"refactors that preserve behaviour").

Wrapped-C++-from-Python reachability can ONLY be verified under a launched
Slicer (the wrapped kit is loaded into the interpreter there); bare
``PythonSlicer -m pytest`` cannot import the kit nor reach ``slicer.mrmlScene``,
so this skips cleanly.  RED now -- the kit does not exist yet, so the import
and the placement both fail/skip; green once the implementer lands the kit +
the LiverSegmentation rewrite (ADR-0027 §Conformance: the skip lifts at the
implementation commit).
"""

from __future__ import annotations

import pytest

WRAPPED_MODULE = "vtkSlicerSubjectHierarchyFoldersPython"
UTILITY_CLASS = "vtkSlicerSubjectHierarchyFolders"
ANATOMY_FOLDER_NAME = "Anatomy"


def _utility_or_skip():
    """Import the wrapped SH-folder utility class, or skip cleanly.

    Skips under bare PythonSlicer (no launched interpreter loads the wrapped
    kit) and pre-implementation (kit absent).
    """
    from conftest import _import_slicer_or_skip, _require_mrml_scene

    _require_mrml_scene()
    _import_slicer_or_skip()

    wrapped = pytest.importorskip(
        WRAPPED_MODULE,
        reason=(
            f"{WRAPPED_MODULE} not importable -- the T5.2-f "
            f"{UTILITY_CLASS} kit is not built / not on sys.path (RED "
            "pre-implementation, or running outside a launched Slicer that "
            "loads the wrapped kit).  Skip lifts at the implementation "
            "commit (ADR-0027 §Conformance)."
        ),
    )
    utility = getattr(wrapped, UTILITY_CLASS, None)
    if utility is None:
        pytest.skip(
            f"{WRAPPED_MODULE} imported but {UTILITY_CLASS} symbol absent -- "
            "kit wrapping incomplete."
        )
    return utility


def test_utility_importable_and_collect_method_callable():
    """``vtkSlicerSubjectHierarchyFolders.CollectUnderFolder`` is callable.

    ADR-0004 (Python/C++ boundary) + ADR-0023 §Conformance [test]: the wrapped
    static method is the single entry the LiverSegmentation rewrite calls.
    """
    utility = _utility_or_skip()
    assert hasattr(utility, "CollectUnderFolder"), (
        f"{UTILITY_CLASS} must expose the static CollectUnderFolder method "
        "the LiverSegmentation rewrite calls (ADR-0023 §'MRML scene "
        "organisation')."
    )
    assert callable(utility.CollectUnderFolder)
    # The Anatomy folder-name constant accessor the call site references.
    assert hasattr(utility, "GetAnatomyFolderName"), (
        f"{UTILITY_CLASS} must export the Anatomy folder-name constant "
        "(ADR-0023 §'MRML scene organisation' string table)."
    )
    assert utility.GetAnatomyFolderName() == ANATOMY_FOLDER_NAME


def test_anatomy_placement_through_utility():
    """A node collected via the utility lands under a scene-root "Anatomy" folder.

    ADR-0023 §"MRML scene organisation" [test]: behaviour preserved across the
    ``_collectUnderAnatomyFolder`` rewrite (ADR-0003 §"refactors that preserve
    behaviour").  Idempotent: a second call reuses the same folder.
    """
    utility = _utility_or_skip()
    import slicer  # noqa: PLC0415 -- resolved live under launched Slicer

    scene = slicer.mrmlScene
    scene.Clear(0)
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(scene)
    if shNode is None:
        pytest.skip("no Subject-Hierarchy node available.")

    folder_name = utility.GetAnatomyFolderName()

    first = scene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Anatomy: liver")
    assert utility.CollectUnderFolder(scene, first, folder_name) is True

    folder_item = shNode.GetItemChildWithName(shNode.GetSceneItemID(), folder_name)
    assert folder_item, (
        f"no scene-root '{folder_name}' folder after CollectUnderFolder -- "
        "the utility must lazily create the per-stage folder (ADR-0023 "
        "§'MRML scene organisation')."
    )
    first_item = shNode.GetItemByDataNode(first)
    assert shNode.GetItemParent(first_item) == folder_item

    # Idempotency: a second node reuses the SAME folder (no duplicate).
    second = scene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Anatomy: tumor")
    assert utility.CollectUnderFolder(scene, second, folder_name) is True
    folder_item_again = shNode.GetItemChildWithName(shNode.GetSceneItemID(), folder_name)
    assert folder_item_again == folder_item, (
        "second CollectUnderFolder minted a duplicate folder -- the utility "
        "must reuse the existing per-stage folder (ADR-0023 §Conformance: "
        "folders exist after typical workflow use, not one-per-call)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
