# 0028. Parameter node wrapper + UI custom attributes for v2.0 widgets

- **Status:** Accepted
- **Date:** 2026-05-21
- **Deciders:** R. Palomar
- **Diagrams:** code-shape examples inline.
- **PR:** <filled on merge>

## Context

Slicer 5.4 (May 2023) introduced the **parameter node wrapper**
mechanism, a Python decorator that pairs a typed parameter class with
a `vtkMRMLScriptedModuleNode`-backed parameter node, plus a UI
auto-binding helper that wires Qt widgets to parameter properties via
a custom `SlicerParameterName` attribute declared in the `.ui` file.

The pattern is documented in upstream Slicer-core at
`Base/Python/slicer/parameterNodeWrapper/` and surfaced as the
*idiomatic* way to write scripted module widgets going forward — most
new upstream modules and the Slicer-core scripted-module template
use it.

Slicer-Liver's existing scripted modules (`Liver/`, `LiverSegments/`,
`LiverVolumetry/`) **do not** use parameter node wrapping. They
follow the v1-era pattern: per-widget `valueChanged.connect(...)`
calls in `setup()`, per-handler boilerplate that pulls the widget
value and writes it onto the parameter node manually, and matching
read-back code for `onParameterNodeModified()`. Dozens of lines of
transactional code per module that does what one `connectParametersToQtWidgets`
call does idiomatically.

The maintainer flagged on 2026-05-21:

> *"For UI design — you are not to forget to enforce the use of the
> Slicer parameter node wrapper and Ui elements custom attributes /
> elements to make the connection effectively. This is going to save
> quite some transactional code and make more human readable."*

v2.0 ships substantial new widget code (the Liver-shell sidebar per
#410, the new `LiverSegmentation/` module per #409, the renamed
`VascularTerritories/` widget refactor per #408, and the renovated
Stage 4 + Stage 5 widgets). Adopting the modern pattern from the
start avoids re-writing the boilerplate twice.

The current v1 widget pattern looks like this (paraphrased from
`LiverSegments/LiverSegments.py`):

```python
class LiverSegmentsWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ...
        self.ui.addCenterlineSegmentButton.connect(
            'clicked(bool)', self.onAddCenterlineButton)
        self.ui.endPointsMarkupsSelector.connect(
            'nodeAddedByUser(vtkMRMLNode*)', self.newEndpointsListCreated)
        self.ui.vascularTerritoryId.connect(
            'currentIndexChanged(int)', self.updateParameterNodeFromGUI)
        # ... many more connect() calls ...

    def onParameterNodeModified(self, caller=None, event=None):
        # manual pull-from-parameter-node, push-to-widget for every field
        self.ui.someField.setValue(self._parameterNode.GetParameter("FieldName"))
        # ... many more push-to-widget calls ...

    def updateParameterNodeFromGUI(self, caller=None, event=None):
        # manual pull-from-widget, push-to-parameter-node for every field
        self._parameterNode.SetParameter("FieldName", str(self.ui.someField.value))
        # ... many more push-to-parameter-node calls ...
```

The parameter-node-wrapper version of the same thing:

```python
from slicer.parameterNodeWrapper import parameterNodeWrapper

@parameterNodeWrapper
class VascularTerritoriesParameters:
    vascularTerritoryId: int = 0
    activeMarkupsNode: "vtkMRMLMarkupsFiducialNode"
    # typed fields auto-bound; defaults declared inline


class VascularTerritoriesWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ...
        self._parameterNode = self.logic.getParameterNode()
        slicer.util.connectParametersToQtWidgets(
            self._parameterNode, self.ui)
        # Per-button signal/slot for action-buttons that aren't parameter-backed
        self.ui.addCenterlineSegmentButton.connect(
            'clicked(bool)', self.onAddCenterlineButton)
```

In the `.ui` file, each parameter-backed widget declares the binding
via a Qt custom property:

```xml
<property name="SlicerParameterName">
  <string>vascularTerritoryId</string>
</property>
```

Net: typed parameter dataclass + one helper call + per-widget
`SlicerParameterName` attribute replaces dozens of `connect()` +
per-handler pull/push lines per module.

## Decision

Every Slicer-Liver v2.0 scripted module that declares a parameter
node **uses the parameter node wrapper + `SlicerParameterName`
custom-attribute binding pattern**:

1. The module's `Logic` class exposes a typed parameter class
   decorated with `@parameterNodeWrapper` from
   `slicer.parameterNodeWrapper`. The class holds typed fields for
   every parameter the module persists into the
   `vtkMRMLScriptedModuleNode`.

2. Every Qt widget in the module's `.ui` file that is **parameter-
   backed** declares a `SlicerParameterName` custom property whose
   value is the typed field name from the parameter wrapper class.

