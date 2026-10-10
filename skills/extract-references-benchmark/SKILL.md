---
name: extract-references-benchmark
description: Build an independently reviewed reference benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, find and label every reference (external citations, reference-list entries, internal pointers), audit completeness and correctness, and save evidence-backed snapshots in testbed.ref_mentions for evaluating extract_references. Use for gold references, ground truth, or reference benchmark extraction; production references remain in kb.ref_mentions.
disable-model-invocation: true
---

# Extract References Benchmark

Produce a complete, source-grounded reference benchmark for one document. The required input is a positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record. Creating this skill alone does not require a document ID or extracting a document.

An invocation such as **"Use $extract-references-benchmark, version <version> for document <document-id>"** requests the complete workflow: extract independently, audit, validate, save a new snapshot, and verify it by read-back. The invocation authorizes that save; do not stop at a draft or ask for separate saving confirmation. Only an explicit draft-only/no-save instruction changes this outcome. The benchmark tables are `testbed.reference_benchmark_runs`, `testbed.ref_mentions` and `testbed.ref_mentions_dropped`.

This file is the shared procedure: resolving the source, preparing, validating, saving and reading back. **What counts as a reference, and how to label and audit it, is defined by a versioned rules file** in `rules/`. Every run uses exactly one rules version.

For every version: author the benchmark independently of `extract_references` predictions. Do not call the processor or a preview API, copy `kb.ref_mentions`, or read its rows until the benchmark is frozen.

## Versions

- `rules/versions.json` lists the released versions, the rules file for each, and its SHA-256.
- **Choose the version first.** If the user names a version, use it. Otherwise use the newest released version (highest version number, compared numerically; pre-releases such as `2.0.0-rc.1` are used only when named). Tell the user which version you are using. Comparing versions means separate runs of the same document, one per version, each with its own `run_id`.
- **Read `rules/<rules file>` for that version completely before annotating**, and follow it in place of any rule you remember from another version. Do not mix rules from different versions in one run.
- Pass `--skill-version <version>` and `--model-name <invoking model identity>` to `scripts/benchmark_io.py prepare`. The helper refuses an unknown version or a rules file whose SHA-256 differs from `versions.json`, and stamps `skill_name`, `skill_version` and `model_name` on every saved row (plus `rules_sha256` in the run row).
- **Released rules files are frozen.** Never edit one. To change the rules, copy the newest file to `rules/<new version>.md`, edit the copy, add it to `versions.json` with its SHA-256, add a `CHANGELOG.md` entry, and update the "Available versions" table in `USER_MANUAL.md` (and its Change Log). Bump major when the rules change which occurrences are references or how a label is decided, minor for compatible additions, patch for wording that does not change outcomes. To trial a draft, release it as a pre-release such as `2.0.0-rc.1`; it is frozen the same way.
- The tooling (`SKILL.md`, `references/benchmark-contract.md`, `scripts/`) is shared by all versions and always the latest. A tooling change must keep every released rules version runnable; if a rules version needs different validation, gate it by version in `benchmark_io.py`. Tooling changes are recorded in `CHANGELOG.md` and do not create a rules version.
- The governed vocabularies in `benchmark_io.py` mirror `ChenWeb/server/api/doc-processing/reference_model.go`. When the application's vocabulary changes, release a new rules version that says so and update the mirror, gated by version if older runs would no longer validate.

## Invoking model identity

`model_name` identifies the model invoking and executing this skill, not the project's configured `EXTRACT_REFERENCES_MODEL_NAME`, a model mentioned in an example, or a model the user must select. Obtain it from the current runtime context or the active session's metadata. For Codex, when the context does not expose the exact ID, match `CODEX_THREAD_ID` (or `CODEX_SESSION_ID`) to its session file under `~/.codex/sessions/` and read the latest `turn_context.payload.model`; inspect only model metadata for this active session.

Use the exact ID when available (for example `claude-opus-5-5`). If the host exposes only a model label, use it and say so in the first reference's `annotation_notes`; do not invent a more specific ID. Do not ask the user for it.

## 1. Resolve and preserve the source

Read `ChenWeb/CLAUDE.md` and these sources before extracting:

- `KnowledgeStore/Capsules/coding-capsules/doc-processor/extract-references-spec.md` (orientation) and the contract it points at: `ChenWeb/openspec/changes/extract-references-processor/specs/document-references/spec.md` and `design.md` (D2–D5)
- devdoc `KnowledgeStore/doc-repo/devdocs/202610/2026101002-devdoc-extract-references-processor.md` §3 (the reference model)
- `ChenWeb/prompts/prompt-extract-references-v1.md` for what the extractor is asked to find, as the output contract, not a substitute for independent annotation
- `ChenWeb/server/api/doc-processing/reference_model.go`, `reference_identifiers.go` and `reference_normativity.go` for the vocabularies, identifier normalization and normativity derivation
- `ChenWeb/KnowledgeStore/Capsules/coding-capsules/input-management/+CAPSULE.md` and `KnowledgeStore/doc-repo/specs/202604/2026042101-spec-line-file.md` (canonical line format)

