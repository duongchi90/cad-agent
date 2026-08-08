# R5 Visual Supervisor Adapter Design

Status: planning only — Issue #135 does not authorize runtime implementation.

Date: 2026-08-09

Planning base: `b217ebfd597260d7b59badc3ffbcfbe7b1139754`

Issue: `#135 — [Acceleration][Planning] R5 Visual Supervisor Adapter executable design and runtime plan`

Activation comment: `5227232182`

## 1. Decision summary

R5 adds exactly one missing orchestration capability: an **independent visual-verdict adapter** that consumes already-authoritative evidence and emits a closed, freshness-bound visual verdict.

R5 is not a new image pipeline, comparator, AutoCAD evidence exporter, provider transport, CAD truth owner, engineering-approval owner, repair planner/executor, candidate-revision owner, manifest store, or publisher.

The accepted runtime shape after all upstream gates are satisfied is:

```text
accepted R4 candidate identity and mutation state
+ accepted R3 component/view/region/sheet membership
+ confirmed/protected dimension and constraint evidence
+ VS-T2 deterministic geometry comparison evidence
+ VS-T3 fresh AutoCAD-native visual evidence
        |
        v
R5 request snapshot and freshness binding
        |
        v
existing vision_handoff + accepted official worker/provider seam
        |
        v
UNTRUSTED provider region observations
        |
        v
existing visual_contracts owner validates closed observation
        |
        v
R5 rechecks candidate/evidence freshness
        |
        v
deterministic region -> view -> sheet aggregation
        |
        v
existing visual_contracts owner validates final R5 verdict
        |
        v
visual evidence only
```

The final R5 output can be `PASS`, `FAIL`, or `NEEDS_HUMAN`, but **none of those values is engineering approval, revision promotion, repair authorization, or publication eligibility**.

## 2. Why the historical `visual_review-1.0` contract is not the R5 authority

The current `cad_agent.visual_contracts` owner already contains `visual-review-1.0`. That historical contract remains useful compatibility evidence, but its `FAIL` semantics require non-empty `repair_intent.change` and `repair_intent.preserve`.

Issue #135 explicitly forbids R5 from creating repair plans or repair-intent authority. Therefore R5 must not silently reinterpret `visual-review-1.0` as the new final R5 contract.

The migration decision is:

- keep `visual-review-1.0` valid for historical/current consumers that already use it;
- do not weaken or redefine its existing semantics;
- extend the **same existing `cad_agent.visual_contracts` authority** with R5-specific closed contracts whose payloads contain no repair-plan or mutation authority;
- keep R6 as the future consumer of validated R5 `FAIL` evidence and the owner of repair planning/execution routing according to its separately accepted design.

This is an extension of the existing contract authority, not a second visual-contract owner.

## 3. Reuse map and authority ownership

