# Metric Extraction Analysis — Record 416, rules 1.0.0 vs 2.0.0 (gpt-6.1-sol)

**Date:** 2026-10-06
**Document:** `kb.inputs.id = 416`, DB33/T 2030—2018 《农村生活垃圾分类处理规范》
**Source:** `/Users/cding/Apps/SemOS/Artifacts/0/416/std_1503937_mineru.txt` (169 records)
**Reference judgement:** devdoc `KnowledgeStore/doc-repo/devdocs/202610/2026100601-devdoc-gold-metrics-416-review.md`
(row-by-row verdict on the 1.0.0 run), with the group C/D policy decisions recorded in its "Outcome".

| | Run A | Run B |
|---|---|---|
| `skill_version` | 1.0.0 | 2.0.0 |
| `model_name` | gpt-6.1-sol | gpt-6.1-sol |
| `benchmark_run_id` | `20261006_071048` (legacy `22aa157c…`) | `20261006_121911` |
| Saved metric rows | **134** | **69** |
| Candidates (accepted / excluded / duplicate) | 295 (134 / 161 / 0) | 194 (69 / 123 / 2) |
| `rule_id` on candidates | none (not in 1.x) | all 194 |

Record 416 is the only document with a run of both versions by this model. Record 753 has only a 1.1.0
run (`20261006_081536`, 478 rows) and cannot be compared yet.

## 1. Summary

- **Rules 2.0.0 halved the gold set (134 → 69) without losing recall.** Every 2.0.0 row corresponds to
  exactly one 1.0.0 row; 65 of the 1.0.0 rows were dropped and no new assertion appeared. The devdoc
  had already found no metric missing from the 1.0.0 run, so the drop is pure precision gain.
- **Agreement with the reviewed verdict is high.** Applying the devdoc verdict plus the recorded
  policy decisions gives an expected set of 68 rows. Run B matches 67 of them, adds 2 the review would
  exclude and misses 1 the review keeps: **precision ≈ 97% (67/69), recall ≈ 99% (67/68)**. Run A
  scored ≈ 51% precision (68/134) and 100% recall against the same set.
- **All 2.0.0 representation fixes landed:** bare `metric_value` with `strict_bound`, `test_condition`
  on all 15 Annex B settings, the "declared parameter → `limit_absent`" pattern, `definition` used for
  the formula only, and applicability carried as `condition` instead of as rows.
- **Three decisions in run B look wrong or debatable** (§4), and **two representation questions are
  not settled by the rules** (§5). None blocks using run B for scoring, but §4.1 should be fixed in a
  future rules version or re-run.
- **Recommendation:** use run `20261006_121911` (2.0.0) as the benchmark for record 416. Do not use
  run `20261006_071048` for scoring.

## 2. What changed, by the devdoc's verdict groups

The devdoc sorted all 134 rows of run A into five groups. Run B's treatment of each:

| Devdoc group | Rows in A | Expected under 2.0.0 | Run B kept | Notes |
|---|---:|---|---:|---|
| A — keep as is | 45 | keep | 44 | Dropped row 33 (§4.3) |
| B — keep, fix fields | 4 | keep, fixed | 4 | 43/44 → `limit_absent`; 133/134 bare `100` + `strict_bound` |
| C — Annex B numeric test settings | 15 | keep (A6), tag `test_condition` | 15 | All tagged |
| D — policy decision | 18 | keep 21, 78, 79, 80 (A2); exclude the rest | 5 | Kept the four expected plus 87 (§4.1) |
| E — exclude | 52 | exclude | 1 | Kept 42 (§4.2) |
| **Total** | **134** | **68** | **69** | |

The 65 dropped rows fall into these patterns (with the rule run B cited):

| Pattern | Rows in A | Rule in B |
|---|---|---|
| Principles, slogans, term definitions (应收尽收, 日产日清, 定时) | 1–4 | X3 |
| Number of waste categories (四大类) | 10 | X4 |
| Planning / admin duties, 定期 inspection and publicity, 密闭化管理 | 5, 6, 33, 100, 101 | X2 |
| Aspiration without a target (提高准确率) | 102 | X6 |
| Instructions to residents / operators | 14–20, 23, 24 | X1 / X8 (尽量) |
| Facility provision or disposal route | 51, 52, 56, 57, 62, 63 | X7 |
| Unnamed "达标" / safety requirements | 53, 61 | X9 |
| Licences, certificates, provenance | 31, 40, 41, 45, 74, 86 | X10 |
| Subjective housekeeping (整洁美观, 良好) | 22, 29, 30, 81, 82, 83 | X11 |
| Applicability descriptors and the 50 m³ scope | 65–73 | X5 (now carried as `condition`) |
| Vague quality words (菌种安全、有效) | 84, 85 | X13 |
| Permissive 可 delegation (GB/T 19095 colours) | 103 | X8 |
| Apparatus and procedure steps | 107, 116–120, 126–128 | X12 |
| Formula operands split from GI formula | 129–132 | X13 |

