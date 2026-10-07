# Benchmark payload and storage

## Connection and source preparation

Run from the workspace root. Use the configured ChenWeb project database, not an assumed database name. Prefer existing configured tooling; for `psql`, provide credentials through `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` and `PGSSLMODE` in the environment. ChenWeb's `.env` uses names including `PG_USER_NAME`, `PG_PASSWORD` and `PG_DB_NAME`; map those privately. Never print `.env`, put passwords/DSNs in process arguments, or commit connection settings.

For document ID 123, after validating that input is a positive integer:

```bash
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=123 \
  -o /tmp/metrics-123-record.json <<'SQL'
SELECT json_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name,
 'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata)
FROM kb.inputs WHERE id = :'record_id'::bigint;
SQL

python3 .agents/skills/extract-metrics-benchmark/scripts/benchmark_io.py prepare \
  --record /tmp/metrics-123-record.json --output /tmp/metrics-123-benchmark.json \
  --skill-version <released version; omit for the newest> \
  --model-name <invoking model identity resolved from the active runtime/session> > /tmp/metrics-123-source.json
```

A document invocation includes saving and read-back unless the user explicitly requests draft-only/no-save. Resolve `model_name` from the invoking model’s runtime or active-session metadata as described in SKILL.md; do not ask the user to supply it. Prefer the exact model ID; if only a runtime label is exposed, record that label and explain it in `annotation_notes`.

Use fresh artifact paths per invocation to preserve existing audits. `prepare` refuses to overwrite its payload. Its stdout includes all validated source records; read that file in bounded portions to avoid truncation. Empty query results mean an unknown ID. `DATA_HOME_DIR` is required for relative result paths. The parser tolerates blank lines/CRLF, validates seven TAB fields and rejects duplicate/non-increasing IDs. Gaps remain visible rather than silently renumbered.

## Reviewed JSON envelope

Populate the prepared payload; retain its ID/path/hash/run ID/skill name/skill version/model name. This abbreviated pressure example illustrates the shape, not a universal extraction result:

```json
{
  "record_id": 123,
  "benchmark_run_id": "<yyyymmdd_hhmmss from prepare>",
  "skill_name": "extract-metrics-benchmark",
  "skill_version": "<version from prepare>",
  "rules_sha256": "<SHA-256 of that version's rules file, from prepare>",
  "model_name": "<from prepare --model-name>",
  "source_filename": "<resolved working .txt path>",
  "source_sha256": "<SHA-256 from prepare>",
  "language": "en",
  "completeness_review": "All sections re-read; measured-property candidates reconciled.",
  "correctness_review": "Checked subject, lower-bound operator, value, unit and source quotes.",
  "limitations": [],
  "coverage": [{"source_line_spans": ["1:2"], "reason": "Heading and pressure clause reviewed."}],
  "candidates": [{"candidate_id": "c1", "source_line_spans": ["2"], "decision": "accepted",
                  "metric_ids": ["123_gold_1"], "rule_id": "A1",
                  "reason": "Explicit minimum pressure."}],
  "metrics": [{
    "metric_id": "123_gold_1",
    "metric_name": "Outlet pressure",
    "metric_subject": "Pump",
    "metric_desc": "Minimum pump outlet pressure",
    "metric_context": "Pump requirements",
    "metric_keywords": ["pressure", "pump"],
    "source_line_spans": ["1:2"],
    "source_table_rows": [],
    "location_type": "sentence",
    "metric_unit": "MPa",
    "metric_value": "0.5",
    "value_data_type": "number",
    "value_range_type": "lower_bound",
    "value_class": "requirement",
    "value_min": null,
    "value_max": null,
    "condition": "",
    "formula_or_definition": "",
    "threshold_or_target": "Pressure shall be ≥ 0.5 MPa.",
    "measurement_frequency": "",
    "metric_categories": ["pressure"],
    "confidence": 1.0,
    "is_explicit_metric": true,
    "table_name_or_section": "Pump requirements",
    "reasoning_tags": ["has_threshold", "has_unit"],
    "evidence": [{"line": 2, "quote": "Pressure shall be ≥ 0.5 MPa."}]
  }]
}
```

Benchmark-local `metric_id` convention: `<record_id>_gold_<seqno>`; not a production metric/candidate ID. Ledger IDs are unique within a review. Accepted candidates link final metrics; excluded candidates link none; duplicate candidates link retained metrics. Uncertain decisions or nonempty `limitations` block saving.

**Rules 2.0.0 and later.** Each candidate carries `rule_id`, one of the bold rule IDs in that version's rules file: an `A` rule for `accepted`, an `X` rule for `excluded`, `D1` for `duplicate`. `validate` reads the IDs from the rules file. Payloads for rules 1.x need no `rule_id` and keep their original checks.

Use **storage names** (`metric_subject`, `metric_desc`, `metric_context`, `metric_keywords`, `metric_unit`), not enrichment aliases (`subject`, `desc`, `context`, `keywords`, `unit`). Empty source-absent text is `""`; absent endpoints are null. Arrays remain JSON arrays.