| Capability | Existing owner | R5 decision | R5 may do | R5 must not do |
|---|---|---|---|---|
| Visual contract validation | `cad_agent.visual_contracts` | `EXTEND_WITH_ADAPTER` | Add R5 closed contract validation in the existing owner | Add a parallel validator/contract registry inside the adapter |
| Historical `visual-review-1.0` | `cad_agent.visual_contracts` + `contracts/visual-supervisor` | `REUSE_AS_COMPATIBILITY_ONLY` | Continue validating legacy records | Treat legacy repair intent as R5 repair authority |
| Dimension observation | VS-T1 `primitive_ir_lib.dimension_observer` + `cad_agent.dimension_observer_run` | `REUSE_AS_IS` | Consume validated confirmed/unresolved/conflict evidence | Run OCR, parse dimensions, invent attachments or values |
| Dimension gate | `cad_agent.visual_contracts.require_dimension_gate_ready` | `REUSE_AS_IS` | Require accepted dimension readiness where the R5 scope needs it | Create a second dimension status policy |
| Deterministic comparator | VS-T2 `primitive_ir_lib.geometry_comparator` + `cad_agent.geometry_comparison_run` | `REUSE_AS_IS` | Consume closed comparison metrics/trend/evidence hashes | Re-align, recompute metrics, or turn one score into PASS |
| AutoCAD-native visual evidence | VS-T3 File IPC/.NET exporter + `cad_agent.visual_evidence` | `REUSE_AS_IS` | Consume freshly validated read-only evidence | Call AutoCAD through a new path or create another exporter |
| Evidence freshness/persistence | `cad_agent.visual_evidence` | `REUSE_AS_IS` | Verify exact evidence/candidate bindings through accepted APIs | Create a second evidence store or mutation-state authority |
| Vision handoff | `cad_agent.vision_handoff` | `REUSE_AS_IS` after rebaseline | Bind server-owned scope, protected constraints, schema, policy, and evidence | Put verdict/repair/publication authority into the handoff |
| Worker lifecycle/provider transport | accepted Wave 1A `agent_lib.codex_worker` + process owner | `REUSE_AS_IS` after acceptance | Invoke the accepted official worker seam only | Add SDK/App Server/CLI/MCP/third-party transport |
| Provider-observed effective policy attestation | final accepted Wave 1A Task 5 boundary | `REUSE_AS_IS` after #113 acceptance | Require the accepted attestation before provider work | Assume the moving #113 symbol/field shape |
| Canonical JSON/SHA | `cad_agent.drawing_contracts.canonical_json_sha256` | `REUSE_AS_IS` | Hash R5 deterministic records | Add another canonical serializer/hash owner |
| Component/view/region relationships | final accepted R3 | dependency | Consume stable identity/membership/criticality | Reconstruct a component/view registry |
| Candidate revision/current state | final accepted R4 | dependency | Consume candidate identity and latest mutation state | Mint/select/promote/rollback revisions |
| Manifest/checkpoint/resume | `cad_agent.manifest` and accepted orchestration owner | external owner | Reference existing identities when required | Create an R5 store or checkpoint authority |
| Engineering approval | existing owner-controlled approval boundaries | external owner | State explicitly that R5 is not approval | Issue/consume approval as visual PASS authority |
| Repair planning/execution | `agent_lib` advisory boundary, `dxf_builder_lib.repair`, AutoCAD repair/File IPC, future R6 | external owner | Emit evidence usable by later R6 | Create operations, mutation intent, or execute repair |
| Publication/promotion | existing promotion path and future R7 | external owner | Supply validated visual evidence as one input | Declare publish eligibility or publish |

## 4. R5 authority boundary

R5 owns only these responsibilities:

1. build one deterministic review request from already validated upstream identities;
2. minimize and bind the provider-visible evidence scope;
3. invoke the accepted independent worker/provider boundary;
4. treat every provider response as untrusted;
5. validate provider observations against the server-owned request and closed output schema;
6. recheck candidate and evidence freshness after provider completion;
7. aggregate region results deterministically into view, sheet, and overall visual verdicts;
8. emit one closed, hash-bound visual-verdict artifact.

R5 explicitly does not own:

```text
CAD geometry truth
engineering acceptance
source/base/accepted/published CAD mutation
candidate revision creation or selection
component/view identity creation
OCR or dimension interpretation
deterministic image comparison
AutoCAD render/measurement capture
provider process/transport implementation
repair planning or repair execution
approval issuance
promotion or rollback
publication eligibility or publication
```

Any runtime design requiring one of those authorities triggers `R5 REBASELINE REQUIRED` rather than widening R5.

## 5. Mandatory post-R4/Wave-1A rebaseline

No R5 runtime repository write may begin until Master PO records the exact accepted upstream map.

The runtime Issue must resolve, from then-current accepted `main`:

1. final R1 source/fusion evidence identities needed by R5;
2. final R2 exact-base provenance identities where a reviewed region depends on reused base geometry;
3. final R3 symbols and fields for component, view, region, sheet membership and criticality;
4. final R4 symbols and fields for candidate revision identity, candidate artifact SHA, latest mutation identity, lineage, and stale/current semantics;
5. final accepted Wave 1A official worker lifecycle symbols;
6. final accepted provider-observed effective instruction/policy/schema attestation symbols and evidence shape after #113;
7. accepted VS-T3 live prerequisite state required for the chosen R5 acceptance level;
8. current visual-contract/schema owner paths and current writer overlap;
9. current manifest/checkpoint owner and whether R5 needs only references or any later integration;
10. current open writer overlap on every proposed R5 runtime path.

