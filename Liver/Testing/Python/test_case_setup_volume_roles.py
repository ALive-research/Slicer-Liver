# Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
# Distributed under the OSI-approved BSD 3-Clause License.

"""Stage-1 Case-Setup volume-role vocabulary + tagging seam (ADR-0029 §Stage 1).

Pins the *logic seam* behind Stage 1's role-tagging job -- the GL-free,
Qt-free half of Case Setup (ADR-0004 §"Python/C++ boundary": the Case Setup
panel is a ``Liver``-shell Qt widget, but the vocabulary + the write-side
tagging kernel it drives are a separate, testable pure-Python seam).

WHAT IS PINNED -- a NEW shared role-vocabulary + tagging module (to be
implemented later) importable by BOTH the ``Liver`` shell (Case Setup, the
role WRITER) and ``LiverSegmentation`` (Stage 2, the role READER):

    LiverSegmentationLib.roles

    LIVER_ROLE_ATTRIBUTE = "LiverRole"
    LIVER_ROLES = ("Native", "Arterial", "PortalVenous", "Delayed", "Other")
    LIVER_ROLE_PORTAL_VENOUS = "PortalVenous"        # convenience constant

    set_volume_role(volume_node, role) -> bool
        Validate ``role`` is in ``LIVER_ROLES`` and write
        ``volume_node.SetAttribute(LIVER_ROLE_ATTRIBUTE, role)``; return True.
        Return False (no-op) on an unknown role or a None volume, never raising.

-- WHY A SHARED MODULE --
Today the vocabulary is DRIFTED across three places: ``LiverSegmentation.py``
carries ad-hoc constants (``LIVER_ROLE_ATTRIBUTE`` / ``LIVER_ROLE_PORTAL_VENOUS``),
``Docs/architecture/ui-stage-1-case-setup.md`` lists the five values WITH spaces
("Portal venous", "Delayed/venous"), and ``Liver.py:_stage1IsComplete`` reads the
raw ``"LiverRole"`` string.  ADR-0029 §"Decision" makes Stage 1 the role WRITER
and Stage 2 the role READER of the SAME tag; the single shared module collapses
that drift to one machine-stable vocabulary (CamelCase, NO spaces -- human
labels are decoupled and live in the Qt panel).  The maintainer fixed the key
as ``"LiverRole"`` (the shipped scene-attribute key; the closed-vocab
Liver-prefix guardrail covers new MRML CLASSES, not scene-attribute keys) and
the five values as ``Native / Arterial / PortalVenous / Delayed / Other``.  No
SCT codes: phase roles are not ADR-0011 anatomy structures.

SCOPE: this file pins the WRITE side + the vocabulary.  The READ side --
``selectInputVolume`` (the ``PortalVenous`` reader in ``LiverSegmentation``, the
Stage-1 -> Stage-2 hand-off) -- is a separate deliverable and is exercised by
``LiverSegmentation/Testing/Python/test_liversegmentation_segment_input_selection.py``;
it is NOT re-exercised here.

-- WHY LAUNCHED-SLICER (invariant 2 + 3) --
The tagging + Stage-1-predicate invariants mint a ``vtkMRMLScalarVolumeNode`` on
the live ``slicer.mrmlScene``, so they run under the launched-Slicer harness and
SKIP CLEANLY under bare ``PythonSlicer -m pytest`` via the shared
``slicer_pytest_support`` guards.  GL-free: only node attributes + a scene-level
predicate are asserted -- no view / render window.  The vocabulary invariant
(1) needs no scene and runs everywhere the shared module imports.

-- WHY RED NOW --
``LiverSegmentationLib.roles`` does not exist yet, so every test skips-pending on
its import (``_roles_or_skip_pending``).  The skip lifts at the implementation
commit, at which point the tests ASSERT (ADR-0027 §Conformance -- the skip lifts
at the implementation commit).

See also:
  * Docs/adr/0029-stage1-case-setup-contract.md §Decision, §Conformance
  * Docs/adr/0023-unified-gui-stage-workflow.md §"Stage 1"
  * Docs/adr/0004-python-cpp-boundary.md  (the Qt panel vs the pure-Python seam)
  * Docs/adr/0027-invariant-test-first-v2-implementation.md  (RED / skip-pending)
  * Docs/architecture/ui-stage-1-case-setup.md §"Role tagging"
  * Liver/Liver.py  (LiverWidget._stage1IsComplete -- the shell predicate)
  * LiverSegmentation/LiverSegmentation.py  (the ad-hoc constants this collapses)
"""

