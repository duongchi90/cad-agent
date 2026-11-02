# CAD Agent Working Agreement

## Authority and currentness

- GitHub is canonical for mutable product, issue, PR, CI, and runtime state. Before a material decision, verify current `main` SHA/tree and the relevant issue or PR identity, checks, and evidence. Fresh GitHub evidence supersedes chat history, cached state, and stale local checkouts. Inspect recent commits when they bear on the task’s ownership, provenance, or changed boundary.
- Use current #429 as the ordinary operating overlay when its role, authority, currentness, execution, or review rules apply.
- #305 is a predecessor operating record. Read it only when its still-unique semantics matter. #392 is the specialized material-review owner. Read it when its review or V7 procedure applies. Neither is a routine bootstrap read.
- Read #291 when product direction or scope matters; read #461 when relying on accepted-product evidence.
- For an active issue event log, read its body and metadata, then the newest relevant authoritative checkpoint, then only explicit pointer targets. Expand further only to resolve a contradiction. Do not scan the full history by default.
- `docs/STATUS.md` routes durable acceptance; mutable frontier and transient status belong in current GitHub evidence. Historical plans, ledgers, and unchecked boxes are not an active queue.

## Task routing

Read only the current source needed for the task:

- Product scope or mode: `docs/PROJECT.md` and, when needed, #291.
- Existing owner, package boundary, or architecture choice: relevant sections of `docs/ARCHITECTURE.md`.
- Accepted baseline or durable evidence: `docs/STATUS.md` and, when applicable, #461.
- Test classes, benchmark, or release gate: `docs/QUALITY.md`.
- Role authority, escalation, or live-operation procedure: relevant sections of `docs/AI_OPERATING_MODEL.md` and current #429.
- Design/plan record lifecycle: `docs/superpowers/README.md`.
- Historical provenance or regression question: the specific historical record needed; do not load historical design/plan files for routine work.

## Product and implementation rules

- Reuse existing owners and APIs first. For new production behavior, identify the current reachable causal RED, use a failing regression test or benchmark before implementation, and prefer the smallest repair or thin adapter. Obtain design approval before changing behavior.
- Before designing a new solution, check existing implementations/APIs/libraries and established, evidence-backed methods; compare reuse, quality, cost, and owner fit. Use the smallest real-case A/B that distinguishes options; design anew only when evidence shows they fall short. Keep research proportionate and reuse completed findings unless new evidence changes the decision. See `docs/AI_OPERATING_MODEL.md`.
- Apply engineering-first reasoning to every CAD operation, proportionate to scope: in REVISION, reuse a trustworthy native base and verify the bounded source-supported delta plus affected relationships; in RECONSTRUCTION, understand the full drawing, dimension roles/feature associations, datums, dependencies, and construction order; in NATIVE_EDIT, verify only the affected scope. Classify dimensions as DRIVING, REFERENCE, REDUNDANT, CONFLICTING, or UNRESOLVED; OCR text alone is not a constraint. Reuse correct native geometry and owners, derive only from evidence, and measure geometry rather than labels or appearance. Do not use DIMENSION text to hide a mismatch or require a DIMENSION when it is not needed. Use native readback/save-reopen when applicable. See `docs/AI_OPERATING_MODEL.md`.
- Complete the task’s internal/external reuse review before adding production behavior. Stop for product-owner review when licensing, reproducibility, architecture ownership, or benchmark benefit is unclear.
- Do not create a custom production Codex transport; use the approved official SDK/App Server/fallback order in `docs/AI_OPERATING_MODEL.md`.
- Keep one writer for overlapping files. Keep changes scoped; run focused checks after each task.
- Use the authoritative commands below. Do not copy pytest selection into another script or workflow; add test roots or lint targets through `scripts/verify.ps1` and its contract test.

## Supported environment and commands

Supported environment: Windows, Python 3.11, AutoCAD Mechanical 2027, and Tesseract 5.4.0.20240606. Do not expand platform, deployment, or AutoCAD scope without an approved design.

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

