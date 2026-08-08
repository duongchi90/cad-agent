# R7 Verified Publisher Design

Status: planning only — Issue #140 authorizes no R7 runtime implementation and no R8 pilot work.

Date: 2026-08-09

Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

Issue: `#140 — [Acceleration][Planning] R7 Verified Publisher executable design and runtime plan`

Activation comment: `5227350155`

## 1. Scope resolution

R7 is required, but it is **not a new broad publisher subsystem**.

The accepted reuse inventory already classifies `verified-promotion` as `EXTEND_WITH_ADAPTER`. Current accepted publication-adjacent owners cover important pieces but not the complete roadmap requirement:

- `cad_agent.fidelity.promote_fidelity_page()` promotes a private fidelity candidate only to `approved_for_mechanical_review`; it explicitly allows read-only Mechanical review and prohibits production save;
- `cad_agent.visual_contracts.require_auto_publish_authorized()` validates a run-scoped, path/hash-bound, single-use publication authorization but does not copy or replace target bytes;
- `cad_agent.visual_evidence` owns fresh read-only visual evidence and strong hash/path handling, not final production publication;
- `cad_agent.manifest` owns durable atomic run/checkpoint persistence, not a second publication truth store;
- existing approval/proposal-apply boundaries prove authority separation but do not let R7 mint approval;
- existing repair/live owners contain verified-backup and rollback behavior that must be reused or extended rather than duplicated.

Therefore the R7 roadmap requirement is a **thin verified-publication eligibility and execution adapter over accepted existing authorities**.

`R7 SCOPE GAP — MASTER PO DECISION REQUIRED` is **not triggered by the accepted planning baseline**. It becomes a future STOP condition only if post-R6 rebaseline cannot resolve a safe existing publication-file/backup/authorization-consumption seam without creating a second authority.

## 2. Decision summary

R7 owns only the transition from an already-selected, already-verified candidate to verified publication evidence.

The intended post-rebaseline flow is:

```text
accepted R4 selected candidate/current-lineage evidence
+ accepted R5 visual verdict evidence
+ accepted R6 repair/second-review evidence when applicable
+ accepted engineering/human approval evidence
+ accepted source/base provenance and manifest/checkpoint evidence
        |
        v
R7 deterministic publication-eligibility snapshot
        |
        +---- eligible != authorized
        v
existing auto-publish authorization owner
(require_auto_publish_authorized or accepted successor)
        |
        +---- authorized != published
        v
existing safe-file / verified-backup owner
+ existing manifest/checkpoint owner
        |
        v
same-volume temporary copy of exact candidate bytes
        |
        v
atomic target replacement or idempotent same-hash replay
        |
        v
immediate target hash verification
        |
        v
existing manifest/checkpoint owner records durable result
+ existing authorization owner records one-time consumption
        |
        v
R7 verified publication evidence
        |
        +---- published != R4 accepted/current state
        v
R8 may consume the evidence for a separately authorized pilot
```

R7 never:

- selects a candidate revision;
- changes R4 current/accepted state;
- mints visual or engineering approval;
- calls a model/provider;
- runs repair;
- adds an AutoCAD/File IPC transport or operation;
- parses or rebuilds CAD;
- modifies source/base/accepted inputs in place;
- creates a second manifest/checkpoint/publication store.

## 3. Existing-owner reuse map

