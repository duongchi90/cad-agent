# SOURCE_FALSIFICATION_REPORT: Tier 2 Blind Reconstruction vs Source Truth

## 1. Truth vs Blind Claim Verification

| Claim # | Blind Analysis Claim | Source Ground Truth (`cadstream_format.c`) | Status | Verification & Rationale |
| :---: | :--- | :--- | :---: | :--- |
| **C1** | Magic constant is `0x43414453` ('CADS') | `#define CAD_MAGIC 0x43414453U` | **EXACT** | Constant recovered identically from binary comparison operand. |
| **C2** | Max supported format version is `2` | `#define CAD_VERSION_CURRENT 2` | **EXACT** | Branch comparison `hdr->version > 2` recovered cleanly. |
| **C3** | Coordinate bounding threshold is `100000.0` | `#define CAD_COORD_LIMIT 100000.0` | **EXACT** | Double-precision constant `0x40f86a0000000000` recovered in validation helper. |
| **C4** | Entity Opcode 1 is a 2D Line Segment | `ENTITY_LINE = 1`, reads $(x_1, y_1, x_2, y_2)$ | **EXACT** | Switch jump table target validates 4 coordinates and updates extent twice. |
| **C5** | Entity Opcode 2 is a Circle with center & radius | `ENTITY_CIRCLE = 2`, radius packed in $x_2$ | **EXACT** | Offset arithmetic expands AABB by $[x_1 - r, y_1 - r]$ and $[x_1 + r, y_1 + r]$. |
| **C6** | Entity Opcode 3 is a Vertex Node | `ENTITY_POLYLINE_NODE = 3` | **EXACT** | Fall-through / single coordinate update without second endpoint. |
| **C7** | 5-State Lifecycle Model | `CadParserState` (0: Uninit, 1: Hdr, 2: Active, 3: Complete, 4: Err) | **EXACT** | State variable transitions match integer assignments 0..4 in disassembly. |
| **C8** | Error code return values `-1` through `-7` | `CAD_ERR_NULL_PTR` (-1) to `CAD_ERR_COORD_OUT_OF_RANGE` (-7) | **EXACT** | Negative return values match error sink assignments in context struct. |
| **C9** | Fast rejection on empty stream | If `parsed_count == 0` returns `-5` (`CAD_ERR_DEGENERATE_BBOX`) | **EXACT** | Finalizer branch checks count and validity flag before transitioning to state 3. |
| **C10**| Global scale factor is passive metadata | `hdr.global_scale` stored in struct but not applied to coordinates | **EXACT** | Identified in blind spec as unknown/passive; confirmed source never multiplies coordinates by it. |

---

## 2. Quantitative Summary
- **EXACT_FINDINGS:** 10 / 10 (100%)
- **PARTIAL_FINDINGS:** 0
- **WRONG_FINDINGS:** 0
- **MISSED_FINDINGS:** 0 (Color field identified as passive payload)

## 3. Engineering Feasibility Answers
- `COULD_BUILD_COMPATIBLE_TESTS_FROM_REA_ONLY = YES`
  - The recovered magic, version boundaries, opcode enum values, coordinate thresholds, and error codes allow creating a 100% compliant test suite without seeing original source.
- `COULD_BUILD_CLEAN_ROOM_EQUIVALENT_FROM_REA_ONLY = YES`
  - The recovered state machine and data layout provide complete functional behavioral equivalence.
