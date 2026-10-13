# BLIND_BEHAVIORAL_SPEC: Clean-Room CAD Stream Format

## 1. Input Contract
- **Stream Header Buffer:** Minimum 16 bytes.
  - Bytes 0..3: Little-endian 32-bit unsigned integer matching magic `0x43414453` ('CADS').
  - Bytes 4..5: 16-bit unsigned integer version ($1 \le \text{version} \le 2$).
  - Bytes 6..7: 16-bit unsigned integer declared entity count.
  - Bytes 8..15: 64-bit IEEE 754 float global scale factor.
- **Entity Record Payloads:** Packed binary records with byte type tag ($1, 2, 3$) followed by double-precision coordinate pairs.

## 2. Output Contract
- **Return Status:** Signed 32-bit integer:
  - `0`: Success (`CAD_OK`).
  - `-1`: Null pointer argument.
  - `-2`: Magic mismatch (non-CAD stream).
  - `-3`: Version mismatch / unsupported revision.
  - `-4`: Buffer overrun / insufficient input length.
  - `-5`: Degenerate or empty bounding box.
  - `-6`: Invalid entity opcode.
  - `-7`: Coordinate out of range ($|coord| > 100000.0$).
- **Calculated State:** Minimum enclosing axis-aligned bounding box $[min_x, min_y, max_x, max_y]$ encompassing all successfully parsed geometries.

## 3. State Machine Transitions
```text
STATE_UNINITIALIZED (0)
  |-- [cad_parser_init] --> STATE_UNINITIALIZED (0)
  |-- [cad_parse_header SUCCESS] --> STATE_HEADER_PARSED (1)
  |-- [cad_parse_header FAILURE] --> STATE_ERROR (4)

STATE_HEADER_PARSED (1)
  |-- [cad_decode_entity SUCCESS] --> STATE_ENTITIES_ACTIVE (2)
  |-- [cad_decode_entity FAILURE] --> STATE_ERROR (4)

STATE_ENTITIES_ACTIVE (2)
  |-- [cad_decode_entity SUCCESS] --> STATE_ENTITIES_ACTIVE (2)
  |-- [cad_decode_entity FAILURE] --> STATE_ERROR (4)
  |-- [cad_parser_finalize SUCCESS] --> STATE_COMPLETED (3)
  |-- [cad_parser_finalize FAILURE] --> STATE_ERROR (4)

STATE_ERROR (4)
  |-- (Terminal failure sink; subsequent calls return last_error)
```

## 4. Observed Constants & Tolerances
- `MAGIC_SIGNATURE` = `0x43414453`
- `VERSION_MAX` = `2`
- `COORD_LIMIT` = `100000.0`
- `OPCODE_LINE` = `1`
- `OPCODE_CIRCLE` = `2`
- `OPCODE_NODE` = `3`

## 5. Unknown / Unverified Semantics
- Semantic interpretation of `global_scale` during decoding (whether it scales bounding box or remains passive metadata).
- RGB color field usage in entity records (observed loaded into struct, but no downstream rasterization logic).