| Field | Contract |
|---|---|
| `location_type` | `sentence`, `bullet`, `table_row`, `table_cell`, `heading_context`, `mixed` |
| `value_range_type` | `lower_bound`, `upper_bound`, `exact`, `range`, `qualitative`, `limit_absent` |
| `value_class` | `observation`, `requirement`, `target`, `reference`, `design_capability`, `definition`. From rules 2.0.0, `definition` is only for metric/formula definitions and needs `formula_or_definition` |
| `is_explicit_metric` | True for numeric lower/upper/exact/range; false for qualitative/limit_absent |
| `metric_value`, `metric_unit` | Both empty for qualitative/limit_absent; preserve source text for numeric values |
| `metric_value` (rules ≥ 2.0.0) | The bare number, never a comparator (`100`, not `<100`); the comparator is `value_range_type` plus `threshold_or_target` |
| `reasoning_tags` (rules ≥ 2.0.0) | `strict_bound` marks a strict `lower_bound`/`upper_bound` (> or <); `test_condition` marks a numeric test-method setting (rule A6) and is not allowed on qualitative/limit_absent rows |
| `reasoning_tags` (rules ≥ 2.1.0) | Exactly one `kind:<kind>`: `requirement_with_criterion`, `requirement_value_open`, `inspection_requirement`, `delegated_requirement`, `test_parameter`, `metric_definition`, `metric_value`, `observation`. `validate` derives the kind from the row (`statement_kind` in `benchmark_io.py`, mirroring ChenWeb `web/src/lib/metric-statement-kind.ts`) and refuses a mismatch. `interpretation_bound` marks an interpretation cut-off: `value_class = definition`, `lower_bound`/`upper_bound`. `cited_doc:<identifier>` has a space before the number (`cited_doc:NY 884`); `value_class = reference` requires `external_reference` |
| `value_data_type` | Describe the actual stored value representation (for example `number`); empty for qualitative/limit_absent rows with no scalar value |
| `value_min`, `value_max` | Finite JSON numbers for range only, lower ≤ upper |
| `condition` | Source-stated applicability; empty if absent |
| `source_line_spans` | Original `N`/`N:M` strings; no page numbers or row suffixes |
| `source_table_rows` | `[{"line": 116, "rows": ["r1"]}]`; optional verified `row_hash` map in production form |
| `confidence` | Finite number 0–1; never substitutes for review |
| `evidence` | Exact source substrings, not paraphrases; cited line inside metric spans |
| `metric_categories` | One or more meaningful keys, never hierarchy paths |
| `annotation_notes` | Optional source-interpretation, tolerance/comparator, table-context or category rationale; saved in `ext_info` |

For non-English sources add applicable `metric_name_en`, `metric_subject_en`, `metric_desc_en`, `metric_context_en`, `metric_keywords_en`, `metric_unit_en`, `value_class_en`. English rows store them null. The helper supplies document/run IDs, filename/hash, `skill_name` (from `SKILL.md` frontmatter `name`), `skill_version` and `rules_sha256` (from `prepare --skill-version`, checked against `rules/versions.json`; validation fails for an unknown version or an edited released rules file; the hash is kept in `ext_info.rules_sha256`), `model_name` (from `prepare --model-name`; required) and `ext_info` (language, schema version `2`, evidence, ledgers and reviews). Title/doc number use `doc_metadata` with top-level fallback. It records only the model ID it is given and generates no prompt claims or production event IDs.

## Table provisioning and save

Committed schema: `ChenWeb/project_migrations/20261006000001_create_testbed_metrics.sql`, plus `20261006000002_add_skill_version_to_testbed_metrics.sql` (`skill_version TEXT NOT NULL`; rows saved before versioning were backfilled as `1.0.0`), plus `20261006000003_add_skill_and_model_name_to_testbed_metrics.sql` (`skill_name`, `model_name`, both `TEXT NOT NULL`; run `22aa157c` backfilled as `extract-metrics-benchmark` / `gpt-6.1-sol`). Startup runs project migrations through `server/cmd/config/config.go`. Use the Goose project track, `ChenWeb/project_migrations`, and existing `project_db_migration` version table. Follow db-migration skill guidance for credentials/execution; never test rollback against valuable benchmark data. The schema excludes production search indexes/triggers/category side effects.

Inspect before saving:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'testbed' AND table_name = 'metrics'
ORDER BY ordinal_position;
```

Validate and save the reviewed snapshot:

```bash
python3 .agents/skills/extract-metrics-benchmark/scripts/benchmark_io.py validate \
  --record /tmp/metrics-123-record.json --payload /tmp/metrics-123-benchmark.json
python3 .agents/skills/extract-metrics-benchmark/scripts/benchmark_io.py save \
  --record /tmp/metrics-123-record.json --payload /tmp/metrics-123-benchmark.json
```

The helper sends fixed-identifier, quoted JSON SQL through `psql` stdin with `ON_ERROR_STOP=1`. All rows insert atomically. A run key (`skill_name`, `skill_version`, `model_name`, `benchmark_run_id`) is used once: the transaction takes an advisory lock on the key and aborts if any row already carries it, and the table enforces `UNIQUE (skill_name, skill_version, model_name, benchmark_run_id, metric_id)` plus the `yyyymmdd_hhmmss` format. Fresh runs append snapshots; nothing is replaced. After an ambiguous connection failure, query by the run key before retrying; a refused save of an already-saved key means the run is already stored.

Read back, substituting the prepared run key:

```bash
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=123 -v run_id='<yyyymmdd_hhmmss>' \
  -v skill_version='<version>' -v model_name='<model>' \
  -o /tmp/metrics-123-readback.json <<'SQL'
SELECT COALESCE(jsonb_agg(to_jsonb(m) ORDER BY m.metric_id), '[]'::jsonb)
FROM testbed.metrics m
WHERE input_record_id = :'record_id'::bigint AND benchmark_run_id = :'run_id'
  AND skill_name = 'extract-metrics-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';
SQL
```

Compare all substantive fields/excerpts/hash to validated JSON, allowing only database-managed ID/time fields and helper-generated audit timestamps. Numeric endpoints may deserialize as floats. Report the explicit evaluation run ID; never count multiple snapshots together. An empty verified document retains local review JSON but creates no rows. If DB access is unavailable, retain validated JSON and report persistence pending; artifacts alone are not a saved benchmark.
