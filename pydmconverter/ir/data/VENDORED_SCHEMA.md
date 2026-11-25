# Vendored Canopy contracts

Everything in this directory except `VENDORED_SCHEMA.md`, `.gitignore` and
`widget-registry/` is **vendored**, not generated here. canopy-spec owns the
Canopy screen contract and the colour-scheme contract; canopy owns the default
colour scheme. This converter is a disposable consumer that must
produce IR the editor accepts. It validates its output against the vendored
screen schema (`validate_screen_json`); it does not mint any of these contracts.

## Pinned source

- Repo: `slaclab/canopy-spec`, the single canonical home of the Screen IR
  contract (the SDK's `@slaclab/canopy-screen-ir` copies its schema from there).
- Screen IR schema version: `1.1` (accepts documents declaring `1.0` or `1.1`).
  Both canopy-spec files are taken from canopy-spec v0.2.0 (`466fd0a`).
- Canonical macro-name pattern: `^[A-Za-z][A-Za-z0-9_]*$` (accepts lowercase —
  PyDM/EDM sources author `${dev}`/`${signal}`).
- Widget registry: **not vendored**. `widget-registry/*.json` holds only each
  type's `id`, `qtMapping` and `qtPropMap`; these files are the source of truth
  for the Qt mappings and are edited here (see `pydmconverter/ir/registry.py`).

## Vendored files

Each file is a byte copy of its source, taken from the committed file in the
source repo. Sources are repo-relative (`<repo>: <path>`).

| Vendored file | Source | sha256 |
|---|---|---|
| `screen-ir.schema.json` | `canopy-spec: screen-ir/screen-ir.schema.json` | `ec4352576211c113750f98eaa372e583856980e03d5e76340b539022c3099950` |
| `canopy-color-scheme-1.schema.json` | `canopy-spec: screen-ir/color-scheme.schema.json` | `df8f1e22d28263ce19b7c7726a61d78e12c866c0ad92565fe279a75cc39f83ce` |
| `schemes/canopy-default.json` | `canopy: src/canopy/core/data/canopy-default.json` | `0a8f403e70f0b9a5dc2eb9679da24f72f54209e19a8a9043d3de636e49ce810d` |

`tests/ir/test_vendored_data.py` pins these values and checks that the files ship
as package data.

## Re-vendoring

Because this tool is short-lived there is no live sync. To refresh, byte-copy
each file from its source above (`git show <commit>:<path>`, never an
uncommitted working tree), update the sha256 values here and in
`tests/ir/test_vendored_data.py`, then run `python -m pytest tests/ir` to confirm
converter output still validates. If validation fails, reconcile: fix converter
output, or file a change against the owning package — do NOT widen only the
converter's copy.
