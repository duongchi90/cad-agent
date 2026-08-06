# R1C Source Integrity and Deterministic Fusion Design

## Status and authority

- Issue: #71
- Exact planning base: `d71d0c97e28e03cb430f05589c8381b4ede70e66`
- Planning branch: `planning/w1b-r1c-source-integrity-fusion`
- Paired independent research/red-team: Issue #77
- This document is planning/design only.
- R1C runtime implementation, dependencies, model calls, AutoCAD mutation, OCR expansion, registry, revision, repair, verdict, and publication remain locked.

## Decision summary

R1C will be an adjacent, pure-Python, fail-closed adapter around the accepted R1A `SourceBundle`, the R1B manifest binding, existing `primitive_ir_lib` and `semantic_ir_lib` artifacts, and the existing `cad_agent` manifest/checkpoint owner.

R1C will not expand `source-bundle-1.0`, create another source registry, copy source bytes by default, infer page or crop identity, select a silent winner among conflicting sources, or produce a visual/engineering verdict. It will create two closed derived artifacts:

1. `source-custody-1.0`: byte-stable, media-verified custody evidence for each SourceBundle item.
2. `source-fusion-1.0`: deterministic ordering, locator binding, provenance grouping, and conflict-state evidence for downstream reconstruction.

Both artifacts are hash-bound to the accepted R1A SourceBundle. The existing run manifest remains the only run truth store and records only closed references to the derived artifacts.

## Goals

R1C must:

- verify approved source bytes without mutating them;
- bind declared source metadata to observed bytes, size, media structure, and stable identity;
- detect path escape, reparse/symlink traversal, aliasing, duplicates, replacement, and mid-read mutation;
- preserve explicit source roles without treating role order as engineering authority;
- bind page, sheet, view, crop, and region locators explicitly;
- reuse Primitive IR traces/calibration and Semantic IR references instead of re-recognizing sources;
- create deterministic conflict records and unresolved states;
- produce a deterministic downstream fusion packet, not fused geometry and not PASS;
- integrate through `cad_agent.manifest` without a second manifest/checkpoint/evidence store;
- remain testable using synthetic bytes only.

## Non-goals

R1C does not:

- discover files outside an approved intake root;
- crawl folders or infer sources from filenames;
- change R1A/R1B schema versions;
- perform OCR, image recognition, CAD parsing authority, visual comparison, or model inference;
- resolve engineering conflicts automatically;
- mutate source bytes or accepted CAD;
- create a component/view registry or revision store;
- authorize repair, publication, or AutoCAD operations;
- commit private source bytes, source paths, or customer data.

## Existing internal owners and exact reuse map

### R1A SourceBundle contract — `REUSE_AS_IS`

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

R1A already owns closed source IDs, kinds, roles, relative paths, declared SHA-256, media type, page/region labels, capture time, and coarse quality. R1C consumes the normalized R1A artifact and must not add filesystem behavior or authority fields to R1A.

### R1B manifest binding — `EXTEND_WITH_ADAPTER`

Owner and APIs:

- `cad_agent/manifest.py`
- `SOURCE_BUNDLE_REFERENCE_SCHEMA_VERSION`
- `validate_source_bundle_reference(value)`
- `bind_source_bundle(manifest, source_bundle)`
- `require_source_bundle_match(manifest, source_bundle)`
- `read_manifest(path)` / `write_manifest(path, manifest)`
- `sha256_file(path)`
- `verify_source(manifest, source)`
- `completed_artifact(output_dir, stage)`
- `cad_agent/pdf.py::read_pdf_manifest(path)`

Tests and evidence:

- `tests/test_cad_agent_source_bundle_manifest.py`
- `tests/test_cad_agent_cli.py`
- `tests/test_cad_agent_pdf.py`
- `docs/superpowers/implementation-records/2026-08-05-source-bundle-manifest-binding.md`

R1B already proves that optional closed references can be added without copying SourceBundle items or breaking legacy manifests. R1C follows this pattern for custody/fusion references.

### Primitive IR source evidence — `REUSE_AS_IS`

Owner and APIs:

