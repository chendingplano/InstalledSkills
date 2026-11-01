---
name: score-extract-provisions
description: Use when asked to score, grade, evaluate or measure the quality of the provisions that extract_provisions produced for a document (kb.inputs.id), against that document's gold provisions / benchmark / ground truth in testbed.provisions.
disable-model-invocation: true
---

# Score extract_provisions

Score how well `extract_provisions` did on one document, on a scale of **1 to 100**:

- 100 means every gold provision was found, with every checked field right and nothing extra.
- 1 means total failure.

The gold provisions come from the `extract-provisions-benchmark` skill: `testbed.provisions`, one
run in `testbed.provision_benchmark_runs`. The predictions are the document's active rows in
`kb.provisions`.

The work is split on purpose:

- **You** decide which predicted row is the same provision as which gold row.
- **The script** does every check that can be computed, and the arithmetic, so the number can be
  reproduced from the saved files.

Never compute or adjust the score by hand. ChenWeb's System Admin › Benchmark › Provisions ›
Benchmark page runs the same steps, with an LLM doing the matching
(`ChenWeb/prompts/prompt-score-extract-provisions-v1.md`).

Input: a positive integer document ID. Run from the workspace root. Below, `S` stands for
`.agents/skills/score-extract-provisions/scripts/score_io.py`.

## 1. Export (stop if there is no gold)

```bash
python3 $S export --record-id <id>
```

The script finds the database settings (ChenWeb `.env`) and `DATA_HOME_DIR` (ChenWeb `mise env`)
itself. Never print credentials.

By default it picks the gold run with the newest released rules version, and the latest run on a
tie. Use `--gold-version`, `--gold-model` or `--gold-run-id` only when the user names a run. A
pre-release run must be named.

| Exit | Meaning | What you do |
|---|---|---|
| 0 | `input.json` written; stdout gives its path | continue |
| 3 | `NO_GOLD`: no gold run for this document | **Report the error message to the user and stop.** Do not build gold provisions or estimate a score yourself |
| 4 | `NO_PREDICTIONS`: `kb.provisions` has no active rows for the document | report and stop |
| 1 | other error (unknown ID, database) | report and stop |

Read every `warnings` entry. State these in your final answer:

- the source file changed since the gold run (pairs then need not share a line, and `lines` is
  not checked);
- the rows come from several extractions;
- the gold run has zero provisions.

## 2. Match: write `matches.json` next to `input.json`

Read all of `input.json`:

- `gold`;
- `predictions`;
- `gold_ledger`: the gold run's excluded and duplicate candidates, with `rule_id` and reason;
- `suggestions`: the predicted rows that share a source line with each gold row, most similar
  text first. They are a hint, not a decision.

**What a pair is.** A pair means both rows state **the same normative statement**: the same
obligation, prohibition, instruction, recommendation or permission, on the same subject (gold
rules §2.2).

- The rows must share a source line. The script refuses a pair that does not, unless the line
  file changed.
- Different wording, a clause number in front, or a missing final 。 do not prevent a pair.
- A different `provision_type`, subject or location does not prevent a pair either, because the
  field checks grade those.

**Pairs are one-to-one.**

- **Merges.** If the extractor merged several gold provisions into one row (two sentences of one
  clause, a sentence that gold split by type or subject), pair the row with the closest gold
  provision. On a tie, pick the one stated first. List the others as missed, with a note
  ("merged into 416_prv_12").
- **Splits.** If the extractor split one gold provision into several rows, pair the closest row.
  List the others as false positives with cause `split` and the gold row's ID in `gold`.

Every gold row appears exactly once, in `pairs` or `missed`. Every predicted row appears exactly
once, in `pairs` or `false_positives`. The script refuses anything else.

```json
{
  "pairs": [{"gold": "416_gprv_12", "pred": "416_prv_9", "note": ""}],
  "missed": [{"gold": "416_gprv_13", "note": "merged into 416_prv_9 (paired with 416_gprv_12)"}],
  "false_positives": [
    {"pred": "416_prv_1", "cause": "gold_excluded", "gold_candidate_id": "c3", "rule_id": "X2",
     "note": "scope statement"},
    {"pred": "416_prv_20", "cause": "split", "gold": "416_gprv_30", "note": "second half of the sentence"},
    {"pred": "416_prv_21", "cause": "duplicate", "of": "416_prv_20", "note": ""},
    {"pred": "416_prv_22", "cause": "not_in_gold", "note": "..."}
  ],
  "overrides": [{"gold": "416_gprv_5", "field": "subject", "correct": true, "reason": "..."}]
}
```

False-positive `cause`:

| Cause | When | Required fields |
|---|---|---|
| `gold_excluded` | The gold ledger has a candidate for the same statement, either excluded (`X*`: scope, definition, principle, pointer …) or a duplicate (`D1`) | its `candidate_id` and `rule_id` |
| `split` | The row is part of a gold provision that is already paired with another row | the gold row in `gold` |
| `duplicate` | The row repeats another predicted row | the other row in `of` |
| `not_in_gold` | The gold run never considered it. Say in the note whether you think gold missed a real provision | — |
| `invalid` | The row misreads the source | — |

**Overrides** correct the `subject` check, and only it. Use one only when both rows name the same
party or object in different words (`垃圾分类收集容器` / `分类收集容器`), and give a reason. A
different party or object is a real error. Every other check is a vocabulary value, a boolean or
a computed measure, and is never overridden.

## 3. Score

```bash
python3 $S score --dir <directory of input.json> --scorer-model <your exact model ID>
```

The script writes `score.json` and `report.md` in that directory: next to the source line file,
under `extract-provisions-scores/`, outside Git. If it refuses `matches.json`, fix the file and
run it again.

**How the score is computed.**

- Each pair earns credit: the weighted share of the checks it passes. Default weights are in
  `weights.json` (relative, normalized to 1):
  - `provision_type` 30;
  - `text` 20 (similarity of the provision texts, ignoring whitespace, clause numbers and the final
    stop);
  - `lines` 20 (line-set overlap);
  - `subject` 15;
  - `location_type` 10;
  - `is_explicit` 5.
- `text` and `lines` earn partial credit.
- `lines` is left out, and the rest renormalized, when line numbers are not comparable.
- Missed gold rows and false positives earn nothing.
- Soft precision = credit / predicted rows. Soft recall = credit / gold rows.
- **Score = round(100 × soft F1)**, clamped to 1–100.

The report also gives:

- the same measures per `provision_type` (a type counts a pair under its gold row for recall and
  under its predicted row for precision);
- recall per gold `provision_kind`. Production stores no kind, so kinds have no precision.

## 4. Report to the user

Give the score first, then:

- the gold run key (version / model / run ID);
- the extraction (model, prompt, saved time);
- soft precision and soft recall (the score is built from these), and matched-row precision and
  recall;
- the per-type scores and the recall per kind;
- the main error patterns: which fields fail most, the false-positive causes, what was missed
  (and whether it was merged);
- any warnings;
- the `report.md` path.

When comparing scores, compare only scores made against the same gold run.

## Common mistakes

- **Pairing by line alone.** One numbered clause often holds several sentences, and so several
  gold provisions. Pair by statement.
- **Using a leftover prediction to raise recall.** A false positive must not be paired with a
  leftover gold row.
- **Calling a merge a split, or the reverse.** One prediction covering two gold provisions is a
  merge: one pair plus missed rows. Two predictions covering one gold provision is a split: one
  pair plus `split` false positives.
- **Overriding a wrong subject because it looks close.** `运营单位` vs `运行管理人员` are
  different parties.