The planning documents intentionally do not name moving R3, R4, or #113 runtime APIs.

Stop before the first R5 runtime write with `R5 REBASELINE REQUIRED` if any required accepted symbol or authority cannot be resolved without invention.

## 6. Input model

R5 consumes validated references, not arbitrary files or caller-authored truth.

A future R5 request must be bound semantically to:

```text
run identity
candidate revision identity
candidate drawing/artifact SHA-256
latest candidate mutation identity
component/view registry identity
review scope: region IDs -> view IDs -> sheet IDs
region criticality from accepted upstream authority
source/reference evidence identities
confirmed/protected dimension and constraint identities
VS-T2 geometry-comparison identities and hashes
VS-T3 visual-evidence package identities and hashes
server-owned provider/instruction/schema policy identity
```

Exact field names for R3/R4/Wave 1A are deferred to the mandatory rebaseline. R5 must not derive them from filenames, paths, timestamps, volatile CAD handles, or model prose.

### 6.1 Input readiness

R5 may invoke the provider only when the request scope is internally complete and all required upstream records validate.

Examples that fail before provider invocation:

- unknown or dangling region/view/sheet membership;
- candidate identity does not match the R4 accepted candidate record;
- stale R3/R4 dependency identity;
- VS-T3 evidence does not bind to the candidate/latest mutation state;
- required geometry comparison references are missing or foreign;
- a critical unresolved/conflicting dimension blocks the reviewed region;
- source/reference evidence is outside the accepted scope;
- provider policy/schema binding cannot be proven.

These are categorical input failures, not model questions.

## 7. Two-stage contract model under the existing `visual_contracts` owner

R5 needs two different trust stages and therefore two closed contract types in the existing Visual Supervisor contract owner.

### 7.1 `visual_supervisor_observation`

Purpose: validate the **untrusted provider candidate output** before it can influence a final verdict.

Proposed schema version:

```text
visual-supervisor-observation-1.0
```

The provider observation contains only server-request-bound region observations:

```text
schema_version
request_id
regions[]
  region_id
  verdict            PASS | FAIL | NEEDS_HUMAN
  severity           INFO | MINOR | MAJOR | CRITICAL
  confidence
  findings[]
    finding_id
    category
    feature
    severity
    description
    evidence_refs[]
  requested_next_evidence[]
```

It must not contain:

```text
overall verdict
view verdict
sheet verdict
region membership or criticality authority
repair_intent
repair operations
engineering approval
candidate revision state changes
publish/promotion fields
AutoCAD commands
provider policy overrides
new evidence paths not present in the server request
```

The observation validator requires every server-requested region exactly once and rejects extra, missing, duplicate, or foreign region/evidence references.

### 7.2 `visual_supervisor_verdict`

Purpose: validate the **server-final deterministic R5 evidence record** after freshness recheck and aggregation.

Proposed schema version:

```text
visual-supervisor-verdict-1.0
```

The final record contains at least:

```text
schema_version
verdict_id
request_id
run_id
candidate_revision_identity
candidate_sha256
latest_mutation_identity
registry_identity
request_sha256
provider_observation_sha256
provider_attestation_identity
regions[]
  region_id
  view_id
  sheet_id
  criticality
  evidence_refs[]
  verdict
  severity
  confidence
  finding_ids[]
views[]
  view_id
  region_ids[]
  verdict
sheets[]
  sheet_id
  view_ids[]
  verdict
overall_verdict       PASS | FAIL | NEEDS_HUMAN
finding_summary
```

Exact accepted upstream identity field names are substituted during the mandatory rebaseline without changing the authority model.

The final contract contains no repair intent, approval, mutation, revision promotion, rollback, or publication field.

## 8. Deterministic identities

