# Slicer-Liver visual-regression test harness

This directory hosts the **golden-image regression test infrastructure** for
the LiverResections module — characterisation tests that pin the v2.0.0
Bezier mapper's pixel output before the v2.1 GPU-tessellation rewrite
([ADR-0020](../../Docs/adr/0020-gpu-tessellation.md) §"Rollout plan" §7).

The harness is the foundation that subsequent mapper-affecting PRs use
as their regression gate.

## Layout

```
LiverResections/Testing/
├── Cxx/                          C++ unit tests (existing)
├── Python/
│   ├── CMakeLists.txt            ExternalData + CTest wiring
│   ├── __init__.py
│   ├── capture_baseline.py       Interactive capture driver (user-run)
│   ├── replay_test.py            CI replay driver (CTest-run)
│   └── scenarios/
│       ├── __init__.py
│       ├── BezierSurface4x4Planning.py
│       └── BezierSurface4x4Confirmed.py
├── Data/Baseline/                .sha512 content-hash stubs (committed)
└── Scripts/
    └── upload_baseline.sh        gh release upload + stub-rotation helper
```

Plus a transient `Testing/baselines-staging/` directory (gitignored)
that the capture flow writes to before the upload script copies the
content into the release.

## Test level

Per the task brief and the precedent set by SlicerLayerDM and
trame-slicer, the harness runs at **Level 2 — minimal `qSlicerApplication`**:

```bash
Slicer --no-main-window --python-script <script> -- --test <name>
```

This is the correct level because the Bezier mapper is driven by display
nodes + scene observers; the integration seam *is* the bug surface.
Pure-VTK Level-1 tests would miss observer-ordering regressions.

## Bundle contents

Every baseline is a **reproducible recipe**, not a photograph.  For
each scenario `<test-name>` the bundle is:

| Asset                          | Role                                                                   |
|--------------------------------|------------------------------------------------------------------------|
| `<test-name>.png`              | Comparison target.  Pixel-level golden image.                          |
| `<test-name>.mrml`             | Full scene saved via `slicer.util.saveScene()`.                        |
| `<test-name>.camera.json`      | `vtkCamera` state — position, focal point, view up, parallel scale, view angle, clipping range. |
| `<test-name>.viewport.json`    | Render-window pixel size, background, anti-aliasing, GL profile.       |
| `<test-name>.notes.md`         | (optional) human rationale for what the baseline validates.            |

