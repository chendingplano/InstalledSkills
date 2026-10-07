# Metric Extraction Analysis: Record 416, rules 4.0.0, gpt-6.1-sol (domain-expert review)

**Date:** 2026-10-07
**Document:** `kb.inputs.id = 416`, DB33/T 2030—2018 《农村生活垃圾分类处理规范》 (Zhejiang provincial
standard for separating and treating rural household waste)
**Source:** `/Users/cding/Apps/SemOS/Artifacts/0/416/std_1503937_mineru.txt`, 169 records, SHA-256
`5acb3df6…4a590fcd`. Every saved row carries this hash.

| Run key | Value |
|---|---|
| `skill_name` | extract-metrics-benchmark |
| `skill_version` | 4.0.0 (`rules_sha256` `82e5b8a2…73ee34`, matches `rules/versions.json`) |
| `model_name` | gpt-6.1-sol |
| `benchmark_run_id` | `20261007_120517` |
| Saved rows | 32 |
| Candidate ledger | 147: 32 accepted (A1 14, A6 15, A4 2, A5 1), 113 excluded, 2 duplicate (D1) |

## How this review was done

This review asks one question: **does the run capture what a solid-waste and compost-quality expert
would call the measurable requirements of this standard, with correct values, and nothing extra?**
As instructed, the answer does not rest on the skill's rules. Wherever the rules and expert
judgement disagree, this report follows expert judgement and names the rule involved, so the
disagreement can be traced.

I read all 169 source records, including the full HTML of Tables 1–3 and the whole of Annex B. I
checked each of the 32 saved rows and all 115 non-accepted ledger decisions against that text. I
also compared the run with the other 4.0.0 run of this document (`claude-opus-5-5`,
`20261007_115911`). I did not read the production `kb.metrics` predictions.

## 1. Verdict

- **Correct.** For every metric it saves, the run identifies the right thing measured, the right
  object it applies to, the right comparison (minimum, maximum, exact or range), the right number
  and the right unit. This holds for all 32 rows. No value is invented, misread or attached to the
  wrong fertilizer or table row.
- **Accurate.** The problems I found are about how values are recorded, not what they are: one
  comparison that is arguably too strict (§3.1), a few fields that hold information they were not
  meant for (§3.2), and value/unit spellings that a scorer has to normalize (§3.3). None of them
  would mislead a reader of the standard.
- **Nearly complete, with one real expert-level gap.** Every number in the document that sets a
  requirement on the waste system, the fertilizer or the test method is captured. The gap is the
  two pathogen-safety indicators that 9.3.6 names but whose limits it takes from NY 884 (粪大肠菌群数,
  蛔虫卵死亡率). An expert would count them among the document's key product-quality metrics (§4.1).
  Three smaller items are judgement calls (§4.2).
- **Reproducible.** The claude-opus-5-5 4.0.0 run, built independently, contains the same 32
  assertions with the same values and comparisons (§6). That agreement makes the run a stable
  benchmark for scoring `extract_metrics`.

**Expert-adjusted gold for 416:** the 32 saved rows, plus 2 rows for the NY 884 indicators if the
benchmark is meant to cover every quality indicator the standard requires. Two of the 32 (the
GI < 100% and GI > 100% readings) are correct but of little use to a practitioner (§5).

## 2. What the document actually specifies

Read as a practitioner would, the document's measurable content falls into six groups. The run
covers each one.

