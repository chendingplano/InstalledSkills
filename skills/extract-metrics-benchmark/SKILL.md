---
name: extract-metrics-benchmark
description: Build an independently reviewed metric benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, audit completeness and correctness, and save evidence-backed metric snapshots in testbed.metrics for evaluating extract_metrics. Use for gold metrics, ground truth, or benchmark extraction; ordinary production extraction remains in kb.metrics.
---

# Extract Metrics Benchmark

Produce a complete, source-grounded benchmark for one document. The required input is a positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record. Creating this skill alone does not require a document ID or extracting a document.

This file is the shared procedure: resolving the source, preparing, validating, saving and reading back. **What counts as a metric, and how to annotate and audit it, is defined by a versioned rules file** in `rules/`. Every run uses exactly one rules version.

For every version: author the benchmark independently of `extract_metrics` predictions. Do not call the processor or preview extraction API, copy `kb.metrics`, or read its predictions until the benchmark is frozen.

## Versions

- `rules/versions.json` lists the released versions, the rules file for each, its SHA-256, and the `default` version.
- **Choose the version first.** If the user names a version (for example "run version 1.0.0", or to compare versions), use it. Otherwise use `default`. Comparing versions means separate runs of the same document, one per version, each with its own `benchmark_run_id`.
- **Read `rules/<rules file>` for that version completely before annotating**, and follow it in place of any rule you remember from another version. Do not mix rules from different versions in one run.
- Pass `--skill-version <version>` and `--model-name <exact ID of the model running this skill>` (for example `claude-opus-5-5` or `gpt-6.1-sol`; never guess or abbreviate it) to `scripts/benchmark_io.py prepare`. The helper refuses an unknown version or a rules file whose SHA-256 differs from `versions.json`, and stamps `skill_name`, `skill_version` and `model_name` on every saved row (plus `rules_sha256` in `ext_info`).
- **Released rules files are frozen.** Never edit one. To change the rules, copy the newest file to `rules/<new version>.md`, edit the copy, add it to `versions.json` with its SHA-256, and add a `CHANGELOG.md` entry. Bump major when the rules change which assertions are metrics, minor for compatible additions, patch for wording that does not change outcomes. To trial a draft, release it as a pre-release such as `2.0.0-rc.1`; it is frozen the same way. Change `default` only when the user asks.
- The tooling (`SKILL.md`, `references/benchmark-contract.md`, `scripts/`) is shared by all versions and always the latest. A tooling change must keep every released rules version runnable; if a rules version needs different validation, gate it by version in `benchmark_io.py`. Tooling changes are recorded in `CHANGELOG.md` and do not create a rules version.
- When comparing runs or scoring `extract_metrics`, report the skill version and the run ID.

## 1. Resolve and preserve the source

Read `ChenWeb/CLAUDE.md` and these workspace sources before extracting:

- `ChenWeb/KnowledgeStore/Capsules/coding-capsules/doc-processor/extract-metrics-spec.md`
- `ChenWeb/KnowledgeStore/Capsules/coding-capsules/input-management/+CAPSULE.md`
- `KnowledgeStore/doc-repo/specs/202604/2026042101-spec-line-file.md` (canonical format; the capsule's old `spec-line-file.md` link is stale)
- `ChenWeb/prompts/prompt-enrich-metrics-v7.md` for value enums, qualitative/reference rules, endpoints and conditions. Read it as the output contract, not as a substitute for independent annotation.

Read [references/benchmark-contract.md](references/benchmark-contract.md) for field names, payload shape, database setup and commands. Prefer current explicit requirements in the specification; resolve conflicts with the implementation contract before publishing.

Export exactly the requested `kb.inputs` row through the configured project PostgreSQL connection, using an integer parameter. Include `id`, `result_filename`, `parser_name`, `staging_filename`, `title`, `doc_no` and `doc_metadata`. Do not display credentials. An unavailable connection or missing ID blocks saving; continue local preparation where possible and report the exact gap.

Resolve the working `.txt` file using `docprocessing.ResolveInputFilePath` in `ChenWeb/server/api/doc-processing/event.go` and `pathutil.ResolveDataHomePath`. Normally it is next to `result_filename`, named `<staging filename stem>_<parser_name>.txt`. Relative result paths use `DATA_HOME_DIR`. `.origin` is the preserved original, not the working file. Never select the first matching file or silently regenerate/reparse a source.

Run `scripts/benchmark_io.py prepare` to validate the canonical seven TAB fields, record the source SHA-256, create a unique run ID and expose source lines. Keep its output in a local file and read it in bounded portions. Never confuse record line IDs with physical file lines, pages, table row IDs or chunk-local indexes. Fail on malformed records; do not fall back to five-field or space-delimited parsing. Investigate numbering gaps and parser damage.

## 2–4. Inventory, annotate and audit — follow the rules file

Sections 2–4 (candidate inventory, assertion resolution and the completeness/correctness audits) are in the selected `rules/<version>.md`. Apply them in full, then continue with section 5.

## 5. Validate, save and read back

Run `scripts/benchmark_io.py validate` before writing. It checks source identity/hash, complete coverage, candidate links, enums, excerpts and core types. It cannot verify semantic correctness, table row interpretation, translations or whether all candidates were discovered; those remain the reviewer's responsibility.

Inspect `testbed.metrics` and required columns. If absent, apply the committed Goose project migration `ChenWeb/project_migrations/20261006000001_create_testbed_metrics.sql` using the existing migration workflow; do not issue ad hoc DDL or copy production indexes/triggers. If incompatible, report differences and prepare a reviewed migration rather than adapting silently.

Run `save` when extracting/saving the requested document is authorized. The helper revalidates, checks `kb.inputs` identity and inserts all rows in one transaction. Runs are immutable snapshots with unique UUIDs. It never deletes benchmarks or writes `kb.metrics`, processing status, queues, embeddings, ontology, categories or production indexes. A failed transaction leaves no partial benchmark; inspect by run ID before retrying an ambiguous connection failure. An already-saved run ID is not a new run.

Read saved rows back by **both** `input_record_id` and `benchmark_run_id`, compare count/substantive fields to validated JSON, and verify evidence/provenance. Report success only after read-back matches. Keep payload/audit JSON so zero metrics also has a reviewable record; zero metrics creates no rows and must not be claimed as a stored snapshot.

Report document ID, source path/hash, run ID, saved count, coverage, uncertainty/limitations and audit location. When comparing predictions, select an explicit benchmark run; never concatenate snapshots or use benchmarks as predictions. Match complete assertions and provenance, not just names/numbers.