The bundle lives as release assets on
`github.com/ALive-research/ALiveResearchTestingData`, which follows
the [SlicerTestingData mirror pattern](https://github.com/Slicer/SlicerTestingData):

- One release per hash algorithm, named `<HASHALGO>` (`SHA256`,
  `SHA512`, …).  The visual-regression harness uses **`SHA512`**
  (CMake `ExternalData`'s default for new content addressing).
- Release assets are named by their `<hashsum>` — there is no
  per-purpose tag (no `liver-test-baselines-v1`).  The same `SHA512`
  release backs every Slicer-Liver fixture and any future ALive
  fixture.
- A sibling `SHA512.csv` in the repo root maps `<hashsum>;<filename>`;
  `process_release_data.py` regenerates `SHA512.md` on each upload.

In the Slicer-Liver repo the bundle is represented by **64-byte
`.sha512` content-hash stubs** under `Data/Baseline/`.  CMake's
`ExternalData` module resolves them lazily at test time by fetching
the matching blob from:

```
https://github.com/ALive-research/ALiveResearchTestingData/releases/download/SHA512/<hash>
```

## Workflow

### Replay (CI)

```
CTest entry  ──►  Slicer --no-main-window --python-script replay_test.py
                  --test <name> --baseline-dir … --scenarios-dir …
              ──►  scenario.setup_scene()  +  setup_camera()  +  setup_viewport()
              ──►  vtkWindowToImageFilter snapshot
              ──►  vtkImageDifference vs baseline PNG (tolerance 0.15)
              ──►  exit 0 / 1
```

ExternalData wires the lazy fetch: the CTest entry references
`DATA{<test>.png.sha512}` which CMake expands at configure time; the
test invocation runs only after the blob is on disk.

### Capture (developer / maintainer)

The interactive capture is **user-launched** — the agent does not
orchestrate it.  Once a behaviour change is approved for baseline
rotation, the maintainer runs:

```bash
Slicer --no-main-window \
       --python-script LiverResections/Testing/Python/capture_baseline.py \
       --test BezierSurface4x4Planning
```

A Qt window opens with the scenario rendered.  Keypresses:

- **`s`** Save the four-file bundle to `Testing/baselines-staging/<test>.*`
  and print the next-step hint.
- **`q`** Quit without saving.

After visual approval, hash + stage the bundle for the testing-data
repo's canonical `INCOMING/` workflow:

```bash
export ALIVE_TESTING_DATA_INCOMING=~/src/ALiveResearchTestingData/INCOMING
./LiverResections/Testing/Scripts/upload_baseline.sh BezierSurface4x4Planning
```

The script:

1. Bundle-completeness pre-flight: refuses to proceed unless all four
   sidecars (`.png`, `.mrml`, `.camera.json`, `.viewport.json`) are
   present in staging.
2. Computes SHA-512 of each staged file.
3. Two-pass atomic stage: writes the `.sha512` stubs under
   `Data/Baseline/` AND copies the staged artefacts into the
   testing-data repo's `INCOMING/` directory.

Then run the testing-data canonical upload script:

```bash
cd ~/src/ALiveResearchTestingData
python process_release_data.py upload --hashalgo SHA512 \
                                      --github-token "$GH_TOKEN"
git add SHA512.csv SHA512.md
git commit -m "ENH: Add BezierSurface4x4Planning visual-regression baseline"
git push
```

Finally on the Slicer-Liver side:

```bash
git add LiverResections/Testing/Data/Baseline/BezierSurface4x4Planning.*.sha512
git commit -m "ENH: Capture BezierSurface4x4Planning visual-regression baseline"
```

## Adding a new scenario

1. Drop a `<NewScenario>.py` module under `Python/scenarios/`.  Expose
   `setup_scene()`, `setup_camera()`, `setup_viewport()`, `describe()`.
   See `BezierSurface4x4Planning.py` for the canonical shape.
2. Add the scenario name to the `_visual_test_scenarios` list in
   `Python/CMakeLists.txt`.
3. Run the capture flow + upload script as documented above.
4. Commit the four `.sha512` stubs plus the scenario module.

The CTest entry registers automatically once the scenario is listed in
the CMake; no per-scenario CMake boilerplate.

## Bumping baselines after a Slicer/VTK/image upgrade

When a Slicer / VTK / VTK-image upgrade causes legitimate visual drift
(e.g., a freetype version change or a Mesa rasteriser change), every
baseline needs re-capture.  Because the testing-data repo is
**content-addressed** (one `SHA512` release; no per-purpose tags), the
procedure does NOT involve rotating a release tag.  Just re-capture:

1. For each scenario, run the capture flow + upload script (same as
   the per-scenario capture path documented above).  New hashes are
   computed; new assets land in the `SHA512` release; the
   `<HASHALGO>.csv` grows.
2. The `.sha512` stubs in `Data/Baseline/` rotate automatically as
   part of the upload script.
3. Commit the rotated stubs on the Slicer-Liver side; commit the
   `SHA512.csv` update on the testing-data side.

The old hashes stay in the release indefinitely (content-addressed;
no deletion needed for forward-compat).  History remains
reproducible.

## Bootstrapping a local testing-data clone (one-time)

```bash
cd ~/src
git clone https://github.com/ALive-research/ALiveResearchTestingData.git
cd ALiveResearchTestingData
# process_release_data.py requires the githubrelease package.
pip install --user githubrelease

# Export the INCOMING path for the upload script.
export ALIVE_TESTING_DATA_INCOMING=~/src/ALiveResearchTestingData/INCOMING

# Verify the SHA512 release exists.  If not, ask a maintainer to run:
#     gh release create SHA512 --repo ALive-research/ALiveResearchTestingData \
#       --title "SHA512" --notes "SHA512-keyed content-addressed assets."
# and create the initial SHA512.csv as an empty file in the repo root.
gh release view SHA512 --repo ALive-research/ALiveResearchTestingData
```

## Initial scope (v2.0.0)

Two scenarios land in this first PR:

- **`BezierSurface4x4Planning`** — 4×4 Bezier surface, default fixture,
  parenchyma trim OFF (`ClipOut=0`).  The "full surface visible" baseline.
- **`BezierSurface4x4Confirmed`** — same fixture, parenchyma trim ON
  (`ClipOut=1`).  The "discarded side" baseline.

The Confirmed scenario currently drives `ClipOut` directly because the
state machine described in ADR-0019 has not landed yet (issue #18).
The TODO comment inside `BezierSurface4x4Confirmed.py::setup_scene`
marks the migration anchor; when ADR-0019 lands the scenario migrates
to `resection.SetState(resection.Confirmed)`.

## CI integration

The build-test job in `.github/workflows/ci.yml` runs CTest after
configure + build.  Visual-regression entries get the label
`visual-regression` and are wired with `QT_QPA_PLATFORM=offscreen` in
their environment.  No special CI workflow changes are needed for the
infrastructure itself — the entries run via the standard `ctest -V`
invocation.

If a GPU-stack issue prevents offscreen GL on the CI image, gate the
entries with `LIVER_RUN_VISUAL_TESTS=1` as described in the task brief
and add a `continue-on-error: true` smoke step in the workflow.
