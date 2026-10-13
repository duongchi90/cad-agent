# CAD_AGENT_OWNER_MAP: Existing Owners & Anti-Bloat Architecture

- **Document ID:** `REA_DIM_ASSOC_OWNER_MAP_V1`
- **Executor Role:** `CAD_AGENT_REA_GHIDRA_CROSS_MACHINE_RESEARCH_EXECUTOR`
- **Workstation Role:** `ANTI_HOME_RESEARCH_MACHINE`
- **Project:** `duongchi90/cad-agent`

---

## 1. Mapping to Existing Main Codebase Owners

| Component | Responsibility in Main | Integration Role for REA-021 | Status on Main |
| :--- | :--- | :--- | :---: |
| **`primitive_ir_lib/cross_validation.py`** | Associates `RawText` with `RawLine` to confirm dimension values. | Ingests the 3-stage discriminator to prevent witness-line misbinding and pair extension lines. | **EXISTING_OWNER** |
| **`primitive_ir_lib/models.py`** | Data models matching `primitive_ir.schema.json`. | Stores verified feature points ($P_1, P_2$) and dimension line offset in `CrossValidation`. | **EXISTING_OWNER** |
| **`dxf_builder_lib/builder.py`** | Generates native DXF entities (`msp.add_linear_dim`). | Consumes verified feature points ($P_1, P_2$) to pass exact definition points to `ezdxf`. | **EXISTING_OWNER** |

---

## 2. Anti-Bloat Principles

1. **NO New Subsystem:** Do **not** create a separate `dimension_association_service/` or `arrowhead_graph_parser/`. The logic consists of pure vector trigonometry easily encapsulated in a single helper module or added directly to `cross_validation.py`.
2. **NO External Dependency:** Zero dependencies outside Python standard library (`math`, `dataclasses`).
3. **Backwards Compatibility:** Existing callers passing `raw_texts` and `raw_lines` to `cross_validate()` retain identical signatures; the discriminator runs as an internal enhancement before falling back to Euclidean nearest-line if no witness lines are detected.