from __future__ import annotations

import pytest

# The scene-attribute key + the machine-stable role vocabulary the shared module
# MUST expose.  Duplicated here as the assertion oracle (the test pins the
# contract; the module must match these EXACTLY).
EXPECTED_ROLE_ATTRIBUTE = "LiverRole"
EXPECTED_ROLES = ("Native", "Arterial", "PortalVenous", "Delayed", "Other")
PORTAL_VENOUS = "PortalVenous"

SCALAR_VOLUME_CLASS = "vtkMRMLScalarVolumeNode"


# --------------------------------------------------------------------------- #
# Skip-guards (mirror LiverResections/Testing/Python/test_ensure_locator_node.py)
# --------------------------------------------------------------------------- #


def _slicer_or_skip():
    """Return the launched-Slicer ``slicer`` module, or skip under bare pytest."""
    from conftest import (  # type: ignore[import-not-found]
        _import_slicer_or_skip,
        _require_mrml_scene,
    )

    _require_mrml_scene()
    return _import_slicer_or_skip()


def _roles_or_skip_pending():
    """Import the shared role module or SKIP-PENDING (ADR-0027).

    RED == ``LiverSegmentationLib.roles`` is not built yet; the skip lifts at
    the implementation commit, at which point the tests ASSERT.
    """
    try:
        from LiverSegmentationLib import roles
    except Exception as exc:  # pragma: no cover - import-environment dependent
        pytest.skip(
            f"LiverSegmentationLib.roles not importable ({exc!r}) -- the "
            "ADR-0029 §Stage 1 shared role vocabulary + tagging seam has not "
            "landed.  Skip lifts at the implementation commit (ADR-0027)."
        )
    return roles


def _set_volume_role_or_skip_pending(roles):
    """Return the ``set_volume_role`` seam or SKIP-PENDING (ADR-0027)."""
    seam = getattr(roles, "set_volume_role", None)
    if not callable(seam):
        pytest.skip(
            "LiverSegmentationLib.roles.set_volume_role not present -- the "
            "ADR-0029 §Stage 1 tagging seam has not landed.  Skip lifts at the "
            "implementation commit (ADR-0027)."
        )
    return seam


def _add_scalar_volume(slicer):
    """Mint a scalar volume on the live scene (caller tears it down)."""
    node = slicer.mrmlScene.AddNewNodeByClass(SCALAR_VOLUME_CLASS)
    if node is None:
        pytest.skip(f"{SCALAR_VOLUME_CLASS} not registered in this build.")
    return node


# --------------------------------------------------------------------------- #
# Invariant 1 -- the vocabulary contract (no scene needed)
# --------------------------------------------------------------------------- #


def test_role_vocabulary_contract():
    """Invariant 1: the shared module exposes the exact key + ordered values.

    ADR-0029 §Decision fixes Stage 1 as the role writer of the ``LiverRole``
    scene attribute; the maintainer fixed the key (``"LiverRole"``, the shipped
    key) and the five machine-stable CamelCase values in order
    (``Native / Arterial / PortalVenous / Delayed / Other``).  Human labels are
    decoupled (they live in the Qt panel); the stored values carry NO spaces.
    ``PortalVenous`` -- the Stage-1 -> Stage-2 hand-off value (ADR-0024
    §"Per-structure micro-workflows") -- must be among them.
    """
    roles = _roles_or_skip_pending()

    assert getattr(roles, "LIVER_ROLE_ATTRIBUTE", None) == EXPECTED_ROLE_ATTRIBUTE, (
        "the shared module's LIVER_ROLE_ATTRIBUTE must be the shipped scene key "
        f"{EXPECTED_ROLE_ATTRIBUTE!r} (ADR-0029 §Decision); got "
        f"{getattr(roles, 'LIVER_ROLE_ATTRIBUTE', None)!r}."
    )

    values = tuple(getattr(roles, "LIVER_ROLES", ()))
    assert values == EXPECTED_ROLES, (
        "LIVER_ROLES must be the five machine-stable CamelCase values IN ORDER "
        f"{EXPECTED_ROLES!r} (ADR-0029 §Decision); got {values!r}."
    )

    assert PORTAL_VENOUS in values, (
        f"{PORTAL_VENOUS!r} must be in LIVER_ROLES -- it is the Stage-1 -> "
        "Stage-2 hand-off value (ADR-0024 §'Per-structure micro-workflows')."
    )

    assert getattr(roles, "LIVER_ROLE_PORTAL_VENOUS", None) == PORTAL_VENOUS, (
        "LIVER_ROLE_PORTAL_VENOUS convenience constant must equal "
        f"{PORTAL_VENOUS!r} (the value LiverSegmentation reads); got "
        f"{getattr(roles, 'LIVER_ROLE_PORTAL_VENOUS', None)!r}."
    )

    for value in values:
        assert " " not in value, (
            f"role value {value!r} must contain NO space -- stored values are "
            "machine-stable; human labels with spaces live in the Qt panel "
            "(ADR-0029 §Decision)."
        )


