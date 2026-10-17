# Changelog — extract-metrics-benchmark

Two kinds of change are tracked separately:

- **Rules versions** — the annotation rules in `rules/<version>.md`, frozen once released and listed
  with their SHA-256 in `rules/versions.json`. `testbed.metrics.skill_version` is the rules version a
  run used. Any released version can be run again (`prepare --skill-version <version>`).
- **Tooling changes** — `SKILL.md` procedure, `references/`, `scripts/`, storage. Shared by all
  versions and always the latest; they must keep every released rules version runnable.

## Rules versions

| Version | Rules file | Notes |
|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | Original rules (jj commit 9e18). Known problems: devdoc `2026100601-devdoc-gold-metrics-416-review`. |
| 1.1.0 | `rules/1.0.0.md` | Alias: released as a tooling-only change (skill_version column); rules identical to 1.0.0. Used by run `e6bd8f49` (record 753). |
| 1.2.0 | `rules/1.0.0.md` | Alias: released as a tooling-only change (skill_name, model_name columns); rules identical to 1.0.0. |
| 2.0.0 | `rules/2.0.0.md` | Fixes from devdoc `2026100601-devdoc-gold-metrics-416-review` (S1–S8). See below. |
| 2.1.0 | `rules/2.1.0.md` | Statement kind per row (ADR 2026100603) and representation fixes from the 2.0.0 audit of record 416. See below. |
| 3.0.0 | `rules/3.0.0.md` | Requirements with nothing to measure are not metrics, matching `extract_metrics` since 2026-10-07. See below. |
| 3.1.0 | `rules/3.1.0.md` | A4 never supplies the object: a duty to agree an activity's time or frequency is X2. See below. |
| 4.0.0 | `rules/4.0.0.md` | A quantity to be set or sized according to another factor, or by design, is a requirement (X17), not a metric. See below. |
| 4.1.0 | `rules/4.1.0.md` | A4 rows are metrics with no value (`value_class = metric-with-no-value`) with typical values in `metric_desc`. See below. |
| 5.0.0 | `rules/5.0.0.md` | Sizing duties (X17) are metrics with no value too: A4 covers values to be declared, agreed, or set/sized by another factor. X17 retired. See below. |
| 5.1.0 | `rules/5.1.0.md` | Typical values of a metric with no value must be a numeric range with unit; "no typical value" only with a reason. See below. |
| 6.0.0 | `rules/6.0.0.md` | A metric has at least a value: A4 and A5 retired, value-less candidates are X18; definitions anywhere are X3; counts of the document's own parts are X4; provisions with no named quantity are X7. See below. |
| 6.1.0 | `rules/6.1.0.md` | A symmetric `±x` tolerance keeps its sign in `metric_value` (`±0.2`, not `0.2`). See below. |
| 6.2.0 | `rules/6.2.0.md` | The same metric stated in several places is one row listing all its lines (not D1 duplicates); a value stated in prose or a table is not an X13 formula operand. See below. |
| 6.3.0 | `rules/6.3.0.md` | Data dictionaries: a data element's data format (one row, the whole format) and allowed occurrences are A1, not X3 definitions. See below. |
| 6.4.0 | `rules/6.4.0.md` | Conditions read broadly (test method or apparatus, environment, population, location, load), object-only subject, `<kind>：<value>` shape. See below. |
| 6.5.0 | `rules/6.5.0.md` | A number that only qualifies another value (paired load, apparatus grade, restated setting) is its condition, not a row; a limit relative to another limit is A1 (`倍`), not D1. See below. |
| 6.6.0 | `rules/6.6.0.md` | A value the source does not state as a quantity (a derived count of ends/positions, a reset-to-zero instruction) is excluded as X19. See below. |
| 6.7.0 | `rules/6.7.0.md` | A number inside a definition is A1 only when it limits a measured property of the document's object; category boundaries of the people or things the object is for, and counting conventions, are X3. See below. |
| 6.8.0 | `rules/6.8.0.md` | A size written as a product of dimensions (250 mm×200 mm) is one row `250×200`, with one tolerance row; separately stated dimensions stay split. See below. |
| 6.8.1 | `rules/6.8.1.md` | Wording only: a tolerance cell serving several listed quantities is one row per quantity, with its qualifiers. See below. |
| 7.0.0 | `rules/7.0.0.md` | Modality is not part of the metric gate: a 可/宜/建议/酌情/考虑 clause that states a number is A1/A6 (X8 narrowed to clauses with no value); X1 excludes the action, not its numbers; new §2.6 for treatment protocols and procedures. See below. |

Default when no version is named: the newest released version (currently 7.0.0); pre-releases are never the default. From now on tooling changes do not create rules versions; 1.1.0 and 1.2.0 remain only
because rows were already saved under those labels.

### 7.0.0 — 2026-10-17

