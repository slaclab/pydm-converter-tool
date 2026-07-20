# Vendored `@slaclab/canopy-screen-ir` schema

`screen-ir.schema.json` in this directory is **vendored**, not generated here.
`@slaclab/canopy-screen-ir` owns the Canopy screen contract; this converter is a
disposable consumer that must produce IR the editor accepts. The converter
validates its output against this file (`validate_screen_json`); it does not
mint the contract.

## Pinned source

- Package: `@slaclab/canopy-screen-ir` (the shared SDK contract package;
  canopy-sdk-js issue #2). This is the single canonical home — the previous
  `@canopy/screen-ir` copy in `canopy-screen-builder` and the workspace copy in
  `canopy-screen-runtime` are being retired in favor of it.
- Repo: `slaclab/canopy-sdk-js`, path `packages/screen-ir/schema/screen-ir.schema.json`
- Release: `v0.1.1` (published; package version `0.1.0`)
- Canonical macro-name pattern: `^[A-Za-z][A-Za-z0-9_]*$` (accepts lowercase —
  PyDM/EDM sources author `${dev}`/`${signal}`).

## Re-vendoring

Because this tool is short-lived there is no live sync. To refresh, copy the
file from the pinned source path above and update the source note here, then run
`python -m pytest tests/ir/test_ir_schema.py` to confirm converter output still
validates. If validation fails, reconcile: fix converter output, or file a
change against `@slaclab/canopy-screen-ir` — do NOT widen only the converter's copy.
