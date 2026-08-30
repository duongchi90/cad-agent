# M3 Task6 Provider Accounting Correction Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:test-driven-development. This is a bounded correction to the current M3 live acceptance oracle.

**Goal:** Prevent an M3 live PASS from undercounting the two canonical Task6 provider turns required by the pre-R5 and post-R5 chain.

**Architecture:** Reuse the existing canonical R5 result validator and current M3 record validator. Add only exact Task6 transport cardinality and ordered turn-ID binding; do not change other transport categories or introduce a provider/transport owner.

**Spec:** GitHub #305, #301, #311; critical advisory `5468460160`; source lookahead `5468458694`.

**Status:** executing

## Constraints

- `R5_MODE=contract-only` remains non-live; no provider/AutoCAD/NETLOAD/process action.
- Existing R4/R5/R6/R7/FileIPC/.NET owners and canonical result validators remain authoritative.
- Only `task6_provider` cardinality is tightened; no unrelated transport generalization.

## Tasks

- [x] Write causal REDs for Task6 attempts `1` and `3`, plus turn-ID drift.
- [x] Require exact two successful Task6 attempts and ordered pre/post turn IDs.
- [x] Run focused and nearest regressions, Ruff, and diff hygiene.
- [ ] Run canonical verifier on the clean exact candidate head.
- [ ] Push, hosted-verify, and merge only the bounded correction.

## Evidence

- Focused M3/Task6 suite: `21 passed`.
- Nearest M3/R5/R6 regression: `214 passed`.
- Live/provider/AutoCAD: `NOT RUN` by policy.
