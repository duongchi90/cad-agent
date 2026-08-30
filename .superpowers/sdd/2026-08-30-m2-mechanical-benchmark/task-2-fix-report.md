Task 2 fix report

Commit base: `f0c8e6a`

Root cause

Fresh builds of the same Task 2 fixture produced different staged DXF bytes because `ezdxf` serialized non-deterministic metadata into the saved DXF. A direct byte diff between two empty-root builds showed the geometry was stable, but the staged files diverged in `$FINGERPRINTGUID`, `$VERSIONGUID`, and the embedded `1.4.4 @ <timestamp>` banner. The fixture originally hashed the staged DXF immediately after build, so the recorded staged hash was not reproducible across fresh roots.

Change made

- Normalized the staged DXF bytes in `tests/m2_benchmark_support.py` immediately after `build_dxf()` writes the file and before build evidence is written.
- Replaced all GUID-shaped values in the staged DXF with a fixed sentinel GUID.
- Replaced the ezdxf version/timestamp banner with a fixed sentinel banner.
- Added a regression test in `tests/test_m2_benchmark.py` that builds the fixture twice in two fresh empty roots and asserts:
  - the input hashes match;
  - the staged DXF hashes match;
  - the raw staged DXF bytes are identical;
  - each staged hash equals the raw SHA-256 of its file.

Files changed

- `tests/m2_benchmark_support.py`
- `tests/test_m2_benchmark.py`

Verification

- `& .\.venv-py311\Scripts\python.exe -m pytest tests\test_m2_benchmark.py -q -p no:cacheprovider`
  - Result: `44 passed`
- `& .\.venv-py311\Scripts\ruff.exe check tests\m2_benchmark_support.py tests\test_m2_benchmark.py`
  - Result: `All checks passed!`
- `git diff --check`
  - Result: clean, with only Git line-ending warnings in the working copy
- Manual byte inspection
  - Two fresh-root builds were compared directly and the differing bytes were isolated to DXF metadata, not geometry.

Residual concern

- The normalization is intentionally test-support-only and keeps the builder/reviewer/evidence reuse path intact, but it does encode knowledge of ezdxf’s current metadata output. If ezdxf changes that metadata format in a future upgrade, this fixture helper may need one more normalization rule.
