---
name: score-extract-references
description: Use when asked to score, grade, evaluate or measure the quality of the references that extract_references produced for a document (kb.inputs.id), against that document's gold references / benchmark / ground truth in testbed.ref_mentions.
disable-model-invocation: true
---

# Score extract_references

Score how well `extract_references` did on one document, on a scale of **1 to 100** (100 = every
gold reference found with every checked field right and nothing extra; 1 = total failure). The
gold references come from the `extract-references-benchmark` skill (`testbed.ref_mentions`, one run
in `testbed.reference_benchmark_runs`). The predictions are the document's current rows in
`kb.ref_mentions`.

The work is split on purpose. **You** decide which predicted row is the same reference as which
gold row. **The script** does every check that can be computed, and the arithmetic, so the number
can be reproduced from the saved files. Never compute or adjust the score by hand.

Input: a positive integer document ID. Run from the workspace root. Below, `S` stands for
`.agents/skills/score-extract-references/scripts/score_io.py`.

## 1. Export (stop if there is no gold)

```bash
python3 $S export --record-id <id>
```

The script finds the database settings (ChenWeb `.env`) and `DATA_HOME_DIR` (ChenWeb `mise env`)
itself. Never print credentials. By default it picks the gold run with the newest released rules
version, and the latest run on a tie. Use `--gold-version`, `--gold-model` or `--gold-run-id` only
when the user names a run (a pre-release run must be named).

| Exit | Meaning | What you do |
|---|---|---|
| 0 | `input.json` written; stdout gives its path | continue |
| 3 | `NO_GOLD`: no gold run for this document | **Report the error message to the user and stop.** Do not build gold references or estimate a score yourself |
| 4 | `NO_PREDICTIONS`: `kb.ref_mentions` has no rows for the document | report and stop |
| 1 | other error (unknown ID, database) | report and stop |

Read every `warnings` entry. A source file that changed since the gold run (pairs then need not
share a line), rows from several extraction events, or a gold run with zero references must be
stated in your final answer.

## 2. Match: write `matches.json` next to `input.json`

Read all of `input.json`: `gold`, `predictions`, `gold_ledger` (the gold run's excluded and
duplicate candidates, with `rule_id` and reason), and `suggestions` (predicted rows that share a
source line with each gold row, the same `cited_raw` first, then by field agreement; a hint, not a
decision). Each row has a `group`: `listed`, `external_in_text` or `internal`.

A **pair** means both rows are the same reference: **one occurrence of one target taking one kind
of content** (gold rules §2.1). They must share a source line (the script refuses a pair that does
not, unless the line file changed) and point at the same target: the same identity key for an
external reference, or the same locator and `cited_raw` for an internal or indirect one. `cited_raw`
written differently is fine (`[2] 国务院办公厅…:国办发〔2017〕26号` vs `国办发〔2017〕26号`). A
different `target_content` does not prevent a pair, because the field checks grade it. But a row
for another target, or another occurrence of the same target, is a different reference. Pairs are
one-to-one:

- If the extractor merged two gold references into one row (two contents of one target in one
  sentence, two criteria of one standard), pair it with the closer one (on a tie, the one stated
  first) and list the other as missed, with a note.
- When one line cites the same target for several contents, pair by content, then by order.

Every gold row appears exactly once, in `pairs` or `missed`. Every predicted row appears exactly
once, in `pairs` or `false_positives`. The script refuses anything else.

```json
{
  "pairs": [{"gold": "416_gref_36", "pred": "416_ref_34", "note": ""}],
  "missed": [{"gold": "416_gref_37", "note": "merged into 416_ref_34 (paired with 416_gref_36)"}],
  "false_positives": [
    {"pred": "416_ref_50", "cause": "gold_excluded", "gold_candidate_id": "c4", "rule_id": "X2",
     "note": "the document's own number on the cover"},
    {"pred": "416_ref_51", "cause": "duplicate", "of": "416_ref_50", "note": ""},
    {"pred": "416_ref_52", "cause": "not_in_gold", "note": "..."}
  ],
  "overrides": [{"gold": "416_gref_44", "field": "identifiers", "correct": true,
                 "reason": "..."}]
}
```

False-positive `cause`: `gold_excluded` when the gold ledger has a candidate for the same
occurrence, whether excluded (`X*`: own identity, open class, actor, caption …) or a duplicate
(`D1`); give its `candidate_id` and `rule_id`; `duplicate` when it repeats another predicted row;
`not_in_gold` when the gold run never considered it (say in the note whether you think gold missed
a real reference); `invalid` for a row that misreads the source.

The checks already normalize notation: full-width/half-width forms, case, whitespace and dash
variants inside identifiers (`GB/T1.1—2009` = `GB/T 1.1-2009`), and the list link is compared
through your pairs (a predicted in-text row is right when it links the predicted entry you paired
with the gold row's entry). These need no override.

**Overrides** correct a field check that the normalized comparison still got wrong. They are
allowed only for `identifiers` and `quantity`, and each needs a reason. Use one only when both sides
name the same thing in different words: the same quantity paraphrased (`粪大肠菌群数` /
`粪大肠菌数`), or one identifier written two equivalent ways the normalizer does not know. A missing
identifier, a missing edition or a wrong kind is a real error. Every other field is a governed
vocabulary value and is never overridden.

## 3. Score

```bash
python3 $S score --dir <directory of input.json> --scorer-model <your exact model ID>
```

The script writes `score.json` and `report.md` in that directory (next to the source line file,
under `extract-references-scores/`, outside Git). Fix any refusal in `matches.json` and run it again.

How the score is computed: each pair earns credit, the weighted share of the checks it passes:
`target_content` 0.25; `in_requirement`, `identifiers`, `relationships` 0.10 each; `mechanism`,
`target_type`, `target_subtype`, `target_scope`, `ref_form`, `normativity`, list link,
`list_mismatch` and the named quantity 0.05 each. `relationships` earns its set overlap (Jaccard);
the named quantity applies only when both rows are `criterion` rows (otherwise it is left out and
the rest renormalized). Missed gold rows and false positives earn nothing. Soft precision = credit /
predicted rows. Soft recall = credit / gold rows. **Score = round(100 × soft F1)**, clamped to
1–100. The report also gives the same measures for listed entries, external in-text references,
internal references, and `criterion`/`criteria_set` rows (what the metric resolver takes): a group
counts a pair under its gold row for recall and its predicted row for precision.

The report also compares the gold run's `document_identifier` with the identifier
`extract_references` attached the document to (`kb_input` identifier, design D5): `match`,
`match_without_edition`, `edition_differs`, `mismatch` or `missing`. This is a diagnostic, not part
of the score.

## 4. Report to the user

Give the score first, then: the gold run key (version / model / run ID) and the extraction (event
ID, date; the rows do not record the prompt or model); soft precision and soft recall (the ones the
score is built from), the matched-row precision and recall, and the per-group scores, especially
`criterion`/`criteria_set`; the main error patterns (which fields fail most, the false-positive
causes, what was missed); the document identifier result; any warnings; and the `report.md` path.
When comparing scores, compare only scores made against the same gold run.

## Common mistakes

- Pairing by line alone. One line often cites several targets, or one target for several
  contents; pair by target, then content.
- Pairing a listed entry with an in-text citation of the same standard. They are different
  occurrences.
- Pairing a false positive with a leftover gold row to raise recall.
- Overriding a real mistake because it looks small (a missing edition, a dropped URL). The weights
  already keep small mistakes small.