- `primitive_ir_lib/models.py::SourceDocument`
- `primitive_ir_lib/models.py::Trace`
- `primitive_ir_lib/models.py::Calibration`
- `primitive_ir_lib/models.py::Primitive`
- `primitive_ir_lib/models.py::PrimitiveIRDocument`
- `primitive_ir_lib/run_image.py::run`
- `primitive_ir_lib/run_pdf.py::run_pdf`

Tests:

- `primitive_ir_lib/tests/test_run_image.py`
- `primitive_ir_lib/tests/test_run_pdf.py`
- Primitive IR model/schema tests under `primitive_ir_lib/tests/`

R1C reuses source SHA, page index, pixel dimensions, trace bounding boxes, extraction tool, primitive IDs, confidence, cross-validation, and calibration evidence. It does not invoke a second OCR or recognition engine.

### Semantic IR engineering references — `EXTEND_WITH_ADAPTER`

Owner and APIs:

- `semantic_ir_lib/models.py::PrimitiveIRRef`
- `semantic_ir_lib/models.py::SemanticPart`
- `semantic_ir_lib/models.py::Constraint`
- `semantic_ir_lib/models.py::SemanticIRDocument`
- `semantic_ir_lib.assemble.build_semantic_document`
- `semantic_ir_lib.constraint_pruning.prune_constraints`
- `semantic_ir_lib.constraint_solving.solve_constraints`

Tests:

- `semantic_ir_lib/tests/test_semantic_ir.py`
- `semantic_ir_lib/tests/test_constraint_pruning.py`
- `semantic_ir_lib/tests/test_constraint_solving.py`

Semantic IR intentionally references Primitive IR IDs instead of copying geometry. R1C preserves that pattern: fusion provenance points to artifact hashes and IDs; it does not duplicate primitives, parts, constraints, or solved coordinates.

### Run manifests, checkpoints, resume, evidence, and approvals — `EXTEND_WITH_ADAPTER`

Owner and APIs:

- `cad_agent/manifest.py`
- `cad_agent/pdf.py`
- `cad_agent/cli.py::run_stages`
- `cad_agent/pdf.py::run_pdf_stages`
- existing manifest source SHA verification and artifact checkpoint hashes
- existing calibration approval records and draft-reference safety defaults

Tests:

- `tests/test_cad_agent_cli.py`
- `tests/test_cad_agent_pdf.py`
- `tests/test_cad_agent_source_bundle_manifest.py`

The run manifest remains the sole lifecycle owner. Full custody/fusion artifacts live under the existing run output directory and the manifest stores only schema/version/ID/hash/count/status references.

### Existing hashing and fail-closed patterns — `REUSE_AS_IS`

- `cad_agent.manifest.sha256_file()` for streamed SHA-256.
- `cad_agent.drawing_contracts.canonical_json_sha256()` for canonical JSON hashing.
- closed-object validation and lowercase SHA-256 checks in `cad_agent.source_bundle`.
- atomic temporary-write plus `os.replace()` in `cad_agent.manifest.write_manifest()`.
- source hash verification before resume in `cad_agent.manifest.verify_source()`.
- artifact hash verification in `cad_agent.manifest.completed_artifact()`.
- optional-reference validation without default injection in R1B.

### Missing internal capability — `NEW_MISSING_CAPABILITY`

The repository does not currently own a Python boundary that:

- inspects every SourceBundle item against an approved root;
- proves bytes were stable while media metadata was read;
- records aliases/duplicates without leaking absolute paths;
- binds explicit page/crop locators;
- groups Primitive/Semantic evidence deterministically;
- emits conflict/unresolved state and a fusion-ready packet.

That bounded gap is R1C. It is an adapter and evidence boundary, not a new recognition, manifest, CAD, verdict, or approval authority.

## Approaches considered

### A. Expand `source-bundle-1.0` with custody and fusion fields

Rejected. R1A is a closed, accepted metadata contract. Adding observed filesystem/media fields would either break the schema or require `source-bundle-2.0`, mix declared intake with derived evidence, and enlarge migration scope.

### B. Create a source registry/database

Rejected. A new registry would duplicate the existing run manifest/checkpoint owner, create lifecycle and migration complexity, and conflict with the future component/view registry.

### C. Adjacent derived artifacts plus existing manifest references

Selected. R1A remains declared-source truth, R1C derives immutable custody/fusion evidence, and R1B's existing manifest owner binds only hashes and state. This is the smallest architecture that closes the missing byte-integrity and deterministic-fusion gap.

