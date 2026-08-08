# R8 Pilot Program Design

Status: planning only — Issue #142 authorizes no R8 runtime implementation, test harness, workflow, dependency, schema/contract change, AutoCAD execution, real provider/model/auth execution, or private/customer CAD use.

Date: 2026-08-09

Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

Issue: `#142 — [Acceleration][Planning] R8 Pilot Program executable design and acceptance plan`

Activation comment: `5227447357`

## 1. Scope resolution

R8 is an **acceptance program**, not a new production subsystem.

The accepted program architecture already assigns production authority to R1 through R7 and defines the final pilot order as synthetic, disposable AutoCAD Mechanical, approved private real-drawing, then a separately authorized production-readiness review. R8 therefore must compose accepted owners and collect evidence; it must not create a new CAD, vision, worker/provider, repair, revision, manifest, approval, publication, or pilot-state truth owner.

The selected architecture is:

```text
accepted R1-R7 runtime and evidence owners
        |
        v
mandatory R8 fresh rebaseline
        |
        +--> synthetic orchestration pilot
        |
        +--> disposable AutoCAD Mechanical pilot
        |
        +--> public-fixture full-system pilot
        |
        +--> separately authorized private/customer pilot
        |
        v
sanitized acceptance dossier
        |
        v
separately authorized production-readiness review
```

R8 may add only narrowly scoped pilot tests/runbooks/evidence records when a future Master PO Issue explicitly authorizes them. It must not add production behavior merely to make a pilot pass.

If any pilot proves that accepted production behavior is missing or defective, the pilot stops and the defect returns to the existing owning stage. The repair is then implemented under a fresh bounded R1-R7 defect/runtime Issue. The R8 pilot resumes only after that fix is independently accepted and the pilot is freshly rebaselined.

## 2. Alternatives considered

### 2.1 One monolithic end-to-end R8 orchestrator — rejected

A new R8 runtime module that calls R1 through R7 and owns pilot state would appear convenient, but it would create another orchestration/state authority above already accepted manifest, revision, visual, repair, and publication owners. It would also tempt the pilot layer to normalize mismatched upstream APIs instead of forcing correct rebaseline.

This approach is rejected.

### 2.2 Manual-only pilot runbook — rejected as insufficient

A prose-only checklist avoids duplicate runtime authority, but it is not strong enough for deterministic acceptance. It cannot by itself prove exact SHAs, replayable inputs, stale-evidence rejection, candidate hashes, expected live gates, or evidence completeness.

This approach is useful only as operator guidance around automated/existing gates.

### 2.3 Staged acceptance program over existing owners — selected

Each pilot stage has one bounded objective, explicit prerequisite matrix, exact evidence requirements, and literal PASS/FAIL/SKIP/NOT RUN semantics. Existing R1-R7 APIs remain authoritative. R8-specific code, if any, is test/runbook-only and disposable. No R8 production module or persistent store is required.

## 3. Hard authority boundaries

R8 may:

- prepare a final post-R7 dependency/reuse map;
- invoke already accepted R1-R7 interfaces under separately authorized pilot Issues;
- run synthetic, disposable, public-fixture, and private/customer acceptance scenarios in the required order;
- collect references to authoritative evidence already produced by R1-R7;
- verify that hashes, lineage, approvals, verdicts, cleanup, rollback, and publication records are mutually bound;
- produce a sanitized pilot acceptance dossier;
- recommend PASS, FAIL, BLOCKED, or `R8 REBASELINE REQUIRED` to Master PO.

R8 may not:

- implement missing R1-R7 production behavior;
- create a second end-to-end workflow/state store;
- parse CAD or source media for new authority;
- issue source/custody identity;
- create component/view registry identity;
- create/select/promote/rollback candidate revision state;
- issue visual PASS;
- issue engineering/human approval;
- plan or execute repair outside accepted R6;
- mint publication authorization or publish outside accepted R7;
- add or modify AutoCAD/File IPC transport;
- add another worker/model/provider transport;
- treat a model/provider result as self-authorizing evidence;
- commit private/customer CAD or raw private evidence;
- modify source/base/accepted/published CAD merely to satisfy a pilot;
- turn `SKIP` or `NOT RUN` into PASS.

## 4. Required fresh post-R7 rebaseline

