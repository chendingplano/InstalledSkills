---
name: extract-provisions-benchmark
description: Build an independently reviewed provision benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, find and label every normative provision (requirements, prohibitions, instructions, recommendations, permissions), audit completeness and correctness, and save evidence-backed snapshots in testbed.provisions for evaluating extract_provisions. Use for gold provisions, ground truth, or provision benchmark extraction; production provisions remain in kb.provisions.
disable-model-invocation: true
---

# Extract Provisions Benchmark

Produce a complete, source-grounded provision benchmark for one document. The required input is a
positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record.

**What an invocation authorizes.** "Use $extract-provisions-benchmark, version <version> for
document <document-id>" requests the complete workflow: extract independently, audit, validate,
save a new snapshot, and verify it by read-back. The invocation authorizes the save. Do not stop
at a draft or ask for separate confirmation; only an explicit draft-only/no-save instruction
changes this. The benchmark tables are `testbed.provision_benchmark_runs`, `testbed.provisions`
and `testbed.provisions_dropped`.

**What this file covers.** This file is the shared procedure: resolving the source, preparing,
validating, saving and reading back. **What counts as a provision, and how to label and audit it,
is defined by a versioned rules file** in `rules/`. Every run uses exactly one rules version.

**Independence.** For every version, author the benchmark independently of the
`extract_provisions` predictions:

- Do not call the processor or the provisions extract API.
- Do not copy `kb.provisions` or read its rows or the `.provisions` artifact until the benchmark
  is frozen.

## Versions

- `rules/versions.json` lists the released versions, the rules file for each, and its SHA-256.
- **Choose the version first.**
  - If the user names a version, use it.
  - Otherwise use the newest released version (highest version number, compared numerically).
    Pre-releases such as `2.0.0-rc.1` are used only when named.
  - Tell the user which version you are using.
  - Comparing versions means separate runs of the same document, one per version, each with its
    own `run_id`.
- **Read `rules/<rules file>` for that version completely before annotating.** Follow it in place
  of any rule you remember from another version, and never mix rules from different versions in
  one run.
- Pass `--skill-version <version>` and `--model-name <invoking model identity>` to
  `scripts/benchmark_io.py prepare`. The helper:
  - refuses an unknown version, or a rules file whose SHA-256 differs from `versions.json`;
  - stamps `skill_name`, `skill_version` and `model_name` on every saved row, and `rules_sha256`
    in the run row.
- **Released rules files are frozen.** Never edit one. To change the rules:
  1. Copy the newest file to `rules/<new version>.md` and edit the copy.
  2. Add it to `versions.json` with its SHA-256.
  3. Add a `CHANGELOG.md` entry.
  4. Update the "Available versions" table and the Change Log in `USER_MANUAL.md`.

  Bump major when the rules change which statements are provisions or how a label is decided,
  minor for compatible additions, patch for wording that does not change outcomes. To trial a
  draft, release it as a pre-release such as `2.0.0-rc.1`; it is frozen the same way.
- **Tooling is shared.** `SKILL.md`, `references/benchmark-contract.md` and `scripts/` are shared by
  all versions and always the latest.
  - A tooling change must keep every released rules version runnable. If a rules version needs
    different validation, gate it by version in `benchmark_io.py`.
  - Tooling changes are recorded in `CHANGELOG.md` and do not create a rules version.
- **Vocabularies.** `provision_type` and `location_type` mirror the extractor's output schema
  (`ChenWeb/prompts/prompt-extract-provisions-v3.md`). When the extractor's vocabulary changes,
  release a new rules version that says so and update `benchmark_io.py`, gated by version if older
  runs would no longer validate.

## Invoking model identity

`model_name` identifies the model invoking and executing this skill. It is not the project's
configured `EXTRACT_PROVISIONS_MODEL_NAME`, a model mentioned in an example, or a model the user
must select.

- Obtain it from the current runtime context or the active session's metadata.
- For Codex, when the context does not expose the exact ID, match `CODEX_THREAD_ID` (or
  `CODEX_SESSION_ID`) to its session file under `~/.codex/sessions/` and read the latest
  `turn_context.payload.model`. Inspect only model metadata for this active session.
- Use the exact ID when available (for example `claude-opus-5-5`). If the host exposes only a
  model label, use it and say so in the first provision's `annotation_notes`. Do not invent a
  more specific ID, and do not ask the user for it.

## 1. Resolve and preserve the source

Read these sources before extracting:

- `ChenWeb/CLAUDE.md`
- `KnowledgeStore/Capsules/coding-capsules/doc-processor/extract-provisions-spec.md` (what
  the processor produces)
