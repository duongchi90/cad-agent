# R1C Source Integrity and Deterministic Fusion — Implementation Record

## Task10 handoff

This record is documentation-only. It records the accepted R1C runtime chain and
its exact evidence; it does not add runtime capability.

- Runtime Issue: #169
- Runtime branch: `runtime/issue-169-task10-r1c-implementation-record`
- Exact Task10 base/current main: `90881e351d1ce6a8a55f877800af5211659020cd`
- Predecessor Task9 head: `103a6a335ace388fccd4a39bfeaf857129d43498`
- Predecessor Task9 synthetic: `a7f25526414106ac527d1ae51b71a99ea6647742`
- Task9 merge/current-main SHA: `90881e351d1ce6a8a55f877800af5211659020cd`
- Task10 effective write-set: this file only.

No runtime production or test file is modified here. No schema, workflow,
dependency, history, branch-base, merge, live, AutoCAD, File IPC, S2C, S3B,
private-data, or customer-CAD action is authorized or performed.

## Actual merge chain

The following are the actual serial runtime merges consumed by Task10. Each
head is the final accepted writer head before its merge; merge SHAs are the
actual commits now represented in `main`.

| Task | Runtime Issue / PR | Branch | Final writer head | Actual merge SHA | Effective write-set |
| --- | --- | --- | --- | --- | --- |
| 1 | #91 / #92 | `runtime/issue-91-source-integrity-contracts` | `6713bb7d345f0f94cfaf01bc7f3df62f49d02126` | `d099ac2c8a70969c29a8c1c64a1264ee3eb41a9a` | `cad_agent/source_integrity.py`; `tests/test_cad_agent_source_integrity.py` |
| 2 | #100 / #108 | `runtime/issue-100-source-object-identity` | `78f8e5ee5205b271122437e16cb3f362ee4b1f96` | `4f62623165f1dc6e30738a127e7e45c347f4c165` | same two source-integrity paths |
| 3 | #109 / #111 | `runtime/issue-109-media-adapters-json` | `84c87e56546d7811aa8fad887f0808696e4d117f` | `da63a799c0729157770040c7c5e3036227675ce4` | same two source-integrity paths |
| 4 | #115 / #116 | `runtime/r1c-task4-source-fusion` | `d289e5d649963fa928601f4bfc8d68a2851e635c` | `b217ebfd597260d7b59badc3ffbcfbe7b1139754` | `cad_agent/source_fusion.py`; `tests/test_cad_agent_source_fusion.py` |
| 5 | #123 / #146 | `runtime/r1c-task5-uuid-independent-projections` | `aaa49ee275ba4cca6bceea1bceb039238b0a5150` | `61445aa1d341fec2560ab29a29473d83d82885ff` | same two source-fusion paths |
| 6 | #157 / #161 | `runtime/r1c-task6-deterministic-conflict-packets` | `27ddb4d66e77d5d7c0a292bf52b1be7385593d75` | `1425f4697ab0813deff1b154b35c06da74df056b` | same two source-fusion paths |
| 7 | #162 / #163 | `runtime/issue-162-task7-evaluation-reuse` | `a2f3108ae84269337418d4fb23cf4df1d4b8be34` | `d2cb34475172b29f2cc1e13c18bfe6666944e98a` | `cad_agent/source_fusion.py`; both source-integrity/fusion tests; `cad_agent/source_integrity.py` unchanged |
| 8 | #165 / #166 | `runtime/issue-165-task8-manifest-r1c-references` | `75669c8a56e1271dd01c1d8bd4b98bf6dbe3ee77` | `fbc30bc3b7a2e7dab9aa4c5f0112d29f7e1e0625` | `cad_agent/manifest.py`; `cad_agent/pdf.py`; `tests/test_cad_agent_source_bundle_manifest.py` |
| 9 | #167 / #168 | `runtime/issue-167-task9-r1c-boundary-hardening` | `103a6a335ace388fccd4a39bfeaf857129d43498` | `90881e351d1ce6a8a55f877800af5211659020cd` | `cad_agent/source_fusion.py`; both source-integrity/fusion tests; `cad_agent/source_integrity.py` unchanged |

The cumulative accepted runtime paths are exactly:

1. `cad_agent/source_integrity.py`
2. `tests/test_cad_agent_source_integrity.py`
3. `cad_agent/source_fusion.py`
4. `tests/test_cad_agent_source_fusion.py`
5. `cad_agent/manifest.py`
6. `cad_agent/pdf.py`
7. `tests/test_cad_agent_source_bundle_manifest.py`

Task10 adds no runtime path to that historical set; its one-path audit is
separate and must compare the Task10 head to `90881e3...`.

## Authority and reuse ledger

R1C kept one owner per concern:

- `cad_agent.drawing_contracts.canonical_json_sha256` remains the canonical
  serialization/hash owner.
- `cad_agent.source_integrity` owns closed numeric, custody, identity/path,
  tolerance, evaluation, injected-time, and expiry validation. Its policy
  constants remain authoritative.
- `cad_agent.source_bundle` remains the SourceBundle validation and hash owner.
- `cad_agent.source_fusion` owns locator/render validation, Primitive/Semantic
  projection, deterministic packet/conflict construction, and evaluation
  building/matching by reusing the integrity and canonical-hash owners.
- `cad_agent.manifest` remains the sole run-manifest writer and owns compact
  optional custody/fusion/evaluation references and exact bind/match refusal.
- `cad_agent.pdf` only validates present optional references while preserving
  legacy absent-reference behavior; it is not a second writer.

No task introduced a second store, serializer, hash, clock, timestamp issuer,
custody, numeric/tolerance, parser, approval, resolution, verdict, repair,
publication, transport, or live-CAD authority.

## Policy and schema versions

The accepted policy/version surface is:

- numeric: `r1c-numeric-v1`
- tolerance: `r1c-tolerance-v1`
- expiry: `r1c-expiry-v1`
- object identity: `HMAC-SHA-256` / `r1c-file-identity-v1`
- source custody: `source-custody-1.0`
- Source Fusion: `source-fusion-1.0`
- Source Fusion evaluation: `source-fusion-evaluation-1.0`
- SourceBundle reference: `source-bundle-reference-1.0`
- custody reference: `source-custody-reference-1.0`
- fusion reference: `source-fusion-reference-1.0`
- evaluation reference: `source-fusion-evaluation-reference-1.0`
- locked HMAC domains: `cad-agent:r1c:file-object:v1`,
  `cad-agent:r1c:path-binding:v1`, and the approved-root domain owned by
  `source_integrity`.

Evaluation time is caller-injected and recorded as strict UTC evidence. No
ambient clock is used by the Task7 evaluation surface.

## Task evidence and review dispositions

Counts below are the accepted evidence attached to the final writer head or
its fresh current-main synthetic. Historical RED is identified separately and
is never reused as GREEN evidence.

### Task 1 — closed numeric, custody-candidate, and evaluation contracts

- Issue/PR: #91 / #92; issuance base `adcccff0eeb0974ce10a73017e1f8ecd047cd62d`.
- RED/remediation chronology: initial contract head `b607986214f506371231e4df3a0a4d778b514483`; later test-only RED `6cc96e48d2cadc49a112b65a4614294bc04d18c4`; final head `6713bb7...`.
- Final synthetic: `b18386fc959dcf8ddec4f885f5eb020705c8d557`.
- Focused GREEN: 73 passed; broader R1A/R1B: 123 passed.
- Hosted final tests run `31176431653`: 1213 passed, 15 deselected, 25 subtests; offline JUnit 1238/0/0/0.
- Hosted reuse run `31176432484`: PASS. Contract pretest 25 passed + 25 subtests; AutoCAD .NET/live NOT RUN.
- Review: final acceptance comment `5217548467` records fresh Cell3 integration audit and Cell5 PASS on the final head. Earlier Cell3/Cell5 reactivation comments `5217103575` and `5217106551` are review routing, not stale verdicts.
- Rollback: revert the bounded two-file contract commit(s); no migration and no persisted authority.

### Task 2 — opened-handle source object custody

