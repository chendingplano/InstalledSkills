# Metric Extraction Analysis — Record 416, rules 2.0.0, gpt-6.1-sol (row-by-row audit)

**Date:** 2026-10-06
**Document:** `kb.inputs.id = 416`, DB33/T 2030—2018 《农村生活垃圾分类处理规范》
**Source:** `/Users/cding/Apps/SemOS/Artifacts/0/416/std_1503937_mineru.txt` (169 records, IDs 1–169,
no gaps), SHA-256 `5acb3df6…4a590fcd`, matching the hash stored on every row.

| Run key | Value |
|---|---|
| `skill_name` | extract-metrics-benchmark |
| `skill_version` | 2.0.0 (`rules_sha256` `2bcdf015…729ee42d7`, matches `rules/versions.json`) |
| `model_name` | gpt-6.1-sol |
| `benchmark_run_id` | `20261006_121911` (the only 2.0.0 run of this document by this model) |
| Saved rows | 69 |
| Candidate ledger | 194: 69 accepted, 123 excluded, 2 duplicate (D1); every candidate has a `rule_id` |
| `limitations` | none |

This report checks the 69 saved rows and the 125 non-accepted decisions directly against the source
and the 2.0.0 rules. The earlier report
[20261006-1258](20261006-1258-metric-extraction-analysis-report.md) compares this run with the 1.0.0
run and the devdoc verdict. Where the two reports agree, this one says so briefly. The new findings
are in §4.2–§4.5 and §5.

## 1. Summary

- **The run is sound and usable as the record-416 benchmark.** 65 of the 69 rows are correct as
  saved. Two rows should be excluded (§3.1, §3.2) and two have the wrong `value_class` (§3.3).
  Estimated precision is 67/69 ≈ 97%.
- **No missing metrics found.** I re-read all 169 lines and found no gate-passing assertion without a
  row. The claude-opus-5-5 run on the same document (1.2.0, run `20261006_085331`, 82 rows) supports
  this: every row it has that this run lacks is one that 2.0.0 explicitly excludes (§6).
- **The mechanical checks all pass.** All 104 evidence quotes are exact substrings of their cited
  lines. Every non-empty `condition` appears verbatim in the source. No `metric_value` contains a
  comparator. `strict_bound` appears exactly on the two strict (小于/大于) rows. All 15 Annex B
  settings carry `test_condition`. The table row IDs for Tables 1–3 are correct, and Table 2 is
  correctly limited to machine compost while Table 3 covers both compost modes.
- **The main new finding is a representation problem in 14 rows** (§4.1). The Table 1 rows store the
  "适用范围" column, which describes where a treatment mode is suitable, as the `condition` of each
  technical requirement. This will cause condition mismatches when scoring `extract_metrics`.

## 2. Composition of the saved set

| Rule | Rows | Content |
|---|---:|---|
| A1 numeric | 14 | container count, 2 × daily collection, GI ≥ 60%, Table 2 (3), Table 3 (5), 2 GI interpretive bounds |
| A2 inspectable feature or state | 15 | lids, signs, enclosure, vehicle anti-odour/spill/leak, sealing, insulation, intact containers, no odour/sewage/litter |
| A3 delegation to an identified document | 17 | CJJ 27, GB 16889 (×2), CJJ 184, CJJ 52 (×2), NY/T 90, NY/T 2371, GB 50869, CJJ 90, GB 18485, GB/T 31962, GB 14554, NY 1109, NY884 (×2) |
| A4 value left open | 7 | food-waste collection time and frequency, 主体工艺, 比能耗, 发酵周期, chamber volume, 种名 |
| A5 formula | 1 | GI formula B.1 |
| A6 test setting | 15 | B.1.1 (10), B.1.2 (5) |

| Shape | Count |
|---|---:|
| `qualitative` | 33 |
| numeric (`exact` / `lower_bound` / `upper_bound` / `range`) | 29 |
| `limit_absent` | 7 |
| rows with a `condition` | 38 |

The rules' warning sign, a set dominated by `qualitative` rows from prose 应 clauses, does not apply
here. Of the 33 qualitative rows, 17 are A3 delegations, and every A2 row names a concrete feature or
observable state.

## 3. Rows that should change

### 3.1 `416_gold_39` 微生物菌种种名, accepted as A4, should be X10

Line 127 reads "菌种应安全、有效，有明确来源和种名". The run split the phrase into 来源 (X10, excluded)
and 种名 (A4, accepted). Both halves are the same requirement: the strain must be documented. A
species name is an identity, not a property that can be measured or inspected, so it fails gate (b).
X10's own example is "strain source stated". The opus run and the devdoc both kept the two halves
together. (The earlier report reached the same conclusion.)