# --------------------------------------------------------------------------- #
# Invariant 2 -- the tagging seam (write side)
# --------------------------------------------------------------------------- #


def test_set_volume_role_tags_portal_venous():
    """Invariant 2a: ``set_volume_role(vol, "PortalVenous")`` writes the tag.

    The seam validates the role is in the vocabulary and writes it to the
    ``LiverRole`` attribute, returning True (ADR-0029 §Decision -- Stage 1 is
    the role writer).
    """
    slicer = _slicer_or_skip()
    roles = _roles_or_skip_pending()
    set_volume_role = _set_volume_role_or_skip_pending(roles)
    scene = slicer.mrmlScene

    volume = _add_scalar_volume(slicer)
    try:
        result = set_volume_role(volume, PORTAL_VENOUS)
        assert result is True, (
            "set_volume_role(vol, 'PortalVenous') must return True on a valid "
            f"role; got {result!r}."
        )
        assert volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE) == PORTAL_VENOUS, (
            "set_volume_role must write the role to the 'LiverRole' attribute; "
            f"got {volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE)!r}."
        )
    finally:
        scene.RemoveNode(volume)


def test_set_volume_role_round_trips_every_role():
    """Invariant 2b: each of the five roles round-trips through the seam.

    Every value in ``LIVER_ROLES`` is a valid write; the attribute reads back
    exactly the value written (ADR-0029 §Decision -- machine-stable values).
    """
    slicer = _slicer_or_skip()
    roles = _roles_or_skip_pending()
    set_volume_role = _set_volume_role_or_skip_pending(roles)
    scene = slicer.mrmlScene

    volume = _add_scalar_volume(slicer)
    try:
        for role in EXPECTED_ROLES:
            result = set_volume_role(volume, role)
            assert result is True, (
                f"set_volume_role(vol, {role!r}) must return True for a "
                f"vocabulary value; got {result!r}."
            )
            assert volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE) == role, (
                f"role {role!r} must round-trip through the 'LiverRole' "
                f"attribute; got {volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE)!r}."
            )
    finally:
        scene.RemoveNode(volume)


def test_set_volume_role_rejects_unknown_role_as_noop():
    """Invariant 2c: an unknown role is a no-op returning False.

    An off-vocabulary role must NOT be written; the seam returns False and
    leaves any prior attribute value untouched (ADR-0029 §Decision -- the
    vocabulary is closed; the panel only offers the five values).
    """
    slicer = _slicer_or_skip()
    roles = _roles_or_skip_pending()
    set_volume_role = _set_volume_role_or_skip_pending(roles)
    scene = slicer.mrmlScene

    volume = _add_scalar_volume(slicer)
    try:
        # Seed a known-good prior tag so we can prove the bad write is a no-op.
        assert set_volume_role(volume, PORTAL_VENOUS) is True
        result = set_volume_role(volume, "bogus")
        assert result is False, (
            "set_volume_role(vol, 'bogus') must return False for an "
            f"off-vocabulary role; got {result!r}."
        )
        assert volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE) == PORTAL_VENOUS, (
            "an unknown-role write must leave the prior 'LiverRole' value "
            f"untouched; got {volume.GetAttribute(EXPECTED_ROLE_ATTRIBUTE)!r}."
        )
    finally:
        scene.RemoveNode(volume)