| Concern | Existing owner on planning baseline | R7 classification | R7 use | R7 prohibition |
|---|---|---|---|---|
| Verified-promotion capability | Current `cad_agent` + `mcp_integration_lib` surfaces named by reuse inventory | `EXTEND_WITH_ADAPTER` | Compose accepted verification + authorization + file promotion | Create a replacement publication subsystem |
| Fidelity promotion checkpoint | `cad_agent.fidelity.promote_fidelity_page` + CLI `fidelity-promote` | `REUSE_AS_COMPATIBILITY_PREDECESSOR` | Preserve private review semantics; reuse tests as regression evidence | Turn `approved_for_mechanical_review` into production publication |
| Auto-publish authorization | `cad_agent.visual_contracts.require_auto_publish_authorized` + `auto-publish-authorization-1.0` | `REUSE_AS_IS` unless final rebaseline proves a bounded owner extension is required | Validate exact run/path/current-target-hash and unused one-time authorization | Mint or reinterpret authorization in R7 |
| Visual evidence freshness | `cad_agent.visual_evidence` | `REUSE_AS_IS` | Consume accepted freshness outcome and safe-file primitives where publicly supported | Create a second evidence/freshness store |
| Visual verdict | accepted future R5 owner | dependency | Consume validated final R5 evidence only | Call provider or issue visual PASS |
| Repair and second review | accepted future R6 + existing headless/Mechanical owners | dependency | Consume final repair/second-review evidence when required | Execute repair or own repair iteration |
| Candidate revision/current lineage | accepted future R4 | dependency | Consume already-selected publishable candidate identity/currentness | Create/select/promote/rollback revision state |
| Component/view provenance | accepted future R3 | dependency | Reference final scoped provenance where required | Rebuild registry |
| Source/base provenance | accepted R1/R2 owners | dependency | Bind publication to accepted source/base identity | Parse or reopen source for new authority |
| Engineering/human approval | accepted owner-controlled approval boundary | `REUSE_AS_IS` | Require exact approval identity/hash/state | Issue approval or infer it from visual/model evidence |
| Manifest/checkpoint/resume | `cad_agent.manifest` and accepted successor | `REUSE_AS_IS` | Persist publication intent/result/recovery state in existing run lifecycle | Add a second state store/database |
| Canonical JSON identity | `cad_agent.drawing_contracts.canonical_json_sha256` | `REUSE_AS_IS` | Build deterministic eligibility/publication IDs | Add another canonical serializer/hash owner |
| File hashing | existing manifest/evidence owners | `REUSE_AS_IS` | Hash exact candidate/target/backup bytes | Trust caller-supplied file hashes without reread |
| Verified backup/rollback | existing live safety owner and any accepted successor | `REUSE/EXTEND_EXISTING_OWNER` | Use accepted public backup/restore primitive | Copy private backup logic into a new R7 authority |
| Safe path/reparse policy | existing visual evidence / IPC / accepted file-safety owner | `REUSE/EXTEND_EXISTING_OWNER` | Require one accepted safe-file primitive | Add a third independent path-security policy |
| AutoCAD/File IPC | `mcp_integration_lib` + .NET owner | external | Optional later delegated read-only post-publish evidence only if separately issued | Add transport or save command |
| Proposal/apply separation | `agent_lib` approval/apply boundary | `REUSE_PATTERN_ONLY` | Preserve separation of evidence and authority | Treat Agent approval as publication authorization |
| R8 pilot rollout | future R8 | external | Emit verified publication evidence | Select pilot/customer/drawing or define rollout |

## 4. Why `fidelity-promote` is not R7 publication

The current fidelity promotion path is intentionally private and review-only.

Its accepted behavior:

```text
reviewable private composition
  -> delegated visual approval
  -> fidelity-promotion-1.0
  -> state = approved_for_mechanical_review
  -> allowed_actions = [mechanical-review-read-only]
  -> prohibited_actions include production-save
  -> read-only Mechanical review
```

That boundary must remain backward compatible. R7 must not rename, widen, or silently reinterpret it as a production publisher.

A future R7 implementation should be adjacent to accepted final publication ownership rather than embedding production publication into the historical fidelity module.

## 5. Four states that must never collapse

R7 must keep these states distinct.

### 5.1 `eligible`

A candidate is eligible only when all required upstream facts are accepted, fresh, mutually bound, and complete.

Eligibility is evidence. It is not permission to write a target.

### 5.2 `authorized`

Publication is authorized only when the accepted publication-authorization owner validates the exact run, target path, current target hash, status, one-time/expiry state, and approval identity.

Authorization does not prove bytes were published.

### 5.3 `published`

Published means the final target bytes have been proven to match the exact eligible candidate bytes and durable publication evidence has been recorded.

### 5.4 `accepted/current`

Accepted/current candidate state belongs to R4 or its accepted successor. R7 must not mark a revision accepted/current merely because publication succeeded.

The invariant is:

```text
eligible != authorized != published != accepted/current
```

No R5 model/visual result may directly produce `authorized` or `published`.

## 6. Mandatory post-R6 rebaseline

No R7 runtime repository write may begin until Master PO performs a fresh rebaseline against then-current accepted `main`.

The runtime Issue must resolve exact accepted paths, symbols, fields, tests, ownership, and active writers for:

