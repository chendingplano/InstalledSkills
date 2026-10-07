---
name: extract-metrics-benchmark
description: Build an independently reviewed metric benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, audit completeness and correctness, and save evidence-backed metric snapshots in testbed.metrics for evaluating extract_metrics. Use for gold metrics, ground truth, or benchmark extraction; ordinary production extraction remains in kb.metrics.
disable-model-invocation: true
---

# Extract Metrics Benchmark

Produce a complete, source-grounded benchmark for one document. The required input is a positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record. Creating this skill alone does not require a document ID or extracting a document.

An invocation such as **"Use $extract-metrics-benchmark, version <version> for document <document-id>"** requests the complete workflow: extract independently, audit, validate, save a new snapshot in `testbed.metrics`, and verify it by read-back. The invocation authorizes that save; do not stop at a draft or ask for separate saving confirmation. Only an explicit draft-only/no-save instruction changes this outcome. The configured benchmark table is `testbed.metrics`.

This file is the shared procedure: resolving the source, preparing, validating, saving and reading back. **What counts as a metric, and how to annotate and audit it, is defined by a versioned rules file** in `rules/`. Every run uses exactly one rules version.

For every version: author the benchmark independently of `extract_metrics` predictions. Do not call the processor or preview extraction API, copy `kb.metrics`, or read its predictions until the benchmark is frozen.

## Versions

- `rules/versions.json` lists the released versions, the rules file for each, and its SHA-256.
- **Choose the version first.** If the user names a version (for example "run version 1.0.0", or to compare versions), use it. Otherwise use the newest released version (highest version number, compared numerically; pre-releases such as `2.0.0-rc.1` are used only when named). Tell the user which version you are using. Comparing versions means separate runs of the same document, one per version, each with its own `benchmark_run_id`.
- **Read `rules/<rules file>` for that version completely before annotating**, and follow it in place of any rule you remember from another version. Do not mix rules from different versions in one run.
- Pass `--skill-version <version>` and `--model-name <invoking model identity>` to `scripts/benchmark_io.py prepare`. Resolve the identity yourself as described below; it is not user input. The helper refuses an unknown version or a rules file whose SHA-256 differs from `versions.json`, and stamps `skill_name`, `skill_version` and `model_name` on every saved row (plus `rules_sha256` in `ext_info`).
- **Released rules files are frozen.** Never edit one. To change the rules, copy the newest file to `rules/<new version>.md`, edit the copy, add it to `versions.json` with its SHA-256, add a `CHANGELOG.md` entry, and update the "Available versions" table in `USER_MANUAL.md` (and its Change Log). Bump major when the rules change which assertions are metrics, minor for compatible additions, patch for wording that does not change outcomes. To trial a draft, release it as a pre-release such as `2.0.0-rc.1`; it is frozen the same way.
- The tooling (`SKILL.md`, `references/benchmark-contract.md`, `scripts/`) is shared by all versions and always the latest. A tooling change must keep every released rules version runnable; if a rules version needs different validation, gate it by version in `benchmark_io.py`. Tooling changes are recorded in `CHANGELOG.md` and do not create a rules version.
- When comparing runs or scoring `extract_metrics`, report the skill version and the run ID.

## Invoking model identity

`model_name` identifies the model invoking and executing this skill, not a project-configured extraction model, a model mentioned in an example, or a model the user must select for this run. Obtain it from the current runtime context or the active session's metadata. For Codex, when the context does not expose the exact ID, match `CODEX_THREAD_ID` (or `CODEX_SESSION_ID`) to its session file under `~/.codex/sessions/` and read the latest `turn_context.payload.model`; inspect only model metadata for this active session. Do not use another session's model or dump conversation contents.

Use the exact ID when available (for example `gpt-6.1-sol`). If the host exposes only a model label, use that supplied identity and record that only a label was exposed in the metrics' `annotation_notes`; do not invent a more specific ID. A missing exact API ID alone does not block extraction or saving. Do not ask the user to provide the invoking model identity.

## 1. Resolve and preserve the source

Read `ChenWeb/CLAUDE.md` and these workspace sources before extracting:

- `ChenWeb/KnowledgeStore/Capsules/coding-capsules/doc-processor/extract-metrics-spec.md`
- `ChenWeb/KnowledgeStore/Capsules/coding-capsules/input-management/+CAPSULE.md`
- `KnowledgeStore/doc-repo/specs/202604/2026042101-spec-line-file.md` (canonical format; the capsule's old `spec-line-file.md` link is stale)
- `ChenWeb/prompts/prompt-enrich-metrics-v8.md` for value enums, endpoints and conditions, and `ChenWeb/prompts/prompt-extract-metric-candidates-v11.md` for what the extractor is asked to find. These are the current defaults (since 2026-10-07: requirements with nothing to measure are not extracted). Read them as the output contract, not as a substitute for independent annotation. For rules 2.x runs, `prompt-enrich-metrics-v7.md` describes the qualitative/reference rows those rules still accept.

Read [references/benchmark-contract.md](references/benchmark-contract.md) for field names, payload shape, database setup and commands. Prefer current explicit requirements in the specification; resolve conflicts with the implementation contract before publishing.

Export exactly the requested `kb.inputs` row through the configured project PostgreSQL connection, using an integer parameter. Include `id`, `result_filename`, `parser_name`, `staging_filename`, `title`, `doc_no` and `doc_metadata`. Do not display credentials. An unavailable connection or missing ID blocks saving; continue local preparation where possible and report the exact gap.

Resolve the working `.txt` file using `docprocessing.ResolveInputFilePath` in `ChenWeb/server/api/doc-processing/event.go` and `pathutil.ResolveDataHomePath`. Normally it is next to `result_filename`, named `<staging filename stem>_<parser_name>.txt`. Relative result paths use `DATA_HOME_DIR`. `.origin` is the preserved original, not the working file. Never select the first matching file or silently regenerate/reparse a source.

Run `scripts/benchmark_io.py prepare` to validate the canonical seven TAB fields, record the source SHA-256, create the run ID (`yyyymmdd_hhmmss`, local time of `prepare`) and expose source lines. Keep its output in a local file and read it in bounded portions. Never confuse record line IDs with physical file lines, pages, table row IDs or chunk-local indexes. Fail on malformed records; do not fall back to five-field or space-delimited parsing. Investigate numbering gaps and parser damage.

## 2–4. Inventory, annotate and audit — follow the rules file

Sections 2–4 (candidate inventory, assertion resolution and the audits) are in the selected `rules/<version>.md`. Apply them in full, then continue with section 5. From rules 2.0.0 on, the rules file also defines the metric gate and the decision rules (`A*` accept, `X*` exclude, `D1` duplicate); every candidate records the `rule_id` that decided it. From rules 2.1.0 on, every accepted metric also records its statement kind (`kind:<kind>` tag: requirement, metric value, test parameter or definition, per ADR 2026100603). From rules 3.0.0 on, a requirement with nothing to measure is not a metric, matching `extract_metrics` since 2026-10-07: inspection requirements are excluded as X15 and delegations to a cited document as X16, and both stay in the candidate ledger. From rules 3.1.0 on, A4 (value left open) never supplies the object: a duty to agree or set an activity's time or frequency is X2. From rules 4.0.0 on, A4 needs a party that must declare or agree the value; a quantity to be set or sized according to another factor, or by design, is a requirement, not a metric (X17).

## 5. Validate, save and read back

Run `scripts/benchmark_io.py validate` before writing. It checks source identity/hash, complete coverage, candidate links, enums, excerpts and core types; for rules 2.0.0 and later it also checks each candidate's `rule_id` against the rules file, that `metric_value` carries no comparator, and the `strict_bound`, `test_condition` and `definition` constraints; for rules 2.1.0 and later it also checks that each metric's `kind:` tag matches its shape (the same rules the ChenWeb labels use), that `reference` rows are A3 delegations, that `interpretation_bound` rows are definition bounds, and that `cited_doc:` identifiers have a space before the number; for rules 3.0.0 and later it refuses any accepted row whose kind is `inspection_requirement`, `delegated_requirement` or `observation`, or that carries `value_class = reference`, `external_reference` or a `cited_doc:` tag. It cannot verify semantic correctness, table row interpretation, translations or whether all candidates were discovered; those remain the reviewer's responsibility.

Inspect `testbed.metrics` and required columns. If absent, apply the committed Goose project migration `ChenWeb/project_migrations/20261006000001_create_testbed_metrics.sql` using the existing migration workflow; do not issue ad hoc DDL or copy production indexes/triggers. If incompatible, report differences and prepare a reviewed migration rather than adapting silently.

Run `save` as part of the document invocation after validation and audit succeed, unless the user explicitly requested draft-only/no-save. Saving is already authorized by that invocation. The helper revalidates, checks `kb.inputs` identity and inserts all rows in one transaction. A run is identified by (`skill_name`, `skill_version`, `model_name`, `benchmark_run_id`); `save` refuses a run key that already has rows, so runs are never overwritten or extended and every save creates new records. Never edit `benchmark_run_id` to force a save. It never deletes benchmarks or writes `kb.metrics`, processing status, queues, embeddings, ontology, categories or production indexes. A failed transaction leaves no partial benchmark; inspect by run ID before retrying an ambiguous connection failure. An already-saved run ID is not a new run.

Read saved rows back by `input_record_id` and the full run key, compare count/substantive fields to validated JSON, and verify evidence/provenance. Report success only after read-back matches. Keep payload/audit JSON so zero metrics also has a reviewable record; zero metrics creates no rows and must not be claimed as a stored snapshot.

Report document ID, source path/hash, run ID, saved count, coverage, uncertainty/limitations and audit location. When comparing predictions, select an explicit benchmark run; never concatenate snapshots or use benchmarks as predictions. Match complete assertions and provenance, not just names/numbers.

Scoring `extract_metrics` (candidates prompt v11 / enrich prompt v8 or later) needs a rules 3.0.0 or later run; under 2.x the inspection and delegated rows are gold metrics the extractor deliberately drops. Score two things: the gold rows against `kb.metrics`, and the gold X15/X16 candidates against the run's `kb.doc_proc_logs` entry with `activity_name = 'exclude_pure_requirements'` (X15 ↔ `inspection_requirement`, X16 ↔ `delegated_requirement`). A pure requirement the extractor stored under another kind (for example a delegation stored as `limit_absent`, which the filter keeps) is a false positive, not a match. A 2.1.0 run can stand in only by dropping its `kind:inspection_requirement` and `kind:delegated_requirement` rows, and the report must say so.
