# Fidelity Linetype Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement task-by-task.

**Goal:** Produce a hash-bound private DXF candidate that assigns an explicit dashed linetype only to observed horizontal dashed-line evidence.

**Architecture:** Add a focused function in `cad_agent.fidelity`, then a thin CLI wrapper in `cad_agent.cli`. Clone the supplied private DXF, change only matched LINE attributes, and write a `needs_review` report.

**Tech Stack:** Python 3.11, ezdxf, pytest.

## Constraints

- Fidelity output remains outside the worktree and cannot be used by Mechanical commands.
- Only existing horizontal LINE entities may change linetype.
- No model, text, dimension, hatch, or production mutation is included.

### Task 1: Core reconstruction using TDD

- [ ] Add `test_linetype_reconstruction_is_hash_bound_and_changes_only_matching_horizontal_lines` to `tests/test_cad_agent_fidelity.py`.
- [ ] Run it and confirm the missing-function failure.
- [ ] Implement `run_fidelity_linetype_reconstruct(source, output_root, manifest, observation_path, base_dxf, *, workspace_root) -> Path` in `cad_agent/fidelity.py`.
- [ ] Re-run the focused test and commit the core change.

### Task 2: CLI and verification

- [ ] Add a failing CLI invocation test and confirm the parser rejects it.
- [ ] Add `fidelity-linetype-reconstruct --input --manifest --observation --base-dxf` in `cad_agent/cli.py`.
- [ ] Run focused fidelity tests, `scripts/verify.ps1`, update `docs/STATUS.md`, and commit.