- Issue/PR: #100 / #108; issuance base `d099ac2c8a70969c29a8c1c64a1264ee3eb41a9a`.
- RED/remediation chronology: initial RED `e162a56ce9fe40d0a4b41cf69a90a8350d782df1`; consolidated RED `6f2eb62e421ea65e96c6447b0971dd8aad31051a`; production hardening `8c3eab1...`; final test-only correction `78f8e5ee...`.
- Hosted RED run `31199668743`: 1 failed, 1301 passed, 15 deselected, 25 subtests; failure was the self-referential fixture assertion and authorized a test-only correction.
- Final synthetic: `4a82eb73a3eaa0fbae433cdd4067fb5ebacdeb2a`.
- Hosted final tests run `31225657478`: 1302 passed, 15 deselected, 25 subtests; offline JUnit 1327/0/0/0; .NET JUnit 50/0/0/0.
- Hosted reuse run `31225657484`: PASS. Windows-native custody adapter evidence PASS; AutoCAD .NET/live NOT RUN.
- Cell5 final PASS: `5223244342`; Cell3 integration PASS after dependency resolution: `5223242697`.
- Rollback: normal forward revert of the two source-integrity paths; no schema/dependency migration.

### Task 3 — bounded media adapters and strict Engineer JSON

- Issue/PR: #109 / #111; issuance base `93dbfa6ca4251499013969175bf447c71126ff72`.
- RED head `70d9b9ccf41013178e1c6d8b365dd9e9cd205430`; hosted RED run `31246476485`: 21 failed, 1303 passed, 15 deselected, 25 subtests; reuse `31246476464`: PASS.
- Production `8ce8f163ff26ec6ca90e129502fa9bc071a58b36`; final test remediation head `84c87e56546d7811aa8fad887f0808696e4d117f`.
- Final synthetic: `30113bcaa0a5544633500bb3c87a4b954c5819eb`.
- Hosted final tests run `31260895375`: 1386 passed, 15 deselected, 25 subtests; offline JUnit 1411/0/0/0; .NET 25+25.
- Hosted reuse run `31261246396`: PASS. Focused source-integrity file 145/145, Task3 cases 22/22, Task2 regressions 32/32; Ruff/diff/architecture-reuse PASS.
- Final Cell3 + Cell5 PASS is recorded in the accepted exact-tuple review comment `5226517127`; no live/private action.
- Rollback: revert only the two source-integrity paths; no parser package/schema migration.

### Task 4 — explicit locators and PDF render provenance

- Issue/PR: #115 / #116; base `da63a799c0729157770040c7c5e3036227675ce4`.
- RED head `13620679b584ecf6fb51eea98827cdfae313aae2`; RED synthetic `4d374485a8f6b343b0633bdd41564d609c966db6`; hosted RED run `31263249917`, reuse `31263249897`; result 84 failed, 1386 passed, 15 deselected, 25 subtests.
- Production `949fcb8080fc924d5f5ced2f5b08eba180b5c459`; test-hardening final head `d289e5d649963fa928601f4bfc8d68a2851e635c`.
- Final synthetic: `2aa9f952a25251bb1462622bd7b744805d1db99b`.
- Hosted final tests run `31264286932`: 1496 passed, 15 deselected, 25 subtests; offline JUnit 1521/0/0/0; Task4 source-fusion JUnit 110/110; .NET 25+25.
- Hosted reuse run `31264535925`: PASS. Cell5 final PASS is accepted at `5226834541`; Cell3 exact-tuple final review was activated at `5226786645` and the merge was accepted only after the same tuple passed. AutoCAD .NET/live NOT RUN.
- Rollback: revert the three normal Task4 commits; no migration.

### Task 5 — deterministic Primitive/Semantic projections

- Issue/PR: #123 / #146; base `b217ebfd597260d7b59badc3ffbcfbe7b1139754`.
- Latest meaningful RED head `d89c7adfd5180d00cc93daf72de7b8e42d9643e0`; hosted RED run `31296784944`: 3 failed, 1612 passed, 15 deselected, 25 subtests; Cell2/Cell5 RED PASS comments `5230098239` / `5230064259`.
- Final recovery production head `aaa49ee275ba4cca6bceea1bceb039238b0a5150`; final synthetic `a729f3e4fa1d19c2a23eb712dd31b3e726ccb65f`.
- Hosted final PR tests run `31306095190`: 1662 passed, 15 deselected, 30 subtests; offline JUnit 1692/0/0/0; .NET JUnit 50/0/0/0. Push run `31306092903`: 1566 passed, 15 deselected, 25 subtests; JUnit 1591/0/0/0.
- Hosted reuse run `31306095192`: PASS. Local source-fusion 180 passed; Task5 focused 70 passed with 110 deselected; Ruff/diff PASS.
- Cell5 final PASS `5230835252`; Cell2 final PASS `5230841175`. The final accepted behavior preserves canonical projection owners; Task9 later adds the explicitly approved legacy-lineage binding repair.
- Rollback: revert the two source-fusion paths; no data migration.

