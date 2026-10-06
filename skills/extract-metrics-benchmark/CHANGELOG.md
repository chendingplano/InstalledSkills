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

Default when no version is named: the newest released version (currently 1.2.0, which has the 1.0.0
rules); pre-releases are never the default. From now on tooling changes do not create rules versions; 1.1.0 and 1.2.0 remain only
because rows were already saved under those labels.

## Tooling changes

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
