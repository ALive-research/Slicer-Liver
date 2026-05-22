# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
#
# Python-wrapper test for the v2.0.0 vascular-territories node
# hierarchy (ADR-0023 §"Class abstraction for territories",
# Docs/architecture/territories-class-hierarchy.md, ADR-0004
# Python/C++ boundary).  Test-first scaffolding landed per ADR-0027 --
# Subject Hierarchy folder placement (invariant 7) requires the module
# Logic class which the implementer commit will supply.
#
# Run inside Slicer via ctest's slicer_add_python_unittest hook.
#
# ruff: noqa: F403, F405  # standard Slicer scripted-module wildcard-import pattern

import unittest

import slicer
from slicer.ScriptedLoadableModule import ScriptedLoadableModuleTest


class TerritoriesNodeWrapperTestCase(ScriptedLoadableModuleTest):
    """Smoke + invariant tests for the C++ territories MRML node family
    consumed via Slicer's Python wrappers."""

    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        # The runTest entry point keeps ScriptedLoadableModuleTest's
        # historical contract.  Delegate to the unittest-style methods
        # so they can also be invoked individually under pytest in
        # Testing/ (per ADR-0008 §2).
        self.setUp()
        self.test_subclasses_creatable_via_slicer_mrmlScene()
        self.setUp()
        self.test_polymorphic_method_dispatch()
        self.setUp()
        self.test_subject_hierarchy_folder_placement()
        self.setUp()
        self.test_couinaud_sct_codes_through_wrappers()

    # ------------------------------------------------------------------
    # Invariant 2 + 6 -- subclasses are creatable through Slicer's
    # scene API (which relies on RegisterNodeClass having run).  This
    # exercises both the vtkStandardNewMacro plumbing and the module
    # logic's RegisterNodes() side effect.
    # ------------------------------------------------------------------
    def test_subclasses_creatable_via_slicer_mrmlScene(self):
        couinaud = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLStdCouinaudTerritoriesNode", "Auto Couinaud")
        self.assertIsNotNone(
            couinaud,
            "vtkMRMLStdCouinaudTerritoriesNode not registered in scene "
            "-- module Logic RegisterNodes() must wire this up (impl).")
        self.assertEqual(couinaud.GetClassName(),
                         "vtkMRMLStdCouinaudTerritoriesNode")

        custom = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLCustomTerritoriesNode", "Custom watershed")
        self.assertIsNotNone(
            custom,
            "vtkMRMLCustomTerritoriesNode not registered in scene "
            "-- module Logic RegisterNodes() must wire this up (impl).")
        self.assertEqual(custom.GetClassName(),
                         "vtkMRMLCustomTerritoriesNode")

    # ------------------------------------------------------------------
    # Invariant 3 -- polymorphic GetMethod() through the Python
    # wrappers.  Downstream consumers (Stage 4 overlay, Stage 5
    # analysis, the .lrp.json writer) all live in Python and read the
    # discriminator through this method.
    # ------------------------------------------------------------------
    def test_polymorphic_method_dispatch(self):
        couinaud = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLStdCouinaudTerritoriesNode")
        custom = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLCustomTerritoriesNode")
        self.assertEqual(couinaud.GetMethod(), "standard-couinaud")
        self.assertEqual(custom.GetMethod(), "custom")

    # ------------------------------------------------------------------
    # Invariant 7 -- Subject Hierarchy folder placement.
    #
    # ADR-0023 §"MRML scene organisation" mandates that programmatic
    # node creation via the module logic places the node under the
    # "Vascular Territories" Subject Hierarchy folder.  This test
    # asserts the strong post-condition: before module-logic
    # creation, the folder either does not exist or holds 0 territory
    # nodes; after, it holds the new node.  Until the module Logic
    # class lands with the SH wiring, this assertion fails red.
    # ------------------------------------------------------------------
    def test_subject_hierarchy_folder_placement(self):
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        self.assertIsNotNone(shNode)

        # TODO(impl): once the VascularTerritories module Logic exposes
        # CreateStandardCouinaud()/CreateCustomTerritories() factory
        # entry points (per ADR-0023's Subject Hierarchy convention),
        # replace this scaffolding with the factory call.
        try:
            from territories_test_helpers import (  # type: ignore[import-not-found]
                createStandardCouinaud,
            )
        except ImportError:
            self.fail(
                "territories_test_helpers.createStandardCouinaud not "
                "yet importable -- the implementer commit per ADR-0023 "
                "§'MRML scene organisation' must add the Subject "
                "Hierarchy folder convention to the module Logic.")
            return

        node = createStandardCouinaud(name="Auto Couinaud (2026-05-22)")
        self.assertIsNotNone(node)

        # Folder must exist and the node must sit under it.
        folderItem = shNode.GetItemByName("Vascular Territories")
        self.assertNotEqual(
            folderItem, 0,
            "Subject Hierarchy folder 'Vascular Territories' not "
            "created by module Logic -- ADR-0023 §'MRML scene "
            "organisation' mandate not yet honoured.")
        nodeItem = shNode.GetItemByDataNode(node)
        self.assertEqual(
            shNode.GetItemParent(nodeItem), folderItem,
            "New territory node is not parented under 'Vascular "
            "Territories' folder.")

    # ------------------------------------------------------------------
    # Invariant 4 -- spot-check three pinned Couinaud SCT codes
    # through the Python wrapper.  The C++ test exhaustively covers
    # the full table; this is just a smoke test that the Python ABI
    # surfaces the same strings.
    # ------------------------------------------------------------------
    def test_couinaud_sct_codes_through_wrappers(self):
        couinaud = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLStdCouinaudTerritoriesNode")
        # SetSubdivision uses the C++ enum literal value (0 == I_VIII).
        couinaud.SetSubdivision(0)
        self.assertEqual(couinaud.GetSCTCode(0), "71133005",   # Segment I
                         "Couinaud Segment I SCT code mismatch")
        self.assertEqual(couinaud.GetSCTCode(1), "277956007",  # Segment II
                         "Couinaud Segment II SCT code mismatch")
        self.assertEqual(couinaud.GetSCTCode(7), "277962002",  # Segment VIII
                         "Couinaud Segment VIII SCT code mismatch")


if __name__ == "__main__":
    unittest.main()