- `ChenWeb/prompts/prompt-extract-provisions-v3.md`, for what the extractor is asked to find.
  Treat it as the output contract, not a substitute for independent annotation.
- `KnowledgeStore/doc-repo/specs/202604/2026042101-spec-line-file.md` (canonical line format)

Read [references/benchmark-contract.md](references/benchmark-contract.md) for field names, payload
shape, database setup and commands.

**Export the record.**
- Export exactly the requested `kb.inputs` row through the configured project PostgreSQL
  connection, using an integer parameter.
- Include `id`, `result_filename`, `parser_name`, `staging_filename`, `title`, `doc_no` and
  `doc_metadata`.
- Do not display credentials.
- An unavailable connection or a missing ID blocks saving. Continue local preparation where
  possible and report the exact gap.

**Resolve the working `.txt` file** the way `docprocessing.ResolveInputFilePath` and
`pathutil.ResolveDataHomePath` do:
- normally next to `result_filename`, named `<staging filename stem>_<parser_name>.txt`;
- relative result paths use `DATA_HOME_DIR`;
- `.origin` is the preserved original, not the working file.

Never select the first matching file, and never silently regenerate or reparse a source.

**Prepare.** Run `scripts/benchmark_io.py prepare`. It validates the canonical seven TAB fields,
records the source SHA-256, creates the run ID (`yyyymmdd_hhmmss`, local time of `prepare`) and
exposes the source lines.
- Keep its output in a local file and read it in bounded portions.
- Never confuse record line IDs with physical file lines, pages or table row IDs.
- Fail on malformed records. Investigate numbering gaps and parser damage.

## 2–4. Inventory, label and audit — follow the rules file

Sections 2–4 (candidate inventory, labelling and the audits) are in the selected
`rules/<version>.md`. Apply them in full, then continue with section 5. Every candidate records
the `rule_id` that decided it: `A*` accept, `X*` exclude, `D1` duplicate.

## 5. Validate, save and read back

**Validate.** Run `scripts/benchmark_io.py validate` before writing. It checks:
- source identity and hash;
- complete coverage;
- candidate links, rule IDs, and candidate text as source text;
- the governed vocabularies, the `provision_kind` → `provision_type` mapping, and table lines
  ↔ `table_row`/`table_cell`;
- `provision` as source text (each ` … ` part in the joined cited lines), evidence as exact
  substrings, and `source_table_rows` on table lines;
- English companions on non-English documents;
- duplicate provisions (same lines and text).

Validation cannot verify that every provision was found, or that a kind, subject or split
decision is right. Those remain the reviewer's responsibility.

**Check the tables.** Inspect the `testbed.provisions` columns. If the tables are absent, apply the
committed Goose project migration
`ChenWeb/project_migrations/20261106000101_create_testbed_provisions.sql` through the existing
migration workflow (db-migration skill). Do not issue ad hoc DDL. If they are incompatible,
report the differences and prepare a reviewed migration rather than adapting silently.

**Save.** Run `save` after validation and the audit succeed, unless the user asked for
draft-only/no-save. The helper:
- revalidates and checks the `kb.inputs` identity;
- inserts the run audit, the gold provisions and the dropped candidates in one transaction;
- never writes `kb.provisions`, `kb.metrics`, processing status or queues.

A failed transaction leaves no partial benchmark. Inspect by full run key before retrying an
ambiguous connection failure.

**Run keys are used once.** A run is identified by (`skill_name`, `skill_version`, `model_name`,
`run_id`). `save` refuses a run key already in `testbed.provision_benchmark_runs`, so runs are
never overwritten or extended. Never edit `run_id` to force a save.

**Read back.** Read the saved rows back by `input_record_id` and the full run key, and compare:
- the count and substantive fields of `testbed.provisions` with the validated JSON;
- `testbed.provisions_dropped.candidate_data` with exactly the excluded and duplicate
  candidates;
- the run row (`candidates`, `coverage`, reviews).

Report success only after every read-back check matches. Zero gold provisions still saves the
run audit and any dropped candidates; report zero explicitly.

**Report** the document ID, the source path and hash, the run ID, the saved count by
`provision_type` and `provision_kind`, coverage, uncertainty and limitations, and the audit
location.

## Scoring `extract_provisions`

Use the `score-extract-provisions` skill. It exports the gold run and the predictions, you write
the pairs, and its script computes a reproducible 1–100 score. The ChenWeb page System Admin ›
Benchmark › Provisions › Benchmark runs the same scorer with LLM matching. Always report the
skill version and run ID with a score.