### Task 6 — deterministic unresolved conflict packets

- Issue/PR: #157 / #161; base `61445aa1d341fec2560ab29a29473d83d82885ff`.
- RED head `ac231cd42e17c7cddb7084479e6c1b284664e690`; hosted RED run `31308806672`: 4 failed, 1662 passed, 15 deselected, 30 subtests; reuse `31308806695`: PASS; .NET 25+25.
- Production chronology: `4b015e2c9d8cb3dd5723273c7ba5299c4d33180d`; subsequent test-only and forward repair commits culminated in final head `27ddb4d66e77d5d7c0a292bf52b1be7385593d75`.
- Final synthetic: `5ae764e16b5382948b6fd5bfb15c663da4a383f3`.
- Hosted final tests run `31314721508`: 1702 passed, 15 deselected, 30 subtests; offline JUnit 1732/0/0/0; .NET JUnit 50/0/0/0. Hosted reuse `31314721495`: PASS.
- Local final focused Source Fusion 207 passed, Task6 focused 27 passed, local full 1688 passed with 16 environment skips; hosted Ruff/architecture/side-effect gates PASS.
- Production unlock: Cell2 `5231138519` and Cell5 `5231137519`; final affected-delta Cell5 PASS `5231714442`, Cell2 PASS `5231716446`.
- Conflicts remain unresolved blocking evidence only; no approval/resolution/verdict authority was added.
- Rollback: remove the Task6 appended source-fusion surface with a normal revert; no migration.

### Task 7 — injected evaluation-time evidence and reuse gate

- Issue/PR: #162 / #163; base `1425f4697ab0813deff1b154b35c06da74df056b`.
- RED head `dfd0c46c73d6a03c158b5fa94908b6de3b55baf4`; synthetic `b4f58a25a3e3fb2d1fca467fc27372ed5d881c47`; hosted RED `31317509564`: 15 failed, 1704 passed, 15 deselected, 30 subtests; reuse `31317509559`: PASS; .NET 25+25.
- RED review PASS: Cell5 `5231992798`, Cell2 `5231993993`; production unlock `5231995395`.
- Production head `a2f3108ae84269337418d4fb23cf4df1d4b8be34`; final synthetic `02a17b5edf87d109d4af7405ca48d1393ab509cd`.
- Hosted final tests run `31318487661`: 1719 passed, 15 deselected, 30 subtests; duplicate push run `31318486371` same result; .NET 25+25.
- Hosted reuse final `31318705554`: PASS. Local exact two-path suite 369 passed; Ruff/architecture/side-effect checks PASS.
- Final Cell2 PASS `5232063699`; Cell5 PASS `5232064744`.
- Only the two evaluation APIs were added; existing injected-time/expiry/evaluation/hash and Task6 packet owners remain authoritative.
- Rollback: revert `a2f3108...`; no persisted-store/schema migration.

### Task 8 — compact manifest/PDF references

