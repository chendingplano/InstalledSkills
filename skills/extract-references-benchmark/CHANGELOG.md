# Changelog — extract-references-benchmark

Two kinds of change are tracked separately:

- **Rules versions** — the annotation rules in `rules/<version>.md`, frozen once released and listed
  with their SHA-256 in `rules/versions.json`. `testbed.ref_mentions.skill_version` is the rules
  version a run used.
- **Tooling changes** — `SKILL.md` procedure, `references/`, `scripts/`, storage. Shared by all
  versions and always the latest; they must keep every released rules version runnable.

## Rules versions

| Version | Rules file | Notes |
|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | First release. See below. |

Default when no version is named: the newest released version (currently 1.0.0); pre-releases are
never the default.

### 1.0.0 — 2026-10-11

Derived from the reference model of `extract_references` (devdoc 2026101002 §3, openspec change
`extract-references-processor`, prompt `prompt-extract-references-v1.md`).

- Accept: external in-text references (A1), reference-list entries (A2), internal pointers (A3),
  indirect references to one specific resource (A4).
- Exclude: table of contents (X1), the document's own identity (X2), drafting metadata (X3), open
  classes such as "有关规定" (X4), non-pointers and captions (X5), actors and places in the content
  (X6), notices (X7), unnamed alternatives and examples (X8). D1 for duplicates.
- Choices the sources leave open, marked "(benchmark rule)" in the file: a numbered range gives one
  reference per list entry; internal references are never `criterion`/`criteria_set`; group
  standards (T/xxx) are `industry_standard`; unnamed alternatives and examples are X8.

## Tooling

### 2026-10-11 — first release

- `SKILL.md`, `references/benchmark-contract.md`, `USER_MANUAL.md`, `agents/openai.yaml`.
- `scripts/benchmark_io.py` (`prepare`, `validate`, `save`): mirrors the governed vocabularies of
  `reference_model.go`, identifier normalization of `reference_identifiers.go`, and recomputes
  normativity, list links and list mismatches as `reference_normativity.go` does.
- Storage: ChenWeb migration `20261011000003_create_testbed_ref_mentions.sql`
  (`testbed.reference_benchmark_runs`, `testbed.ref_mentions`, `testbed.ref_mentions_dropped`). The
  run ID column is `run_id` in all three tables.
- Tests: `scripts/test_benchmark_io.py`; `scripts/test_postgres_io.py` (opt-in, disposable cluster,
  `BENCHMARK_TEST_POSTGRES=1`).
