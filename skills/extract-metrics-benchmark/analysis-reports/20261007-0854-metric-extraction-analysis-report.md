# Metric Extraction Analysis — Record 416, rules 3.0.0, claude-opus-5-5

**Date:** 2026-10-07
**Document:** `kb.inputs.id = 416`, DB33/T 2030—2018 《农村生活垃圾分类处理规范》
**Source:** `/Users/cding/Apps/SemOS/Artifacts/0/416/std_1503937_mineru.txt` (169 records, IDs 1–169,
no gaps, all seven TAB fields), SHA-256 `5acb3df6…4a590fcd`. This matches the hash stored on every
row.

| Run key | Value |
|---|---|
| `skill_name` | extract-metrics-benchmark |
| `skill_version` | 3.0.0 (`rules_sha256` `08c2e313…26d55ec5`, matches `rules/versions.json` and the file on disk) |
| `model_name` | claude-opus-5-5 (exact ID, recorded as such in `annotation_notes`) |
| `benchmark_run_id` | `20261007_083500` (the only 3.0.0 run of this document) |
| Saved rows | 35 |
| Candidate ledger | 161: 35 accepted, 123 excluded, 3 duplicate (D1). Every candidate has a `rule_id` |
| X15 / X16 candidates | 16 inspection requirements, 17 delegated requirements |
| `limitations` | none |

This report checks the 35 saved rows and all 126 non-accepted decisions against the source and
`rules/3.0.0.md`. It then compares the run with the gpt-6.1-sol 2.1.0 run (`20261007_054115`), which
SKILL.md allows as a stand-in once its inspection and delegated rows are dropped. Production
`kb.metrics` predictions were not read.

## 1. Summary

- **The run can be used as the record-416 benchmark for scoring `extract_metrics` (candidates v11 /
  enrich v8), with two rows marked disputed.** 33 of the 35 saved rows pass the gate, have the right
  rule, and match the source in value, comparator, unit and table row. `416_gold_3` (餐厨垃圾收运时间)
  should be excluded, and `416_gold_4` (餐厨垃圾收运频次) fails the gate for the same reason (§3.1).
  I found no gate-passing assertion that is missing.
- **It fixes every problem raised in the two 2.0.0 reports.** 主体工艺 is X13 and 种名 is X10. The
  GI cut-offs are `definition` rows tagged `interpretation_bound`. Table 1 suitability text is no
  longer a `condition`. Measurement basis (以烘干基计, 鲜样) is in `metric_name`. "每日" is encoded
  as exact 1 次/日. No accepted row is `reference`.
- **The mechanical checks all pass.** All 49 evidence quotes are exact substrings of their cited
  lines. All 5 non-empty conditions appear in the source. No `metric_value` holds a comparator.
  `strict_bound` is on exactly the two strict rows (GI < 100%, > 100%). Coverage runs 1–169 without
  gaps or overlaps. The accepted ledger entries link exactly the 35 saved metric IDs. Every X16
  reason names its documents with a space (`NY 884`).
- **The one substantive dispute is in the X15 ledger, not in the rows** (§4.1). Two clauses in 8.1.6
  (收运过程密闭化管理, 密闭清运) are recorded as X15 inspection requirements. The first names a
  process, which X15 does not cover, and an earlier report confirmed it as X2. This affects
  only the scoring of the `exclude_pure_requirements` log: 33 X15/X16 candidates under this run,
  31 if both are moved.

## 2. Composition of the saved set

| Rule | Rows | Content |
|---|---:|---|
| A1 requirement | 12 | container count ≥ 2; 2 × daily collection; GI ≥ 60%; Table 2 (3); Table 3 (5) |
| A1 interpretation cut-off | 2 | GI < 100% phytotoxic, GI > 100% promoting |
| A4 value left open | 5 | food-waste collection time and frequency (by agreement); 比能耗, 发酵周期 (to be declared); 阳光房单室体积 (by daily throughput) |
| A5 formula | 1 | GI formula B.1 |
| A6 test setting | 15 | B.1.1 (10), B.1.2 (5) |

| `kind:` tag | Rows |
|---|---:|
| `requirement_with_criterion` | 12 |
| `test_parameter` | 15 |
| `requirement_value_open` | 5 |
| `metric_definition` | 3 |

`value_range_type`: exact 12, upper_bound 8, lower_bound 7, limit_absent 5, range 2, qualitative 1.
The only `qualitative` row is the A5 formula, as §3.1 of the rules requires. The run's consistency review
derives 35 from the document's structure (1 + 2 + 2 + 3 + 1 + 3 + 5 + 15 + 1 + 2). Without the
two agreement rows (§3.1) the expected count is 33.

