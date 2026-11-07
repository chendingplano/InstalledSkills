---
name: extract-products-benchmark
description: Build an independently reviewed product benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, find every product it names (articles, equipment, product classes, materials, waste categories and streams), label every relation the document has with each one plus its enrichment fields, audit completeness and correctness, and save evidence-backed snapshots in testbed.products for evaluating extract_products. Use for gold products, ground truth, or product benchmark extraction; production products remain in kb.products.
disable-model-invocation: true
---

# Extract Products Benchmark

Produce a complete, source-grounded product benchmark for one document. The required input is a
positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record.

**What an invocation authorizes.** "Use $extract-products-benchmark, version <version> for
document <document-id>" requests the complete workflow: extract independently, audit, validate,
save a new snapshot, and verify it by read-back. The invocation authorizes the save. Do not stop
at a draft or ask for separate confirmation; only an explicit draft-only/no-save instruction
changes this. The benchmark tables are `testbed.product_benchmark_runs`, `testbed.products` and
`testbed.products_dropped`.

**What this file covers.** This file is the shared procedure: resolving the source, preparing,
validating, saving and reading back. **What counts as a product, which relations it has, and how
to label and audit them, is defined by a versioned rules file** in `rules/`. Every run uses
exactly one rules version.

**The unit.** One gold row is one (product, `relation_type`) pair, the unit `kb.products` stores.
All rows of one product share a `product_key`, so the scorer can also measure product detection
on its own.

**Independence.** For every version, author the benchmark independently of the `extract_products`
predictions:

- Do not call the processor or the products extract API.
- Do not copy `kb.products` or read its rows, `kb.product_names` or the `.products` artifact until
  the benchmark is frozen.

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

  Bump major when the rules change which things are products, which relations they have or how a
  label is decided; minor for compatible additions; patch for wording that does not change
  outcomes. To trial a draft, release it as a pre-release such as `2.0.0-rc.1`; it is frozen the
  same way.
- **Tooling is shared.** `SKILL.md`, `references/benchmark-contract.md` and `scripts/` are shared by
  all versions and always the latest.
  - A tooling change must keep every released rules version runnable. If a rules version needs
    different validation, gate it by version in `benchmark_io.py`.
  - Tooling changes are recorded in `CHANGELOG.md` and do not create a rules version.
- **Vocabularies.** `product_type`, `relation_type`, `obligation_level` and the related-product
  `relationship` mirror the long names `kb.products` stores (`ChenWeb/prompts/
  prompt-enrich-product-mention-v4.md`, `prompt-extract-products-merged-v2.md`). When the
  extractor's vocabulary changes, release a new rules version that says so and update
  `benchmark_io.py`, gated by version if older runs would no longer validate.
- **Table rows.** `benchmark_io.py` assigns table row IDs (`h0…`, `r1…`) with a port of ChenWeb's
  `docprocessing.ParseTableGrid` (`TableGridVersion` 3). If ChenWeb bumps `TableGridVersion`,
  port the change and re-check parity before the next run.

## Invoking model identity

`model_name` identifies the model invoking and executing this skill. It is not the project's
configured `EXTRACT_PRODUCT_MENTIONS_MODEL_NAME` or `ENRICH_PRODUCT_RELATIONS_MODEL_NAME`, a model
mentioned in an example, or a model the user must select.

- Obtain it from the current runtime context or the active session's metadata.
- For Codex, when the context does not expose the exact ID, match `CODEX_THREAD_ID` (or
  `CODEX_SESSION_ID`) to its session file under `~/.codex/sessions/` and read the latest
  `turn_context.payload.model`. Inspect only model metadata for this active session.
- Use the exact ID when available (for example `claude-opus-5-5`). If the host exposes only a
  model label, use it and say so in the first row's `annotation_notes`. Do not invent a more
  specific ID, and do not ask the user for it.

## 1. Resolve and preserve the source

Read these sources before extracting:

- `ChenWeb/CLAUDE.md`
- `KnowledgeStore/Capsules/coding-capsules/doc-processor/extract-products-spec.md` (what the
  processor produces, and its producthood gate)
- `ChenWeb/prompts/prompt-extract-products-merged-v2.md`, for what the extractor is asked to find.
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
exposes the source lines. Each table line also lists its rows by ID (`"r3": "3 | 垃圾桶"`), which
is how the extractor sees them and how evidence cites them (`"121#r3"`).
- Keep its output in a local file and read it in bounded portions.
- Never confuse record line IDs with physical file lines, pages or table row IDs.
- Fail on malformed records. Investigate numbering gaps and parser damage.

## 2–4. Inventory, label and audit — follow the rules file

Sections 2–4 (candidate inventory, producthood, relations and row fields, and the audits) are in
the selected `rules/<version>.md`. Apply them in full, then continue with section 5. Every
candidate records the producthood rule that decided it (`A*` accept, `X*` exclude, `D1`
duplicate), and every row the relation rule (`R*`).

A large document can have well over a hundred rows. Draft them in a compact form of your own (a
script or a table in your scratch directory) and generate the payload from it, so names, keys and
spans stay consistent across a product's rows.

## 5. Validate, save and read back

**Validate.** Run `scripts/benchmark_io.py validate` before writing. It checks:
- source identity and hash;
- complete coverage;
- candidate links, rule IDs, and candidate text as source text;
- the governed vocabularies, and that each row's `rule_id` is the R rule of its relation type;
- product-key consistency (shared name, canonical name and type) and one row per relation type
  per product;
- spans: `N`, `N-M`, `N#rK`, `N#hK`; table lines cited by existing rows only;
- `product_name` (or an expansion's `name_source`), `evidence_quote` and each ` … ` part of
  `requirement_text` as source text;
- descriptive rows without requirement text or actor, and `scope`/`exempted_product` rows
  descriptive;
- `related_products` exactly for the four inter-product relations, and the parameter shape;
- English companions on non-English documents.

Validation cannot verify that every product or relation was found, or that a type, relation or
obligation decision is right. Those remain the reviewer's responsibility.

**Check the tables.** Inspect the `testbed.products` columns. If the tables are absent, apply the
committed Goose project migration
`ChenWeb/project_migrations/20261108000101_create_testbed_products.sql` through the existing
migration workflow (db-migration skill). Do not issue ad hoc DDL. If they are incompatible, report
the differences and prepare a reviewed migration rather than adapting silently.

**Save.** Run `save` after validation and the audit succeed, unless the user asked for
draft-only/no-save. The helper:
- revalidates and checks the `kb.inputs` identity;
- inserts the run audit, the gold rows and the dropped candidates in one transaction;
- never writes `kb.products`, `kb.product_names`, processing status or queues.

A failed transaction leaves no partial benchmark. Inspect by full run key before retrying an
ambiguous connection failure.

**Run keys are used once.** A run is identified by (`skill_name`, `skill_version`, `model_name`,
`run_id`). `save` refuses a run key already in `testbed.product_benchmark_runs`, so runs are
never overwritten or extended. Never edit `run_id` to force a save.

**Read back.** Read the saved rows back by `input_record_id` and the full run key, and compare:
- the count and substantive fields of `testbed.products` with the validated JSON;
- `testbed.products_dropped.candidate_data` with exactly the excluded and duplicate candidates;
- the run row (`candidates`, `coverage`, reviews).

Report success only after every read-back check matches. Zero gold rows still saves the run audit
and any dropped candidates; report zero explicitly.

**Report** the document ID, the source path and hash, the run ID, the saved counts (rows,
products, by `relation_type` and `product_type`), coverage, uncertainty and limitations, and the
audit location.

## Scoring `extract_products`

Use the `score-extract-products` skill. It exports the gold run and the predictions, you write
the pairs, and its script computes a reproducible 1–100 score plus product-detection precision
and recall. The ChenWeb page System Admin › Benchmark › Products › Benchmark runs the same scorer
with LLM matching. Always report the skill version and run ID with a score.
