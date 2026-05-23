# ==============================================================================
#
#  Distributed under the OSI-approved BSD 3-Clause License.
#
#   Copyright (c) 2026, The Intervention Centre, Oslo University Hospital. All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions
#   are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
#   * Neither the name of Oslo University Hospital nor the names
#     of Contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#   HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#   SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#   LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#   DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#   THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#   (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# ==============================================================================

"""Python-facing factory helpers for the territories node hierarchy.

Wraps the C++ ``vtkSlicerVascularTerritoriesLogic`` so Python consumers
(Stage 4 overlay, Stage 5 volumetry, the ``.lrp.json`` writer) can
create standard-Couinaud or surgeon-custom territory nodes without
threading the C++ logic instance through their own state.

The factories ensure the underlying ``vtkSlicerVascularTerritoriesLogic``
exists in ``slicer.modules`` (registers the node classes + wires the
Subject Hierarchy folder per ADR-0023 §"MRML scene organisation") and
then delegate to ``slicer.mrmlScene.AddNewNodeByClass`` so the Logic's
``OnMRMLSceneNodeAdded`` observer places the new node under the
"Vascular Territories" folder.
"""

import slicer

# Test-context fallback Logic.  Slicer modules expose a singleton via
# ``slicer.modules.vascularterritories.logic()`` once the loadable
# module is built; outside that bootstrap (ctest Python runs that
# import this helper without the full module hosting) we construct a
# Logic on first call and reuse it so a fresh observer isn't attached
# to the scene on every factory invocation.
_fallbackLogic = None


def _ensureLogicInstantiated():
  """Return a specialized ``vtkSlicerVascularTerritoriesLogic``
  instance observing ``slicer.mrmlScene``.

  Prefers the instance the Module class created at startup-completion
  time (exposed as ``slicer.modules.vascularterritories.specializedLogic``)
  -- that is the one whose ``OnMRMLSceneNodeAdded`` observer drives
  Stage 4 Subject Hierarchy folder placement.  Falls back to a cached
  module-level instance for test contexts where the Module class did
  not run its bootstrap (e.g. when ``createStandardCouinaud`` is
  imported standalone from pytest).

  Note: ``slicer.modules.vascularterritories.logic()`` would return a
  *generic* ``vtkSlicerScriptedLoadableModuleLogic`` because this is a
  scripted module, so it cannot be used here -- only the specialized
  Logic carries the territory-aware ``OnMRMLSceneNodeAdded`` override.
  """
  module = getattr(slicer.modules, "vascularterritories", None)
  if module is not None and hasattr(module, "specializedLogic"):
    return module.specializedLogic
  global _fallbackLogic
  if _fallbackLogic is None:
    from vtkSlicerVascularTerritoriesModuleLogicPython import (
      vtkSlicerVascularTerritoriesLogic,
    )
    _fallbackLogic = vtkSlicerVascularTerritoriesLogic()
    _fallbackLogic.SetMRMLScene(slicer.mrmlScene)
    _fallbackLogic.RegisterNodes()
  return _fallbackLogic


def createStandardCouinaud(name="Auto Couinaud"):
  """Create + scene-add a ``vtkMRMLStdCouinaudTerritoriesNode``.

  Returns the new node, which on return is already parented under the
  "Vascular Territories" Subject Hierarchy folder (the Logic's
  ``OnMRMLSceneNodeAdded`` observer performs the placement before
  control returns to Python).

  :param name: User-visible node name (e.g. ``"Auto Couinaud"``)
               per architecture-doc §"Subject Hierarchy organisation".
  """
  _ensureLogicInstantiated()
  return slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLStdCouinaudTerritoriesNode", name)


def createCustomTerritories(name="Custom Territories"):
  """Create + scene-add a ``vtkMRMLCustomTerritoriesNode``.

  Sibling of :func:`createStandardCouinaud` for the Manual-tab path.
  """
  _ensureLogicInstantiated()
  return slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLCustomTerritoriesNode", name)
