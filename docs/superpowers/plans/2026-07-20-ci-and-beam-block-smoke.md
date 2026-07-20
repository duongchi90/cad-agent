# CI and Beam Block Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline GitHub Actions regression gate and verify a real AutoCAD `COMP_FRAME_BEAM` INSERT with attributes can be reviewed and repaired.

**Architecture:** CI runs the existing offline pytest command with Python 3.11. The opt-in smoke builds a beam, opens it through File IPC, reads its INSERT/attributes, corrupts one attribute, repairs the DXF, reopens it, and verifies it again.

**Tech Stack:** GitHub Actions, Python 3.11, pytest, ezdxf, AutoCAD File IPC/AutoLISP.

## Global Constraints

- CI has no AutoCAD HWND, API key, or `CAD_AGENT_FILE_IPC` variable.
- The real smoke requires `CAD_AGENT_FILE_IPC=1`, `CAD_AGENT_AUTOCAD_HWND`, and `CAD_AGENT_AUTOCAD_LISP_PATH`.
- Scope is `COMP_FRAME_BEAM`; bracket, panel, and hinge are separate future smoke tests.

---

### Task 1: Offline GitHub Actions gate

**Files:** Create `.github/workflows/tests.yml`.

- [ ] Write the workflow for `push` and `pull_request` on `windows-latest`, with Python 3.11.
- [ ] Install `requirements.txt`, `pytest`, `python-solvespace`, and Tesseract via Chocolatey.
- [ ] Run `python -m pytest primitive_ir_lib/tests semantic_ir_lib/tests dxf_builder_lib/tests mcp_integration_lib/tests agent_lib/tests -q`.
- [ ] Validate the same command locally; expected result is the full suite passing with AutoCAD smoke skipped.
- [ ] Commit with `ci: run offline test suite on GitHub Actions`.

### Task 2: File IPC block attribute mapping

**Files:** Modify `mcp_integration_lib/mcp_client.py`; test `mcp_integration_lib/tests/test_phase4.py`.

- [ ] Add failing mapping tests that expect `FileIPCLiveMCPClient.block_get_attributes("10")` to dispatch `block-get-attributes` and `block_update_attribute("10", "PART_ID", "wrong")` to dispatch `block-update-attribute`.
- [ ] Run the focused test and confirm it fails with no `block_get_attributes` method.
- [ ] Add `block_get_attributes(entity_id: str) -> Dict[str, str]` and `block_update_attribute(entity_id: str, tag: str, value: str) -> None` to the MCP protocol, fake client, File IPC client, and callback-backed live client.
- [ ] Run `python -m pytest mcp_integration_lib/tests/test_phase4.py -q`; expected result: all pass.
- [ ] Commit with `feat: query block attributes through File IPC`.

### Task 3: Real beam INSERT review and repair

**Files:** Modify `mcp_integration_lib/tests/test_file_ipc_e2e.py` and `HANDOFF.md`.

- [ ] Add a failing opt-in test that builds a semantic `thanh_ngang` beam with `build_dxf(..., semantic_doc=...)`, opens the DXF, and expects a real `INSERT` named `COMP_FRAME_BEAM` with `PART_ID` equal to the expected part id.
- [ ] Run it with the three AutoCAD environment variables and confirm the failure occurs before the new mapping is implemented.
- [ ] Deliberately change `PART_ID` through File IPC, use `review_dxf` to collect component mismatches, run `repair_insert_components`, reopen the DXF, and assert block name, transform, and restored attributes.
- [ ] Run the opt-in smoke and the full offline pytest suite; both must pass.
- [ ] Record the exact opt-in command in `HANDOFF.md` and commit with `test: verify beam block repair through real AutoCAD`.