## 3. Saved rows: findings

Two rows fail the gate (§3.1). The other points are wording or representation details that do not
make a row wrong. The scorer should normalize the ones marked *(scoring)*.

### 3.1 `416_gold_3` / `416_gold_4`: food-waste collection time and frequency by agreement, accepted as A4, should be X2

*Added after review on 2026-10-07. The first version of this report confirmed these rows in §5.
That was wrong.*

Line 101 reads "收运单位应与集中供餐单位约定餐厨垃圾收运的时间和频次". The run turned this into two
A4 `limit_absent` rows, with the collection activity as the subject. The clause does not set a value
for anything. It tells the collection unit to make an arrangement with the catering units. What an
inspector checks is whether that agreement exists. Nothing is measured and no number passes or
fails, so this is a requirement and not a metric. The rule is X2, an organizational duty.

The rules exclude it in two places:

- **Gate (a).** "An activity counts as the object only when the requirement is a number about it."
  These rows have an activity as the subject (集中供餐单位餐厨垃圾收运) and no number. A4 can stand in
  for the value (c). It cannot supply the object (a). So both rows fail the gate before A4 is
  considered. Compare the A4 rows that remain: 比能耗 and 发酵周期 are properties of a physical
  object (the equipment), and 单室体积 is a property of the sun house.
- **Gate (b), for the time row in particular.** 收运的时间 is a time slot for when collection
  happens. It is not a property of an object measured on a scale.

The frequency row is closer, because frequency is a quantity, and A4 lists "set by agreement" as a
case. But that phrase describes the value of an object's property. It does not turn an agreement
duty about an activity into a metric. The daily-collection rows on the same line (`416_gold_2`, `416_gold_5`) stay, because they
state a number about the activity (1 次/日). That is exactly the exception gate (a) allows.

The gpt-6.1-sol 2.1.0 run and the 2.0.0 run accepted the same two rows, and the 20261006-1311
report confirmed them. Every annotator, including this review, has read A4's "set by agreement"
wording as covering this clause. That points to a gap in the rules' wording more than an annotator error (§7).

*Effect:* the clean core set is 33 rows. Neither row belongs in the X15/X16 answer key either: an
agreement duty is not an inspection or delegated requirement. An extractor that emits these rows
should count as a false positive under the corrected reading.

### 3.2 Table 1 rows say "机器成肥设备" where the source says "机械成肥设备"

`416_gold_6` and `416_gold_7` use the mode name (机器成肥) as the subject. The cell itself says
"采用机械成肥设备 … 设备应明确…". `metric_desc` uses 机械, but `metric_subject` and
`threshold_or_target` use 机器. The threshold text "机器成肥设备应明确比能耗等运行技术参数" is
also a paraphrase rather than source wording. Evidence is exact, so this is cosmetic. Subject
matching should treat 机器成肥设备 and 机械成肥设备 as the same object. *(scoring)*

### 3.3 Units: per-object denominators

`416_gold_1` stores the container count in 个 and `416_gold_28` the seed count in 粒. The gpt 2.1.0
run used 个/户 and 粒/皿 for the same rows. Both are faithful, because the per-household and
per-dish scope is in the subject. Treat a bare count unit and its per-object form as equal.
*(scoring)*

### 3.4 `measurement_frequency` on `416_gold_25`

"每次测定，做蒸馏水空白对照3个" puts 每次测定 in `measurement_frequency`. That phrase scopes the
count (three blanks per determination); it is not how often anything is measured. The gpt run
put it in `condition`. Neither is clearly wrong under the rules. The scorer should not penalize
either placement. *(scoring)*

### 3.5 Conditions are now minimal and correct

There are five non-empty conditions: 室温下 (extraction time), 黑暗 (incubation temperature and
time), and 如浸出液不能马上分析 (storage temperature and time). Each is source text and each
limits the row it is on. This is cleaner than the gpt 2.1.0 run, which also attached 在室温下 to
shaker frequency and amplitude and repeated the storage temperature inside the storage-time
condition. Where the two runs differ on a condition, this run is the better answer.

### 3.6 Smaller points

- `416_gold_20` stores the ratio as `1：10` with a full-width colon and `value_data_type = number`.
  Normalize the colon before matching.
- `location_type` is `table_cell` for the Table 1 rows and `table_row` for Tables 2 and 3. Both are
  defensible. This is harmless if the scorer ignores `location_type`.
- The GI cut-off rows cite line 163 only; the gpt run also cites the formula line 161. Match on
  line 163.