`scripts/bootstrap.ps1` and `scripts/verify.ps1` are authoritative.

## Evidence and specialized gates

- Report `SKIP` or `NOT RUN` when a prerequisite is absent; neither state is PASS.
- Calibration, OCR, geometry, line merging, pattern recognition, or constraints: run the affected `real_data` benchmark using approved private input.
- File IPC, handles, components, live review, or live repair: run the affected `autocad_mechanical` smoke test when prerequisites are available.
- Automatic calibration’s production gate is at least two independent candidates with median relative error at most 3 percent.
- Run the canonical verifier before claiming completion or committing a release candidate. Verification must not silently change repository status.

## Safety and native/live custody

- Never commit API keys, `.env`, customer drawings, private annotations, or unapproved generated DXF files.
- Within the active package’s explicit authority, routine actions—including APPLOAD, file-picker, AutoCAD, tests, Git, PR, CI, save, close, reopen, and mutation of explicitly authorized disposable candidates—require no additional human confirmation. This does not broaden authority beyond that package or authorize source, customer, accepted-drawing, or other production mutation.
- Human approval remains required for unverified calibration; ambiguous recognition requiring product judgment; credentials, billing, or private-data authority; unknown executable or trust expansion; source/customer/accepted-drawing mutation; destructive or irreversible high-cost action; and genuinely ambiguous product requirements. Production DXF mutation outside the active package’s explicit disposable-candidate authority remains subject to human approval.
- Preserve the original DXF and establish rollback before AutoCAD Mechanical repair. Keep live AutoCAD/FileIPC work exclusive; bind actions to the verified process, document, and configured IPC path. Do not infer that FileIPC moved from `C:\temp`; verify `CAD_AGENT_DOTNET_IPC_DIR` and current process configuration.
- Prefer `D:\Cad agent temp` for new project scratch/build/test/evidence outputs when the owning tool allows it. On repository refresh, verify the current scratch and IPC locations before use.
- Keep local resource use bounded: one heavy local job by default; one Luna-managed Edge window by default, maximum two; one Luna-managed DWG by default, maximum two, with one exclusive mutable AutoCAD lane. Do not open a third window/drawing or count/close user-owned resources.
- Reuse valid sessions and evidence. Before recovery, identify the owned process/document, active command, unsaved state, and rollback path; never blindly retry or terminate user-owned work. A blocked lane does not stop independent authorized work.
- Do not alter architecture, public schemas, or package boundaries outside the approved task.

## Executor and hard-reasoning consultation