These match the devdoc's exclusion reasons one for one, and run B's ledger records them consistently
(the consistency audit in its `correctness_review` explicitly groups X7 vs A2, X10 vs A4, X9/X13 vs A3).

## 3. Shape of the two sets

| | A (1.0.0) | B (2.0.0) |
|---|---:|---:|
| `qualitative` | 100 (75%) | 33 (48%) |
| numeric (`exact`/`upper`/`lower`/`range`) | 31 | 29 |
| `limit_absent` | 3 | 7 |
| `value_class = requirement` | 97 | 49 |
| `value_class = reference` | 18 | 19 |
| `value_class = definition` | 18 | 1 |
| `value_class = target` | 1 | 0 |
| Rows with a `condition` | 59 | 38 |
| `metric_value` containing a comparator | 2 | 0 |

The rules' warning sign ("a set dominated by `qualitative` rows from prose 应 clauses") applied to A and
no longer applies to B. Numeric rows are nearly unchanged (31 → 29): the two lost numeric rows are the
category count (row 10) and the apparatus volume / filter paper (107, 120); two qualitative daily
collection rows became numeric (§3.1).

Accepted candidates in B by rule: A1 14, A2 15, A3 17, A4 7, A5 1, A6 15.

### 3.1 Field changes on the 69 matched rows

Of the 69 rows present in both runs, 23 changed in a scoring-relevant field:

| Change | Rows (A → B) | Assessment |
|---|---|---|
| `qualitative` → `exact` `1` `日` (每日定时收运) | 25→8, 32→12 | Improvement: a daily schedule is a numeric frequency (A1). |
| `qualitative` → `limit_absent` | 42→19, 43→20, 44→21, 87→39 | Correct for 比能耗 and 发酵周期 (devdoc B). 19 and 39 are disputed (§4). |
| `<100` / `>100` → `100` + `strict_bound`; `definition` → `reference` | 133→68, 134→69 | Value fix is correct; the class change is questionable (§5.1). |
| Unit loses its "per" denominator (`个/户`→`个`, `粒/培养皿`→`粒`, `ml/培养皿`→`ml`, `个/样品`→`个`, `个/次测定`→`个`) | 13→6, 113→59, 121→62, 122→63, 125→66 | The "per X" moved into `metric_name` (每户…, 每培养皿…). Not wrong, but a unit-matching scorer will see a difference (§5.2). |
| `W/V` → `ratio` | 108→54 | Follows the contract (`N:1` → `ratio`); "W/V, 以干重计" moved to `condition`. |
| `0~4` → `0～4` | 115→60 | Now the source's full-width tilde. |
| Condition added from source | 8→2, 55→28, 121→62, 123→64, 124→65 | Applicability (X5) and qualitative test settings (X12) correctly carried as `condition`. |
| Condition removed | 94→46, 105→52, 106→53, 112→58 | A's conditions were section labels ("植物种子发芽试验浸提步骤"), not source applicability; B is right under S7. |

`threshold_or_target` differs on all 69 rows: A stored source fragments (e.g. "防臭", "比能耗",
"种名"); B stores self-contained sentences composed from the source ("收集、运输车辆应具有防臭功能。").
That satisfies the 2.0.0 stand-alone requirement. Exact source text remains in `evidence`, which
`validate` checks. Note that B adds "应" to some Annex B settings that the source states descriptively
("频率不小于100次/分钟" → "…震荡频率应不小于100次/分钟。"); harmless for scoring, but the text is
paraphrase, not quotation.

## 4. Disputed decisions in run B

### 4.1 `416_gold_39` — 微生物菌种种名 accepted as A4 `limit_absent` (likely wrong)