- The model-identity note is appended to every row's `annotation_notes`, so `ext_info` differs
  row by row. That is expected and does not affect scoring.

## 4. Candidate ledger: findings

Under 3.0.0 the X15/X16 candidates are the answer key for the extractor's
`exclude_pure_requirements` log. They need the same scrutiny as accepted rows.

### 4.1 8.1.6 enclosed collection, recorded as two X15 candidates (disputed)

Line 105 reads "收运过程应实行密闭化管理。采用非垃圾压缩车直接清运方式的，应密闭清运，防止二次污染。"
The run records:

- **c47** 收运过程应实行密闭化管理 → X15. X15 covers "a concrete feature or observable state of a
  **specific object**". Only X16 extends to "object or process". The clause names a process and a
  management regime, so it is X2. The 2.0.0 report (20261006-1311, §5) confirmed X2 for this
  clause. **I recommend X2.**
- **c48** 应密闭清运 (for direct clearance by non-compactor vehicles) → X15. This is closer to the
  line: the transport is observably enclosed. But it is phrased as an instruction for how to carry
  out the operation, which is X1. The gpt 2.1.0 run took that view and recorded the whole line
  as one X1 candidate, pointing out that the vehicle's enclosed state is stated concretely at
  8.2.3. **Disputed; I lean X1.**

The run's consistency review groups lines 50, 105 and 109 as "enclosed vehicles/processes, all X15".
For lines 50 and 109 this is right, because both name vehicles. Line 105 does not.

