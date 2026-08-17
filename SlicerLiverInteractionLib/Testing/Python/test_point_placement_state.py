# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital.  All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.
"""Unit skeletons for the shared ``PointPlacementState`` display-node accessors.

ADR-0038 §"Shared home + names" extracts
``VascularTerritoriesLib.TerritoryInteractionState`` (the arm / active /
module-active / carrier accessors on a display node) into the shared
``SlicerLiverInteractionLib`` package as ``PointPlacementState``, with the
attribute-key namespace PARAMETERIZED per consumer.  Today the territory
module hard-codes ``VascularTerritories.Armed`` etc.; the shared base must
let each consumer (vascular territories, volumetry, resection) get its OWN
keys on its OWN display node, so two consumers' arm/active/carrier state
never collide (ADR-0038 §"Base extension" -- the base carries no
data-model knowledge, only the parameterized interaction channel).

The critical invariant beyond a plain rename: LayerDM interaction state
(arm / active / module-active / carrier) MUST live on the shared MRML
display node, not a Python pipeline instance (ADR-0032/0033; the
LayerDM-state-on-the-display-node lesson).  These accessors are the
read/write channel both the widget/table side and the manager-created
Pipeline read back through, so the base can only carry them AS display-node
accessors.

HARNESS: bare ``PythonSlicer -m pytest``.  The accessors are pure Python
over a ``SetAttribute`` / ``GetAttribute`` / node-reference surface -- a
plain FAKE display node (below) satisfies the contract with no live scene,
so this RUNS bare AND launched.  (The launched harness additionally proves
a real ``vtkMRMLDisplayNode`` honours the same accessor calls.)

The SUT does not exist yet.  Per ADR-0027 red->skip the import is guarded
and every test SKIP-PENDINGs on ``ImportError``; the skips lift when the
implementer lands ``SlicerLiverInteractionLib/PointPlacementState.py``.

References
----------
* ADR-0038 -- §"Shared home + names" names ``PointPlacementState`` and the
  parameterized attribute-key namespace.
* ADR-0032 / ADR-0033 -- interaction through the LayerDM Pipeline seam +
  hover discipline; the arm/hover/grab channel lives on the display node.
* ADR-0027 -- invariant-test-first (red->skip lifecycle).
* VascularTerritories/VascularTerritoriesLib/TerritoryInteractionState.py --
  the origin these accessors generalise (namespace parameterized).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PY_DIR = REPO_ROOT / "SlicerLiverInteractionLib"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

_PENDING = (
    "PointPlacementState not yet implemented -- the ADR-0038 extraction "
    "(SlicerLiverInteractionLib/PointPlacementState.py) has not landed "
    "(ADR-0027 red->skip)."
)


def _import_state():
    """Import the shared state helper or SKIP-PENDING when it is absent.

    PROPOSED seam (sharpen at landing).  The base parameterizes the
    attribute-key namespace per consumer.  The most likely shape is a small
    class bound to a namespace prefix::

        class PointPlacementState:
            def __init__(self, namespace: str) -> None: ...
            def set_armed(self, displayNode, armed: bool) -> None: ...
            def is_armed(self, displayNode) -> bool: ...
            def set_module_active(self, displayNode, active: bool) -> None: ...
            def is_module_active(self, displayNode) -> bool: ...
            def set_active(self, displayNode, key: str | None) -> None: ...
            def get_active(self, displayNode) -> str | None: ...
            def set_carrier(self, displayNode, carrier) -> None: ...
            def get_carrier(self, displayNode): ...

    The accessors preserve TerritoryInteractionState's semantics: armed is
    a "1"/"0" string attribute; module-active reads ACTIVE unless
    explicitly closed ("0"); active is the empty string -> ``None``; the
    carrier is a typed node-reference role and ``set_carrier`` fires an
    explicit ``Modified()``.
    """
    try:
        from PointPlacementState import PointPlacementState
    except ImportError:
        pytest.skip(_PENDING)
    return PointPlacementState


class _FakeDisplayNode:
    """A minimal display-node double: attribute bag + one node-ref role.

    Enough to exercise the pure-Python accessor logic bare -- SetAttribute
    / GetAttribute / SetNodeReferenceID / GetNodeReference / Modified.  The
    launched harness swaps in a real ``vtkMRMLDisplayNode`` to prove the
    same calls land on the wrapped node.
    """

    def __init__(self):
        self._attrs: dict[str, str] = {}
        self._refs: dict[str, object] = {}
        self.modified_count = 0

    def SetAttribute(self, key, value):  # noqa: N802 - VTK verb
        self._attrs[key] = value

    def GetAttribute(self, key):  # noqa: N802 - VTK verb
        return self._attrs.get(key)

    def SetNodeReferenceID(self, role, node_id):  # noqa: N802 - VTK verb
        self._refs[role] = node_id

    def GetNodeReference(self, role):  # noqa: N802 - VTK verb
        return self._refs.get(role)

    def Modified(self):  # noqa: N802 - VTK verb
        self.modified_count += 1

    # Attribute-bag inspection for the isolation assertions (not a VTK verb).
    def raw_keys(self):
        return set(self._attrs)


class _FakeCarrier:
    def __init__(self, node_id):
        self._id = node_id

    def GetID(self):  # noqa: N802 - VTK verb
        return self._id


# --------------------------------------------------------------------------- #
# Arm / module-active / active accessors on a display node
# --------------------------------------------------------------------------- #


def test_arm_state_round_trips_on_the_display_node():
    """Arm state written by one side reads back on the SAME display node.

    The interaction state MUST live on the shared MRML display node, not a
    pipeline instance (ADR-0032/0033) -- so the accessor writes onto the
    node and reads it back, and a fresh (unset) node reads DISARMED.
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    assert state.is_armed(node) is False, "a fresh node must read DISARMED."
    state.set_armed(node, True)
    assert state.is_armed(node) is True
    state.set_armed(node, False)
    assert state.is_armed(node) is False