## Closed derived contracts

### `source-custody-1.0`

Canonical root fields:

- `schema_version`
- `bundle_id`
- `run_id`
- `source_bundle_sha256`
- `approved_root_id`
- `items`
- `alias_groups`

No wall-clock timestamp or absolute path participates in the canonical payload.

Each item contains:

- `source_id`
- `kind`
- `role`
- `relative_path`
- `declared_sha256`
- `observed_sha256`
- `size_bytes`
- `declared_media_type`
- `observed_media_type`
- `media_metadata`
- `page_ids`
- `region_ids`
- `alias_group_id` or `null`
- `custody_state`

Allowed custody states:

- `VERIFIED`
- `DUPLICATE_BYTES`
- `ALIAS_PATH`
- `MISSING`
- `PATH_ESCAPE`
- `REPARSE_POINT`
- `UNSUPPORTED_MEDIA`
- `MEDIA_MISMATCH`
- `HASH_MISMATCH`
- `CHANGED_DURING_READ`
- `UNREADABLE`

Only `VERIFIED` and a fully explained `DUPLICATE_BYTES` group are eligible for a ready fusion packet. All other states fail closed.

### `source-fusion-1.0`

Canonical root fields:

- `schema_version`
- `bundle_id`
- `run_id`
- `source_bundle_sha256`
- `source_custody_sha256`
- `page_locators`
- `region_locators`
- `primitive_evidence`
- `semantic_evidence`
- `evidence_groups`
- `conflicts`
- `status`

Status values:

- `READY`
- `BLOCKED_UNRESOLVED`
- `STALE`

`READY` means only that inputs are byte-stable, locators/provenance are closed, and no blocking conflict remains. It is not a visual PASS, engineering approval, CAD acceptance, repair permission, or publication permission.

## Source byte custody flow

1. Validate and normalize the R1A SourceBundle.
2. Require a server/operator-approved intake root ID and filesystem root supplied outside the SourceBundle.
3. Resolve the root strictly and reject a non-directory or reparse/symlink root.
4. Join only the validated R1A `relative_path` under that root.
5. Reject lexical escape before filesystem access.
6. Walk each path component with `lstat`; reject symlink, junction, mount/reparse, or non-regular-file substitution.
7. Open the final file read-only in binary mode.
8. Capture descriptor identity/size before read.
9. Stream SHA-256 over the opened descriptor.
10. Seek and read media metadata through the same descriptor or a bounded read-only adapter.
11. Stream SHA-256 a second time after metadata extraction.
12. Capture descriptor and path identity/size after read.
13. Require both hashes, sizes, descriptor identity, and final path identity to match.
14. Compare the stable observed hash to the SourceBundle declared hash.
15. Emit a normalized custody item; never write to the source.

Two-pass hashing is intentional. It is more expensive than a single hash but gives deterministic evidence that metadata extraction did not race an in-place replacement or mutation. Performance is bounded by synthetic benchmarks and may later use an approved optimization only if it preserves the same guarantee.

## Path, alias, duplicate, and privacy rules

- Absolute source paths are never serialized into custody/fusion artifacts.
- `approved_root_id` is a stable configuration identifier, not a path.
- `relative_path` remains the R1A normalized value.
- Runtime alias checks use `os.path.samefile`, descriptor/path stat identity, and reparse checks.
- Alias groups are represented by a deterministic ID derived from sorted source IDs and the stable byte hash.
- Identical bytes under different source IDs are preserved as separate evidence references but may share one alias/duplicate group.
- Same path or same file identity with conflicting declared hashes/media/kinds fails closed.
- Same bytes with different roles never silently collapse the roles.
- A duplicate does not become authoritative merely because it appears multiple times.

## Media verification and metadata

Media verification uses existing pinned dependencies only; declared extensions and MIME strings are insufficient.

### Images

Use Pillow read-only verification against the same opened descriptor. Record format, width, height, mode, and available DPI metadata. Do not call save, transpose, convert, thumbnail, or any mutating transform. PNG/JPEG observed types must match the R1A declared media type.

### PDFs

Use pypdf strict read-only parsing for page count, encryption state, page boxes, and structural readability. Do not rewrite, repair, decrypt without an approved secret flow, or extract source text in R1C. Multi-page page identity requires explicit locator bindings.

