# Metric Extraction Specification

## Inputs

- `input_filename`: source file name to analyze.
- `record_id`: integer identifier from `kb.inputs.id`.

Input file format is line-based. Each line contains:

1. line number (integer)
2. page number (integer)
3. line type (single token, for example `title`, `list-item`)
4. content text
5. coordinate array

Example:

```text
65 6 list-item 2.0.7 integrated bathroom with shower, sink [90,246.953,505.2,284.484]
```

## What Counts as a Metric

Treat an item as a metric when it defines or strongly implies measurable evaluation, such as:

- quantity, value, ratio, score, rate, percentage, count, duration, threshold, limit, index, or formula
- observable/testable/monitorable/reportable indicator
- criterion with numeric bounds or target values
- named measure in a table with unit, target, formula, threshold, frequency, baseline, benchmark, or calculation notes

Likely metric examples:

- response time
- uptime percentage
- defect density
- mean time to recovery
- packet loss rate
- compliance score
- false positive rate
- number of incidents per month
- precision, recall, F1
- maximum latency <= 200 ms
- CPU utilization %

## What Is Not a Metric

Do not extract:

- non-measurable goals or qualities
- ordinary reference tables (roles, abbreviations, ownership, lists of names)
- units alone
- formulas alone unless tied to a named metric
- methods/procedures without explicit measured subject

## Table Rules

1. Decide first whether the table is metric-related.
2. Treat headers like `Metric`, `Measure`, `Indicator`, `KPI`, `Threshold`, `Target`, `Unit`, `Formula`, `Frequency`, `Baseline`, `Benchmark`, `Calculation`, `Acceptance Criteria` as strong signals.
3. Treat tables dominated by IDs, names, categories, references, or ownership as weak signals.
4. Extract only metric rows from mixed tables.
5. Use heading/caption/surrounding prose for interpretation.

## Required Output Fields

For each extracted metric:

```text
metric_name
source_line_spans
subject
desc
context
keywords
location_type
unit
formula_or_definition
threshold_or_target
measurement_frequency
confidence
is_explicit_metric
table_name_or_section
reasoning_tags
```

Constraints:

- `source_line_spans` should point to exact supporting lines (for example `[10-12, 15, 20-22]`).
- `location_type` is one of:
  `sentence | bullet | table_row | table_cell | heading_context | mixed`.
- `confidence` is in `[0,1]`.
- `subject` must be fully descriptive with context.
- `reasoning_tags` should include concise evidence tags (for example `named_metric`, `has_unit`, `has_threshold`, `formula_present`, `inferred_from_table`).
- Preserve source wording for evidence fields; do not hallucinate.

## Output Language

Use the same language as the source document.

## Storage Contract (`kb.metrics`)

Generate one `ExtractInvokeID` per run with format `yyyymmdd-hhmmss`.

Store each metric record with:

- `input_record_id` = `record_id`
- `extract_id` = `ExtractInvokeID`
- `input_filename`
- `metric_name`
- `source_line_spans`
- `metric_subject` (from `subject`)
- `metric_desc` (from `desc`)
- `metric_context` (from `context`)
- `metric_keywords` (from `keywords`)
- `location_type`
- `metric_unit` (from `unit`)
- `formula_or_definition`
- `threshold_or_target`
- `measurement_frequency`
- `confidence`
- `is_explicit_metric`
- `reasoning_tags`
- `ext_info` (optional JSON with additional evidence/notes)

`id`, `created_at`, and `modified_at` are managed by the database.

## Uncertainty Handling

If metric status is unclear, do not force extraction into the main list. Return those items in a separate `uncertain_metrics` section for human review.