- Issue/PR: #165 / #166; base `d2cb34475172b29f2cc1e13c18bfe6666944e98a`.
- RED head `7016310a254659393fbad014497daf0509baf7e6`; synthetic `ed040558a1e0c8568def7bcb8db71767baf6421f`; hosted RED `31319646345`: 20 failed, 1723 passed, 15 deselected, 30 subtests; reuse `31319646208`: PASS; .NET 25+25.
- RED review: Cell3 PASS `5232151600`, Cell5 initial PASS `5232157001`; a later Cell5 coverage CHANGES_REQUIRED `5232165374` was historical and superseded by the bounded RED hardening before production.
- Production head `75669c8a56e1271dd01c1d8bd4b98bf6dbe3ee77`; final synthetic `0a88647f7e92383d8e151cab8af50b271c64f8e4`.
- Hosted final tests `31320081505` and push `31320078844`: 1743 passed, 15 deselected, 30 subtests; offline JUnit 1773/0/0/0; .NET 25+25.
- Hosted reuse `31320081514`: PASS. Focused Task8/SourceBundle 60 passed; source-integrity/source-fusion regression 369 passed; Ruff/diff PASS.
- Final Cell5 PASS `5232191756`; Cell3 PASS `5232192432`.
- Three reference schemas are closed, optional, compact, deep-copied, and bound through the sole manifest writer; PDF validates only present references.
- Rollback: normal revert of manifest/PDF/test paths; legacy absent-reference manifests require no migration.

### Task 9 — security, determinism, and boundary hardening

- Issue/PR: #167 / #168; base `fbc30bc3b7a2e7dab9aa4c5f0112d29f7e1e0625`.
- Test-only RED head `5f6068dac31bbc8817b8036f960c722c5625740c`; synthetic `9bba69ff31bebf1cf573601e71f997debb31146d`; hosted RED runs `31320825570` and `31320841169`: 1 failed, 1759 passed, 15 deselected, 30 subtests; reuse `31320841168`: PASS; .NET 25+25.
- RED review PASS: Cell3 `5232269372`; Cell5 `5232268079`; production unlock `5232270878`.
- Proven defect: primitive identity did not bind canonical `legacy_ids` lineage. Forward repair head `103a6a335ace388fccd4a39bfeaf857129d43498`; synthetic `a7f25526414106ac527d1ae51b71a99ea6647742`.
- Local focused authorized tests 386 passed; full R1 533 passed; Ruff, architecture, diff, and exact-path audits PASS.
- Hosted GREEN `31321412974`: 1760 passed, 15 deselected, 30 subtests; offline JUnit 1790/0/0/0; .NET 25+25; live NOT RUN. Final reuse `31321600931`: PASS.
- Final Cell5 PASS `5232328147`; Cell3 PASS `5232329324`.
- The fourth allowed production path, `cad_agent/source_integrity.py`, remained byte-identical; no new API, hash, serializer, store, clock, or authority was added.
- Rollback: normal forward revert of the Task9 repair; no migration and no history rewrite.

## Verification and exact Task10 audit

Task10 must be verified from the exact base `90881e351d1ce6a8a55f877800af5211659020cd` after the record is created:

```powershell
git diff --name-only 90881e351d1ce6a8a55f877800af5211659020cd...HEAD
git diff --check 90881e351d1ce6a8a55f877800af5211659020cd...HEAD
```

The expected result is exactly:

```text
docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md
```

Where the repository verifier is available, run the offline form:

```powershell
.\scripts\verify.ps1 -SkipAutoCADDotNet
```

Task10 is documentation-only, so runtime test counts above remain the accepted
hosted evidence for Tasks 1–9. Any local verifier limitation must remain
`NOT RUN` rather than being promoted to PASS. The Task10 draft PR must remain
DRAFT and must not be marked ready or merged.

## Migration, rollback, and retained locks

No R1C task introduced a persisted migration or dependency/workflow migration.
Rollback is a normal forward revert of the task's bounded paths; no rebase,
amend, squash, reset, force-push, or history rewrite is part of the chain.
Legacy absent optional references remain valid, and no source bytes or
customer/private evidence are rewritten.

The following remain **NOT RUN / LOCKED** at Task10 handoff:

- AutoCAD Mechanical live execution and AutoCAD .NET live gate;
- AutoCAD/File IPC;
- S2C and S3B execution;
- derived/private/customer CAD and private-data gates;
- approval, resolution, verdict, repair, and publication authority;
- external model/provider/SDK live execution, OCR, and network/subprocess
  authority outside the accepted offline verifier boundary.

## Terminal state

`TASK10 DRAFT HANDOFF — STOP_WRITE`

The record is ready for independent review on the exact one-path Task10 head.
Luna retains merge/ready authority. No runtime code/test changes, no merge or
ready transition, and no live/private action were performed.
