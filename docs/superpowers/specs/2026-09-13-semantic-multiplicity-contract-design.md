# Semantic Multiplicity Contract

Approval date: 2026-09-13

Approval source: SOL PO 2 chat, exact user approval: APPROVE SEMANTIC MULTIPLICITY CONTRACT. Durable checkpoint: GitHub Issue #409 comment 5651230636.

Supported scope: Page-1 approved fidelity-layout reconstruction only, using the existing cad_agent.fidelity geometry mapping, filtering, and selection owner.

## Purpose

The existing review-only Hough filter collapses near-parallel raw detections by endpoint distance before the product has established whether they represent one semantic line occurrence or multiple real occurrences. This contract supplies source-bound semantic occurrence descriptors to that existing owner so it deduplicates only within one approved occurrence.

## Contract

- The approved PDF/render is the source of truth for visible line occurrences. Hough and RawLine output are candidate evidence only. Native DWG remains a read-only acceptance oracle and is never fed back into reconstruction.
- An approved region may carry a list of semantic geometry occurrences. Each occurrence has a unique stable id and a source-pixel line segment in the existing page pixel-top-left coordinate system.
- One semantic occurrence may map to one or more RawLine fragments. A RawLine is not itself a semantic occurrence.
- A raw candidate is eligible for duplicate comparison only when the existing mapping path assigns it to exactly one occurrence. Candidates assigned to distinct occurrences both survive even when their endpoints are within the old eight-pixel proximity gate.
- If a candidate maps to no occurrence or maps ambiguously to multiple occurrences, the filter fails closed for that candidate: it does not use semantic deduplication to remove it. The system does not guess or promote from an ambiguous mapping.
- Existing behavior without an approved occurrence mapping remains unchanged for backward compatibility. Semantic mode is explicit and hash-bound to the approved region proposal.
- The Hough extraction owner is unchanged. No new classifier, registry, geometry engine, transport, or public package boundary is introduced.

## Acceptance oracle

The causal RED/GREEN test contract includes:

1. Two near-parallel true occurrences survive as two lines.
2. Multiple raw detections mapped to one occurrence deduplicate while retaining that occurrence's coverage.
3. An ambiguous or unmapped candidate is retained rather than guessed away.

Page-1 replay additionally inspects occurrence recall, source-missing geometry, duplicate and near-duplicate population, unrelated line/entity population, and full approved-region visual evidence. An F1 increase alone is not acceptance.

## Non-goals

This design does not authorize source/customer drawing mutation, native DWG feedback into reconstruction, page-2 expansion, Hough parameter tuning, or reuse of the rejected component-identity candidate ancestry.
