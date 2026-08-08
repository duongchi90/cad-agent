# R8 Pilot Program Implementation and Acceptance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a dependency-ordered R8 acceptance program over final accepted R1-R7 without creating any new production authority, progressing from synthetic evidence to disposable AutoCAD Mechanical, a public-fixture full-system proof, and a separately authorized private/customer pilot.

**Architecture:** R8 is an acceptance layer only. A mandatory read-only rebaseline first resolves exact accepted R1-R7 symbols, commands, evidence owners, and live prerequisites; later pilot Issues invoke those owners through test/runbook-only surfaces and produce derived sanitized acceptance dossiers. Any missing production behavior stops the pilot and returns to its owning R1-R7 subsystem under a fresh defect/runtime Issue.

**Tech Stack:** Windows, Python 3.11 locked environment, pytest, Ruff, PowerShell `scripts/verify.ps1`, existing architecture/reuse checks, accepted CAD Agent R1-R7 Python owners, accepted AutoCAD Mechanical 2027 File IPC/.NET plugin and live harnesses, accepted official worker/provider seam, existing manifest/checkpoint/evidence/hash/backup/rollback/publication owners.

## Global Constraints

- Planning authority: Issue #142, activation comment `5227447357`.
- Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`.
- Issue #142 changes exactly two planning docs and no other path.
- R8 executable work remains BLOCKED until required R1-R7 runtime is accepted and freshly mapped.
- Do not invent moving R1-R7 API names or fields. Use `R8 REBASELINE REQUIRED` whenever exact accepted seams are unavailable.
- R8 owns no CAD parser, source/custody authority, component/view registry, revision/current store, visual verdict, repair executor, approval issuer, manifest/checkpoint store, publisher, AutoCAD transport, or model/provider transport.
- A pilot may not modify production code to make itself pass.
- Source/base/accepted/published inputs are immutable; mutation is candidate-only through accepted owners.
- Real model/provider output is untrusted and never self-authorizing.
- Confirmed DRIVING/protected dimensions may not be changed merely to improve visual similarity.
- Pixel/image differences may not become model-space mutations without accepted datum/calibration mapping.
- Private/customer CAD and raw private evidence remain outside Git/public CI unless separately and explicitly approved.
- Literal `PASS`, `FAIL`, `SKIP`, and `NOT RUN` are preserved. `SKIP` and `NOT RUN` never satisfy a required gate.
- Production readiness is a separate authorization after R8-P; R8-P PASS does not itself authorize rollout.

---

## File structure for future R8 execution

R8 should not create a production module. The preferred future repository shape is acceptance-only:

| Path | Responsibility | Production authority? |
|---|---|---|
| `tests/test_cad_agent_r8_synthetic_pilot.py` | Compose final accepted R1-R7 offline/synthetic seams and assert cross-owner identity/freshness/determinism | No |
| `mcp_integration_lib/tests/test_r8_disposable_pilot_live.py` | Optional new cross-owner live acceptance test only if existing accepted live harnesses cannot express the complete disposable scenario | No |
| `tests/test_cad_agent_r8_public_fixture_pilot.py` | Full public/non-sensitive product-loop acceptance, including real provider/live gates where required | No |
| `docs/reviews/r8-synthetic-pilot-acceptance.md` | Sanitized immutable review record for R8-S | No |
| `docs/reviews/r8-disposable-pilot-live-acceptance.md` | Sanitized live review record for R8-D | No |
| `docs/reviews/r8-public-fixture-pilot-acceptance.md` | Sanitized public full-system review record | No |
| `docs/reviews/r8-private-customer-pilot-sanitized.md` | Optional separately authorized redacted summary after R8-P | No |

A future Issue should use at most two paths per bounded pilot slice. Existing accepted harnesses should be invoked without modification whenever possible.

If a pilot requires a new production Python/C# module, dispatcher operation, schema, dependency, workflow, persistent state store, or authority owner, stop with `R8 REBASELINE REQUIRED` and route the need to the correct R1-R7 owner.

---

### Task 0: R8-0 final readiness rebaseline

**Mode:** STRICT READ ONLY.

**Files:**
- Create: NONE
- Modify: NONE
- Delete: NONE

**Interfaces:**
- Consumes: final accepted R1-R7 repository state, accepted implementation records, current live harnesses, worker/provider attestation evidence, current active writer/reviewer state.
- Produces: one Master-PO issuance dossier containing the exact accepted seam map and exact pilot command map. This dossier is governance evidence, not a repository state store.

- [ ] **Step 1: Freeze exact accepted main and prove ancestry**

Record the exact current `main` SHA and compare it against every R1-R7 implementation/release SHA used by the planned pilot.

Expected result: every required owner is merged/accepted or the task returns `R8 REBASELINE REQUIRED` before any pilot write.

- [ ] **Step 2: Resolve the exact R1-R7 seam map**

For each stage, record exact accepted file, symbol/API, contract/version, validator, canonical identity/hash function, tests, and owner for:

```text
R1 source bundle/custody/fusion
R2 exact-base adapter/provenance
R3 component/view registry
R4 candidate revision/selection/freshness
R5 visual request/evidence/verdict/freshness
R6 repair planning/result/approval/rollback/second review
R7 eligibility/authorization/publication/recovery
engineering/human approval
manifest/checkpoint/resume
safe path/reparse/custody
file hashing and canonical JSON hashing
worker/provider/auth/attestation
AutoCAD Mechanical File IPC/.NET live evidence
```

Expected result: no semantic seam is mapped to more than one authority owner.

- [ ] **Step 3: Resolve exact live prerequisite matrix**

Record the final accepted environment inputs needed for each live gate, including at minimum the accepted successors of:

```text
CAD_AGENT_FILE_IPC
CAD_AGENT_AUTOCAD_HWND
CAD_AGENT_AUTOCAD_LISP_PATH
CAD_AGENT_DOTNET_IPC_DIR
CAD_AGENT_S2C_LIVE
CAD_AGENT_VS_T3_LIVE
CAD_AGENT_S3B_* variables when exact-base extraction is exercised
provider/model/auth variables required by the final worker seam
```

Do not infer that a variable remains authoritative merely because it exists on planning base; map the final accepted owner.

- [ ] **Step 4: Resolve the exact command map**

Freeze exact commands for:

```text
canonical offline verifier
AutoCAD .NET restore/build/test when required
focused R1-R7 regressions used by the pilot
S2C/VS-T3 live gates
S3B/exact-base live gate when applicable
worker/provider real-attestation smoke gate
R5 full verdict path
R6 repair/no-repair path
R7 non-production publication path
cleanup/rollback/recovery checks
```

Every command must name exact accepted test/CLI paths and expected PASS/FAIL/SKIP/NOT RUN state.

- [ ] **Step 5: Audit shared-writer overlap**

Check active branches/PRs for every candidate R8 test/review path and every shared live harness the pilot will invoke.

Expected result: zero write overlap. Read-only invocation of an accepted shared harness is allowed only when its exact source/build identity is frozen.

- [ ] **Step 6: Audit historical live blockers**

Explicitly classify S2C, VS-T3, S3B/exact-base live, AutoCAD .NET, provider/model/auth, backup/rollback, and R7 publication evidence as current `PASS`, `FAIL`, `SKIP`, or `NOT RUN`.

If exact-base route is required and S3B/successor live remains `NOT RUN`/`SKIP`, R8-D/R8-F are blocked until that upstream gate is accepted.

- [ ] **Step 7: Issue the next bounded pilot only**

Master PO issues R8-S only after Task 0 is clean. Do not pre-authorize R8-D, R8-F, or R8-P.

**Task 0 acceptance:** exact accepted seams/commands/prerequisites are known; no repository writes; no unresolved duplicate owner; no moving API assumption.

**Task 0 STOP conditions:** any unaccepted R1-R7 owner, unresolved provider attestation, unresolved R7 publication semantics, unresolved required S3B live gate, shared writer overlap, or need for new production behavior.

---

### Task 1: R8-S synthetic orchestration pilot

**Files — candidate future Issue write-set:**
- Create: `tests/test_cad_agent_r8_synthetic_pilot.py`
- Create: `docs/reviews/r8-synthetic-pilot-acceptance.md`
- Modify: NONE

**Interfaces:**
- Consumes: exact accepted R1-R7 functions/contracts frozen by R8-0; accepted fake/stub provider seam where final R5/R6 supports one; canonical JSON/hash owner; existing temporary/disposable file utilities.
- Produces: one deterministic synthetic acceptance test plus one sanitized review record bound to exact repository SHA and evidence identities.

**Important:** The exact imports/function signatures in this future test must be copied from the R8-0 accepted seam map. If the map is incomplete, do not create this file.

- [ ] **Step 1: Create only the synthetic pilot test first**

The first repository write is `tests/test_cad_agent_r8_synthetic_pilot.py` only.

The test must construct generated/non-sensitive inputs and exercise these semantic checkpoints in order:

```text
R1 accepted source/custody/fusion identity
-> R2 synthetic exact-base/no-base route as applicable
-> R3 deterministic component/view graph
-> R4 candidate revision + stale-state checks
-> R5 accepted fake-provider closed verdict path
-> R6 approved repair and no-repair paths without self-authorization
-> R7 safe synthetic/disposable eligibility/publication path only if final R7 supports it offline
-> derived R8 evidence-reference dossier
```

The test must contain negative cases for stale candidate, stale visual evidence, mismatched source identity, invalid repair approval, invalid publication authorization, and any final accepted cross-owner mismatch rules.

- [ ] **Step 2: Run the test and classify the first result honestly**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_r8_synthetic_pilot.py -q -p no:cacheprovider
```

