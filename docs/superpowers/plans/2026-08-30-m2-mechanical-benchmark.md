# M2 Mechanical Benchmark Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax.

**Goal:** Turn the existing one-epoch Mechanical smoke into a hash-bound, repeatable M2 benchmark record with explicit headless/live/transport/safety evidence and no benchmark subsystem.

**Architecture:** Add one stateless cad_agent.m2_benchmark contract/oracle that validates a closed JSON record and aggregates only comparable epochs. Add test-only deterministic fixture/live harness code that composes existing builder, reviewers, FileIPC/.NET clients, and disposable cleanup. No CLI, database, telemetry, new transport, AutoCAD operation, or repair owner is added.

**Tech Stack:** Windows, Python 3.11, pytest, JSON, ezdxf, existing dxf_builder_lib, mcp_integration_lib, AutoCAD Mechanical 2027, and scripts/verify.ps1.

**Spec:** docs/superpowers/specs/2026-08-30-m2-mechanical-benchmark-design.md

**Status:** baseline implementation and offline verification complete; representative live gate pending

**Base SHA:** ffde4673be48f85a7fd4c0a10b9b35000c710e16

**Evidence Head SHA:** eed11ea0b2d8d4d81c0b127e44337253d3e01eb1

**Verification command:** powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1

**Verification result:** `scripts/verify.ps1` exit `0` on the evidence head; offline, .NET managed, and dotnet IPC suites passed; real_data and AutoCAD live prerequisites remain explicit SKIP/NOT RUN. The evidence oracle also records human/environment/failure details, distinct source/staged hash pairs, and a separate M2 opt-in verifier marker.

**Required gates:** autocad_mechanical live benchmark is required for representative acceptance; real_data remains NOT RUN unless an approved private input is explicitly in scope. Missing prerequisites are recorded as SKIP or NOT RUN, never as pass.

## Global Constraints

- Base SHA: ffde4673be48f85a7fd4c0a10b9b35000c710e16.
- Schema version: m2-mechanical-benchmark-record-1.0.
- The benchmark remains DRAFT_REFERENCE; it never creates SETUP_VERIFIED evidence or authoritative output.
- Reuse build_dxf, review_dxf, review_dxf_live, FileIPCLiveMCPClient, DotNetIPCClient, write_build_evidence, load_build_evidence, and existing cleanup helpers.
- No customer drawing, including BVTL.dwg, enters Git or the fixture; all live files are disposable under C:\temp.
- Live actions are read-only health/review/BOM plus open and close-without-save; no repair, save, NETLOAD automation, SECURELOAD change, or production mutation.
- `main_sha` is the exact current-main lowercase 40-character Git commit SHA;
  fixture, source, staged-DXF, and file hash fields remain lowercase
  64-character SHA-256 values.
- NOT_CAPTURED, SKIP, and NOT_RUN are explicit non-success states; dimension_checked=0 and missing human-event capture cannot satisfy a comparable epoch.
- Success rate is successful_comparable_epochs / comparable_epochs, never an inference from enqueue/submission.
- REPRESENTATIVE requires at least three successful comparable epochs across at least two explicit AutoCAD session ids.
- Records are written outside the repository; do not modify scripts/verify.ps1 unless existing discovery demonstrably omits the new test root.

---

### Task 1: Closed record contract and aggregate oracle

**Files:**
- Create: contracts/benchmarks/m2-mechanical-benchmark-record.schema.json
- Create: cad_agent/m2_benchmark.py
- Create: tests/test_m2_benchmark.py

**Interfaces:**
- Produces M2_BENCHMARK_SCHEMA_VERSION, M2BenchmarkError, validate_m2_record(record: Mapping[str, object]) -> dict[str, object], new_m2_record(*, benchmark_id: str, main_sha: str, profile_id: str, profile_revision: str, fixture_id: str, fixture_input_sha256: str, staged_dxf_sha256: str) -> dict[str, object], append_m2_epoch(record: Mapping[str, object], epoch: Mapping[str, object]) -> dict[str, object], and aggregate_m2_epochs(epochs: Sequence[Mapping[str, object]]) -> dict[str, object].