1. R1 source-bundle/fusion identity needed at final publication;
2. R2 base-CAD/provenance identity when the candidate contains reused base geometry;
3. R3 component/view registry identity required by final evidence;
4. R4 candidate revision identity, selected/current eligibility semantics, candidate artifact hash, lineage, and stale behavior;
5. R5 final visual-verdict identity and freshness semantics;
6. R6 repair result and second-review semantics, including the exact accepted representation of "no repair required";
7. engineering/human approval identity, scope, freshness/consumption rules, and accepted validator;
8. exact publication-authorization version and validator;
9. exact one-time authorization-consumption persistence owner/API;
10. exact manifest/checkpoint intent/result/recovery owner/API;
11. one accepted public safe-file policy for target, candidate, temporary, and backup paths;
12. one accepted public verified-backup and restore primitive;
13. existing file hashing and canonical hashing APIs;
14. current active writer overlap for every future R7 path;
15. current-main SHA used to issue each bounded runtime task.

The runtime Issue must also map those accepted owners to these semantic R7 facts without inventing upstream names:

```text
run_identity
candidate_revision_identity
candidate_artifact_identity
candidate_sha256
candidate_currentness/freshness
source/base provenance identities
R5 final verdict identity/hash
R6 result or accepted no-repair state identity/hash
engineering/human approval identity/hash
manifest/checkpoint identity
publication_authorization identity/hash
exact target path
expected current target sha256
allowed backup root
publication attempt/consumption identity
```

### 6.1 `R7 REBASELINE REQUIRED` STOP conditions

Stop before the first runtime repository write when any of these is unresolved:

- R4 cannot prove exactly which immutable candidate is selected for publication;
- R5 cannot provide one accepted freshness-bound final visual-verdict record;
- R6/second-review requirement cannot be resolved for the candidate state;
- engineering/human approval is ambiguous or caller-mintable;
- the publication authorization owner cannot validate the exact target/prehash/run binding;
- no accepted owner can persist one-time authorization consumption;
- no accepted public safe-file/reparse primitive exists;
- no accepted public verified-backup/restore primitive exists;
- implementing R7 would require a second manifest/store/path-security/backup/publisher owner;
- an active writer overlaps the proposed R7 task paths;
- accepted publication requires a new AutoCAD mutation/transport operation.

Do not solve any of these by copying private helper logic into R7.

## 7. Initial publication target policy

The accepted `auto-publish-authorization-1.0` requires `expected_initial_sha256`. The safe first R7 runtime interpretation is therefore **replacement of an already-existing authorized target only**.

Initial R7 runtime rules:

- target must already exist as a normal allowed file;
- target suffix must be `.dwg` for the first production publication slice;
- target current SHA-256 must exactly equal the authorization's expected initial SHA-256;
- candidate must be a distinct immutable file from target;
- candidate must be inside the accepted candidate/disposable ownership boundary, not source/base/accepted/published input;
- backup root must be exactly the authorized root and pass the accepted safe-path policy;
- no wildcard, traversal, symlink, junction, reparse alias, or path alias may bypass target identity;
- no overwrite is allowed when the target bytes differ from the exact authorized prehash.

### 7.1 Missing target

An absent target fails closed under `auto-publish-authorization-1.0` because there is no authorized current target hash to validate.

R7 must not invent `null`, zero hash, magic sentinel, or a caller boolean to mean "new file allowed".

If future product requirements need first-time publication into an absent path, Master PO must issue a separate bounded extension/versioning task to the **existing authorization owner** before R7 can support it.

### 7.2 Non-DWG output

The first production R7 slice publishes one authorized DWG target. DXF/PDF/export publication belongs to a separately accepted scope, not an extension inferred by filename.

## 8. Eligibility inputs

R7 eligibility is a deterministic composition of accepted upstream evidence.

At minimum the future eligibility snapshot binds:

```text
run identity
R4 candidate revision identity
candidate artifact SHA-256
R4 currentness/stale evidence
R1/R2 source/base provenance where applicable
R3 registry/scope provenance where required
R5 final visual-verdict identity/hash
R6 repair + second-review identity/hash, or accepted no-repair state
engineering/human approval identity/hash
manifest/checkpoint identity
required upstream gate versions
```

Eligibility fails before any target write when:

- candidate identity/hash no longer matches R4;
- candidate is stale or superseded;
- R5 is absent, stale, `FAIL`, or `NEEDS_HUMAN` for a required scope;
- required R6/second review is absent, stale, or failed;
- a required engineering/human approval is missing, expired, consumed, scoped to another candidate, or otherwise invalid;
- source/base/registry provenance has drifted;
- manifest/checkpoint identity no longer matches the candidate/run;
- any required gate is `NOT_RUN`, `SKIP`, or unresolved where publication requires PASS.

