---
name: extract-metrics-benchmark
description: Build an independently reviewed metric benchmark for a document identified by kb.inputs.id. Read its complete canonical line file, audit completeness and correctness, and save evidence-backed metric snapshots in testbed.metrics for evaluating extract_metrics. Use for gold metrics, ground truth, or benchmark extraction; ordinary production extraction remains in kb.metrics.
metadata:
  version: "1.2.0"
---

# Extract Metrics Benchmark

Produce a complete, source-grounded benchmark for one document. The required input is a positive integer `record_id` from `kb.inputs.id`; resolve the line filename from that record. Creating this skill alone does not require a document ID or extracting a document.

Author the benchmark independently of `extract_metrics` predictions. Do not call the processor or preview extraction API, copy `kb.metrics`, or read its predictions until the benchmark is frozen. Production records are predictions, not ground truth. Do not inherit the older `document-metric-extractor` skill's precision-over-recall policy or legacy file/storage schema.

## Skill version

This skill is versioned. The version is declared once, as `metadata.version` in this file's frontmatter, and its history is in [CHANGELOG.md](CHANGELOG.md). `scripts/benchmark_io.py` stamps the skill `name` and version into the prepared payload and into `testbed.metrics.skill_name` / `skill_version` on every saved row, so each benchmark run records which rules produced it. Pass `prepare --model-name <exact model ID>` with the ID of the model running this skill (for example `claude-opus-5-5` or `gpt-6.1-sol`); it is stored in `testbed.metrics.model_name`. Never guess or abbreviate it. Validation refuses a payload prepared under a different version. Any change to annotation rules, payload shape or storage needs a version bump and a changelog entry: patch for wording that does not change outcomes, minor for compatible additions, major for rules that change which assertions are metrics. When comparing benchmark runs or scoring `extract_metrics`, report the skill version along with the run ID.

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

## 2. Make a full-document candidate inventory

Read every source line, including appendices, tables, notes, equations and headings. For long documents use bounded windows with surrounding context, tracking which original line IDs have been read; return to complete evidence before deciding boundary-spanning assertions. Search is a second-pass discovery aid, never a replacement for reading the document.

Build two ledgers in the payload:

- `coverage`: non-overlapping source ranges covering every line, with section/table-specific review notes, including regions with no metrics.
- `candidates`: each plausible assertion with a stable local ID, exact spans, disposition (`accepted`, `excluded`, `duplicate`, or temporarily `uncertain`), rationale and final metric IDs. A single line/table can have many candidates; line coverage alone is insufficient.

Include quantities, limits, targets, counts, frequencies, ratios, rates, tolerances, scores, formulas, named measured properties and explicit testable requirements. A stated value need not be a requirement; preserve observations, targets and design capabilities as their actual claim class.

Apply the broader contract to requirements without numbers: retain a concrete measured-property requirement as `qualitative`, and an explicit statement that a limit is unspecified/determined elsewhere as `limit_absent`. Exclude vague aspirations or generic procedural prose that does not define an assessed property or criterion.

**Retain delegated requirements.** A clause imposing a requirement on a specific object while delegating criteria to a cited standard is a `qualitative` / `reference` row with `is_explicit_metric = false`, empty value/unit/formula, the original clause in `threshold_or_target`, `external_reference` and `cited_doc:<identifier>` tags, and identifiers in keywords. Do not import values from the cited document. A normative-reference list alone is excluded. A numeric requirement citing only a test method remains an ordinary numeric metric.

Exclude incidental years, edition numbers, document codes, clause numbering, page counts, coordinates, font sizes, standalone units and reference-list entries. Classify each by meaning, not by whether it contains digits. Keep borderline candidates visible until source context resolves them.

## 3. Resolve each assertion and its context

One row represents one property of one subject under one condition, with its stated value or requirement. Split distinct properties in a sentence. Split table cells/rows when conditions, objects or measured properties differ. Preserve a single interval/tolerance as one assertion. Never combine a value from one row with a subject/unit from another.

The subject may be a source-supported object, facility, system, party or activity. If only an activity is named (for example, "每月至少检查2次"), use that activity as the subject and note that its object is unspecified. Do not attach it to a nearby object without evidence. If neither a subject nor activity can be established from the source/context, retain the candidate as uncertain rather than fabricating a subject.

