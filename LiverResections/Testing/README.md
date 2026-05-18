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
`github.com/ALive-research/ALiveResearchTestingData` (release tag
**`liver-test-baselines-v1`**, bumped per the rule in
[ADR-0020](../../Docs/adr/0020-gpu-tessellation.md) §"Rollout plan").

In the Slicer-Liver repo the bundle is represented by **64-byte
`.sha512` content-hash stubs** under `Data/Baseline/`.  CMake's
`ExternalData` module resolves them lazily at test time by fetching
the matching blob from:

```
https://github.com/ALive-research/ALiveResearchTestingData/releases/download/liver-test-baselines-v1/SHA512/<hash>
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

After visual approval:

```bash
./LiverResections/Testing/Scripts/upload_baseline.sh BezierSurface4x4Planning
```

The script:

1. Computes SHA-512 of each staged file.
2. Uploads each as a release asset on `ALiveResearchTestingData` (named by its
   digest; `--clobber` so re-captures replace cleanly).
3. Writes the matching `.sha512` stubs under `Data/Baseline/`.
4. Prints `git add` + `git commit` hints.

Finally:

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

## Bumping the baseline tag

When a Slicer / VTK / VTK-image upgrade causes legitimate visual drift
(e.g., a freetype version change or a Mesa rasteriser change), every
baseline needs re-capture.  The tag-bump procedure is:

1. Create the next-N release on `ALiveResearchTestingData`:

   ```bash
   gh release create liver-test-baselines-v2 \
     --repo ALive-research/ALiveResearchTestingData \
     --title "Slicer-Liver visual-regression test baselines v2" \
     --notes "Re-captured against Slicer X.Y.Z + VTK A.B.C."
   ```

2. Edit the URL template in `Python/CMakeLists.txt`:

   ```cmake
   "https://github.com/.../releases/download/liver-test-baselines-v2/%(algo)/%(hash)"
   ```

3. Run the capture flow for every scenario.  The upload script
   accepts an optional tag argument:

   ```bash
   ./LiverResections/Testing/Scripts/upload_baseline.sh BezierSurface4x4Planning liver-test-baselines-v2
   ```

4. Commit the rotated `.sha512` stubs and the CMakeLists.txt URL
   change in a single PR.  The PR title should be `ENH: Bump
   visual-regression baselines to liver-test-baselines-v2`.

## Bootstrapping the release (one-time per organisation)

When the release tag namespace is first established on
`ALiveResearchTestingData`:

```bash
gh release create liver-test-baselines-v1 \
  --repo ALive-research/ALiveResearchTestingData \
  --title "Slicer-Liver visual-regression test baselines v1" \
  --notes "Baseline image bundles for Slicer-Liver visual-regression tests.  Tag namespace: liver-test-baselines-vN.  Bump N when baselines change (Slicer/VTK/image bump).  This release backs Slicer-Liver's Testing/Data/Baseline/*.sha512 fixtures resolved via CMake ExternalData."
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
