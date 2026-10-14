---
name: score-extract-metrics
description: Use when asked to score, grade, evaluate or measure the quality of the metrics that extract_metrics produced for a document (kb.inputs.id), against that document's gold metrics / benchmark / ground truth in testbed.metrics.
disable-model-invocation: true
---

# Score extract_metrics

Score how well `extract_metrics` did on one document, on a scale of **1 to 100** (100 = every
gold metric found with every checked field right and nothing extra; 1 = total failure). The
gold metrics come from the `extract-metrics-benchmark` skill (`testbed.metrics`). The
predictions are the document's current rows in `kb.metrics`.

Gold rows store their run ID in `testbed.metrics.run_id`. The export helper maps
it to the existing `benchmark_run_id` field in scoring artifacts and joins run
audits on `m.run_id = r.benchmark_run_id` plus skill name, version and model.

The work is split on purpose. **You** decide which predicted row states the same assertion as
which gold row. **The script** does every check that can be computed, and the arithmetic, so the
number can be reproduced from the saved files. Never compute or adjust the score by hand.

Input: a positive integer document ID. Run from the workspace root. Below, `S` stands for
`.agents/skills/score-extract-metrics/scripts/score_io.py`.

## 1. Export (stop if there is no gold)

```bash
python3 $S export --record-id <id>
```

The script finds the database settings (ChenWeb `.env`) and `DATA_HOME_DIR` (ChenWeb `mise env`)
itself. Never print credentials. By default it picks the gold run with the newest rules version
of at least 3.0.0, and the latest run on a tie. Use `--gold-version`, `--gold-model` or
`--gold-run-id` only when the user names a run.

| Exit | Meaning | What you do |
|---|---|---|
| 0 | `input.json` written; stdout gives its path | continue |
| 3 | `NO_GOLD`: no gold run for this document, or only runs under rules older than 3.0.0 (2.1.0 can stand in) | **Report the error message to the user and stop.** Do not build gold metrics, score against an incompatible run, or estimate a score yourself |
| 4 | `NO_PREDICTIONS`: `kb.metrics` has no rows for the document | report and stop |
| 1 | other error (unknown ID, database) | report and stop |

Read every `warnings` entry. A stand-in 2.1.0 run, or a source file that changed since the gold
run (the lines check is then disabled), must be stated in your final answer.

## 2. Match: write `matches.json` next to `input.json`

Read all of `input.json`: `gold`, `predictions`, `gold_ledger` (the gold run's excluded and
duplicate candidates, with `rule_id` and reason), and `suggestions` (predicted rows that share a
source line with each gold row, ranked by how many field checks they pass; a hint, not a decision).

A **pair** means both rows state the same assertion: the same measured property of the same
object, from the same clause. Paraphrased names and broader or narrower subject wording are fine
("肥料" vs "机器成肥产出的肥料"). Different values do not prevent a pair, because the value check
grades them. But a row from another table row or clause is a different assertion, and so is a row
for another condition of the same property (幼儿 vs 成年人, a simulation device vs a simulant object):
pair each predicted row with the gold row of its condition, and let the condition check grade a
wrong or missing condition only when no gold row of the right condition is left. Pairs are
one-to-one. If the extractor merged two gold assertions into one row, pair it with the closer one
(on a tie, the one stated first in the source) and list the other as missed, with a note.

Every gold row appears exactly once, in `pairs` or `missed`. Every predicted row appears exactly
once, in `pairs` or `false_positives`. The script refuses anything else.

```json
{
  "pairs": [{"gold": "416_gold_7", "pred": "416_mtc_7", "note": ""}],
  "missed": [{"gold": "416_gold_32", "note": "merged into 416_mtc_5 (paired with 416_gold_31)"}],
  "false_positives": [
    {"pred": "416_mtc_3", "cause": "gold_excluded", "gold_candidate_id": "c58", "rule_id": "X2",
     "note": "agreement duty, nothing to measure"},
    {"pred": "416_mtc_9", "cause": "duplicate", "of": "416_mtc_8", "note": ""},
    {"pred": "416_mtc_40", "cause": "not_in_gold", "note": "..."}
  ],
  "overrides": [{"gold": "416_gold_1", "field": "unit", "correct": true,
                 "reason": "个 vs 个/户: per-household scope is in the subject"}]
}
```

