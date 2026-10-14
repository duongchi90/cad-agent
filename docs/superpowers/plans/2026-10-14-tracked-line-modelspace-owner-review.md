# Tracked LINE ModelSpace Owner Review Implementation Plan

> **For agentic workers:** Execute this plan inline under the authorized #491 package. Subagents are disabled by the current repository contract. Steps use checkbox tracking.

**Goal:** Make the default DXF reviewer reject builder-tracked raw LINE entities that are no longer owned by and present in ModelSpace.

**Architecture:** Add one LINE-specific readback guard in the existing reviewer loop, using the reopened document's ModelSpace membership and block-record owner. Preserve existing whole-inventory opt-in behavior and all other entity semantics.

**Tech Stack:** Windows, Python 3.11.9, ezdxf 1.4.4, pytest, Ruff.

**Spec:** [2026-10-14-tracked-line-modelspace-owner-review.md](../specs/2026-10-14-tracked-line-modelspace-owner-review.md)

## Global Constraints

- Base SHA: `c80303aa841980138c18b170162386f6d5eb3a5a`; base tree: `d47db24cb8a809eda1efbe75d10d4209409e6c9f`.
- Existing supported environment only: Windows Python 3.11.9 at `C:\cad-agent\.venv-py311\Scripts\python.exe`, ezdxf 1.4.4, lock `requirements/windows-py311.lock`; do not install or create an environment.
- Exact write set: `dxf_builder_lib/reviewer.py`, `dxf_builder_lib/tests/test_reviewer.py`, `dxf_builder_lib/README.md`, this spec, and this plan.
- No builder/CLI/schema/lock/config/STATUS edits; no native, AutoCAD, private drawing, push, PR, CI, review request, or merge.

## Review Focus

- Saved LINE in PaperSpace — reject with expected and actual owner evidence.
- Saved LINE in an owned block layout — reject despite valid handle/type/layer/geometry.
- Missing or unresolved owner — fail closed and preserve candidate bytes.
- Unrelated extra ModelSpace entity — default review still passes; strict inventory rejects it.
- Other tracked entity types and existing geometry/tolerance checks — retain prior behavior.

---

## Authorized package sequence

### Step 1 — admission and isolated branch

- [x] Fresh-read #491 package, governance routers, exact main/tree, source blobs, and existing Windows/Python environment.
- [x] Create `codex/tracked-line-modelspace-owner-v1` from the exact admitted main in the existing isolated checkout.
- [ ] Stop if identity, lock/runtime, owner, or custody differs.

### Step 2 — TDD RED

**Files:** `dxf_builder_lib/tests/test_reviewer.py`

- [x] Add saved/reopened LINE cases moved to PaperSpace and to an owned block layout. Assert exact tracked handle, unchanged layer/endpoints, wrong owner/layout membership, default review non-PASS with primitive/handle/expected/actual owner, and unchanged DXF bytes.
- [x] Add an absent/unknown owner test through a controlled post-read seam, explicitly recording that this is not serialized-file evidence.
- [x] Add compatibility coverage that default review permits an unrelated ModelSpace extra while `strict_primitive_inventory=True` rejects it.
- [x] Run the new moved/owner cases once against the unmodified reviewer: `4 failed, 75 deselected`; all four reached the expected assertion that default review incorrectly passed. RED log SHA256 `14443c0540c12572110a989c391c7d81ee9c755658f4a4fb9744666b6d39665d`.

### Step 3 — narrow GREEN

**Files:** `dxf_builder_lib/reviewer.py`

- [x] After tracked-handle resolution and expected-type validation, require a raw LINE's DXF owner to equal `doc.modelspace().block_record_handle` and require its membership in that reopened ModelSpace.
- [x] Report primitive, handle, expected ModelSpace owner, and actual owner. Unknown/absent owner fails closed; do not repair or mutate entities.
- [x] Keep strict inventory default false; do not change other entity types, signatures, or tolerances.

### Step 4 — focused compatibility verification and docs

**Files:** `dxf_builder_lib/tests/test_reviewer.py`, `dxf_builder_lib/tests/test_builder.py`, `tests/test_cad_agent_cli_staged_semantic_policy.py`, `dxf_builder_lib/README.md`, this spec.

- [x] Run exactly once: `python -m pytest -q dxf_builder_lib/tests/test_reviewer.py dxf_builder_lib/tests/test_builder.py tests/test_cad_agent_cli_staged_semantic_policy.py` using the existing Python 3.11.9 environment; result `97 passed`, actual exit 0; log SHA256 `b6a44958a559055fe8996143cf5882661198d78620833392d52c15ed91eee8d3`.
- [x] Ruff on `dxf_builder_lib/reviewer.py` and `dxf_builder_lib/tests/test_reviewer.py`: PASS; `git diff --check`: PASS.
- [x] No failures, unknowns, or out-of-scope changes in the focused/static gates.
- [x] Document the direct ModelSpace tracked-LINE contract and offline-only limits in the library README.

### Step 5 — implementation checkpoint and canonical verification

- [ ] Commit the scoped implementation checkpoint and record parent/tree/status and source/test hashes.
- [ ] Prove the existing qualified PowerShell Core launcher and Python executable before starting one supervised `scripts/verify.ps1 -SkipAutoCADDotNet` run.
- [ ] Capture durable START/PID/elapsed/stdout/stderr/completion/exit/JUnit. Allow at most the package's bounded observations; no retry, cancellation, or termination.
- [ ] Require actual exit 0, required offline coverage, and unchanged clean source/tree/status.

### Step 6 — plan lifecycle close

- [ ] Mark the plan completed in a separate plan-only local commit if needed, proving verified source/test/spec/README bytes are unchanged and the final tree is clean.
- [ ] Record native/private/live/AutoCAD.NET gates as NOT RUN.

### Step 7 — durable receipt and stop

- [ ] Publish and read back one compact #491 receipt with exact identities, write set, RED/GREEN/static/canonical results, hashes, compatibility limits, and NOT RUN gates. If any step stopped, publish only bounded stop evidence.
- [ ] Return to Local Sol before push, PR, review, or promotion.

## Package status

- Status: executing
- Base SHA: `c80303aa841980138c18b170162386f6d5eb3a5a`
- Completion Head SHA: pending
- Required private/live gates: NOT RUN; not authorized by this package.
