# INSERT finite rotation review

Approval date: 2026-10-14, PO authority in [GitHub issue #491 comment 6165622691](https://github.com/duongchi90/cad-agent/issues/491#issuecomment-6165622691).

## Approved scope

The headless DXF reviewer must reject an INSERT rotation comparison if either the saved/reopened actual rotation or the recorded expected rotation is non-finite. Finite rotations keep the existing absolute tolerance of `1e-4` degrees and the existing `rotation_deg` mismatch shape and message. Reviewing the candidate remains read-only.

This change is limited to `dxf_builder_lib/reviewer.py`, its existing regression tests, the module README, and this spec and execution plan. It does not define angle wrapping, a new rotation domain policy, scale behavior, or native AutoCAD acceptance.

## Reuse dossier

- Existing owner: `dxf_builder_lib/reviewer.py`, in the INSERT comparison within `review_dxf()`.
- Existing validation: `_scalar_matches(actual, expected, tolerance)` checks that both operands are finite and then applies the supplied absolute tolerance.
- Existing test fixture: `_build_beam_component()` in `dxf_builder_lib/tests/test_reviewer.py` writes a disposable INSERT candidate and returns its handle and path.
- Decision: reuse `_scalar_matches` for the existing rotation comparison after the saved-NaN regression proves the false pass. Do not add a validator, dependency, schema, owner, or transport.
- Base: `7da1ed42a2168b5c991fc389a4c8155b1e88a387`; base tree: `de41dc0707f695c085f0e40218d240e78cebdb8a`.

## Acceptance

1. A NaN rotation persisted in a saved/reopened candidate is rejected and reported as `rotation_deg`.
2. Positive and negative infinity actual/expected cases are rejected when representable by the existing DXF writer.
3. Equal and within-tolerance finite rotations pass; an outside-tolerance finite rotation fails.
4. Review does not change candidate bytes.
5. Focused and canonical verification evidence is recorded in the implementation plan; unavailable live/private gates remain explicitly not run.