| Group | Source | Expert expectation | Run |
|---|---|---|---|
| Household containers | 7.1.2 | ≥ 2 containers (one set: perishable + other) per household | `gold_1` ✔ |
| Collection schedule | 8.1.2, 8.1.5 | perishable and other waste collected daily | `gold_2`, `gold_3` ✔ (comparison: see §3.1) |
| Composting-machine parameters | Table 1, row 1 | 比能耗 and 发酵周期 must be stated by the equipment (no value given) | `gold_4`, `gold_5` ✔ |
| Fertilizer quality | 9.3.6, Tables 2–3 | GI ≥ 60%; OM ≥ 30% (dry), moisture ≤ 30% (fresh), pH 5.5–8.5; As ≤ 15, Hg ≤ 2, Pb ≤ 50, Cd ≤ 3, Cr ≤ 150 mg/kg (dry); fecal coliforms and roundworm-egg mortality per NY 884 | 9 of 11 ✔ (`gold_6`–`gold_14`); the 2 NY 884 indicators are missing (§4.1) |
| Germination test (Annex B, normative) | B.1.1, B.1.2 | 15 numerical test settings | `gold_15`–`gold_29` ✔ |
| GI calculation and reading | B.2 | formula B.1; < 100% phytotoxic, > 100% stimulating | `gold_30`–`gold_32` ✔ |

The fertilizer rows apply each table to the right product. 9.3.6 applies Table 2 to
machine-composted fertilizer only, and Table 3 to both machine-composted and solar-assisted compost.
The run follows this exactly: Table 2 rows are on "机器成肥产出的肥料" and Table 3 rows on both
products. This is the reading error an extractor is most likely to make here, and the run avoids it.

As a cross-check, the heavy-metal limits, the moisture limit and the pH range are the same as those
in the national organic-fertilizer standard NY 525-2012, which is what a reader would expect a
provincial standard to adopt. The organic-matter minimum (30%) is the provincial choice and is
stored as written.

The measurement basis travels with each value: 以烘干基计 (dry basis) and 鲜样 (fresh sample) are part
of `metric_name`, not stored as a `condition`. This is right. "Moisture ≤ 30%" means something
different on a dry basis.

## 3. Saved rows: findings

### 3.1 Daily collection is stored as exactly once a day (`gold_2`, `gold_3`)

The source says "易腐垃圾应每日定时收运" and "其他垃圾应每日定时收运". Both rows store this as exactly
1 次/日 (`value_range_type = exact`). A practitioner reads 每日定时 as "every day, at a set time": the
point is that no day is skipped. A village that collects twice a day meets the requirement. "At
least once a day" (`lower_bound`, 1 次/日) is the more faithful reading. `exact` would mark the
twice-a-day village as non-compliant.

*Impact:* low. The value and unit match either way. A scorer that requires the same comparison type
would mark a correct `lower_bound` prediction as wrong, so it should accept either here.

### 3.2 Fields used for something other than their purpose

- **`measurement_frequency` on `gold_2`/`gold_3`** holds "每日定时收运". That field is meant for how
  often a metric is *measured*. Here the frequency is the metric itself, and it is already the value.
  The text duplicates the value and could confuse a consumer that reads the field literally.
- **`condition` on test parameters.** Several entries are not conditions under which the value
  applies:
  - `gold_22` "每次测定" and `gold_29` "每个样品" give the basis of the count (per run, per sample).
    They belong in the name, which `gold_29` already has ("每样品").
  - `gold_25` "水堇或萝卜种子" names the test species. The seed count is 10 for either species, so
    the species does not restrict the value. It is a separate qualitative test setting. GI depends
    on the species, so an expert would want it recorded, but not as a condition on the seed count.
  - `gold_27`/`gold_28` "黑暗" (darkness) is defensible. Darkness is a co-required incubation
    setting, and the condition field is the nearest place to keep it.
- **`gold_31` and `gold_32` share one `metric_name`** ("植物种子发芽指数解释界限"). The phytotoxic
  reading and the stimulating reading can only be told apart by the comparison and the threshold
  text. The claude run names them separately ("植物毒性判读" / "促进作用判读"), which is clearer.
- **`gold_1` stores ≥ 2 containers in total.** The source requires one set made up of a perishable
  container and an other-waste container. Two other-waste containers would meet "≥ 2 in total" but
  not the clause. The annotation note says this, but the stored row cannot express it. This is the
  limit of a single number, not an error.

### 3.3 Value and unit spellings the scorer must normalize *(scoring)*

