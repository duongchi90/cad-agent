# Real-PDF DRAFT_REFERENCE owner/write-set closure — iteration 85

Date: 2026-09-11  
Issue: #409 real-PDF exact-identity acceptance  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch: `codex/audit-text-style-compat-20260910`  
Prior evidence head: `e98ee55dc19007255b915f952592f960ef2d3926`

## Authorization and scope

SOL authorized exactly one offline owner/write-set closure after iteration 84.
The requested owner change was to enforce that `DRAFT_REFERENCE` remains
non-authoritative without adding a parallel acceptance or custody authority.
No production code was written.

## Existing owner and consumers

The existing owner is `cad_agent.manifest.classify_draft_reference`.
`cad_agent.pdf.new_pdf_manifest` invokes it when creating a PDF run manifest,
and `cad_agent.pdf.read_pdf_manifest` invokes it again when loading one. The
owner requires these safe fields:

```text
release_profile=DRAFT_REFERENCE
authoritative_release_eligible=false
drawing_setup_evidence=null
```

It rejects any conflicting value instead of silently downgrading it.

The only immediate production callers found for the PDF reader are
`cad_agent.cli._resume_pdf_command` and
`cad_agent.mechanical_pilot.bind_simple_shaft_pilot_from_primitive`.
They use the reader for run/source and primitive binding. A current-main
production search found no consumer that reads
`authoritative_release_eligible` to promote an artifact. The authoritative
source-fusion owner remains `cad_agent.source_fusion.build_source_fusion_packet`;
its validated-custody path is separate and fail-closed.

## Causal RED characterization

The following existing tests were run with the repository-owned `.venv-py311`
and disabled pytest cache provider:

```text
.venv-py311\Scripts\python.exe -m pytest -p no:cacheprovider -q \
  tests/test_cad_agent_pdf.py tests/test_cad_agent_source_fusion.py \
  -k "new_and_historical_pdf_manifests_are_draft_reference or pdf_manifest_refuses_unsafe_release_claim or task4_rejects_non_ready_custody"
5 passed, 232 deselected in 2.02s
```

The five passing cases establish the required causal boundary:

1. New and historical PDF manifests normalize to `DRAFT_REFERENCE` and
   `authoritative_release_eligible=false`.
2. Each unsafe claim (`release_profile=AUTHORITATIVE`,
   `authoritative_release_eligible=true`, and non-null setup evidence) is
   rejected by the existing reader.
3. A valid but `BLOCKED` custody record is rejected by the existing fusion
   path with `CUSTODY_NOT_READY`.

## Exact write-set closure

```text
MODIFY=NONE
CREATE=NONE
```

The current owner already satisfies
`DRAFT_REFERENCE => NON_AUTHORITATIVE_ONLY`; adding an adapter would create a
second acceptance seam without changing the safe outcome. The correct result
is to preserve `cad_agent.manifest`, `cad_agent.pdf`,
`cad_agent.source_integrity`, and authoritative `cad_agent.source_fusion`
unchanged. No key removal, custody fabrication, foreign fixture reuse, or
authoritative DARA/R3/R4 promotion is allowed.

Classification:

```text
DRAFT_REFERENCE_OWNER_WRITE_SET_CLOSED=PROVEN_CURRENT
AUTHORITATIVE_PROMOTION_WITHOUT_READY_CUSTODY=REJECTED_CURRENT
MODIFY_NONE_CREATE_NONE=CONFIRMED
HUMAN_GATE=NO
```

## Next review

Send this exact closure to SOL for fresh review. No implementation is pending
unless SOL identifies a concrete missing behavior with a narrower approved
write-set.
