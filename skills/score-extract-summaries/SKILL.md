---
name: score-extract-summaries
description: Use when asked to score, grade or evaluate extract_summaries output for a kb.inputs document against gold summaries in testbed.summaries. Also supports explicit comparisons with generate_summaries output; gold creation is a separate workflow.
---

# Score extract_summaries

Score one document's chunk summaries on **1–100**, following the export → judge → score → report pattern of `score-extract-metrics`. Semantic judgments are made by the agent and saved with evidence; the helper validates their structure and computes the score. This is an evidence-based rubric, not an objective measurement of all aspects of writing quality.

Input: positive `kb.inputs.id`. Default candidate: one algorithm's level-0 `kb.ex_summaries` rows. Use `--candidate generate` only when requested to score LLM-generated `kb.summaries` instead. Never mix algorithms or those tables. The gold is one reviewed run from `testbed.summary_benchmark_runs` and `testbed.summaries`, created by `generate-summaries-benchmark`.

## 1. Export

Run from the workspace root. `S` below means `.agents/skills/score-extract-summaries/scripts/score_io.py`.

```sh
python3 $S export --record-id <id> [--algorithm lexrank]
```

The helper reads ChenWeb `.env`/standard `PG*` settings privately and resolves paths through ChenWeb `mise env`. Queries are read-only. It snapshots record, gold payloads and candidate rows in one SQL statement, validates the selected benchmark and its stored rows using the gold skill's helper, and checks the current canonical source and finalized `.chunks` artifact. An explicit `--chunks <path>` selects the current chunk artifact when needed. No database schema or production data is changed.

Default gold selection: newest released semantic version, then newest run ID, then model name to break ties. Use `--gold-version`, `--gold-model`, `--gold-run-id` for a requested run; prereleases require an explicit version. Scoring-version and rules compatibility must be checked before comparing results.

- Exit 3 (`NO_GOLD`): report and stop. Do not create a benchmark or invent a score.
- Exit 4 (`NO_PREDICTIONS`): report and stop. Missing individual chunks within an existing candidate are scored as misses.
- Exit 1: report the prerequisite/error. Changed source, chunk membership, record metadata, frozen rules or saved gold rows block scoring. Do not bypass validation.
- Multiple extract algorithms require `--algorithm`; if the user did not choose, ask which to score or export each separately when comparison was requested.

Successful export prints `input.json`'s path, by default beside the canonical source under `extract-summaries-scores/<record>-<UTC timestamp>/`. Existing input files are never overwritten. `--out-dir` selects another output directory. Read the complete exported source, gold units, candidate text/configuration and warnings in bounded portions. Production rows may lack a verifiable source fingerprint or generation-run identity; disclose this limitation. Different extraction configurations in one candidate should be disclosed rather than presented as a controlled experiment.

## 2. Judge and save `judgments.json`

Read [the judgment contract](references/judgments.md). Align by original chunk sequence, never semantic similarity or summary ID alone. The helper takes the first exported row per gold sequence; duplicate/unknown sequences count as extras. Do not pool evidence from other chunks. Each chunk includes regular payload and overlap context.

For every aligned prediction:

1. Judge every **included** gold information unit: `1` fully preserves its meaning, `0.5` retains the central proposition with a material missing/changed qualifier, `0` absent, contradicted or unrecognizable. Preserve actors, objects, modality, comparators, units, conditions, exceptions and negation. Give a reason and exact prediction spans for positive credit. Intentionally omitted gold units are diagnostic only and do not reduce coverage.
2. Segment the entire source-language prediction into atomic factual claims. Mark each `supported`, `contradicted` or `unsupported` against the **full original chunk**, not only the gold wording. Provide source spans for support. Correct additional facts absent from the gold inventory are allowed. Combining a correct threshold and an invented instruction in one supported claim is invalid. A true quotation can still be misleading when it drops a governing header, exception or scope.
3. Record readable diagnostics for repetition, coherence, regular payload displaced by overlap, language metadata, keywords, translation fidelity where present, and critical errors. English translation and keywords are diagnostic rather than scored: extracts do not promise these fields. Empty/image-only gold does not license invented text; disclose inaccessible image information and gold limitations.

Paraphrases earn full credit when equivalent. Do not use lexical overlap, ROUGE, exact quotation coverage or the frozen offline span scorer under `ChenWeb/benchmark/summaries/` as a substitute for semantic judgment. An `included=false` fact may support an additional prediction claim without becoming a required coverage target. Gold defects are reported separately; never rewrite gold or award credit to hide them.

Use the actual reviewer/session identity. A self-review is acceptable if disclosed. Independent review, when used, must involve a different agent; never claim it from separate passes by the same agent. Resolve substantive disputes before computing a final score, retaining uncertainty in `limitations`. This skill's installation does not authorize evaluating a real document.

## 3. Compute

```sh
python3 $S score --dir <export directory> --scorer-model '<actual runtime model identity>'
```

Use the available session label and disclose uncertainty if no exact model ID is exposed. Do not ask the user to invent a model identity. The helper writes `score.json` and `report.md`; both retain the scoring version, weights and input/review hashes. Keep `input.json` and `judgments.json` beside them. Fix validation errors in judgments, then rerun. Never adjust the numeric score by hand.

Scoring version **1.0.0**:

| Component | Definition | Weight |
|---|---|---:|
| `chunks` | F1 of aligned row count: `2 × matches / (gold rows + predictions)` | 10 |
| `coverage` | Importance-weighted credit over all included gold units; missing chunks earn zero | 30 |
| `faithfulness` | Per-aligned-chunk share of atomic claims supported by source; sum divided by larger row count | 30 |
| `critical` | Importance-weighted coverage of included critical units | 15 |
| `provenance` | Correct source-line provenance for each aligned row; sum divided by larger row count | 10 |
| `budget` | Aligned summaries within gold's non-whitespace Unicode character budget; sum divided by larger row count | 5 |

Generated summaries must cite the full input line set including overlap. Extracts cite selected passages, so their line set must be within the chunk and cover the review's evidence lines; their saved sentence spans must also reproduce the extracted text. Empty text earns faithfulness 1 only for gold explicitly marked empty; otherwise 0. Missing and extra rows earn no faithfulness, provenance or budget credit. Components with no gold units (coverage/critical) are N/A and their weights are excluded. **Score = round-half-up(100 × weighted mean)**, clamped to 1–100; 1 denotes complete failure. A critical defect is prominently reported even when other components keep the aggregate high. Diagnostic fields never silently alter the score.

Defaults live in `weights.json`. `--weights <file.json>` overrides named weights; missing names retain defaults. Unknown names, negative/nonfinite values and all-zero applicable weights are refused. Compare scores only for the same gold run, source/chunks, budget, scoring version and weights. Candidate settings and review differences also affect comparability. Production sentence-count budgets differ from the gold character budget: report both; this skill does not rerun either pipeline to equalize them.

## 4. Report

Give the score first, candidate/table and algorithm, record ID, gold version/model/run, scorer/reviewer identities, budget, components/weights, missing/extra counts and main errors. Highlight critical losses and unsupported/contradicted claims; disclose gold self-review, parser/image limits, uncertain production provenance, missing translations and budget differences where applicable. Link `report.md`. Do not claim evaluation or database changes when only creating this skill.
