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

Default when no version is named: the newest released version (currently 5.0.0); pre-releases are never the default. From now on tooling changes do not create rules versions; 1.1.0 and 1.2.0 remain only
because rows were already saved under those labels.

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
`metric_statement_kind.go`) are unchanged: kb.metrics never holds the class. ChenWeb pages that show
gold rows will label 4.1.0 A4 rows `unclassified` until the TS mirror learns the class.

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