Expected result:

- PASS only if final accepted owners compose without production changes;
- FAIL attributable to a genuine accepted-owner defect => STOP R8-S and open a fresh bounded defect Issue against that owner;
- import/API mismatch despite R8-0 map => `R8 REBASELINE REQUIRED`;
- do not add R8 production glue to fix the failure.

- [ ] **Step 3: Prove deterministic replay**

Run the focused test at least five times from one committed source state:

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_r8_synthetic_pilot.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

Expected: 5/5 PASS with exact deterministic identities/output where final owners promise determinism.

Real model/provider nondeterminism is not part of R8-S because real provider execution is `NOT RUN`.

- [ ] **Step 4: Run focused upstream regressions**

Use the exact R1-R7 focused regression command frozen by R8-0.

Expected: PASS with zero unexpected skips for all offline-required tests.

- [ ] **Step 5: Run Ruff and architecture/reuse checks**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check tests/test_cad_agent_r8_synthetic_pilot.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
```

Expected: all PASS.

- [ ] **Step 6: Run canonical offline verification**

Run:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Expected:

```text
canonical offline suite: PASS
AutoCAD .NET: NOT RUN
AutoCAD Mechanical live: NOT RUN
real provider/model/auth: NOT RUN
private/customer data: NOT RUN
```

Unavailable-state probes may report SKIP exactly as the canonical verifier requires; do not promote them.

- [ ] **Step 7: Commit the test-only checkpoint**

```powershell
git add tests/test_cad_agent_r8_synthetic_pilot.py
git commit -m "test: add R8 synthetic orchestration pilot"
```

- [ ] **Step 8: Create the sanitized R8-S review record**

Create `docs/reviews/r8-synthetic-pilot-acceptance.md` containing:

```text
exact accepted main/head
exact changed paths
R1-R7 seam identities
focused test result
5x replay result
upstream regression result
canonical verifier result
evidence-reference dossier hash using accepted canonical owner
PASS/FAIL/SKIP/NOT RUN matrix
R8 duplicate-authority audit
remaining live/provider/private gates
```

No private content belongs in this record.

- [ ] **Step 9: Commit the review record**

```powershell
git add docs/reviews/r8-synthetic-pilot-acceptance.md
git commit -m "docs: record R8 synthetic pilot evidence"
```

- [ ] **Step 10: Open a DRAFT PR and require hosted gates**

Required hosted gates on exact final head/current-main synthetic:

```text
tests: PASS
reuse-declaration: PASS
unresolved review threads: 0 before final acceptance
```

Independent integration/CI and safety/authority reviewers must both PASS before Master PO accepts R8-S.

**Task 1 STOP conditions:** any production path needed; any source/accepted mutation; deterministic replay failure; stale evidence accepted; approval/verdict/publication authority collapse; provider/network unexpectedly invoked; third path required.

---

### Task 2: R8-D disposable AutoCAD Mechanical pilot

**Preferred mode:** invoke existing accepted live harnesses with repository writes `NONE`.

**Fallback candidate future Issue write-set only when one cross-owner live composition test is genuinely missing:**
- Create: `mcp_integration_lib/tests/test_r8_disposable_pilot_live.py`
- Create: `docs/reviews/r8-disposable-pilot-live-acceptance.md`
- Modify: NONE

**Interfaces:**
- Consumes: accepted R8-S result, accepted live File IPC/.NET/AutoCAD owners, accepted S2C/VS-T3 successors, accepted S3B successor if exact-base route is included, accepted candidate/repair/publication safety primitives needed for the selected disposable scenario.
- Produces: exact live environment/build identity plus proof that required CAD operations are candidate-only, hash-bound, session-stable, cleaned up, and rollback-safe.

- [ ] **Step 1: Rebaseline again immediately before live execution**

Confirm no accepted owner/harness/plugin/build changed since R8-S acceptance.

If anything changed materially, return `R8 REBASELINE REQUIRED`.

- [ ] **Step 2: Prepare one generated/non-sensitive disposable fixture outside production paths**

The operator records:

```text
fixture path under accepted disposable root
fixture SHA-256
source/base/accepted fixture hashes when applicable
expected drawing setup
expected protected dimensions
exact AutoCAD Mechanical version/profile
plugin assembly SHA-256
File IPC/.NET root identity
```

Do not commit the generated DWG/DXF unless a future Issue explicitly authorizes a redistributable fixture path.

- [ ] **Step 3: Run canonical verification with required .NET gate**

Run the final accepted canonical verifier without a skip flag when AutoCAD .NET is required:

```powershell
.\scripts\verify.ps1
```

Expected: .NET/offline/Ruff/diff/architecture gates PASS. Private data remains NOT RUN.

- [ ] **Step 4: Run accepted S2C/VS-T3 live gates**

Use the exact commands frozen by R8-0/R8-D rebaseline.

Expected evidence:

```text
native render/evidence export PASS
changed=false for read-only evidence operations
source/drawing hash before == after
DBMOD/session/layout/UCS/view restoration PASS
request/result cleanup PASS
```

A collected-only SKIP does not satisfy R8-D.

- [ ] **Step 5: Run exact-base live gate when the scenario exercises base CAD**

Use final accepted S3B/successor command from rebaseline.

Required evidence:

```text
source hash unchanged
accepted drawing hash unchanged
fresh live preflight PASS
candidate-only output/mutation
source-handle/component provenance preserved
cleanup and session restoration PASS
```

If final S3B/successor has no accepted live PASS path, STOP. Do not emulate it in R8.

- [ ] **Step 6: Exercise accepted mutation/rollback primitives with a bounded deterministic plan if required by the disposable scenario**

Use only final accepted existing executor semantics. Do not invoke a real provider solely to satisfy R8-D; an already validated synthetic/preapproved operation may be used if the final R6 design permits this isolation gate.

Required evidence:

```text
candidate prehash
operation identity
candidate posthash
backup identity
cleanup result
rollback result or proof no rollback required
fresh post-mutation evidence identity
```

If final R6 cannot separate deterministic executor validation from real provider planning, classify provider execution as a later R8-F requirement rather than weakening the R6 boundary.

- [ ] **Step 7: Verify source/base/accepted immutability mechanically**

Compare exact hashes captured before and after the complete live attempt.

Any mismatch is FAIL and immediate STOP.

- [ ] **Step 8: Record literal live states**

Required record fields:

```text
AutoCAD .NET PASS/FAIL
AutoCAD Mechanical PASS/FAIL/SKIP/NOT RUN
S2C PASS/FAIL/SKIP/NOT RUN
VS-T3 PASS/FAIL/SKIP/NOT RUN
S3B exact-base PASS/FAIL/SKIP/NOT RUN or NOT APPLICABLE to issued scenario
real provider/model/auth NOT RUN unless separately required
private/customer data NOT RUN
cleanup PASS/FAIL
rollback PASS/FAIL/NOT APPLICABLE
```

- [ ] **Step 9: Create a review record only when the future Issue authorizes it**

`docs/reviews/r8-disposable-pilot-live-acceptance.md` contains sanitized hashes/versions/states only.

- [ ] **Step 10: STOP for independent review before R8-F**

No public full-system pilot begins until Master PO accepts R8-D.

**Task 2 STOP conditions:** live gate required but SKIP/NOT RUN; source/base/accepted hash change; candidate escaped disposable root; DBMOD/session restoration failure; cleanup/rollback failure; private data encountered; live defect requires production edit; real provider unexpectedly becomes necessary for a gate that was issued as infrastructure-only.

---

### Task 3: R8-F public-fixture full-system pilot

**Files — candidate future Issue write-set:**
- Create: `tests/test_cad_agent_r8_public_fixture_pilot.py`
- Create: `docs/reviews/r8-public-fixture-pilot-acceptance.md`
- Modify: NONE

**Interfaces:**
- Consumes: Master-PO accepted R8-S and R8-D; immutable redistributable/non-sensitive public fixture; final accepted R1-R7 production seams; accepted real worker/provider/model/auth seam; accepted AutoCAD live environment; human engineering approval owner.
- Produces: the first complete non-private end-to-end product evidence package, ending in final accepted R7 non-production publication evidence.

- [ ] **Step 1: Freeze and approve the public fixture**

Record before execution:

```text
fixture source/reuse/license status
immutable fixture source hashes
engineering intent
known protected/DRIVING/reference dimensions
expected component/view scope
exact-base CAD hash/revision if included
allowed non-production publication target
cleanup policy
reason this fixture represents the target product route
```

If fixture redistribution is not allowed, keep bytes outside Git and pass them through a separately authorized local path. The review record stores only sanitized identity metadata.

- [ ] **Step 2: Create the public-fixture acceptance test first**

The test must consume only exact accepted seams from the current R8 rebaseline and enforce this ordering:

```text
R1 source/custody/fusion
-> R2 exact-base handoff when applicable
-> R3 component/view registry
-> R4 candidate revision
-> fresh AutoCAD render/measurement evidence
-> real accepted R5 provider/verdict
-> R6 approved repair only if R5 FAIL and repair is authorized
-> after repair: new R4 candidate state + fresh AutoCAD evidence + fresh R5 verdict
-> engineering/human approval as required
-> R7 eligibility + exact authorization + non-production publication
-> final post-publication verification
```

The test must reject stale evidence at every boundary and must not contain direct CAD mutation logic.

- [ ] **Step 3: Run canonical build/offline gates before real provider/live work**

Run:

```powershell
.\scripts\verify.ps1
```

Expected: all required offline/.NET gates PASS before any public-fixture mutation/model call.

- [ ] **Step 4: Run the focused public-fixture test with the final accepted environment**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_r8_public_fixture_pilot.py -q -p no:cacheprovider -ra
```