### 3.2 `416_gold_19` 机械成肥设备主体工艺, accepted as A4, should be X13

Line 121, Table 1 r1, reads "设备应明确主体工艺、比能耗、发酵周期等运行技术参数". 比能耗 and 发酵周期 are
quantities, and A4 is correct for them. 主体工艺 is the name of a process, and X13 excludes "the bare
name of a process". The run's consistency note defends the row because "a named equipment parameter
must be declared". That reasoning would accept anything the source happens to call a 参数. The opus
run excluded it independently.

### 3.3 `416_gold_68` / `416_gold_69`: GI interpretive bounds stored as `value_class = reference`

Line 163 says GI < 100% means the compost is phytotoxic and GI > 100% means it promotes growth. These
are cut-offs for interpreting a result, not limits the product must meet. In 2.0.0, `reference` means
a delegation to an identified document (A3, with `cited_doc:` tags). These rows have no cited
document, so the class is wrong. `validate` does not catch this because it checks `reference` rows
only when they carry the A3 tags. 2.0.0 offers no correct class for them: `definition` requires a
formula, and `requirement` would misstate them. **This is a gap in the rules, not a model error.** Until
it is settled, treat both rows as disputed when scoring.

## 4. Representation issues that affect scoring

None of these makes a row wrong. Each changes what a matching `extract_metrics` prediction must look
like.

### 4.1 Table 1 "适用范围" stored as `condition` (14 rows)

`416_gold_19` to `416_gold_32` each copy the row's 适用范围 cell (for example
"人口密度高，有机肥需求量较大的农村地区。") into `condition`. That column says where a treatment mode is
*suitable*. It does not limit when the technical requirement applies: if a village uses machine
composting, the equipment must state its specific energy consumption regardless of population density.
X5 itself gives "适用于人口密度高的地区" as its example of applicability that is *not* a metric. The
requirement's real applicability, "uses this treatment mode", is already in `metric_subject`.