Read [references/benchmark-contract.md](references/benchmark-contract.md) for field names, payload shape, database setup and commands.

Export exactly the requested `kb.inputs` row through the configured project PostgreSQL connection, using an integer parameter. Include `id`, `result_filename`, `parser_name`, `staging_filename`, `title`, `doc_no` and `doc_metadata`. Do not display credentials. An unavailable connection or missing ID blocks saving; continue local preparation where possible and report the exact gap.

Resolve the working `.txt` file as `docprocessing.ResolveInputFilePath` (`ChenWeb/server/api/doc-processing/event.go`) and `pathutil.ResolveDataHomePath` do: normally next to `result_filename`, named `<staging filename stem>_<parser_name>.txt`; relative result paths use `DATA_HOME_DIR`. `.origin` is the preserved original, not the working file. Never select the first matching file or silently regenerate/reparse a source.

Run `scripts/benchmark_io.py prepare` to validate the canonical seven TAB fields, record the source SHA-256, create the run ID (`yyyymmdd_hhmmss`, local time of `prepare`) and expose source lines. Keep its output in a local file and read it in bounded portions. Never confuse record line IDs with physical file lines, pages or table row IDs. Fail on malformed records. Investigate numbering gaps and parser damage.

## 2–4. Inventory, label and audit — follow the rules file

Sections 2–4 (candidate inventory, labelling and the audits) are in the selected `rules/<version>.md`. Apply them in full, then continue with section 5. Every candidate records the `rule_id` that decided it (`A*` accept, `X*` exclude, `D1` duplicate).

## 5. Validate, save and read back

Run `scripts/benchmark_io.py validate` before writing. It checks source identity/hash, complete coverage, candidate links and rule IDs, the governed vocabularies (target type/subtype with `others` + label, mechanism, asserted relationships, scope, content), form and internal-reference constraints, identifier normalization (standard prefix + space + number, edition apart, lower-case DOIs), `cited_raw` and evidence as exact source text, the named quantity on `criterion` rows only (with English companions for non-English documents), and duplicate occurrences. It **recomputes** `normativity`, `list_entry_ref_id` and `list_mismatch` from the rows (as `reference_normativity.go` does) and refuses any disagreement. It cannot verify that every reference was found, or that a `criterion`/`method`/`requirements` decision is right; those remain the reviewer's responsibility.

Inspect the `testbed.ref_mentions` columns. If the tables are absent, apply the committed Goose project migration `ChenWeb/project_migrations/20261011000003_create_testbed_ref_mentions.sql` through the existing migration workflow (db-migration skill); do not issue ad hoc DDL. If incompatible, report the differences and prepare a reviewed migration rather than adapting silently.

Run `save` after validation and audit succeed, unless the user requested draft-only/no-save. The helper revalidates, checks the `kb.inputs` identity and inserts the run audit, gold references and dropped candidates in one transaction. A run is identified by (`skill_name`, `skill_version`, `model_name`, `run_id`); `save` refuses a run key already in `testbed.reference_benchmark_runs`, so runs are never overwritten or extended. Never edit `run_id` to force a save. It never writes `kb.ref_mentions`, the resource catalog, `kb.metrics`, processing status or queues. A failed transaction leaves no partial benchmark; inspect by full run key before retrying an ambiguous connection failure.

Read the saved rows back by `input_record_id` and the full run key: compare count and substantive fields of `testbed.ref_mentions` to the validated JSON, `testbed.ref_mentions_dropped.candidate_data` to exactly the excluded and duplicate candidates, and the run row (`candidates`, `coverage`, reviews, `document_identifier`). Report success only after all read-back checks match. Zero gold references still saves the run audit and any dropped candidates; report zero explicitly.

Report document ID, source path/hash, run ID, saved count (by `ref_form`, internal/external and `target_content`), coverage, uncertainty/limitations and the audit location.

## Scoring `extract_references`

Select one explicit benchmark run; never concatenate snapshots. Compare it with the record's `kb.ref_mentions` rows. Match a predicted mention to a gold reference by overlapping `source_line_spans` and the same target (identity key, or for internal and indirect references the same locator and `cited_raw`), one-to-one. Report detection precision and recall separately for listed entries, external in-text references and internal references, then label accuracy on the matched pairs: `target_type`, `target_subtype`, `mechanism`, `relationships` (set overlap), `target_scope`, `target_content`, `in_requirement`, `normativity`, `list_mismatch`, identifiers, and the named quantity on `criterion` pairs. The `criterion`/`criteria_set` rows matter most: they are what the metric resolver takes. Compare the run's `document_identifier` with the identifier the processor attached (`kb_input` identifier of the record). Report the skill version and run ID with every score.
