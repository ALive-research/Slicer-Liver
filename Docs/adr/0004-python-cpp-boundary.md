# 0004. Python by default; C++ only for MRML node classes and algorithm libraries

- **Status:** Proposed
- **Date:** 2026-05-13
- **Deciders:** Rafael Palomar
- **Diagrams:** N/A
- **PR:** _filled in on merge_

## Context

Slicer-Liver today is heavy C++.  Every module is a Loadable C++ module
(`qSlicerLiverResectionsModule` etc.), every MRML node is a C++
subclass of `vtkMRMLNode`, every displayable manager is a C++ subclass
of `vtkMRMLAbstractDisplayableManager`, and the storage node is a C++
subclass of `vtkMRMLStorageNode`.  Python is used only for narrow
glue.

Two reasons historically pushed Slicer extensions toward C++:

1. **Interactive widgets required `vtkMRMLMarkupsNode` inheritance,**
   which is a C++ class tree.  This is the constraint
   [ADR-0002](0002-migrate-to-slicerlayerdm.md) lifts.
2. **MRML node serialization, scene introspection, and node-reference
   resolution** are conventionally done by C++ subclasses with proper
   `Set/Get` accessors, `Modified()` events, and `Copy()`/
   `PrintSelf()` / `WriteXML()` / `ReadXMLAttributes()` semantics.
   The `vtkMRMLScriptedModuleNode` mechanism exists for declaring node
   attributes from Python but is limited compared to a proper C++
   subclass — and the limitations are precisely the ones that hurt
   for a clinical artefact (introspectability, storage
   round-tripping, scene-query reliability).

Today's Slicer ecosystem precedent has two clear camps:

- **Loadable C++ modules** (Volumes, Markups, Segmentations, Models,
  VolumeRendering) — performance-critical, deeply integrated with
  VTK/ITK pipelines, used in inner rendering loops.
- **Scripted Python modules** (SegmentEditor, DICOM, SampleData,
  ExtensionWizard, SegmentStatistics, MONAI-Label, the broad AI
  extension ecosystem) — module logic, orchestration, UI, storage.

The hybrid pattern that emerges in well-maintained extensions is:
small C++ surface for nodes and algorithms; everything else Python.

Three pressures specifically apply to Slicer-Liver's migration:

- **Refactor cost dominates over a multi-year migration horizon.**
  Python edits are seconds; C++ edits are a Slicer rebuild
  (10–60 min depending on tree state).  Iterating the design itself
  — not just the implementation — is only feasible if the design
  lives in fast-edit code.
- **Contributor base is researcher-heavy.**  C++/Qt/CMake fluency is
  uneven; Slicer Python is approachable.  Lowering the contribution
  barrier without giving up performance requires that the C++ surface
  shrink to a well-defined band where C++ expertise actually pays
  back.
- **Workflow plurality keeps growing.**  Slicer-Liver supports
  multiple resection-definition workflows (contour initialisation +
  Bezier modification; manual contour creation + fitting; 2-point
  initialisation + fitting) and multiple surface representations
  (Bezier today, NURBS in progress).  Each variant is a separate
  LayerDM pipeline class with its own state machine and interaction
  semantics; the catalogue is expected to grow over the migration
  horizon.  Code that must absorb new variants without a Slicer
  rebuild on every iteration belongs in Python.

## Decision

We will adopt the following implementation-language boundary for
Slicer-Liver, applied to new code and to migration code; existing
code that fits the boundary stays in place, and code outside the
boundary migrates as opportunity allows (not in dedicated rewrite PRs).

**C++ is used only for:**

1. **MRML node classes**, kept *data-only*.  A node class declares
   typed fields, `Set/Get` accessors, `Copy()`/`PrintSelf()`/
   `WriteXML()`/`ReadXMLAttributes()`, and the
   `vtkMRMLCopyContent`/`InvokeEvent` plumbing that the scene depends
   on.  It does **not** carry business logic, display state, or
   workflow.
2. **Performance-critical algorithm libraries** — when there is a
   measured or profile-justified need for native speed.  This
   captures the existing tuned inner loops: Bezier-surface
   evaluation, distance-map computation, slicing-contour
   interpolation, volumetry integrators, and any custom VTK filters
   with a demonstrated per-frame or inner-loop budget.  New compute
   that does *not* have a profile-justified native-speed need does
   not belong here — it should be packaged as a Python VTK filter
   (see Python band below).  The default is not "C++ because it is
   an algorithm"; the default is "Python VTK filter unless a profile
   says otherwise".

