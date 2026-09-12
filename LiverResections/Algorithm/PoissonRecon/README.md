# Vendored: PoissonRecon (Kazhdan)

Upstream <https://github.com/mkazhdan/PoissonRecon>, commit `262b0f5`
("Version 8.76"). MIT — see `LICENSE`, which is upstream's, unmodified.

Per [ADR-0040](../../../Docs/adr/0040-poisson-surface-reconstruction.md)
this is a **vendored drop, not a fork**: nothing under `Src/` is edited.
Our code lives outside this directory and includes these headers. Keeping
the drop pristine is what makes a future upstream sync a re-copy rather
than a merge.

## What is here, and what is not

Upstream `Src/` holds 82 headers plus 13 `.cpp` command-line mains. We
vendor **69 headers** and none of the mains.

The exclusions are not a hand-picked minimal set — they are two whole
upstream *variants* we do not build, which is what makes the rule
re-derivable when upstream moves:

| Excluded | Why |
| --- | --- |
| `Socket.{h,inl}`, `*ClientServer.h` | the **distributed** variant. These are the only files in `Src/` that reach for Boost. Dropping them is what makes the build Boost-free. |
| `Image.h`, `PNG.h`, `JPEG.h` | the **image** path, reached only from upstream's own mains for their `--colors` CLI option. It is also the one genuinely unportable part of upstream: against a *system* libpng it fails with `invalid use of incomplete type 'png_struct'`, because it reaches into internals opaque since libpng 1.5. Upstream's vendored `PNG/` tree is load-bearing for their executable; writing our own adapter against `Reconstructors.h` sidesteps it entirely. |

Consequently none of upstream's four vendored third-party trees (`PNG/`,
`JPEG/`, `ZLIB/`, and the Boost headers) are needed, and no heavyweight
dependency is inherited.

The transitive include closure of `Reconstructors.h` is **59 headers**, a
strict subset of the 69 here. The extra ten are the rest of the
non-excluded upstream surface, kept so the drop is "upstream minus two
variants" rather than "whatever the compiler happened to need on the day"
— the latter silently rots the moment upstream adds an include.

## Threading

`MultiThreading.h` guards OpenMP behind `#ifdef _OPENMP` and falls back
to `std::async` or single-threaded execution. We therefore do **not**
make OpenMP a build requirement; it is used if the toolchain offers it.

## Gotchas when including these headers

**Include VTK first.** Upstream's `Array.h` defines a function-like macro
named `Pointer`. VTK's `vtkBuffer` has a *member* named `Pointer` and
initialises it as `Pointer(nullptr)`, which the preprocessor rewrites to
`nullptr*`. Include PoissonRecon before VTK and the build fails inside
`vtkBuffer.h` with an error that mentions neither PoissonRecon nor a
macro.

Better still, keep these headers out of your own **headers** entirely, so
the macros stay inside one translation unit and no consumer can be
poisoned whatever order it includes things in.
`vtkLiverPoissonSurfaceReconstruction.h` forward-declares `vtkPolyData`
and includes nothing from here, on purpose.

**`outputGradients` defaults to false.** With it off, the per-vertex
gradient handed to a `OutputLevelSetVertexStream` is all zeros —
silently, with no error. Anything deriving normals from the level set
must set it.

## Syncing to a newer upstream

1. Check out the new upstream tag.
2. Re-copy `Src/*.h` and `Src/*.inl` **minus the excluded set above**.
3. Re-copy `LICENSE`; update the commit and version at the top of this file.
4. Confirm the exclusion rule still holds — `grep -rl boost Src/` upstream
   should still name only the socket files, and nothing we vendor should
   include `Image.h`.
5. Rebuild and run the adapter's tests. Reconstruction output is expected
   to shift slightly between upstream versions; the tests assert geometric
   agreement with a tolerance, not exact vertices.

Do not apply local fixes here. If upstream needs a change, the change
belongs upstream, and the workaround belongs in our adapter.