Major (which assertions are metrics changes). Found by auditing the 6.8.1 run `20261017_135026`
(claude-sonnet-5-5) of record 364 (WS/T 810—2022, emergency referral with clinical appendices)
against `kb.metrics`: 59 of the extractor's 139 rows were true metrics the gold missed (drug doses,
repeat intervals and counts, caps, infusion and observation times, thresholds). The ledger excluded
24 candidates covering them as X8 (permissive modality) and a few as X1. The gold was inconsistent
inside single sentences (洛贝林 3 mg accepted, the repeat interval of the same sentence excluded;
a plain-imperative diazepam dose accepted, a 可应用 cardioversion energy excluded).

- **X8 narrowed (§2.3).** Applies only to a permissive clause that states no value. A number in a
  可/宜/建议/酌情/考虑/尽量 clause is A1/A6; the modality is kept in `threshold_or_target`. The gate
  (§2.1) now says modality is not part of it.
- **X1 narrowed (§2.3).** Excludes the action, not a number stated in it.
- **§2.6 Treatment protocols, clinical pathways and operating procedures (new).** Table of what is a
  row: dose/amount per agent and population, caps, duration, repeat interval and repeat count,
  device energy/setting, observation or waiting time, trigger/discharge/transfer thresholds (a
  two-sided range is one `range` row), preparation quantities. Not rows: formulation labels
  (1:1000, 5％), actions, bare score values without their band, grade labels.
- **Audit (§4).** No X8/X1 candidate may state a number; a modality word governs the whole sentence,
  so one sentence gets one treatment.

Not changed, deliberately: a bound given only as a formula (SBP < 70 + age×2) stays X18, and a
scale of qualitative states with points (AVPU) stays out. Both were also among the 59 and are the
user's earlier rulings (6.0.0), to revisit separately. The stored 6.8.1 run is not changed.
Tooling is unchanged; the validator accepts 7.0.0 as it did 6.8.1.

### 6.8.1 — 2026-10-17

Patch (wording; outcomes unchanged). The 6.7.0 run of record 371 merged the shared ±5 mm cells of
Table 1 into one row per cell (障碍物尺寸允许误差, 平衡木尺寸允许误差), against §3's one property per row.
6.8.1 says it outright: a tolerance or resolution cell written once for several listed quantities
gives one row per quantity, named after it and with its qualifiers. Audit (§4) check added.

### 6.8.0 — 2026-10-17

Found when the user reviewed `extract_metrics` on record 371 (GB/T 44700—2024) against the 6.7.0 run
`20261017_070046` (claude-sonnet-5-5). Minor.

- **Product sizes (§3, Splitting).** "250 mm×200 mm 的面" and "底座尺寸为长300 mm×宽 300 mm" are one
  property each, the size: one row, `metric_value` `250×200` / `300×300`, unit once, `exact`, and one
  row for a tolerance that serves the size. Dimensions stated separately stay one row each. The 6.7.0
  run kept 250×200 mm as one row (256) but split 底座长度 / 底座宽度 (172/173).

The stored 6.7.0 run is not changed; its corrected copy is a separate 6.8.0 run. `extract_metrics`
follows the ruling from candidates prompt v25 / enrich prompt v23 (ChenWeb).

### 6.7.0 — 2026-10-17

Found when the user reviewed the 6.6.0 gold for record 371 (GB/T 44700—2024), run `20261017_060405`
(a corrected copy of `20261016_162743`, gpt-6.1-sol). Minor.

- **Where the X3 "aggressive" exception stops.** The 6.6.0 run accepted the age bands of 4 注 1
  (年龄分组（幼儿）3~6 周岁 … 老年人 60~79 周岁, subject 测试人群, rows 242–245) and the counting
  convention of 6.5.21.3 (绳转动角度 360°, row 461) as A1. The 6.3.0–6.5.0 runs excluded the same lines
  (X3/X5). The rules allowed both readings: X3 said a number inside a definition that is a value of
  a named quantity is A1 "aggressively", with no limit. Now it is A1 only when the defined term is a
  class of the thing the document specifies, measures or tests and the number limits a property
  measured on that thing (高滑移 stays A1). A category boundary of the people or things the object is
  for, and a counting, naming or unit convention, are X3; the category or convention goes into the
  `condition` of the rows it limits. A value required of a person, sample or population stays A1.
  The audit (§4) gains a check for `definition` rows and numbers in notes and "为/称为/计为" sentences.

The stored 6.6.0 runs are not changed.

### 6.6.0 — 2026-10-16

Found when the user reviewed `extract_metrics` on record 371 (GB/T 44700—2024) against the 6.5.0 run
`20261016_134040` (gpt-6.1-sol). Minor.

- **A value the source does not state as a quantity (new X19).** A count the reader derives from
  "两端数值" or "四角和中心" (端点数量 2, 测量点数量 5) and a reset instruction with no value and unit
  ("指针调整到"0"位" → 零位 0 mm) are not metrics: a user cannot use them. A number the text writes
  stays A1/A6.