No R8 executable pilot work may begin until Master PO performs a fresh rebaseline against the then-current accepted `main` after required R1-R7 runtime acceptance.

The rebaseline must resolve exact accepted paths, symbols, versions, fields, tests, owners, evidence artifacts, and active writers for all facts the intended pilot will consume.

At minimum map:

1. final R1 SourceBundle/source-custody/fusion identities and source-binding semantics;
2. final R2 Base CAD Adapter identity/provenance semantics when exact-base reuse is exercised;
3. final R3 Component/View Registry identity and impact graph;
4. final R4 candidate revision, parent/baseline lineage, selection-for-review/currentness, stale-state, and immutable candidate artifact identity;
5. final R5 independent visual verdict, region/view/sheet evidence identity, freshness, provider attestation, and accepted `PASS`/`FAIL`/`NEEDS_HUMAN` semantics;
6. final R6 repair-plan/result/approval/cleanup/rollback/second-review semantics and exact representation of "no repair required";
7. final R7 publication eligibility, authorization, publication, replay/recovery, target hash, and publication evidence semantics;
8. engineering/human approval owner and scope/freshness/consumption semantics;
9. manifest/checkpoint/resume owner used by accepted R1-R7;
10. canonical JSON/hash and file-hash owners;
11. safe path/reparse/custody and disposable-root owners;
12. AutoCAD Mechanical live harnesses and exact prerequisite variables;
13. official worker/provider/auth/runtime seam and provider-observed policy/schema attestation;
14. exact dependency and plugin assembly identities used by live pilots;
15. current writer/reviewer overlap for every proposed pilot test or review-record path.

### 4.1 `R8 REBASELINE REQUIRED`

Stop before the first R8 repository write or executable pilot when any required upstream owner is missing, moving, contradictory, or not accepted.

`R8 REBASELINE REQUIRED` is mandatory when:

- R1 remains incomplete or its source/custody/fusion identities are not final;
- R2-R7 are only planning artifacts rather than accepted runtime;
- exact accepted R3/R4/R5/R6/R7 symbols cannot be mapped without guessing;
- the final R5 provider seam or attestation is not accepted;
- the final R7 publication semantics are unresolved;
- the pilot requires exact-base extraction while S3B live acceptance or accepted successor evidence is still missing;
- a live harness was changed after its accepted evidence without a fresh acceptance decision;
- a required safe-path, rollback, approval, or publication owner would need to be copied into R8;
- an active writer overlaps the proposed pilot write-set;
- the pilot would need a production code change to become executable.

## 5. Pilot sequence

The minimum R8 sequence is dependency ordered. Later stages may not bypass earlier required stages.

### 5.1 R8-S — Synthetic orchestration pilot

Purpose: prove that final accepted R1-R7 contracts compose deterministically without depending on AutoCAD, a real model/provider, private data, or production publication.

Use only generated/synthetic/non-sensitive source descriptors and CAD fixtures. Provider-dependent behavior uses the accepted fake/stub seam only where the final owner already supports it.

Required outcomes:

- exact R1 source/custody/fusion identities are accepted by downstream adapters;
- optional exact-base route is represented using synthetic accepted evidence, not a fabricated live claim;
- R3 component/view graph is deterministic;
- R4 revision lineage is deterministic and immutable;
- stale candidate/evidence is rejected;
- R5 closed verdict validation/aggregation behaves correctly with accepted fake-provider evidence;
- R6 approved repair/no-repair paths remain bounded and cannot self-authorize;
- R7 eligibility/authorization/publication logic is exercised only through a safe synthetic/disposable target if final R7 explicitly supports such an offline mode;
- all identities and evidence links replay exactly;
- no R8 production owner is introduced.

Required evidence class: offline/synthetic.

Real AutoCAD, real provider/model/auth, and private/customer data remain `NOT RUN` for this stage.

### 5.2 R8-D — Disposable AutoCAD Mechanical pilot

Purpose: prove real AutoCAD Mechanical behavior and filesystem/session safety independently of private data.

Use an operator-approved generated/non-sensitive disposable DWG/DXF fixture under the accepted disposable root. Reuse accepted S2C/VS-T3/File IPC/.NET/live evidence owners and, when the scenario includes exact-base reuse, accepted S3B/live successor evidence.

