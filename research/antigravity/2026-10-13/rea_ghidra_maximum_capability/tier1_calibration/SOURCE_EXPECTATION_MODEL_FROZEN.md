# TIER 1 SOURCE EXPECTATION MODEL (Ground Truth Specification)

## Target Subsystem: libcadgeom_core
- **Language:** C99
- **Compiler:** MSVC 19.51.36248 (x64)
- **Target Role:** Standalone 2D CAD Computational Geometry Kernel
- **Binary:** cadgeom_core.exe
- **Function Count:** 12 core geometric functions + 2 intrinsics

## Detailed Function Invariant Table

| Index | Source Function | Role | Inputs | Outputs | Callers | Callees | Key Constants | Structs Used | Failure Branches / Guards | Algorithm Family | Side Effects |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `cadgeom_dist_sq` | Distance Squared | `p1, p2: Point2D*` | `double` | `cadgeom_perp_distance` | None | None | `CadPoint2D` (x:0, y:8) | None | Pythagorean dx^2 + dy^2 | Pure |
| 2 | `cadgeom_transform_point` | Affine Matrix Transform | `in: Point2D*, xf: Transform2D*, out: Point2D*` | `void` | None / Utility | None | None | `CadPoint2D`, `CadTransform2D` (a:0, b:8, c:16, d:24, tx:32, ty:40) | None | 2D Linear Affine | Writes `out` |
| 3 | `cadgeom_bbox_expand` | AABB Point Enclosure | `bb: BBox2D*, pt: Point2D*` | `void` | `cadgeom_evaluate_contour` | None | None | `CadBBox2D` (min_x:0, min_y:8, max_x:16, max_y:24) | None | Min/Max interval expansion | Mutates `bb` |
| 4 | `cadgeom_bbox_intersects` | AABB Intersection | `b1, b2: BBox2D*` | `int (0/1)` | Spatial query | None | None | `CadBBox2D` | 2 early exits | Separating Axis on AABB | Pure |
| 5 | `cadgeom_cross_product` | 2D Orientation / Cross Product | `o, a, b: Point2D*` | `double` | `cadgeom_perp_distance`, `cadgeom_convex_hull` | None | None | `CadPoint2D` | None | 2D vector cross product (A-O) x (B-O) | Pure |
| 6 | `cadgeom_perp_distance` | Point-to-segment Perpendicular Distance | `p, a, b: Point2D*` | `double` | `cadgeom_douglas_peucker_recurse` | `cadgeom_dist_sq`, `cadgeom_cross_product` | `1e-9 (EPSILON)` | `CadPoint2D` | l^2 < eps fallback to endpoint | Normal projection distance squared | Pure |
| 7 | `cadgeom_polygon_signed_area` | Polygon Signed Area | `poly: Polygon2D*` | `double` | `cadgeom_evaluate_contour` | None | `0.5`, threshold `3` | `CadPolygon2D` (pts:0, cnt:8, bbox:16..47, is_closed:48) | `poly==NULL`, `count<3` | Shoelace formula 0.5 * sum(xi*yj - xj*yi) | Pure |
| 8 | `cadgeom_point_in_polygon` | Point-in-Polygon Query | `poly: Polygon2D*, pt: Point2D*` | `int (0/1)` | `cadgeom_evaluate_contour` | None | threshold `3` | `CadPolygon2D`, `CadPoint2D` | `count<3` (err -2), AABB reject | Jordan curve ray casting (odd/even crossing) | Pure |
| 9 | `cadgeom_douglas_peucker_recurse` | Recursive Polyline Simplification | `pts, first, last, sq_tol, keep*` | `void` | self, `cadgeom_evaluate_contour` | `cadgeom_perp_distance`, self | Base condition `last <= first + 1` | `CadPoint2D` | Base exit, tol threshold | Ramer-Douglas-Peucker divide-and-conquer | Sets `keep[idx]=1` |
| 10 | `cadgeom_convex_hull` | 2D Convex Hull | `in, n, out, out_cnt*` | `int (0/-1)` | `cadgeom_evaluate_contour` | `cadgeom_cross_product` | Buffer cap `32`, `0.0` | `CadPoint2D` | `n<3`, `n>32`, null pointers | Andrew's Monotone Chain (Sort + Lower/Upper stack) | Populates `out` & `out_cnt` |
| 11 | `cadgeom_evaluate_contour` | Master Evaluation Pipeline | `raw_pts, n, tol, probe, out_area*, out_in*, out_hull*` | `int (0/-1)` | `main` | `douglas_peucker`, `bbox_expand`, `polygon_signed_area`, `point_in_polygon`, `convex_hull` | Cap `32`, tol `< 0.0` | `CadPoint2D`, `CadPolygon2D` | Param validation guards returning -1 | Complete geometry analysis pipeline | Writes output pointers |
| 12 | `main` | Test Harness Entry | `void` | `int` | PE Entry Point | `cadgeom_evaluate_contour` | 5 points, square 10x10, probe (5,5), tol 0.5 | `CadPoint2D` | None | Synthetic evaluation | Returns pipeline status |