Expected: PASS with zero required skips.

If a real provider/live prerequisite is absent, the focused test may truthfully SKIP or fail closed according to the accepted harness, but R8-F does not PASS.

- [ ] **Step 5: Verify real provider/model/auth evidence**

The accepted worker boundary must prove:

```text
exact worker/runtime identity
model/config identity
instruction-source identity
provider policy identity
output schema/validator identity
provider-observed attestation
bounded lifecycle/timeout/cancel/cleanup behavior
no caller-minted matching evidence accepted as authority
```

Do not record secrets/tokens/raw customer-like content in the public review record.

- [ ] **Step 6: Verify the final visual/repair chain**

For every mutation cycle record:

```text
candidate revision identity
candidate prehash
mutation/repair plan identity
separate approval identity
candidate posthash
fresh AutoCAD evidence identity
fresh R5 verdict identity
```

Final acceptance requires a fresh final R5 `PASS` when the final accepted R5 contract defines PASS as the required visual condition.

`NEEDS_HUMAN` cannot be relabeled PASS. `FAIL` cannot be averaged away by other views/regions.

- [ ] **Step 7: Verify engineering constraints**

Human/engineering evidence must resolve every protected/DRIVING/conflicting critical fact required by the scenario.

A visual/model result alone cannot satisfy this step.