def test_module_active_defaults_open_and_closes_only_on_explicit_zero():
    """Module-active reads ACTIVE unless EXPLICITLY closed (the "0" opt-in).

    LayerDM creates the placement Pipelines the moment the display node
    enters the scene (before any ``enter()``); a gesture must still land in
    that window, so an UNSET flag reads active and only an explicit
    ``set_module_active(False)`` declines (TerritoryInteractionState
    semantics, preserved by the base).
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    assert state.is_module_active(node) is True, "an unset flag must read ACTIVE."
    state.set_module_active(node, False)
    assert state.is_module_active(node) is False
    state.set_module_active(node, True)
    assert state.is_module_active(node) is True


def test_overlay_gate_defaults_closed_and_opens_only_on_explicit_enter():
    """The OVERLAY gate is the mirror image: unset reads CLOSED.

    Drawing and gesture-accepting are two different questions.  LayerDM
    builds the Pipelines the moment the display node enters the scene --
    which on a scene load happens with no widget in play at all -- and an
    overlay drawn in that window is clutter over whatever module the surgeon
    actually has open.  So the overlay gate opens ONLY on an explicit
    ``set_overlays_visible(True)`` from the owning module's ``enter()``,
    while ``is_module_active`` keeps its optimistic default (a declined
    click is a lost gesture; a not-yet-drawn overlay costs nothing).
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    assert state.overlays_visible(node) is False, (
        "an unset overlay gate must read CLOSED -- no enter() has run."
    )
    state.set_overlays_visible(node, True)
    assert state.overlays_visible(node) is True
    state.set_overlays_visible(node, False)
    assert state.overlays_visible(node) is False

    # The two gates are independent channels: closing the overlay gate must
    # not decline placement, and vice versa.
    assert state.is_module_active(node) is True
    state.set_module_active(node, False)
    state.set_overlays_visible(node, True)
    assert state.overlays_visible(node) is True
    assert state.is_module_active(node) is False


