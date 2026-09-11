# Real-PDF PDF-lane/source-fusion call-site closure — iteration 86

Date: 2026-09-11  
Issue: #409 real-PDF exact-identity acceptance  
Canonical main context: `e8fc0092ee46750e50de0ea408fd91811cae10c2`  
Executor branch: `codex/audit-text-style-compat-20260910`  
Prior evidence head: `c3d792d7f547a4038d8c89267a56a74482037813`

## Authorization and bounded scope

SOL changed the product decision: the PDF `DRAFT_REFERENCE` lane must not be
blocked on approved-root or identity-key custody. The key-backed
`source-custody-1.0` and authoritative source-fusion contracts remain
unchanged. SOL authorized one bounded current-main call-site audit followed by
the smallest RED/GREEN characterization.

## Call-site result

Current-main search found no production caller that routes a PDF manifest or
`DRAFT_REFERENCE` artifact into `build_source_fusion_packet`:

- `cad_agent.cli` creates/resumes PDF stages through `cad_agent.pdf`.
- `cad_agent.mechanical_pilot` reads a PDF manifest only for source name/SHA
  and primitive-stage binding.
- `cad_agent.source_fusion` is consumed by authoritative/R3-style owners and
  requires validated `READY` custody through its existing guard.

The PDF path therefore already has the requested split: its run-pdf and pilot
workflow can proceed using SHA-bound evidence without custody/key, while the
authoritative fusion path remains separate and fail-closed.

## Focused characterization

The following existing tests were run with `.venv-py311` and no pytest cache:

```text
.venv-py311\Scripts\python.exe -m pytest -p no:cacheprovider -q \
  tests/test_cad_agent_pdf.py \
  tests/test_cad_agent_phase4_pilot_binding.py \
  tests/test_cad_agent_source_fusion.py \
  -k "test_pdf_cli_run_and_resume or test_phase4_pdf_pipeline_binds_the_selected_pilot_contract or task4_rejects_non_ready_custody"
3 passed, 240 deselected in 7.20s
```

These cases show:

1. PDF run/resume continues through the existing non-authoritative workflow.
2. PDF pilot binding continues from a PDF manifest without source custody or
   an identity key.
3. A non-`READY` custody record still fails at source-fusion with
   `CUSTODY_NOT_READY`.

## Exact write-set

```text
MODIFY=NONE
CREATE=NONE
```

There is no immediate consumer seam to modify. Adding a PDF-to-fusion adapter
would create the unwanted parallel acceptance authority. The correct current
main result is to preserve the existing PDF owner and preserve the existing
authoritative custody/fusion guard.

Classification:

```text
PDF_DRAFT_LANE_WITHOUT_CUSTODY=PROVEN_CURRENT
PDF_TO_SOURCE_FUSION_DIRECT_ROUTE=NOT_PRESENT_CURRENT
AUTHORITATIVE_READY_CUSTODY_GUARD=PROVEN_CURRENT
MODIFY_NONE_CREATE_NONE=CONFIRMED
HUMAN_GATE=NO
```

No production code, source, custody, candidate, DXF, or live CAD state was
mutated.

## Next review

Return this call-site closure and focused evidence to SOL for a fresh verdict.