Required outcomes:

- exact plugin/build identity is recorded;
- exact AutoCAD Mechanical version/profile/device/media prerequisites are recorded;
- candidate/source/accepted hashes are recorded before execution;
- source/base/accepted inputs remain byte-identical;
- candidate-only mutation is proven when mutation is expected;
- DBMOD/session/layout/UCS/view state restoration follows the reused live owner;
- request/result artifacts are cleaned according to accepted ownership;
- live native render/evidence export succeeds where required;
- backup/rollback/reopen/second-review behavior required by final R6/R7 is exercised through accepted owners;
- no private/customer data is used;
- public-fixture full-system acceptance is not claimed yet.

Required evidence class: AutoCAD Mechanical live.

A stage cannot PASS if its required AutoCAD gate is `SKIP` or `NOT RUN`.

### 5.3 R8-F — Public-fixture full-system pilot

Purpose: prove the complete accepted product loop with redistributable/non-sensitive evidence before any customer drawing is used.

The fixture must be legally reusable, documented, non-sensitive, and sufficiently representative to exercise the intended end-to-end architecture. The first complete public fixture should include an exact-base route if exact-base reuse is part of the target product proof.

Required outcomes:

- final R1 source/custody/fusion evidence comes from the real accepted source path, not synthetic authority;
- final R2/R3/R4 candidate provenance and revision lineage are real for this fixture;
- real AutoCAD Mechanical render/measurement/read-back evidence is fresh after the latest mutation;
- real accepted provider/model/auth seam is exercised for any R5/R6 capability whose production design depends on it;
- provider-observed instruction/policy/schema attestation is proven from the accepted worker boundary;
- R5 final verdict is produced only from fresh evidence;
- any R6 repair uses separate accepted approval and is followed by a fresh evidence cycle and fresh R5 result;
- engineering/human approval is present for all required protected/DRIVING/conflict decisions;
- R7 publication is exercised only according to final accepted R7 policy and only against a non-production/disposable target;
- final publication evidence proves exact candidate/target hash relationship and recovery semantics;
- replay from the same immutable source/build state is deterministic at every deterministic owner;
- no customer/private material is required.

Required evidence classes: offline/synthetic where applicable, AutoCAD Mechanical live, real provider/model/auth where required by final R5/R6, and human engineering approval where required.

### 5.4 R8-P — Separately authorized private/customer pilot

Purpose: prove the already accepted complete system on one explicitly approved real private/customer package.

This stage is not automatically authorized by completion of R8-F. Master PO/owner must issue a separate private-data authorization naming the approved source package, allowed local evidence root, retention/redaction policy, and exact pilot scope.

No production code changes are allowed during the private pilot. The exact binaries, dependencies, contracts, and plugin identity accepted for the pilot must be frozen before private material is opened.

Required outcomes:

- private-data authorization is recorded without exposing private bytes or sensitive paths in public GitHub evidence;
- source/custody evidence remains authoritative and immutable;
- engineering intent and protected dimensions are explicitly approved by the owner/engineer;
- all required R1-R7 stages execute through their accepted owners;
- every post-mutation visual/measurement result is fresh;
- repair, if used, is separately approved and bounded;
- publication, if authorized for the pilot, uses only the exact approved non-production/private target policy and final accepted R7 authority;
- rollback and cleanup succeed;
- sanitized public dossier contains only hashes, categorical states, non-sensitive IDs, versions, counts, and approved references;
- raw customer CAD, images/PDFs, OCR, provider payloads containing customer content, absolute private paths, credentials, and unapproved screenshots are not committed.

Required evidence classes: AutoCAD Mechanical live, real provider/model/auth where production design requires it, human engineering approval, and explicit private/customer-data authorization.

### 5.5 Production-readiness review — outside automatic R8 PASS

R8-P PASS does not itself authorize production rollout.

A separate Master PO/owner decision must review:

- all R8 evidence;
- residual risks;
- rollback/recovery readiness;
- data-retention/privacy policy;
- supported drawing classes and explicit exclusions;
- operator prerequisites;
- provider/account/auth policy;
- AutoCAD Mechanical workstation policy;
- publication/backup/restore policy;
- support/incident ownership.

Only that separate decision may authorize production readiness.

## 6. Pilot input contract