def test_overlay_gate_from_another_session_reads_closed():
    """A gate value THIS session did not write reads CLOSED.

    Display-node attributes are serialized into the scene, so a scene saved
    with the overlays up carries the gate value with it.  Re-opened in a
    later session -- where the owning module may never be opened, and no
    widget therefore exists to scrub the flag -- the persisted value must NOT
    resurrect the overlays.  The gate is keyed on a per-session nonce, so any
    foreign value reads closed.
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    state.set_overlays_visible(node, True)
    live_value = node.GetAttribute("Volumetry.OverlaySession")
    assert live_value, "an opened gate must record a value on the node."

    # A node arriving from a scene saved by an EARLIER session: same key,
    # different (stale) value.
    stale = _FakeDisplayNode()
    stale.SetAttribute("Volumetry.OverlaySession", live_value + "-earlier-session")
    assert state.overlays_visible(stale) is False, (
        "a persisted gate value from another session must read CLOSED; the "
        "overlays would otherwise resurrect on a scene load with the owning "
        "module never opened."
    )

    # The naive boolean encodings a future refactor might reach for must not
    # read open either.
    for value in ("1", "true", "True", "yes"):
        legacy = _FakeDisplayNode()
        legacy.SetAttribute("Volumetry.OverlaySession", value)
        assert state.overlays_visible(legacy) is False, (
            f"the gate must not read {value!r} as open -- only this session's "
            "own token opens it."
        )


def test_active_key_empty_reads_none():
    """The active key round-trips; the empty string reads back as ``None``."""
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    assert state.get_active(node) is None
    state.set_active(node, "SeedGroupA")
    assert state.get_active(node) == "SeedGroupA"
    state.set_active(node, None)
    assert state.get_active(node) is None


def test_carrier_binds_as_node_ref_and_fires_modified():
    """Binding a carrier writes the node-reference role AND fires Modified.

    ADR-0032/0033: a node-reference change does not reliably emit
    ``ModifiedEvent``, so the accessor fires an explicit ``Modified()`` to
    drive LayerDM's ``UpdatePipeline`` on every view (the
    TerritoryInteractionState.set_carrier contract, preserved).
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()
    carrier = _FakeCarrier("vtkMRMLVolumetrySeedsNode1")

    state.set_carrier(node, carrier)
    assert state.get_carrier(node) == "vtkMRMLVolumetrySeedsNode1"
    assert node.modified_count >= 1, (
        "set_carrier must fire an explicit Modified() (ADR-0032/0033 -- a "
        "node-reference change does not reliably emit ModifiedEvent)."
    )


def test_grabbing_flag_round_trips_and_defaults_off():
    """The drag-in-flight (grabbing) flag round-trips; a fresh node reads OFF.

    A point drag relocates the grabbed point on every mouse-move, each firing
    the carrier's ``Modified``; a widget/table observing the carrier reads
    this flag off the SHARED display node to defer its expensive full rebuild
    until the drag ends (ADR-0037 §Decision 3 performance).  The Pipeline sets
    it on grab and clears it on release, so like the arm flag it MUST live on
    the display node, not the pipeline instance.
    """
    PointPlacementState = _import_state()
    state = PointPlacementState("Volumetry")
    node = _FakeDisplayNode()

    assert state.is_grabbing(node) is False, "a fresh node must read NOT grabbing."
    state.set_grabbing(node, True)
    assert state.is_grabbing(node) is True
    state.set_grabbing(node, False)
    assert state.is_grabbing(node) is False


# --------------------------------------------------------------------------- #
# Namespace parameterization -- two consumers, independent keys/nodes
# --------------------------------------------------------------------------- #


def test_two_namespaces_use_independent_attribute_keys():
    """Two consumers with distinct namespaces get DISJOINT attribute keys.

    ADR-0038 §"Shared home + names": the base parameterizes the
    attribute-key namespace so each consumer gets its own keys.  Arming a
    territory display node under the "VascularTerritories" namespace and a
    volumetry display node under the "Volumetry" namespace must write
    NON-OVERLAPPING attribute keys -- no cross-consumer collision.
    """
    PointPlacementState = _import_state()
    terr_state = PointPlacementState("VascularTerritories")
    vol_state = PointPlacementState("Volumetry")

    terr_node = _FakeDisplayNode()
    vol_node = _FakeDisplayNode()

    terr_state.set_armed(terr_node, True)
    vol_state.set_armed(vol_node, True)

    # The two consumers must not share any attribute key on their own nodes.
    assert terr_node.raw_keys().isdisjoint(vol_node.raw_keys()), (
        "distinct namespaces must yield DISJOINT attribute keys (no "
        "cross-consumer collision on the shared display node)."
    )
    # Each namespace's key must carry its own prefix (the parameterization).
    assert any(k.startswith("VascularTerritories") for k in terr_node.raw_keys())
    assert any(k.startswith("Volumetry") for k in vol_node.raw_keys())


def test_one_namespace_does_not_read_anothers_state():
    """A consumer reads DISARMED for another consumer's armed node.

    Even given the SAME physical display node, the "Volumetry" namespace
    must not read the "VascularTerritories" arm flag as its own -- the
    namespaced key isolation holds when two consumers accidentally share a
    node (ADR-0038 parameterized namespace).
    """
    PointPlacementState = _import_state()
    terr_state = PointPlacementState("VascularTerritories")
    vol_state = PointPlacementState("Volumetry")
    shared_node = _FakeDisplayNode()

    terr_state.set_armed(shared_node, True)

    assert terr_state.is_armed(shared_node) is True
    assert vol_state.is_armed(shared_node) is False, (
        "the Volumetry namespace must NOT read the VascularTerritories arm "
        "flag -- namespaced keys are isolated."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