| Row | Stored | Normal form | Note |
|---|---|---|---|
| `gold_17` | `1：10` / unit `ratio` | `1:10`, unit W/V (g : mL, dry basis) | Full-width colon. "W/V" means a mass-to-volume ratio (20 g dry sample to 200 mL water), so a bare `ratio` unit loses the dimensions. The basis is kept only in `metric_desc` |
| `gold_23` | `0℃～4℃` / unit `℃` | `0~4` / `℃` | Unit repeated inside the value; `value_min`/`value_max` (0, 4) are correct |
| `gold_9` | `5.5~8.5`, unit empty | as stored | Correct: pH has no unit |
| `gold_16` | `20.0` g | as stored | The trailing zero is the source's stated precision |

### 3.4 Points checked and confirmed correct

- All 55 evidence quotes are exact substrings of their cited source lines, including the LaTeX
  formula on line 161.
- All non-empty conditions appear in the source.
- `strict_bound` is on exactly the two strict readings (< 100%, > 100%). GI ≥ 60% is inclusive, as
  written.
- Table row references and units: Table 3's unit comes from its header cell "限量指标 (mg/kg)", and
  the header is cited as evidence.
- Precision and orientation of values are kept: 20.0 g, 1:10 (solid : liquid), 0.5 h.
- The `gold_25` annotation keeps the source spelling 水堇 rather than "correcting" it. This is right
  for a benchmark. For the record, the species normally used in compost GI tests is 水芹 (garden
  cress, *Lepidium sativum*). 水堇 (*Ranunculus sceleratus*) is not a usual test seed, so 水堇 is very
  probably a misprint for 水芹 in the original standard or an OCR error. Readers who use these rows
  should know this.

## 4. Completeness against expert expectation

### 4.1 Gap: the NY 884 pathogen indicators (c100, c101, excluded as X16)

9.3.6: "粪大肠菌群数和蛔虫卵死亡率应达到NY884的要求". The clause names two specific, well-defined,
measurable properties of the finished fertilizer: fecal coliform count (个/g) and roundworm-egg
mortality (%). It takes their limits from a named standard. For anyone assessing compost safety,
these are two of the four headline indicators in 9.3.6, next to GI and the heavy metals. They are
the indicators that show pathogens have been killed.

The run excludes them as delegations to another document. The run also accepts 比能耗 and 发酵周期
(`gold_4`, `gold_5`), where the standard names the property and leaves the value to the equipment
supplier. From an expert's point of view the NY 884 indicators are the *more* determinate of the two
cases. Their limits exist and can be looked up, while the equipment parameters have no limit at all.
Accepting the second case and rejecting the first does not reflect how an expert would rank them.

This is a rules decision (rules 3.0.0, X16), not an annotation error. `extract_metrics` makes the
same decision (candidates v11), so leaving them out does not distort the score today. But if the
benchmark is meant to answer "has the extractor found every quality indicator the standard
requires?", these two should be gold, for example as rows whose value is delegated, tagged with the
cited standard.

Other X16 delegations are different. The effluent clauses (GB/T 31962, GB 16889), odour emissions
(GB 14554) and microbial safety (NY 1109) delegate a whole standard and name no single property.
Excluding those is reasonable from an expert view too.

### 4.2 Judgement calls

| Candidate | Run decision | Expert view |
|---|---|---|
| c35: 餐厨垃圾收运的时间和频次 by agreement (8.1.2) | X2 | **Disputable.** Collection frequency is a named, measurable operating parameter (次/日). Its value is set by contract between the collector and the catering unit. That is structurally the same as 比能耗, whose value is set by the manufacturer, which the run accepts. An expert would treat both the same way, either both value-open metrics or neither. Rules 3.1.0 deliberately chose X2. Under expert judgement the frequency is a borderline +1. The time window (收运时间) is a schedule, not a metric |
| c72: 容积在50立方米以下的农村户用沼气池 (Table 1) | X5 (scope) | **Inconsistent with `gold_31`/`gold_32`.** 50 m³ is a numerical class boundary: digesters below it follow NY/T 90. The run treats it as scope, which is the correct reading of what the clause does. But the run keeps the GI < 100% / > 100% readings, which are also class boundaries, as metrics. Both should be treated the same way. If neither is required, the gold drops to 30; if both are kept, it rises to 33 |
| c134: 500 ml 具密封塞聚乙烯瓶 (B.1.1) | X12 (apparatus) | **Acceptable.** The bottle size affects the headspace during shaking but is not a quantity a lab would report. An expert would not miss it |
| c66: 阳光房单室体积 sized by daily throughput | X17 | **Agree.** This is a design rule with no value, no ratio and no party who must declare one |
| c6: 日产日清 (4.2) | X3 (principle) | **Agree.** It is a slogan under 基本要求. The daily collection rows already capture what it implies |
| Seed species (B.1.2) | stored only as `condition` of `gold_25` | Minor. It is a qualitative test setting. See §3.2 |