The stored 6.5.0 run is not changed; its corrected copies `20261016_151516` (nine derived counts) and
`20261016_153000` (plus the zero position) are separate runs. `extract_metrics` follows the ruling
from candidates prompt v21 / enrich prompt v18 (ChenWeb).

### 6.5.0 — 2026-10-16

Found when the user reviewed `extract_metrics` on record 371 (GB/T 44700—2024) against the 6.4.0 run
`20261016_085615` (claude-opus-5-5). Minor.

- **Numbers that qualify another value (§3).** A paired load (B.1.4 静载荷力 300 N with 弯曲变形 ≤8 mm), an
  apparatus grade (6.5.4.1 5 等量块 → `试验装置：5 等量块`) or a setting restated in the same clause (6.4.2.1
  second 倾斜 10°) is part of the other value's condition, not a row. The extractor's mtc_21/76/92.
- **Relative limits (A1, D1).** 5.5.2 repeatability "不应大于该类测试器材所允许误差的绝对值" is A1 (1 倍,
  upper_bound), not a D1 pointer; the 6.4.0 run recorded it as D1 (c529). The extractor's mtc_8.

The stored 6.4.0 gold runs are not changed. `extract_metrics` follows the same rules from candidates
prompt v19 / enrich prompt v16 (ChenWeb jj `qpwu`).

### 6.4.0 — 2026-10-16

Found when scoring `extract_metrics` on record 371 (GB/T 44700—2024) against the 6.3.0 run
`20261015_163536` (claude-sonnet-5-5). Clauses 6.5.14.1 and 6.5.14.2 state the same test settings,
once with a 运动模拟装置 and once with a 模拟物; the gold merged each pair into one row covering both
lines. The user ruled on 2026-10-16 that the test method is a condition, so they are two metrics.
Minor: 6.3.0 already kept different conditions apart; 6.4.0 says what a condition is.

- **Conditions (§3).** `condition` holds what limits when, where, for whom or how the value holds:
  applicability (population, category, size class, variant), environment and operating state, test
  method or apparatus, location or body site, load, input level or time point.
- **Subject vs condition.** `metric_subject` names only the object; qualifiers go to `condition`.
- **Shape.** `<kind>：<value>` qualifiers joined by `；` (English: `<kind>: <value>` joined by `; `).
- **Occurrences / X12.** The same settings stated under different methods are separate metrics; a
  method or apparatus that qualifies a value is its condition, not an excluded row.

`extract_metrics` uses the same definition from candidates prompt v16 / enrich prompt v13 (ChenWeb
openspec change `extract-metrics-conditions`), and `score-extract-metrics` checks `condition` as a
weighted field.

### 6.3.0 — 2026-10-15

Found in the 6.2.0 run `20261015_043344` (claude-sonnet-5-5) of record 376 (GB/T 40423—2021), which
kept 6 gold rows from a 322-element data-element catalogue (Table 4). The run excluded every data
format and allowed occurrence count as X3 ("attribute definitions of a data dictionary"), after the
annotator recommended that reading and the user accepted it; on review the user ruled it wrong.
Minor: correctly read, 6.2.0's gate already accepts these rows; 6.3.0 makes it explicit.

- **Data dictionaries (§2.5).** The data element is the object. Its data format with a number
  ("an..70", "n4..5,1") is **one A1 row** holding the whole format (fixed length `exact`, maximum
  `upper_bound`, minimum and maximum `range`; tag `data_format`), and its allowed occurrences ("1",
  "0..1", "1..n") one A1 row (tag `occurrence_count`). Notation clauses, code lists, enumerated value
  domains and date patterns (YYYYMMDD) stay X3; GB/T value domains X16; the element's measured value
  with no number X18; obligation M/O/C makes no row; the document's identifier scheme is X14.
- **Misprints** that the document's own notation resolves (`nl` for `n1`, `n3..4.1` for `n3..4,1`) are
  stored as the notation reads them, with the printed text in `evidence` and `annotation_notes`.
- **Audits (§4)** check one format and one occurrence row per element.
- No tooling change: `validate` already gates by version, and 6.3.0 inherits every 6.x check.

### 6.2.0 — 2026-10-15

Found by comparing the 6.0.0 (claude-opus-5-5, run `20261010_055329`) and 6.1.0 (claude-sonnet-5-5, run
`20261014_162055`) gold sets of record 753. Minor: which assertions are metrics is unchanged except the X13 fix.

- **Occurrences (§3).** The same metric (subject, property, value, unit, comparator, condition, class)
  stated in several places is **one row** whose `source_line_spans` list every occurrence line, with the
  table rows unioned and one evidence entry per line. The ledger keeps one `accepted` candidate per
  occurrence, all linking that row. Replaces "preserve independently stated occurrences for mention-level
  benchmarking", which left later occurrences as D1 rows with no gold evidence (753: 3.28 and 11.3 for the
  5.4 nominal fan power). Different subject, property, value, unit, comparator or condition stays a
  separate row (753: 名义风量 and 名义风机功率 both at 1013.25 hPa). **D1** is now only the same occurrence
  detected twice in overlapping windows, or a pointer that states no value.