R8 does not create a new schema. After rebaseline, each pilot must assemble an immutable input snapshot using accepted owners and record the exact evidence references required by the selected route.

At minimum the snapshot must identify:

```text
pilot stage and pilot run identity
exact accepted repository/main SHA
exact R1-R7 implementation identities used
locked Python/dependency environment identity
AutoCAD plugin assembly SHA when live
AutoCAD Mechanical version/profile identity when live
worker/provider/model/config identity when real provider is used
provider-observed instruction/policy/schema attestation identity
source package identity and source/custody hashes
source roles/pages/regions required by the scenario
engineering intent and approval identity
protected/DRIVING/reference/conflict dimension evidence
optional exact-base CAD source SHA and revision
candidate/disposable root identity
R3 component/view registry identity
R4 candidate revision/parent/baseline identity
expected R5 evidence scope
allowed R6 repair operation classes and approval requirements
R7 target/authorization policy when publication is exercised
privacy classification and evidence-retention policy
required pilot gates and STOP conditions
```

Caller-selected filenames, UUIDs, timestamps, paths, model text, or list order may not replace accepted owner identities.

## 7. Evidence package

R8 must not create a second persistent evidence store. The authoritative records remain with accepted R1-R7 manifest/checkpoint/revision/verdict/repair/publication owners.

The R8 acceptance dossier is a **derived index of authoritative evidence references**, plus sanitized execution metadata. It does not become a new source of truth.

A complete dossier records, as applicable:

### 7.1 Build and environment identity

- exact accepted `main` SHA;
- exact R1-R7 implementation/release identities;
- dependency-lock identity;
- Python version;
- canonical verifier result;
- plugin assembly SHA;
- AutoCAD Mechanical version/profile/device/media identity;
- worker/provider SDK/runtime/model/config identity;
- provider-observed policy/schema/instruction attestation identity.

### 7.2 Source and engineering identity

- R1 bundle/custody/fusion identity and canonical hashes;
- source item hashes and roles needed by the pilot;
- exact-base source hash/revision when applicable;
- engineer/owner intent reference;
- protected/DRIVING dimension/constraint evidence identities;
- conflict/unresolved disposition and approval evidence.

### 7.3 Candidate and lineage identity

- R3 component/view registry identity;
- R4 candidate revision identity;
- parent/baseline/selected-for-review identity;
- candidate artifact hash before each mutation cycle;
- affected component/view identities;
- immutable supersession/rollback evidence where applicable.

### 7.4 Visual and repair evidence

- latest mutation identity/hash;
- fresh AutoCAD render/entity/measurement evidence identity;
- R5 request/verdict identity and per-region/view/sheet outcome;
- exact final R5 verdict after the last mutation;
- R6 repair-plan identity, approval identity, operation/executor identity, pre/post hashes, result, cleanup/rollback evidence, and fresh second-review evidence when repair occurs;
- accepted no-repair state identity when no repair is required.

### 7.5 Publication evidence

- R7 eligibility identity;
- human/engineering approval identity required for publication;
- exact publication authorization identity/status/consumption state;
- candidate SHA before publication;
- expected target prehash when required by final R7;
- backup identity/hash;
- final published target hash;
- reopen/rerender/remeasure or equivalent final verification evidence required by final R7;
- replay/recovery classification when applicable.

### 7.6 Safety and privacy evidence

- source/base/accepted immutability proof;
- candidate-only mutation proof;
- DBMOD/session-state restoration proof for live gates;
- request/result/staging cleanup result;
- backup/rollback result;
- private-data authorization reference for R8-P only;
- explicit redaction check proving no customer bytes, raw OCR/provider content, secrets, or private paths entered public artifacts;
- literal PASS/FAIL/SKIP/NOT RUN matrix.

### 7.7 Dossier identity

Any deterministic dossier identity must reuse the accepted canonical hash owner after rebaseline. R8 must not implement a new canonical serializer or hash helper.

The dossier hash is a convenience for evidence completeness/replay. It is not a replacement for authoritative upstream evidence hashes.

## 8. Evidence-class matrix