R5 reuses `cad_agent.drawing_contracts.canonical_json_sha256()` as the sole canonical hash owner.

The request identity is the canonical SHA-256 of the normalized server-owned request material. Provider output does not supply or override the request ID.

The provider observation identity is the canonical SHA-256 of the validated observation mapping.

The final verdict identity is derived deterministically from canonical final record material excluding the self-hash field if one is used by the accepted implementation convention.

Identity material includes the candidate/latest-mutation/evidence/registry bindings. It excludes volatile absolute paths, timestamps, process IDs, CAD handles not already part of an authoritative provenance record, model prose ordering, and caller collection order.

Changing any freshness-critical input changes the request/verdict identity or invalidates the pending review.

## 9. Provider independence and trust model

The Visual Supervisor must not be the same generation-side authority evaluating its own output by an unbound shortcut.

Independence is enforced structurally:

- R5 uses a fresh, server-owned visual-review handoff/request identity;
- its allowed operations are review-only and contain no mutation operation;
- it runs through the accepted official worker/process boundary;
- provider candidate output is always untrusted until closed validation;
- the provider cannot set scope, criticality, R3/R4 identities, evidence hashes, policy, approval, or aggregation membership;
- provider-observed effective instruction sources, provider policy, model/config, sandbox/cwd, schema and transport evidence must match the accepted Wave 1A authority after #113 is accepted;
- no direct SDK, App Server, CLI, MCP, HTTP, or alternate transport is introduced by R5;
- timeout/cancel/cleanup semantics are inherited from the accepted worker owner.

A distinct model is not itself the authority boundary. The important requirement is an independent, server-bound review role/process/handoff that cannot reuse generation-side self-approval state.

## 10. Prompt and evidence minimization

The provider receives the minimum evidence needed for the requested regions.

Allowed provider-visible material is limited to bounded, server-selected artifacts and metadata already validated by accepted owners, for example:

- source/reference crop for the requested region;
- VS-T3 render crop or bounded render artifact reference;
- deterministic VS-T2 metrics and comparison artifact references;
- confirmed/protected dimension/constraint facts needed to interpret the region;
- stable component/view/region/sheet labels needed for review;
- explicit review criteria and closed output schema.

The provider does not receive:

- entire private/customer CAD merely for convenience;
- source/base/accepted/published CAD write access;
- unrelated project files;
- credentials or provider secrets in prompts;
- arbitrary absolute workstation paths;
- repair tools or AutoCAD mutation operations.

Initial R5 runtime tests use only synthetic data and fake/provider-independent worker responses. Real provider/model/auth and private/customer CAD remain `NOT RUN` until separately authorized.

## 11. Freshness lifecycle

Freshness is checked twice around provider execution.

### 11.1 Before provider work

The adapter validates and snapshots:

- accepted R4 candidate identity and current mutation state;
- all required VS-T3 evidence through the accepted freshness owner;
- VS-T2 comparison identity and mutation binding;
- R3 registry/scope identity;
- dimension/protected-constraint readiness;
- provider handoff/schema/policy identity.

### 11.2 After provider work and before final verdict

The adapter re-observes the authoritative candidate/latest-mutation and required evidence identities through the accepted owners.

Any change after capture invalidates the provider result. The adapter must not “refresh” hashes inside an old result.

Categorical failure:

```text
R5_EVIDENCE_STALE
```

No final verdict artifact is emitted from stale provider output.

## 12. Region -> view -> sheet aggregation

Provider observations are region-level. Membership and criticality come from accepted R3/R4/upstream records, never from the model.

Aggregation order is fixed:

```text
region -> view -> sheet -> overall visual verdict
```

For each parent scope, deterministic precedence is:

```text
FAIL > NEEDS_HUMAN > PASS
```

Rules:

1. every required child must appear exactly once;
2. any child `FAIL` makes its parent `FAIL`;
3. otherwise any child `NEEDS_HUMAN` makes its parent `NEEDS_HUMAN`;
4. only all-`PASS` children yield parent `PASS`;
5. a missing/duplicate/foreign child is invalid input, not an implicit PASS;
6. one critical-region `FAIL` necessarily fails its view, sheet, and overall visual verdict;
7. a whole-sheet/average similarity score is never allowed to override a region result;
8. a critical region blocked by unresolved/conflicting protected evidence cannot become `PASS`;
9. aggregation is pure and deterministic; the provider cannot supply parent verdicts.

This rule directly prevents a visually strong average score from hiding a critical local defect.

## 13. Relationship to deterministic metrics

R5 does not replace deterministic comparator policy.

VS-T2 metrics are evidence inputs and guardrails:

- failed alignment cannot be silently treated as a match;
- missing/extra/topology regressions remain explicit evidence;
- metric trend can support findings but does not independently mint visual PASS;
- a model statement cannot override malformed or stale deterministic evidence;
- an R5 `PASS` requires the accepted request policy to have no blocking deterministic condition for that region.

Exact metric thresholds, if any are needed in an accepted runtime profile, remain server-owned policy and must be issued explicitly. They are not model-selected.

## 14. Failure semantics

R5 fails closed with privacy-safe categorical errors. Raw provider/private exception text must not become public error authority.

Required categories include the semantic equivalents of:

```text
R5_REBASELINE_REQUIRED
R5_INPUT_INVALID
R5_INPUT_NOT_READY
R5_EVIDENCE_STALE
R5_WORKER_AUTHORITY_MISMATCH
R5_PROVIDER_FAILED
R5_PROVIDER_TIMEOUT
R5_PROVIDER_CANCELLED
R5_PROVIDER_OUTPUT_INVALID
R5_PROVIDER_ATTESTATION_GAP
R5_CLEANUP_FAILED
R5_AGGREGATION_INVALID
```

Exact public names may be locked in the runtime Issue after accepted upstream error vocabulary is rechecked. They must remain categorical and sanitized.

Provider failure, timeout, cancel, interrupt, missing terminal output, malformed output, partial region coverage, stale result, or failed cleanup produces **no authoritative final PASS**.

## 15. Visual verdict versus human/engineering approval

R5 `PASS` means only:

> The bounded visual-review evidence supplied for this exact candidate/latest-mutation identity satisfied the accepted R5 visual policy at the time of review.

It does not mean:

- engineering dimensions are approved;
- regulatory compliance is approved;
- a candidate revision is accepted/current;
- repair is authorized;
- publication is authorized.

Human or engineering approval remains a separate existing/future owner-controlled record. `NEEDS_HUMAN` specifically requests that external decision/evidence; it cannot create the approval itself.

## 16. Relationship to R6 and R7

### R6

R6 may consume a validated R5 `FAIL` record and its finding/evidence references. R5 never emits repair operations, target transforms, or executor commands.

### R7

R7 may consume a fresh R5 verdict as one publication/promotion input. R5 never computes final publisher eligibility and cannot call publication APIs.

The R5 verdict is therefore evidence, not an action authorization token.

## 17. Proposed public runtime surface

Subject to the mandatory rebaseline, the preferred R5 adapter surface is deliberately small:

```python
class VisualSupervisorAdapterError(ValueError):
    ...


def build_visual_supervisor_request(
    *,
    upstream_context: object,
    region_ids: object,
) -> dict[str, object]:
    ...


def validate_visual_supervisor_observation(
    observation: object,
    *,
    request: object,
    upstream_context: object,
) -> dict[str, object]:
    ...


def finalize_visual_supervisor_verdict(
    *,
    request: object,
    observation: object,
    upstream_context: object,
) -> dict[str, object]:
    ...


def visual_supervisor_verdict_sha256(verdict: object) -> str:
    ...
```

These are R5-owned orchestration names, not assumptions about R3/R4/#113. The runtime issue may rename them if accepted repository naming or ownership at rebaseline shows a safer extension seam.

The adapter must delegate closed contract validation to `cad_agent.visual_contracts`; it must not become a parallel schema registry.

## 18. Preferred minimal runtime ownership