### Exact-base CAD

- DWG: bounded header/media sniff only; no new DWG parser and no geometry authority.
- DXF: existing pinned `ezdxf` may be used read-only for structural audit in a separately tested adapter; it does not replace AutoCAD truth.
- R1C does not mutate or normalize CAD bytes.

### Engineer records

Require UTF-8 JSON parsing. Record a canonical JSON digest as derived metadata while retaining the original byte SHA-256 as custody authority. A record with role `DECISION` is evidence only; it is not an approval unless an existing approval owner supplies a separate hash-bound approval reference.

## Explicit page, sheet, view, crop, and region identity

R1A `page_ids` and `region_ids` are stable labels, but R1A sorts them and does not bind a page ID to a PDF page index or a region ID to crop coordinates. R1C must not infer those mappings.

`source-fusion-1.0` therefore requires explicit locator records:

Page locator:

- `source_id`
- `page_id`
- `page_index_zero_based`
- `sheet_id` or `null`
- `view_id` or `null`

Region locator:

- `source_id`
- `region_id`
- `page_id` or `null`
- `coordinate_space` (`PIXEL` or `PDF_POINT`)
- `bounds` (`x_min`, `y_min`, `x_max`, `y_max`)
- `locator_source_sha256`

Rules:

- every declared page/region label must have exactly one locator;
- locator indexes/bounds must fit observed media metadata;
- a locator hash must bind to the custody source hash;
- multi-page PDF mapping without explicit locators is `BLOCKED_UNRESOLVED`;
- no filename convention, sorted label order, OCR, or model call may infer a mapping.

## Quality, skew, distortion, resolution, and calibration

R1C preserves the R1A coarse quality values and adds only observed media metadata. Recognition-derived quality belongs to Primitive IR:

- image dimensions/DPI and PDF page boxes/page count come from custody adapters;
- trace bounding boxes, confidence, extraction tool, and page index come from Primitive IR;
- skew/distortion observations already produced by approved Primitive IR processing are referenced by artifact hash and observation ID;
- calibration comes from `PrimitiveIRDocument.calibration`, including status and `source_sha256`;
- unverified calibration stays unresolved and cannot become verified in R1C;
- R1C does not calculate a new production scale.

## Deterministic provenance

Primitive evidence reference fields:

- `primitive_ir_sha256`
- `source_id`
- `page_id` or `null`
- `region_id` or `null`
- `primitive_id`
- `trace_bbox`
- `calibration_sha256`

Semantic evidence reference fields:

- `semantic_ir_sha256`
- `primitive_ir_sha256`
- `part_id` or `constraint_id`
- sorted `primitive_ids`

Every reference must resolve to a supplied artifact whose file hash matches the reference. Semantic evidence must point to the exact Primitive IR hash declared by `PrimitiveIRRef`; IDs alone are never sufficient.

Canonical arrays are sorted by stable compound keys. Canonical JSON hashing uses the existing `canonical_json_sha256()` helper. Random IDs, filesystem iteration order, locale-dependent values, floating-point string shortcuts, and current time are forbidden from canonical output.

## Roles, precedence, and conflicts

Roles determine evidence lanes, not automatic truth:

- `BASE_CAD`: exact-base geometry reference for explicitly mapped components/views only.
- `MEASUREMENT`: explicit numeric measurement evidence.
- `DECISION`: engineering decision evidence; requires separate approval to resolve a conflict.
- `DETAIL` and `SECTION`: local geometry/detail evidence.
- `OVERALL`: global arrangement evidence.
- `MATERIAL_TABLE`: material/text evidence.

The packet uses a deterministic display/order rank, then `source_id`, but ordering never discards evidence.

A conflict record contains:

- deterministic `conflict_id` from canonical conflict content;
- `conflict_type`;
- `subject_key`;
- sorted evidence references;
- normalized compared values/units where applicable;
- `state` (`UNRESOLVED`, `RESOLVED_BY_APPROVAL`, `STALE`);
- `resolution_reference` or `null`;
- `blocking` boolean.

Required conflict types include:

- `BYTE_IDENTITY_CONFLICT`
- `MEDIA_TYPE_CONFLICT`
- `LOCATOR_CONFLICT`
- `CALIBRATION_CONFLICT`
- `MEASUREMENT_CONFLICT`
- `GEOMETRY_CONFLICT`
- `MATERIAL_CONFLICT`
- `DECISION_CONFLICT`

No majority vote, confidence-only winner, source-count weighting, or model-generated resolution is allowed. A blocking unresolved conflict makes status `BLOCKED_UNRESOLVED`.

## Stale and changed-source behavior

The fusion packet is stale when any of these changes:

- canonical SourceBundle hash;
- custody artifact hash;
- any source byte hash/size/identity;
- page or region locator hash;
- Primitive IR or Semantic IR artifact hash;
- calibration evidence hash;
- approved conflict-resolution reference.

Consumers must call a fail-closed match function before reuse. A prior run ID, filename, source ID, or manifest path is never authority. Changed bytes require a fresh SourceBundle/custody/fusion lifecycle; R1C never rewrites an old artifact in place.

## Existing manifest/checkpoint integration

The existing manifest owner gains optional closed references only:

`source_custody` reference:

- `schema_version = source-custody-reference-1.0`
- `source_bundle_sha256`
- `source_custody_sha256`
- `item_count`
- `verified_count`

`source_fusion` reference:

- `schema_version = source-fusion-reference-1.0`
- `source_bundle_sha256`
- `source_custody_sha256`
- `source_fusion_sha256`
- `status`
- `conflict_count`
- `unresolved_count`

Rules:

- legacy manifests without either field remain readable and unchanged;
- readers validate an optional reference only when present;
- readers never inject null/default R1C fields;
- binding an unequal existing reference fails;
- full custody/fusion items are never copied into the run manifest;
- artifact files are written atomically under the existing run output root;
- resume requires all bound hashes to match before any downstream stage is reused.

## Failure behavior

R1C raises one closed domain error type per module and returns no partial ready packet. On any failure:

- source bytes remain untouched;
- temporary derived artifacts owned by the current operation are removed;
- existing manifest/checkpoints are not replaced;
- no downstream recognition/fusion stage starts;
- the error names a stable code/category without leaking absolute paths or private content.

Expected failure categories include path policy, unreadable source, changed source, hash mismatch, media mismatch, invalid locator, stale evidence, duplicate conflict, unresolved conflict, and malformed closed contract.

## Synthetic and private-data boundaries

Planning and ordinary CI use only synthetic bytes generated in `tmp_path`:

- minimal valid/invalid PNG and JPEG files;
- one- and multi-page PDFs created in memory;
- minimal DWG header samples and ASCII DXF samples;
- UTF-8 JSON engineer records;
- symlink/junction/reparse tests when the platform permits;
- duplicate, alias, replacement, truncation, and mid-read mutation probes.

Private-data tests remain separately marked and require an approved external root. Private bytes, absolute paths, hashes, metadata, and generated artifacts must not be committed or printed in ordinary logs.

## External reuse dossier

The runtime Issue must re-verify the exact repository lock before implementation. Current planning-base candidates are:

| Candidate | Exact version/revision basis | License | Classification | Decision |
|---|---|---|---|---|
| Python 3.11 `hashlib`, `json`, `pathlib`, `os`, `stat` | CPython 3.11 supported environment | PSF | `REUSE_AS_IS` | Primary byte hash, path/stat, JSON, and reparse primitives; zero dependency cost. |
| Pillow | repository lock `pillow==12.3.0` | PIL/MIT-CMU style | `EXTEND_WITH_ADAPTER` | Read-only image format/dimension/DPI verification; no transform/save. |
| pypdf | repository lock `pypdf==6.14.2` | BSD-3-Clause | `EXTEND_WITH_ADAPTER` | Strict PDF structure/page metadata; no rewrite/repair/text authority. |
| PyMuPDF | repository lock `pymupdf==1.28.0` | AGPL-3.0 or commercial | `REJECT` for new R1C authority | Existing PDF-render path may remain; R1C does not create a second PDF parser dependency or expand licensing exposure. |
| ezdxf | repository lock `ezdxf==1.4.4` | MIT | `SPIKE_ONLY`, then `EXTEND_WITH_ADAPTER` if accepted | Read-only DXF structure only; never DWG or CAD truth. |
| `python-magic`/libmagic | not pinned | mixed wrapper/libmagic deployment | `REJECT` | Adds Windows native binary/deployment/pinning cost for behavior covered by existing parsers. |
| `filetype`-style signature libraries | not pinned | varies | `REJECT` | New dependency is unnecessary for the closed supported media set. |

