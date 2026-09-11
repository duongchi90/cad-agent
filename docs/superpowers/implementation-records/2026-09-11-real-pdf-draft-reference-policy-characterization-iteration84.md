# Real-PDF DRAFT_REFERENCE policy characterization — iteration 84

Date: 2026-09-11  
Issue: #409 real-PDF exact-identity acceptance  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch: `codex/audit-text-style-compat-20260910`  
Prior evidence head: `ccf91b06c199d45aded95d75016a54e84a91409f`

## Authorization and bounded scope

The owner requested removing the approved-root and identity-key requirement.
SOL reviewed that request and returned `VERDICT=MATERIAL_FINDING`:
authoritative `source-custody-1.0` must retain keyed object/path identity and
approved-root revisions. SOL authorized one offline characterization only:
identify the smallest existing acceptance boundary and define a causal RED
for a policy split where `DRAFT_REFERENCE` remains non-authoritative while
authoritative promotion still requires `READY` custody.

No code was added. No source-custody artifact, source-fusion packet, source,
candidate, DXF, or live CAD state was mutated.

## Characterization evidence

The existing PDF owner `cad_agent.pdf.new_pdf_manifest` was invoked for the
approved source identity using the repository-owned `.venv-py311` interpreter.
The normalized result was:

```text
release_profile=DRAFT_REFERENCE
authoritative_release_eligible=false
source_sha256=e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75
```

The same interpreter invoked the existing owner
`cad_agent.source_fusion.build_source_fusion_packet` with the repository's
valid source-bundle fixture and a valid but `BLOCKED` custody record. The
existing owner returned:

```text
blocked_custody_status=BLOCKED
blocked_custody_blocking_count=1
causal_red_error=CUSTODY_NOT_READY
```

The focused existing regression was then run without the cache provider:

```text
.venv-py311\Scripts\python.exe -m pytest -p no:cacheprovider -q \
  tests/test_cad_agent_source_fusion.py \
  -k "task4_rejects_non_ready_custody"
1 passed, 226 deselected in 0.10s
```

## Result

`cad_agent.source_fusion.build_source_fusion_packet` is the smallest existing
authoritative acceptance boundary found in this characterization. Its
validated-custody path is the causal gate: it requires `READY` custody before
page/region/render fusion can be accepted. The existing PDF path already has
the safe non-authoritative `DRAFT_REFERENCE` classification.

The smallest possible future write-set, subject to a separate design approval,
is a thin policy/acceptance adapter plus focused tests that allows only
non-authoritative DRAFT_REFERENCE evidence to continue. It must not modify
`cad_agent.source_integrity`, the `source-custody-1.0` contract,
`build_source_fusion_packet`, or authoritative promotion semantics. No second
custody owner/store and no fabricated identity is allowed.

Classification:

```text
DRAFT_REFERENCE_POLICY_SPLIT_CHARACTERIZATION=PROVEN_CURRENT
AUTHORITATIVE_PROMOTION_WITHOUT_READY_CUSTODY=REJECTED_CURRENT
HUMAN_GATE=NO
```

## Next bounded review

Return this exact owner/write-set/oracle to SOL for fresh review before any
implementation. Implementation remains pending that review; the reviewed
production state remains unchanged.
