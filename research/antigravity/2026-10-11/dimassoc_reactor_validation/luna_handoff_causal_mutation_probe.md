# Decision-Grade Luna Handoff Specification

## TITLE: `DIMASSOC_ASSOCIATIVE_LINE_MUTATION_CAUSAL_PROBE_V1`

- **Role:** `ANTIGRAVITY_REA_EVIDENCE_PACKAGER`
- **Target Owner:** `LUNA`
- **Project:** `duongchi90/cad-agent`
- **Date:** 2026-10-13
- **Basis Commit:** `86318afc722939d88f355437e55405d012cba356` (`origin/main`)
- **Target Experiment:** Single Bounded Causal Mutation Workstation Probe
- **Production Status:** `PRODUCTION_CODE_CHANGE_AUTHORIZED = NO`

---

## 1. PURPOSE

Determine whether AutoCAD 2027 native associativity correctly survives an in-place LINE endpoint edit when the LINE has a proven DIMASSOC relationship.

This is the **missing causal evidence** required before any proposal or design can be considered to relax the current persistent-reactor refusal in production [`BoundedNativeLineEditPolicy`](file:///C:/Users/duong/ZCodeProject/cad-agent-main/autocad_plugin/CadAgent.AutoCAD2027/Drawing/BoundedNativeLineEditPolicy.cs#L238-L249).

---

## 2. EXPERIMENT GUARDS & ISOLATION

> [!IMPORTANT]
> - **Zero Production Code Edits:** Do NOT alter production files in `autocad_plugin/`, `cad_agent/`, or `primitive_ir_lib/`.
> - **Policy Retention:** Current production `ApplyBoundedNativeLineEdit` is expected to refuse the associative target because `HasPersistentReactors=true`. Do NOT weaken production policy merely to execute this experiment.
> - **Harness Isolation:** Luna must use a research-only disposable harness or isolated test assembly to execute the mutation.
> - **Execution Lane:** Run exclusively on a dedicated, non-overlapping mutable CAD lane with zero customer/evaluator drawings.

---

## 3. PRECONDITIONS

Before executing any mutation:

1. **Synthetic Drawing Only:** Use disposable synthetic fixture DWG generated via `fixtures/gen_fixture_b.scr` (`FIXTURE_B`, `DIMASSOC=2`).
2. **Hash & Cleanliness Check:**
   - Pre-action SHA-256 matches: `47c8d9f7b1a3286efdbcd917653ac8a9d7642b6d0eb3a827eb7e93993b2361e8`
   - Database state: `DBMOD = 0` (unmodified).
3. **Session & Process Identity:**
   - AutoCAD 2027 Commercial / Preview 64-bit (`accoreconsole.exe` or interactive `acad.exe`).
4. **Target Entity Identities:**
   - Target LINE handle: `H_LINE = 265` (from `0,0,0` to `100,0,0`).
   - Associated DIMENSION handle: `H_DIM = 266` (measurement `100.0`).
   - DIMASSOC object handle: `H_ASSOC = 281`.
5. **Read-Only Pre-Verification:**
   - Read-only classifier proves:
     - `LINE classification = KNOWN_DIMASSOC_REACTOR`
     - `DIMENSION` persistent reactors contain `H_ASSOC`
     - Extension dictionary `ACAD_DIMASSOC` on `H_DIM` points to `H_ASSOC`
     - `H_ASSOC.OwnerId` matches `H_DIM.ExtensionDictionary`.

### Negative Control Precondition

- Fixture A (`DIMASSOC=1`, non-associative, SHA-256 `836abde79f70684ae1e1bec4ebb2aedda9256ed872072c11d3eca3bc094b45cb`):
  - Same line and dimension geometry.
  - Classifier must return `NoReactor`.
  - Proves zero false-positive association classification.

---

## 4. EXPERIMENTAL ACTION

In `FIXTURE_B`:
- Target LINE starts at `(0, 0, 0)` and ends at `(100, 0, 0)`.
- **Action:** Mutate strictly in-place the endpoint property:
  ```text
  line.EndPoint = new Point3d(120, 0, 0);
  ```
- **Constraint:** Identity must remain completely unchanged.
  - Do NOT erase the line.
  - Do NOT recreate the line.
  - Do NOT re-add reactors manually.

---

## 5. REQUIRED OBSERVATION STAGES

Capture the exact database state separately across 6 discrete stages:

1. `PRESTATE`
2. `ACTIVE_IN_TRANSACTION` (after `line.EndPoint = (120,0,0)` before commit)
3. `ACTIVE_AFTER_COMMIT` (transaction committed)
4. `ACTIVE_AFTER_REGEN_OR_RECOMPUTE_IF_REQUIRED` (after calling Recompute or Regen if Q1 fails)
5. `AFTER_SAVE` (after `database.SaveAs()`)
6. `COLD_REOPEN` (process exit, fresh `Database.ReadDwgFile()` on saved DWG)

### Per-Stage Observation Schema

For each of the 6 stages, record:
```text
STAGE_NAME=
LINE_HANDLE_UNCHANGED=YES|NO
DIM_HANDLE_UNCHANGED=YES|NO
ASSOC_OBJECT_ID_PERSISTED=YES|NO
LINE_END=(x, y, z)
DIM_MEASUREMENT=float
DIM_DEFINITION_POINTS=[p1, p2, p3]
ASSOCIATION_CLASSIFICATION=NoReactor|KnownDimAssocReactor|UnknownOtherReactor|MixedReactors
DBMOD=int
DRAWING_SHA256=hex
```

---

## 6. ORDERED CAUSAL QUESTIONS

Answer strictly in this sequence:

### Q1: Automatic Propagation
> Does the associated dimension automatically update its `Measurement` and definition points immediately after the in-place LINE endpoint mutation and transaction commit?

- If **YES** $\rightarrow$ Stop. Native engine handles propagation automatically.
- If **NO** $\rightarrow$ Proceed to Q2.

### Q2: Managed Recompute
> Does supported managed:
> ```csharp
> dimension.RecomputeDimensionBlock();
> ```
> cause the semantic measurement and definition points to update to `120.0`?

- If **YES** $\rightarrow$ Stop. Managed `RecomputeDimensionBlock` is the required supported mechanism.
- If **NO** $\rightarrow$ Proceed to Q3.

### Q3: Native Regeneration
> Does a normal supported AutoCAD database regeneration mechanism (`doc.Editor.Regen()` or database audit/update) cause the dimension to update?

### Technical Constraints on Probe:
- **NO P/Invoke:** Pure managed calls only.
- **NO ObjectARX C++:** Zero unmanaged adapters.
- Stop when the first supported route proves the required persisted behavior.

---

## 7. PASS / FAIL ORACLES

### Pass Oracle (`DIMASSOC=2` Fixture B)

To declare **PASS**, the probe must satisfy **ALL** criteria:
1. `LINE` handle unchanged (`265`).
2. `DIMENSION` handle unchanged (`266`).
3. Shared `AcDbDimAssoc` `ObjectId` still present.
4. Exact `LINE <-> DIMENSION` relationship still proven via the 3 invariants.
5. `LINE` length equals `120.0`.
6. `DIMENSION.Measurement` equals `120.0`.
7. Dimension definition/association points are consistent with the new endpoint `(120, 0, 0)`.
8. Save operation succeeds without error.
9. Close and cold reopen succeed cleanly.
10. Same relationship and measurement persist after cold reopen.
11. `DBMOD = 0` clean after save.
12. Zero database audit errors or corrupted proxies.

### Negative Control Oracle (`DIMASSOC=1` Fixture A)

- Classifier must NOT claim a `DIMASSOC` relationship.
- Non-associative dimension is expected to retain original measurement (`100.0`) despite line edit.
- Negative control passes if classifier correctly distinguishes non-associative geometry.

---

## 8. FAILURE CLASSIFICATION TAXONOMY

If any step in the probe fails, classify the defect into exactly one of:

- `ASSOCIATION_NOT_UPDATED`: Dimension measurement remains 100.0 across all supported updates.
- `MEASUREMENT_STALE`: Block geometry changes but `Measurement` property does not update.
- `DEFINITION_POINT_STALE`: Text measurement changes but definition points remain at 100.0.
- `ASSOC_OBJECT_LOST`: `AcDbDimAssoc` object erased or unlinked during mutation.
- `IDENTITY_CHANGED`: LINE or DIMENSION handle changed.
- `RECOMPUTE_INSUFFICIENT`: `RecomputeDimensionBlock()` throws or fails to update block record.
- `REGEN_REQUIRED`: Only full viewport REGEN updates associativity, not headless database operations.
- `SAVE_PERSISTENCE_FAILURE`: Save fails or throws database corruption exception.
- `COLD_REOPEN_FAILURE`: Reopened DWG reports audit errors, proxy entities, or detached dimension.
- `UNKNOWN`: Unclassified anomaly.

> [!CAUTION]
> If the experiment fails, do NOT immediately propose a code repair. First record the exact failure classification and establish the empirical causal boundary.

---

## 9. HYPOTHETICAL FUTURE PRODUCTION SEAM

Only **AFTER** the above causal mutation probe produces an unequivocal **PASS**:
- The potential candidate design for production is to replace the binary condition:
  ```csharp
  // Current:
  var hasPersistentReactors = line.GetPersistentReactorIds().Count > 0;
  ```
  with an explicit classification:
  ```csharp
  // Future candidate (strictly hypothetical):
  var classification = ClassifyLineReactors(line.GetPersistentReactorIds());
  // Refuse if classification is UnknownOtherReactor or MixedReactors.
  // Allow if NoReactor or KnownDimAssocReactor (with verified paired dimension).
  ```
- **CURRENT STATUS:** This remains strictly a hypothesis. `PRODUCTION_CODE_CHANGE_AUTHORIZED = NO`.
