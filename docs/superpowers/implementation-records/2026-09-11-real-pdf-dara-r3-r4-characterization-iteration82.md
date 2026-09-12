# Current-Main DARA/R3/R4 Characterization — Iteration 82

Date: 2026-09-11 (Asia/Saigon)
Canonical main SHA: `e8fc0092ee46750e50de0ea408fd91811cae10c2`
Executor branch: `codex/audit-text-style-compat-20260910`

## Authority and exact scope

SOL's iteration-81 decision authorized one read-only characterization for the
same fresh page-1 candidate identity. It required the existing source-fusion,
reuse/base-CAD, ComponentViewRegistry (R3), and CandidateRevision (R4) owners
to determine the first exact required input or contract that prevents or
permits a same-identity DARA/R3/R4 binding.

The characterization used only the fresh iteration-80 manifest and page-1 DXF
identity:

- manifest SHA-256:
  `f7c7b1afbd52f8f504dafbcb9b6efb416ee332b88260a01aea2414ab9d650eaf`;
- current-main SHA:
  `e8fc0092ee46750e50de0ea408fd91811cae10c2`;
- approved source SHA:
  `e48f39702ff75c72b4cda208128f8e00abf77b9660df9589427b7d923988dc75`;
- page-1 staged DXF SHA:
  `167a3955a84e24c40c81112ad696eb08f943f4b2721d56891bef8620a731a714`.

No provenance packet, DARA reference, reuse handoff, registry, candidate
revision, source/candidate/DXF, or live artifact was created or mutated.

## Exact owner characterization

The run-pdf manifest contains source/configuration/render/page/stage identity,
but it does not contain the required source-fusion evidence collection. The
source-fusion owner requires:

- a validated `source_bundle`;
- `READY` source custody bound to that bundle;
- page and region locators;
- render provenance;
- primitive and semantic observations;
- tolerance policy and the resulting `fusion_input_sha256`.

The existing owner probes rejected the absent inputs as follows:

- `build_source_fusion_packet` without bundle/custody:
  `SOURCE_BUNDLE_INVALID`;
- empty source-fusion packet:
  `SOURCE_FUSION_PACKET_INVALID`;
- empty base-CAD reuse handoff: closed-field rejection, including missing
  `source_fusion_sha256`, candidate input/output hashes, and live preflight
  evidence;
- empty DARA baseline reference: `INVALID_REFERENCE`;
- R3 registry build without upstream context: `UPSTREAM_CONTEXT_INVALID`;
- R4 candidate revision without registry/baseline: `BASELINE_CONTEXT_INVALID`.

The machine-readable characterization is outside Git at:

`C:/temp/cad-agent-real-pdf-current-main-iter80-run/dara-r3-r4-characterization-iteration82.json`

## Classification and stopping point

- `DARA_R3_R4_SAME_IDENTITY_BINDING=NOT_PROVEN`.
- `FIRST_CAUSAL_MISSING_INPUT=VALIDATED_SOURCE_BUNDLE_AND_READY_SOURCE_CUSTODY_FOR_SOURCE_FUSION`.
- The raw PDF SHA and run-pdf manifest SHA are not a substitute for a
  validated source bundle/custody and source-fusion packet. Reusing historical
  or synthetic packet data would cross the identity boundary, so it was not
  done.
- No code, source, candidate, DXF, live CAD/FileIPC, or downstream artifact
  was changed. The characterization stops here as SOL required.