I found no number in the document that sets a requirement and is missing from both the rows and the
ledger. The ledger's exclusions of administrative duties, qualitative states (有盖, 密闭, 无臭气) and
permissions (可, 鼓励) all match how a practitioner would read them.

## 5. Precision: rows an expert would question

- **`gold_31`/`gold_32` (GI < 100% phytotoxic, > 100% stimulating).** These sentences explain how to
  read the index. They are not requirements. They also sit awkwardly with the standard's own
  acceptance limit: a fertilizer with GI 60–100% passes 9.3.6 but is called "phytotoxic" by B.2.
  The rows are faithful to the source, but they would rarely be asked for and invite misuse as
  limits. Keeping them is defensible as long as scoring treats them as definitions, not
  requirements. They are already stored with `value_class = definition`.
- **The 15 Annex B settings.** They are numerous relative to the document's 12 product and operating
  requirements. Annex B is marked 规范性附录 (normative), so these are binding method requirements
  and an expert would keep them. A scorer may want to report them separately, so that the 15 method
  settings do not outweigh the fertilizer limits in an overall score.

No row is a false positive in the sense of asserting something the standard does not say.

## 6. Comparison with the claude-opus-5-5 4.0.0 run (`20261007_115911`)

The two runs contain the same 32 assertions, with the same values, comparisons, subjects and
`value_class`. The differences are representational only:

| Aspect | gpt-6.1-sol | claude-opus-5-5 |
|---|---|---|
| Line spans | evidence lines only (`158`) | include the section heading (`157:158`) |
| `gold_17` value/unit | `1：10` / `ratio` | `1:10` / `W/V` (better) |
| `gold_23` value | `0℃～4℃` | `0~4` (better) |
| `condition` on 22, 25, 29 | 每次测定, 水堇或萝卜种子, 每个样品 | empty (better) |
| `condition` on 27, 28 | 黑暗 | 黑暗的培养箱中 |
| `gold_2`/`gold_3` names | generic "收运频次" | stream-specific "易腐垃圾收运频次" (better) |
| `gold_31`/`gold_32` names | identical | distinct (better) |

Either run can serve as the 4.0.0 gold. The claude run has slightly cleaner values and names. The
gpt run has tighter line spans.

## 7. Recommendations

1. **Use this run as a valid 4.0.0 benchmark for record 416.** The values are correct, and the 32
   assertions match an independent run.
2. **When scoring:** accept either `exact` or `lower_bound` for the two daily-collection rows. Treat
   `1：10`/`1:10` and `0℃～4℃`/`0~4` as equal. Do not penalize a prediction that leaves out the
   non-conditions in §3.2.
3. **For a future rules version (not this run):** consider a value-delegated class for named
   properties whose limit is in a cited standard (the NY 884 pair). Apply one consistent rule to
   numerical class boundaries (50 m³ and the GI readings), and to collection frequency left to
   agreement versus parameters the equipment must state.
4. **Data quality note:** check 水堇 against the original PDF. If it is an OCR error for 水芹, fix it
   in the line file before the next run.

## Knowledge-change checklist

- *What changed:* this report only. No benchmark rows, rules or tooling were modified.
- *Docs affected:* none. *Stale:* none.
- *Left undocumented on purpose:* the original PDF was not opened, so the 水堇/水芹 question is
  unresolved.