3. The module's `Widget` class calls
   `slicer.util.connectParametersToQtWidgets(self._parameterNode, self.ui)`
   once in `setup()` (or its `enter()` callback per the upstream
   pattern). No per-widget `valueChanged.connect(...)` for
   parameter-backed widgets.

4. Per-widget `connect()` calls remain valid for **non-parameter-
   backed widgets**: action buttons that trigger orchestration
   (`[Compute]`, `[Add resection]`, `[+ Add centerline]`, etc.),
   read-only display labels, and event-driven affordances that
   don't map to a persistent parameter field.

### Code-shape example for the new LiverSegmentation module (#409)

```python
from slicer.parameterNodeWrapper import parameterNodeWrapper

@parameterNodeWrapper
class LiverSegmentationParameters:
    sourceVolume: "vtkMRMLScalarVolumeNode"
    canonicalSegmentation: "vtkMRMLSegmentationNode"
    activeStructure: str = "Liver"
    safetyMargin_mm: float = 10.0
```

In `LiverSegmentation/Resources/UI/LiverSegmentation.ui` (Qt Designer
fragments):

```xml
<widget class="qMRMLNodeComboBox" name="sourceVolumeSelector">
  <property name="SlicerParameterName">
    <string>sourceVolume</string>
  </property>
  <!-- ... -->
</widget>

<widget class="QDoubleSpinBox" name="safetyMarginSpinBox">
  <property name="SlicerParameterName">
    <string>safetyMargin_mm</string>
  </property>
  <!-- ... -->
</widget>
```

In `LiverSegmentation.py`:

```python
class LiverSegmentationWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/LiverSegmentation.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        self.logic = LiverSegmentationLogic()
        self._parameterNode = self.logic.getParameterNode()
        slicer.util.connectParametersToQtWidgets(
            self._parameterNode, uiWidget)
        # Action buttons (not parameter-backed) — standard connect
        self.ui.runTotalSegmentatorButton.connect(
            'clicked(bool)', self.onRunTotalSegmentator)
```

### Scope

Applies to:

