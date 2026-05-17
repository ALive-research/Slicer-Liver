# SlicerLayerDisplayableManager (LayerDM) — build dependency

Slicer-Liver depends on
[SlicerLayerDisplayableManager][upstream] (LayerDM) at build time per
[ADR-0002][adr-0002] (migration commitment) and [ADR-0013][adr-0013] §5
(three registration calls).  `SlicerLayerDisplayableManager` is listed
unconditionally in Slicer-Liver's `EXTENSION_DEPENDS` block in the
root `CMakeLists.txt`.

[upstream]: https://github.com/KitwareMedical/SlicerLayerDisplayableManager
[adr-0002]: ../adr/0002-migrate-to-slicerlayerdm.md
[adr-0013]: ../adr/0013-layerdm-pipeline-pattern.md

## CI build layer

The repository CI (`.github/workflows/ci.yml`) builds SlicerLayerDM as
a prerequisite of the `build-test (slicer-main, Linux)` job:

1. Clones SlicerLayerDM at a pinned commit (see `LAYERDM_SHA` env var
   in the workflow file).
2. Configures + builds it against the same Slicer build tree the
   canonical job uses (`/usr/src/Slicer-build/Slicer-build` in the
   `ghcr.io/alive-research/slicer-build-ubuntu2404` image).
3. Caches the resulting build tree on `(runner_os, LAYERDM_SHA)` so
   subsequent runs at the same pin skip the clone + build.
4. Passes `-DSlicerLayerDisplayableManager_DIR=<LAYERDM_BUILD>` to
   Slicer-Liver's configure.

Bumping the pinned SHA is a deliberate workflow edit; document the
rationale in the commit message.

## Local developer workflow

Assuming a Slicer-main build tree already exists at `<SLICER_BUILD>`
(the path that contains `SlicerConfig.cmake`), the three-step local
workflow is:

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

SlicerLayerDM is a flat-layout Slicer extension — `project(LayerDisplayableManager)`
produces `LayerDisplayableManagerConfig.cmake` at the **build root**.
`SlicerLayerDisplayableManager_DIR` therefore points at
`<SLICERLAYERDM_BUILD>` itself, not at any inner subdirectory.

### 3. Configure Slicer-Liver

```sh
cmake -S <SLICER_LIVER_SRC> -B <SLICER_LIVER_BUILD> \
      -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTING=ON \
      -DSlicer_DIR=<SLICER_BUILD> \
      -DSlicerLayerDisplayableManager_DIR=<SLICERLAYERDM_BUILD>
cmake --build <SLICER_LIVER_BUILD> -j
```

Then launch Slicer with the Slicer-Liver build tree's additional
module path the way you normally do — both Slicer-Liver's modules and
the upstream LayerDM module will be available in the launched Slicer
process.

## Cross-references

- [ADR-0002][adr-0002] — migration commitment to SlicerLayerDM.
- [ADR-0013][adr-0013] §5 — the three registration calls every
  LayerDM-aware module performs.
- `CONTRIBUTING.md` — top-level development setup; this document is
  linked from its "Development setup" section.
