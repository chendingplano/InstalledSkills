# Changelog — extract-products-benchmark

Two kinds of change are tracked separately:

- **Rules versions**: the annotation rules in `rules/<version>.md`. A rules file is frozen once
  released and is listed with its SHA-256 in `rules/versions.json`.
  `testbed.products.skill_version` is the rules version a run used.
- **Tooling changes**: the `SKILL.md` procedure, `references/`, `scripts/` and storage. Tooling is
  shared by all versions and always the latest, so it must keep every released rules version
  runnable.

## Rules versions

| Version | Rules file | Notes |
|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | First release. See below. |

Default when no version is named: the newest released version (currently 1.0.0). Pre-releases are
never the default.

### 1.0.0 — 2026-11-08

First release. It follows the product model of `extract_products` (capsule
`extract-products-spec.md` and its producthood gate; prompts `prompt-extract-product-mentions-v2.md`,
`prompt-enrich-product-mention-v4.md`, `prompt-extract-products-merged-v2.md`).

User rulings (openspec change `extract-products-benchmark`):

- One gold row is one (product, `relation_type`) pair, as in `kb.products`; rows of one product
  share `product_key`.
- Waste categories and waste streams are products (`product_class` or `material`).
- Obligation level, requirement text (exact source text), conditions, exceptions, parameters,
  related products and responsible actor are recorded and graded.
- The first gold run is record 416.

Benchmark rules (open for a later version): distinct names are distinct products unless they
differ only by normalization or the document equates them; table lines are cited by rows;
provide/equip duties and waste treatment duties are `requirement_target`; deposit and transport
duties for wastes are `storage_requirement`; a substance named only as a limited quantity is a
property (X5).

## Tooling changes

### 2026-11-08

- First release of `scripts/benchmark_io.py` (prepare / validate / save) with a port of ChenWeb's
  `ParseTableGrid` (`TableGridVersion` 3) for `N#rK` spans; parity checked against Go on 390
  tables from 154 documents.
