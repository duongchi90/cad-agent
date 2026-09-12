# R1C executor binding GREEN — iteration 171

Date: 2026-09-12

## Scope

The current `cad_agent.pdf.run_pdf_stages` executor now accepts one optional
caller-supplied `r1c_configuration`. The binding requires exactly the existing
closed R1C owner fields and delegates validation and byte inspection directly
to `cad_agent.source_integrity.inspect_source_bundle`. The existing owner
evidence is returned unchanged; no second custody or provenance representation
was introduced.

The binding is evaluated before downstream PDF staging. Invalid, incomplete,
or extra-field configurations fail closed with `R1C_CONFIGURATION_INVALID`.
The existing call path remains unchanged when the optional configuration is
omitted.

## Evidence

- Base/main: `e8fc0092ee46750e50de0ea408fd91811cae10c2`.
- Implementation commit: `f2e6c54` (`feat: bind R1C configuration to PDF executor`).
- Focused R1C binding tests: `4 passed in 0.10s`.
- Nearest offline regression (`r1c_executor_binding`, PDF, SourceIntegrity,
  SourceFusion): `400 passed in 12.59s`.
- Ruff: `PASS`.
- `git diff --check`: `PASS`.
- The disposable test source bundle hash is checked against the bytes on disk;
  the real existing SourceIntegrity owner performs the custody read and
  returns `observed_sha256` and the owner-generated bundle evidence.

## Boundary and safety

This closes only the offline executor-to-existing-owner binding gap. It does
not claim authentic provenance for the exact private PDF, SourceFusion packet
acceptance, DARA/R3/R4 acceptance, persistence/reopen, visual acceptance,
dimension acceptance, or release eligibility. No bridge/raw-key API, key
loader/provider/store, SourceCustody bypass, source/customer drawing, DXF,
AutoCAD, live FileIPC, provider, or M2 mutation was performed.

The predecessor SOL authorization was `CLEAR_CONTINUE` for this smallest
GREEN. Because the implementation moved HEAD, a fresh exact-head SOL review
is required before the next material boundary. `HUMAN_GATE=NO`.
