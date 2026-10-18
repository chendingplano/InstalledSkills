# Metric Extraction Analysis: Record 364, missed gold rows of score run 13

**Date:** 2026-10-18
**Document:** `kb.inputs.id = 364`, WS/T 810—2022 《基层医疗卫生机构急重患者判断及转诊技术标准》 (an
emergency-referral standard with clinical treatment appendices)
**Source:** 327 records, SHA-256 `03b385c6…4c038ddb` (unchanged across every run below).

| Item | Value |
|---|---|
| Gold run analysed | 7.1.0 / claude-sonnet-5-5 / `20261017_164614` (138 rows) |
| Extraction analysed | run 232: candidates v27, enrich v26, deepseek-flash |
| Score run | `metric-score-runs/13` (scored by deepseek-flash): 81, 15 missed, 10 false positives |
| Outcome | rules 8.0.0; corrected gold `20261018_074618`; extractor candidates v28 / enrich v27 |

## 1. Were the 15 missed gold rows true metrics?

| Gold | Source | Verdict |
|---|---|---|
| 112, 113 | 以下3项中符合任何1项; 同时至少有下述1种表现 | **Not metrics.** "Any one of" is "or"; the 1 counts the document's own listed criteria (the 7.1.0 run excluded the "3项" beside it as X4) |
| 101 | 直至降到180/110mmHg以下 (systolic) | True, and **found**: `364_mtc_63` merged 180/110 and the scorer left it as a false positive while pairing the same shape (`364_mtc_64`) elsewhere |
| 19, 114 | 同时有两项以上分层为高危; 迅速出现下述2种以上表现 | True: a threshold on how many findings are present (k ≥ 2) |
| 42, 43, 130, 135 | 近2周有外伤史; 年龄≥75岁; 抽搐持续超过5min; 抽搐超过15min未缓解 | True: triggers (§2.6 examples) |
| 78 | 必要时10min～20min重复一次 | True: repeat count |
| 92, 93, 95, 102 | 血压≥180/110mmHg (D.2.2 heading, after treatment, target) | True |
| 126 | 沙丁胺醇或特布他林 2.5mg～5mg (terbutaline) | True: one row per agent |

## 2. Where the extractor lost them (run 232 logs)

| Pattern | Rows | Stage and cause |
|---|---|---|
| Trigger folded into the action's condition | 130, 135 | enrich dropped `17_5`/`17_10` as `not_a_metric:condition_of` ("Numbers That Qualify Another Value" applied to an observed state) |
| Case threshold read as a category definition | 43 | enrich dropped `6_5` as `term_definition` (the 6.7.0 age-band rule) |
| Time window read as qualitative | 42 | enrich dropped `6_6` as `qualitative_criterion` |
| Heading that states a criterion skipped | 92, 93 | candidates: "do not extract headings"; D.2.1 (same line type) was extracted |
| Paired value kept as one row | 95, 102 | enrich: split at D.2.1, merged at D.2.2 (`180/110`) |
| One value for alternative agents merged | 126 | candidates: "alternatives together stay ONE" overrode "one per object" |
| Count fused with a verb | 78 | candidates: 重复**一**次 missed, 重复应用**1**次 caught |
| k-of-n with k ≥ 2 | 19, 114 | candidates: no rule |

The enrich drops were invisible to the score report: they lived only in `kb.doc_proc_logs`.

## 3. Benchmark findings and fixes

- **Rules 8.0.0** (major): trigger vs scope test (a number about the case that decides whether, when
  or how far to act is A1 and also the condition of the actions; a method chosen by group is X5);
  k-of-n (k = 1 is X4, k ≥ 2 is an A1 cut-off); one row per alternative agent; paired notation one row
  per component; matching audit checks.
- **Gold inconsistencies found:** 125/126 split one "A或B" sentence while 133/134 merged an equivalent
  one; 86 (生理盐水或林格氏液), 56 (洛贝林、尼可刹米) and 100 (卡托普利、美托洛尔) were also merged.
- **Corrected gold:** `20261018_074618` (8.0.0, 141 rows): 112/113 excluded as X4; 56, 86, 100, 133,
  134 split per agent (new 139–143). Run `20261018_074301` is an earlier copy that missed 56 and 100;
  do not score against it.
- **Scoring tooling:** `score_io.py` refuses a `not_in_gold`/`invalid` false positive whose note
  names a missed gold row (the 364_mtc_63 mistake), and lists enrich-pass drops in the report.

## 4. Extractor fixes and result

Candidates v28 / enrich v27 (ChenWeb `yovu`) add the patterns above plus: no invented repeat count for
"可重复", the class-word case ("应用呼吸兴奋剂，洛贝林…或尼可刹米…"), and the 7.1.0 case-parameter bound
(70+年龄×2), which the production prompts never had. Code: enrich drops saved as
`drop_stage = enrich`; `180/110` with a physical unit is sent back for splitting; a row whose range
type promises a number but has no `metric_value` is retried (run 233 lost a whole batch this way).

| Run | Gold | Score | Missed | False positives |
|---|---|---:|---:|---:|
| 232 (v27/v26) | 7.1.0 `20261017_164614` | 81 | 15 | 10 |
| 235 (v28/v27) | 7.1.0 `20261017_164614` | 85 | 2 (112, 113) | 16 |
| 235 (v28/v27) | 8.0.0 `20261018_074618` | 86 | 2 | 13 |

The 232 score was made by deepseek-flash, the 235 scores by claude-opus-5-5. All validation of the
fixes is on record 364 only.

## 5. Still open

- 林格氏液 and 美托洛尔 1 h are still merged into class rows (gold 141, 143 missed).
- The MEWS table (line 118): the gold stores the band as the value (§2.6), production stores the
  points as the value with the band as condition (enrich "Sparse Scoring Tables"). 19 pairs fail
  value/unit/kind on this alone. A ruling is needed.
- Conditions: 22% after overrides. The extractor adds `病情分层：极高危` to stratification rows and
  leaves out the 适应证 qualifier on many treatment rows.
- False positives: formulation concentrations (50 %, 10 %, 5 %, 1:1000), "最大不超过成人剂量" as 1 倍,
  and "等量氢化可的松" given methylprednisolone's 1~2 mg/kg.