After the post-R4/Wave-1A rebaseline, the preferred adapter slice is:

```text
cad_agent/visual_supervisor_adapter.py
tests/test_cad_agent_visual_supervisor_adapter.py
```

Existing visual-contract evolution remains in the existing owner and its existing tests/schemas, issued as separate two-path tasks so no task requires a third path.

No R5 runtime task should modify worker/process/provider transport files merely to integrate R5. If the accepted worker seam is insufficient, stop with `R5 REBASELINE REQUIRED` and issue an upstream worker task instead.

## 19. Runtime task decomposition principle

The future runtime plan separates:

1. R5 observation contract extension in the existing visual contract owner;
2. observation schema alignment;
3. final verdict contract extension/schema alignment;
4. the thin R5 adapter with fake/provider-independent tests;
5. only after all fake gates are GREEN, an optional separately authorized real-provider acceptance gate.

This keeps every writer bounded and makes it possible to reject one authority layer without accepting another.

## 20. Overlap and dependency matrix

| Lane | Current planning state at Issue #135 baseline | R5 rule |
|---|---|---|
| R1 Source Fusion | moving/acceptance dependency | consume only after accepted/merged |
| R2 Base CAD Adapter | moving/acceptance dependency | consume only after accepted/merged |
| R3 PR #134 | planning DRAFT / not runtime accepted | do not import or name its moving APIs |
| R4 Issue #133 | planning active / not runtime accepted | require semantic candidate/mutation seam only |
| Wave 1A PR #113 | DRAFT / moving | require final accepted provider-attestation seam; no current symbol lock |
| VS-T1 | accepted reusable evidence | no writer overlap; consume only |
| VS-T2 | accepted reusable evidence | no writer overlap; consume only |
| VS-T3 / Issue #29 | accepted exporter evidence | no exporter/File IPC write by R5 |
| Wave 1C live Issue #72 | operator/evidence lane | no repository overlap; live state must be reported truthfully |
| R6 Issue #136 planning | separate repair lane | R5 emits evidence only; no repair ownership |
| Existing promotion/publisher | external owner | no R5 write/authority |

A future R5 runtime issue must redo this matrix against then-current `main` and active writers.

## 21. STOP conditions

Stop and return `R5 REBASELINE REQUIRED` before widening scope if any of the following is true:

- accepted R3/R4/#113 symbols cannot be mapped exactly;
- R5 would need to parse CAD/source bytes itself;
- R5 would need to run OCR or compute geometry metrics itself;
- R5 would need a new AutoCAD/File IPC operation;
- R5 would need direct SDK/App Server/CLI/MCP transport;
- R5 would need a new evidence, manifest, checkpoint, or revision store;
- R5 would need to emit repair operations or execute repair;
- R5 would need to issue engineering approval;
- R5 would need to promote/rollback/select candidate revisions;
- R5 would need to decide publication eligibility;
- a third path is required for a bounded runtime task without explicit Master PO amendment;
- source/base/accepted/published CAD mutation becomes necessary;
- private/customer CAD is required for the first runtime RED/GREEN slice;
- provider-observed policy/schema/instruction attestation cannot be proven through the accepted worker owner.

## 22. Planning verification and non-authorization

Issue #135 planning acceptance requires:

- exactly the two authorized planning docs in the branch diff;
- no runtime, test, workflow, dependency, lock, schema, or contract file change in this planning PR;
- explicit reuse map for VS-T1/T2/T3, `visual_contracts`, `visual_evidence`, `vision_handoff`, worker/provider, manifest, repair, revision, and publisher owners;
- no moving R3/R4/#113 API invention;
- deterministic region -> view -> sheet aggregation and critical-region fail-closed policy;
- explicit separation of visual verdict from human/engineering approval;
- `git diff --check` and relevant docs/reuse/architecture checks through the supported verifier;
- hosted `tests` and `reuse-declaration` GREEN on the final PR synthetic;
- DRAFT PR then STOP WRITE.

This design authorizes no R5 runtime implementation, no real provider call, no AutoCAD execution, and no private/customer CAD use.