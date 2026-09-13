# External Authenticated GitHub Decision Reader V1

## Status and authority

- Status: `PROPOSED_CONTRACT_ONLY_NOT_IMPLEMENTED`
- Issue: #409
- Exact planning base: `bda58859bbd8a90c2ec606eab4d79d03b16321e6`
- First unsatisfied boundary: `REAL_PAGE1_SOURCE_FUSION_OCCURRENCE_ACCEPTANCE`
- Candidate state: `FROZEN_NON_PASS`
- This record defines a missing capability boundary only. It does not authorize
  a workflow change, runtime implementation, candidate promotion, merge, or
  source/accepted-drawing mutation.

The real GitHub record currently available for this lane is comment
`5651227165` on issue #409. It is an OWNER-authored design decision for the
semantic-multiplicity contract, but its own text explicitly excludes occurrence
issuance, occurrence population, implementation approval, and promotion. It is
therefore not an input that can issue Page-1 occurrence authority.

## Decision summary

The repository has no existing production owner that can read a canonical
PO/HUMAN decision for issue #409, verify its exact occurrence scope, and hand
an authenticated result to the existing approval consumer without allowing an
ordinary CAD-Agent caller to mint the same result.

The missing capability is named:

```text
EXTERNAL_AUTHENTICATED_GITHUB_DECISION_READER_V1
```

It is an external trust boundary that consumes a fresh canonical GitHub
issue-comment record and emits one opaque, authenticated decision result. The
future thin `github_decision_witness` adapter may consume that result and
project it into the existing `VerifiedApprovalDecision` seam. Neither
`APPROVAL_V1` nor the CAD-Agent runtime may fetch GitHub, authenticate the
author, or mint the opaque result.

The concrete execution host remains deliberately unselected. In particular,
the local-executor watchdog is a control-plane liveness owner for issues 131
and 294 and must not be expanded into a semantic approval issuer.

## Boundary contract

### Trusted input

The external boundary must obtain a fresh canonical GitHub response for the
repository and issue under review. The authenticated result must bind, at
minimum:

- repository identity: `duongchi90/cad-agent`;
- issue identity: `409`;
- immutable comment identity: comment ID, node ID, and immutable reference;
- authenticated author identity and authority class (`PO` or `HUMAN`);
- exact comment body bytes and their SHA-256;
- explicit decision: `APPROVED`;
- approval identity and approval reference;
- occurrence-approval scope;
- exact source PDF SHA-256, Page-1 identifier, render SHA-256, and sorted
  semantic occurrence IDs.

Authentication is a property of the external reader boundary and its
canonical GitHub response, not a claim carried by caller-supplied mapping
fields. `OWNER`, a node ID, a body hash, or an immutable-looking reference is
not sufficient when those values are merely supplied by the ordinary caller.

### Opaque output

The boundary emits an opaque `AuthenticatedGitHubDecisionRecord` with the
bindings above. Ordinary CAD-Agent code must not be able to construct an
accepted record by importing a public constructor, calling a factory,
subclassing a nominal type, or passing a byte/field-identical mapping.

The downstream composition is exactly:

```text
external authenticated GitHub decision result
  -> thin github_decision_witness adapter
  -> existing VerifiedApprovalDecision
  -> SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1 binder
```

The adapter may preserve and project the authenticated decision. It may not:

- read GitHub or introduce a new transport;
- decide that a mapping is authenticated from fields inside the mapping;
- mint a new approval identity, authority class, reference, or scope;
- add a registry, store, queue, daemon, signature system, or second authority
  database;
- widen `source_integrity`, `source_fusion`, repair authorization, action
  approval, the watchdog, or a development-agent/provider path.

### Required exact scope

Only a decision whose scope is explicitly
`SOURCE_BOUND_SEMANTIC_OCCURRENCE` may issue the downstream occurrence
authority. The scope must match all of the following exactly:

```text
source_pdf_sha256
page_id
render_sha256
sorted occurrence_ids
```

A contract-only decision such as comment `5651227165` has a different scope and
must remain occurrence-ineligible, even though its author and repository
identity are real and fresh.

## Fail-closed oracle

The contract is satisfied only if the external boundary rejects each of these
cases before `VerifiedApprovalDecision` or `APPROVAL_V1` can become current:

1. comment `5651227165` used as an occurrence approval;
2. altered comment body, body hash, comment ID, node ID, or immutable
   reference;
3. repository or issue other than the canonical `duongchi90/cad-agent` / 409
   decision record;
4. missing, wrong, or unverified author/authority class;
5. a decision other than explicit `APPROVED`;
6. missing or non-occurrence scope;
7. source PDF, Page-1, render, or occurrence-ID binding mismatch;
8. caller-created mapping, nominal lookalike, or result replayed outside the
   external reader boundary.

The positive contract case is a fresh external result whose `APPROVED`
decision binds the exact source/page/render/occurrence set. That case is a
contract oracle only until a real approved Page-1 decision is independently
created and verified; synthetic positive fixtures are never product evidence.

## Existing-owner and reuse dossier

Reuse is intentionally narrow:

- reuse the existing GitHub Actions authenticated-read pattern only as
  transport precedent;
- reuse the existing `VerifiedApprovalDecision` and
  `SOURCE_BOUND_SEMANTIC_OCCURRENCE_APPROVAL_V1` consumer/binder;
- keep `source_integrity` and `source_fusion` as custody/currentness/
  provenance owners;
- keep agent-action approval and repair authorization in their existing
  operation scopes;
- keep `codex_worker` and visual-supervisor/provider outputs untrusted;
- exclude the local-executor watchdog and ChatGPT/Codex development-agent
  mechanisms from semantic approval ownership.

No current existing API issues the required external result. The capability is
therefore recorded as `NEW_MISSING_CAPABILITY`, not hidden behind a new
in-process constructor or a broadened existing owner.

## Acceptance and lifecycle locks

This specification does not create Page-1 evidence and does not change the
current real-source state: the current BVTL Page-1 source/render custody is
fresh, but only 2 of 517 semantic line occurrences are mapped and 515 remain
unresolved. The candidate remains `FROZEN_NON_PASS`.

Before any future implementation, a new bounded action must separately name
the concrete privileged execution boundary, its allowed files, its
authentication policy, and its exact review/CI/evidence gates. A production
GREEN is forbidden while the issuer boundary remains unselected or while the
only real decision is comment `5651227165`.

This record is contract/design evidence only. It is not a PO/HUMAN occurrence
approval, a real Page-1 source-fusion evidence packet, a candidate acceptance,
or a merge authorization.