**Python is used for everything else, including:**

- Module class (`ScriptedLoadableModule` subclass).
- Widget / GUI logic (Qt `.ui` files loaded via `qt.QUiLoader`,
  wired in Python).
- Logic / orchestration (the equivalent of `vtkSlicerLiver*Logic`).
- Storage *parsing / serialization logic* — the `.lrp.fcsv` read/
  write body can live in Python (CSV is trivial; schema evolution is
  easier).  Note however that the **`vtkMRMLStorageNode` subclass
  itself stays C++** — it falls under "MRML node classes" above,
  because the scene's storage dispatch, file-extension registration,
  and `IsA()` queries depend on its C++ class identity.  This is
  precisely the storage pair ADR-0002 calls for; the storage *class*
  is C++, the parsing *body* can delegate to Python helpers.
- LayerDM pipelines — per [ADR-0002](0002-migrate-to-slicerlayerdm.md);
  LayerDM provides a first-class Python abstract pipeline class.
- **Python VTK filters** — compute paths that do not have a measured
  per-frame or inner-loop bottleneck.  Python-bound filters keep the
  data flow through VTK's pipeline machinery while preserving Python
  iteration speed.  This is the default home for new compute under
  ADR-0002's "unify the language seam" Decision bullet.
- Tests — per [ADR-0003](0003-testability-invariant.md); the Slicer
  self-test pattern is Python.
- Build / packaging glue.

The boundary is **stable** — choose carefully when crossing it.  PRs
that move logic from Python to C++ for performance reasons must carry
a profile that demonstrates the need; PRs that move data-only nodes
from C++ to Python are out of scope.

## Alternatives considered

### A. All C++

Keep the current pattern; the LayerDM migration just swaps MRMLDM for
LayerDM internals.

**Rejected** because:

- The maintenance burden stays high — every PR is a Slicer rebuild.
- Refactor cost dominates the migration horizon; an all-C++ migration
  takes years more than necessary.
- Contributor barrier remains high; the researcher-heavy team gives up
  iteration speed it should not have to.
- LayerDM's Python pipeline API is wasted; we'd be using LayerDM at a
  small fraction of its capability.

### B. All Python (including MRML nodes via `vtkMRMLScriptedModuleNode`)

Push everything to Python, including the MRML node classes — declare
them as `vtkMRMLScriptedModuleNode` instances at module load time.

**Rejected** because `vtkMRMLScriptedModuleNode` is too limited for a
clinical artefact:

- **Scene introspection is weaker** — other modules querying the scene
  for "all `vtkMRMLLiverResectionNode` instances" rely on the proper
  C++ type for the `IsA()` check; scripted nodes use a string-based
  attribute hack that is brittle and reads as "magic" to consumers.
- **Storage round-tripping is rougher** — scripted node serialization
  goes through a generic attribute path that loses type fidelity
  (everything becomes string-keyed); migration to a different
  representation is harder.
- **Custom validators on Set/Get** (range checks on margins, enum
  validation on State, etc.) are awkward to attach.
- **The risk surface is wrong** for clinical software: a "we tried
  this experimental Python escape hatch" decision is exactly the kind
  of choice that bites in clinical use months after the fact.

The pragmatic compromise — C++ for nodes, Python for everything else
— gives 90% of the iteration-speed benefit at a fraction of the risk.

### C. Mixed without an explicit boundary

Decide case-by-case in each PR whether to use C++ or Python.

**Rejected** because every PR becomes a re-litigation of the same
question, review comments accumulate around it, and convention drifts
over time.  A documented boundary turns a recurring debate into a
single decision a reviewer can point at.

### D. Migrate the existing tuned C++ algorithm libraries to Python

Reimplement the existing Bezier evaluation, distance-map, and related
inner-loop algorithms in Python (typically via NumPy).

**Rejected** because:

- The existing C++ implementations are tuned and used in inner loops
  (per-frame surface evaluation, real-time distance updates).
- NumPy equivalents are usually fast enough but not always; profiling
  every algorithm to confirm is expensive work for no clear gain.
- The C++ algorithm surface is small (handful of classes) and stable
  — exactly the kind of place where C++ pays back.