R7 never upgrades a missing gate to PASS.

## 9. Deterministic eligibility and publication identities

R7 reuses `cad_agent.drawing_contracts.canonical_json_sha256()` as the canonical JSON hash owner.

A future eligibility ID is derived only from stable accepted identity material such as:

```text
schema/policy version
run identity
candidate revision identity
candidate SHA-256
source/base provenance identities
R5 verdict identity/hash
R6 result or accepted no-repair identity/hash
engineering/human approval identity/hash
manifest/checkpoint identity
required gate identity set
```

A publication-attempt ID additionally binds:

```text
eligibility SHA-256
publication authorization identity/hash
normalized target identity
expected target pre-publication SHA-256
```

Excluded from deterministic identity authority:

- wall-clock timestamp;
- random temporary filename;
- backup filename suffix;
- PID/thread ID;
- volatile AutoCAD handle unless already embedded in accepted provenance;
- caller ordering;
- raw private workstation path beyond the normalized authorized target identity required by the authorization owner.

Changing any freshness-critical accepted input changes the identity or invalidates the operation.

## 10. Authorization boundary

R7 does not create publication authorization.

The accepted authorization validator remains authoritative. For current `auto-publish-authorization-1.0`, R7 must at minimum require:

```text
policy = AUTO_PUBLISH_AFTER_ALL_GATES
exact run ID
exact normalized target path
exact current target SHA-256
single_use = true
expires_after_run = true
consumed = false
status = APPROVED
owner-controlled authorized_by / approval_reference
```

R7 performs eligibility first and authorization validation immediately before byte publication.

The future implementation must use the accepted owner to persist the one-time consumed transition. If post-R6 rebaseline still has only a `consumed` field with no accepted persistence operation, R7 stops rather than inventing a second authorization store.

## 11. Freshness lifecycle

Freshness is rechecked at multiple boundaries because publication changes externally visible bytes.

### 11.1 Before eligibility

Validate accepted upstream records and candidate identity.

### 11.2 Immediately before authorization

Re-read candidate bytes and current target bytes through accepted safe file/hash owners. Reject stale candidate or target.

### 11.3 Immediately before replacement

After verified backup and temporary copy, re-hash candidate and confirm it remains equal to the eligibility hash. Recheck target remains at the authorized prehash.

### 11.4 Immediately after replacement

Re-hash target. It must exactly equal the candidate publication hash.

No old evidence may be "refreshed" by editing its stored hash after a mutation.

## 12. Normal publication sequence

The preferred runtime algorithm after Gate 0 resolves exact accepted owner APIs is:

1. validate all required upstream evidence and produce a deterministic eligibility snapshot;
2. snapshot and hash the exact immutable candidate bytes;
3. resolve exact authorized target and backup root using the accepted safe-path owner;
4. hash the current target and require the authorization's expected initial hash;
5. validate the exact unused publication authorization through the existing authorization owner;
6. persist a publication intent/checkpoint through the existing manifest/checkpoint owner before any target replacement;
7. create and verify a backup through the accepted backup owner; prove target source hash is stable across copy and equals backup hash;
8. copy candidate bytes to an exclusive temporary file in the target's same parent/same volume using the accepted file-safety owner;
9. flush/sync the temporary bytes as supported, hash them, and require exact equality with candidate hash;
10. re-hash candidate and target immediately before replacement; candidate must be unchanged and target must still equal authorized prehash;
11. atomically replace the target with the verified same-volume temporary file using the accepted file owner;
12. immediately re-hash the target and require exact candidate equality;
13. persist the deterministic publication result through the existing manifest/checkpoint owner;
14. record one-time authorization consumption through the accepted authorization/state owner;
15. finalize the existing run/checkpoint state as published;
16. return validated publication evidence only.

R7 must not invoke an AutoCAD `SAVE` command to implement this sequence.

## 13. Same-hash replay and collision policy

### 13.1 Same-hash replay

If, after exact authorization validation:

```text
current target SHA == authorized expected initial SHA == eligible candidate SHA
```

then the desired bytes are already present.

The adapter returns an idempotent result such as:

```text
ALREADY_PUBLISHED_SAME_HASH
```

without copying/replacing target bytes.

It still records the deterministic publication result and consumes the one-time authorization through the accepted owner. Otherwise the same permission could be reused for a later unrelated operation.