| Gate | R8-S | R8-D | R8-F | R8-P |
|---|---|---|---|---|
| Canonical offline verifier | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| R1-R7 deterministic contract/identity checks | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| Synthetic/fake-provider seam | ALLOWED/REQUIRED where applicable | ALLOWED only for isolation | MAY RUN as regression, not production evidence | MAY RUN as regression, not production evidence |
| AutoCAD .NET build/tests | NOT RUN unless separately required | REQUIRED | REQUIRED | REQUIRED |
| AutoCAD Mechanical live | NOT RUN | REQUIRED | REQUIRED | REQUIRED |
| S2C/VS-T3 live evidence | NOT RUN | REQUIRED as scenario needs | REQUIRED | REQUIRED |
| S3B/exact-base live | NOT RUN | REQUIRED when exact-base route is exercised | REQUIRED for the first exact-base full proof | REQUIRED when private scenario uses exact-base |
| Real provider/model/auth | NOT RUN | NOT RUN unless final stage owner explicitly requires it for this isolation gate | REQUIRED wherever final R5/R6 production behavior depends on it | REQUIRED wherever final R5/R6 production behavior depends on it |
| Human engineering approval | synthetic fixed fixture only; no real-world authority claim | operator fixture approval only | REQUIRED for engineering decisions | REQUIRED |
| Private/customer authorization | NOT RUN | NOT RUN | NOT RUN | REQUIRED |
| R7 non-production publication | synthetic/disposable only if final R7 supports it | optional/required by issued scenario | REQUIRED for complete public proof | REQUIRED only when separately authorized in private pilot |
| Production publication | NOT RUN | NOT RUN | NOT RUN | NOT RUN unless separately authorized outside this plan |

## 9. PASS / FAIL / SKIP / NOT RUN semantics

### 9.1 PASS

A gate is PASS only when:

- the required command or accepted owner actually executed;
- execution is tied to the exact pilot build/environment identity;
- required assertions completed without failure;
- the evidence package references the exact result;
- no required sub-gate is silently skipped;
- the result remains fresh relative to the candidate/source state it claims to verify.

### 9.2 FAIL

FAIL means the gate executed and any required safety, determinism, correctness, freshness, approval, cleanup, rollback, or evidence assertion failed.

A required FAIL stops the pilot immediately. A later successful rerun is a new attempt and must retain the failed attempt as evidence where the accepted owner supports history.

### 9.3 SKIP

SKIP means a collected optional/gated test did not execute because its explicit prerequisites were unavailable or the exact branch of the scenario did not apply.

SKIP is never PASS.

If a stage requires that gate, the stage cannot PASS while the gate is SKIP.

### 9.4 NOT RUN

NOT RUN means the gate was intentionally not executed in that stage.

Examples:

- real provider/model/auth in R8-S;
- private/customer data in R8-S/R8-D/R8-F;
- production publication in all pilots unless a separate authorization exists.

NOT RUN is never PASS and may not be relabeled as SKIP merely because a harness exists.

## 10. Determinism and replay

Every deterministic R8 stage must prove exact-output or exact-identity replay where the accepted owner promises determinism.

Required replay dimensions include, as applicable:

- source list/input order permutations;
- component/view ordering;
- candidate lineage read order;
- region/view/sheet evidence ordering;
- repeated canonical dossier construction;
- same-hash publication replay semantics;
- cross-platform-sensitive path/numeric/canonicalization cases already owned upstream.

R8 must not demand byte-identical outputs from a real model/provider where the accepted provider owner does not promise that property. Instead it verifies closed schema, authority, evidence binding, bounded semantics, and server-owned deterministic aggregation.

## 11. Freshness rules

Any candidate mutation invalidates all visual/measurement evidence captured before that mutation unless the accepted owner explicitly proves otherwise.

R8 must verify the final acceptance chain in this order:

```text
candidate mutation complete
  -> candidate/revision identity finalized for the cycle
  -> fresh AutoCAD/render/measurement evidence
  -> fresh R5 verdict
  -> R6 repair only when separately approved
  -> if repaired: new candidate identity + new fresh evidence + new R5 verdict
  -> engineering/human approval as required
  -> R7 final eligibility/authorization/publication
  -> required post-publication verification
```

No pre-repair R5 PASS can authorize a post-repair candidate. No stale provider response can authorize later state. No previous publication authorization can silently authorize a changed target/candidate.

## 12. Protected engineering constraints

R8 preserves final accepted engineering authority from upstream owners.

