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

Default when no version is named: the newest released version (currently 2.0.0); pre-releases are never the default. From now on tooling changes do not create rules versions; 1.1.0 and 1.2.0 remain only
because rows were already saved under those labels.

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
