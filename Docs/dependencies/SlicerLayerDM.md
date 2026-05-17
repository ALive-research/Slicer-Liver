# SlicerLayerDisplayableManager (LayerDM) — opt-in build dependency

Slicer-Liver carries an **opt-in** build-time dependency on
[SlicerLayerDisplayableManager][upstream] (LayerDM) — the upstream
displayable-manager framework Slicer-Liver is migrating onto
([ADR-0002][adr-0002]).  The dependency is gated by a CMake option so
that the canonical CI cell and default developer builds stay
byte-identical to pre-LayerDM Slicer-Liver until the migration code
lands and stabilises.

[upstream]: https://github.com/KitwareMedical/SlicerLayerDisplayableManager
[adr-0002]: ../adr/0002-migrate-to-slicerlayerdm.md
[adr-0013]: ../adr/0013-layerdm-pipeline-pattern.md

## What the flag enables

`Slicer_Liver_USE_SlicerLayerDM` (default **OFF**) appends
`SlicerLayerDisplayableManager` to Slicer-Liver's `EXTENSION_DEPENDS`
list at configure time.  When ON, Slicer's CMake machinery picks up
`SlicerLayerDisplayableManager_DIR` and folds the LayerDM extension's
build tree into the Slicer launcher's `ADDITIONAL_MODULE_PATHS` — so
that Slicer-Liver modules can `import LayerDMLib` and reach the
upstream `vtkMRMLLayerDMScriptedPipeline` base class, the
`vtkMRMLLayerDMPipelineFactory`, and the LayerDM-aware
`vtkMRMLLayerDisplayableManager` per [ADR-0013][adr-0013] §5.

When the flag is OFF (the default), Slicer-Liver does **not** depend on
LayerDM at configure, build, or runtime.  Production packaging
flows the OFF path until the migration is complete.

## CI build layer

The repository CI (`.github/workflows/ci.yml`) carries a sibling job
`build-test-layerdm` that exercises the ON path:

1. Clones SlicerLayerDM at a pinned commit (see `LAYERDM_SHA` env var
   in the workflow file).
2. Configures + builds it against the same Slicer build tree the
   canonical `build-test (slicer-main, Linux)` job uses
   (`/usr/src/Slicer-build/Slicer-build` in the project-managed
   `ghcr.io/alive-research/slicer-build-ubuntu2404` image).
3. Configures Slicer-Liver with
   `-DSlicer_Liver_USE_SlicerLayerDM=ON` and
   `-DSlicerLayerDisplayableManager_DIR=<LayerDM-build>/LayerDM-build`.
4. Builds Slicer-Liver and runs the same CTest suite as the canonical
   cell.

The build-test-layerdm job runs with `continue-on-error: true` — it is
**informational** while the migration is in flight, not a merge gate.
The canonical `build-test (slicer-main, Linux)` job stays
authoritative.  Once T2.6-LayerDM lands and stabilises, the
expectation is to flip the merge-gate role to the ON-path cell (see
ADR-0012 for the v2.0.0 cutover scope).

## Local developer workflow

Assuming a Slicer main build tree already exists at
`<SLICER_BUILD>` (e.g. the path where you keep your local Slicer-main
checkout's `Release-qt6/Slicer-build`), the three-step local workflow
is:

### 1. Clone SlicerLayerDM (once)

```sh
git clone https://github.com/KitwareMedical/SlicerLayerDisplayableManager.git \
  <SLICERLAYERDM_SRC>
```

If you already have a local clone, fetch the latest from upstream and
check out the pinned ref (see `LAYERDM_SHA` in
`.github/workflows/ci.yml` for the exact commit CI builds against):

```sh
cd <SLICERLAYERDM_SRC>
git fetch origin
git checkout <pinned-sha>
```

### 2. Build SlicerLayerDM against your Slicer build tree

```sh
cmake -S <SLICERLAYERDM_SRC> -B <SLICERLAYERDM_BUILD> \
      -DCMAKE_BUILD_TYPE=Release \
      -DSlicer_DIR=<SLICER_BUILD>
cmake --build <SLICERLAYERDM_BUILD> -j
```

The LayerDM extension follows the standard Slicer
"inner-build-with-doubled-suffix" layout — the directory that contains
the produced `LayerDMConfig.cmake` (or the dependency-build directory
Slicer-Liver should consume) is `<SLICERLAYERDM_BUILD>/LayerDM-build`.
That path is what `SlicerLayerDisplayableManager_DIR` should point at.

### 3. Configure Slicer-Liver with the flag ON

```sh
cmake -S <SLICER_LIVER_SRC> -B <SLICER_LIVER_BUILD> \
      -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTING=ON \
      -DSlicer_DIR=<SLICER_BUILD> \
      -DSlicer_Liver_USE_SlicerLayerDM=ON \
      -DSlicerLayerDisplayableManager_DIR=<SLICERLAYERDM_BUILD>/LayerDM-build
cmake --build <SLICER_LIVER_BUILD> -j
```

Then launch Slicer with the Slicer-Liver build tree's additional
module path the way you normally do — both Slicer-Liver's modules and
the upstream LayerDM module will be available in the launched Slicer
process.

## Switching back to the OFF path

```sh
cmake -B <SLICER_LIVER_BUILD> -DSlicer_Liver_USE_SlicerLayerDM=OFF
cmake --build <SLICER_LIVER_BUILD> -j
```

The flag flips the `EXTENSION_DEPENDS` list back to the production
shape; no clean rebuild is strictly required, but a clean configure
tree is recommended when bisecting LayerDM-related regressions.

## Cross-references

- [ADR-0002][adr-0002] — the migration commitment.
- [ADR-0013][adr-0013] — the canonical LayerDM Pipeline pattern, §5
  enumerates the three registration calls every LayerDM-aware module
  performs.
- `CONTRIBUTING.md` — top-level development setup; this document is
  linked from its "Development setup" section.