Mandatory pilot behavior:

- confirmed DRIVING/protected dimensions cannot be changed merely to improve pixel/visual similarity;
- unresolved/conflicting critical dimensions block any pilot stage that requires engineering correctness unless the accepted owner explicitly routes them to human resolution;
- image/pixel deltas may not become model-space mutations without accepted calibration/datum mapping;
- model/provider suggestions remain untrusted until closed validation and separate approval;
- a visual PASS is not engineering approval;
- engineering approval is not publication authorization;
- publication success is not proof of engineering correctness.

## 13. Public-fixture policy

The public fixture stage must use content that is safe to retain in public CI/review evidence.

Before R8-F execution, the future pilot Issue must record:

- fixture source and reuse/license status;
- exact immutable fixture hash;
- whether redistribution in the repository is permitted;
- expected engineering intent and known ground-truth dimensions;
- whether an exact-base CAD is part of the fixture;
- allowed publication target and cleanup policy;
- any reason the fixture is representative of the target product route.

If redistribution is not permitted, treat it as externally hosted/locally supplied non-sensitive evidence and keep bytes outside the repository. Do not silently convert it into a committed fixture.

## 14. Private/customer pilot policy

R8-P requires a separate authorization that names the specific private-data scope. The authorization should identify only the minimum metadata necessary in public records.

Private artifacts remain outside Git and public CI artifacts unless explicitly approved otherwise.

Public evidence must not include:

- original private CAD/image/PDF bytes;
- customer names/vehicle identifiers when not approved for disclosure;
- absolute private source paths;
- raw OCR/transcription output containing customer content;
- raw model/provider payloads containing customer content;
- API keys/tokens/cookies/account identifiers;
- screenshots or rendered crops not separately approved for publication;
- backup copies or private intermediate candidates.

Allowed sanitized evidence may include approved opaque IDs, SHA-256 values, software versions, categorical gate states, test counts, operation categories, timings if non-sensitive, and approval references that reveal no private content.

## 15. Failure, rollback, and cleanup

### 15.1 Immediate pilot STOP

Stop the current pilot attempt immediately for:

- source/base/accepted/published input mutation;
- candidate mutation outside the accepted disposable/candidate owner;
- unexpected DBMOD/session-state change;
- stale R1/R3/R4/R5/R6/R7 evidence;
- provider attestation mismatch or untrusted provider route;
- unresolved protected/DRIVING dimension conflict;
- R5 final `FAIL` or `NEEDS_HUMAN` where PASS is required;
- repair attempted without accepted separate approval;
- partial mutation without accepted cleanup/rollback proof;
- cleanup failure or late result after cancel/timeout;
- publication target/hash/authorization mismatch;
- backup/restore/recovery failure;
- safe-path/root/reparse/alias ambiguity;
- private-data leakage into repository/CI/public logs;
- any required gate reported as SKIP/NOT RUN;
- any need to change production code during the pilot.

### 15.2 Recovery

Recovery follows accepted owners only:

- R4 owns candidate lineage/supersession/rollback semantics;
- R6/existing repair owners own mutation cleanup/rollback evidence;
- R7/existing publication owners own target backup/restore/recovery;
- manifest/checkpoint owner records durable state;
- R8 only verifies and indexes the resulting evidence.

R8 must not implement emergency file replacement, direct CAD repair, manual manifest edits, or alternate rollback logic.

## 16. Current accepted/live harness reuse

The planning baseline already contains useful live and private-data harnesses that future R8 work should reuse after fresh rebaseline rather than duplicate.

### 16.1 Canonical verifier

`scripts/verify.ps1` owns:

- clean-tree verification provenance;
- locked Python/environment checks;
- optional/required AutoCAD .NET gate behavior;
- offline pytest;
- explicit real-data unavailable-state probe;
- explicit AutoCAD Mechanical unavailable-state probe;
- optional AutoCAD live marker;
- Ruff and diff checks;
- side-effect snapshot verification.

R8 must not build a second general verifier.

### 16.2 S2C native render

Accepted S2C implementation records a real AutoCAD Mechanical 2027 live PASS for native PNG/PDF capture with DBMOD/drawing/session invariants and negative device/media refusal probes.

R8 should reuse its accepted successor live path for fresh pilot evidence rather than creating another native render path.