*Effect:* if the extractor logs either 8.1.6 clause as `inspection_requirement`, this run counts it
as a hit and the alternative reading counts it as a false positive. Report log precision and recall
both ways. The core X15 set is 14 (it matches the gpt run's 14 inspection rows one for one).

### 4.2 X16 set agrees completely with the independent run

The 17 X16 candidates match the gpt 2.1.0 run's 17 `delegated_requirement` rows document by
document: CJJ 27 (5.3), CJJ 27 + GB 16889 (5.4, one candidate), CJJ 184, CJJ 52 (×2), NY/T 90,
NY/T 2371, GB 50869, GB 16889 (landfill), CJJ 90, GB 18485, GB/T 31962, GB 16889 (leachate),
GB 14554, NY 1109, and NY 884 (×2, faecal coliforms and ascarid egg mortality). The NY 884 pair is
correctly X16 and not A4, as rules §2.2 requires. 5.4 is one candidate because one requirement
cites two documents for the same property. This is the right split under §2.4.

The supporting decisions are also correct. The 50 m³ scope of NY/T 90 is X5 (c78). The two
达标排放 clauses are split correctly: X9 when GB 18485 covers the same property in the same cell
(c87), and X7 for the sun-house discharge-system provision (c74).

### 4.3 Minor ledger labels

These do not change any row or any X15/X16 count.

- **c62** (lines 118–120, "主要处理模式见表1" + caption + image) is X14. Rules §2.4 say a pointer to a
  table of the same document is D1 of the rows it points to, or takes the X rule of what it points
  to. X14 (incidental numbers) is the wrong label, but harmless.
- **c160** "该值越小毒性越强" is X3. It is a qualitative reading of the GI, not a principle or term
  definition. X13 or X6 fits better. Harmless.
- **c26** covers only "应尽量保持清洁" (X8). "清空内容物，避免污染" in the same clause has no
  candidate of its own. It would be X1 or X8, so nothing is lost.

## 5. Decisions checked and confirmed

| Decision | Lines | Why it holds |
|---|---|---|
| 主体工艺 X13, 菌种来源要求 X10, 比能耗/发酵周期 A4 | 121 r1 | A4 covers quantities only; the rules name both exclusions as examples |
| 安全、有效 X13; 来源 and 种名 X10; strain safety → NY 1109 X16 | 127 | Matches X10/X13 examples; resolves 2.0.0 report §3.1 |
| GI cut-offs `definition` + `interpretation_bound` + `strict_bound` | 163 | A1 interpretation cut-off; resolves 2.0.0 report §3.3 |
| Table 1 适用范围 → X5 (4 candidates), no conditions | 121 | §3 Conditions; resolves 2.0.0 report §4.1 |
| Measurement basis in `metric_name` | 131, 134, 158 | §3 Conditions; resolves 2.0.0 report §4.2 |
| 每日定时收运 → exact 1 次/日, wording in `measurement_frequency` | 101, 104 | §3 Schedules; resolves 2.0.0 report §4.3 |
| Table 2 only for machine compost; Table 3, GI apply to both modes | 128 | Matches 9.3.6 exactly; one row per Table 3 row with the joint subject |
| Three 9.3.6 table pointers are D1 | 128 | Link to the Table 2 and Table 3 rows |
| 500 ml bottle, filter paper, seed species are X12 | 158, 159 | Apparatus and material identity |
| GI operands and the 100% factor are not rows | 161 | X13 / X14 |
| Container 完好 X15, 整洁美观 X11 | 97 | X15 example "container intact"; X11 example 美观 |
| Sun house 密封性, 保温性 X15 (two candidates) | 121 r2 | X15 example; split per §2.4 |
| Vehicle sign, 全密闭, 防臭, 防遗撒, 防渗滤液 (five X15) | 109 | Split per §2.4 example |

All 15 A6 values were checked against B.1.1 and B.1.2: 3 samples, ≥ 20.0 g, 1：10 W/V, ≥ 100
次/分钟, ≥ 40 mm, 1 h, 0.5 h, 3 blanks, 0～4 ℃, ≤ 48 h, 10 seeds, 5 ml, 25 ℃, 48 h, 3 replicates.
Comparators are correct (不小于 and 不超过 are inclusive). The Table 3 unit (mg/kg) is taken from the
column header, as it must be.

## 6. Cross-check against the gpt-6.1-sol 2.1.0 run

Run `20261007_054115` has 66 rows. Dropping its 14 `kind:inspection_requirement` and 17
`kind:delegated_requirement` rows leaves 35, the stand-in that SKILL.md describes.

- **Accepted rows: 35 = 35, one to one.** The two runs agree on every subject, property, value,
  comparator, unit, table row and `kind:` tag. The only differences are in units (§3.3), condition
  placement (§3.4, §3.5) and the GI cut-off line spans (§3.6). Both runs also accept
  `416_gold_3` and `416_gold_4`, which should be excluded (§3.1).
- **Pure requirements: 31 vs 33.** The X16 sets are identical (§4.2). The X15 sets differ only by
  the two 8.1.6 candidates (§4.1).

Two independent annotators, using different rule versions, reached the same 35 rows. Agreement
shows that both read the rules the same way. It does not show that the reading is right: both
accepted the agreement rows of §3.1, so the shared reading of A4 is the problem there.

## 7. Impact on scoring and recommended actions

1. Use run `20261007_083500` as the record-416 benchmark for `extract_metrics` (candidates v11 /
   enrich v8), and cite the run ID with every score. Report scores with and without
   `416_gold_3` and `416_gold_4` (§3.1). The clean core set is 33 rows.
2. Score the `exclude_pure_requirements` log against 33 X15/X16 candidates, and report the
   alternative with c47 (and optionally c48) removed (§4.1).
3. Normalize when matching: 机器成肥 and 机械成肥 equipment (§3.2), bare and per-object count units
   (§3.3), the placement of 每次测定 (§3.4), full-width colons in ratios (§3.6), and the
   `NY884`/`NY 884` spacing.
4. Report recall with and without the 15 `test_parameter` rows, because production extraction
   may not target test-method settings.
5. Next rules version (3.0.1 wording, or 3.1.0 if outcomes change; never edit 3.0.0):
   - Say whether X15 covers a process or management regime ("过程应密闭化管理"). If not, name X2 for
     it, and say whether "应密闭清运" is X1 or X15.
   - Add a pointer to a whole table that is only partly metrics (Table 1) to the D1/X list of §2.4.
   - State that an agreement duty about an activity ("约定收运的时间和频次") is X2, not A4. A4's
     "set by agreement" applies only to a property of an object; gate (a) still needs an object.
     Add this clause as an X2 example.
   - Say where per-occurrence scope such as "每次测定" belongs: `condition` or
     `measurement_frequency`.

## Method

The 35 rows and their `ext_info` (candidate ledger, coverage, reviews) were read from
`testbed.metrics` by the full run key. All 161 candidates were reviewed against source lines 1–169
and the text of `rules/3.0.0.md`. Table 1 (line 121) was read cell by cell, and Tables 2 and 3 row
by row. Evidence quotes, conditions, coverage contiguity, `strict_bound` placement, the absence of
`reference`/`cited_doc:` rows and the accepted-ledger links were checked by script. Field values
were checked by hand. The gpt-6.1-sol 2.1.0 run was read after the row review was drafted, to look
for missed metrics and ledger disagreements. Production `kb.metrics` predictions and
`kb.doc_proc_logs` were not read. The verdicts in §3 and §4 are one reviewer's judgement and should
be confirmed before they become rules.