- **`LiverSegmentation/`** (new module, #409).
- **`Liver/` shell** (sidebar refactor, #410).
- **`VascularTerritories/`** (renamed from `LiverSegments/`, content
  refactor, #408). Per the scope: the rename PR opportunistically
  introduces the parameter-wrapper pattern as part of the refactor.
- **`LiverVolumetry/`** widget refactor (covered when the Stage 5
  panel work lands as an implementation issue — currently captured
  via Stage 5 UI architecture doc; will get its own implementation
  sub-issue).

Does NOT apply to:

- **C++ MRML node classes** (e.g., `vtkMRMLAbstractTerritoriesNode`
  per #407, `vtkMRMLBezierSurfaceStorageNode`). Parameter node
  wrapper is a Python pattern; C++ data classes manage their own
  state via MRML XML serialisation per ADR-0004's data-only rule.
- **Segment Editor effects** (Kumar-Oram per ADR-0026). Effects
  follow Slicer's `qSlicerSegmentEditorAbstractEffect` parameter
  contract, not the scripted-module parameter-node-wrapper pattern.
- **Action-button connects** (described above). Per-button
  `connect()` calls remain idiomatic when no parameter field is
  involved.

## Alternatives considered

### Alternative A — Keep the v1 per-widget connect pattern

Continue with `valueChanged.connect(...)` + per-handler pull/push
boilerplate. No new dependency on Slicer 5.4+ machinery.

**Rejected because** v2.0 already declares minimum Slicer version
bumps as a MAJOR-triggering compatibility surface per ADR-0007. The
v2.0 minimum Slicer version will be high enough to use parameter
node wrapper (Slicer 5.4 released May 2023; v2.0's target is later).
And the boilerplate cost — multiplied across 4 module rewrites — is
substantial.

### Alternative B — Use parameter node wrapper, but keep manual `connect()` for everything

Adopt the wrapper class for typed access but keep per-widget
`connect()` calls instead of `connectParametersToQtWidgets`.

**Rejected because** the manual-connect approach loses the main
benefit (zero boilerplate at the widget layer). The
`connectParametersToQtWidgets` helper is the value of the
mechanism; halving it doesn't pay off.

### Alternative C — Custom Slicer-Liver-side binding helper

Write Slicer-Liver's own binding helper that wraps `connect()`
calls behind a dataclass-style API. Independent of upstream Slicer's
parameter node wrapper.

**Rejected because** it forks from upstream's idiomatic pattern.
Future contributors familiar with upstream Slicer would meet a
Slicer-Liver-private surface that re-implements what's already
upstream — exactly the kind of "align with Slicer" violation
ADR-0010 was designed to prevent.

### Alternative D — Apply only to NEW modules, leave renamed module widgets on v1 pattern

Use parameter node wrapper in `LiverSegmentation/` (new) but leave
the `VascularTerritories/` rename of `LiverSegments/` on v1
connect-heavy pattern. Defer the existing modules' widget refactors
to v2.1.

**Rejected because** the rename PR (#408) is the natural moment to
land the pattern change — touching the file already, no churn delta.
Splitting "rename + parameter-wrapper" across two PRs is more work,
not less.

## Consequences

### What becomes easier

- Per-module widget code shrinks substantially — typed parameter
  class + one helper call + per-widget custom property replaces
  dozens of `connect()` + handler lines.
- Parameter pull/push code becomes type-checked at the Python level
  (parameter node wrapper enforces typed field annotations).
- Future contributors familiar with upstream Slicer's scripted-module
  template meet the same pattern in Slicer-Liver — onboarding cost
  drops.
- UI element ↔ parameter binding is declared in one place (the .ui
  file's custom property) — easier to grep, easier to audit.

### What becomes harder

- Contributors editing widgets need to know two binding surfaces
  (the typed parameter class + the .ui custom property). For
  contributors used to v1's `connect()` pattern, this is a new
  pattern to learn.
- Debugging when bindings don't fire takes more attention — the
  helper auto-connects based on widget metadata; if a widget is
  missing `SlicerParameterName`, no error, the binding just doesn't
  fire. Conformance grep helps but doesn't catch typos.
- Some widget types (custom Slicer-Liver widgets, deeply-nested
  QFrame children) may not be auto-discoverable by
  `connectParametersToQtWidgets` — those still need manual
  `connect()`. The boundary needs to be checked per-widget.

### Follow-on work

- **Per-module implementation issues** for #408, #409, #410 (and
  future LiverVolumetry refactor issue) carry the parameter-wrapper
  enforcement as part of their Acceptance criteria.
- **Slicer minimum version** in `CMakeLists.txt` confirmed at the
  Slicer 5.4+ floor when the v2.0 release-prep PR lands — Slicer
  5.6 and 5.8 are already retired from the ExtensionsIndex per
  ADR-0006.

## Conformance

Reviewable invariants that signal this decision is honoured:

- Every v2.0 scripted module's `Logic` class exposes a
  `@parameterNodeWrapper`-decorated parameter class. Grep
  `@parameterNodeWrapper` should match in
  `Liver/Liver.py`, `LiverSegmentation/LiverSegmentation.py`,
  `VascularTerritories/VascularTerritories.py`, and
  `LiverVolumetry/LiverVolumetry.py` (the latter when its refactor
  lands).
- Every parameter-backed Qt widget declares `SlicerParameterName`
  as a custom property. Grep `<string>SlicerParameterName</string>`
  in `*.ui` files under each module's `Resources/UI/`.
- Every module's `Widget.setup()` calls
  `slicer.util.connectParametersToQtWidgets(...)` once. Grep that
  string per module.
- No parameter-backed widget has a corresponding manual
  `valueChanged.connect(...)` /
  `currentIndexChanged.connect(...)` call for the *parameter
  binding*. Action-button `clicked.connect(...)` is fine and
  expected; the differentiation is whether the connected slot
  pushes/pulls a parameter field (forbidden — let the wrapper do
  it) or triggers an action (fine).
- `/slicer-review`'s checklist gains a "UI binding shape" bullet:
  did this module use parameter node wrapper for parameter-backed
  widgets?

## References

- Upstream Slicer parameter node wrapper documentation:
  `Base/Python/slicer/parameterNodeWrapper/__init__.py` in the
  Slicer-core repo.
- [ADR-0004 — Python/C++ boundary](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0004-python-cpp-boundary.md). Parameter wrapper is Python; C++ MRML node classes manage their own state.
- [ADR-0009 — UX and design discipline](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0009-ux-and-design-discipline.md). Per-PR UX discipline; this ADR adds a code-level binding convention complementary to ADR-0023's design surface.
- [ADR-0010 — Accessibility and i18n](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0010-accessibility-and-i18n.md). "Align with Slicer, contribute upstream" — parameter node wrapper is Slicer's idiomatic upstream pattern.
- [ADR-0023 — Unified GUI / six-stage surgeon workflow](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0023-unified-gui-stage-workflow.md). The widget surfaces this ADR's binding pattern applies to.
- [ADR-0027 — Invariant-test-first discipline](https://github.com/ALive-research/Slicer-Liver/blob/preview/Docs/adr/0027-invariant-test-first-v2-implementation.md). Tests for parameter-bound widgets pin the binding shape — wrapper field value reflects in widget value and vice versa.
- Tracker [issue #305](https://github.com/ALive-research/Slicer-Liver/issues/305) — v2.0.0 release tracker.

---

*AI-assisted authorship: this ADR was drafted with help from Anthropic's Claude (Opus 4.7, `claude-opus-4-7`) via Claude Code in response to the maintainer's 2026-05-21 directive to enforce parameter node wrapper + UI custom-attribute binding for v2.0 widgets to eliminate v1's transactional connect-heavy boilerplate.*
