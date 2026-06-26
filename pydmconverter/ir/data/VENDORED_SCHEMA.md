# Vendored `@canopy/screen-ir` schema

`screen-ir.schema.json` in this directory is **vendored**, not generated here.
`@canopy/screen-ir` owns the Canopy screen contract; this converter is a
disposable consumer that must produce IR the editor accepts. The converter
validates its output against this file (`validate_screen_json`); it does not
mint the contract.

## Pinned source

- Package: `@canopy/screen-ir`
- Version: `0.2.0` (`package.json` at the pinned commit)
- Repo: `canopy-screen-builder`, branch `main` (PR #2 merged)
- Commit: `affddbc` ("Add @canopy/screen-ir: the canonical, read-tolerant
  screen IR" — step 1; on `main` via merge `a706d4a`)
- Source path in that repo: `packages/screen-ir/schema/screen-ir.schema.json`

## Re-vendoring

Because this tool is short-lived there is no live sync. To refresh, copy the
file from the pinned source path above and update the commit/version here, then
run `python -m pytest tests/ir/test_ir_schema.py` to confirm converter output
still validates. If validation fails, reconcile per
`plans/converter-conformance-handoff.md`: fix converter output, or file a change
against `@canopy/screen-ir` — do NOT widen only the converter's copy.
