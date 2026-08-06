# R1C Source Integrity and Deterministic Fusion Design

## Status and authority

- Issue: #71
- Exact planning base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`
- Planning branch: `planning/w1b-r1c-source-integrity-fusion`
- Draft PR: #78
- Independent source-integrity red-team: Issue #77
- This document is planning/design only.
- R1C runtime implementation remains locked until this planning PR is accepted and a separate runtime Issue supplies an exact base, branch, allowlist, and gates.
- No model call, AutoCAD mutation, OCR expansion, component/view registry, candidate revision, repair, visual verdict, engineering approval, or publication authority is introduced.

## Decision summary

R1C is an adjacent, pure-Python evidence adapter around the accepted R1A `SourceBundle`, the accepted R1B SourceBundle-to-manifest binding, existing Primitive/Semantic IR artifacts, and the existing `cad_agent` manifest/checkpoint owner.

R1C preserves `source-bundle-1.0` unchanged and creates two closed derived artifacts:

1. `source-custody-1.0` proves approved-root configuration, stable source bytes, privacy-safe file identity, media observations, aliases, duplicates, and blocking custody states.
2. `source-fusion-1.0` binds explicit page/region/render locators, deterministic Primitive/Semantic projections, evidence groups, conflicts, stale state, and replay-safe conflict resolutions.

The existing run manifest remains the only run/checkpoint truth store and stores only small closed references to these artifacts. The derived artifacts live under the existing run output root and never become a second database, source registry, or approval store.

`READY` means only that deterministic downstream reconstruction inputs are closed and unblocked. It is never visual PASS, engineering truth, CAD acceptance, repair permission, or publication authorization.

## Goals

R1C must:

- verify approved source bytes without changing them;
- prove the opened file remains under the approved root after open;
- bind a stable approved-root configuration revision to every custody artifact;
- distinguish same-file aliases from independent files with duplicate bytes;
- preserve source roles without allowing source count, confidence, or order to silently choose truth;
- bind PDF page, render, crop, rotation, coordinate convention, region, view, and sheet identity explicitly;
- project Primitive/Semantic observations into deterministic identities that exclude UUIDs, handles, timestamps, and list order;
- bind current Semantic IR artifacts to Primitive IR using existing manifest/checkpoint hashes without requiring an optional field that current producers omit;
- preserve conflicts and unresolved states;
- accept only replay-safe, hash-bound conflict-resolution evidence from an existing external approval owner;
- fail closed on changed source, changed root mapping, changed file identity, stale evidence, ambiguous duplicate observations, and parser disagreement;
- remain testable with synthetic files and no AutoCAD session.

## Non-goals

R1C does not:

- discover or crawl files outside an approved intake root;
- trust filenames, extensions, R1A labels, or path strings as byte identity;
- change R1A or R1B schema versions;
- create a content-addressable store, database, source registry, or checkpoint owner;
- perform OCR, recognition, geometric solving, CAD parsing authority, visual comparison, or model inference;
- modify Primitive IR, Semantic IR, CLI producers, AutoCAD/File IPC, or accepted source CAD in the first runtime slice;
- automatically resolve engineering conflicts;
- treat an engineer `DECISION` source as an approval;
- publish private absolute paths, raw filesystem identity, customer content, or parser exception details.

## Internal reuse dossier

### R1A SourceBundle — `REUSE_AS_IS`

Owner and APIs:

- `cad_agent/source_bundle.py`
- `SOURCE_BUNDLE_SCHEMA_VERSION`
- `validate_source_bundle(payload)`
- `build_source_bundle(...)`
- `source_bundle_sha256(payload)`

Tests and evidence:

- `tests/test_cad_agent_source_bundle.py`
- `tests/fixtures/source-bundle.json`
- `docs/superpowers/implementation-records/2026-08-05-source-bundle-offline.md`

R1A remains the declared-source metadata contract. It owns source ID, kind, role, safe relative path, declared SHA-256, declared media type, page/region labels, capture time, and coarse quality. R1C does not add filesystem, custody, fusion, approval, or verdict behavior to it.

### Canonical JSON hashing — `REUSE_AS_IS`

Owner and API:

- `cad_agent/drawing_contracts.py::canonical_json_sha256()`

The helper already provides sorted, compact UTF-8 canonical JSON hashing and rejects non-finite numeric values. R1C reuses it for closed configuration, identity, observation, conflict, resolution, custody, and fusion projections.

### R1B manifest binding — `EXTEND_WITH_ADAPTER`

Owner and APIs:

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

R1C follows R1B's optional closed-reference and unequal-rebind refusal pattern. It does not copy custody/fusion arrays into the manifest.

### Windows safe-handle path and identity concepts — `PORT_BOUNDED_LOGIC`

Reference owner:

- `autocad_plugin/CadAgent.AutoCAD2027/Drawing/ExactBaseXrefPolicy.cs`
- its use of safe handles, final path resolution, file identity, reparse checks, and server-owned source revision/hash configuration

R1C ports only the bounded Windows concepts required for source intake: open a read-only handle, obtain the final path from that handle, obtain volume/file identity, prove post-open containment, reject reparse substitution, and compare identity before/after inspection. It does not copy AutoCAD-specific policy or create a second general path-policy authority.

### Primitive IR evidence — `EXTEND_WITH_ADAPTER`

Owners and APIs:

- `primitive_ir_lib/models.py::{SourceDocument, Trace, Calibration, Primitive, PrimitiveIRDocument}`
- `primitive_ir_lib/run_image.py::run()`
- `primitive_ir_lib/run_pdf.py::run_pdf()`

Tests:

- `primitive_ir_lib/tests/test_run_image.py`
- `primitive_ir_lib/tests/test_run_pdf.py`
- existing Primitive IR model/schema tests

R1C reads current artifacts and projects deterministic observation content. It does not use current UUID fields as canonical identity and does not rerun OCR or geometry extraction.

### Semantic IR evidence — `EXTEND_WITH_ADAPTER`

Owners and APIs:

- `semantic_ir_lib/models.py::{PrimitiveIRRef, SemanticPart, Constraint, SemanticIRDocument}`
- `semantic_ir_lib/assemble.py::build_semantic_document()`
- `semantic_ir_lib.constraint_pruning.prune_constraints()`
- `semantic_ir_lib.constraint_solving.solve_constraints()`

Current compatibility fact:

- `PrimitiveIRRef.sha256` is optional.
- `build_semantic_document()` creates a reference with filename and primitive count but does not normally populate SHA-256.
- `cad_agent.cli._run_semantic()` uses that current producer behavior.

R1C therefore binds Semantic IR externally to the Primitive IR checkpoint hash from the existing run manifest. It validates filename/count and validates the optional `PrimitiveIRRef.sha256` only when present.

### Run manifests, checkpoints, resume, and approvals — `EXTEND_WITH_ADAPTER`

Owners:

- `cad_agent/manifest.py`
- `cad_agent/pdf.py`
- `cad_agent/cli.py::run_stages()`
- `cad_agent/pdf.py::run_pdf_stages()`

The existing manifest remains the sole run/checkpoint lifecycle owner. Existing calibration approval and draft-reference safety behavior remains unchanged. Conflict approval is supplied by an existing external approval owner and merely validated/bound by R1C.

### Genuine missing capability — `NEW_MISSING_CAPABILITY`

No current Python owner proves every R1A item against an approved root using final-handle containment and privacy-safe identity, or emits explicit render/locator/provenance/conflict/stale evidence. This narrow gap is R1C.

## Approaches considered

### Expand `source-bundle-1.0`

Rejected. It would mix declared intake with observed evidence, break the accepted closed contract, and enlarge migration scope.

### Add a source registry or content-addressable database

Rejected. It would duplicate the existing manifest/checkpoint lifecycle and conflict with later registry/revision work.

### Adjacent custody/fusion artifacts with existing manifest references

Selected. It preserves accepted contracts and owners while adding only the missing evidence boundary.

## `source-custody-1.0` contract

### Root fields

- `schema_version`
- `bundle_id`
- `run_id`
- `source_bundle_sha256`
- `approved_root_id`
- `approved_root_configuration_sha256`
- `file_identity_scheme`
- `status`
- `eligible_count`
- `blocking_count`
- `items`
- `alias_groups`

Allowed status values:

- `READY`
- `BLOCKED`

A custody operation publishes one complete closed artifact after scanning all declared items. Expected source failures become sanitized item states and produce `status=BLOCKED`; malformed contracts, internal invariant violations, or inability to obtain required Windows final-handle evidence raise `SourceIntegrityError` and publish no artifact.

Fusion accepts only a custody artifact with `status=READY` and `blocking_count=0`.

### Approved-root binding

`approved_root_id` is a stable logical identifier. `approved_root_configuration_sha256` binds the server-owned root mapping and revision without publishing the path. It is computed from a closed server configuration projection containing:

- configuration schema/version;
- approved root logical ID;
- root revision;
- normalized server-owned root path;
- identity namespace/version;
- policy limits.

Only the hash enters custody/fusion artifacts. A root ID remapped to another path/revision produces a different configuration hash and makes prior custody stale.

### Item fields

Each item contains:

- `source_id`
- `kind`
- `role`
- `relative_path`
- `declared_sha256`
- `observed_sha256` or `null`
- `size_bytes` or `null`
- `declared_media_type`
- `observed_media_type` or `null`
- `media_metadata` or `null`
- `page_ids`
- `region_ids`
- `file_identity_scheme`
- `file_identity_sha256` or `null`
- `alias_group_id` or `null`
- `custody_state`
- `blocking_reason_code` or `null`

Allowed custody states:

- `VERIFIED`
- `DUPLICATE_BYTES`
- `SAME_FILE_ALIAS`
- `MISSING`
- `PATH_ESCAPE`
- `REPARSE_POINT`
- `FINAL_PATH_OUTSIDE_ROOT`
- `UNSUPPORTED_MEDIA`
- `MEDIA_MISMATCH`
- `HASH_MISMATCH`
- `CHANGED_DURING_READ`
- `IDENTITY_CHANGED`
- `UNREADABLE`
- `RESOURCE_LIMIT`

Only `VERIFIED` and fully explained independent-file `DUPLICATE_BYTES` items are eligible. `SAME_FILE_ALIAS` is blocking until declarations are proven compatible and the approved policy explicitly allows that alias group; the first runtime slice defaults it to blocking.

### Privacy-safe file identity

On Windows, R1C derives `file_identity_sha256` from a closed projection containing:

- `file_identity_scheme = windows-volume-file-id-v1`;
- `approved_root_configuration_sha256`;
- opened-handle volume serial;
- opened-handle file index/ID;
- final-handle normalized relative path under the approved root.

The raw volume serial, file ID, and absolute final path are never serialized or logged. The derived hash permits stale/alias checks without disclosing workstation details.

### Alias groups

Each alias group contains:

- `alias_group_id`
- `group_type`
- sorted `source_ids`
- `observed_sha256`
- sorted `file_identity_sha256s`

Allowed group types:

- `SAME_FILE_ALIAS`
- `DUPLICATE_BYTES`

A same file/hardlink identity and two independent identities with equal bytes are never conflated. Roles and source IDs remain separate; duplicate count never increases authority.

## Source custody flow

For every item:

1. Validate the R1A SourceBundle and approved-root configuration hash.
2. Reject lexical escape, absolute/UNC/device paths, alternate data streams, empty components, and unsupported Unicode/case forms before open.
3. Walk components with `lstat`/Windows attributes and reject symlink, junction, mount point, or other reparse traversal.
4. Open the final file read-only using a Windows-safe handle with sharing flags that permit normal read coexistence but no write by R1C.
5. Obtain final path and volume/file identity from the opened handle.
6. Prove the final opened path remains under the exact approved root and matches the requested relative path policy.
7. Capture initial handle identity and size.
8. Stream first SHA-256 from the custody-owned descriptor.
9. Parse media through a duplicated handle or bounded operation-owned snapshot; parser code never owns or closes the custody descriptor.
10. Stream second SHA-256 from the original custody descriptor.
11. Re-read final path, handle identity, size, and path identity.
12. Require first/second hashes, size, file identity, and final containment to remain unchanged.
13. Compare observed byte hash and media with R1A declarations.
14. Compute privacy-safe identity and alias/duplicate groups.
15. Emit one sanitized item state.

If final-handle containment or file identity cannot be proved on Windows, the item fails closed. No fallback to pre-open `Path.resolve()`, `samefile()`, filename, or extension is allowed.

## Parser isolation and media verification

R1C retains one custody-owned source descriptor. Parser adapters receive either:

- an OS/C-runtime duplicated read-only handle whose closure cannot close the custody descriptor; or
- a bounded operation-owned temporary snapshot produced from already-hashed bytes, whose SHA-256 must equal the first source hash.

A temporary snapshot:

- lives only under the current run temp area;
- is never referenced by manifests as a source;
- is removed on success/failure;
- is not a second store;
- is followed by a second hash and final-identity check of the original source.

### Images

Use locked Pillow 12.3.0 as `EXTEND_WITH_TEST`. Record format, width, height, mode, and bounded DPI observations. Treat decompression-bomb warning/error as `RESOURCE_LIMIT`. Never save, convert, transpose, thumbnail, or mutate source data.

### PDFs

Use locked pypdf 6.14.2 as `EXTEND_WITH_TEST`, with strict structural parsing. Record page count, encryption state, media/crop boxes, user unit, and normalized rotation. Encrypted, malformed, repaired-only, excessive-page, or resource-unbounded inputs fail closed. R1C performs no rewrite, decryption, text extraction authority, or PDF repair.

### Exact-base CAD

- DWG: bounded `AC10xx` header/media observation only; no new DWG parser.
- DXF: header-only first slice. Locked ezdxf 1.4.4 remains `SPIKE_ONLY`; a later read-only structure adapter requires its own focused proof and never becomes CAD truth.

### Engineer JSON

Original byte SHA-256 remains custody authority. Derived canonical JSON digest is allowed only after:

- strict UTF-8 decode;
- duplicate-key refusal via `object_pairs_hook`;
- `NaN`, `Infinity`, and `-Infinity` refusal via `parse_constant`;
- object-root requirement;
- byte, depth, key-count, array-length, and string-length limits;
- finite numeric validation.

An engineer `DECISION` record is evidence only.

## `source-fusion-1.0` contract

### Root fields

- `schema_version`
- `bundle_id`
- `run_id`
- `source_bundle_sha256`
- `source_custody_sha256`
- `approved_root_configuration_sha256`
- `page_locators`
- `region_locators`
- `render_provenance`
- `primitive_observations`
- `semantic_observations`
- `evidence_groups`
- `conflicts`
- `resolution_references`
- `fusion_input_sha256`
- `status`

Status values:

- `READY`
- `BLOCKED_UNRESOLVED`
- `STALE`

`fusion_input_sha256` hashes the canonical bundle/custody/locator/render/provenance/conflict content before applying resolutions. Conflict-resolution artifacts bind to this value to prevent replay and avoid circular dependency on the final fusion hash.

## Explicit page and region identity

R1A page/region IDs are labels only. R1C never maps them by sort order or filename convention.

### Page locator

- `source_id`
- `page_id`
- `page_index_zero_based`
- `sheet_id` or `null`
- `view_id` or `null`
- `custody_source_sha256`
- `box_kind`
- `box_bounds_pdf_points`
- `normalized_rotation_degrees`
- `user_unit`
- `pdf_coordinate_convention`

For PDF pages:

- `box_kind` is `MEDIA_BOX` or `CROP_BOX`;
- `normalized_rotation_degrees` is one of `0`, `90`, `180`, `270`;
- `pdf_coordinate_convention` is `PDF_USER_SPACE_BOTTOM_LEFT_X_RIGHT_Y_UP`;
- finite decimal values are normalized to canonical non-exponent decimal strings with no negative zero.

### Region locator

Common fields:

- `source_id`
- `region_id`
- `page_id` or `null`
- `coordinate_space`
- `locator_source_sha256`

For `PIXEL`:

- convention is `RASTER_TOP_LEFT_X_RIGHT_Y_DOWN`;
- bounds are integer pixels;
- exact raster SHA-256, width, and height are required.

For `PDF_POINT`:

- the exact page locator is required;
- box kind/bounds, user unit, rotation, origin convention, and canonical decimal bounds are required.

Every declared label has exactly one locator. Out-of-bounds, ambiguous rotated/cropped coordinates, missing raster identity, or equivalent-but-noncanonical numeric forms fail closed.

## PDF render provenance

A PDF Primitive IR is bound through a closed render-provenance record:

- custody source PDF SHA-256;
- source/page locator and page index;
- selected box kind/bounds;
- normalized page rotation and user unit;
- render DPI;
- canonical PDF-to-raster matrix;
- raster coordinate convention;
- rendered image SHA-256, width, and height;
- Primitive IR artifact SHA-256;
- Primitive IR `source_document.sha256`;
- Primitive IR source dimensions/page index.

The Primitive IR source-document hash must equal the rendered raster hash, not the PDF byte hash. The render record proves the PDF-to-page-to-raster-to-Primitive chain.

For a direct image source, Primitive IR `source_document.sha256` must equal the custody observed source hash and dimensions must match custody metadata.

Wrong page, wrong DPI, wrong crop/rotation, wrong matrix, wrong raster hash, or wrong Primitive source-document hash makes fusion stale or blocked.

## Deterministic Primitive provenance

Current Primitive IDs use UUIDs and are not canonical identity. R1C computes a closed `primitive_observation_sha256` from a projection excluding:

- `id`;
- `handle`;
- extraction timestamps;
- validation notes/status that are not approved evidence;
- list position.

The projection includes the source/render binding, primitive type/source/layer, normalized geometry or text content, confidence, trace bounds, and calibration projection/hash.

Canonical arrays sort by observation digest and closed content. Equivalent Primitive artifacts rebuilt with different UUIDs or list order must produce the same fusion hash.

For exactly identical observation projections:

- R1C creates one duplicate-observation group with `observation_sha256` and `occurrence_count`;
- canonical occurrence labels are `observation_sha256:0001` through the count;
- labels are interchangeable and do not depend on legacy UUIDs;
- a Semantic artifact that selects only a strict subset of indistinguishable duplicates is `DUPLICATE_OBSERVATION_AMBIGUITY` and blocks fusion unless additional stable evidence distinguishes them.

Legacy UUIDs may appear only in a non-authoritative diagnostic map outside canonical identity when policy allows; they do not participate in sorting, conflict IDs, or hashes.

## Deterministic Semantic provenance

R1C computes semantic observation digests from closed projections excluding semantic UUIDs and input order.

Binding rules:

- the supplied Semantic artifact file hash must match the existing manifest/checkpoint hash;
- the externally supplied Primitive artifact hash must match the Primitive checkpoint hash associated with that Semantic stage;
- `PrimitiveIRRef.file_name` and `primitive_count` must match the bound Primitive artifact;
- optional `PrimitiveIRRef.sha256`, when present, must equal the bound Primitive artifact hash;
- omission of the optional SHA remains compatible and is not itself a failure;
- part/constraint primitive references are converted from legacy IDs to deterministic Primitive observation digests/multiplicities;
- unresolved mapping to indistinguishable duplicates blocks fusion.

`primitive_ir_lib/**`, `semantic_ir_lib/**`, and `cad_agent/cli.py` remain unchanged in the first runtime slice.

## Roles, ordering, and conflicts

Roles define evidence lanes, not authority. A deterministic display rank followed by canonical evidence digest controls ordering only.

Required conflict types:

- `BYTE_IDENTITY_CONFLICT`
- `MEDIA_TYPE_CONFLICT`
- `PARSER_OBSERVATION_CONFLICT`
- `LOCATOR_CONFLICT`
- `RENDER_PROVENANCE_CONFLICT`
- `CALIBRATION_CONFLICT`
- `MEASUREMENT_CONFLICT`
- `GEOMETRY_CONFLICT`
- `MATERIAL_CONFLICT`
- `DECISION_CONFLICT`
- `DUPLICATE_OBSERVATION_AMBIGUITY`

A conflict contains:

- deterministic `conflict_id` from canonical conflict content;
- `conflict_type`;
- `subject_key`;
- sorted compared evidence hashes;
- normalized compared values/units;
- `state` (`UNRESOLVED`, `RESOLVED_BY_APPROVAL`, `STALE`);
- `blocking`;
- `resolution_reference_sha256` or `null`.

No majority vote, source-count weighting, confidence-only winner, parser priority, or model-generated resolution is allowed. Parser disagreement is preserved as a conflict.

## `source-conflict-resolution-1.0`

R1C validates but does not issue approvals. The external approval owner supplies a closed resolution artifact containing:

- `schema_version`
- `resolution_id`
- `run_id`
- `conflict_id`
- `subject_key`
- sorted `compared_evidence_sha256s`
- `source_bundle_sha256`
- `source_custody_sha256`
- `approved_root_configuration_sha256`
- `fusion_input_sha256`
- `selected_resolution`
- `approval_reference`
- `issued_at_utc`
- `expires_at_utc`
- `status = APPROVED`

Validation requires exact conflict/context/evidence matching and a non-expired approval. A resolution from another conflict, run, source bundle, custody artifact, root revision, or fusion-input context is rejected. Changing any bound evidence makes the resolution stale. An engineer `DECISION` source alone never satisfies this contract.

## Stale-state rules

Custody/fusion reuse fails closed when any of these changes:

- SourceBundle canonical hash;
- approved-root configuration hash;
- source byte hash, size, or privacy-safe file identity;
- final-handle relative path or containment result;
- media observations relevant to locators;
- page/region/render provenance;
- Primitive or Semantic artifact/checkpoint hash;
- deterministic observation projection/multiplicity;
- calibration hash/status;
- conflict content;
- resolution context, approval, or expiry.

A prior run ID, filename, UUID, manifest path, or equal byte hash alone is not sufficient authority.

## Manifest/checkpoint integration

The existing manifest owner gains optional closed references only.

### Custody reference

- `schema_version = source-custody-reference-1.0`
- `source_bundle_sha256`
- `approved_root_configuration_sha256`
- `source_custody_sha256`
- `status`
- `item_count`
- `eligible_count`
- `blocking_count`

### Fusion reference

- `schema_version = source-fusion-reference-1.0`
- `source_bundle_sha256`
- `source_custody_sha256`
- `approved_root_configuration_sha256`
- `source_fusion_sha256`
- `fusion_input_sha256`
- `status`
- `conflict_count`
- `unresolved_count`
- `resolution_count`

Rules:

- legacy manifests without R1C fields remain readable and unchanged;
- readers validate optional fields only when present;
- readers never inject null/default R1C fields;
- unequal rebinding fails;
- full item/locator/provenance/conflict arrays never enter the manifest;
- resume requires exact reference/artifact/hash matching;
- `READY` cannot coexist with custody blockers or unresolved blocking conflicts.

## Security and threat model

Synthetic tests must cover:

- lexical escape, absolute/UNC/device path, alternate data stream, Unicode/case ambiguity;
- symlink, junction, reparse/mount traversal and component replacement;
- final opened path outside root;
- hardlinks/same-file aliases and duplicate bytes/different identities;
- root-ID remapping and source replacement with identical bytes;
- mutation before open, during parsing, between hashes, and before downstream reuse;
- extension/header/media mismatch, polyglots, truncation, encrypted/malformed PDF;
- decompression bombs and page/pixel/byte limits;
- duplicate JSON keys, malformed UTF-8, excessive depth/count/length, non-finite constants;
- rotated/cropped PDF and ambiguous coordinate systems;
- parser disagreement;
- UUID/list-order nondeterminism;
- wrong Primitive/Semantic checkpoint binding;
- replayed/expired conflict approval;
- absolute path/private content leakage in artifacts, logs, and errors.

R1C imports no network, subprocess, OCR, model, AutoCAD, File IPC, repair, or publication modules.

## External reuse dossier

The runtime Issue must re-check the exact lock at its selected base. Planning-base evidence:

| Candidate | Exact basis | License/support | Classification | Decision |
|---|---|---|---|---|
| Python 3.11 stdlib `hashlib`, `json`, `os`, `pathlib`, `stat`, `ctypes`, `msvcrt` | supported project runtime | PSF; no dependency | `REUSE_AS_IS` | Primary hashing, strict JSON primitives, and bounded Windows handle adapter. |
| Pillow | locked `12.3.0`; official release 2026-07-01; Python >=3.10 | MIT-CMU | `EXTEND_WITH_TEST` | Read-only image observations under strict resource limits; original bytes remain authority. |
| pypdf | locked `6.14.2`; official release 2026-06-23; Python >=3.9 including 3.11 | BSD-3-Clause | `EXTEND_WITH_TEST` | Strict PDF structure/page observations only; no rewrite/text/repair authority. |
| ezdxf | locked `1.4.4`; official release 2026-05-14; Python >=3.10; CPython 3.11 Windows wheel | MIT | `SPIKE_ONLY` | Header-only first slice; read-only structure requires later focused acceptance. |
| PyMuPDF | locked `1.28.0` | AGPL-3.0 or commercial | `REJECT` for new R1C authority | Existing approved render use remains untouched; no second custody PDF parser. |
| `filetype` | unpinned `1.2.0`, 2022-11-02 | MIT, pure Python, old release | `REJECT` first slice | Existing parsers plus bounded signatures cover supported media. |
| `python-magic` | unpinned `0.4.27`, 2022-06-07 | MIT wrapper plus Windows libmagic/DLL | `REJECT` | Native deployment and pinning cost. |
| stdlib `mimetypes` | Python 3.11 | filename based | `REJECT` as authority | May not prove bytes. |
| new CAS/database/fsspec store | not pinned | new owner/dependencies | `REJECT` | Duplicates manifest/checkpoint/storage authority. |

No dependency or lock-file change is authorized by the first runtime slice.

## Deterministic benchmark method

Use synthetic fixed bytes only:

- valid/truncated/mismatched PNG/JPEG/PDF/DWG-header/DXF/JSON;
- small, medium, and approved-limit sizes;
- repeated and permuted runs must produce byte-identical canonical artifacts/hashes;
- equivalent Primitive/Semantic artifacts with different UUIDs/order must produce identical fusion hashes;
- resource limits, not workstation-specific timing, are acceptance gates;
- hash and parser phases may be measured separately for diagnostics;
- source bytes/mtime remain unchanged;
- no private file or AutoCAD session is required.

## Migration and rollback

- Existing SourceBundle, manifests, Primitive IR, Semantic IR, CLI, and run outputs are not migrated.
- R1C references are optional and absent from legacy manifests.
- Existing runs gain R1C evidence only through an explicit fresh rerun; no guessed backfill.
- Derived custody/fusion artifacts may be deleted without changing source bytes or accepted legacy runs.
- Rollback is a revert of bounded R1C commits and removal of derived artifacts/references from disposable runs.
- No AutoCAD rollback is needed because R1C performs no AutoCAD operation.

## Proposed future runtime allowlist

A separate runtime Issue may narrow this list.

### Create

- `cad_agent/source_integrity.py`
- `cad_agent/source_fusion.py`
- `tests/test_cad_agent_source_integrity.py`
- `tests/test_cad_agent_source_fusion.py`
- `docs/superpowers/implementation-records/2026-08-06-r1c-source-integrity-fusion.md`

### Modify

- `cad_agent/manifest.py`
- `cad_agent/pdf.py`
- `tests/test_cad_agent_source_bundle_manifest.py`

### Do not modify

- `cad_agent/source_bundle.py`
- `cad_agent/cli.py`
- `primitive_ir_lib/**`
- `semantic_ir_lib/**`
- `agent_lib/**` and Wave 1A files
- `dxf_builder_lib/**`
- `mcp_integration_lib/**`
- `autocad_plugin/**`
- `requirements/**` and lock files
- workflows, `docs/STATUS.md`, and `docs/HANDOFF.md`
- registry, revision, repair, verdict, and publication code

## One-writer overlap matrix

| Lane | Writer | Write set | Rule |
|---|---|---|---|
| Wave 1A / #70 | Cell 1 | vision-handoff/Codex worker planning or later approved worker files | Must not modify R1C or manifest R1C references concurrently. |
| Wave 1B / #71 | Cell 2 | these two planning files; later approved R1C runtime allowlist | Sole R1C writer. |
| Wave 1C / #72 | Cell 3 | no repository writes by default | AutoCAD evidence only; no R1C dependency. |
| Cell 5 / #77 | read-only | comments/reviews only | No branch push. |
| Master PO | final governance | acceptance/merge/scope amendments | No production code in this slice. |

`cad_agent/manifest.py` is shared canonical ownership. Future R1C implementation must not run concurrently with another writer changing that file.

## Cell 5 blocker disposition

- A root revision/config hash and privacy-safe file identity are now explicit.
- Same-file aliases and duplicate bytes are separate group types.
- Final-handle Windows containment is mandatory and ports bounded S3B concepts.
- UUIDs/handles/timestamps/list order are excluded from canonical Primitive/Semantic identity.
- Current Semantic artifacts with omitted optional Primitive SHA remain compatible through external checkpoint binding.
- PDF render provenance and coordinate conventions are closed and hash-bound.
- Parser isolation uses duplicated handles or bounded operation-owned snapshots.
- Engineer JSON safety is explicit.
- Custody publishes one complete `READY/BLOCKED` artifact; fusion rejects `BLOCKED`.
- Conflict-resolution evidence has an exact replay-safe schema and external approval owner.
- Pillow/pypdf classifications are corrected to `EXTEND_WITH_TEST` and official version/release/support evidence is recorded.

## Planning acceptance criteria

This design is acceptable when:

- final diff contains only this design and its plan;
- R1A/R1B and current producers remain unchanged;
- approved root, byte identity, final-handle containment, alias/duplicate, and stale behavior fail closed;
- deterministic provenance is invariant to UUID and list-order changes;
- PDF page/render/coordinate provenance is explicit;
- conflicts are preserved and resolutions cannot replay across context;
- manifest/checkpoint ownership is not duplicated;
- no dependency, model, OCR, AutoCAD, repair, verdict, or publication authority is introduced;
- hosted tests and Reuse Declaration pass;
- Cell 5 re-reviews the exact revised head;
- Master PO reviews the exact final head before merge.
