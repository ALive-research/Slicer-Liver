# Control-grid grouping — `{3×3, 4×4}` ring-group taxonomy

Reference companion to [ADR-0014][adr-0014] §3 +
[ADR-0018][adr-0018] §1.  The `vtkLiverBezierWidget`'s right-drag
ring-group taxonomy operates on the two control-polygon shapes
v2.0.0 admits: **3×3** and **4×4** (square only).

Per [ADR-0018][adr-0018] §"Why `{3×3, 4×4}` square-only, not
arbitrary M×N in v2.0.0", both shapes have a natural three-ring
structure (corners, edges, interior) that matches the ring-of-
control-points manipulation philosophy.  Non-square shapes and
larger sizes are v2.1 NURBS territory.

[adr-0014]: ../adr/0014-livermarkups-dissolution.md
[adr-0018]: ../adr/0018-nurbs-extension-surface.md

## Ring counts

| Shape   | Corners | Edges | Interior | Total |
|---------|---------|-------|----------|-------|
| **3×3** | 4       | 4     | 1        | 9     |
| **4×4** | 4       | 8     | 4        | 16    |

## Layouts

Each cell is a control point; `C` = corner, `E` = edge, `I` =
interior.

### 3×3 — degree-2 Bezier (the smaller shape ADR-0018 adds)

```
+---+---+---+
| C | E | C |
+---+---+---+
| E | I | E |
+---+---+---+
| C | E | C |
+---+---+---+
```

Corners = 4, Edges = 4, Interior = 1.  Total = 9.

### 4×4 — degree-3 Bezier (the v2.0.0 default)

```
+---+---+---+---+
| C | E | E | C |
+---+---+---+---+
| E | I | I | E |
+---+---+---+---+
| E | I | I | E |
+---+---+---+---+
| C | E | E | C |
+---+---+---+---+
```

Corners = 4, Edges = 8, Interior = 4.  Total = 16.

## Right-drag ring-group event flow

The `vtkLiverBezierWidget` right-drag event (per
[ADR-0014][adr-0014] §3, deferred under `TODO(T2.3 right-drag-ring-group)`)
manipulates the picked control point's **ring set** as a group.
Picking a corner translates / rotates all 4 corners; picking an edge
point manipulates the edge ring; picking an interior point
manipulates the interior ring.  The ring-set identification is
purely positional — `(row, col)` in `[0, Rows-1] × [0, Cols-1]`:

```
ring_of(row, col, Rows, Cols):
    if row in (0, Rows-1) and col in (0, Cols-1):
        return Corner
    if row in (0, Rows-1) or col in (0, Cols-1):
        return Edge
    return Interior
```

This formula is shape-agnostic — the same code handles 3×3 and 4×4.
The widget's runtime validates `(Rows, Cols) ∈ {(3, 3), (4, 4)}` at
its `SetBezierNode()` entry; other shapes are rejected by the data
node's `SetRows`/`SetCols` setters per [ADR-0018][adr-0018] §1.

## Implications for `vtkLiverBezierFitter`

The fitter ([ADR-0015][adr-0015]) is independent of the ring taxonomy
— it sees only the flat control-grid array.  Per [ADR-0018][adr-0018]
§1, the fitter parameterizes its basis matrix on degree-`(Rows-1)`
Bernstein (degree-2 for 3×3; degree-3 for 4×4).  Ring grouping does
not feed into the fit.  This is the right separation of concerns:
the widget owns *manipulation*, the fitter owns *math*.

[adr-0015]: ../adr/0015-cpp-algorithm-library.md

## Implications for `.lrp.json` schema v2

The schema v2 (per [ADR-0018][adr-0018] §1 rollout) carries explicit
`rows` + `cols` + `controlGrid: [3 * rows * cols doubles]` row-major.
Schema v2 readers validate `(rows, cols) ∈ {(3, 3), (4, 4)}` at load
+ reject otherwise with `vtkErrorMacro`.  Forward-compat: v3 readers
(post NURBS landing) admit larger M×N for the NURBS node sibling but
keep the {3×3, 4×4} restriction for Bezier nodes.

## Out of scope of this diagram

- The widget's left-drag (per-point) event flow — handled by the
  existing skeleton (PR #360) and parameterizes trivially for both
  shapes.
- The widget's right-click context menu — separate
  `TODO(T2.3 right-click-context-menu)` deliverable.
- NURBS-specific manipulation events (e.g., "edit weight at corner")
  — deferred to v2.1's NURBS extension.  v2.1 may relax to arbitrary
  M×N for NURBS surfaces; Bezier stays {3×3, 4×4}.