Line 127: "菌种应安全、有效，**有明确来源和种名**". Run B split the conjunction: 来源 → X10 (provenance,
excluded), 种名 → A4 (declared parameter, accepted). The two halves of one phrase are the same kind of
requirement — the strain must be documented — and the devdoc placed both (rows 86, 87) in the
licence/provenance group that the user decided to exclude (X10). A species name is an identity, not a
measured or inspectable property, so it also fails gate (b). Run B's own consistency note asserts
"declared operational/species parameters A4 differ from strain provenance X10", which is the
distinction the rules do not make. **Expected: exclude under X10.**

### 4.2 `416_gold_19` — 机械成肥设备主体工艺 accepted as A4 (debatable)

Line 121: "设备应明确**主体工艺**、比能耗、发酵周期等运行技术参数". Run B treats all three as declared
parameters. 比能耗 and 发酵周期 are quantities (devdoc B, correct). 主体工艺 (main process) is the name of
a process; the devdoc excluded it (E, "not quantities"), and 2.0.0 X13 excludes "the bare name of a
process". Run B argues the source itself calls it a 运行技术参数. That argument is textual, not
semantic: no inspector measures a main process. **Expected: exclude under X13**, unless the rules are
amended to accept any parameter the source names as one.

### 4.3 Line 105 收运过程应实行密闭化管理 excluded as X2 (minor)

The devdoc kept run A row 33 ("collection process enclosed"). Run B excluded it as a management
instruction (X2) and kept the second sentence on the same line (row 13, 非垃圾压缩车应密闭清运, A2).
X2 is defensible because the clause names a management regime on a process rather than a property of
an object, and enclosure is already captured by rows 13 and 15 (vehicles fully enclosed). The effect
on scoring is small; an extractor that emits it would be counted as a false positive.

## 5. Representation questions the rules do not settle

### 5.1 Interpretation thresholds (GI < 100% phytotoxic, > 100% promotes growth)

Rows 68/69 are classification boundaries for reading a result, not limits a product must meet. A
stored them as `definition` (now reserved for formulas); B stores them as `reference` with
`upper_bound`/`lower_bound` and `strict_bound`. But `reference` in 2.0.0 means "delegated to an
identified document" (A3), and these rows carry no `cited_doc`. They were accepted under A1, whose
class is "as stated", and the source states neither a requirement nor a target. **Suggested rules fix
(next version):** either an explicit exclude rule for interpretive cut-offs, or a stated class for them
(e.g. `definition` with `formula_or_definition` naming the GI scale).

### 5.2 Per-object units

Whether "每户至少 2 个" is unit `个/户` or unit `个` with "每户" in the subject/name is not specified.
Run B moved consistently to the bare unit. Fix this in the scorer (normalise "per X" between unit and
subject) or in the rules, before comparing `extract_metrics` output on unit.

## 6. Impact on scoring `extract_metrics`

Production `kb.metrics` holds 45 rows for record 416 (count only, from the devdoc; predictions were
not read for this report). Against run A's 134 rows, production recall could not exceed 34%; against
run B's 69 rows it can reach 65% even before matching. The 15 `test_condition` rows (22% of B) are a
category the production prompt may not target at all, so report recall with and without
`test_condition` rows.

## 7. Recommended actions

1. Use run `20261006_121911` (skill 2.0.0, gpt-6.1-sol) as the record-416 benchmark; cite the run ID in
   every score.
2. When scoring, treat `416_gold_19` and `416_gold_39` as known-disputed (report scores with and
   without them) until a corrected run exists.
3. In the next rules version (2.0.1 or 2.1.0; never edit 2.0.0): state that species name and strain
   source are both X10; clarify that A4 applies only to quantities, not process names; add a rule for
   interpretive thresholds (§5.1); state the per-object unit convention (§5.2).
4. Run record 753 under 2.0.0 so the comparison covers a second, larger document (1.1.0 run has 478
   rows).

## Method

Both runs were read from `testbed.metrics` by full run key (`skill_name`, `skill_version`,
`model_name`, `benchmark_run_id`). Rows were matched by hand on source line, table row, subject and
property; the match is 1:1 for 69 rows. Field differences were then computed over the matched pairs.
Disputed decisions were checked against source lines 105, 121, 127 and 163 and the 2.0.0 rules text.
The "expected set" is the devdoc verdict (groups A + B + C + the D rows kept by the user's decisions);
it is one reviewer's judgement, not an independent third annotation.