- **X13 narrowed.** A formula operand is a symbol or constant that exists only inside the formula. A
  named quantity that a sentence, note or table states with its own value is a metric even when a formula
  encodes it (753 11.1.2 "每增加 1 hPa，排热量增加约 0.065 %" versus the coefficient 6.5×10⁻⁴ of formula (11),
  which 6.0.0 excluded as X13). The formula itself stays X18.
- **Consistency audit (§4)** checks both points.
- **Tooling:** `validate` (rules ≥ 6.2.0) refuses two rows with the same name, subject, unit, value, range
  type, class and condition (the spans no longer tell them apart), and refuses an `accepted` candidate whose
  lines are not among its metric's `source_line_spans`. Earlier versions are unaffected.
- Runs saved under 6.1.0 and earlier are not changed. Scoring: a merged row has several line spans, so
  match on any shared line (not on the first span).

### 6.1.0 — 2026-10-14

Representation fix, found on `753_gold_29` (`±0.2 K` stored as `0.2`). Rules 6.0.0 said both "`metric_value`
is the bare number" and "keep ± tolerances in source-faithful text", and the bare-number rule won:
48 other ± rows of run `20261010_055329` lost their sign too, while `20±5` kept it.

- **Rule:** a symmetric tolerance, uncertainty or permitted deviation written `±x` is stored as
  `metric_value = "±x"` with `value_range_type = upper_bound` (bound on the magnitude). `a±b` stays `range`
  as written; asymmetric tolerances are not stored this way. Which assertions are metrics is unchanged.
- **Tooling:** `validate` (rules ≥ 6.1.0) refuses a non-range row whose `threshold_or_target` states `±<metric_value>`
  while `metric_value` has no ±. Earlier versions are unaffected.
- Runs saved under 6.0.0 and earlier are not changed. `score-extract-metrics` does not strip `±`, so score a
  6.1.0 gold against predictions that also keep it.

### 6.0.0 — 2026-10-09

Major: which assertions are metrics changes. Follows the user's decisions while reviewing
`extract_metrics` on records 416 and 753 (devdoc `2026100801-devdoc-extract-metrics-soft-drop-and-filtering`):
after many rounds of keeping some value-less candidates and excluding others, the rule is **a metric
has at least a value**; a named quantity without one is at most a definition.

- **§2.1:** gate (c) needs a value stated by this document; the "value left open" stand-in is gone.
- **A4 retired.** Quantities to be declared, agreed, or set/sized by another factor or by design are
  **X18 (no value)**; `value_class = metric-with-no-value` and the typical-values text (4.1.0–5.1.0)
  are no longer used. 416's 比能耗, 发酵周期 and 单室体积 are X18.
- **A5 retired.** A formula or a definition of how a quantity is computed states no value: X18
  ("标准排热量为两种方法测量结果的算术平均值", 753). Interpretation cut-offs keep their value and stay A1
  (`value_class = definition` is only for them).