### 13.2 Conflicting target contents

If current target SHA does not equal the authorization's expected initial SHA, fail closed before backup/replacement with a categorical target-mismatch error.

Do not overwrite a foreign or concurrently changed target even when candidate evidence is otherwise valid.

### 13.3 Candidate equals target path

Candidate and target must be distinct path/file identities. Publishing may never mean editing the authorized target in place.

## 14. Atomicity, rollback, and recovery

R7 must be recoverable across process interruption without a second state store.

The existing manifest/checkpoint owner records a durable publication intent before the replacement boundary. Recovery classifies the observed target by exact hash.

### 14.1 Crash before target replacement

If target still equals the authorized prehash, no replacement landed. The accepted owner may clean verified temporary state and either retry the bounded attempt or stop according to the run policy. Authorization must not silently become a fresh unlimited permission.

### 14.2 Crash after replacement but before final record

If target equals the eligible candidate hash, the replacement landed. Recovery finalizes publication evidence and authorization consumption idempotently; it must not perform a second replacement.

### 14.3 Unexpected third hash

If target equals neither authorized prehash nor eligible candidate hash, publication enters fail-closed recovery.

Only the accepted verified-backup owner may restore the exact backup. R7 must not guess which file is authoritative.

### 14.4 Rollback failure

If verified restore cannot be proven, return a categorical rollback failure, preserve available evidence/backup for operator review, and do not mark publication accepted.

No unbounded retry loop is allowed.

## 15. Publication evidence record

R7 produces a deterministic, closed record suitable for R8 consumption and independent review.

Semantic fields should include, after exact rebaseline names are resolved:

```text
schema/policy version
publication_id
run identity
eligibility identity/hash
candidate revision identity
candidate SHA-256
source/base provenance refs
R5 verdict ref/hash
R6 result/no-repair ref/hash
engineering/human approval ref/hash
publication authorization identity/hash
normalized target identity
expected target prehash
observed target prehash
backup verification identity/hash
observed final target SHA-256
publication disposition
authorization consumption identity/state
manifest/checkpoint identity
recovery/rollback disposition when applicable
```

Allowed dispositions are closed and should distinguish at least:

```text
PUBLISHED
ALREADY_PUBLISHED_SAME_HASH
REFUSED
ROLLED_BACK
RECOVERY_REQUIRED
```

A `PUBLISHED` record means byte-level publication succeeded under exact accepted authorization. It still does not assert R4 `accepted/current` state.

## 16. Error model and privacy

R7 public failures are categorical and must not leak private paths, CAD contents, raw approval prose, provider output, credentials, or customer metadata.

Recommended stable categories:

```text
R7_UPSTREAM_STALE
R7_NOT_ELIGIBLE
R7_AUTHORIZATION_INVALID
R7_AUTHORIZATION_CONSUMED
R7_TARGET_MISMATCH
R7_TARGET_UNSAFE
R7_TARGET_MISSING
R7_CANDIDATE_UNSAFE
R7_CANDIDATE_CHANGED
R7_BACKUP_FAILED
R7_TEMPORARY_FAILED
R7_PUBLISH_FAILED
R7_ROLLBACK_FAILED
R7_RECOVERY_REQUIRED
R7_RECORD_INVALID
```

Detailed private diagnostic evidence may exist only in the accepted external run/evidence root according to existing privacy policy; it is not embedded in public exception text or Git fixtures.

## 17. Safe-path and file-authority rule

Exact base contains multiple strong path/reparse/atomicity implementations, but important helpers are currently private and scoped to their owners.

R7 therefore does **not** define a new path utility package in this design.

At the post-R6 rebaseline:

- if an accepted public safe-file/backup owner exists, R7 calls it;
- if the required helper remains private but clearly belongs to an existing owner, Master PO issues a bounded owner-extension task first;
- if implementing a safe path/backup policy would make R7 its own second file authority, STOP with `R7 REBASELINE REQUIRED`.

This constraint applies to symlink, junction, reparse, traversal, root containment, collision, exclusive-create, backup, restore, and atomic-replace semantics.

## 18. Provider/model and AutoCAD boundaries

R7 has no model/provider operation.

R5 provider output, if any, reaches R7 only through the accepted validated R5 verdict evidence. A model cannot set target path, authorization, current target hash, publication state, or recovery action.

R7 also creates no AutoCAD/File IPC operation. The first synthetic acceptance proves file-level publication only.

