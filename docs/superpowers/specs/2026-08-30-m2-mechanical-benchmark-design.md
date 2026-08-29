# M2 Mechanical Benchmark Design

Date: 2026-08-30  
Status: approved for execution under the active M2 benchmark goal  
Approval basis: active user goal continuation and the reviewed M2 design boundary  
Applies to: representative, read-only AutoCAD Mechanical benchmark evidence only  
Base SHA: `ffde4673be48f85a7fd4c0a10b9b35000c710e16`

## Decision

Add a stateless M2 benchmark record and a disposable live test harness around
the existing DXF builder, headless reviewer, `FileIPCLiveMCPClient`,
`DotNetIPCClient`, and live reviewer. The benchmark produces one JSON evidence
record outside Git; it does not introduce a database, telemetry service,
background worker, new transport, dispatcher, or production repair path.

The benchmark is a quality gate for the existing DRAFT_REFERENCE Mechanical
review path. It is not an authoritative drawing setup acceptance and it does
not promote the image/PDF path beyond `DRAFT_REFERENCE`.

## Evidence and reuse dossier

| Capability | Existing owner | Decision | Evidence used |
|---|---|---|---|
| deterministic staged DXF and BuildResult | `dxf_builder_lib.builder.build_dxf` | `REUSE_AS_IS` | exact handles, written geometry, components, native dimensions |
| headless translation review | `dxf_builder_lib.reviewer.review_dxf` | `REUSE_AS_IS` | `ReviewResult` primitive/component/dimension counts and mismatches |
| live semantic review | `mcp_integration_lib.reviewer2.review_dxf_live` | `REUSE_AS_IS` | structural, geometry, dimension counts, mismatch and degraded flags |
| AutoCAD/FileIPC execution | `FileIPCLiveMCPClient`, `DotNetIPCClient` | `REUSE_AS_IS` | open/list/get, health/BOM, close-without-save, result identity |
| setup/profile contracts | `cad_agent.drawing_contracts`, `cad_agent.drawing_setup` | `REUSE_AS_IS` | profile/setup identity is recorded; no new authoritative profile is invented |
| benchmark record and aggregate oracle | new stateless M2 evidence helper | `EXTEND_WITH_TEST` | closed JSON shape, field presence, comparable-epoch and false-green checks |
| `observe_drawing` / `query_entities` façades | none on current main | `SPIKE_ONLY` | implement only after measured payload/context evidence demonstrates need |

The existing BOM smoke fixture is useful for component discovery but is not
enough for M2 because it has no native dimension and does not retain headless
review counts. The new fixture extends the test boundary only: it builds a
deterministic disposable DXF from existing IR/builder APIs containing at least
one LINE, one CIRCLE, one TEXT, one attributed component INSERT, and one
confirmed native DIMENSION. Its exact input and staged-output SHA-256 values
are recorded per epoch.

No customer drawing, including `BVTL.dwg`, is used as a benchmark fixture or
modified by this slice.

## Benchmark profile and setup boundary

The benchmark profile is a non-authoritative configuration identity:

```json
{
  "profile_id": "M2_MECHANICAL_REVIEW_V1",
  "release_state": "DRAFT_REFERENCE",
  "autocad_product": "AutoCAD Mechanical 2027",
  "model_units": "mm",
  "model_scale": "1:1",
  "fixture_kind": "disposable_generated_dxf",
  "setup_audit": "NOT_REQUIRED_FOR_DRAFT_REFERENCE_REVIEW"
}
```

The record also captures the plugin health version and a redacted IPC-root
identity, but never stores tokens, private drawing bytes, or customer paths.
`SETUP_VERIFIED` remains a separate owner-approved Drawing Setup gate. If a
future run needs that gate, it must supply an independently approved profile,
template manifest, setup plan, and read-only audit; this benchmark does not
manufacture those approvals.

## Record contract

The repository owns the closed contract
`m2-mechanical-benchmark-record-1.0`. The artifact is written outside the
repository and contains:

- benchmark id, current-main SHA, profile identity, fixture identity, and
  environment facts;
- one `epoch` object per disposable run with UTC start/end and wall-clock
  seconds;
- `human_interventions` as an integer plus an event list. Manual NETLOAD is an
  explicit event; missing capture is invalid for a comparable epoch;
- exact source/input and staged-DXF SHA-256 values before and after the run;
- headless status and primitive/component/dimension checked and defect counts;
- live status and structural/geometry/dimension checked and defect counts;
- `geometry_degraded`, warning/mismatch details, and categorical transport or
  result-identity failures;
- repair attempts, stale-evidence refusals, wrong-target refusals, close
  without save, IPC-artifact cleanup, and source-unchanged results;
- aggregate accepted/comparable epoch counts and `success_rate` only when the
  numerator and denominator are both explicit.

Unknown fields, invalid SHA values, negative counts, missing mandatory fields,
and `NOT_CAPTURED` values in a comparable epoch fail closed. A record may
retain incomplete/non-comparable epochs for diagnosis, but they never enter
the success-rate denominator.

## Acceptance oracle

An epoch is `accepted_comparable=true` only when all of these are true:

1. its `main_sha`, profile id/revision, fixture id, input SHA, and staged-DXF
   SHA are exact and stable;
2. the headless report is present, `PASS`, and has explicit primitive,
   component, and dimension defect counts;
3. live review returns semantic `PASS`, checks at least one structural entity,
   one geometry entity, and one native dimension, with zero defects and no
   geometry degradation;
4. human intervention count/event list is captured, even when the count is
   zero; manual NETLOAD is recorded rather than hidden;
5. transport/result-identity failures are classified, source and staged-DXF
   before/after identities are unchanged, no repair or save occurs, and the
   disposable document closes without saving;
6. the stale-evidence and wrong-target negative probes are exercised and
   refused without mutation; and
7. owned request/result artifacts are cleaned up and the disposable fixture
   directory passes its release/integrity check.

The benchmark is `REPRESENTATIVE` only after at least three comparable,
successful epochs run across at least two fresh AutoCAD sessions. Before that,
the record status is `BASELINE_ONLY` or `NOT_REPRESENTATIVE`; a positive 1/1
smoke is never generalized.

Failure evidence is useful even when an epoch is not comparable: transport
timeouts, invalid result identity, stale evidence, wrong target, headless
defects, live semantic mismatches, and cleanup failures are each retained in
their own category. `SKIP` and `NOT_RUN` remain explicit and are never
converted to success.

## Human and safety boundary

The live test is operator-assisted only for loading the already approved DLL
through the existing manual NETLOAD workflow. It never automates NETLOAD,
changes `SECURELOAD`, saves a customer drawing, repairs a production drawing,
or overwrites an accepted artifact. The benchmark opens generated disposable
DXFs, performs read-only health/review/BOM/semantic checks, closes without
saving, verifies source identity, and removes only its exact disposable test
directory after release verification.

## MECH-1 decision rule

M2 first measures the current owner path. If the evidence shows that callers
repeatedly transfer large entity payloads or cannot cheaply select the active
drawing/entity subset, add only a thin read-only façade with the following
shape:

```text
observe_drawing(path, fields) -> bounded drawing identity/setup summary
query_entities(path, selector, fields) -> bounded entity summaries
```

The façade must delegate to existing FileIPC/.NET operations, preserve exact
path/hash/result binding, and have a causal RED test showing the measured
coverage or token/context problem. Without that evidence, no façade is added.

## Verification and completion

Focused offline contract/fixture tests run first, followed by the opt-in live
benchmark when AutoCAD/FileIPC prerequisites are present. The authoritative
`.\scripts\verify.ps1` run is required before claiming completion. The
`autocad_mechanical` gate is recorded as `PASS`, `SKIP`, or `NOT RUN` exactly;
an unavailable live environment cannot be reported as a pass. The final
implementation record updates `docs/STATUS.md` with exact run ids, hashes,
epoch counts, and gate state.