This rejection is **narrow**: it covers reimplementing the existing
tuned native code in Python without a triggering reason.  It is
*not* a blanket ban on Python algorithms.  New compute defaults to a
Python VTK filter unless a profile justifies native speed — captured
by the "Performance-critical algorithm libraries" C++ band above.

## Consequences

### Easier

- **Contributor onboarding** — a new researcher can ship a useful PR
  without learning Slicer's C++/Qt/CMake stack.  C++ knowledge is
  needed only for the small node-and-algorithm band.
- **Refactor turnaround** — Python iteration is seconds; the LayerDM
  migration becomes tractable in calendar-realistic timelines.
- **Test infrastructure** — Slicer's Python self-test framework is
  mature; tests are fast to write and fast to run; the testability
  invariant in [ADR-0003](0003-testability-invariant.md) is cheaper
  to honour.
- **UI iteration** — Qt designer `.ui` + Python wiring round-trips
  in seconds; tweaking layouts in C++ is painful.
- **Build/distribution** — the Python surface is one source tree
  working across Slicer versions; only the C++ surface needs per-
  version / per-Qt / per-platform binary builds.  The Qt5/Qt6 split
  shrinks correspondingly.

### Harder

- **Maintaining the discipline** — the temptation to "just write this
  in C++" is real when a Python implementation feels clunky.  Resist
  unless the case fits one of the two C++ bands (data-only MRML node;
  algorithm library).  The `/slicer-review` reviewer flags drift.
- **C++/Python boundary crossings** — VTK observer chains crossing
  the boundary are well-known to have measurable overhead (the
  Python callback round-trip goes through `vtkPythonCommand`).  Fine
  for UI events; bad for per-frame render hooks.  Keep Python
  callbacks out of inner loops.  LayerDM pipelines handle this
  correctly when used per its API.  Profile before assuming a
  Python-side observer is "free".
- **Some kinds of static typing/introspection** we'd get in C++ are
  weaker in Python.  Mitigate with `typing`/`mypy`, but accept that
  the discipline is convention rather than compiler-enforced.
- **Performance profiling is now part of routine PR review — both
  directions.**  PRs moving logic from C++ to Python (or adding
  Python on a path that used to be C++) carry a profile /
  microbenchmark showing no regression.  PRs introducing *new* C++
  compute carry a profile showing a Python VTK filter would not
  have sufficed.  The `/slicer-review` reviewer can be extended with
  this check.
- **Two test infrastructures coexist temporarily** — Python self-tests
  for new code, CTest C++ tests for the legacy C++ that has not yet
  migrated.  Both must pass on CI.
- **Lazy `slicer.util.pip_install` is mandatory for heavy Python
  deps.**  Modules that need numpy-extras, monai, torch, etc. must
  `pip_install` them on first use (inside the function that needs
  them) — never at module import time.  Eager imports stall Slicer
  startup during module enumeration; the lazy pattern is the
  convention in `Base/Python/slicer/util.py` (see existing usages of
  `pip_install` for the try-import-then-prompt template).

## References

- Slicer scripted module base classes:
  `Base/Python/slicer/ScriptedLoadableModule.py` in the Slicer source
  tree.
- Slicer Python utilities (`getNode`, `loadVolume`, `arrayFromVolume`,
  `pip_install`): `Base/Python/slicer/util.py`.
- LayerDM Python abstract pipeline class: source at
  `~/src/SlicerLayerDisplayableManager/LayerDM/MRMLDM/Python/vtkMRMLLayerDMScriptedPipeline.py`
  (the top-level `Python/` directory is only a 2-line re-export
  shim; the class is consumed in extension mode as
  `from LayerDMLib import vtkMRMLLayerDMScriptedPipeline`).  Online
  architecture docs at
  https://slicerlayerdisplayablemanager.readthedocs.io/
- `vtkMRMLScriptedModuleNode` mechanism — for the record of why it's not
  used here; see Slicer source `Libs/MRML/Core/vtkMRMLScriptedModuleNode.h`
  (note the limited scope vs a proper subclass).
- Related:
  - [ADR-0002](0002-migrate-to-slicerlayerdm.md) — the migration this
    language convention enables (LayerDM's Python pipelines are first-
    class).
  - [ADR-0003](0003-testability-invariant.md) — the testability
    invariant, made cheaper by Python-first.