Security and maintenance rules:

- use only versions already present in `requirements/windows-py311.lock` for the first runtime slice;
- no dependency or lock-file change without a separate amendment;
- parsers receive bounded local files only, with size/page/pixel limits checked before expensive work;
- no network access or telemetry;
- parser exceptions map to closed R1C errors;
- fuzz/truncation/decompression-bomb tests must be included for supported media.

Benchmark method:

- generate deterministic synthetic files at small, medium, and approved maximum sizes;
- run custody twice and require byte-for-byte identical canonical artifacts/hashes;
- compare two-pass hash time and parser time separately;
- enforce a bounded memory/size policy rather than an unproven wall-clock SLA;
- test parallel input ordering and require identical sorted output;
- no private file is needed for benchmark acceptance.

Migration and rollback:

- no existing bytes or manifests are migrated in the first runtime slice;
- R1C fields are optional and absent from legacy manifests;
- revert the bounded R1C commit(s) to roll back;
- derived R1C artifacts may be deleted without changing source bytes or accepted legacy runs;
- a later migration may generate fresh R1C artifacts only through explicit rerun, never backfill guessed values.

## Proposed future runtime allowlist

A separate runtime Issue must pin an exact base after this planning PR is accepted. Proposed first-slice files:

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

- `cad_agent/source_bundle.py` and the R1A fixture/schema behavior;
- recognition/OCR/geometry packages;
- Semantic IR models/solver;
- `agent_lib` and Wave 1A files;
- DXF/AutoCAD/File IPC code;
- requirements and lock files;
- workflows, `STATUS.md`, and `HANDOFF.md`;
- registry, revision, repair, verdict, and publication code.

The Master PO may narrow this proposed allowlist. Any expansion requires a formal amendment before implementation.

## One-writer overlap matrix

| Lane | Writer | Production write set | Overlap rule |
|---|---|---|---|
| Wave 1A / Issue #70 | Cell 1 | future `agent_lib`/closed vision-handoff worker-control slice | Must not modify R1C files or manifest source-integrity references. |
| Wave 1B / Issue #71 | Cell 2 | planning files only; future proposed R1C files above | Sole writer for R1C planning/runtime allowlist. |
| Wave 1C / Issue #72 | Cell 3 | none by default | Evidence/operator only; defects require separate Issue. |
| Cell 5 / Issue #77 | read-only red-team | none | May comment/review only; never pushes to the writer branch. |
| Master PO | governance/review | no production code in this slice | Final acceptance, merge order, and scope amendments only. |

`cad_agent/manifest.py` is a shared canonical owner. During future R1C implementation, Wave 1A must not modify it concurrently. Integration order is controlled by Master PO.

## Acceptance criteria for the future runtime slice

- R1A and R1B compatibility tests remain passing.
- SourceBundle declared hash and stable observed hash must match.
- Path escape, reparse, alias, duplicate, missing, changed-during-read, media mismatch, and truncation tests fail closed.
- Supported media metadata is deterministic and read-only.
- Multi-page/page-region mappings require explicit locators.
- Primitive/Semantic provenance is hash- and ID-bound.
- Conflicts are preserved and sorted; no silent winner exists.
- `READY` is never represented as visual PASS or engineering approval.
- Legacy manifests remain byte-compatible when R1C is absent.
- Final diff stays within the approved runtime allowlist.
- Focused tests, canonical verifier, hosted synthetic-merge checks, and Reuse Declaration pass.
- Private-data, AutoCAD, and hosted AutoCAD .NET gates remain truthful `NOT RUN`/`SKIP` unless separately executed.

## Planning acceptance

This design is acceptable when:

- it composes R1A/R1B rather than replacing them;
- it names existing owners, APIs, tests, and missing gaps;
- source custody and stale-state behavior fail closed;
- locator mapping is explicit, not inferred;
- conflict preservation is deterministic;
- external candidates are bounded to the existing lock and license posture;
- the future runtime write set does not overlap Wave 1A or Wave 1C;
- the planning PR changes only this design and its implementation plan.
