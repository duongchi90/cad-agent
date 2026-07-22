# Release Checklist

- **Candidate Head SHA:** required 40-character commit
- **Target:** Windows, Python 3.11, AutoCAD LT
- **Human approval:** approver identity and timestamp

## Evidence

- [ ] `scripts/verify.ps1` passed on the candidate Head SHA.
- [ ] Required `real_data` gate passed, or is explicitly not affected.
- [ ] Required `autocad_lt` gate passed, or is explicitly not affected.
- [ ] JUnit, private input hash, and live-session evidence are recorded.
- [ ] Independent findings are adjudicated; unresolved P0/P1 count is zero.

## Safety

- [ ] Secrets and private drawings are absent from Git.
- [ ] Original DXF backup is verified.
- [ ] Rollback steps and operator are named.
- [ ] Post-repair review and health check are defined.