- [x] Step 1: Write causal RED tests

Add a valid closed record fixture with one epoch containing exact main/profile/fixture identities, UTC timestamps, wall clock, human events, headless/live counts, transport arrays, stale/wrong-target counts, unchanged before/after hashes, cleanup, and accepted_comparable/success. Test valid acceptance and rejection of unknown keys, bad SHA/timestamp, negative or boolean counters, event-count mismatch, bad wall clock, NOT_CAPTURED/SKIP/NOT_RUN, dimension zero, missing negative probes, changed hashes, save/repair attempts, binding mismatch, and append mismatch. Test aggregate numerator/denominator, one epoch baseline, one-session non-representative, two-session representative, and no-comparable success_rate=None.

Use this exact aggregation expectation in the test:

    comparable = [e for e in epochs if e["accepted_comparable"]]
    successful = [e for e in comparable if e["success"]]
    representative = (
        len(successful) >= 3
        and len({e["session_id"] for e in successful}) >= 2
    )

- [x] Step 2: Run RED

    & .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py -q -p no:cacheprovider

Expected causal failure: the new module and schema are absent.

- [x] Step 3: Implement the closed schema and validator

Use additionalProperties=false for top-level, epoch, fixture, profile, human, headless, live, transport, negative-probe, mutation, cleanup, and aggregate objects. Validate lowercase 64-character SHA-256 values, RFC3339 UTC timestamps, finite non-negative wall-clock values, non-negative integer counters, status enums, and event count equal to the sum of event counts. Derive success from measured fields and reject a caller that sets it true while any oracle condition fails.