- [ ] **Step 8: Exercise final R7 on an explicitly non-production target**

Use exact final R7 semantics from rebaseline.

Required evidence includes:

```text
R7 eligibility identity
publication authorization identity
candidate SHA
expected target prehash when final R7 requires one
backup identity/hash
publication result identity
final target hash
one-time authorization consumption
post-publication verification
replay/recovery classification
```

If final R7 is replacement-only, prepare an existing approved disposable target with the exact authorized prehash. Do not invent absent-target behavior.

- [ ] **Step 9: Replay the deterministic portions**

Re-execute deterministic identity/aggregation/dossier construction from the same immutable evidence.

Expected: exact identities match where the accepted owners promise determinism.

Do not require byte-identical natural-language/model output when the final provider owner does not promise it; require closed schema and deterministic server-owned aggregation instead.

- [ ] **Step 10: Run final regression and hygiene gates**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check tests/test_cad_agent_r8_public_fixture_pilot.py
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
git diff --check
.\scripts\verify.ps1
```

Also run the exact focused R1-R7 regression set frozen by rebaseline.

- [ ] **Step 11: Commit the test-only checkpoint**

```powershell
git add tests/test_cad_agent_r8_public_fixture_pilot.py
git commit -m "test: add R8 public fixture pilot"
```

- [ ] **Step 12: Create and commit the sanitized R8-F review record**

`docs/reviews/r8-public-fixture-pilot-acceptance.md` records only non-sensitive/public fixture information and exact evidence identities.

```powershell
git add docs/reviews/r8-public-fixture-pilot-acceptance.md
git commit -m "docs: record R8 public fixture pilot"
```

- [ ] **Step 13: Open DRAFT PR and require hosted gates**

Required:

```text
tests PASS on exact head/current-main synthetic
reuse-declaration PASS
independent integration/CI reviewer PASS
independent safety/authority/privacy reviewer PASS
review threads 0 before Master PO acceptance
```

Hosted CI does not replace local real AutoCAD/provider evidence when those prerequisites are unavailable on hosted runners.

**Task 3 STOP conditions:** any private data required; final accepted API mismatch; real provider attestation gap; required live gate SKIP/NOT RUN; final R5 not PASS when PASS is required; protected engineering conflict unresolved; repair without approval; stale post-repair evidence; R7 authorization/target mismatch; cleanup/rollback/publication recovery failure; any production edit needed.

---

### Task 4: R8-P separately authorized private/customer pilot

**Execution repository writes:** NONE preferred and expected.

**Optional post-run write-set only under a separate explicit authorization:**
- Create: `docs/reviews/r8-private-customer-pilot-sanitized.md`
- Modify: NONE

**Interfaces:**
- Consumes: accepted R8-F, exact frozen accepted R1-R7 build, explicit private/customer authorization, approved local evidence root, approved retention/redaction policy, owner/engineering intent and approvals.
- Produces: private local authoritative evidence plus an optional sanitized public summary. Raw private evidence never becomes a repository truth source.

- [ ] **Step 1: Obtain separate private-data authorization before opening any customer source**

Authorization must identify:

```text
approved source package or opaque source identity
allowed operator/machine/workspace
allowed local evidence root
retention/deletion policy
redaction policy
whether real provider processing is permitted for this content
whether non-production publication is permitted
exact pilot objective
STOP conditions
```

No implicit authorization from R8-F is valid.

- [ ] **Step 2: Freeze exact executable identities**

Record exact:

```text
accepted main SHA
R1-R7 implementation identities
locked dependency identity
worker/provider/runtime identity
plugin assembly SHA
AutoCAD Mechanical version/profile
accepted command map
```

No production code change is allowed after private bytes are introduced into the pilot workspace.

- [ ] **Step 3: Prepare private input outside Git**

Verify source/custody hashes using final accepted R1 authority. Do not copy private sources into repository directories, Git staging, public CI artifacts, or public logs.

- [ ] **Step 4: Execute the exact R8-F accepted product sequence**

Use the command/API map frozen before the run. The route is:

```text
R1 -> R2 when applicable -> R3 -> R4 -> live evidence -> R5
-> R6 only when separately approved -> fresh evidence -> fresh R5
-> engineering/human approval -> R7 only when explicitly authorized
```

No new code, contract, workflow, or dependency may be introduced during this run.

- [ ] **Step 5: Prove privacy-safe evidence handling continuously**

Publicly visible output must exclude:

```text
private CAD/image/PDF bytes
customer names/identifiers unless explicitly approved
absolute private paths
raw OCR/transcriptions
raw provider payloads containing customer content
API keys/tokens/cookies/account identifiers
private screenshots/crops
backup copies
private intermediate candidates
```

Allowed public metadata is limited to approved opaque IDs, hashes, versions, categorical states, non-sensitive counts, and approval references.

- [ ] **Step 6: Enforce freshness after every mutation**

Any R6 repair or other accepted candidate mutation creates a new candidate state and invalidates earlier visual/measurement evidence.

Final private-pilot acceptance requires fresh final evidence and the final accepted R5 condition for that exact candidate.

- [ ] **Step 7: Verify source/base/accepted immutability, cleanup, and rollback**

Record exact before/after hashes and accepted rollback/cleanup evidence.

Any unexpected immutable-input change, cleanup failure, or rollback failure is FAIL and immediate pilot STOP.

- [ ] **Step 8: Classify all gates literally**

Record every gate as one of:

```text
PASS
FAIL
SKIP
NOT RUN
NOT APPLICABLE
```

`NOT APPLICABLE` is only for a route explicitly excluded by the issued scenario, such as exact-base reuse when no exact-base source is part of the authorized package. It is not a substitute for a missing required gate.

- [ ] **Step 9: Run a local redaction audit before any public report**

An independent safety/privacy reviewer examines the proposed sanitized summary and rejects any private path/content/credential leakage.

- [ ] **Step 10: Optionally create one sanitized repository record after separate authorization**

If authorized, create only:

`docs/reviews/r8-private-customer-pilot-sanitized.md`

It may contain:

```text
opaque pilot/source IDs
SHA-256 values approved for disclosure
software/build versions
PASS/FAIL/SKIP/NOT RUN/NOT APPLICABLE matrix
non-sensitive test counts
approval reference IDs
rollback/cleanup categorical results
final advisory verdict
```

It must not contain raw private artifacts.

- [ ] **Step 11: STOP for Master PO/owner decision**

R8-P PASS is evidence for a later production-readiness review only. Do not promote it directly to production authorization.

**Task 4 STOP conditions:** missing/ambiguous private authorization; provider use not authorized for private content; source/custody mismatch; production build changes after private-data introduction; source/base/accepted mutation; stale evidence; unresolved engineering conflict; required gate SKIP/NOT RUN; data leakage; cleanup/rollback failure; any production fix needed.

---

### Task 5: Separate production-readiness review

**Mode:** governance/approval only unless a new Issue explicitly permits a sanitized docs record.

**Files:**
- Default: NONE

**Interfaces:**
- Consumes: accepted R8-S, R8-D, R8-F, and R8-P evidence plus residual-risk/operator/privacy/support policy.
- Produces: owner/Master-PO production-readiness decision. This decision is not minted by R8 code.

- [ ] **Step 1: Verify all pilot stages were accepted in order**

No stage may be skipped merely because a later stage happened to work.

- [ ] **Step 2: Review residual risk and explicit support envelope**

Record supported/unsupported:

```text
source media classes
base CAD conditions
engineering dimension/constraint expectations
AutoCAD Mechanical workstation/profile requirements
provider/model/runtime versions
repair operation classes
publication target policy
privacy/data-retention policy
rollback/recovery expectations
operator escalation path
```

- [ ] **Step 3: Verify no required gate is still SKIP or NOT RUN**

A production requirement still classified SKIP/NOT RUN blocks readiness.

- [ ] **Step 4: Verify private-data and publication policy**

Confirm that production authorization does not widen beyond what R8-P actually exercised and what R7/owner approvals authorize.

- [ ] **Step 5: Issue explicit owner/Master-PO decision**

Allowed outcomes:

```text
PRODUCTION READINESS ACCEPTED
PRODUCTION READINESS BLOCKED
R8 REBASELINE REQUIRED
```

No implicit readiness is inferred from merge state or pilot PASS alone.

---

## Cross-task evidence package contract

R8 does not create a new schema or store. Every pilot review record is a derived, sanitized index into authoritative accepted-owner evidence.

For each applicable pilot, record:

```text
pilot stage/run identity
accepted main SHA
R1-R7 build/contract identities
canonical verifier result
dependency lock identity
plugin/AutoCAD identity
worker/provider/model/config/attestation identity
source bundle/custody/fusion identities
source hashes and roles
exact-base source SHA/revision
engineering intent/approval identity
protected dimension/constraint identities
R3 component/view registry identity
R4 candidate revision/parent/baseline/selection identity
candidate hash before each mutation
R5 fresh evidence/verdict identity
R6 plan/approval/executor/prehash/posthash/cleanup/rollback/second-review identity
R7 eligibility/authorization/target-prehash/backup/publication/consumption/final-hash identity
source/base/accepted immutability proof
cleanup/rollback proof
privacy authorization/redaction result
literal PASS/FAIL/SKIP/NOT RUN matrix
```

A deterministic dossier hash must reuse the accepted canonical JSON/hash owner. It is not a substitute for individual upstream evidence hashes.

---

## Gate interpretation table

| State | Exact meaning | Can satisfy required pilot gate? |
|---|---|---|
| `PASS` | Exact required gate executed against exact bound build/evidence and all assertions passed | Yes |
| `FAIL` | Required execution occurred and one or more required assertions failed | No; immediate STOP |
| `SKIP` | Test/gate was collected but explicit prerequisites were unavailable or scenario branch did not apply | No when required |
| `NOT RUN` | Gate was intentionally not executed | No when required |
| `NOT APPLICABLE` | Issued scenario explicitly excludes the route; only valid when that route is not part of stage acceptance | Not a replacement for a required route |

Hosted unavailable-state SKIP is evidence that skip behavior is correct; it is not live PASS.

---

## Reviewer matrix

| Pilot | Integration/CI reviewer | Safety/authority/privacy reviewer | Live operator/evidence role |
|---|---|---|---|
| R8-S | Required | Required | Not required |
| R8-D | Required | Required | Required |
| R8-F | Required | Required | Required |
| R8-P | Required for build/evidence consistency | Required, including redaction | Required |

Reviewer responsibilities remain advisory. Master PO is final acceptance authority.

---

## Overlap matrix

Before every future R8 repository write, rerun this matrix against current GitHub state.

| Owner/lane | Potential overlap | R8 action |
|---|---|---|
| R1C #123 or successor | source-fusion production/test paths | Never touch; wait for final R1 |
| Wave 1A #113 or successor | worker/provider/handoff lifecycle paths | Consume accepted API only |
| R2 | base CAD adapter | Consume only |
| R3 | component/view registry | Consume only |
| R4 | revision/current/manifest integration | Consume only |
| R5 | visual supervisor/provider adapter | Consume only |
| R6 | repair planning/executor routing | Consume only |
| R7 | publisher/authorization integration | Consume only |
| S2C/VS-T3/S3B live harnesses | AutoCAD/File IPC shared tests | Prefer read-only invocation; no edit while another writer owns them |
| Luna/local private evidence | private machine-local paths/artifacts | Never commit; consume only approved sanitized evidence |
| R8 pilot test path | R8 sole writer | One writer per bounded future Issue |
| R8 review record | R8 sole writer | Create only after corresponding evidence exists |

Any ambiguous ownership means STOP before write.

---

## Failure-routing matrix

A failing pilot is diagnostic evidence, not permission for R8 to fix production.

| Failure | Owning follow-up |
|---|---|
| source/custody/fusion identity defect | R1 |
| exact-base eligibility/provenance/extraction defect | R2/S3 accepted owner |
| component/view graph defect | R3 |
| revision/currentness/stale-state defect | R4 |
| visual evidence/verdict/provider-attestation defect | R5 / accepted worker owner |
| repair planning/execution/cleanup/rollback defect | R6 / existing repair owner |
| publication/authorization/backup/recovery defect | R7 / existing publication owner |
| shared manifest/checkpoint defect | existing manifest owner under a fresh bounded Issue |
| AutoCAD/File IPC transport defect | existing File IPC/.NET owner under a fresh bounded Issue |
| private-data policy gap | governance/owner decision; no runtime workaround |

After a fix is accepted, return to Task 0 and rebaseline before resuming the pilot.

---

## Verification policy for Issue #142 planning PR

Issue #142 itself is docs-only. Before final planning handoff:

- [ ] Compare issued base to branch and confirm forward-only ancestry.
- [ ] Confirm cumulative diff contains exactly:

```text
docs/superpowers/specs/2026-08-09-r8-pilot-program-design.md
docs/superpowers/plans/2026-08-09-r8-pilot-program.md
```

- [ ] Confirm no runtime/test/workflow/dependency/lock/schema/contract path changed.
- [ ] Scan both docs for `TODO`, `TBD`, accidental moving API names used as accepted contracts, and contradictory PASS/SKIP semantics.
- [ ] Run/obtain applicable docs/reuse/architecture checks.
- [ ] Open DRAFT PR only.
- [ ] Require hosted `tests` PASS on exact final planning head/current-main synthetic.
- [ ] Require hosted `reuse-declaration` PASS.
- [ ] Record AutoCAD .NET as NOT RUN unless hosted canonical workflow legitimately executes it.
- [ ] Record AutoCAD Mechanical live as NOT RUN.
- [ ] Record real provider/model/auth as NOT RUN.
- [ ] Record private/customer CAD as NOT RUN.
- [ ] STOP WRITE after hosted GREEN and final evidence capture.

Final return string:

`CODER B R8 PLANNING READY — STOP WRITE`