- **X3** covers definitions wherever they appear: definitions clause, symbol/abbreviation list,
  "式中" explanation, note, running text (753's 3.7–3.15 and its symbols table). A number inside a
  definition that is a value or limit of a named quantity is A1, aggressively (高滑移: 滑移温度 > 3 K at
  40 °C); a number that only describes the computation is not (两个独立测点的算术平均值).
- **X4** is a count of the document's own parts: categories, methods, procedures, steps, definitions,
  concepts, clauses ("应使用两种试验方法", 753). Counts of samples, measuring points, sensors and sets of
  readings stay A1/A6 (A6 now lists them).
- **X7** includes provisions with no named quantity even when "suitable" or "according to" factors
  (416's "配备相应的收集、运输设备和作业人员": no 配备数量).
- **§3 splitting:** one row per condition (753's SC1/SC2/SC3), never one row with "25; 25; 35".
- **§3.2** is now how to record X18 candidates, the answer key for the extractor's `no_value` drops.
- **Audit (§4):** no accepted row is `qualitative` or `limit_absent`.
- Open judgement recorded in the rules: a bound whose value is only a formula
  ("τ ≥ (200 × Δt_i × C) / P") is X18, matching the extractor; revisit if that loses real criteria.
- Tooling: `validate` (rules ≥ 6.0.0) refuses an accepted row without a value (`qualitative`,
  `limit_absent`) and a `definition` row that is not an `interpretation_bound`. Citing A4, A5 or X17
  is refused because they are not rule IDs of 6.0.0.

### 5.1.0 — 2026-10-07

Minor: the same assertions are metrics as in 5.0.0; only `metric_desc` of A4 rows changes. In 5.0.0
run `20261007_131153` (record 416, gpt-6.1-sol) all three metrics with no value said
"无可靠通用典型值", so none gave the typical values the user asked for.

- **§3.2:** typical values are a numeric range with unit plus what it depends on; order of magnitude
  is enough. Uncertainty or dependence on type/scale/feedstock is never a reason to omit it. Only when
  no range can exist for that kind of object: "无可比典型值（原因：…）" / "No comparable typical value
  (reason: …)".
- **Audit (§4)** checks the same.
- Tooling: `validate` (rules ≥ 5.1.0) requires a digit after the typical-values marker, or the escape
  phrase with a non-empty reason, in `metric_desc` and `metric_desc_en`. Whether the range is
  plausible stays a reviewer check.

### 5.0.0 — 2026-10-07

Major: changes which assertions are metrics. Asked for by the user for consistency with 4.1.0: a
sizing duty (堆肥设施(阳光房)应根据垃圾日处理量合理设置单室体积) names a real metric without a value, exactly
like the declared 比能耗 and 发酵周期, so it is a metric with no value too.

- **A4** (§2.2): a named quantity of an object whose value the document leaves open, to be declared,
  agreed, or set/sized/chosen according to another factor or by design. Stored per §3.2
  (`metric-with-no-value`, typical values in `metric_desc`); the sizing factor goes in `metric_desc`,
  not `condition`.
- **X17** retired (§2.3); its ID is not reused, and `validate` refuses it for 5.0.0.
- **Gate** (§2.1 (c)): the stand-in is "the document names the quantity and leaves its value open".
- Unchanged exclusions: an activity's open value (X2), cited-document values (X16), same-document
  tables (D1), direction-only aspirations (X6).
- Record 416: 单室体积 returns as an A4 row; expect 33 rows. `extract_metrics` keeps sizing duties as
  `limit_absent`, so they now match instead of scoring as false positives.

### 4.1.0 — 2026-10-07

Minor: the same assertions are metrics as in 4.0.0; only how A4 rows are stored changes. Asked for by
the user after the domain-expert review of `416_gold_4`/`416_gold_5` in run `20261007_120517`
(gpt-6.1-sol): 比能耗 and 发酵周期 are real metrics of the composting equipment that the document names
without a value, so they are metrics with no value, not requirements.

- **A4** (§2.2, §3.2 new): `value_class = metric-with-no-value` (`value_class_en` "metric with no
  value"). `limit_absent`, empty value and unit, and the `requirement_value_open` kind are unchanged.
- **`metric_desc`** (§3.2): explains the metric (property, object, how measured, usual unit) and gives
  typical values from domain knowledge after the marker "典型值（领域经验，非本文件规定）：" or "Typical
  values (domain knowledge, not stated by this document):". The only place outside knowledge is allowed.
- **Audit** (§4): every A4 row uses the class and plausible, marked typical values; no other row does.

Tooling (`benchmark_io.py`), gated to rules ≥ 4.1.0: `metric-with-no-value` is a valid `value_class`;
`limit_absent` rows and only they use it; `metric_desc` (and `metric_desc_en` for non-English sources)
must carry the typical-values marker; `value_class_en` must be "metric with no value".
`statement_kind` maps the class to `requirement_value_open`, as for the extractor's requirement +
`limit_absent` rows, so scoring still matches them. The ChenWeb mirrors (`metric-statement-kind.ts`,
`metric_statement_kind.go`) map it the same way since 2026-10-07, so gold pages no longer show these
rows as `unclassified`.

### 4.0.0 — 2026-10-07

Major: changes which assertions are metrics. Asked for by the user after reviewing `416_gold_6` of
run `20261007_093654` (堆肥设施(阳光房)应根据垃圾日处理量合理设置单室体积): a domain expert reads it as a
design requirement, not a metric. It names a quantity, but no value exists anywhere and nobody must
state one, so there is nothing to check a measurement against. 3.x accepted it as A4, using it as
A4's own example.

- **X17** (§2.3, new): sizing duty. A quantity to be set, sized, chosen or matched according to
  another factor (throughput, population, demand, site), or by design, with no value, relation,
  formula or table and no party obliged to declare or agree a value.
- **A4** (§2.2): keeps only values a party must fix and record: declared by a supplier or
  manufacturer, or agreed between named parties for a quantity of an object.
- **Gate** (§2.1 (c)): the stand-in no longer lists "determined by another factor".
- **Audit** (§4): every A4 row names who must declare or agree the value; equivalent sizing clauses
  all get X17.
- `validate` is unchanged apart from accepting X17 (rule IDs are read from the rules file); whether
  a party must state the value is a reviewer check. Test added for X17 being valid only from 4.0.0.
- Record 416: `416_gold_6` (单室体积) of run `20261007_093654` becomes X17; 32 rows remain. 比能耗 and
  发酵周期 (the equipment must state them) stay A4.
- Extractor gap: enrich prompt v8 still keeps "determined by design" values as `limit_absent`, so
  X17 clauses score as `extract_metrics` false positives until the prompt follows.

### 3.1.0 — 2026-10-07

Minor: a clarification. Read correctly, 3.0.0 already excluded these candidates (gate (a) admits an
activity as the object only when the requirement is a number about it), but every reviewed run of
record 416 (2.0.0, 2.1.0, 3.0.0) accepted them as A4, because A4 lists "set by agreement" without
saying it needs an object. Follows `analysis-reports/20261007-0854-metric-extraction-analysis-report.md`
§3.1 (run `20261007_083500`).

- **Gate** (§2.1): A4's stand-in for the value does not make an activity an object. An activity's
  time slot or clock time is not a measurable property.
- **A4** (§2.2): the open quantity must belong to an object that passes gate (a).
- **X2** (§2.3): covers a duty to agree, set or announce an activity's time, frequency or method, with
  "约定餐厨垃圾收运的时间和频次" as an example.
- **Audit** (§4): every A4 row's subject is an object, not an activity.
- `validate` is unchanged: whether a subject is an object or an activity is not mechanically
  checkable, so this stays a reviewer check.
- Record 416: `416_gold_3` and `416_gold_4` of run `20261007_083500` (餐厨垃圾收运时间/频次) become one
  X2 candidate; 33 rows remain. The daily-collection rows (1 次/日) stay A1.

### 3.0.0 — 2026-10-07

Major: changes which assertions are metrics. Follows ADR 2026100603 DR1/DR3 (amended 2026-10-07)
and ChenWeb openspec change `exclude-pure-requirements-from-metrics`: `extract_metrics` (candidates
prompt v11, enrich prompt v8) no longer stores inspection or delegated requirements, so 2.x gold
rows of those kinds count against an extractor that is doing what it was asked.

- **Gate** (§2.1): property (b) must be measurable, a quantity; the delegation stand-in in (c) is
  removed. A4 (value left open) is the only stand-in.
- **A2 → X15, A3 → X16**: inspection requirements and delegations to an identified document are
  excluded, but each is still one ledger candidate, split like a metric, with the object and (for
  X16) the cited documents in its reason (§2.4). The ledger is the answer key for the
  extractor's `exclude_pure_requirements` log.
- **A4 narrowed**: a value set by a cited document is X16 even when the clause names a quantity
  (粪大肠菌群数应达到 NY884 的要求); a pointer to the document's own table is D1.
- **Kinds** (§3.1): no accepted row is `inspection_requirement`, `delegated_requirement` or
  `observation`; the only accepted `qualitative` rows are A5 definitions.
- Record 416: of the 66 rows of 2.1.0 run `20261007_054115`, the 31 inspection/delegated rows
  become X15/X16; 35 rows remain. `extract_metrics` stored 36 on 2026-10-07 (prompt v8).

### 2.1.0 — 2026-10-07

Minor: which assertions are metrics does not change. Follows the audit
`analysis-reports/20261006-1311-metric-extraction-analysis-report.md` (run `20261006_121911`) and
ADR 2026100603 (Separate Requirements from Metrics).

- **Statement kind** (§3.1): every accepted row carries one `kind:<kind>` tag, the vocabulary the
  ChenWeb interface uses to label rows as requirements, metric values, test parameters or
  definitions. Scorers can now split gold rows into requirements and metrics without a new run.
- **Interpretation cut-offs** (A1): `value_class = definition`, the reading in
  `formula_or_definition`, tag `interpretation_bound`, not `reference` (audit §3.3).
- **Conditions** (§3): a method's suitability (适用范围) is not a `condition`; a measurement basis
  (以烘干基计, 鲜样) goes in the name or description (audit §4.1, §4.2).
- **Schedules** (§3): "每日" is `exact` 1 `次/日`, not an interval of 1 day (audit §4.3).
- **Delegations** (A3, §2.4): a process may be the object; `cited_doc:` identifiers are written as
  in the normative-reference list (`NY 884`); `reference` is only for A3 rows (audit §4.4, §4.5).
- **Clarifications, not new exclusions:** A4 only for quantities; process names stay X13 even when
  the source calls them parameters; species/strain names and other identities are X10. These state
  how 2.0.0's rules already apply; the 2.0.0 run accepted `416_gold_19` (主体工艺) and `416_gold_39`
  (种名) in error (audit §3.1, §3.2).

### 2.0.0 — 2026-10-06

Major: changes which assertions are metrics. Expect far fewer rows than 1.x (record 416: 134 rows
under 1.0.0, about 64 hold up under the review).

- **Metric gate** (S1): a metric needs an object, a measurable or inspectable property, and a value,
  bound or concrete criterion, or a delegation to an identified document, or `limit_absent`.
- **Decision rules with IDs**: accept A1–A6, exclude X1–X14, duplicate D1. Every candidate records
  `rule_id`. Non-metric patterns are listed (actions, duties, planning, principles, term definitions,
  classification counts, applicability, aspirations, facility provision, disposal routes).
- **Splitting** (S2): only into parts that each pass the gate; never split formula operands.
- **Consistency audit** (S3): third audit comparing excluded and accepted candidates by line and rule.
- **Test-method settings** (S4): numeric settings kept, tagged `test_condition` (A6); qualitative
  settings become `condition`; apparatus and procedure steps excluded (X12).
- **Modality and references** (S5): 可/宜/鼓励/提倡/尽量 excluded (X8); delegation needs an identified
  document; unnamed "达标"/"requirements" excluded (X9).
- **Representation** (S6): `metric_value` is the bare number; strict bounds tagged `strict_bound`;
  `definition` only for metric/formula definitions; "supplier declares named parameter X" →
  `limit_absent` on X itself (A4).
- **Correctness review** (S7): every `condition` must appear in the source; every
  `threshold_or_target` must stand alone.
- **User decisions** (S8, group D): licences/certificates/provenance excluded (X10); housekeeping
  states kept only when presence/absence is observable (A2), subjective ones excluded (X11).

## Tooling changes

### 2026-10-16 — interpretation intervals and exact scale mappings

Document 364 exposed a validator/contract restriction that rejected numeric interpretation ranges
(for example `5 ≤ MEWS < 9`) and exact MEWS consciousness scores. A1 accepts numeric values and
ranges, and the rules require one interval per assertion. The shared validator now accepts all
four numeric range types on `interpretation_bound` definition rows, retaining the required
definition text, matching kind, finite ordered range endpoints and rejection of nonnumeric rows.
The procedure and payload contract explain exact scale mappings and preservation of half-open
endpoints in source wording and annotation notes. Released rules and their hashes are unchanged;
existing single-bound payloads keep validating. Regression tests cover intervals under 2.1.0 and
6.4.0, exact scores, missing endpoints and nonnumeric rejection.
The same document also exposed a false duplicate between `<40` and `≤40`: from rules 6.2.0,
assertion identity now includes `strict_bound`, as the rules' same-comparator requirement implies.
A regression test distinguishes these bounds while still rejecting a true repeated assertion.

### 2026-10-16 — condition_en in gold metrics

`testbed.metrics.condition_en` (ChenWeb migration `20261016000002`) holds the English rendering of a
gold row's `condition`, like `kb.metrics.condition_en`. `validate` accepts it as one of the `_en`
fields and, for rules 6.4.0 and later, requires it on every row of a non-English source whose
`condition` is non-empty. Earlier rules versions are unchanged. The ChenWeb metric pages show both.

### 2026-10-10 — one stored run ID column in gold metrics

`testbed.metrics.run_id` is now the writable run ID column; the duplicate
`benchmark_run_id` column is removed by a reversible project migration. Existing
run values and constraints are preserved. The helper maps the unchanged payload
field `benchmark_run_id` to `run_id` when saving gold rows. Run audits and saved
scoring artifacts retain their field names. Benchmark options and scoring readers
now query the canonical column. No rules versions change.

### 2026-10-10 — persist benchmark dropped candidates

Save excluded and duplicate candidates to `testbed.metrics_dropped` with the same
run ID and full skill/version/model identity as gold metrics, preserving the original
candidate JSON. The project migration backfills existing run ledgers. Saves are atomic
across the run audit, gold metrics and dropped candidates; runs with zero gold rows
now persist their audit and drops too, and cannot be saved twice. The Benchmark page
loads drops from this table for the same resolved run as its gold view. Rules are unchanged.

### 2026-10-10 — run_id column

The Goose project migration `20261010000002_add_run_id_to_testbed_metrics.sql` adds
`testbed.metrics.run_id`, a stored generated column equal to `benchmark_run_id`.
Existing rows and new saves receive it automatically; writers and full composite
run identity are unchanged. PostgreSQL integration checks cover saves, existing-row
population and rollback/reapply. No rules version changes.

### 2026-10-08 — extract_metrics keeps dropped rows

`extract_metrics` now saves every row it sets aside to `kb.metrics_dropped` and logs them as one
`drop_metric_rows` entry; the `exclude_pure_requirements` entry is no longer written (ChenWeb openspec
change `metric-row-soft-drop-decision-model`). Dropped pure requirements are the rows with
`drop_stage = 'statement_kind'`. Rules files are unchanged; where they name the old log entry, read
it as "the run's dropped pure requirements".

### 2026-10-07 — run audit record stored once per run
- `testbed.metrics.ext_info` used to copy the run's whole audit record (candidate ledger, coverage,
  reviews; ~30 KB) into every row, about 94% of each row's `ext_info`. Migration `20261007000002`
  adds `testbed.metric_benchmark_runs` (one row per run key, referenced by `testbed.metrics`), moved
  the 10 saved runs there and cut per-row `ext_info` to schema `3`: `evidence`, `annotation_notes`,
  `candidate_ids`. Table size 43 MB → 2.6 MB. The migration refuses to collapse a run whose rows
  disagree; its Down restores the schema-2 rows.
- `benchmark_io.py`: `run_row()` builds the run row; `save` inserts it before the metrics in the same
  transaction. `score-extract-metrics` reads the ledger from the run table.
- Migration `20261007000001` widens `testbed.metrics.value_class` to `metric-with-no-value`, which
  rules 4.1.0+ need (without it their saves fail).

### 2026-10-07 — validation and scoring for rules 3.0.0
- `validate` gates on rules ≥ 3.0.0: an accepted row may not have kind `inspection_requirement`,
  `delegated_requirement` or `observation`, nor `value_class = reference`, `external_reference` or
  `cited_doc:`. Rule IDs come from the rules file, so A2/A3 are refused there. 2.x and 1.x payloads
  validate unchanged; the 2.1.0 tests now pin 2.1.0 explicitly.
- `SKILL.md` points at the current default prompts (enrich v8, candidates v11) and says how to score
  `extract_metrics`: gold rows against `kb.metrics`, X15/X16 candidates against the
  `exclude_pure_requirements` log; a 2.1.0 run stands in only with its pure-requirement rows dropped.
- `references/benchmark-contract.md`: the 3.0.0 tag and rule constraints.

### 2026-10-07 — document invocation completes persistence
- Invoking the skill for a document authorizes extraction, audit, validation, save to `testbed.metrics`, and read-back; only an explicit draft-only/no-save request omits persistence.
- `model_name` comes from the invoking model’s runtime or active-session metadata, not user input or project extraction configuration. When only a runtime label is exposed, record it with a provenance note rather than blocking or inventing an exact ID.
- Updated the shared procedure, benchmark contract and user manual. Released annotation rules, hashes, storage schema and validation behavior are unchanged.

### 2026-10-07 — validation for rules 2.1.0
- `validate` gates new checks on rules ≥ 2.1.0: exactly one `kind:` tag matching the row's shape
  (`statement_kind`, a copy of the ChenWeb classifier), `reference` only with `external_reference`,
  `interpretation_bound` only on definition bounds, `cited_doc:` identifiers with a space before the
  number. Payloads for 2.0.0 and 1.x validate unchanged.
- Tests: fixture now defaults to 2.1.0; 2.0.0-specific tests pin their version.

### 2026-10-06 — validation for rules 2.0.0
- `validate` gates new checks on rules major version ≥ 2: `rule_id` per candidate (read from the bold
  IDs in the rules file, prefix must match the decision), no comparator in `metric_value`,
  `strict_bound` only on bounds, `test_condition` only on numeric rows, `definition` needs
  `formula_or_definition`. Rules 1.x payloads validate unchanged.

### 2026-10-06 — timestamp run IDs; a run key is never reused
- `prepare` sets `benchmark_run_id` to the local time as `yyyymmdd_hhmmss` (was a UUID); `validate`
  refuses any other format, so payloads prepared with a UUID must be prepared again.
- A run is identified by (`skill_name`, `skill_version`, `model_name`, `benchmark_run_id`). `save`
  locks the key and refuses it if any row already has it: every save creates new records.
- Migration `20261006000004`: column `TEXT` with a format check;
  `UNIQUE (skill_name, skill_version, model_name, benchmark_run_id, metric_id)` replaces
  `UNIQUE (input_record_id, benchmark_run_id, metric_id)`. Existing runs were renamed from their
  first row's time; the old UUID is in `ext_info.legacy_benchmark_run_id`:
  `22aa157c` → `20261006_071048` (record 416, 1.0.0), `e6bd8f49` → `20261006_081536` (record 753,
  1.1.0), `07faf118` → `20261006_085331` (record 416, 1.2.0).
- No new rules version: rules and `skill_version` are unchanged.

### 2026-10-06 — default is the newest version
- With no `--skill-version`, `prepare` uses the newest released version (numeric comparison; pre-releases
  excluded). The `default` field was removed from `rules/versions.json`.

### 2026-10-06 — runnable versions
- Rules moved out of `SKILL.md` into frozen `rules/<version>.md` + `rules/versions.json`.
- `prepare --skill-version <v>` selects a released version and refuses an
  unknown version or an edited rules file; `rules_sha256` is stored in the payload and in
  `ext_info.rules_sha256`. Payloads prepared by older tooling (no hash) still validate.

### 2026-10-06 — skill_name and model_name (labelled 1.2.0)
- `testbed.metrics.skill_name`, `model_name` (`TEXT NOT NULL`, migration `20261006000003`);
  `prepare --model-name` required. Runs `22aa157c` and `e6bd8f49` backfilled as `gpt-6.1-sol` from
  their Codex session log.

### 2026-10-06 — skill_version (labelled 1.1.0)
- `testbed.metrics.skill_version` (`TEXT NOT NULL`, migration `20261006000002`); run `22aa157c`
  backfilled as `1.0.0`.