Implement these interfaces:

    def validate_m2_record(record: Mapping[str, object]) -> dict[str, object]:
        raise M2BenchmarkError("validator implementation required")

    def new_m2_record(*, benchmark_id: str, main_sha: str,
                      profile_id: str, profile_revision: str,
                      fixture_id: str, fixture_input_sha256: str,
                      staged_dxf_sha256: str) -> dict[str, object]:
        raise M2BenchmarkError("record factory implementation required")

    def append_m2_epoch(record: Mapping[str, object],
                        epoch: Mapping[str, object]) -> dict[str, object]:
        raise M2BenchmarkError("append implementation required")

    def aggregate_m2_epochs(
        epochs: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        raise M2BenchmarkError("aggregate implementation required")

new_m2_record starts with aggregate status NOT_RUN. append_m2_epoch validates the old record, requires exact base binding, appends without mutating the caller, and recomputes the aggregate. aggregate_m2_epochs returns comparable_epochs, successful_epochs, success_rate, representative, and status.

- [x] Step 4: Run GREEN and lint

    & .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py -q -p no:cacheprovider
    & .\.venv-py311\Scripts\python.exe -m ruff check cad_agent\m2_benchmark.py tests\test_m2_benchmark.py

Expected: all contract/oracle tests pass and the schema parses as JSON.

- [x] Step 5: Commit

    git add contracts\benchmarks\m2-mechanical-benchmark-record.schema.json cad_agent\m2_benchmark.py tests\test_m2_benchmark.py
    git commit -m "feat: add M2 benchmark record oracle"

---

### Task 2: Deterministic fixture and headless composition

**Files:**
- Create: tests/m2_benchmark_support.py
- Modify: tests/test_m2_benchmark.py

**Interfaces:**
- Produces M2Fixture with input_path, staged_dxf, build, headless, input_sha256, and staged_dxf_sha256; build_m2_fixture(root: Path) -> M2Fixture; and headless_metrics(fixture) -> dict.

- [x] Step 1: Write fixture tests

Call build_m2_fixture(tmp_path) and assert valid hashes, at least three primitives, one semantic component INSERT, one confirmed native DIMENSION, passing review_dxf, explicit primitive/component/dimension counts, build-evidence round-trip, and refusal when a copied staged DXF is changed.

- [x] Step 2: Run the fixture RED test

    & .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py -k fixture -q -p no:cacheprovider

Expected causal failure: tests.m2_benchmark_support and build_m2_fixture do not exist.

- [x] Step 3: Implement fixed fixture bytes

Build a fixed PrimitiveIRDocument: line-001 from (0, 0) to (100, 0), a fixed CIRCLE, a fixed TEXT, and one confirmed CrossValidation for the LINE. Use verified millimetre calibration and SemanticPart(part_type="thanh_ngang", primitive_ids=["line-001"], confidence=1.0). Serialize source IR with sorted keys and compact separators, then call:

    build = build_dxf(
        source,
        str(root / "staged.dxf"),
        semantic_doc=semantic,
        build_components=True,
        build_dimensions=True,
    )
    headless = review_dxf(build)

Write build evidence beside the DXF and compute hashes with sha256_file. Do not include timestamps, UUID ids, absolute paths, or random values in fixture bytes.

- [x] Step 4: Normalize and verify headless metrics

Map ReviewResult.checked_count, mismatches, component_checked_count, component_mismatches, dimension_checked_count, and dimension_mismatches to the record; preserve PASS/FAIL and never replace an absent review with zero. Run the Task 1 focused tests and Ruff.

- [x] Step 5: Commit

    git add tests\m2_benchmark_support.py tests\test_m2_benchmark.py
    git commit -m "test: add deterministic M2 benchmark fixture"

---

### Task 3: Opt-in one-epoch Mechanical harness

**Files:**
- Create: mcp_integration_lib/tests/test_m2_mechanical_benchmark_live.py
- Modify: tests/test_m2_benchmark.py

**Interfaces:**
- Consumes the Task 1-2 oracle/fixture and existing live clients, prerequisite and cleanup helpers.
- Produces one disposable epoch per invocation, appended to CAD_AGENT_M2_RECORD_PATH; repeated invocations with explicit session ids form the aggregate.

- [x] Step 1: Write harness-shape RED tests

Test human-event JSON parsing; missing capture becomes non-comparable rather than zero; stale build evidence increments stale_evidence_rejections; wrong-target identity increments wrong_target_rejections; timeout and MCPToolError retain operation/category; and an existing record from another main SHA is refused.

- [x] Step 2: Implement explicit prerequisites

Mark the live class pytest.mark.autocad_mechanical and reuse the existing core predicate. Require CAD_AGENT_M2_RECORD_PATH (absolute and outside the repository), CAD_AGENT_M2_SESSION_ID, and CAD_AGENT_M2_HUMAN_EVENTS_JSON for a comparable epoch. Missing values write non-comparable evidence and fail after persistence; they never silently become a pass. Never record tokens or complete customer paths.

- [x] Step 3: Implement the read-only epoch

Create one unique directory under C:\temp, build the fixture, capture monotonic/UTC start, exact current-main/profile/fixture hashes, and human events, then run headless review. Open only the staged DXF with existing FileIPC. Run .NET health and mechanical_bom, requiring exact drawing identity, success=true, changed=false, empty errors, and expected component/attribute evidence. Run review_dxf_live(build, legacy_client, open_drawing=False) and record structural, geometry, dimension, component, warning, mismatch, and degradation fields.

Exercise stale evidence with a copied evidence file and changed disposable DXF. Exercise wrong-target identity by opening a second disposable drawing and sending the first drawing's existing .NET-bound request, then reopen the intended staged DXF. Never call repair, save, save-as, or entity mutation; derive repair/save counts from a harness call ledger.

In finally, close the exact disposable document with close_disposable(disposable=True, save_changes=False), verify before/after hashes, request/result cleanup, file release, and exact-directory cleanup. Persist with existing atomic write_live_report; re-raise a pytest failure after persistence when the epoch is not successful. Capture request/result byte sizes and the number of repeated entity queries so Task 4 can make a measured MECH-1 decision; absence of a measured payload/context problem is recorded as MECH-1 NOT JUSTIFIED and adds no façade.

- [x] Step 4: Run offline/unavailable-state checks

    & .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py mcp_integration_lib\tests\test_dotnet_ipc_live.py -q -p no:cacheprovider

Expected: offline tests pass and the opt-in live class is explicitly skipped when AutoCAD/FileIPC prerequisites are absent. Skip is not live acceptance.

- [ ] Step 5: Run live epochs when the operator session is ready

    $env:CAD_AGENT_M2_RECORD_PATH = 'C:\temp\cad-agent-m2-record.json'
    $env:CAD_AGENT_M2_SESSION_ID = 'acad-session-20260830-a'
    $env:CAD_AGENT_M2_HUMAN_EVENTS_JSON = '[{"kind":"NETLOAD","count":1,"detail":"manual operator load"}]'
    & .\.venv-py311\Scripts\python.exe -m pytest mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py -q -p no:cacheprovider

Repeat after a fresh AutoCAD start with a new session id until the record contains three successful comparable epochs across two sessions. Record command output, record SHA, exact hashes, and cleanup state.

- [x] Step 6: Commit

    git add mcp_integration_lib\tests\test_m2_mechanical_benchmark_live.py tests\test_m2_benchmark.py
    git commit -m "test: add opt-in M2 Mechanical benchmark harness"

---

### Task 4: Status, full verification, and merge

**Files:**
- Modify: docs/STATUS.md
- Modify: tests/test_documentation_contract.py only if its existing contract requires registering the new spec/plan.

- [x] Step 1: Run documentation tests

Register only the new canonical spec/plan paths if required. Do not rewrite historical status claims or bulk-check old plans.

- [x] Step 2: Run authoritative verification

    $cadPython311 = py -3.11 -c "import sys; print(sys.executable)"
    & .\scripts\bootstrap.ps1 -PythonExe $cadPython311
    & .\scripts\verify.ps1
    git diff --check
    git status --short

Record exact exit code and JUnit/test counts. Missing dotnet/AutoCAD prerequisites are NOT RUN/SKIP, never a substitute pass.

- [x] Step 3: Update current status from evidence only

Record implementation head, focused/full verification, record path/hash, comparable/successful epochs, success rate, profile/setup state, human events, headless/live defect counts, transport/result-identity categories, stale/wrong-target refusals, close-without-save/source/hash cleanup, and explicit autocad_mechanical, real_data, and authoritative-release states. If live prerequisites remain absent, keep acceptance NOT RUN or BASELINE_ONLY and do not close the overall goal.

Use the recorded request/result sizes and repeated-query counts to decide the MECH-1 boundary. If they do not show a material coverage or context/token problem, document MECH-1 NOT JUSTIFIED and do not create observe_drawing or query_entities. If they do show a material problem, stop for a new approved design boundary rather than adding a façade inside this plan.

- [ ] Step 4: Fresh-read before merge

Run git diff --check, git status --short --branch, git log --oneline --decorate -8, and gh pr checks. Fresh-fetch/read current main, #301, #302, and #305. Merge only when the exact PR head has required checks, M2 acceptance is satisfied or the remaining live gate is a genuine human hard gate, no P0/P1 remains, and no current advisory is unacknowledged. After merge verify origin/main and update docs/STATUS.md.

- [ ] Step 5: Close plan only with fresh proof

Set Completion Head SHA to the implementation/evidence commit immediately before the lifecycle-closing commit. Never mark representative acceptance from a single positive smoke epoch.

**Current boundary:** Task 3 Step 5 remains open because no operator-controlled
AutoCAD Mechanical/FileIPC session was available. Task 4 Steps 4-5 therefore
remain open as well: the branch is preserved for the human live gate and has
not been merged or claimed representative. The current evidence head is a
verified baseline, not a lifecycle-closing completion head.
