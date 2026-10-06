# Changelog — extract-metrics-benchmark

The version is declared in `SKILL.md` frontmatter (`metadata.version`) and stored on every
`testbed.metrics` row as `skill_version`.

## 1.2.0 — 2026-10-06

- Rows also record `skill_name` (from SKILL.md `name`) and `model_name` (the model that ran the
  skill, passed as `prepare --model-name`, required). New columns `testbed.metrics.skill_name` and
  `model_name` (migration `20261006000003`). Run `22aa157c` backfilled as `gpt-6.1-sol`, found in its
  Codex session log.
- No change to annotation rules.

## 1.1.0 — 2026-10-06

- Skill is now versioned. `benchmark_io.py prepare` writes `skill_version` into the payload;
  `validate` rejects a payload prepared under a different version; `save` stores it in the new
  `testbed.metrics.skill_version` column (migration `20261006000002`).
- No change to annotation rules.

## 1.0.0 — 2026-10-06

- Initial skill (jj commit 9e18). Benchmark run `22aa157c-d712-46be-abc8-d7f195cff483`
  (record 416, 134 rows) was produced by this version; its rows were backfilled with
  `skill_version = '1.0.0'`. Known rule problems are documented in devdoc
  `2026100601-devdoc-gold-metrics-416-review` (pending a fix release).
