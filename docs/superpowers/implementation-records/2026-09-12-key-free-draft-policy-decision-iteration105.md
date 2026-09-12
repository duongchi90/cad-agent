# Key-Free PDF Draft Policy Decision — Iteration 105

Date: 2026-09-12 (Asia/Saigon)  
SOL channel: `SOL PO mới nhất`  
Executor branch: `codex/audit-text-style-compat-20260910`  
Reviewed executor HEAD: `e08a589ddb0ddd7ad21e08a572c8859d512911c3`

## Owner request

The owner requested that the identity key not be required for the page-1 PDF
workflow.

## Fresh SOL decision

SOL fresh-read the canonical `main=e8fc0092ee46750e50de0ea408fd91811cae10c2`
and confirmed:

- `cad_agent/pdf.py::new_pdf_manifest` wraps new PDF runs as
  `DRAFT_REFERENCE`.
- `read_pdf_manifest` keeps approved-root/source-custody/source-fusion
  references optional for this draft path and reclassifies the manifest as
  `DRAFT_REFERENCE`.
- PDF `DRAFT_REFERENCE` creation/resume therefore has no approved-root or
  identity-key prerequisite.
- The authoritative SourceCustody schema intentionally remains fail-closed,
  including `identity_scheme=HMAC-SHA-256` and `identity_key_revision`.
- No key bytes were read, changed, or removed.

## Decision and scope

```text
VERDICT=REQUEST_SATISFIED_WITH_MODIFY_NONE
FIRST_UNSATISFIED_BOUNDARY=NONE_FOR_DRAFT_REFERENCE_KEY_POLICY
HUMAN_GATE=NO
```

The request is satisfied by preserving the existing key-free
`DRAFT_REFERENCE` lane. Removing or bypassing identity-key validation for
authoritative source promotion would be a separate governance/contract
change and is not part of the page-1 draft workflow. It must not be silently
implemented.

The current project frontier remains the measured raw-LISP receiver
consumption boundary. The next work continues from that boundary without
routing the draft through authoritative SourceCustody/SourceFusion and without
live retry, code, source, DXF, or CAD mutation until a fresh bounded action is
authorized.

