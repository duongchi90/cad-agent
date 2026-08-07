# R1C Source Integrity and Deterministic Fusion Design

## Status and authority

- Issue: #71
- Draft PR: #78
- Exact planning base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`
- Planning branch: `planning/w1b-r1c-source-integrity-fusion`
- Previous reviewed head: `7b697afc06702c0b0756423b760363c12af73094`
- Independent source-integrity red-team: Issue #77
- Master PO follow-up authorization: Issue #71 comment `5207419725`
- This document is planning/design only.
- Runtime implementation remains locked until this planning PR is accepted and a separate runtime Issue supplies an exact base, branch, allowlist, policy values, and verification gates.

No model call, OCR expansion, AutoCAD/File IPC mutation, component/view registry, candidate revision, repair, visual verdict, engineering approval, or publication authority is introduced.

## Decision summary

R1C is an adjacent, pure-Python evidence boundary around the accepted R1A `SourceBundle`, accepted R1B manifest binding, current Primitive/Semantic IR artifacts, and the existing `cad_agent` run-manifest/checkpoint owner.

R1C preserves `source-bundle-1.0` unchanged and defines three closed derived records:

1. `source-custody-1.0` — approved-root revision, stable bytes, bounded media observations, opaque file-object identity, path binding, aliases, duplicate bytes, and blocking custody states.
2. `source-fusion-1.0` — explicit page/region/render provenance, deterministic UUID-independent Primitive/Semantic projections, evidence groups, unresolved conflicts, and stale-state bindings.
3. `source-fusion-evaluation-1.0` — injected server-owned evaluation-time evidence used by reuse/expiry gates without reading an ambient clock.

The existing run manifest remains the sole run/checkpoint lifecycle owner and stores only small closed references to these records. R1C creates no database, source registry, approval store, conflict-resolution issuer, or second manifest.

`READY` means only that deterministic downstream reconstruction inputs are closed and no blocking conflict is present. It is never visual PASS, engineering truth, CAD acceptance, repair permission, or publication authorization.

## First-slice authority narrowing

### Conflict approval is locked

The first R1C runtime slice does not support `RESOLVED_BY_APPROVAL`, does not accept a `selected_resolution`, and does not consume or issue a source-conflict approval artifact.

Every blocking conflict has:

- `state = UNRESOLVED`;
- `blocking = true`;
- complete compared evidence references;
- deterministic subject and conflict identifiers.

A blocking conflict forces fusion status `BLOCKED_UNRESOLVED`.

The repository currently has approval-gate patterns such as `agent_lib/run.py::_validate_agent_action_approval()` and `_apply_report_with_approval()`, but those APIs are scoped to applying `AgentReport` actions. They are not a generic source-conflict approval issuer, durable approval owner, or source-conflict contract. Reusing them would broaden their authority and is rejected.

A future prerequisite Issue must establish all of the following before approval-based conflict resolution can be designed or enabled:

- exact approval owner and repository path;
- closed schema and schema version;
- issuer and validator API signatures;
- approval identity and canonical hash;
- exact conflict, evidence, SourceBundle, custody, fusion-input, run, and scope bindings;
- allowed closed resolution variants and fields;
- tests for issuance, validation, stale state, expiry, and replay;
- storage/lifecycle ownership without duplicating the manifest;
- Master PO authorization.

The missing source-conflict approval issuer is classified `NEW_MISSING_CAPABILITY` outside the R1C first-slice authority.

## Goals

R1C must:

- verify approved source bytes without changing them;
- prove the opened object remains contained under the approved root after open;
- bind an approved-root revision and identity-key revision to custody evidence;
- separate opaque file-object identity from path containment/binding;
- distinguish hardlink/same-object aliases from independent files with duplicate bytes;
- preserve source roles without allowing count, confidence, parser, or ordering to choose truth silently;
- bind PDF page, selected box, rotation, user unit, render matrix, raster, region, view, and sheet identity explicitly;
- project Primitive/Semantic observations into deterministic identities excluding UUIDs, handles, timestamps, filesystem order, and locale;
- bind current Semantic artifacts to Primitive artifacts using existing manifest/checkpoint hashes without requiring optional producer fields;
- apply one exact numeric canonicalization policy to every numeric value participating in hashes, grouping, locators, and conflicts;
- preserve deterministic unresolved conflicts and stale states;
- use injected, recorded evaluation-time evidence rather than ambient `now()`;
- remain testable with synthetic inputs and no AutoCAD session.

## Non-goals

R1C does not:

- discover or crawl files outside an approved intake root;
- trust filenames, extensions, labels, or path strings as byte or object identity;
- change R1A/R1B schemas;
- create a CAS, database, source registry, approval store, or checkpoint owner;
- perform OCR, recognition, geometric solving, CAD truth parsing, visual comparison, or model inference;
- modify Primitive/Semantic producers, CLI behavior, AutoCAD/File IPC, or accepted source CAD in the first runtime slice;
- resolve engineering conflicts automatically or through approval;
- read the ambient wall clock inside canonical fusion or reuse validation;
- publish absolute paths, raw device/volume/file identifiers, secret key material, customer content, or parser exception details.

## Internal reuse dossier

### R1A SourceBundle — `REUSE_AS_IS`

Owner and APIs:

- `cad_agent/source_bundle.py`
- `SOURCE_BUNDLE_SCHEMA_VERSION`
- `validate_source_bundle(payload)`
- `build_source_bundle(...)`
- `source_bundle_sha256(payload)`

Tests/evidence:

- `tests/test_cad_agent_source_bundle.py`
- `tests/fixtures/source-bundle.json`
- `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