If a later release requires post-publication AutoCAD reopen/plot/native verification, that gate must be separately issued and delegated to the accepted existing read-only AutoCAD evidence owner. It cannot be implemented as an R7 transport extension.

## 19. Compatibility and migration

### 19.1 Historical fidelity path

`fidelity-promote` and `fidelity-mechanical-review` retain their current private review semantics. R7 does not modify them merely to create final publishing.

### 19.2 Auto-publish authorization

R7 reuses the accepted authorization owner. Current v1 replacement-only semantics remain unchanged. Supporting an absent target requires explicit versioned owner extension before R7.

### 19.3 Manifest/checkpoint

R7 adds no new store. Publication intent/result/recovery information is bound through the accepted run/checkpoint owner after rebaseline.

### 19.4 Visual evidence

Existing evidence packages remain immutable inputs. R7 references their accepted identities; it does not rewrite evidence packages.

### 19.5 Revision lineage

R4 remains the only candidate/current/accepted lineage authority. R7 returns publication evidence for R4/R8 consumers but does not mutate lineage.

### 19.6 Rollback

Rollback of R7 runtime code must not require data migration. Reverting the thin adapter leaves existing fidelity, authorization, evidence, manifest, revision, repair, and AutoCAD owners intact.

## 20. Proposed public surface after rebaseline

Subject to exact symbol conflicts found at Gate 0, the preferred thin adapter surface is:

```python
class VerifiedPublicationError(ValueError):
    """Categorical R7 failure without raw private path/content leakage."""


def evaluate_publication_eligibility(
    *,
    upstream_context: object,
) -> dict[str, object]:
    """Return one deterministic eligibility snapshot from accepted upstream evidence."""


def verified_publication_id(
    eligibility: object,
    authorization: object,
) -> str:
    """Return the existing canonical-hash identity for one exact attempt."""


def publish_verified_candidate(
    *,
    upstream_context: object,
    authorization: object,
    candidate_path: Path,
    target_path: Path,
    run_root: Path,
) -> dict[str, object]:
    """Publish exact candidate bytes through accepted authorization/file/store owners."""


def recover_verified_publication(
    *,
    publication_id: str,
    upstream_context: object,
    authorization: object,
    run_root: Path,
) -> dict[str, object]:
    """Classify and finish/rollback one durable incomplete publication attempt."""
```

`upstream_context` is an R7 orchestration parameter name only. It is not an invented R4/R5/R6 contract. The runtime Issue must bind it to exact accepted validators and fields.

Preferred new core paths, only if Gate 0 proves no safer existing adjacent extension seam:

```text
cad_agent/verified_publication.py
tests/test_cad_agent_verified_publication.py
```

A later CLI integration may modify only the existing CLI owner plus its existing test owner under a separate bounded task.

## 21. Runtime acceptance principles

Every future R7 runtime task must:

- have exactly one named writer;
- use an exact post-R6 issuance SHA;
- use an exact CREATE/MODIFY allowlist of no more than two paths unless Master PO explicitly amends it;
- begin with meaningful RED in tests before production changes;
- use synthetic files and fake/injected owner seams first;
- avoid private/customer CAD;
- avoid live AutoCAD and real provider/model calls in initial RED/GREEN;
- run focused regression, architecture, reuse, Ruff, diff, canonical verifier, and hosted current-main synthetic gates;
- report `PASS`, `FAIL`, `SKIP`, and `NOT RUN` truthfully;
- stop on a required third authority/store/transport/path owner.

## 22. Adversarial acceptance matrix

The runtime plan must cover at least these cases:

### Authority separation

- visual PASS without exact publication authorization;
- provider/model text claiming publication permission;
- caller-minted eligibility/approval hash;
- R7 attempting to select/promote a revision;
- R7 attempting to consume repair operations;
- authorization issued for another run/candidate/target;
- authorization already consumed or expired.

### Freshness

- candidate changes after eligibility;
- R4 currentness changes after eligibility;
- R5 verdict becomes stale;
- R6/second-review evidence changes;
- engineering approval changes/expires;
- target changes between authorization and replace;
- candidate changes during backup/temp copy window.

### File/path safety

- missing target under v1 authorization;
- wrong extension;
- target outside authorized identity/root policy;
- candidate equals target;
- symlink/junction/reparse in candidate/target/backup/temp ancestry;
- path traversal/alias/case normalization attack;
- temporary collision;
- backup collision;
- target is directory/non-regular file;
- backup root aliases target.