`416_gold_27` mixes the two kinds: the genuine scope "容积在50立方米以下" (correct as a condition, per
X5's own example) is followed by the suitability text.

*Effect:* a correct extractor that leaves `condition` empty, or writes "采用机器成肥模式", will
mismatch on 14 rows, about 20% of the set. *Suggested fix:* in the next rules version, state that a
mode-suitability column is not a condition. Until then, the scorer should ignore `condition` on
Table 1 rows, or the rows should be re-saved under a later version.

### 4.2 Measurement basis stored as `condition` (7 rows)

`416_gold_44`, `416_gold_45` and `416_gold_47` to `416_gold_51` put "以烘干基计" or "鲜样" in
`condition`. These state how the property is measured (dry basis, fresh sample), not when the limit
applies. The rules do not cover this case. The scorer should treat basis wording as matching
whether it appears in `condition`, `metric_name` or `metric_desc`.

### 4.3 Daily collection modelled as `exact` 1 日 (`416_gold_8`, `416_gold_12`)

"每日定时收运" is stored as an exact interval of 1 day, and the row's note says it is "not exactly one
collection event". The opus run stored the same clause as `qualitative`. Other reasonable encodings
include a frequency of 1 次/日 (exact or lower bound). A1 says frequencies are numeric but gives no
canonical form. The scorer needs to treat these encodings as equivalent, or the rules need to name one.

### 4.4 Process-level delegations and gate (a) (3 rows)

Gate (a) accepts an activity as the object only when the requirement is a number about it.
`416_gold_11` (收运过程应符合 CJJ 184), `416_gold_22` (堆肥发酵过程符合 CJJ 52) and `416_gold_23` (太阳能辅助堆肥方式
应符合 CJJ 52) delegate a criterion for a *process* to a standard. Read strictly, they fail gate (a).
The run accepts them under A3 and, for 22 and 23, changes the subject to an object that the source does
not name ("堆肥发酵物料", "处理设施"). The opus run also accepts them. Rule A3 says "a specific object"
but does not say whether a process qualifies. The rules should settle this. Until then, keep these
rows but match them on cited document and line rather than on subject.

### 4.5 Smaller points

- `cited_doc:NY884` (rows 42 and 43) follows the source's spelling. The normative-reference list
  writes "NY 884". Normalize spaces in identifiers before matching.
- `metric_categories`: `waste_management` covers 43 of the 69 rows, so it does little to tell rows
  apart.
- `location_type = bullet` appears on 44 numbered prose clauses (7.1.1 and similar). `sentence` fits
  them better. This is harmless if the scorer ignores `location_type`.
- The `threshold_or_target` text adds 应 where the source has none: on 9.3.4 and on several Annex B
  settings. Exact source text stays in `evidence`, so this is harmless.

## 5. Decisions checked and confirmed

The following decisions are correct under 2.0.0. They are recorded here because they were close
calls or were disputed in earlier runs.

| Decision | Lines | Why it holds |
|---|---|---|
| Food-waste collection time and frequency are A4 `limit_absent` | 101 | "约定" is A4's "set by agreement" case |
| 阳光房单室体积 is A4 | 121 r2 | Matches A4's own example: volume set by daily throughput |
| 焚烧尾气达标排放 is X9 | 121 r5 | GB 18485 in the same clause covers pollution control, so it is the A3 row |
| 收运过程实行密闭化管理 is X2 | 105 | Names a management regime. Enclosure is captured by rows 13 and 15 |
| 50 m³ is not a numeric capacity row | 121 r3 | X5 example; kept as the scope condition on NY/T 90 (row 27) |
| 彩色标志颜色可按照 GB/T 19095 is X8 | 150 | Permissive 可 |
| 500 ml bottle and one filter paper are X12 | 158, 159 | Apparatus, not result-affecting settings |
| GI operands are not separate rows; the formula is one A5 row | 159–161 | X13 |
| Table 2 applies only to machine compost; Table 3, GI and NY884 apply to both modes | 128 | Matches the text of 9.3.6 exactly |
| Two internal table pointers on line 128 are D1 | 128 | The pointers resolve to the retained Table 2 and 3 rows |
| Annex A sign table is X4 | 150–153 | Container sign requirement already captured by row 5 |

All 15 A6 rows were checked value by value against B.1.1 and B.1.2: sample count, dry mass ≥ 20.0 g,
1：10 W/V, ≥ 100 次/分钟, ≥ 40 mm, 1 h, 0.5 h, 3 blanks, 0～4 ℃, ≤ 48 h, 10 seeds, 5 ml, 25 ℃, 48 h
and 3 replicates. Comparators and units are correct. The qualitative settings (室温, 黑暗) are carried
as `condition`, as X12 requires.

## 6. Cross-check against the claude-opus-5-5 run

Run `20261006_085331` was produced under rules 1.2.0, which are identical to the 1.0.0 rules, so the
two runs differ by design. It still serves as an independent annotation for finding missed metrics.

- **Opus rows absent from this run (19).** Every one falls under an explicit 2.0.0 exclusion:
  日产日清 (X3); 沥干水分 and 投放清洁 (X1/X8); the 整洁 and 良好 states (X11); facility provision (臭气处理设施,
  污水设施, 处理系统, 消纳途径, 飞灰炉渣处置: X7); 达标排放 and 选址安全防护 (X9); 菌种有效性 (X13);
  菌种来源和种名 (X10); and 500 ml bottle and 滤纸数量 (X12).
- **Rows in this run absent from opus (2).** 主体工艺 (§3.2, opus is right) and the separate GI formula
  row (opus folded the formula into the GI ≥ 60% row; under 2.0.0 the separate A5 row is correct).
- **Both runs agree on** all numeric values, all Table 1–3 row assignments, all 15 delegated
  standards, and the A6 settings apart from the two apparatus rows.

## 7. Impact on scoring and recommended actions

1. Use run `20261006_121911` as the record-416 benchmark, and cite the run ID with every score.
2. Report scores with and without the four disputed rows: `416_gold_19`, `416_gold_39`,
   `416_gold_68` and `416_gold_69`. The clean core set is 65 rows.
3. Score the `condition` field without the Table 1 suitability text (§4.1) and without measurement
   basis wording (§4.2). Normalize daily-frequency encodings (§4.3) and identifier spacing (§4.5).
4. Report recall with and without the 15 `test_condition` rows, because production extraction may
   not target test-method settings.
5. Next rules version (2.0.1 or 2.1.0; never edit 2.0.0):
   - Species name and strain source are both X10.
   - A4 applies only to quantities, not process names.
   - Interpretive cut-offs need either an X rule or a stated class (§3.3).
   - A mode-suitability column is not a `condition` (§4.1).
   - Say where measurement basis goes (§4.2).
   - Give a canonical encoding for "每日" schedules (§4.3).
   - Say whether a process can be the object of an A3 delegation (§4.4).
   - Also extend `validate` so a `reference` row without `cited_doc:` fails.

## Method

The 69 rows and their `ext_info` (including the candidate ledger) were read from `testbed.metrics` by
the full run key. All 194 candidates were reviewed against source lines 1–169 and the text of
`rules/2.0.0.md`. Table 1 (line 121) was read cell by cell. Evidence quotes and conditions were checked
against the source by script. Field values were checked by hand. Opus run `20261006_085331` was read
only after this run's audit was drafted, to look for missed metrics. Production `kb.metrics`
predictions were not read. The verdicts in §3 and §4 are one reviewer's judgement and should be
confirmed before they become rules.
