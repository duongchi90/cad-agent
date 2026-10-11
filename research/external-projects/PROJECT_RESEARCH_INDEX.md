# External Project Research Index

**Status:** RESEARCH_ONLY  
**Purpose:** Durable recovery index for CadAgent external-project research so a new machine or new chat can reconstruct prior conclusions without relying on conversational memory.  
**Production impact:** NONE. This file does not authorize production changes, native CAD mutation, merges, or architecture changes.

## 1. Recovery rule

For a new chat/session, recover state in this order:

1. Fresh-read GitHub `main` and Issue #291 (Master Roadmap).
2. Read this file.
3. Read `research/antigravity/2026-10-11/MANIFEST.md` on the durable research branch.
4. Fresh-read Issue #491 and any currently open production PRs for mutable runtime/frontier state.
5. Treat old SHA/PR/CI/native verdicts as stale if the exact head changed.

GitHub is canonical for current mutable state. This index is historical research context only.

## 2. Evidence classes

- `DURABLE_GITHUB`: conclusion is directly represented in current repository docs/issues/research artifacts.
- `CHAT_DERIVED_LEGACY_NOTE`: conclusion was established in prior project discussion but the original detailed external-source packet is not yet preserved in this repository. Preserve it as a lead, not as a fresh proof.
- `NEEDS_SOURCE_BACKFILL`: future research should attach exact source/version/license/evidence before production decisions depend on the detail.

Never silently promote a `CHAT_DERIVED_LEGACY_NOTE` to verified implementation evidence.

---

## 3. CadMind

### Durable project role

`DURABLE_GITHUB`

Issue #291 names CAD-native agent systems such as **CadMind** as a learning source for:

- entity understanding;
- native editing;
- drafting behavior.

CadAgent must learn from such systems without becoming runtime-dependent on them. Production implementation remains measured and existing-owner-first.

`docs/HANDOFF.md` also preserves the rule that CADmind-style `observe_drawing` / `query_entities` capability work stays evidence-driven: do not build a broad MECH/CAD query capability merely because it appears useful; require a measured CAD-context/query bottleneck first.

### Prior detailed findings

`CHAT_DERIVED_LEGACY_NOTE`

Prior CadMind investigation identified the following capability ideas as technically valuable candidates for CadAgent, subject to independent proof and existing-owner reuse:

- in-place native ARC / CIRCLE / LWPOLYLINE mutation while preserving object identity where the native CAD contract supports it;
- nested BLOCK / XREF snap-point extraction;
- block redefine and dynamic-property manipulation;
- dimension audit / geometry lint style checks;
- drafting catalogs / reusable drafting knowledge;
- a catalog of approximately 90 ToolPackages with BM25-style retrieval, ranked behind core CAD-native capabilities rather than treated as the product center.

These are research leads, not claims that CadAgent already implements them.

### ToolPackage licensing / clean-room constraint

`CHAT_DERIVED_LEGACY_NOTE`

The prior investigation concluded that the 90 CadMind ToolPackages were only:

- `VERIFIED_RESOURCE`
- `VERIFIED_BINARY`

not source-verified implementations, because implementation was reported as encrypted in `CadMindTools.enc` and loaded through an ECDH/licensing mechanism.

The adopted boundary was:

- approximately 90/90 packages were considered reconstructable at requirement/specification level;
- 0/90 were proven behavior-compatible clean-room reimplementations;
- external analysis (including REA-style research) may inform requirements and observable behavior;
- CadAgent implementation must be independent and placed into the smallest existing CadAgent owner rather than copying protected implementation details.

`NEEDS_SOURCE_BACKFILL`: preserve the original exact CadMind version, package inventory, license text, binary/resource hashes, and external-source citations if they are recovered from an earlier chat/export.

### CadAgent adoption status

- Broad CAD query layer: **NOT ADOPTED by default**; gated on measured need.
- Native identity-preserving edit concepts: **architectural research input**, not universal proof.
- Block/Xref and drafting ideas: **research leads**, adopt only through current owner + causal RED.
- 90 ToolPackages: **NOT copied**, clean-room only.

---

## 4. Scan2CAD / AutoCAD Raster Design

### Durable project role

`DURABLE_GITHUB`

Issue #291 names raster/vectorization products such as **Scan2CAD** and **AutoCAD Raster Design** as learning sources for contracts around:

- image cleanup;
- OCR;
- geometry recognition / vectorization.

The product rule is to learn capability contracts and empirical behavior without introducing a runtime dependency merely because another product contains a feature.

### CadAgent adoption principles

The durable roadmap already maps this family into Reconstruction/Revision shared raster capabilities:

- raster cleanup and segmentation;
- OCR / text orientation;
- LINE / ARC / CIRCLE / contour recognition;
- evidence-bounded topology reconstruction;
- uncertain facts stay unresolved rather than fabricated.

### Detail status

`NEEDS_SOURCE_BACKFILL`

No durable per-product feature matrix, version-specific benchmark, or license/source packet for Scan2CAD or Raster Design is currently indexed here. A future recovered report should append exact findings rather than relying on memory.

---

## 5. BricsCAD BLOCKIFY / AutoCAD Smart Blocks

### Durable project role

`DURABLE_GITHUB`

Issue #291 names **BricsCAD BLOCKIFY** and **AutoCAD Smart Blocks** as learning sources for:

- repeated-geometry reuse;
- structured component behavior.

The corresponding CadAgent product direction is explicit: when repeated equivalent geometry is actually proven, prefer reusable native `BLOCK + INSERT` structure over duplicated loose primitives.

