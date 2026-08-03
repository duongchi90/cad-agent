# Personal Lean Pilot Offline Continuation Design

- Date: 2026-08-03
- Owner: project owner
- Parent design: `2026-08-03-personal-lean-pilot-rebaseline-design.md`
- Status: direction approved in conversation; written record awaiting owner review

## Context

The owner supplied one sample DWG, but the current workstation does not have
AutoCAD Mechanical 2027. Gate A therefore cannot produce valid live
`SETUP_VERIFIED` evidence on this machine today. Stopping all work would waste
the existing offline solver, DXF builder, review, and evidence boundaries, but
retargeting the product to an older AutoCAD release would expand the approved
platform scope.

This addendum separates implementation readiness from acceptance. It changes
which work may be prepared offline; it does not change the acceptance order or
weaken any live gate.

## Approaches considered

1. **Continue offline and defer the Mechanical 2027 gate — selected.** Reuse
   the existing packages, implement the Gate B offline slice with synthetic and
   headless evidence, and keep all live outcomes unverified.
2. **Retarget to the installed AutoCAD release — rejected.** This would require
   a separate compatibility design, plugin target, live matrix, and quality
   claim. It is outside the approved Windows/AutoCAD Mechanical 2027 scope.
3. **Pause all work until Mechanical 2027 is available — rejected.** This is
   safe but blocks independent contract, solver-adapter, DXF, and headless-test
   work that can be completed without weakening acceptance.

## Decision

Implementation may proceed on the smallest offline portion of Gate B while
Gate A remains open. Acceptance order remains strictly Gate A, then Gate B,
then Gate C. Offline implementation must not emit `SETUP_VERIFIED`, mark Gate A
complete, promote the sample, or emit `PERSONAL_VERIFIED`.

AutoCAD Mechanical 2027 remains the only supported AutoCAD acceptance target.
An older AutoCAD installation may not be used as substitute evidence, even if
it can open or export the sample.

## Sample DWG handling

The owner-provided DWG is private external input, not a repository fixture.

- Keep the original file unchanged and outside Git.
- Before any inspection, record its SHA-256 and create a non-overwriting copy
  outside the repository; verify the copy hash equals the original hash.
- Do not save, repair, convert, or overwrite the original.
- Do not commit the DWG, a derived DWT/DXF, raw audit output, its workstation
  path, or private annotations.
- The sample may guide planning and later private measurements, but its mere
  presence is not Drawing Setup evidence.
- If offline geometry content is needed, require an owner-provided export in a
  format already supported by the existing pipeline. Do not add a new DWG
  parser or use an unsupported AutoCAD release as an implicit converter.

## Offline Gate B slice

The next implementation plan is limited to four additive pieces:

1. Define the smallest versioned record for approved linear dimensions, one
   explicit two-axis datum frame, attachment, source hashes, and a required
   positive measurement tolerance in millimetres.
2. Adapt that record to `semantic_ir_lib`; do not create a second solver or
   infer a datum from the sample.
3. Generate one deterministic native editable DXF view through
   `dxf_builder_lib`, then measure the selected geometry and dimensions back
   headlessly against the configured tolerance.
4. Fail closed at the orchestration boundary unless fresh real
   `SETUP_VERIFIED` evidence is supplied. Synthetic setup evidence is allowed
   only inside tests and cannot promote a private run.

The image/PDF reconstruction path remains `DRAFT_REFERENCE`. M5 search,
automatic segmentation, cross-view inference, multi-configuration proof, and
production repair remain deferred.

## State and evidence

No new product status is introduced for offline readiness. Repository status
may say that a Gate B implementation candidate exists, but product evidence
continues to use only `DRAFT_REFERENCE`, `SETUP_VERIFIED`, and
`PERSONAL_VERIFIED` as defined by the parent design.

The following remain blockers until a real Mechanical 2027 session runs:

- an owner-approved external DWT and non-sensitive profile/domain metadata;
- a disposable DWG created from that DWT;
- the managed plugin, File IPC directory, and active-document match;
- unchanged source hash and DBMOD with a blocker-free setup audit.

Gate B acceptance additionally requires owner-approved dimensions, datum, and
tolerance plus fresh read-back measurements. Gate C and
`PERSONAL_VERIFIED` remain unavailable until all earlier evidence is fresh.

## Verification policy

- Use a failing focused test before each production behavior change.
- Run focused schema, solver-adapter, builder, measurement, and refusal tests
  after each bounded task.
- Because Gate B touches constraints, run the affected private `real_data`
  benchmark when an approved compatible export is available. Otherwise record
  it as `NOT RUN`; an unavailable-state probe is not acceptance.
- Run `scripts/verify.ps1` on the candidate. If .NET or live prerequisites are
  absent, use only the verifier's explicit skip option and record `.NET` and
  AutoCAD gates as `NOT RUN`.
- Keep the consolidated pull request in draft while Gate A remains open.

## Success criteria

This continuation is successful when the Gate B offline implementation is
deterministic, covered by focused tests, reuses existing package boundaries,
refuses stale or missing setup evidence, and leaves the private sample and
supported-platform claims unchanged. It is implementation progress, not a gate
pass.

When AutoCAD Mechanical 2027 becomes available, resume Gate A with the approved
DWT-derived disposable DWG. A blocker-free, hash-stable, DBMOD-stable live audit
must close Gate A before any Gate B private result can be accepted.
