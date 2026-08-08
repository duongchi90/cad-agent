# R7 Verified Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Planning only. Issue #140 authorizes no R7 runtime implementation and no R8 pilot work.

**Planning date:** 2026-08-09

**Planning base:** `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

**Goal:** Implement the smallest verified-publication adapter that composes already-accepted R4/R5/R6/approval evidence with the existing publication authorization, safe-file/backup, manifest/checkpoint, and canonical-hash owners to atomically publish one existing authorized DWG target without creating a second publisher or authority.

**Architecture:** R7 is orchestration only. A thin `cad_agent` adapter evaluates eligibility from accepted upstream owner snapshots, validates the existing one-time auto-publish authorization, delegates all file safety/backup/atomic-replace operations to one accepted existing file owner, delegates intent/result/consumption persistence to accepted existing state owners, and emits deterministic publication evidence. R4 remains revision/current authority; R5 remains visual-verdict authority; R6 remains repair/second-review authority; approval owners remain external; no provider or AutoCAD transport exists in R7.

**Tech Stack:** Python 3.11, existing `cad_agent.visual_contracts.require_auto_publish_authorized`, existing `cad_agent.drawing_contracts.canonical_json_sha256`, accepted R1-R6 validators after mandatory rebaseline, accepted manifest/checkpoint owner, accepted safe-file/verified-backup owner, pytest, Ruff, architecture/reuse checkers, `scripts/verify.ps1 -SkipAutoCADDotNet`, GitHub hosted `tests` and `reuse-declaration`. No new dependency.

## Global Constraints

- Authoritative design: `docs/superpowers/specs/2026-08-09-r7-verified-publisher-design.md`.
- Parent reuse-first design: `docs/superpowers/specs/2026-08-04-reuse-first-multisource-cad-reconstruction-design.md`.
- Reuse inventory classifies `verified-promotion` as `EXTEND_WITH_ADAPTER`.
- Preserve `cad_agent.fidelity.promote_fidelity_page()` and `fidelity-promote` as private review-only compatibility behavior; do not make them production publishers.
- Preserve `cad_agent.visual_contracts` as the publication-authorization validation owner.
- Preserve accepted R4 as the only candidate revision/current/accepted lineage owner.
- Preserve accepted R5 as the only independent visual-verdict owner.
- Preserve accepted R6 and existing headless/Mechanical owners as the repair/second-review owners.
- Preserve owner-controlled engineering/human approval; R7 issues no approval.
- Preserve existing manifest/checkpoint/resume ownership; R7 creates no store/database.
- Preserve one accepted safe-file/reparse/backup/atomic-replace owner; R7 contains no fallback file-security implementation.
- Preserve `cad_agent.drawing_contracts.canonical_json_sha256()` as the canonical JSON hash owner.
- Initial R7 publication is replacement-only for one existing `.dwg` target under accepted `auto-publish-authorization-1.0` or its exact rebaselined equivalent.
- Missing target is fail-closed; no zero hash, null hash, boolean, sentinel, or alternate caller switch may create absent-target permission.
- Source, base, accepted, and published input artifacts are never mutated in place.
- Candidate and target must be distinct file identities.
- R7 creates no SDK/App Server/CLI/MCP/HTTP/model/provider transport.
- R7 creates no AutoCAD/File IPC operation and invokes no AutoCAD save command.
- R7 creates no CAD parser, DXF builder, repair executor, visual comparator, evidence store, approval issuer, revision store, or publisher store.
- `eligible`, `authorized`, `published`, and R4 `accepted/current` are distinct states.
- Visual/model PASS alone never authorizes publication.
- Every runtime task is mandatory meaningful RED-first and forward-only.
- Every R7 runtime task has one exact writer and at most two changed paths unless Master PO explicitly amends it.
- Initial RED/GREEN uses synthetic files and fake/injected accepted-owner seams only.
- Private/customer CAD, real provider/model/auth execution, and live AutoCAD are `NOT RUN` unless separately authorized.
- `PASS`, `FAIL`, `SKIP`, and `NOT RUN` are reported truthfully.
- Moving R3 #134, R4 #133, R5 PR #138, R6 #136, and Wave 1A #113 symbols are not assumed by this planning document.

---

## 0. Mandatory post-R6 issuance rebaseline — no repository write

This gate occurs before Task 1. Master PO performs it against fresh accepted `main` and records the result in the runtime Issue.

### 0.1 Exact accepted owners to record

Record exact paths, symbols, field names, versions, tests, current-main SHA, and active writers for:

1. R1 source/fusion provenance identity used at publication;
2. R2 base-CAD provenance identity when reused base geometry is present;
3. R3 registry/scope identity when final publication evidence binds view/component provenance;
4. R4 candidate revision identity, selected/publishable/current semantics, candidate artifact SHA, lineage, and stale/superseded behavior;
5. R5 final visual-verdict validator, identity/hash, PASS semantics, and freshness rule;
6. R6 repair-result/second-review validator and the exact accepted representation of "no repair required";
7. engineering/human approval validator, exact candidate/run binding, freshness/expiry/consumption behavior;
8. publication-authorization version and `require_auto_publish_authorized` or accepted successor;
9. accepted one-time authorization-consumption persistence operation;
10. accepted manifest/checkpoint operations for durable publication intent, result, and recovery lookup;
11. one public safe-file snapshot/path-normalization/reparse owner;
12. one public verified-backup, restore, same-volume staging, and atomic-replace owner;
13. exact file-hash API used by that file owner;
14. `cad_agent.drawing_contracts.canonical_json_sha256()` or accepted canonical successor;
15. every active writer touching proposed R7 core paths.

### 0.2 Required semantic mapping

The runtime Issue maps the accepted owners to exactly these R7 semantic facts:

```text
run_identity
candidate_revision_identity
candidate_artifact_identity
candidate_sha256
candidate_publishable/current/fresh state
source/base provenance identities
registry/scope provenance identity when required
R5 final verdict identity/hash and state
R6 result/no-repair identity/hash and second-review state
engineering/human approval identity/hash and state
manifest/checkpoint identity
publication authorization identity/hash
exact normalized target identity
expected current target sha256
allowed backup root
one-time authorization consumption identity
```

These names are R7 semantic concepts, not guesses at moving R3-R6 field names.

### 0.3 Concrete production binding requirement

Before Task 1 is issued, Master PO must identify concrete accepted implementations for the following adapter callbacks. R7 tests use fakes; production must bind each callback to the recorded accepted owner, with no caller-defined fallback:

```python
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