- Luna Medium is the sole production executor and remains responsible for repository, workstation, native-CAD, and Git mutations.
- `PO_SOL_GPT_6_1_HIGH` is the delegated continuity PO for genuine hard decisions, with bounded decision authority over material product/contract/scope/owner questions and final disposition when required after gates. It has no repository, Git/PR, workstation, or native mutation authority and cannot replace Security or Integration review.
- Before calling PO, run `scripts/po_model_guard.py --repair` with the current official Codex runtime; use explicit `gpt-6.1-sol` / `high` call settings and verify the exact fresh runtime turn before consuming its decision. Missing, mismatched or unobservable evidence holds only PO; never fall back to Luna as PO. Follow [the PO model procedure](docs/AI_OPERATING_MODEL.md#local-po-model-protection).
- Decision precedence: current explicit Human direction > current applicable same-boundary Web-PO decision > current Local PO decision > Luna routine judgment within existing authority. A Human Gate is a separate admission condition; stale or different-boundary Web-PO direction does not control. Web-PO unavailability alone is neither BLOCKED nor a Human Gate.
- `ONE_ACTIVE_PO_SOL_CONSULTATION_PER_BOUNDED_HARD_DECISION_PACKET=YES`; default budget is one call per packet. First use a safe, authorized, sufficiently deterministic cheap oracle when it can resolve the question. Reconsult only for requested discriminating evidence returned, material contradictory evidence, or a changed material decision boundary. Routine work proceeds without PO consultation.
- `NO_DESCENDANT_SWARM=YES`; `NO_PARALLEL_PO_SOL=YES`; `NO_CONSULTATION_FOR_ROUTINE_WORK=YES`. PO_SOL cannot create descendants or act as a control plane. Return decisions to Luna for execution and end the consultation after its result.
- Hard-reasoning triggers include a material architecture fork, unclear owner, unresolved root cause after bounded debugging, a falsified hypothesis with multiple plausible paths, native/live safety ambiguity, or a difficult material review. A topic’s complexity alone does not authorize consultation.
- The five scheduled Web SOLs remain independent radar/review only. There is no mandatory all-role execution quorum or wait for optional review.

## Review and merge

- Follow current #429 review-continuity procedure. Material Security and Integration reviews are independent ChatGPT Web reviews; Codex/Luna review, Local PO, hosted CI, and either reviewer cannot substitute for the other.
- For each required review, bind role, request ID, controlling attempt ID, base, head, and tree. Keep one controlling attempt per role; GitHub receipts are canonical, and a stale head transfers no verdict. Review state follows observable evidence, not elapsed time. Channel failure is not review failure or project stop; a pending review blocks only the gated action. Human is not the message bus.
- For ChatGPT Web recovery, a one-time `Stay in chat` selection and an opaque thread/content-reference are not delivery or a verdict; follow [the chat-mode recovery guidance](docs/AI_OPERATING_MODEL.md#chat-mode-recovery-and-review-result-observability).
- Material runtime, safety, currentness, live-promotion, persistence, or acceptance merges require independent `SECURITY_REDTEAM` and `INTEGRATION_CI` clearance bound to the exact merge head, current base/head/main, terminal PASS hosted checks, and PASS causal/focused evidence. Resolve current material specialist findings.
- Before requesting or consuming mandatory independent reviews for a material PR, perform one cheap self-check. This is not independent acceptance and does not replace either required reviewer.
- `SKIP`, `NOT RUN`, stale evidence, mock-only evidence, cleanup-only evidence, submission/enqueue, or ambiguous live completion is never PASS. Execution and merge gates are distinct; optional reviews must not block execution. Routine documentation changes do not require five-role ceremony.
- Additional specialist review is task-triggered. When external review is needed, use a compact packet from `docs/templates/`; keep first-pass reports independent. Findings should state scope, impact, evidence, and verification; do not use numeric quality scores. Include or upload referenced evidence rather than relying on workstation-local paths.

## Completion

- Satisfy acceptance criteria with fresh evidence. Run focused checks and `scripts/verify.ps1`.
- Run required private/live gates or explicitly record why they are `SKIP` or `NOT RUN`.
- Confirm `git diff --check` is clean and verification did not change repository status.
- Leave no unresolved P0/P1 finding; give deferred P2 findings a reason and owner.
- Route durable acceptance through `docs/STATUS.md`; keep transient state on GitHub.
- Before heavy local jobs, check free space and expected output size on every affected volume. If safe headroom cannot be preserved, defer only that job and continue lightweight work.
- At batch closure classify artifacts as `KEEP`, `REGENERABLE`, or `DISPOSABLE`; retain sources, accepted baselines, current candidates, unique tests, hashes, receipts, and required evidence. Clean only closed, unreferenced reproducible intermediates. Never remove dirty, active, unpushed, or unverified worktrees; remove an obsolete worktree only with `git worktree remove` after verifying its branch/commits, PR, untracked data, sessions/processes, and checkpoint references.
- Use `Z:\DuongChi\Cad Agent` for long-term closed evidence only after verifying its mapped/network status, filesystem, capacity, access, speed, and durability; transfer by copy, hash/readback verification, reference reconciliation, then cleanup only after confirmed success.
- Do not claim durable policy adoption from a document edit alone: require merge to canonical `main`, a fresh repository-only session recovery without chat history, and policy contract plus evidence-backed scenario checks. Otherwise report `PERSISTENCE_ACCEPTANCE_GATE=NOT_VERIFIED`.