R1A remains the declared-source metadata contract. R1C does not add observed filesystem, custody, fusion, approval, or verdict fields to it.

### Canonical JSON hashing — `REUSE_AS_IS`

Owner/API:

- `cad_agent/drawing_contracts.py::canonical_json_sha256()`

R1C reuses this helper after every numeric value has been converted to the closed R1C canonical representation. Non-finite values are rejected before hashing.

### R1B manifest binding — `EXTEND_WITH_ADAPTER`

Owner/APIs:

- `cad_agent/manifest.py`
- `validate_source_bundle_reference(value)`
- `bind_source_bundle(manifest, source_bundle)`
- `require_source_bundle_match(manifest, source_bundle)`
- `sha256_file(path)`
- `read_manifest(path)` / `write_manifest(path, manifest)`
- `verify_source(manifest, source)`
- `completed_artifact(output_dir, stage)`
- `cad_agent/pdf.py::read_pdf_manifest(path)`

Tests:

- `tests/test_cad_agent_source_bundle_manifest.py`
- `tests/test_cad_agent_cli.py`
- `tests/test_cad_agent_pdf.py`

R1C follows the optional closed-reference and unequal-rebind refusal pattern. Full custody/fusion/evaluation arrays are not copied into the manifest.

### Windows final-handle concepts — `PORT_BOUNDED_LOGIC`

Reference owner:

- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs`

R1C ports only bounded concepts: read-only handle ownership, final-path-by-handle, file information by handle, post-open containment, reparse refusal, and identity comparison before/after inspection. It does not copy AutoCAD policy or create a general second path-policy owner.

### Primitive IR — `EXTEND_WITH_ADAPTER`

Owners:

- `primitive_ir_lib/models.py::{SourceDocument, Trace, Calibration, Primitive, PrimitiveIRDocument}`
- `primitive_ir_lib/run_image.py::run()`
- `primitive_ir_lib/run_pdf.py::run_pdf()`

R1C reads accepted artifacts and projects deterministic observation content. Legacy IDs remain lookup labels only and never enter canonical identity, sorting, grouping, or conflict IDs.

### Semantic IR — `EXTEND_WITH_ADAPTER`

Owners:

- `semantic_ir_lib/models.py::{PrimitiveIRRef, SemanticPart, Constraint, SemanticIRDocument}`
- `semantic_ir_lib/assemble.py::build_semantic_document()`
- `semantic_ir_lib.constraint_pruning.prune_constraints()`
- `semantic_ir_lib.constraint_solving.solve_constraints()`

`PrimitiveIRRef.sha256` is optional, and current producers normally emit filename/count without SHA-256. R1C binds Semantic artifacts externally to the Primitive checkpoint hash in the existing manifest, validates filename/count, and validates the optional SHA only when present.

### Manifest/checkpoint and approval boundaries

The existing manifest remains sole run/checkpoint owner. Existing calibration approval and draft-reference behavior remain unchanged.

No accepted source-conflict approval owner exists. Agent action approval APIs are inspected as a pattern but explicitly not reused or broadened. Approval-based source-conflict resolution remains locked.

## External reuse dossier

First-slice decisions:

| Candidate | Version/basis | Classification | Decision |
|---|---|---|---|
| Python 3.11 `hashlib`, `hmac`, `json`, `os`, `pathlib`, `stat`, `ctypes`, `msvcrt`, `decimal` | supported runtime | `REUSE_AS_IS` | Hashing, HMAC, bounded filesystem adapter, strict JSON, and numeric canonicalization. |
| Pillow | locked `12.3.0` | `EXTEND_WITH_TEST` | Read-only image observations only; decompression-bomb warnings/errors block; never save/convert. |
| pypdf | locked `6.14.2` | `EXTEND_WITH_TEST` | Strict bounded PDF structure/page observations; no rewrite/decrypt/text authority. |
| ezdxf | locked `1.4.4` | `SPIKE_ONLY` | Not used in first slice; header-only DXF observation remains project-owned. |
| PyMuPDF as a new R1C parser | locked but separately governed | `REJECT` | Do not create a second PDF custody authority or expand license exposure. |
| `filetype` / `python-magic` / libmagic | not accepted for R1C | `REJECT` | Avoid stale package/native DLL/database deployment and a second media authority. |
| New CAS/database/source store | none | `REJECT` | Duplicates manifest/checkpoint/storage authority. |

No new dependency or lock-file change is required.

## Closed `source-custody-1.0` contract

### Root fields

- `schema_version`
- `bundle_id`
- `run_id`
- `source_bundle_sha256`
- `approved_root_id`
- `approved_root_revision`
- `approved_root_configuration_sha256`
- `identity_scheme`
- `identity_scheme_version`
- `identity_key_revision`
- `numeric_policy_version`
- `status`
- `eligible_count`
- `blocking_count`
- `items`
- `alias_groups`

Statuses:

- `READY`
- `BLOCKED`

Expected per-item failures produce one sanitized complete `BLOCKED` artifact. Malformed input, missing server-owned identity context, inability to prove final-handle containment, or internal invariant failure raises `SourceIntegrityError` and publishes no artifact.

Fusion accepts only exact `READY` custody with `blocking_count = 0`.

### Server-owned identity context

The caller injects an approved-root context containing:

- `approved_root_id`;
- `approved_root_revision`;
- normalized server-owned root path;
- `identity_scheme = HMAC-SHA-256`;
- `identity_scheme_version = r1c-file-identity-v1`;
- opaque key material held outside artifacts;
- `identity_key_revision`;
- policy limits.

`cad_agent.source_integrity` consumes key material for domain-separated HMAC and never stores, logs, returns, or hashes the key itself into public artifacts. The key remains owned by server/process configuration; R1C adds no secret store. Key/namespace revision change makes previous identity/path bindings stale.

### Separate object and path evidence

Each eligible item contains:

- `file_object_identity_token`;
- `path_binding_sha256`;
- `identity_scheme`;
- `identity_scheme_version`;
- `identity_key_revision`;
- `approved_root_revision`.

`file_object_identity_token` is:

```text
HMAC-SHA-256(
  key,
  domain="cad-agent:r1c:file-object:v1",
  identity_scheme_version,
  identity_key_revision,
  opened-handle volume identity,
  opened-handle file identity
)
```

It contains no path or byte hash. Hardlinks to the same filesystem object produce the same object token.

`path_binding_sha256` is:

```text
HMAC-SHA-256(
  key,
  domain="cad-agent:r1c:path-binding:v1",
  approved_root_configuration_sha256,
  approved_root_revision,
  normalized final relative path,
  file_object_identity_token
)
```

It proves path/root containment separately. The canonical absolute root/source path, raw volume/file identity, and HMAC key never enter artifacts or logs.

### Alias and duplicate semantics

- `SAME_FILE_ALIAS`: two source IDs share `file_object_identity_token`; detected by object identity, independent of path.
- `DUPLICATE_BYTES`: two different object tokens share `observed_sha256`; detected by bytes, not called alias.
- Hardlink paths: same object token, distinct path bindings.
- Copy: different object tokens, potentially same byte hash.
- Same object moved/rebound to another path: object token stable, path binding changes.
- Root remap/revision/key rotation: path/config evidence changes and previous custody becomes stale.

Alias groups contain deterministic group type, sorted source IDs, byte hash, object tokens, and path bindings. Source roles remain separate; duplicate count confers no authority.

### Item fields

Each item contains:

- source identity/role fields copied from normalized R1A;
- declared and observed SHA-256;
- bounded media observations;
- `file_object_identity_token` or `null`;
- `path_binding_sha256` or `null`;
- identity scheme/version/key revision;
- approved-root revision;
- alias group reference or `null`;
- custody state and sanitized blocking code.

Allowed custody states include `VERIFIED`, `DUPLICATE_BYTES`, `SAME_FILE_ALIAS`, `MISSING`, `PATH_ESCAPE`, `REPARSE_POINT`, `FINAL_PATH_OUTSIDE_ROOT`, `UNSUPPORTED_MEDIA`, `MEDIA_MISMATCH`, `HASH_MISMATCH`, `CHANGED_DURING_READ`, `IDENTITY_CHANGED`, `UNREADABLE`, and `RESOURCE_LIMIT`.

Only `VERIFIED` and fully explained independent-object `DUPLICATE_BYTES` are eligible in the first slice. `SAME_FILE_ALIAS` blocks by default.

## Source custody flow

For each item:

1. Validate R1A and injected approved-root/identity context.
2. Reject lexical escape, absolute/UNC/device paths, alternate data streams, empty components, and unsupported normalization before open.
3. Reject symlink/junction/mount/reparse traversal.
4. Open the final file read-only with a custody-owned handle.
5. Obtain final path and object identity from the opened handle.
6. Prove final containment under the exact approved root.
7. Capture initial object identity and size.
8. Stream first byte SHA-256.
9. Parse media through a duplicated handle or bounded operation-owned snapshot.
10. Stream second SHA-256 on the original custody handle.
11. Re-read final path, object identity, size, and containment.
12. Require hashes, size, object identity, and containment to remain unchanged.
13. Compare bytes/media against R1A declarations.
14. Compute separate object token and path binding.
15. Build alias/duplicate groups and sanitized state.

There is no fallback to pre-open `Path.resolve()`, filename, extension, or `samefile()` when final-handle evidence is unavailable.

## Parser isolation and media observations

The original custody descriptor remains under R1C control. Parser adapters receive a duplicated read-only handle or bounded operation-owned snapshot. Snapshot hash must equal the first source hash; it lives only under the current run temporary area and is removed on success/failure. The source is always second-hashed and identity-checked afterward.

Engineer JSON requires strict UTF-8, duplicate-key refusal, non-standard constant refusal, finite values, object root, and explicit depth/key/array/string/byte limits. Original byte SHA remains custody authority.

## R1C canonical numeric policy

All numeric fields entering a custody/fusion/evaluation digest, observation key, locator, evidence group, or conflict use `r1c-numeric-v1`.

### Conversion sequence

1. Identify quantity kind and declared unit.
2. Convert to the canonical unit using an exact `Decimal` conversion factor from the policy table.
3. Reject NaN, Infinity, missing unit, unsupported unit, and values outside the stated range.
4. Quantize using `decimal.ROUND_HALF_EVEN` and the quantity scale.
5. Convert negative zero to zero.
6. Serialize as locale-independent fixed-point decimal text, never exponent notation.
7. Remove insignificant trailing zeros and a trailing decimal point; zero serializes exactly as `"0"`.

Float input is converted with `Decimal(str(value))`, not the binary representation. Booleans are not numeric.

### Quantity table

| Quantity | Canonical unit | Quantum | Inclusive range |
|---|---|---:|---:|
| CAD/image physical length, measurement, tolerance | mm | `0.001` | `-1000000000` to `1000000000` |
| PDF coordinate/box length | pt | `0.001` | `-1000000000` to `1000000000` |
| Pixel coordinate/dimension | px integer | `1` | `0` to `2147483647` |
| Angle/rotation | degree | `0.000001` | `-360000` to `360000` |
| Unitless confidence/quality | unitless | `0.000001` | `0` to `1` |
| DPI/resolution | dpi | `0.001` | `0.001` to `1000000` |
| Affine/render matrix coefficient | unitless | `0.000000001` | `-1000000000` to `1000000000` |
| Scale/calibration ratio | declared canonical ratio | `0.000000001` | `-1000000000` to `1000000000` |

Exact conversion factors include `1 in = 25.4 mm`, `1 cm = 10 mm`, `1 m = 1000 mm`, and `1 pt = 1/72 in`. Unsupported implicit conversions are rejected.

### Equality and conflict order

Hash/group equality is exact equality of canonical quantity kind, canonical unit, policy version, and canonical decimal text.

Engineering conflict comparison is separate:

1. canonicalize both values;
2. require the same quantity kind and canonical unit;
3. load an explicit tolerance and `tolerance_policy_version` from the approved input contract;
4. canonicalize that tolerance under `r1c-numeric-v1`;
5. compare absolute canonical difference;
6. difference `<= tolerance` is within tolerance; difference `> tolerance` is conflicting.

Tolerance never changes a digest or collapses distinct evidence. It only determines conflict classification. Missing/invalid tolerance blocks rather than using a default.

## Closed `source-fusion-1.0` contract

Root fields:

- schema/run/bundle/custody/root bindings;
- `numeric_policy_version`;
- explicit page and region locators;
- PDF render provenance;
- Primitive/Semantic observations;
- evidence groups;
- conflicts;
- `fusion_input_sha256`;
- `status`.

No `resolution_references`, `selected_resolution`, approval status, approval expiry, or approval issuer field exists in the first-slice contract.

Statuses:

- `READY`
- `BLOCKED_UNRESOLVED`
- `STALE`

`fusion_input_sha256` covers canonical bundle/custody/root/locator/render/provenance/numeric-policy/conflict content. All arrays are sorted by deterministic content keys.

## Explicit page/region/render provenance

R1A page/region IDs are labels only; no mapping is inferred from sorting or filenames.

Pixel coordinates use `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`, bind exact raster SHA/dimensions, and require integer pixel coordinates.

PDF coordinates use `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`, bind page locator, selected media/crop box, normalized rotation, user unit, and `r1c-numeric-v1` decimal values.

PDF Primitive provenance binds the complete chain:

```text
custody PDF SHA
→ explicit page index/locator
→ selected box, rotation, user unit
→ render DPI and canonical matrix
→ rendered raster SHA and dimensions
→ Primitive artifact SHA
→ Primitive source-document SHA/dimensions/page index
→ trace/observation projection
```

Direct-image provenance requires Primitive source-document SHA/dimensions to equal custody observations.

## Deterministic Primitive/Semantic provenance

Legacy UUIDs, handles, timestamps, and list order are lookup information only.

Primitive observation keys hash a closed projection containing source/render binding, primitive type, source/layer, canonical geometry/text, confidence, trace, calibration, and numeric policy version.

Semantic observation keys hash closed part/constraint projections using deterministic Primitive observation keys plus canonical semantic properties. Current Semantic filename/count and optional SHA compatibility is validated against existing manifest checkpoint hashes.

Identical closed observations form deterministic multisets with occurrence counts. If legacy Semantic references cannot distinguish an intended subset of identical observations, R1C emits `DUPLICATE_OBSERVATION_AMBIGUITY` rather than guessing.

## Deterministic conflicts

Conflict IDs hash:

- conflict type;
- deterministic subject key;
- sorted compared evidence hashes;
- canonical compared values/units;
- numeric and tolerance policy versions;
- source bundle/custody/root/fusion-input context.

Roles affect display order only. Source count, confidence, parser preference, and caller order never discard evidence or choose a winner.

First-slice conflict state is only `UNRESOLVED`. Blocking conflicts force `BLOCKED_UNRESOLVED`.

## Closed `source-fusion-evaluation-1.0` contract

Evaluation is separate from time-independent fusion content.

Fields:

- `schema_version = source-fusion-evaluation-1.0`;
- `run_id`;
- `source_fusion_sha256`;
- `fusion_input_sha256`;
- `evaluation_time_utc`;
- `evaluation_time_source`;
- `evaluation_time_evidence_sha256`;
- `expiry_policy_version`;
- `evaluated_reference_hashes`;
- `status`;
- `blocking_codes`.

`evaluation_time_utc` is an injected RFC 3339 UTC value with exactly six fractional digits and `Z`. It is never read from `datetime.now()`, `time.time()`, filesystem timestamps, or local timezone inside canonical validation.

`evaluation_time_source` is a closed identifier for the server-owned source. `evaluation_time_evidence_sha256` binds the recorded clock/evaluation packet supplied by that source. `expiry_policy_version` identifies exact inclusive/exclusive boundary rules.

For policy `r1c-expiry-v1`:

- valid when `issued_at_utc <= evaluation_time_utc < expires_at_utc`;
- exactly at expiry is expired;
- all values must be normalized UTC with microsecond precision;
- clock rollback is not inferred or corrected; changed evaluation evidence produces a distinct evaluation record;
- replay with identical fusion and evaluation evidence produces identical output/hash.

The first slice uses evaluation evidence only for deterministic reuse/stale gates that already have recorded expiry fields. Approval resolution remains locked. Fusion canonical status does not change merely because wall time advances; a new evaluation record may refuse reuse without rewriting the original fusion artifact.

## Manifest integration

The existing manifest owner may later bind optional references:

- `source_custody` — bundle/root/key revision, custody hash, status/counts;
- `source_fusion` — bundle/custody/root, numeric policy, fusion-input/fusion hashes, status/conflict counts;
- `source_fusion_evaluation` — fusion/evaluation hashes, time-source/policy versions, status.

Absent keys remain absent. Equal rebinding is idempotent; unequal rebinding fails closed. Full evidence arrays and key material are never stored in the manifest.

## Failure and stale behavior

- Source byte/object/path/root/key revision change invalidates custody.
- Locator/render/Primitive/Semantic/numeric/tolerance policy change invalidates fusion.
- Evaluation-time evidence/policy change invalidates only the evaluation reference, not the immutable fusion artifact.
- Malformed or unsupported evidence raises a closed error without private details.
- Blocking expected observations produce `BLOCKED` custody or `BLOCKED_UNRESOLVED` fusion.
- No stale evidence is silently refreshed, resolved, or promoted.

## Security and privacy invariants

- No source write path.
- No network, subprocess, model, OCR, AutoCAD, or File IPC dependency.
- No ambient clock in canonical fusion/evaluation validation.
- No raw path/device/file identity/key material in artifacts, logs, or exceptions.
- HMAC domains are distinct for object identity and path binding.
- Key revision/namespace rotation produces stale evidence and requires new custody.
- Operation-owned temporary snapshots are bounded and always cleaned.

## Future runtime file map

Proposed first-slice runtime allowlist, subject to a separate exact runtime Issue:

Create:

- `cad_agent/source_integrity.py`
- `cad_agent/source_fusion.py`
- `tests/test_cad_agent_source_integrity.py`
- `tests/test_cad_agent_source_fusion.py`
- `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