False-positive `cause`: `gold_excluded` when the gold ledger has a candidate for the same clause,
whether excluded (`X*`) or a duplicate of a gold row (`D1`); give its `candidate_id` and `rule_id`; `duplicate` when it repeats another predicted row;
`not_in_gold` when the gold run never considered it (say in the note whether you think gold
missed a real metric); `invalid` for a row that misreads the source.

The checks already normalize notation: full-width/half-width forms (`0～4` = `0~4`, `1：10` =
`1:10`), whitespace, case, comparators inside `metric_value` (`≤20` = `20`) and numeric form
(`20.0` = `20`). These need no override.

**Overrides** correct a field check that the normalized comparison still got wrong. They are allowed only for
`value`, `unit`, `lines` and `condition`, and each needs a reason. Use one only when both sides state the same
thing in different notation: a bare count unit and its per-object form (个 / 个/户), a unit
conversion, or a value given in words that is unambiguous with its unit ("每日" with 次/日 = 1).
Do not use one because a mistake looks minor. `range_type` (the comparator) and `kind` are never
overridden. A test setting stored as a requirement is a real kind error.

The `condition` check compares the qualifier values: it splits each condition on `；`/`;`, ignores
the `<kind>：` labels, whitespace and order, and passes when both sides hold the same set (both
empty also passes). Override it only when both sides state the same qualifiers in other words
(`幼儿` vs `3 周岁～6 周岁幼儿`, a label the gold leaves out). A missing qualifier, an extra one
(a repeated subject or property, or a condition the source does not state) or a different one is a
real error.

## 3. Score

```bash
python3 $S score --dir <directory of input.json> --scorer-model <your exact model ID>
```

The script writes `score.json` and `report.md` in that directory (next to the source line file,
under `extract-metrics-scores/`, outside Git). Fix any refusal in `matches.json` and run it again.

How the score is computed: each pair earns credit, the weighted share of the checks it passes
(value 0.25, comparator 0.15, statement kind 0.15, unit 0.15, overlapping source lines 0.10,
condition 0.20). This is scoring version 2 (2026-10-16), recorded in `score.json` and the report;
version 1 had no condition check (value 0.30, comparator 0.20, kind 0.20, unit 0.15, lines 0.15), so
never compare a version-1 score with a version-2 score.
Missed gold rows and false positives earn nothing. Soft precision = credit / predicted rows.
Soft recall = credit / gold rows. **Score = round(100 × soft F1)**, clamped to 1–100. The report
also gives a score without test-method settings (`test_parameter` gold rows), because production
extraction may not target them.

## 4. Report to the user

Give the score first, then: the gold run key (version / model / run ID) and the extraction
(prompt, model, date); soft precision and soft recall (the ones the score is built from), the
matched-row precision and recall, and the without-test-parameters score; the main error
patterns (which fields fail most, the false-positive causes, what was missed); any warnings; and
the `report.md` path. Mention any dropped row the report flags as on the same lines as a missed gold
row: `extract_metrics` set it aside (`kb.metrics_dropped`, not scored), so it may be a wrong drop.
When comparing scores, compare only scores made against the same gold run and the same scoring
version. A gold run under rules older than 6.4.0 may write conditions in another shape or leave
the test method out of them; say so when the condition check fails often against such a run.

## Common mistakes

- Scoring a 1.x or 2.0.0 gold run, or a document with no gold. Under those rules, requirements
  with nothing to measure count as gold metrics, while the extractor drops them on purpose.
  The script refuses this; do not work around it.
- Pairing by line number or name alone. A table line often holds several metrics, so pair by
  object, property and clause.
- Pairing a false positive with a leftover gold row to raise recall.
- Overriding a real mistake because it looks small. The weights already keep small mistakes small.
