# Claude Review Adapter

Read `AGENTS.md` first, then only the canonical document relevant to the assigned
review:

- scope: `docs/PROJECT.md`
- architecture: `docs/ARCHITECTURE.md`
- evidence: `docs/STATUS.md`
- gates/severity: `docs/QUALITY.md`

Work only inside the supplied review packet and diff scope. Do not infer current
status from `HANDOFF.md`, old plans, unchecked boxes, or model-generated claims.
Do not edit the repository from a Claude Free review session.

Use only content in the self-contained packet and its uploaded attachments.
Report an attachment as missing if the packet gives only a local filesystem
path or if its SHA-256 does not match the manifest.

Return findings using `docs/templates/REVIEW_FINDING.md`. Every finding must name
the file/line or artifact, impact, evidence, reproduction, and verification. If
no actionable issue exists in scope, state the files and evidence reviewed and
return "No findings".

Do not read another reviewer's first-pass report until all independent reports
have been submitted.
