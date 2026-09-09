# Drawing Setup Expectation Policy Contract Change V2

## Record status

- Status: approved design; implementation not started
- Approval date: 2026-09-09
- Supported scope: the M2 drawing-initialization `SETUP_VERIFIED` boundary only
- Base repository SHA: `2d320361e2146d0602aac6f226f5bffed5f931a5`
- SOL technical-clear evidence: [issue comment 5601271257](https://github.com/duongchi90/cad-agent/issues/412#issuecomment-5601271257)
- Human approval evidence: [issue comment 5601313049](https://github.com/duongchi90/cad-agent/issues/412#issuecomment-5601313049)

## Exact approval binding

This specification is authorized only for proposal body SHA-256:

`17ee02ea89d6fadce5148b730a8f62d302b032a29431cba6a3a33847b4e0da6d`

The approved proposal is [issue comment 5601256901](https://github.com/duongchi90/cad-agent/issues/412#issuecomment-5601256901), with identifier `CREATE_BOUNDED_DRAWING_SETUP_CONTRACT_CHANGE_PROPOSAL_V2` and revision `20260909.02`.

## Goal

Extend the existing Drawing Setup contract and evaluator with an optional,
hash-bound `expectation_policy` that distinguishes `GATING` from
`OBSERVATION_ONLY`, while ensuring that non-gating observations can never
produce a vacuous `SETUP_VERIFIED` result.

## In scope

- `cad_agent/drawing_contracts.py`
  - validate an optional policy on `drawing_setup_plan-1.0`;
  - allow only the approved field paths and modes;
  - allow `UNRESOLVED` or the explicitly empty observation shape only for
    `OBSERVATION_ONLY` paths;
  - validate the scoped evidence fields added by this change.
- `cad_agent/drawing_setup.py`
  - preserve the current no-policy evaluator behavior;
  - evaluate only `GATING` paths for conformance and blockers;
  - copy exact audit values for observation-only paths as
    `NOT_EVALUATED`/`NOT_ASSERTED`;
  - enforce the non-vacuous status rule in both evaluation and
    `require_setup_verified`.
- `tests/test_cad_agent_drawing_setup.py`
  - add red regressions for empty and mixed scopes;
  - retain and run legacy behavior tests.

## Out of scope

- AutoCAD plugin or FileIPC code, IPC transport, dispatcher, queue, daemon,
  registry, or new control plane.
- `cad_agent/cli.py` unless a focused test proves that accepting or emitting a
  policy requires a CLI change; the default plan must leave it unchanged.
- Source PDF, candidate geometry, disposable DWG, DWT, accepted drawings, or
  production CAD mutation.
- Fabricating scale/UCS, layer/style/layout, font, embedded-settings, or DWT
  lineage expectations.
- A second `drawing_setup_verify` invocation.

## Contract semantics

### Policy shape

The optional root-level `expectation_policy` on a `drawing_setup_plan-1.0`
has this exact shape:

```json
{
  "schema_version": "drawing-setup-expectation-policy-1.0",
  "default_mode": "GATING",
  "field_modes": {
    "variables.INSUNITS": "GATING"
  }
}
```

`default_mode` is `GATING`. `field_modes` may contain only these paths:

- `variables.INSUNITS`
- `variables.MEASUREMENT`
- `variables.LTSCALE`
- `variables.CELTSCALE`
- `variables.PSLTSCALE`
- `variables.MSLTSCALE`
- `variables.DIMASSOC`
- `variables.ANNOALLVISIBLE`
- `current_layer`
- `required_layers`
- `required_styles`
- `layouts`
- `font_policy`
- `embedded_settings`

Each mode is exactly `GATING` or `OBSERVATION_ONLY`. Unknown paths,
unknown modes, malformed policy objects, and policy hash mismatches are
contract errors. A missing policy means the legacy all-gating contract.

### Expected-value representation

- A `GATING` path keeps the current concrete type and current validation.
- A scalar observation-only path may use the exact marker `UNRESOLVED`.
- An observation-only collection may use its current empty JSON shape, such as
  `layouts: []`; an observation-only object may use the exact marker
  `UNRESOLVED` where the current contract expects a concrete object.
- The evaluator never converts an observed value into an expected value.
- The raw audit contract remains authoritative for the observed value and is
  still validated independently.

The `embedded_settings` path controls whether the existing template custom
property comparison is gating. When it is observation-only and the embedded
settings were not measured, the proposal/template hash is retained only as an
identity reference; no custom-property conformance claim or DWT lineage claim
is made.

### Evaluation and evidence

For a policy plan:

- `GATING` paths use the existing comparison and blocker vocabulary.
- `OBSERVATION_ONLY` paths are emitted with
  `comparison=NOT_EVALUATED` and `conformance=NOT_ASSERTED`; they never add a
  blocker and never enter `gating_paths`.
- Evidence includes `expectation_policy_sha256`, `verification_scope`,
  `gating_paths`, `evaluated_gating_paths`, `observation_only_paths`,
  `unresolved_paths`, `observation_records`, and
  `conformance_assertion`.
- Existing no-policy evidence keeps its current output and status semantics.

### Non-vacuous status rule

`SETUP_VERIFIED` is allowed for a policy plan only when all of the following
are true:

1. `gating_paths` is non-empty.
2. At least one approved `GATING` path was actually evaluated.
3. Every declared `GATING` path was evaluated and passed.
4. No `GATING` blocker exists.
5. Evidence has `verification_scope=GATING_ONLY` and
   `conformance_assertion=true`.

If `gating_paths` is empty, or if all M2 mandatory dimensions are only
`OBSERVATION_ONLY`/`UNRESOLVED`, the result is `NEEDS_REVIEW` with
`verification_reason=EMPTY_GATING_SCOPE`,
`verification_scope=NO_CONFORMANCE_ASSERTION`, and
`conformance_assertion=false`, even when the blocker list is empty. The
downstream `require_setup_verified` function rejects this evidence. No
fabricated value may be introduced to make the scope non-empty.

For a mixed policy, an observation-only mismatch is non-blocking and remains
`NOT_ASSERTED`; a gating mismatch produces `NEEDS_REVIEW` through the existing
blocker vocabulary.

## Compatibility and rollback

- A plan without `expectation_policy` follows the current strict contract and
  evaluator byte-for-byte in semantic behavior.
- The change is opt-in at the plan boundary and does not alter the audit
  operation.
- Rollback is the single bounded code change: revert the contract/evaluator
  changes and their tests; no drawing or external application state is
  changed.
- No migration of existing plans is required; old plans remain valid.

## Required acceptance evidence

- Red tests exist first for all-observation-only, empty gating scope, mixed
  gating/observation, downstream vacuous rejection, and legacy compatibility.
- Focused drawing setup tests pass.
- `scripts/verify.ps1` passes.
- `git diff --check` is clean and verification does not add unrelated status.
- Required AutoCAD/FileIPC smoke is recorded as `NOT RUN` unless the changed
  owner is explicitly exercised against the live session; no live mutation is
  part of this contract change.
