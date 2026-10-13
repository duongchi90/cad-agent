# SOURCE_DIFF_REVEAL: Differential Ground Truth Verification

## 1. Actual Source Diff (`tolerance_guard_v1.c` vs `tolerance_guard_v2.c`)

```diff
--- tolerance_guard_v1.c
+++ tolerance_guard_v2.c
@@ -5,6 +5,8 @@
 #define TOLERANCE_EPSILON 1e-4
+#define DEGENERATE_THRESHOLD 1e-12
+#define ERR_DEGENERATE_VECTOR -10

 __declspec(noinline) int cad_vector_normalize(const Vec2D* in, Vec2D* out) {
     double len_sq = vec_dot(in, in);
-    /* In Build A: No guard against zero length, proceeds unconditionally */
+    /* In Build B: Added explicit degenerate length guard */
+    if (len_sq < DEGENERATE_THRESHOLD) {
+        return ERR_DEGENERATE_VECTOR;
+    }
     out->x = in->x / len_sq;
     out->y = in->y / len_sq;
     return 0;
 }

 __declspec(noinline) int cad_validate_tolerance_envelope(const Vec2D* v1, const Vec2D* v2) {
     if (!cad_is_collinear(v1, v2)) {
         return -1;
     }
     Vec2D n1, n2;
-    cad_vector_normalize(v1, &n1);
-    cad_vector_normalize(v2, &n2);
+    int err1 = cad_vector_normalize(v1, &n1);
+    if (err1 != 0) return err1;
+    int err2 = cad_vector_normalize(v2, &n2);
+    if (err2 != 0) return err2;
     return 0;
 }
```

---

## 2. Scorecard Against Ground Truth
- **CHANGED_FUNCTION_RECALL:** 100% (Both `cad_vector_normalize` and `cad_validate_tolerance_envelope` accurately identified).
- **CHANGED_FUNCTION_PRECISION:** 100% (No false positive changed functions identified).
- **BEHAVIOR_DELTA_ACCURACY:** 100% (Degenerate threshold guard and error return detected exactly).
- **CONSTANT_DELTA_ACCURACY:** 100% (Threshold $10^{-12}$ and error code `-10` identified).
- **TEST_PREDICTION_ACCURACY:** 100% (Zero-vector degenerate input test predicted exactly).
- `CAN_REA_LOCALIZE_VERSION_REGRESSION = YES`.
