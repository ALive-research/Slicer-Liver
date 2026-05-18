# Control-grid grouping — M×N ring-group taxonomy

Reference companion to [ADR-0014][adr-0014] §3 +
[ADR-0018][adr-0018] §1.  Generalises the
`vtkLiverBezierWidget` right-drag ring-group taxonomy from the v1
fixed-4×4 case to arbitrary M×N control polygons.

[adr-0014]: ../adr/0014-livermarkups-dissolution.md
[adr-0018]: ../adr/0018-nurbs-extension-surface.md

## Ring formula

For an M-row × N-column control polygon:

- **Corners** — always exactly `4`.
- **Edges** — `2 * (M - 2) + 2 * (N - 2)` — boundary points minus corners.
- **Interior** — `(M - 2) * (N - 2)` — non-boundary points.
- **Total** — `M * N` — sanity check: `4 + 2(M-2) + 2(N-2) + (M-2)(N-2) = MN`.

| (M, N)  | Corners | Edges | Interior | Total |
|---------|---------|-------|----------|-------|
| (3, 3)  | 4       | 4     | 1        | 9     |
| (4, 4)  | 4       | 8     | 4        | 16    |
| (5, 4)  | 4       | 10    | 6        | 20    |
| (5, 5)  | 4       | 12    | 9        | 25    |
| (5, 7)  | 4       | 16    | 15       | 35    |
| (M, N)  | 4       | 2(M-2)+2(N-2) | (M-2)(N-2) | MN |

## Example layouts

Each cell is a control point; `C` = corner, `E` = edge, `I` =
interior.

### 4×4 (v1 default)

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

### 5×5

```
+---+---+---+---+---+
| C | E | E | E | C |
+---+---+---+---+---+
| E | I | I | I | E |
+---+---+---+---+---+
| E | I | I | I | E |
+---+---+---+---+---+
| E | I | I | I | E |
+---+---+---+---+---+
| C | E | E | E | C |
+---+---+---+---+---+
```

Corners = 4, Edges = 12, Interior = 9.  Total = 25.

### 5×7 (non-square)

```
+---+---+---+---+---+---+---+
| C | E | E | E | E | E | C |
+---+---+---+---+---+---+---+
| E | I | I | I | I | I | E |
+---+---+---+---+---+---+---+
| E | I | I | I | I | I | E |
+---+---+---+---+---+---+---+
| E | I | I | I | I | I | E |
+---+---+---+---+---+---+---+
| C | E | E | E | E | E | C |
+---+---+---+---+---+---+---+
```

Corners = 4, Edges = 16, Interior = 15.  Total = 35.

## Right-drag ring-group event flow

The `vtkLiverBezierWidget` right-drag event (per
[ADR-0014][adr-0014] §3, deferred under `TODO(T2.3 right-drag-ring-group)`)
manipulates the picked control point's **ring set** as a group.
Picking a corner translates / rotates all 4 corners; picking an edge
point manipulates the edge ring; picking an interior point
manipulates the interior ring.  The ring-set identification is
purely positional — `(row, col)` in `[0, M-1] × [0, N-1]`:

```
ring_of(row, col):
    if row in (0, M-1) and col in (0, N-1):
        return Corner
    if row in (0, M-1) or col in (0, N-1):
        return Edge
    return Interior
```

This formula is independent of M, N — the right-drag-ring-group
event flow inherits the formula mechanically, no per-size branching.

## Implications for `vtkLiverBezierFitter`

The fitter ([ADR-0015][adr-0015]) is independent of the ring taxonomy
— it sees only the flat control-grid array.  Per [ADR-0018][adr-0018]
§1, the fitter parameterizes its basis matrix on degree
`(Rows-1) × (Cols-1)` Bernstein; ring grouping does not feed into the
fit.  This is the right separation of concerns: the widget owns
*manipulation*, the fitter owns *math*.

[adr-0015]: ../adr/0015-cpp-algorithm-library.md

## Implications for `.lrp.json` schema v2

The schema v2 (per [ADR-0018][adr-0018] §1 rollout) carries explicit
`rows` + `cols` + `controlGrid: [3 * rows * cols doubles]` row-major.
The widget reads these to derive ring membership at load time.  No
ring metadata is serialised; it derives mechanically from `(rows,
cols)`.

## Out of scope of this diagram

- The widget's left-drag (per-point) event flow — handled by the
  existing skeleton (PR #360) and parameterizes trivially for any
  M×N.
- The widget's right-click context menu — separate
  `TODO(T2.3 right-click-context-menu)` deliverable.
- NURBS-specific manipulation events (e.g., "edit weight at corner")
  — deferred to v2.1's NURBS extension.