class PublicationUpstreamBoundary(Protocol):
    def snapshot_for_publication(self, context: object) -> Mapping[str, object]: ...

class PublicationFileBoundary(Protocol):
    def snapshot_existing_dwg(self, path: Path) -> Mapping[str, object]: ...
    def create_verified_backup(
        self, target: Path, backup_root: Path, *, expected_sha256: str
    ) -> Mapping[str, object]: ...
    def stage_candidate_same_volume(
        self, candidate: Path, target: Path, *, expected_sha256: str
    ) -> Mapping[str, object]: ...
    def atomic_replace_verified(
        self,
        staged: Path,
        target: Path,
        *,
        expected_target_sha256: str,
        expected_candidate_sha256: str,
    ) -> Mapping[str, object]: ...
    def restore_verified_backup(
        self, backup: object, target: Path, *, expected_backup_sha256: str
    ) -> Mapping[str, object]: ...
    def cleanup_staged(self, staged: object) -> None: ...

class PublicationStateBoundary(Protocol):
    def write_publication_intent(self, intent: Mapping[str, object]) -> object: ...
    def read_publication_intent(self, publication_id: str) -> Mapping[str, object]: ...
    def write_publication_result(self, result: Mapping[str, object]) -> object: ...
    def consume_authorization(
        self, authorization_id: str, *, publication_id: str
    ) -> object: ...
    def mark_publication_complete(self, publication_id: str) -> object: ...