### Safety / architecture boundary

- Do not infer block identity solely from visual similarity.
- Do not introduce a second block/component subsystem when current native owners can express the required behavior.
- Repeated geometry is a candidate for structured reuse only when evidence supports equivalence.

### Detail status

`NEEDS_SOURCE_BACKFILL`

No durable version-specific feature matrix or benchmark for BLOCKIFY / Smart Blocks is currently preserved here. Recover and append exact external evidence before making product claims from those systems.

---

## 6. Open-source geometry / CV / CAD projects

### Durable project role

`DURABLE_GITHUB`

Issue #291 explicitly permits learning from open-source geometry/CV/CAD projects as direct source references where licensing permits.

The governing rule is:

- verify license and exact source version;
- reuse existing CadAgent owners;
- do not create parallel geometry/OCR/CAD subsystems without a measured owner gap;
- keep source provenance and benchmark/evaluator data separated from production truth.

### Detail status

`NEEDS_SOURCE_BACKFILL`

This index does not yet contain a complete historical inventory of every open-source repository inspected in prior chats. When recovered, append each project using the template in Section 9.

---

## 7. CadAgent empirical research that followed the external-project studies

These are not external products, but they are the durable continuation of the same research program and should be read by future chats.

`DURABLE_GITHUB`

Durable branch:

`research/antigravity-2026-10-11`

Primary manifest:

`research/antigravity/2026-10-11/MANIFEST.md`

Current preserved groups include:

### Target/base orientation and registration

- corrected three-layer mapping: raster pixels -> calibrated physical/native units -> target/base alignment -> correspondence;
- target/base alignment is not arbitrary rescaling after calibration;
- caller-declared orientation-envelope research;
- rotational symmetry / wrong-anchor safety tests;
- collinear-anchor behavior treated as a product-safety policy question rather than a false mathematical impossibility claim.

### Source/base LINE correspondence

- KEEP/CHANGE behavior matrix;
- greedy order / collision failure analysis;
- `SOURCE_FUSION_LINE_ADD_PROPOSAL_V1` specified as proposal-only;
- ADD should remain distinct from mutation of an existing base entity.

### Removal / negative raster evidence

- `UNMATCHED_BASE != REMOVE` is a core safety doctrine;
- absence of detection is not evidence of absence;
- naive inversion of positive raster support is unsafe;
- negative source-support evidence must remain observational and must not directly authorize native deletion;
- native removal remains blocked behind stronger semantic/identity evidence.

Read the manifest and exact artifacts for current hashes and detailed empirical results.

---

## 8. Durable CadAgent architectural lessons distilled from the research program

These are represented in Issue #291 and/or the durable research artifacts:

1. **Reuse first.** If a trustworthy native base exists, preserve it and infer only evidenced deltas.
2. **One shared engine, three modes.** Revision, Reconstruction, Native Edit share recognition, semantic/native operations and verification rather than becoming separate products.
3. **Unobserved is not removed.** Raster omission/occlusion cannot silently delete native CAD.
4. **Native semantics when proven.** Prefer native curve/text/dimension/block structure over flattened primitives only when evidence justifies the higher-level semantic object.
5. **Existing owner first.** New subsystem creation requires a measured current owner gap.
6. **Evidence before capability expansion.** Do not build broad CadMind-style query/tool catalogs without a real product bottleneck.
7. **Clean-room where required.** Licensed/encrypted third-party implementation may inform requirements/observable behavior, not be copied into CadAgent.
8. **GitHub current state overrides historical notes.** Old review/runtime conclusions never override fresh exact-head evidence.

---

## 9. Template for future external-project entries

Append new or recovered project research using this exact shape:

```text
PROJECT=
EXACT_PRODUCT_OR_REPO_VERSION=
RESEARCH_DATE=
EVIDENCE_CLASS=DURABLE_GITHUB | CHAT_DERIVED_LEGACY_NOTE | NEEDS_SOURCE_BACKFILL

WHAT_WAS_INSPECTED=
VERIFIED_CAPABILITIES=
UNVERIFIED_CLAIMS=
FAILURE_MODES_OR_LIMITS=
LICENSE_OR_CLEAN_ROOM_CONSTRAINTS=

CADAGENT_LESSONS=
EXISTING_OWNER_TO_REUSE=
WHAT_NOT_TO_COPY_OR_DUPLICATE=
PRODUCTION_STATUS=RESEARCH_ONLY

DURABLE_REFERENCES=
```

A recovered historical report should be appended without rewriting prior evidence into stronger claims.

---

## 10. Canonical durable references

- Issue #291 — Master Roadmap / product definition / source strategy.
- `docs/HANDOFF.md` — current architectural handoff, including evidence-driven CADmind-style query guidance.
- Issue #491 — mutable native/product evidence frontier; always fresh-read.
- Current open production PR(s) — exact-head implementation/review/CI state; always fresh-read.
- `research/antigravity/2026-10-11/MANIFEST.md` — durable empirical research inventory and hashes.

## 11. Known backfill gap

The largest remaining historical gap is not the current CadAgent/Antigravity research; that is durable. The gap is **source-level archival of early external-product investigations**, especially the original detailed CadMind packet and any per-product Scan2CAD / Raster Design / BLOCKIFY / Smart Blocks comparison material that existed only in chat or temporary research sessions.

Until those packets are recovered, this index preserves their role and known conclusions with conservative evidence labels so future chats neither forget them nor overclaim them.
