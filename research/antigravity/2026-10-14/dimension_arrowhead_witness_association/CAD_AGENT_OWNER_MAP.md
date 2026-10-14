# CAD_AGENT_OWNER_MAP: Existing Owners & Anti-Bloat Architecture

- **Document ID:** `REA_DIM_ASSOC_OWNER_MAP_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`
- **Correction:** `OWNER_CLAIM_CORRECTED_2026-10-14` — Prior version incorrectly stated that `models.py` and `builder.py` already stored and consumed P1/P2 feature points and dimension-line offset. This has been corrected below.

---

## 1. Mapping to Existing Main Codebase Owners

| Component | What It Currently Contains (Verified on main) | Gap Introduced by REA-021 | Status on Main |
| :--- | :--- | :--- | :---: |
| **`primitive_ir_lib/cross_validation.py`** | Selects the nearest `RawLine` to each `RawText` via unconstrained Euclidean distance (`find_nearest_line`). Stores only one line ID per text. Does NOT perform angular discriminaton against witness lines. | **GAP:** No angular pre-filter exists; witness-line misbinding is a current failure mode. | **EXISTING_OWNER** (requires augmentation) |
| **`primitive_ir_lib/models.py` (`CrossValidation`)** | Currently stores: `text_primitive_id`, `geometry_primitive_id` (one line ID), `status`, `text_value`, `geometry_measured_length`, `delta_percent`, `match_threshold_percent`. Does NOT store feature points $P_1$/$P_2$ or dimension-line offset. | **GAP:** Schema has no fields for $P_1$, $P_2$, or $P_\text{base}$. These must be added to enable ezdxf to receive correct DXF definition points. | **EXISTING_OWNER** (schema gap) |
| **`dxf_builder_lib/builder.py`** | Receives a `CrossValidation` object and calls `msp.add_linear_dim`. Currently derives dimension line position from referenced `RawLine` endpoints only, not from resolved feature-definition points. | **GAP:** Cannot pass correct DXF Group Code 13/14 definition points ($P_1$, $P_2$) until `CrossValidation` is extended and the discriminator populates them. | **EXISTING_OWNER** (requires input extension) |

---

## 2. Precise Gap Statement

The REA-021 research oracle proves a clean-room discriminator algorithm that resolves $P_1$, $P_2$, and $P_\text{base}$ from scanned raster geometry. However:

> **PRODUCTION_GAP:** This capability does NOT currently exist in any production owner. The production `CrossValidation` schema carries no feature-point fields. The production `cross_validate()` function performs no angular discrimination. A future production implementation requires:
> 1. A measured product RED demonstrating witness-line misbinding on a real drawing.
> 2. A schema extension to `CrossValidation` adding $P_1$, $P_2$, $P_\text{base}$ fields.
> 3. Integration of the 3-stage discriminator into `cross_validate()` replacing the naive `find_nearest_line`.
> 4. A `MEASURED_CURRENT_PRODUCT_RED` + `ACTUAL_OWNER_DISCRIMINATOR` before production promotion.

This research prior provides the design contract and oracle only. It does not authorize production transfer.

---

## 3. Anti-Bloat Principles

1. **NO New Subsystem:** Do **not** create a separate `dimension_association_service/` or `arrowhead_graph_parser/`. The logic consists of pure vector trigonometry to be added into `cross_validation.py`.
2. **NO External Dependency:** Zero dependencies outside Python standard library (`math`, `dataclasses`).
3. **Backwards Compatibility:** When implementing, existing callers passing `raw_texts` and `raw_lines` to `cross_validate()` must retain identical signatures; the discriminator would run as an internal enhancement before falling back to Euclidean nearest-line if no witness lines are detected.