def test_set_volume_role_none_volume_returns_false():
    """Invariant 2d: a None volume returns False without raising.

    The seam guards its inputs -- a None volume is a no-op returning False, not
    an exception (defensive; the Case Setup panel may call it before a volume is
    selected).
    """
    roles = _roles_or_skip_pending()
    set_volume_role = _set_volume_role_or_skip_pending(roles)

    # No scene needed: the None-guard must short-circuit before touching MRML,
    # so this branch runs even under bare pytest (once the seam exists).
    result = set_volume_role(None, PORTAL_VENOUS)
    assert result is False, (
        "set_volume_role(None, ...) must return False without raising; got "
        f"{result!r}."
    )


# --------------------------------------------------------------------------- #
# Invariant 3 -- Stage-1 completion predicate
# --------------------------------------------------------------------------- #
#
# The Liver shell's Stage-1 predicate is ``LiverWidget._stage1IsComplete``
# (Liver.py) -- "done iff at least one scalar volume carries a ``LiverRole``
# attribute" (ADR-0029 §"Stage 1 functional contract"; the shell reads it via
# ``slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode')`` + ``GetAttribute``).
#
# REACHABILITY DECISION (per the docstring mandate): the SHELL-WIDGET path is
# pinned by the sibling ``test_liver_shell_isstagecomplete.py`` (it instantiates
# ``LiverWidget`` behind ``_require_qt_widget`` and asserts the predicate flips).
# Here we pin the EQUIVALENT SCENE-LEVEL predicate the shell body evaluates -- a
# scalar volume carrying the ``LiverRole`` attribute is discoverable via
# ``getNodesByClass`` + ``GetAttribute`` -- because it is the robust GL-free /
# Qt-free path and it closes the loop from the tagging seam (invariant 2) to the
# completion signal without depending on the shell widget being instantiable in
# this dir's harness.  The shell-widget coupling is intentional: this predicate
# IS the body of ``_stage1IsComplete``, so tagging via ``set_volume_role`` and
# the shell reporting complete are the same fact asserted at two layers.


def _scene_reports_any_liver_role(slicer):
    """Mirror ``LiverWidget._stage1IsComplete``'s body at the scene level.

    Returns True iff at least one scalar volume in the live scene carries a
    ``LiverRole`` attribute (ADR-0029 §"Stage 1 functional contract").  Uses
    ``slicer.util.getNodesByClass`` -- the same helper the shell uses -- which
    unregisters the returned collection so the launched leak discipline holds.
    """
    for node in slicer.util.getNodesByClass(SCALAR_VOLUME_CLASS):
        if node.GetAttribute(EXPECTED_ROLE_ATTRIBUTE):
            return True
    return False


def test_stage1_complete_after_tagging_any_role():
    """Invariant 3: tagging any role makes the Stage-1 predicate report complete.

    After ``set_volume_role`` tags a scalar volume with ANY of the five roles,
    the scene-level Stage-1 predicate (the body of
    ``LiverWidget._stage1IsComplete``, ADR-0029 §"Stage 1 functional contract")
    must report complete -- and an otherwise-untagged scene must NOT.  This
    closes the loop from the tagging seam (invariant 2) to Stage 1's commit
    signal.
    """
    slicer = _slicer_or_skip()
    roles = _roles_or_skip_pending()
    set_volume_role = _set_volume_role_or_skip_pending(roles)
    scene = slicer.mrmlScene

    volume = _add_scalar_volume(slicer)
    try:
        # A freshly-minted, untagged volume must NOT satisfy Stage 1.
        assert _scene_reports_any_liver_role(slicer) is False, (
            "an untagged scalar volume must NOT satisfy the Stage-1 predicate "
            "(ADR-0029 §'Stage 1 functional contract' -- attribute presence is "
            "the gate)."
        )

        assert set_volume_role(volume, "Native") is True
        assert _scene_reports_any_liver_role(slicer) is True, (
            "after tagging a scalar volume with a LiverRole, the Stage-1 "
            "predicate must report complete (the body of "
            "LiverWidget._stage1IsComplete, ADR-0029 §'Stage 1 functional "
            "contract')."
        )
    finally:
        scene.RemoveNode(volume)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