Modify:

- `cad_agent/manifest.py`
- `cad_agent/pdf.py`
- `tests/test_cad_agent_source_bundle_manifest.py`

Explicitly unchanged:

- `cad_agent/source_bundle.py`
- `cad_agent/cli.py`
- `primitive_ir_lib/**`
- `semantic_ir_lib/**`
- `agent_lib/**`
- `dxf_builder_lib/**`
- `mcp_integration_lib/**`
- `autocad_plugin/**`
- requirements/locks/workflows
- `docs/STATUS.md`
- `docs/HANDOFF.md`

## Verification design

Synthetic tests must cover:

- source mutation/replacement and final-handle containment;
- hardlink, move, copy, same bytes/different object, same object/different path, and root remap;
- key revision rotation and opaque token privacy;
- parser isolation and strict JSON/PDF/image limits;
- explicit page/region/render lineage;
- UUID/list-order invariant Primitive/Semantic projections;
- equivalent units, int/float equivalence, halfway `ROUND_HALF_EVEN`, negative zero, range overflow, tolerance boundary, permutation, repeated serialization, and Windows/Linux canonical numeric consistency;
- conflicts remain unresolved and no approval-resolution field/API exists;
- evaluation before/exactly-at/after expiry, timezone normalization, precision, rollback evidence, replay, and changed evaluation evidence;
- no ambient clock call in canonical fusion/evaluation paths;
- legacy manifest compatibility and one-owner lifecycle.

No local AutoCAD session is required. AutoCAD Mechanical live, hosted AutoCAD .NET, and private-data gates remain `NOT RUN` unless separately authorized.

## Migration and rollback

This planning PR changes documentation only. Revert its bounded planning commits or close PR #78 to roll back.

A future runtime implementation is additive: legacy manifests without R1C references remain valid. Rollback removes optional references/artifacts and restores the previous runtime code; it never rewrites R1A or source bytes.

## Acceptance criteria

Planning is acceptable only when:

- first-slice approval resolution is explicitly locked;
- evaluation time is injected, recorded, hash-bound, and ambient-clock independent;
- every canonical numeric quantity follows `r1c-numeric-v1`;
- object identity and path binding are separate, opaque, domain-separated, and server-keyed;
- SourceBundle and manifest ownership remain unchanged;
- design and implementation plan use identical fields, interfaces, statuses, file map, and tests;
- cumulative PR diff remains exactly the two Issue #71 planning files;
- fresh hosted checks and Cell 5 exact-head re-review are recorded;
- PR remains OPEN/DRAFT for Master PO review.
