# 3D Slicer host accessibility and i18n posture survey

- **Status:** Findings draft
- **Date:** 2026-05-15
- **Reference Slicer revision:** Slicer 5.8.1 source tree
  ([github.com/Slicer/Slicer @ `v5.8.1`](https://github.com/Slicer/Slicer/tree/v5.8.1)).
- **Gates:** [ADR-0010 — Accessibility and i18n stance](../adr/0010-accessibility-and-i18n.md),
  Tier-2 commitments §§4–6 and the open-questions list.

## Opening

ADR-0010 commits Slicer-Liver to *inherit Slicer's accessibility and
internationalisation posture, and raise gaps upstream rather than
work around them module-locally*. The Tier-2 items in ADR-0010
(palette for diagrammatic surfaces, keyboard-navigation conventions,
WCAG / accessibility conformance target) are explicitly **survey
pending**: they cannot be committed unilaterally because users
alternate between Slicer-Liver and other Slicer modules inside the
same session, and a Slicer-Liver-only convention would break
host-application consistency. This document records what Slicer
itself does on each of those items so that ADR-0010 can be
re-graded from *Proposed* to *Accepted* on Tier-2, and so that the
remaining genuine gaps can be raised upstream rather than worked
around inside Slicer-Liver.

The survey draws on three sources: (i) the Slicer 5.8 source tree
itself (file paths cited as `Path/To/File.cxx:LINE`, anchored to
the upstream Slicer 5.8 source layout — the in-repo paths and
line numbers are stable across mirrors); (ii) the published Slicer
user and developer documentation hosted at
`slicer.readthedocs.io` and the Slicer GitHub wiki; (iii) the
`discourse.slicer.org` community forum, where core developers
(notably Andras Lasso) post the project's de-facto positions in
the absence of a more formal policy document.

The survey is honest about uncertainty: "no clear stance found —
would warrant an upstream question" is recorded as such, rather
than papered over.

---

## 1. Palette conventions for diagrammatic surfaces

### Finding

Slicer ships a **broad catalogue of named lookup tables** and uses
distinct defaults per category, but it has **no published
colour-blind-aware palette convention** and **no documented
palette-selection rationale** beyond the ad-hoc historical record
in `Docs/user_guide/modules/colors.md`. The defaults are:

| Surface | Default palette | Source |
| --- | --- | --- |
| **Segment Editor / segmentation labels** | `GenericAnatomyColors.txt` (whole-body anatomy palette derived from the Slicer3 2010 list — 24 named anatomical entries, each with a recommended RGB) | `Modules/Loadable/Colors/Logic/vtkSlicerColorLogic.cxx:78` (`GetDefaultEditorColorNodeID`) |
| **Label map volumes** | `GenericColors.txt` (numeric-indexed palette — same RGB values as `GenericAnatomyColors.txt` but without anatomical names) | `Modules/Loadable/Colors/Logic/vtkSlicerColorLogic.cxx:72` (`GetDefaultLabelMapColorNodeID`) |
| **Chart series (plot data)** | `DarkBrightChartColors.txt` (8 entries from Stephen Few's *Practical Rules for Using Colors in Charts*) | `Modules/Loadable/Colors/Logic/vtkSlicerColorLogic.cxx:84` (`GetDefaultChartColorNodeID`) |
| **Slice-view identification (state indicator)** | Fixed three-colour set: Red `#F34A33`, Yellow `#EDD54C`, Green `#6EB04B`, plus Compare `#E17012` and Gray `#8C8C8C` for layout colours; 3D Blue `#7483E9` for the 3D view | `Libs/MRML/Core/vtkMRMLAbstractViewNode.cxx:596-650` (`GetRedColor` / `GetYellowColor` / `GetGreenColor` / `GetCompareColor` / `GetGrayColor` / `GetThreeDViewBlueColor`) |
| **DICOM-aligned segmentation terminology** | Terminologies module ships `SegmentationCategoryTypeModifier-SlicerGeneralAnatomy.json` and `…-DICOM-Master.json`, with `recommendedDisplayRGBValue` baked into each anatomical type from the DICOM standard / SNOMED-CT mapping | `Modules/Loadable/Terminologies/Resources/SegmentationCategoryTypeModifier-SlicerGeneralAnatomy.json` |

The palette catalogue documented in
`Docs/user_guide/modules/colors.md:101-180` covers Iron, Rainbow,
Viridis, Plasma, Inferno, Magma, Cividis, the PET standards, the
FreeSurfer palettes, the Stephen Few chart palettes, several brain
and abdomen atlases, and several Stephen Few "shade" and "tint"
ramps. The Viridis / Plasma / Inferno / Magma / Cividis family is
recognised colour-vision-deficiency-aware (perceptually uniform
and chromatically robust under deuteranopia and protanopia
simulation), but is **not selected as the default for any
category** — the only categorical surface that defaults to a
perceptually-uniform table is none of them; `GenericAnatomyColors`
and `DarkBrightChartColors` are the defaults.

A grep across the entire Slicer 5.8 source tree returned **zero
hits** for any of `Okabe`, `colorblind`, `color-blind`,
`colourblind`, `deuteranop`, `protanop`. Slicer's developer and
user documentation directories likewise contain no occurrence of
those terms. The `Docs/user_guide/modules/colors.md` page does
not name colour-vision deficiency as a design criterion for any
of the listed palettes.

The Discourse forum confirms this: when users have raised
specific palette-collision problems (e.g. "the default green
segment is too similar to the blue-green Local Threshold preview
overlay"), core developers respond with code-level workarounds
(adjust hue/saturation/value in the preview generator) rather
than with a palette-level recommendation. No thread surfaces a
project-wide colour-vision-deficiency-aware default.

### Citations

- `Modules/Loadable/Colors/Logic/vtkSlicerColorLogic.cxx:60-86`
  (default getters: label map → `GenericColors.txt`, segment
  editor → `GenericAnatomyColors.txt`, chart →
  `DarkBrightChartColors.txt`).
- `Base/Logic/Resources/ColorFiles/GenericAnatomyColors.txt` —
  attribution comment cites
  `https://www.slicer.org/w/index.php/Slicer3:2010_GenericAnatomyColors`.
- `Base/Logic/Resources/ColorFiles/DarkBrightChartColors.txt` —
  attribution comment cites
  `https://www.slicer.org/w/index.php/Slicer4:2012_DarkBrightChartColors`.
- `Libs/MRML/Core/vtkMRMLAbstractViewNode.cxx:596-650` — fixed
  RGB constants for slice-view layout colours.
- `Modules/Loadable/Terminologies/Resources/SegmentationCategoryTypeModifier-SlicerGeneralAnatomy.json`
  — DICOM-aligned terminology with `recommendedDisplayRGBValue`
  per anatomical type.
- `Docs/user_guide/modules/colors.md:101-180` — built-in lookup
  tables catalogue.
- Slicer Discourse: [Change default color palette for segmentation](https://discourse.slicer.org/t/change-default-color-palette-for-segmentation/20288)
  and [Segmentation: the default green is similar to the blue-green Local Threshold preview](https://discourse.slicer.org/t/segmentation-the-default-green-color-is-very-similiar-the-bluegreen-color/20508)
  — no project-wide colour-blind palette guidance from core
  developers in either thread.

### Slicer-Liver implication

There **is** a Slicer-wide palette convention for *anatomical
segment labels* and *plot series*, but it is the
`GenericAnatomyColors` / `DarkBrightChartColors` pair, neither of
which is documented as colour-vision-deficiency-aware. There is a
**very explicit, hardcoded, host-wide convention** for slice-view
identification colours (Red / Yellow / Green / Compare-Orange /
Gray + 3D-Blue): Slicer-Liver MUST NOT redefine these — every
Slicer module shares them and they are how users distinguish
which slice plane an annotation belongs to.

For segment labels specifically, the right Slicer-Liver posture
is: **assign DICOM-aligned terminology entries to liver-domain
segments** (e.g. `SCT:71976005|Liver`) and let the host's
`recommendedDisplayRGBValue` flow through, rather than picking
RGB values directly. This inherits Slicer's anatomical-palette
convention without adding a Slicer-Liver-specific palette.

For *new* diagrammatic surfaces (resection-state cues,
vessel-tree highlights, plot series produced by Slicer-Liver
modules), Slicer has no host-level colour-vision-deficiency
guidance to inherit. ADR-0010 should record this as **no clear
stance — would warrant an upstream question** rather than
unilaterally adopt Okabe-Ito or any other palette inside
Slicer-Liver alone.

The colour-vision-deficiency question is a genuine cross-module
concern: a Slicer-Liver-only Okabe-Ito palette would collide
visually with `GenericAnatomyColors`-coloured segments from
adjacent modules inside the same scene. The upstream issue is
the right venue.

---

## 2. Keyboard-navigation conventions

### Finding

Slicer publishes an **extensive shortcut table** in
`Docs/user_guide/user_interface.md` covering generic shortcuts,
slice-view shortcuts, 3D-view shortcuts, and the Python console.
It does **not** publish a cross-module convention for
keyboard-only widget navigation (Tab focus order, Escape
semantics, Enter to confirm, etc.). The de-facto practice is:

**Application-level (published, stable):**

| Shortcut | Action | Source |
| --- | --- | --- |
| `Ctrl+f` | Find module by name | `Base/QTGUI/qSlicerModuleSelectorToolBar.cxx:112` |
| `Ctrl+Left` / `Ctrl+Right` | Previous / next module in history | `Base/QTGUI/qSlicerModuleSelectorToolBar.cxx:178,195` |
| `Ctrl+h` | Open default startup module ("Home") | `Base/QTGUI/qSlicerApplication.cxx:350` — reserved against the PythonQt console |
| `Ctrl+0..5` | Show error log / help / settings / Python / extension mgr / module panel | `Base/QTApp/Resources/UI/qSlicerMainWindow.ui` |
| `Ctrl+o`, `Ctrl+s`, `Ctrl+w`, `Ctrl+z`, `Ctrl+y`, `Ctrl+x`, `Ctrl+c`, `Ctrl+v` | Open, save, close, undo, redo, cut, copy, paste | `Base/QTApp/Resources/UI/qSlicerMainWindow.ui` |
| `Ctrl+1`, `Ctrl+2`, `Ctrl+4`, `Ctrl+6` | Documentation, Application Settings, Extension Manager, … | `Applications/SlicerApp/qSlicerAppMainWindow.cxx:82` and `qSlicerMainWindow.ui` |

**Slice-view shortcuts (published, single-key, no modifier):**

`left/right arrow` (or `b`/`f`) prev/next slice; `Shift+mouse`
crosshair; `v` slice visibility; `r` reset zoom/pan; `g` toggle
segmentation; `t` toggle foreground; `[`/`]` and `{`/`}` cycle
volumes; left-double-click maximise. Documented at
`Docs/user_guide/user_interface.md:220-236`.

**3D-view shortcuts:**

`left/right/up/down arrow` rotate; `Shift+arrow` pan; `End` / `PgDn`
/ `Home` / `Keypad 1,3,7` snap-to-anatomical-direction;
`Ctrl+b` tilt lock; `+`/`-` zoom. Documented at
`Docs/user_guide/user_interface.md:246-270`.

**Segment Editor (published in module docs; programmatic in
`installKeyboardShortcuts()`):**

`1..9, 0` activate effects 1..10; `Shift+1..0` effects 11..20;
`Escape` deactivate active effect; `Space` toggle last-used
effect; `Z`/`Y` undo/redo (plus `QKeySequence::Undo`/`Redo`);
`q`,`w`,`/`,`*`,`,`,`.`,`<`,`>` previous / next segment.
Wired at
`Modules/Loadable/Segmentations/Widgets/qMRMLSegmentEditorWidget.cxx:3175-3232`.

**Markups toolbar:**

`Ctrl+Shift+A` create new markups node; `Ctrl+Shift+T` toggle
persistent place mode; `Ctrl+Shift+Space` place a control
point. Default wiring at
`Modules/Loadable/Markups/Widgets/qMRMLMarkupsToolBar.cxx:84-86`.

**Customisation:**

There is **no GUI for keyboard-shortcut customisation.** Andras
Lasso's recommendation on Discourse is to register additional
shortcuts via Python in `.slicerrc.py` using `QShortcut` objects
([Customize keyboard shortcuts in Slicer?](https://discourse.slicer.org/t/customize-keyboard-shortcuts-in-slicer/32891)).

**Translatability of shortcuts:**

The Slicer i18n developer manual explicitly recommends declaring
shortcuts via `QKeySequence::Print` (where a standard sequence
exists) or `tr("Ctrl+g")` (otherwise), so that translators can
adapt shortcuts to keyboard-layout norms in other languages.
String literals like `"Ctrl+g"` and `Qt::CTRL | Qt::Key_G` are
called out as **do-not-use** patterns.

**Focus management / Tab order:**

A grep for `setTabOrder` across the full Slicer 5.8 source tree
returns hits in **a single file** —
`Base/QTGUI/qSlicerExportNodeDialog.cxx`. `setFocusPolicy` is
similarly rare (a handful of widgets in the export dialog and
the search bar; nothing module-wide). There is **no documented
project-wide convention** for keyboard-only widget reachability,
Tab order, or focus-ring styling. In practice this means
Slicer-Liver inherits *whatever Qt's default Tab traversal
produces from the .ui file*, with no cross-module audit.

### Citations

- `Docs/user_guide/user_interface.md:185-285` — published
  shortcut tables.
- `Modules/Loadable/Segmentations/Widgets/qMRMLSegmentEditorWidget.cxx:3160-3232`
  — Segment Editor keyboard shortcut wiring.
- `Modules/Loadable/Markups/Widgets/qMRMLMarkupsToolBar.cxx:84-86`,
  `:575-595` — Markups place-mode shortcut wiring.
- `Base/QTApp/Resources/UI/qSlicerMainWindow.ui` — main-window
  shortcuts in `.ui` properties.
- [SlicerLanguagePacks DevelopersManual.md — "Translating keyboard shortcuts"](https://github.com/Slicer/SlicerLanguagePacks/blob/main/DevelopersManual.md)
  (canonical Slicer i18n developer guidance, including the
  shortcut-translatability rule).
- [Discourse: Customize keyboard shortcuts in Slicer?](https://discourse.slicer.org/t/customize-keyboard-shortcuts-in-slicer/32891)
  (Andras Lasso confirms there is no GUI; customisation is via
  Python `.slicerrc.py`).
- `Base/QTGUI/qSlicerExportNodeDialog.cxx:797-820` — only file in
  the codebase that calls `setTabOrder`.

### Slicer-Liver implication

For **module-internal keyboard reachability**, Slicer has
**published shortcut conventions** that Slicer-Liver MUST not
collide with: `Escape` = deactivate-effect (in segmentation
contexts), `Space` = toggle-last-effect, `1..0` =
effect-by-index, `Z`/`Y` = undo/redo, `q`/`w`/`,`/`.` =
prev/next-segment, arrows = slice/3D navigation, single-letter
keys (`v`, `r`, `g`, `t`, `b`, `f`) reserved for slice-view
state. Slicer-Liver-introduced shortcuts MUST stay clear of
those, MUST use `Ctrl+Shift+...` for new module-level commands
following the Markups precedent, and MUST be declared via
`tr("Ctrl+...")` or `QKeySequence::StandardKey` for
translatability per ADR-0010 §Internationalisation §1.

For **focus-order / Tab traversal**, Slicer has **no published
convention** — Slicer-Liver effectively inherits Qt's default
Tab traversal from `.ui` files, with no host-level audit. ADR-0010
should treat keyboard-only widget reachability as Tier-1
(Slicer-Liver can verify the Tab order is sensible inside each
of its dialogs without affecting other modules), not Tier-2.
**No upstream question is warranted on focus order** — Slicer's
practice is "let Qt decide and verify per dialog," and that's
implementable inside Slicer-Liver without divergence.

For **shortcut customisation by end users**, Slicer has no GUI
and no host-level posture: Slicer-Liver inherits this gap. **No
unilateral remedy is warranted** — a Slicer-Liver-only shortcut
customisation GUI would diverge from host practice.

---

## 3. WCAG / accessibility conformance stance

### Finding

**No published Slicer WCAG / Section 508 / EN 301 549
conformance stance exists.** A grep across the full Slicer 5.8
source and docs returns zero matches for `WCAG`, `Section 508`,
`EN 301`, or `a11y`. The Slicer wiki, ReadTheDocs documentation,
SECURITY.md, CONTRIBUTING.md, and developer-guide style guide
say nothing about conformance targets.

The only public mention of WCAG in connection with Slicer is on
Discourse, where a community member reports that *their own
custom Slicer-based application* increased font sizes "to comply
with WCAG 2.0 Guidelines" — i.e. it is a downstream
customisation, not a host commitment ([Discourse: Slicer default text-size is smaller than other applications (Windows)](https://discourse.slicer.org/t/slicer-default-text-size-is-smaller-than-other-applications-windows/33154)).

The closest thing to a published Slicer accessibility commitment
is the existence of:

- **An application-level font-and-size setting** in
  `Edit → Application Settings → Appearance → Font` that
  re-renders the whole UI at a chosen point size (wired at
  `Base/QTGUI/qSlicerSettingsStylesPanel.cxx:322-325` via
  `qSlicerApplication::setFont()`).
- **Light / Dark / system-tracking Style options** in
  `Edit → Application Settings → Appearance → Style` documented
  at `Docs/user_guide/settings.md:68-78`.
- **Documented `QT_SCALE_FACTOR`, `QT_ENABLE_HIGHDPI_SCALING`,
  `QT_SCALE_FACTOR_ROUNDING_POLICY` environment variables** for
  high-DPI scaling, at `Docs/user_guide/settings.md:144-150`.

These are mechanisms that *enable* a conformance argument but do
not themselves *constitute* one. Core developer guidance on
Discourse is that font-scale changes are useful but
"widget layout issues cannot always be resolved, especially when
font size is set to larger than default" — i.e. the host
acknowledges that larger fonts may break individual widget
layouts and treats this as an ongoing maintenance burden, not a
release criterion.

### Citations

- Slicer 5.8 source-tree-wide grep: zero hits for `WCAG`,
  `Section 508`, `EN 301`, `a11y`. Cross-checked in `Docs/`,
  `README.md`, `CONTRIBUTING.md`, `SECURITY.md`,
  `Docs/developer_guide/style_guide.md`.
- `Docs/user_guide/settings.md:68-78,144-150` — Style and DPI
  scaling settings.
- `Base/QTGUI/qSlicerSettingsStylesPanel.cxx:322-325` — font
  setting handler.
- [Discourse: Slicer default text-size is smaller (Windows)](https://discourse.slicer.org/t/slicer-default-text-size-is-smaller-than-other-applications-windows/33154)
  — the only Slicer-context mention of WCAG, and it is by a
  downstream consumer reporting *their own* WCAG-driven
  customisation, not Slicer's posture.
- [Discourse: Windows font scaling issue on laptop screens](https://discourse.slicer.org/t/windows-font-scaling-issue-on-laptop-screens/40883)
  — core-developer commentary acknowledging that
  larger-than-default fonts can break widget layouts.

### Slicer-Liver implication

**No clear host stance found — would warrant an upstream
question.** ADR-0010 Tier-2 §6 ("Slicer-Liver does not claim a
conformance level ahead of host Slicer") therefore holds: until
Slicer publishes a conformance target, Slicer-Liver claiming AA
ahead of the host would be (a) unverifiable in practice and
(b) inconsistent with the rest of the Slicer ecosystem.

The Tier-1 commitments in ADR-0010 (respect application font
scaling, no hard-coded point sizes, `tr()` discipline) are
compatible with whatever conformance target Slicer eventually
adopts and require no revision pending the upstream answer.

An upstream issue framed as "what is Slicer's documented
accessibility / WCAG conformance posture?" is warranted (see
Gaps §G3 below). Slicer-Liver should file it but does not block
v2.0.0 on the answer.

---

## 4. Screen-reader posture

### Finding

Slicer has **no documented platform-level screen-reader stance**
in user or developer guides. However, the source tree contains
**concrete, intentional, narrowly-scoped screen-reader fixes**,
demonstrating that core developers do think about it tactically
when individual reports surface — they just have not produced a
platform-level policy.

The most explicit example is a 2023-10-05 commit
(`c9466d8e43` upstream, *"BUG: Fix Segment Editor screen reader
compatibility"*), which adds
`effectButton->setAccessibleName(effectButton->toolTip());`
calls to dynamically-created Segment Editor effect tool-buttons
at `Modules/Loadable/Segmentations/Widgets/qMRMLSegmentEditorWidget.cxx:1050,1092`.
The commit message reads:

> When the user hovered over Segment Editor effect buttons,
> screen readers (neither Windows Narrator, nor macOS Spoken
> Content) it could not read any text from it. Standard
> undo/redo toolbar buttons worked, only the dynamically-added
> buttons had this problem. Explicitly setting accessibleName
> property fixed the issue.

This is the only point in the entire Slicer 5.8 source tree
where `setAccessibleName` is called from C++. A grep for
`accessibleName` in `.ui` files returns **exactly one hit** —
the active-markup-control-point table at
`Modules/Loadable/Markups/Resources/UI/qSlicerMarkupsModule.ui:569`
(annotated `"active markup control point table"`). The grep
returns **zero hits** for `accessibleDescription` anywhere in
the codebase, and zero hits for `QAccessible` subclassing or
custom `QAccessibleInterface` implementations.

In other words: Slicer has **no systematic screen-reader-friendly
widget naming**, but it has demonstrated willingness to fix
individual breakages as they are reported. The Qt framework
itself bridges to AT-SPI on Linux, MSAA / UIAutomation on
Windows, and macOS Accessibility on macOS — Slicer benefits from
these bridges by default, but does not declare itself
screen-reader-supported.

**3D-rendered surfaces** (the slice-view crosshair, the 3D
camera, VTK render windows generally) are platform-level
inaccessible to screen readers: VTK does not implement
`QAccessibleInterface` for its render-window children, and
QVTKWidget / `pqQVTKWidgetBase` does not expose the rendered
scene as accessibility-tree nodes. This is not a Slicer choice;
it is the state of the upstream VTK Qt integration.

### Citations

- `Modules/Loadable/Segmentations/Widgets/qMRMLSegmentEditorWidget.cxx:1040-1095`
  — the screen-reader fix for Segment Editor effect buttons,
  with the explicit comment "Without this, screen readers
  (Microsoft Narrator, macOS Spoken Content, …) cannot read
  anything from the button."
- Upstream Slicer commit `c9466d8e43`
  ([gh api repos/Slicer/Slicer/commits/c9466d8e43](https://github.com/Slicer/Slicer/commit/c9466d8e43))
  — *BUG: Fix Segment Editor screen reader compatibility*
  (2023-10-05).
- `Modules/Loadable/Markups/Resources/UI/qSlicerMarkupsModule.ui:569`
  — the only `accessibleName` in any `.ui` file.
- Slicer 5.8 source-tree-wide grep: zero hits for
  `accessibleDescription`, zero subclasses of `QAccessible*`,
  zero `setAccessibleDescription`.
- [Qt accessibility platform-bridge documentation](https://doc.qt.io/qt-5/accessible.html)
  — the AT-SPI / MSAA / NSAccessibility bridge that Slicer
  inherits implicitly via Qt.

### Slicer-Liver implication

ADR-0010 Tier-3 §7 (deferral of screen-reader support to v2.1.0
*or later*, contingent on the host moving) is **well-supported
by the evidence**: Slicer treats screen-reader support as
reactive (fix when reported) rather than proactive (audit and
guarantee), and 3D-rendered surfaces are unreachable at the VTK
layer. Slicer-Liver inheriting this posture is consistent with
the host.

**One concrete Tier-1 implication does follow from the existing
Slicer practice**: where Slicer-Liver dynamically creates
tool-buttons (i.e., not declared in a `.ui` file), the pattern
established by the Segment Editor fix should be followed —
`button->setAccessibleName(button->toolTip())` at construction
time. This is a documented host-level pattern (the upstream
commit comment cites it explicitly), not a Slicer-Liver
invention, and applies to ADR-0010 Tier-1.

The platform-level question ("when will Slicer commit to a
screen-reader-supportable subset of its UI?") is genuinely
upstream and is recorded in Gaps §G4.

---

## 5. Internationalisation posture

### Finding

This is the survey item where Slicer has **the most developed and
the most explicitly documented stance**. ADR-0010
§Internationalisation §1 already aligns Slicer-Liver with it; the
survey confirms the alignment is correct.

**Mechanism:** Qt Linguist `.ts` / `.qm` workflow, enabled by the
top-level `Slicer_BUILD_I18N_SUPPORT=ON` option
(`CMakeLists.txt:285`) and exercised via the
`SlicerMacroTranslation()` CMake helper at
`CMake/SlicerMacroTranslation.cmake`. The macro is called from
`SlicerMacroBuildBaseQtLibrary.cmake:176`,
`SlicerMacroBuildApplication.cmake:177`,
`SlicerMacroBuildLoadableModule.cmake:169`, and
`SlicerMacroBuildModuleWidgets.cmake:85` — i.e. every Qt-based
Slicer module gets translation processing automatically.

**Source-text wrapping conventions (canonical):**

| Context | Wrapper | Note |
| --- | --- | --- |
| C++ `QObject` subclass with `Q_OBJECT` | `tr("...")` | Class-name context auto-resolved by `lupdate`. |
| C++ non-`QObject` (or private impl) | `Q_DECLARE_TR_FUNCTIONS(MyClass)` + `tr(...)`, or `PublicClassName::tr("...")` | Avoid `QObject::tr` / `QLabel::tr` — context attribution wrong. |
| C++ VTK class (no Qt) | `vtkMRMLTr("vtkMRMLFooNode", "text")` | And `vtkMRMLI18N::Format(...)` for placeholder substitution `%1..%9`. |
| Python (scripted module) | `from slicer.i18n import tr as _, translate` ; `_("text")` ; `translate("ContextName", "text")` | Module categories specifically must use `translate("qSlicerAbstractCoreModule", "...")`. |
| Keyboard shortcuts | `QKeySequence::StandardKey` (preferred) or `tr("Ctrl+g")` | `"Ctrl+g"` and `Qt::CTRL \| Qt::Key_G` are **do-not-use**. |
| `.ui` properties | Translatable by default in Qt Designer; mark non-translatable for technical strings (`nodeTypes`, `quantity`, `settingKey`, `sliceViewName`, etc.). Full list in the LanguagePacks DevelopersManual. | |

**Multiline strings:** wrap the entire concatenated literal in
one `tr(...)` call, not per-fragment, so translators see whole
sentences.

**Python f-strings:** explicitly forbidden in translation
contexts (`_(f"...")`) — the developer manual frames this as a
*code-injection vector*: f-string interpolation would let a
translation file execute arbitrary Python at format time. Use
`_("text {name}").format(name=value)` instead.

**Non-translatable strings:** mark with a `/*no tr*/` comment so
that reviewers know the omission is intentional.

**Module title translation:** the older C++ pattern
(`set(MODULE_TITLE …)` + `QTMODULE_TITLE` precompiler define) is
deprecated; new C++ loadable modules use `tr("ModuleTitle")`
inside `qSlicerGetTitleMacro()` in the module header.

**Distribution / translation pipeline:**

- Source of truth: <https://github.com/Slicer/SlicerLanguageTranslations>
  (mirrors `.ts` files for every supported component).
- Contribution interface: <https://hosted.weblate.org/projects/3d-slicer/3d-slicer/>
  (Weblate, community-driven; ~60 languages tracked).
- End-user delivery: the **SlicerLanguagePacks extension**
  (<https://github.com/Slicer/SlicerLanguagePacks>) installs
  compiled `.qm` files into the running Slicer.
- Translator credits: **no project-wide convention found in the
  source** — translator credits are tracked in the Weblate
  contributor list, not in module-metadata source files.
  Searches in `*.ts` files and module CMake `.in` metadata
  returned no `translator`-credit field. (The supplied 5.8
  source tree does not bundle the `.ts` files themselves — they
  are pulled from `SlicerLanguageTranslations` at build time.)

**Language selection at runtime:** an `Application language`
dropdown appears in Application Settings *after* the
SlicerLanguagePacks extension is installed; without that
extension the host ships an English-only build.

### Citations

- `CMakeLists.txt:285-286,332,509-525,672` — i18n option
  declaration, `Slicer_LANGUAGES` and `Slicer_UPDATE_TRANSLATION`
  variables, and macro invocation sites.
- `CMake/SlicerMacroTranslation.cmake` — the canonical
  `lupdate`/`lrelease` wrapper used by every Qt-based Slicer
  build target.
- [SlicerLanguagePacks `DevelopersManual.md`](https://github.com/Slicer/SlicerLanguagePacks/blob/main/DevelopersManual.md)
  — canonical developer guidance: `tr()` use, `Q_OBJECT` /
  `Q_DECLARE_TR_FUNCTIONS` rules, VTK `vtkMRMLTr` macro,
  Python `slicer.i18n` import, f-string injection warning,
  shortcut translatability, `.ui` non-translatable property
  list, `/*no tr*/` convention.
- [`Slicer/SlicerLanguageTranslations`](https://github.com/Slicer/SlicerLanguageTranslations) —
  the `.ts` source-of-truth repository.
- [Slicer on Weblate](https://hosted.weblate.org/projects/3d-slicer/3d-slicer/)
  — community translation interface.
- [SoniaPujolLab/SlicerLanguagePacks](https://github.com/Slicer/SlicerLanguagePacks)
  — end-user language-pack installer extension.
- [Discourse: SlicerLanguagePacks announcement](https://discourse.slicer.org/t/slicerlanguagepacks-new-extension-for-translating-user-interface-of-slicer-to-various-languages/24421)
  and [Slicer Internationalization (project week)](https://discourse.slicer.org/t/slicer-internationalization/579).

### Slicer-Liver implication

ADR-0010 §Internationalisation §1–3 is **fully consistent with
host Slicer practice** and requires no revision. The survey
adds a small number of concrete refinements that should fold
into the ADR or into the ADR-0009 PR-grading framework:

- C++ `tr()` discipline: prefer `Q_OBJECT` + `tr(...)` in
  headers; fall back to `Q_DECLARE_TR_FUNCTIONS` for
  non-`QObject` classes; never `QObject::tr(...)` from outside
  `QObject` subclasses.
- VTK classes (Slicer-Liver has several — `vtkMRMLLiver…`
  family): use `vtkMRMLTr("vtkMRMLLiverFooNode", "…")` with
  `vtkMRMLI18N::Format(...)` for placeholder substitution.
- Python: `from slicer.i18n import tr as _, translate`; never
  f-strings inside `_( … )`.
- Keyboard shortcuts: `tr("Ctrl+…")` or `QKeySequence::Standard…`,
  never bare string literals.
- `.ui` files: every UI-touching PR should also verify
  non-translatable properties (`nodeTypes`, `settingKey`,
  `quantity`, `sliceViewName`, …) are flagged in Qt Designer
  per the upstream property list.
- Translator credits: no host-level convention to inherit.
  Slicer-Liver's PR template can optionally include a
  Translators section, but the Weblate contributor list is the
  upstream-canonical attribution surface.

ADR-0010 §Internationalisation §2 ("ship English-only `.ts` for
v2.0.0") becomes more concrete with this confirmation: the
deliverable is a `SlicerLiver_en-US.ts` source file plus the
build wiring to invoke `SlicerMacroTranslation()` on
Slicer-Liver's targets. Translation contributions, if any
arrive during the v2.0.0 cycle, land in Weblate against the
Slicer-Liver component once the project is registered with the
upstream translation infrastructure.

---

## Gaps — items warranting upstream questions

The following items have no clear host stance. Slicer-Liver
cannot resolve any of them unilaterally without breaking
host-application consistency. Filing decisions are deferred to a
separate PR (per the brief on this survey); the framings below
are drafts.

### G1. Colour-vision-deficiency-aware palette for diagrammatic surfaces

**Suggested issue title:** *Adopt a colour-vision-deficiency-aware default palette for categorical surfaces (segments, plot series, state cues)*

**One-paragraph framing:** Slicer's default categorical
palettes — `GenericAnatomyColors` for segment labels and
`DarkBrightChartColors` for plot series — predate widely-used
colour-vision-deficiency-aware alternatives such as Okabe-Ito
(Wong 2011) or Bang Wong's eight-colour series. Roughly 8% of
men have a red-green colour-vision deficiency; the clinical
populations that use Slicer skew toward this fraction. Slicer
already ships colour-vision-deficiency-robust perceptually
uniform tables (Viridis, Plasma, Inferno, Magma, Cividis) but
does not select any of them as defaults for any *categorical*
surface. Could the project (i) document a recommended
colour-vision-deficiency-aware default for categorical
segment-label and plot-series palettes; (ii) optionally ship the
Okabe-Ito 8-colour palette under that recommendation; (iii)
clarify whether `recommendedDisplayRGBValue` in DICOM-aligned
terminology takes precedence over the categorical default
(observed behaviour) and document that precedence?

### G2. Tab order / focus management policy

**Suggested issue title:** *Document Slicer's expectations for Tab order and keyboard focus reachability in module dialogs*

**One-paragraph framing:** A grep across the Slicer 5.8 source
tree returns `setTabOrder` calls in exactly one file
(`qSlicerExportNodeDialog.cxx`). The project has no documented
guidance for module authors on (a) whether explicit Tab order
declaration is expected in `.ui` files for new dialogs,
(b) whether keyboard reachability of every interactive control
is a release criterion, or (c) which controls (e.g.
`ctkPathLineEdit`) require explicit `setFocusPolicy` because
their defaults are `Qt::NoFocus`. Could the project clarify the
expectation so that module authors targeting keyboard-only
operability know what to aim for?

### G3. WCAG / Section 508 / EN 301 549 conformance posture

**Suggested issue title:** *Publish Slicer's documented accessibility-conformance posture (WCAG / Section 508 / EN 301 549)*

**One-paragraph framing:** A search of the Slicer source tree,
ReadTheDocs documentation, GitHub wiki, README, and SECURITY.md
returns no mention of WCAG, Section 508, or EN 301 549.
Downstream consumers (e.g. customised Slicer-based clinical
applications) have reported needing WCAG 2.0 alignment, and the
host has the relevant mechanisms (application font scaling,
high-DPI scaling environment variables, light/dark theming, Qt's
AT-SPI / MSAA / NSAccessibility bridges). Could the project
publish a documented posture — even if that posture is "no
formal conformance target, but the following mechanisms are
supported and the following surfaces are known unsupported"? A
documented "no formal target" answer is equally useful to
downstream regulated deployments, because they can then quote
it in their own VPATs.

### G4. Platform-level screen-reader supportability target

**Suggested issue title:** *Define a supportable subset of Slicer UI for screen-reader interaction*

**One-paragraph framing:** Slicer already contains tactical
screen-reader fixes (the Segment Editor `setAccessibleName`
calls added in commit `c9466d8e43`, October 2023) but has no
platform-level stance. 3D-rendered surfaces are inaccessible at
the VTK layer; Module Panel, application toolbars, modal
dialogs, and tabular widgets are largely accessible by virtue of
Qt's default AT-SPI/MSAA bridges. Could the project document
which surfaces are intended to be screen-reader-accessible
(e.g. Module Panel and modal dialogs), which are intentionally
not (3D render views, slice views), and what convention module
authors should follow (the
`setAccessibleName(button->toolTip())` pattern, declared in
`.ui` properties for static widgets, called programmatically for
dynamically-created widgets)? This would let module authors —
including Slicer-Liver — meet the existing standard rather than
inventing one.

### G5. Translator-credit / acknowledgement convention

**Suggested issue title:** *Convention for translator credits in module metadata*

**One-paragraph framing:** The Slicer translation pipeline routes
attribution through Weblate's contributor list. There is no
host-level convention for surfacing translator credits inside
module metadata (e.g. in the module's `.cpp` `Contributors` list
or in the Help dialog). Some modules ship a `Translators`
section in their documentation; most do not. Could the project
either ratify the "Weblate is the canonical attribution surface"
position, or document a convention for surfacing translator
credits in module sources, so that module authors do not invent
divergent attribution surfaces?

---

## Recommended ADR-0010 updates

Bullets are written to be folded into a future revision of
`Docs/adr/0010-accessibility-and-i18n.md`. They are minimal
edits — most of ADR-0010's existing structure stands as drafted.

**On §Internationalisation:**

- Add a concrete pointer to the upstream developer manual:
  `https://github.com/Slicer/SlicerLanguagePacks/blob/main/DevelopersManual.md`
  is the canonical Slicer i18n developer guide. ADR-0010 should
  reference it explicitly, since it documents (a) the
  `Q_OBJECT` / `Q_DECLARE_TR_FUNCTIONS` rule, (b) the
  `vtkMRMLTr(context, …)` macro for VTK classes, (c) the
  `slicer.i18n.tr` import for Python, and (d) the forbidden
  f-string pattern.
- Add a small bullet to §1 noting that **shortcuts must also be
  wrapped** for translation via `QKeySequence::StandardKey` or
  `tr("Ctrl+…")` — upstream policy. Bare `"Ctrl+x"` and
  `Qt::CTRL | Qt::Key_X` are upstream-forbidden patterns.
- Add a small bullet to §1 noting that **f-strings inside
  `_(...)` are forbidden** for security reasons (translator-supplied
  format string could become a Python code-injection vector).
- §2 ("Ship English-only `.ts` for v2.0.0") can be made
  concrete: the deliverable is `SlicerLiver_en-US.ts` generated
  via `SlicerMacroTranslation()`, with Slicer-Liver registered
  as a component on
  <https://hosted.weblate.org/projects/3d-slicer/> when the
  project chooses to enable translation contributions.

**On Tier-1 (within Slicer-Liver, low-risk):**

- Add a bullet: **dynamically-created widgets (not declared in
  `.ui`) follow Slicer's screen-reader pattern**:
  `button->setAccessibleName(button->toolTip())` at construction,
  following the upstream Segment Editor precedent
  (`qMRMLSegmentEditorWidget.cxx:1050,1092`, commit
  `c9466d8e43`).
- Add a bullet on **focus reachability**: explicit `setTabOrder`
  in dialogs that have non-trivial tab traversal — Slicer
  itself does this once
  (`qSlicerExportNodeDialog.cxx:797-820`). Promote keyboard-only
  reachability from Tier-2 to Tier-1 for Slicer-Liver-internal
  dialogs — it is intrinsically module-local and not a
  host-coordination question.

**On Tier-2 (survey pending → either committed or referred upstream):**

- **§4 Colour palette:** Slicer's documented categorical
  defaults are `GenericAnatomyColors` (segment labels) and
  `DarkBrightChartColors` (plot series); slice-view layout
  colours are fixed at `#F34A33` / `#EDD54C` / `#6EB04B` /
  `#E17012` / `#8C8C8C` / `#7483E9` in
  `vtkMRMLAbstractViewNode`. Slicer-Liver MUST NOT redefine any
  of these. For segment labels, the right pattern is to assign
  **DICOM-aligned terminology entries** (e.g.
  `SCT:71976005|Liver`) and let
  `recommendedDisplayRGBValue` propagate. The
  colour-vision-deficiency question for *new* categorical
  surfaces in Slicer-Liver (resection-state cues, vessel
  highlights, plot series) is a genuine **upstream gap**, to be
  raised per Gaps §G1. Until upstream resolves, Slicer-Liver
  uses the host defaults and does not ship a parallel palette.
- **§5 Keyboard-navigation conventions:** Slicer **does** have
  published shortcut conventions (full table in
  `Docs/user_guide/user_interface.md:185-285`, plus the Segment
  Editor and Markups module-specific tables). Slicer-Liver
  follows them and the
  `Ctrl+Shift+...` pattern for new module-level commands.
  Slicer does **not** have a Tab-order / focus convention —
  promote that sub-question to Tier-1 (Slicer-Liver verifies
  per dialog) and raise it upstream per Gaps §G2.
- **§6 Conformance target:** **No clear host stance — raise
  upstream per Gaps §G3.** Tier-2 §6 as drafted in ADR-0010
  stands: Slicer-Liver does not claim a conformance level ahead
  of host Slicer.

**On Tier-3 (out of scope):**

- §7 screen-reader deferral is **well-supported** by the
  evidence and stands as drafted.

**New "Upstream issues to file" subsection (recommended):**

Record Gaps §§G1–G5 as a tracked list with status. None block
v2.0.0 by ADR-0010's own Tier-2 framing ("follow Slicer as you
find it"); they unblock future Tier-2 hardening.

**References to add to ADR-0010 §References:**

- The SlicerLanguagePacks DevelopersManual as the canonical
  upstream i18n developer guide.
- `Slicer/SlicerLanguageTranslations` and Weblate as the
  translation pipeline.
- Upstream Slicer commit `c9466d8e43` as the precedent for the
  dynamic-widget screen-reader pattern.
- This survey document itself, as the audit-trail for the
  Tier-2 commitments.
