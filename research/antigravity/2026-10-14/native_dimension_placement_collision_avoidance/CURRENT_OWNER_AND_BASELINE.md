# CURRENT_OWNER_AND_BASELINE: Native Dimension Placement Analysis (REA-023)

- **Document ID:** `REA_DIM_PLACEMENT_OWNER_BASELINE_V1`
- **Role:** `ANTIGRAVITY_RESEARCH_EXECUTOR`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-14
- **Capability:** `NATIVE_DIMENSION_PLACEMENT_COLLISION_AVOIDANCE` (REA-023)
- **Evidence Tier:** `BOUNDED_SYNTHETIC_RESEARCH_ORACLE`

---

## 1. Existing Owner Inspection

The authoritative production owner for native DXF dimension generation in Cad Agent is:

```text
CURRENT_EXISTING_OWNER = dxf_builder_lib/builder.py::_add_confirmed_dimensions
```

Verified on current main (`7da1ed42a2168b5c991fc389a4c8155b1e88a387`), the placement logic within `_add_confirmed_dimensions` is:

```python
# Place the dimension line on the outward normal, far enough from the
# measured line to remain legible without changing the measurement.
offset = max(length * 0.08, 5.0)
normal_x, normal_y = -dy / length, dx / length
midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
base = (midpoint[0] + normal_x * offset, midpoint[1] + normal_y * offset)
angle = math.degrees(math.atan2(dy, dx))
override = msp.add_linear_dim(
    base=base,
    p1=start,
    p2=end,
    location=base,
    angle=angle,
    dxfattribs={"layer": "DIMENSIONS"},
)
override.render()
```

### Owner Obstacle Trace Rectification
Inspection of `dxf_builder_lib/builder.py::build_confirmed_dxf` confirms:
- The argument `written_geometry_by_primitive_id` passed to `_add_confirmed_dimensions` **already contains text primitives** (`type="text"`, with `content`, `insert`, `height`, `rotation_deg`, and font style attributes).
- Therefore:
  - `TEXT_PRIMITIVES_AVAILABLE_AT_OWNER = YES`
  - `GEOMETRY_AND_TEXT_OBSTACLE_TRANSFER_REQUIRES_CALLER_INTERFACE_CHANGE = NO`
  - Any future candidate transfer would receive model geometry and text annotation obstacles directly through existing caller structures without schema changes.

---

## 2. Baseline Semantic Characterization

The current baseline implementation possesses the following exact invariants:

1. **Deterministic Single-Side Normal:**
   $$\mathbf{n}_{\text{baseline}} = \left(-\frac{\Delta y}{L}, \frac{\Delta x}{L}\right)$$
   Always chooses the left-hand perpendicular normal relative to vector $\vec{P}_1\vec{P}_2$. It never considers the opposite normal $(+\Delta y / L, -\Delta x / L)$.

2. **Fixed Proportional Offset:**
   $$d_{\text{baseline}} = \max(L \cdot 0.08, 5.0\text{ mm})$$
   Calculates a single scalar distance from the measured segment. It provides zero alternative lanes.

3. **Obstacle Blindness:**
   Does not inspect:
   - Part model geometry (interior pockets, ribs, bosses, holes)
   - Drawing annotation text (title blocks, notes, callouts)
   - Sheet / view boundary limits
   - Other previously placed or simultaneously placed dimensions

4. **Prototype Measurement Truth Preservation:**
   `p1=start` and `p2=end` are passed directly from the verified DXF `LINE` geometry.
   $$\text{Prototype Measurement Error} = |L_{\text{dim}} - L_{\text{true}}| \equiv 0.0$$
   This physical measurement truth is preserved algebraically by construction.
   `PRODUCTION_NATIVE_MEASUREMENT_PRESERVATION = NOT_VERIFIED_BY_THIS_ORACLE` (actual binary AutoCAD dimension entity readback is outside the scope of this standalone prototype research).

---

## 3. Systematic Baseline Failure Modes Across Synthetic Fixtures

Empirical evaluation across the 10 canonical fixtures revealed **17 total collisions across 7 failed scenes** (9 dimension-to-geometry crossings, 8 dimension-to-annotation overlaps, and 12 unwanted extension crossings, leaving 10 dimensions unresolved):

### Failure 1: Single-Side Obstacle Collision (Fixtures 6 & 7)
- **Scenario:** Measured edge has clear space on one side, but the default left-hand $+n$ side contains model geometry (Fixture 6, pocket cavity) or an annotation note box (Fixture 7).
- **Baseline Behavior:** Emits `base` directly inside the obstacle, causing 2 hard collisions per scene (dimension line crosses geometry and dimension text overlaps obstacle).
- **Impact:** Dimension text is unreadable; dimension line cuts across drawing features.

### Failure 2: Parallel Dimension Stacking Conflict (Fixture 4)
- **Scenario:** Two parallel stepped edges separated by 8 mm (e.g. keyway or shaft shoulder).
- **Baseline Behavior:** Both dimensions evaluate to proportional offsets along $+n$, placing Line 1's dimension line at $y = 206.4$ and Line 2's dimension line at $y = 217.6$, with text bounding boxes directly overlapping or crossing adjacent witness geometry.
- **Impact:** Cluttered overlapping text violating drafting standards.

### Failure 3: Drawing Boundary Escape (Fixture 9)
- **Scenario:** Measured edge at $y = 495\text{ mm}$ located near the top sheet border ($y_{\text{max}} = 500\text{ mm}$).
- **Baseline Behavior:** Default $+n$ pushes `base` to $y = 503\text{ mm}$, placing text outside the drawing sheet.
- **Impact:** Critical dimension text is truncated or clipped during plotting.

### Failure 4: Oblique, Crowded, and Perpendicular Crossing Hazards (Fixtures 5, 8 & 10)
- **Scenario:** Collinear shoulder (Fixture 5, 1 collision, 2 unresolved), crowded short segments (Fixture 8, 8 collisions, 2 unresolved), and L-bracket corner (Fixture 10, 2 collisions, 1 unresolved) where horizontal and vertical lines meet.
- **Baseline Behavior:** Fixed offset creates extension line crossings with flanking geometry corners, text overlaps on neighboring ribs, and dimension line crossings between collinear or intersecting features.

---

## 4. Boundary and Scope Rule

> [!IMPORTANT]
> This research is **NOT authorization to edit `_add_confirmed_dimensions`**.
> Any future production transfer must remain conditional on an explicit measured product RED where baseline placement fails on real drawing comparisons. Until then, `PRODUCTION_TRANSFER_AUTHORIZED=NO`.