```

These Protocols are R7 adapter interfaces only. They do not authorize R7 to implement the underlying file/store/approval behaviors.

### 0.4 STOP before Task 1 with `R7 REBASELINE REQUIRED` when

- any required accepted owner/API cannot be named exactly;
- safe path/reparse, verified backup, restore, staging, or atomic replace would have to be implemented inside R7;
- authorization consumption has no accepted persistence owner;
- R4 cannot identify the exact already-selected publishable candidate;
- R5/R6/approval freshness cannot be proven deterministically;
- a new AutoCAD/provider/repair/revision/store authority appears necessary;
- an active writer overlaps `cad_agent/verified_publication.py` or `tests/test_cad_agent_verified_publication.py`.

If an existing owner merely lacks a public helper, issue a separate bounded owner-extension task first. Do not widen R7 core.

No repository mutation occurs in Gate 0.

---

## 1. Preferred R7 core ownership after Gate 0

If Gate 0 confirms no safer accepted adjacent extension seam, create exactly:

```text
cad_agent/verified_publication.py
tests/test_cad_agent_verified_publication.py
```

All four R7 core tasks below modify only these two paths after their first RED commit.

R7 core must not modify:

```text
cad_agent/fidelity.py
cad_agent/visual_contracts.py
cad_agent/visual_evidence.py
cad_agent/manifest.py
cad_agent/live.py
cad_agent/vision_handoff.py
agent_lib/*
dxf_builder_lib/*
mcp_integration_lib/*
autocad_plugin/*
contracts/*
```

If a dependency owner requires an extension, stop R7 and issue a separate owner-specific task with its own exact allowlist and tests.

---

## 2. R7 public surface

The R7 core public surface is:

```python
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

class VerifiedPublicationError(ValueError):
    code: str

class PublicationUpstreamBoundary(Protocol):
    def snapshot_for_publication(self, context: object) -> Mapping[str, object]: ...

class PublicationFileBoundary(Protocol):
    def snapshot_existing_dwg(self, path: Path) -> Mapping[str, object]: ...
    def create_verified_backup(
        self, target: Path, backup_root: Path, *, expected_sha256: str
    ) -> Mapping[str, object]: ...
    def stage_candidate_same_volume(
        self, candidate: Path, target: Path, *, expected_sha256: str
    ) -> Mapping[str, object]: ...
    def atomic_replace_verified(
        self,
        staged: Path,
        target: Path,
        *,
        expected_target_sha256: str,
        expected_candidate_sha256: str,
    ) -> Mapping[str, object]: ...
    def restore_verified_backup(
        self, backup: object, target: Path, *, expected_backup_sha256: str
    ) -> Mapping[str, object]: ...
    def cleanup_staged(self, staged: object) -> None: ...

class PublicationStateBoundary(Protocol):
    def write_publication_intent(self, intent: Mapping[str, object]) -> object: ...
    def read_publication_intent(self, publication_id: str) -> Mapping[str, object]: ...
    def write_publication_result(self, result: Mapping[str, object]) -> object: ...
    def consume_authorization(
        self, authorization_id: str, *, publication_id: str
    ) -> object: ...
    def mark_publication_complete(self, publication_id: str) -> object: ...


def evaluate_publication_eligibility(
    *,
    upstream_context: object,
    upstream_boundary: PublicationUpstreamBoundary,
) -> dict[str, object]: ...


def verified_publication_id(
    eligibility: Mapping[str, object],
    authorization: Mapping[str, object],
) -> str: ...


def publish_verified_candidate(
    *,
    upstream_context: object,
    authorization: Mapping[str, object],
    candidate_path: Path,
    target_path: Path,
    backup_root: Path,
    upstream_boundary: PublicationUpstreamBoundary,
    file_boundary: PublicationFileBoundary,
    state_boundary: PublicationStateBoundary,
) -> dict[str, object]: ...


def recover_verified_publication(
    *,
    publication_id: str,
    upstream_context: object,
    authorization: Mapping[str, object],
    target_path: Path,
    upstream_boundary: PublicationUpstreamBoundary,
    file_boundary: PublicationFileBoundary,
    state_boundary: PublicationStateBoundary,
) -> dict[str, object]: ...
```

`upstream_context` is an opaque orchestration argument. Only the accepted `PublicationUpstreamBoundary` named by Gate 0 may turn it into authoritative normalized facts.

The R7 module must not contain fallback implementations for the three Protocols.

---

### Task 1: Closed eligibility composition and deterministic identity

**Sole writer:** exact R7 writer named by the runtime Issue.

**Files:**
- Create: `tests/test_cad_agent_verified_publication.py` — first repository write and RED-only commit.
- Create: `cad_agent/verified_publication.py` — only after meaningful RED is captured and accepted.
- Third path: forbidden.

**Consumes:**
- concrete `PublicationUpstreamBoundary` mapped by Gate 0;
- `cad_agent.drawing_contracts.canonical_json_sha256()` or exact accepted successor.

**Produces:**
- `VerifiedPublicationError` with privacy-safe categorical `code`;
- `evaluate_publication_eligibility()`;
- `verified_publication_id()`;
- Protocol definitions used by later tasks.

**Normalized upstream snapshot:** Gate 0 maps accepted upstream owners to a closed R7-owned adapter snapshot with exactly these semantic fields:

```python
{
    "run_identity": "...",
    "candidate_revision_identity": "...",
    "candidate_artifact_identity": "...",
    "candidate_sha256": "<64 lowercase hex>",
    "candidate_publishable": True,
    "candidate_current": True,
    "candidate_stale": False,
    "source_base_provenance_sha256": "<64 lowercase hex>",
    "registry_scope_sha256": "<64 lowercase hex>",
    "visual_verdict": {
        "identity": "...",
        "sha256": "<64 lowercase hex>",
        "status": "PASS",
        "fresh": True,
    },
    "repair_review": {
        "identity": "...",
        "sha256": "<64 lowercase hex>",
        "status": "PASS" | "NOT_REQUIRED",
        "fresh": True,
    },
    "engineering_approval": {
        "identity": "...",
        "sha256": "<64 lowercase hex>",
        "status": "APPROVED",
        "fresh": True,
    },
    "manifest_checkpoint_sha256": "<64 lowercase hex>",
}
```

This is R7's closed adapter vocabulary, not an upstream API. The concrete boundary must validate upstream records through their accepted owners before returning it.

**Meaningful RED attack matrix:**

1. import fails because `cad_agent.verified_publication` is absent;
2. upstream boundary is called and caller mapping is never treated as authority directly;
3. missing/extra snapshot field fails closed;
4. malformed/non-lowercase SHA fails;
5. `candidate_publishable=False` fails `R7_NOT_ELIGIBLE`;
6. `candidate_current=False` or `candidate_stale=True` fails `R7_UPSTREAM_STALE`;
7. R5 `FAIL`, `NEEDS_HUMAN`, missing PASS, or `fresh=False` fails;
8. R6 state other than `PASS` or accepted `NOT_REQUIRED` fails; stale R6 fails;
9. engineering approval other than fresh `APPROVED` fails;
10. caller-injected `authorized`, `published`, `accepted`, `current_revision`, `target_path`, `provider_says_publish`, or repair operation is rejected as an extra field;
11. caller order differences produce identical eligibility identity;
12. changing any freshness-critical hash changes eligibility identity;
13. timestamp/path/PID/random UUID cannot enter deterministic eligibility identity;
14. `verified_publication_id()` delegates to existing canonical hash owner and changes on authorization identity/target-prehash binding;
15. public exception string contains only categorical code, not upstream private details;
16. static import scan rejects provider, AutoCAD, File IPC, DXF builder, repair executor, alternate JSON canonicalizer/hash implementation, filesystem write/store ownership.

- [ ] **Step 1: Write the RED-only test file**

Create only `tests/test_cad_agent_verified_publication.py`. Start with synthetic helpers and the missing-import/public-surface tests.

Use a fake accepted upstream boundary shaped like:

```python
class FakeUpstreamBoundary:
    def __init__(self, snapshot: dict[str, object]) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def snapshot_for_publication(self, context: object) -> dict[str, object]:
        self.calls += 1
        return copy.deepcopy(self.snapshot)
```

The test fixture contains only synthetic IDs and hashes (`"1" * 64`, etc.).

- [ ] **Step 2: Prove meaningful RED**

Run:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
```

Expected: FAIL because `cad_agent.verified_publication` / required public behavior does not exist. Environment/import failures unrelated to the missing R7 capability do not count.

Commit the RED-only test file before creating production code.

- [ ] **Step 3: Implement the minimal pure eligibility module**

Create only `cad_agent/verified_publication.py`.

Implementation rules:

```python
from cad_agent.drawing_contracts import canonical_json_sha256
```

- validate the exact closed normalized snapshot above;
- deep-copy caller/boundary mappings before returning/storing them;
- make `VerifiedPublicationError.__str__()` expose only `code`;
- set eligibility state exactly `ELIGIBLE` only after every required upstream gate is proven;
- compute `eligibility_sha256` via `canonical_json_sha256()` over stable accepted fields only;
- compute publication ID from validated eligibility plus validated authorization identity material only;
- do not import `hashlib` or implement another canonical JSON serializer;
- do not open files or write manifests in Task 1;
- do not let provider/model strings, paths, timestamps, or caller booleans become authority.

- [ ] **Step 4: Prove focused GREEN repeatedly**

Run the focused file five times:

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

Then:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/verified_publication.py tests/test_cad_agent_verified_publication.py
git diff --check
git diff --cached --check
```

- [ ] **Step 5: Run architecture/reuse ratchets and commit**

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Cumulative Task-1 write-set must remain exactly the two R7 core paths. Commit normally; no amend/rebase/squash/force-push.

**Independent reviewer:** integration/revision authority reviewer. Verify R4/R5/R6/approval remain external and `eligible != authorized != published != accepted/current`.

**STOP conditions:** new store, new approval validator, direct trust of caller context, direct import of moving R3-R6 symbols not recorded at Gate 0, or third path.

---

### Task 2: Existing authorization and safe target preflight

**Sole writer:** exact writer named by the runtime Issue.

**Files:**
- Modify: `tests/test_cad_agent_verified_publication.py` — RED first.
- Modify: `cad_agent/verified_publication.py` — only after meaningful RED.
- Third path: forbidden.

**Consumes:**
- Task-1 eligibility API;
- exact accepted `require_auto_publish_authorized()` owner recorded by Gate 0;
- concrete accepted `PublicationFileBoundary` implementation recorded by Gate 0.

**Produces:** publication preflight inside `publish_verified_candidate()` with no target write yet until every check succeeds.

**Meaningful RED attack matrix:**

1. no authorization means no file-boundary mutation method is called;
2. wrong run identity fails;
3. wrong target path binding fails;
4. target current SHA differs from authorization `expected_initial_sha256` and fails before backup;
5. consumed authorization fails;
6. expired/non-approved authorization fails through existing owner;
7. missing target fails `R7_TARGET_MISSING` under v1 authorization;
8. non-`.dwg` target fails before backup;
9. candidate and target resolve to the same accepted file identity and fail;
10. unsafe/symlink/junction/reparse/foreign target is rejected by the accepted file boundary and surfaced categorically;
11. unsafe candidate is rejected by the accepted file boundary;
12. backup root rejected by accepted owner prevents any target write;
13. candidate SHA differs from R4 eligibility candidate hash and fails `R7_CANDIDATE_CHANGED`;
14. a changed eligibility snapshot immediately before authorization fails stale;
15. same-hash replay still requires exact authorization before returning an idempotent disposition;
16. raw authorization exception/path details are not propagated.

- [ ] **Step 1: Add Task-2 RED tests only**

Extend the existing test file with fake file-boundary snapshots. A safe snapshot fixture is:

```python
{
    "identity": "FILE-TARGET-001",
    "normalized_identity": "TARGET-AUTHORIZED-001",
    "sha256": "a" * 64,
    "suffix": ".dwg",
    "regular_file": True,
    "safe": True,
}
```

The fake boundary must count calls to backup/stage/replace so tests can prove none occurs before successful preflight.

- [ ] **Step 2: Prove meaningful RED and commit RED-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
```

Expected: new preflight cases FAIL because Task-1 code lacks authorization/file checks. Existing Task-1 cases remain GREEN.

- [ ] **Step 3: Implement preflight only**

Modify `cad_agent/verified_publication.py`:

- call `evaluate_publication_eligibility()` fresh inside publication;
- snapshot candidate and target only through `PublicationFileBoundary`;
- never fall back to `Path.resolve()`, `os.path`, `shutil`, raw `open()`, or a local reparse implementation for authority;
- require candidate hash equals eligibility candidate hash;
- require existing target `.dwg`, safe regular file, and a distinct file identity;
- call the accepted `require_auto_publish_authorized()` using exact run/target/current-target-hash arguments mapped at Gate 0;
- translate known validation/file-owner failures to categorical R7 errors without raw messages;
- do not call backup/stage/replace until all preflight checks pass.

- [ ] **Step 4: Prove Task-2 GREEN + authorization regressions**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py tests/test_visual_supervisor_contract_policy.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/verified_publication.py tests/test_cad_agent_verified_publication.py
git diff --check
```

- [ ] **Step 5: Verify no duplicated file authority and commit**

Run a static test/grep assertion from the R7 test suite that rejects imports/uses of local `shutil.copy*`, `os.replace`, Win32 reparse APIs, `hashlib` canonicalization, AutoCAD, or provider transports in R7 core.

Commit only the two R7 core paths.

**Independent reviewer:** publication-security reviewer. Red-team authorization replay, path aliases, missing target, consumed auth, and candidate/target identity confusion.

**STOP conditions:** accepted file boundary cannot prove safe existing DWG identity; v1 absent-target behavior would need contract weakening; or R7 needs to implement path/reparse/backup primitives itself.

---

### Task 3: Verified backup, same-volume staging, atomic replace, and publication evidence

**Sole writer:** exact writer named by runtime Issue.

**Files:**
- Modify: `tests/test_cad_agent_verified_publication.py` — RED first.
- Modify: `cad_agent/verified_publication.py` — after meaningful RED.
- Third path: forbidden.

**Consumes:**
- Task-2 preflight;
- concrete accepted `PublicationFileBoundary` and `PublicationStateBoundary` recorded at Gate 0.

**Produces:** full normal publication and same-hash replay dispositions.

**Closed orchestration sequence:**

```text
fresh eligibility
-> safe candidate/target snapshots
-> exact authorization
-> durable publication intent
-> verified backup
-> same-volume staged candidate
-> candidate + target freshness recheck
-> atomic verified replace
-> final target hash equality
-> durable publication result
-> one-time authorization consumption
-> mark publication complete
```

**Meaningful RED attack matrix:**

1. state intent must be written before backup/replacement;
2. intent write failure prevents all file mutation;
3. backup evidence target prehash must equal authorized target hash;
4. backup hash mismatch fails `R7_BACKUP_FAILED` before staging/replace;
5. staged bytes hash mismatch fails before replace;
6. candidate changes after staging and before replace fails `R7_CANDIDATE_CHANGED`;
7. target changes after backup and before replace fails `R7_TARGET_MISMATCH`;
8. atomic replace result must prove observed final target hash equals candidate hash;
9. final target re-snapshot mismatch triggers recovery/rollback path, never PUBLISHED;
10. publication result persistence occurs only after verified target bytes;
11. authorization consumption occurs only after durable successful result (or idempotent same-hash result);
12. `mark_publication_complete()` occurs only after result + consumption succeed;
13. same-hash replay calls no backup/stage/replace but writes result, consumes authorization, and completes;
14. same-hash replay result is exactly `ALREADY_PUBLISHED_SAME_HASH`;
15. normal success result is exactly `PUBLISHED`;
16. cleanup of staged files is delegated and cannot overwrite target/result evidence;
17. cleanup failure after proven publish is recorded categorically through accepted state owner policy but does not fabricate a rollback;
18. public result contains deterministic hashes/identities, not temp/random path authority;
19. source/base/accepted input references are never passed to mutation methods.

- [ ] **Step 1: Add Task-3 RED-only state-machine tests**

Extend fakes to record an ordered call log, for example:

```python
[
    "upstream.snapshot",
    "file.snapshot_candidate",
    "file.snapshot_target",
    "state.intent",
    "file.backup",
    "file.stage",
    "file.snapshot_candidate",
    "file.snapshot_target",
    "file.replace",
    "file.snapshot_target",
    "state.result",
    "state.consume",
    "state.complete",
]
```

Tests assert ordering as well as failure boundaries.

- [ ] **Step 2: Prove meaningful RED and commit RED-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
```

Expected: new state-machine cases fail while Task-1/2 cases stay GREEN.

- [ ] **Step 3: Implement minimal orchestration without file primitives**

Modify only the R7 module:

- write an immutable/deterministic intent mapping through `state_boundary` before backup;
- call `create_verified_backup()` and validate only the closed evidence returned by the accepted owner;
- call `stage_candidate_same_volume()` and verify expected candidate hash evidence;
- re-snapshot candidate and target immediately before replace;
- call `atomic_replace_verified()` only when both remain fresh;
- re-snapshot target and require exact candidate SHA;
- write deterministic result through state owner;
- consume exact authorization through state owner;
- mark completion only after consumption succeeds;
- for same-hash replay skip byte mutation but still persist/consume/complete;
- on any failure, clear no existing authoritative result and never synthesize a successful disposition.

Do not implement `copy`, `fsync`, `rename`, reparse inspection, backup allocation, or restore inside R7.

- [ ] **Step 4: Prove focused + predecessor regression GREEN**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py tests/test_visual_supervisor_contract_policy.py tests/test_cad_agent_fidelity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/verified_publication.py tests/test_cad_agent_verified_publication.py
git diff --check
```

The fidelity regression proves `fidelity-promote` still stops at Mechanical review and remains non-publishing.

- [ ] **Step 5: Commit bounded Task-3 GREEN**

Inspect cumulative diff and imports. Commit only the two R7 core paths.

**Independent reviewers:** both publication-security and integration/revision reviewers.

**STOP conditions:** target publication requires AutoCAD save, result/consumption requires a second store, accepted backup owner cannot produce hash-bound evidence, or source/base/accepted artifact becomes a mutation target.

---

### Task 4: Crash recovery, rollback routing, and idempotent completion

**Sole writer:** exact writer named by runtime Issue.

**Files:**
- Modify: `tests/test_cad_agent_verified_publication.py` — RED first.
- Modify: `cad_agent/verified_publication.py` — after meaningful RED.
- Third path: forbidden.

**Consumes:**
- Task-3 deterministic intent/result shapes;
- accepted `PublicationFileBoundary` restore/snapshot operations;
- accepted `PublicationStateBoundary.read_publication_intent()` and persistence/consumption operations.

**Produces:** `recover_verified_publication()` and closed recovery dispositions.

**Recovery classification:**

```text
observed target hash == intent.expected_target_sha256
    -> replacement did not land

observed target hash == intent.candidate_sha256
    -> replacement landed; finish result/consumption idempotently

observed target hash is anything else
    -> third-hash conflict; accepted backup owner may restore only verified backup
```

**Meaningful RED attack matrix:**

1. unknown publication ID fails `R7_RECOVERY_REQUIRED` without guessing;
2. intent identity/hash must match fresh upstream/candidate/authorization context;
3. stale R4/R5/R6/approval context blocks recovery completion;
4. target still at authorized prehash returns bounded non-published disposition and performs no second replacement;
5. target at candidate hash finalizes exactly one result and one authorization consumption without another replace;
6. already-completed result recovery is idempotent;
7. third target hash cannot be called PUBLISHED;
8. restore is attempted only with verified backup evidence from intent/state owner;
9. restore result must prove target equals exact expected backup/prehash;
10. restore failure yields `R7_ROLLBACK_FAILED` and no completion;
11. recovery never selects a different R4 revision/candidate;
12. duplicate recovery call cannot consume authorization twice;
13. failure after result but before consumption resumes consumption only, not replacement;
14. failure after consumption but before complete marker finalizes complete marker only;
15. staged cleanup remains delegated and safe to repeat;
16. categorical errors do not expose raw target/backup paths or state payloads;
17. no unbounded retry loop exists.

- [ ] **Step 1: Write Task-4 RED-only crash-point tests**

Model explicit synthetic crash states by preloading fake state-boundary records for:

```text
INTENT_ONLY
BACKUP_READY
STAGED
REPLACED_NO_RESULT
RESULT_NO_CONSUMPTION
CONSUMED_NO_COMPLETE
COMPLETE
THIRD_HASH
```

Each test asserts exact boundary calls and final disposition/error.

- [ ] **Step 2: Prove meaningful RED and commit RED-only change**

```powershell
.\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
```

Expected: crash/recovery cases fail because `recover_verified_publication()` is absent/incomplete; prior tasks remain GREEN.

- [ ] **Step 3: Implement deterministic recovery classifier**

Modify only the R7 module:

- read durable intent through accepted state boundary;
- re-run fresh upstream eligibility before accepting recovery completion;
- validate authorization identity against intent;
- snapshot target through accepted file boundary;
- branch only on exact authorized prehash / candidate hash / third hash;
- never issue a second replace when candidate bytes are already target bytes;
- restore only through accepted verified-backup boundary and only from hash-bound evidence persisted with the intent;
- finish result/consumption/complete idempotently using state owner evidence;
- retain `promotion_safe=False`/equivalent non-success semantics for unresolved/rollback-failed cases according to accepted state owner vocabulary.

- [ ] **Step 4: Prove recovery + full R7 focused GREEN**

```powershell
1..5 | ForEach-Object {
  .\.venv-py311\Scripts\python.exe -m pytest tests/test_cad_agent_verified_publication.py -q -p no:cacheprovider
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

.\.venv-py311\Scripts\python.exe -m pytest tests/test_visual_supervisor_contract_policy.py tests/test_cad_agent_fidelity.py -q -p no:cacheprovider
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/verified_publication.py tests/test_cad_agent_verified_publication.py
git diff --check
git diff --cached --check
```

- [ ] **Step 5: Run architecture/reuse verification and commit**

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Commit only the two R7 core paths.

**Independent reviewer:** publication-security reviewer leads crash/rollback review; integration/revision reviewer independently checks no R4/R5/R6/approval authority is acquired during recovery.

**STOP conditions:** recovery requires choosing a candidate, changing R4 current/accepted state, mutating authorization storage directly, creating a retry scheduler, or adding a new store/path owner.

---

## 3. No automatic CLI widening in core R7

The accepted `fidelity-promote` CLI remains review-only and is not repurposed.

The first R7 runtime slice exposes the Python API above. Do **not** modify `cad_agent/cli.py` merely to satisfy the roadmap label.

After Tasks 1-4 are accepted, Master PO may issue a separate bounded CLI integration task only if the then-current product entry point requires it. That task must first map exact accepted R4/R5/R6/approval artifact inputs and cannot accept a caller-authored "eligible" boolean or unvalidated generic JSON as authority.

A future CLI task, if issued, is limited to:

```text
MODIFY cad_agent/cli.py
MODIFY tests/test_cad_agent_cli.py
```

It may call the accepted R7 public API only. It may not duplicate publication validation, file operations, backup, state, authorization, or recovery logic.

Because final upstream artifact shapes are currently moving, this planning document does not invent CLI argument names for them.

---

## 4. Required aggregate verification before an R7 runtime PR

Run all focused R7 tests plus the exact accepted upstream regression files recorded by Gate 0.

At minimum, if paths still exist unchanged at runtime issuance:

```powershell
.\.venv-py311\Scripts\python.exe -m pytest `
  tests/test_cad_agent_verified_publication.py `
  tests/test_visual_supervisor_contract_policy.py `
  tests/test_cad_agent_fidelity.py `
  tests/test_visual_evidence.py `
  -q -p no:cacheprovider
```

Then run exact R4/R5/R6/engineering-approval regression files named by Gate 0.

Run architecture/reuse gates:

```powershell
.\.venv-py311\Scripts\python.exe scripts/reuse_inventory.py check docs/superpowers/reuse/2026-08-04-reuse-inventory.json --repo-root .
.\.venv-py311\Scripts\python.exe scripts/check_architecture_boundaries.py check --repo-root . --baseline contracts/reuse-integration/architecture-boundaries.json
```

Run Ruff and diff checks:

```powershell
.\.venv-py311\Scripts\python.exe -m ruff check cad_agent/verified_publication.py tests/test_cad_agent_verified_publication.py
git diff --check
git diff --cached --check
```

Run canonical verifier:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -SkipAutoCADDotNet
```

Required truthful initial gates:

```text
private/customer CAD: NOT RUN
real provider/model/auth execution: NOT RUN
AutoCAD Mechanical live: NOT RUN
AutoCAD .NET live gate: NOT RUN when -SkipAutoCADDotNet is used
```

Unavailable-state probes may be `SKIP`; they are never counted as live acceptance.

---

## 5. Current-main synthetic and hosted policy

Before a runtime PR is declared final:

1. fresh-fetch current `main` for verification only; do not rebase/sync the task branch unless Master PO explicitly authorizes it;
2. prove the task branch remains forward-descended from its issuance SHA;
3. create/use the hosted PR current-main synthetic merge;
4. require hosted `tests` GREEN on that exact synthetic;
5. require hosted `reuse-declaration` GREEN on that exact final head/current-main PR;
6. record exact task head SHA, current-main SHA, synthetic SHA, workflow run numbers, test counts, Ruff result, diff result, and truthful NOT RUN/SKIP gates;
7. DRAFT PR stays DRAFT until independent reviewers return their verdicts;
8. writer stops repository writes after final hosted GREEN evidence is captured.

Any head movement after hosted evidence invalidates the final dossier and requires fresh hosted verification.

---

## 6. Independent reviewer pairing

### Publication-security reviewer

Attack:

- authorization forgery/replay/consumption;
- target/candidate/backup path aliasing;
- symlink/junction/reparse escapes;
- target prehash race;
- candidate mutation race;
- backup mismatch;
- stage/replace atomicity;
- crash point recovery;
- third-hash conflict;
- rollback failure;
- private path/content leakage;
- second file/publication/state owner.

Verdict is tied to exact task-head/current-main/synthetic triple.

### Integration/revision reviewer

Attack:

- R7 selecting or promoting an R4 revision;
- R5 visual PASS minting authorization;
- R6 result being skipped after repair;
- engineering approval missing/foreign/stale;
- source/base/registry provenance drift;
- manifest/checkpoint duplication;
- `eligible`, `authorized`, `published`, and `accepted/current` state collapse;
- R8 pilot authority leaking into R7.

Verdict is tied to exact task-head/current-main/synthetic triple.

Neither reviewer merges or expands R7 scope.

---

## 7. Migration, rollback, and compatibility

### Existing fidelity promotion

No semantic migration. `promote_fidelity_page()` remains `approved_for_mechanical_review`, and `review_promoted_fidelity_page()` remains read-only.

### Existing auto-publish authorization

No weakening. Current `auto-publish-authorization-1.0` remains replacement-only under R7 because it requires exact expected target hash. Missing-target publication requires a separately reviewed owner-version extension.

### Existing manifest/checkpoint

R7 stores no independent truth. Durable publication intent/result/recovery records are written through the accepted state boundary mapped by Gate 0.

### Existing safe-file/backup owners

R7 implements no alternate path/backup behavior. Rollback of R7 code leaves those owners unchanged.

### R4/R5/R6

R7 references accepted identities only. Reverting R7 cannot rewrite candidate lineage, verdict evidence, repair evidence, or approval state.

### R8

R7 returns verified publication evidence. R8 remains responsible for pilot selection, rollout, private-data authorization, and fleet/run-level rollback decisions.

---

## 8. Runtime STOP matrix

Stop immediately and report the applicable categorical condition when:

| Condition | Required action |
|---|---|
| Required R1-R6/approval symbol not accepted | `R7 REBASELINE REQUIRED` |
| No public accepted safe-file/backup/atomic-replace owner | Stop; issue bounded existing-owner extension first |
| No accepted authorization-consumption persistence | Stop; issue bounded existing-owner extension first |
| R7 would need new authorization schema semantics for absent target | Stop; version existing authorization owner first |
| R7 would need to select/promote/rollback R4 revision | Stop; return to R4 owner |
| R7 would need repair or second review | Stop; return to R6 owner |
| R7 would need visual/model/provider decision | Stop; return to R5/worker owner |
| R7 would need AutoCAD save/new IPC operation | Stop; separate owner task required |
| Third runtime path becomes necessary | Stop; Master PO amendment required |
| Source/base/accepted artifact would be mutated | Stop; unsafe scope |
| Private/customer CAD required for initial test | Stop; use synthetic fixture |
| Accepted architecture shows complete publisher already exists | `R7 SCOPE GAP — MASTER PO DECISION REQUIRED` before duplicating it |

---

## 9. Planning-to-runtime handoff

Master PO may issue Task 1 only after Gate 0 is complete and every concrete production boundary is named.

The preferred runtime sequence is:

```text
Gate 0 — fresh accepted owner mapping, no write
Task 1 — eligibility + deterministic identity
Task 2 — authorization + safe preflight
Task 3 — backup/stage/replace + durable publication evidence
Task 4 — recovery/rollback/idempotent completion
independent paired review
hosted current-main synthetic GREEN
runtime STOP WRITE
```

R7 runtime completion does not authorize R8.