### 16.3 VS-T3 visual evidence

Existing VS-T3 live harness proves disposable AutoCAD visual evidence export can bind render/entity-map/measurement artifacts while preserving drawing hash and session state.

R8 should reuse the final accepted successor.

### 16.4 S3B exact-base extraction

The planning baseline includes an S3B live harness, but its implementation record states live acceptance was `NOT RUN` on that historical head.

Therefore any R8 stage that requires exact-base live extraction must require a fresh accepted S3B/successor live PASS. An unavailable-state SKIP cannot satisfy this dependency.

### 16.5 Private fidelity gate and real-image benchmark

Existing private fidelity and real-image gates demonstrate useful privacy and real-data test patterns: source bytes remain external and repository tests consume explicit environment-provided paths.

They are specialized predecessor evidence, not substitutes for the final R8 full-system private pilot.

## 17. R7 handoff boundary

Current moving R7 planning resolves R7 as a thin verified-publication adapter and explicitly says R8 owns pilot selection/rollout. R8 may use that semantic boundary, but it must not assume draft R7 symbol names or final target policy.

After final R7 acceptance, R8 must map:

- eligibility evidence;
- exact publication authorization semantics;
- target prehash behavior;
- same-hash replay;
- backup/recovery evidence;
- final published hash;
- authorization consumption;
- post-publication verification requirements.

If final R7 retains an existing-target replacement-only first policy, R8 must prepare an approved non-production existing target with the exact expected prehash. It must not invent an absent-target sentinel or bypass R7 authorization.

## 18. Review topology

Every executable R8 pilot Issue must have independent review domains.

### 18.1 Integration/CI evidence reviewer

Verify:

- exact accepted main/build SHAs;
- exact pilot write-set;
- hosted/local gate identity;
- current-main synthetic where repository changes exist;
- PASS/FAIL/SKIP/NOT RUN truthfulness;
- evidence-package completeness;
- active-writer overlap;
- no stale planning API assumption.

### 18.2 Safety/authority/privacy reviewer

Verify:

- source/base/accepted/published immutability;
- candidate-only mutation;
- provider/model non-authority;
- protected engineering constraints;
- approval separation;
- repair separation;
- R5/R6/R7 freshness chain;
- private-data redaction and retention;
- rollback/cleanup evidence;
- no duplicate store/transport/publisher/repair/verdict owner.

### 18.3 Live AutoCAD operator/evidence role

For live stages, the operator supplies the authorized local AutoCAD session, fixture/private-data permissions, and exact environment prerequisites. This role does not gain source-code review or merge authority by operating the live system.

Master PO remains final acceptance and merge authority.

## 19. Current overlap map at planning time

Issue #142 planning itself changes only its two authorized docs and has no runtime overlap.

Future R8 execution must fresh-check at issuance time. Current planning-time hazards include:

| Lane | Current/moving scope | R8 rule |
|---|---|---|
| R1C #123 | `cad_agent/source_fusion.py` + `tests/test_cad_agent_source_fusion.py`; production blocked | Do not touch; R8 runtime blocked until final R1 |
| Wave 1A #113 | worker/handoff/provider attestation paths | Treat as moving; final accepted provider seam required |
| R2 PR #129 | planning only | No runtime API assumption |
| R3 PR #134 | planning only | No runtime API assumption |
| R4 PR #137 | planning only | No runtime API assumption |
| R5 PR #138 | planning only | No runtime API assumption |
| R6 PR #139 | planning only/frozen after STOP WRITE | No runtime API assumption |
| R7 PR #141 | planning only | No runtime API assumption |
| AutoCAD live harnesses | shared File IPC/.NET/live test boundaries | Prefer reuse; do not edit while another writer owns them |
| private/local Luna evidence | machine-local/private | Consume only through explicit accepted evidence; never commit |

## 20. Future R8 issue shape

R8 implementation/acceptance should be issued as separate, sequential Issues. Do not authorize all stages at once.

Preferred sequence:

1. **R8-0 — Final readiness rebaseline**: strict read only, no repository writes.
2. **R8-S — Synthetic orchestration pilot**: one focused pilot test/harness plus at most one sanitized review record if needed.
3. **R8-D — Disposable AutoCAD Mechanical pilot**: prefer existing live harness invocation; create a new R8-specific live test only when final accepted owners cannot be composed safely from existing tests. No production code.
4. **R8-F — Public-fixture full-system pilot**: public/non-sensitive fixture and real provider/live evidence as required; no production code.
5. **R8-P — Private/customer pilot**: ideally repository writes `NONE`; private artifacts external; sanitized acceptance record only if separately authorized.
6. **Production-readiness review**: separate governance decision after R8-P.

Every future repository-changing pilot Issue must define:

- exact accepted base;
- sole writer;
- exact CREATE/MODIFY/do-not-modify paths;
- whether the first write must be a test/evidence harness;
- exact prerequisites;
- exact execution commands using accepted owners;
- exact PASS/FAIL/SKIP/NOT RUN expectations;
- hosted gates if repository changes occur;
- live/private/provider gates when applicable;
- evidence package;
- reviewer pair;
- rollback/cleanup;
- STOP conditions.

Any future R8 request for a production module or production behavior change is presumptively mis-scoped and requires `R8 REBASELINE REQUIRED` plus routing to the correct R1-R7 owner.

## 21. Candidate future write-sets

These are planning candidates only. Exact paths must be revalidated after R1-R7 acceptance.

### R8-S candidate

Prefer:

```text
CREATE tests/test_cad_agent_r8_synthetic_pilot.py
CREATE docs/reviews/<date>-r8-synthetic-pilot.md
```

No production file.

### R8-D candidate

Prefer first to reuse existing accepted live harnesses with **repository writes NONE**.

Only if a closed cross-owner live composition test is genuinely missing:

```text
CREATE mcp_integration_lib/tests/test_r8_disposable_pilot_live.py
CREATE docs/reviews/<date>-r8-disposable-live-pilot.md
```

No dispatcher/plugin/client production change.

### R8-F candidate

Prefer:

```text
CREATE tests/test_cad_agent_r8_public_fixture_pilot.py
CREATE docs/reviews/<date>-r8-public-fixture-pilot.md
```

If the public fixture is redistributable and a committed fixture is needed, that is a separate explicit write-set decision; it is not implicit in the pilot test path.

### R8-P candidate

Prefer:

```text
Repository writes: NONE during execution
```

A separately authorized sanitized review record may be created after successful evidence redaction. Raw private evidence remains outside Git.

## 22. Migration and rollback

Issue #142 is documentation-only and has no runtime/data/schema migration.

Future R8 pilot tests should be additive and removable. They must not migrate authoritative R1-R7 state.

Pilot rollback means:

- stop the pilot;
- use accepted R4/R6/R7 rollback/cleanup owners as applicable;
- preserve failed-attempt evidence according to accepted manifests/checkpoints;
- remove only R8-owned temporary/public test artifacts under their approved roots;
- never rewrite source/base/accepted/private evidence to "reset" a run.

## 23. Planning acceptance

Issue #142 planning is ready for a DRAFT PR only when:

- exactly the two authorized planning docs exist;
- the design defines R8 as acceptance program rather than a production owner;
- pilot order is explicit and dependency-gated;
- `R8 REBASELINE REQUIRED` is mandatory for moving/incomplete R1-R7 seams;
- offline/live/provider/human/private evidence classes are separated;
- PASS/FAIL/SKIP/NOT RUN semantics are explicit;
- evidence package covers source/custody, candidate/revision, component/view, R5, R6, engineering approval, R7, hashes, rollback/cleanup, privacy, and STOP conditions;
- no moving upstream symbol is invented;
- no runtime/test/workflow/dependency/lock/schema/contract path changes;
- hosted `tests` and `reuse-declaration` are GREEN on the exact final planning head/current-main PR synthetic;
- the PR remains DRAFT and the writer stops repository writes.

## 24. Planning STOP conditions

STOP and report rather than widening Issue #142 when:

- a third repository path is needed;
- runtime/test/workflow/dependency/lock/schema/contract change appears necessary;
- AutoCAD or provider execution appears necessary to complete planning;
- private/customer data appears necessary;
- accepted architecture contradicts the staged pilot model;
- a moving R1-R7 planning API would need to be treated as final;
- final pilot design would require a new persistent R8 store or production orchestrator;
- current branch no longer descends exactly from the issued base without an explicit Master PO amendment.
