# CAD Agent Working Agreement

## Canonical sources

Read these before planning or changing behavior:

- Product and scope: `docs/PROJECT.md`
- Current architecture: `docs/ARCHITECTURE.md`
- Verified status: `docs/STATUS.md`
- Quality and release gates: `docs/QUALITY.md`
- Design/plan record policy: `docs/superpowers/README.md`

`HANDOFF.md` and `CAD-Agent-Kien-Truc-v1_3.md` are historical evidence. Do not
use a historical status claim when it conflicts with `docs/STATUS.md` or fresh
command output.

## Supported environment

- Windows
- Python 3.11
- AutoCAD LT
- Tesseract 5.4.0.20240606

Do not expand platform, deployment, or AutoCAD scope without an approved design.

## Authoritative commands

```powershell
$python311 = py -3.11 -c "import sys; print(sys.executable)"
.\scripts\bootstrap.ps1 -PythonExe $python311
.\scripts\verify.ps1
```

The authoritative scripts are `scripts/bootstrap.ps1` and `scripts/verify.ps1`.

Do not copy the pytest selection into another script or workflow. Add a test
root or lint target to `scripts/verify.ps1` and its contract test.

## Change workflow

1. Inspect current status, relevant contracts, and recent commits.
2. For new behavior, obtain design approval before implementation.
3. Use a failing regression test or benchmark before changing production logic.
4. Keep one writer for a branch or overlapping file set. Use parallel agents for
   read-heavy exploration, test execution, and independent review.
5. Keep commits scoped and run focused checks after each task.
6. Run `scripts/verify.ps1` before claiming completion or committing a release
   candidate.

## Specialized gates

- Calibration, OCR, geometry, line merging, pattern recognition, or constraints:
  run the affected `real_data` benchmark using the approved private input.
- File IPC, handles, components, live review, or live repair: run the affected
  `autocad_lt` smoke test.
- If a prerequisite is absent, report `SKIP` or `NOT RUN`; never report a pass.
- Automatic calibration's production gate is at least two independent
  candidates with median relative error at most 3 percent.

## Safety

- Never commit API keys, `.env`, customer drawings, private annotations, or
  unapproved generated DXF files.
- Human approval is required for unverified calibration, ambiguous recognition,
  and production DXF mutation.
- Preserve the original DXF and establish rollback before AutoCAD LT repair.
- Avoid destructive Git/filesystem operations. Resolve and verify exact targets
  before any approved deletion or recursive move.
- Do not alter architecture, public schemas, or package boundaries outside the
  approved task.

## Review allocation

- Small: Codex plus one bounded independent review.
- Medium: requirements/architecture plus correctness/test reviews.
- Calibration, geometry, File IPC, AutoCAD LT, architecture, or release:
  requirements/architecture, correctness/test, and security/operations reviews.

Give Claude Free reviewers a compact packet from `docs/templates/`, not the full
repository. Keep first-pass reports independent. Accept findings only when they
name scope, impact, evidence, and verification; do not use numeric quality
scores. Upload or inline every referenced artifact; a workstation-local path is
not review evidence for an external session.

## Definition of done

- Acceptance criteria are satisfied with fresh evidence.
- Focused tests and `scripts/verify.ps1` pass.
- Required private/live gates ran, or their missing state is explicitly recorded.
- `git diff --check` is clean and verification did not change repository status.
- No unresolved P0/P1 finding remains; deferred P2 has a reason and owner.
- `docs/STATUS.md` reflects only evidence that actually ran.