### Atomicity and recovery

- backup copy mismatch;
- candidate temp hash mismatch;
- interruption before replace;
- interruption after replace before result persistence;
- interruption after result persistence before authorization consumption;
- final target hash mismatch;
- same-hash replay;
- conflicting third target hash;
- restore failure;
- cleanup failure;
- duplicate recovery call.

### Privacy and ownership

- raw path/customer text in categorical failure;
- accidental import of model/provider/AutoCAD/repair/parser code;
- second canonical hash implementation;
- second manifest/checkpoint/publication store;
- second approval validator or authorization issuer.

## 23. Verification and reviewer domains

Initial runtime verification after each bounded task:

```text
focused R7 tests
existing auto-publish authorization policy tests
existing fidelity promotion/mechanical-review regression tests
manifest/checkpoint tests affected by integration
R4/R5/R6 accepted regression tests named at rebaseline
architecture boundary checker
reuse inventory checker
Ruff
both git diff checks
canonical scripts/verify.ps1 -SkipAutoCADDotNet
hosted tests
hosted reuse-declaration
current-main synthetic merge evidence
```

Truthful initial gates:

```text
private/customer CAD: NOT RUN
real provider/model/auth execution: NOT RUN
AutoCAD Mechanical live: NOT RUN
AutoCAD .NET live gate: NOT RUN when explicitly skipped
```

Independent review pairing:

1. **Publication security reviewer** — authorization, path/reparse, backup, atomic replace, crash recovery, consumption, privacy.
2. **Integration/revision authority reviewer** — R4/R5/R6/approval freshness, eligible/authorized/published/current separation, manifest ownership, R8 handoff.

Neither reviewer merges or broadens runtime scope.

## 24. Overlap and dependency matrix

| Lane | R7 dependency | R7 overlap rule |
|---|---|---|
| R1/R2 | source/base provenance | consume final accepted evidence only |
| R3 #134 | component/view provenance | moving now; do not name API until accepted |
| R4 #133 | selected candidate/current lineage | moving now; no R7 revision writes |
| R5 PR #138 | final visual verdict | DRAFT/unmerged; no R5 edits or assumptions |
| R6 #136 | repair/second-review state | moving now; no repair ownership |
| Wave 1A #113 | not a direct R7 provider dependency | R7 must not call worker/provider at all |
| fidelity promotion | compatibility predecessor | preserve private review-only semantics |
| visual contracts | authorization validator | reuse; no second validator |
| manifest/checkpoint | durable run state | reuse/owner extension only |
| live/file safety | backup/restore/safe path | reuse/owner extension only |
| R8 | consumes verified publication evidence | no pilot selection/rollout in R7 |

## 25. STOP conditions

Stop planning/runtime progression and report the exact applicable reason when:

- accepted evidence no longer supports thin-adapter scope;
- publication execution is already completely owned by an accepted post-baseline owner and R7 would duplicate it;
- safe path or verified backup requires a second R7 file authority;
- authorization consumption cannot be persisted by an accepted owner;
- R7 would need to mint approval or revision/current state;
- publication needs new AutoCAD/File IPC mutation;
- publication needs a model/provider decision;
- target-create semantics require weakening `auto-publish-authorization-1.0` without an owner extension;
- a future task requires a third path without Master PO amendment;
- an active writer overlaps the issued allowlist;
- private/customer data is required for initial acceptance.

Before runtime issuance, unresolved owner/symbol conditions return:

```text
R7 REBASELINE REQUIRED
```

If a future accepted architecture contradicts the scope resolution itself, return:

```text
R7 SCOPE GAP — MASTER PO DECISION REQUIRED
```

## 26. R8 handoff

R7's downstream output is verified publication evidence only.

R8 may use that evidence to select or execute a separately authorized synthetic/real pilot, but R7 does not own:

- pilot/customer selection;
- rollout percentage;
- monitoring/telemetry policy;
- private-data authorization;
- acceptance criteria for deployment;
- rollback across multiple pilot runs.

This keeps publication mechanics and rollout authority separate.

## 27. Planning-only conclusion

Issue #140 authorizes only this design and its paired implementation plan.

No runtime, test, workflow, dependency, schema, contract, R5, or R8 file is changed by this planning lane.

The future runtime remains blocked until all required upstream owners are accepted and Master PO performs the mandatory fresh R7 rebaseline.