# EXTERNAL_PRIOR_REPORT: Polyline Bulge and Arc Invariants

## 1. External Implementations Audited
1. **Autodesk DXF Reference (AutoCAD R14 through 2027):**
   - Specification: DXF Group Code 42 for `LWPOLYLINE` vertex records.
   - Definition: Floating point bulge value associated with vertex $i$. Describes the arc segment connecting vertex $i$ to vertex $i+1$.
   - Authority: Official Autodesk DXF Specification.
2. **ezdxf Geometry Kernel (`ezdxf.math.bulge`):**
   - Source: `ezdxf/math/bulge.py` (v1.4.x, MIT License).
   - Audited Functions: `bulge_to_arc`, `arc_to_bulge`, `bulge_center`, `bulge_radius`.
   - Verified Invariants:
     - Sagitta $h = \frac{L}{2} \cdot b$.
     - Radius $R = \frac{L}{4} \cdot \left(b + \frac{1}{b}\right)$.
     - Center offset from chord midpoint: $d = \frac{L}{4} \cdot \left(\frac{1}{b} - b\right)$ along normal vector.
3. **LibreCAD / QCAD C++ Geometry Core (`RS_Math::bulgeToArc`):**
   - Source: `librecad/src/lib/math/rs_math.cpp` (GPLv2, Clean-Room Behavioral Spec Only).
   - Invariant: Singularity protection when $|b| < 10^{-10}$; treats segment as straight vector.

---

## 2. Behavioral Invariant Summary
- **Zero Bulge:** Segment is collinear line; DXF omitted Group 42 or $0.0$.
- **Unit Bulge ($b = 1.0$ or $-1.0$):** Semicircle with diameter equal to chord length $L$.
- **Inflection Point / Negative Bulge:** Negative bulge indicates clockwise orientation; arc center lies to the right of vector $\vec{AB}$.
- **Numerical Stability Guard:** When $|b| < 10^{-7}$, radius exceeds $10^7 \cdot L$, which causes floating-point overflow and catastrophic cancellation in downstream intersection algorithms. The algorithm must snap $b \to 0.0$.