For each table reconstruct multi-level headers, units, row labels, rowspans/colspans, captions, footnotes, merged cells and continued tables before annotating values. A whole HTML table may occupy one source line. Keep its line ID unchanged and record logical data row IDs in `source_table_rows`. Follow `ParseTableGrid` in `ChenWeb/server/api/doc-processing/table_grid.go`: header IDs `h0`, `h1`, ...; data IDs `r1`, `r2`, ... . Cite data rows in stored metrics. Use the existing parser when header/span semantics are complex; do not guess row IDs or hashes. Preserve source HTML substrings as evidence, optionally adding human-readable row text to notes. Enumerate every applicable row/property pair in the candidate ledger.

Use minimal supporting spans plus any header, note or definition needed to interpret the assertion; discontinuous spans are allowed. Normalize spans as strings `"N"` or `"N:M"`, sorted with overlaps/adjacency merged. Never write `"N-M"` or `"116#r1"` into `source_line_spans`. Record exact, nonempty source substrings with original line IDs in `evidence`; an excerpt can support several independent metrics.

Preserve subject, value, comparator, unit, scale, frequency, scope, exceptions and negation. Keep decimal precision, inequalities, strict/inclusive bounds, ± tolerances, scientific notation, percentages and ratios in source-faithful text. Do not invent zero, units or thresholds for absent data. For ratios written `N:1`, the contract's unit is `ratio`. Ranges additionally carry numeric `value_min`/`value_max`; other range types leave those fields null. Tolerances/approximations not losslessly expressible by the enum retain exact wording and interpretation notes; never rewrite them into different acceptance criteria.

Match source language in core text fields. For English, leave `_en` fields empty/null. Translate non-English companion fields faithfully after checking the assertion. Categories are nonempty semantic keys, not paths: reuse existing keys through read-only lookup where appropriate; otherwise annotate an explained key locally without creating production categories or invoking indexing workflows.

Deduplicate repeated window detections using subject, property, value, unit, comparator, condition, claim class, table rows and provenance. Merge evidence for true repeats and retain `duplicate` ledger entries. Do not deduplicate solely by name, number or line; different conditions stay separate. Preserve independently stated occurrences at different source locations for mention-level benchmarking and document that granularity.

## 4. Audit completeness and correctness separately

Perform both reviews against the source after drafting:

1. **Completeness:** re-read each section/table without relying on drafted metrics. Enumerate measurements/property requirements again; reconcile every candidate with final rows or an explained exclusion. Recheck conjunctions, cross-line clauses, continued tables, footnotes, formulas, header units, numeric words and delegated requirements. Account for every data-row/property pair and all original lines.
2. **Correctness:** verify every saved field against cited lines. Check subject-to-value association, operators/negation, units/scales, row/column assignment, ranges/tolerances, frequency, applicability, translations and duplicates. Exact excerpt validity and high confidence do not prove semantic correctness.

Describe concrete checks/findings in `completeness_review` and `correctness_review`. Resolve all uncertain candidates; never relabel uncertainty as exclusion merely to pass validation. If parser damage, missing context or contract ambiguity remains, retain draft JSON and identify it in `limitations`. Do not publish an incomplete/unresolved set as a complete benchmark. Distinguish completeness within the line file from original-PDF coverage; image-only or omitted content requires a stated limitation and appropriate review.

## 5. Validate, save and read back

Run `scripts/benchmark_io.py validate` before writing. It checks source identity/hash, complete coverage, candidate links, enums, excerpts and core types. It cannot verify semantic correctness, table row interpretation, translations or whether all candidates were discovered; those remain the reviewer's responsibility.

Inspect `testbed.metrics` and required columns. If absent, apply the committed Goose project migration `ChenWeb/project_migrations/20261006000001_create_testbed_metrics.sql` using the existing migration workflow; do not issue ad hoc DDL or copy production indexes/triggers. If incompatible, report differences and prepare a reviewed migration rather than adapting silently.

Run `save` when extracting/saving the requested document is authorized. The helper revalidates, checks `kb.inputs` identity and inserts all rows in one transaction. Runs are immutable snapshots with unique UUIDs. It never deletes benchmarks or writes `kb.metrics`, processing status, queues, embeddings, ontology, categories or production indexes. A failed transaction leaves no partial benchmark; inspect by run ID before retrying an ambiguous connection failure. An already-saved run ID is not a new run.

Read saved rows back by **both** `input_record_id` and `benchmark_run_id`, compare count/substantive fields to validated JSON, and verify evidence/provenance. Report success only after read-back matches. Keep payload/audit JSON so zero metrics also has a reviewable record; zero metrics creates no rows and must not be claimed as a stored snapshot.

Report document ID, source path/hash, run ID, saved count, coverage, uncertainty/limitations and audit location. When comparing predictions, select an explicit benchmark run; never concatenate snapshots or use benchmarks as predictions. Match complete assertions and provenance, not just names/numbers.
