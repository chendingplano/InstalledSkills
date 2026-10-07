---
name: document-metric-extractor
description: Extract and normalize quantitative metrics from line-based document extracts, including prose, bullets, and tables, with conservative precision-first classification and structured output for storage in `kb.metrics`. Use when the user provides an input filename plus a `record_id` from `kb.inputs.id`, and requests identifying measurable indicators, thresholds, targets, rates, scores, or KPI-like values from technical, compliance, standards, or requirements documents.
disable-model-invocation: true
---

# Document Metric Extractor

Extract only genuine measurable metrics. Prioritize precision over recall.

## Workflow

1. Confirm required inputs:
   - `input_filename`
   - `record_id` (integer from `kb.inputs.id`)
2. Parse each line into:
   - line number
   - page number
   - line type
   - content
   - coordinate array
3. Scan the full document and identify candidate metrics in:
   - prose sentences
   - bullet/list items
   - table rows and cells
   - nearby headings and captions
4. Classify each candidate using strict metric criteria:
   - Keep measurable quantities, rates, scores, thresholds, targets, limits, formulas, or explicitly monitored values.
   - Reject concepts, principles, roles, references, and non-measurable statements.
   - Treat tables as mixed-quality sources; extract only metric-like rows.
5. Build structured metric records using the schema in `references/extraction-spec.md`.
6. Assign confidence (`0.0`-`1.0`) and set `is_explicit_metric`:
   - `true` for clearly stated metric definitions.
   - `false` only when strongly supported by context.
7. Produce `ExtractInvokeID` formatted as `yyyymmdd-hhmmss`.
8. Persist each metric into `kb.metrics` with:
   - `input_record_id = record_id`
   - `extract_id = ExtractInvokeID`
   - `input_filename = input_filename`
9. If direct database write is unavailable, return:
   - complete metric JSON payloads
   - corresponding SQL `INSERT` statements
10. Add an `uncertain_metrics` section for borderline items instead of over-extracting.

## Core Decision Rules

- Prefer explicit evidence over inference.
- Require measurable meaning, not just technical terminology.
- Treat unit/threshold/formula/target as strong evidence.
- Preserve exact supporting evidence in `source_line_spans` and/or quoted excerpt.
- Do not hallucinate units, thresholds, formulas, or names.
- Do not merge distinct metrics unless the source clearly merges them.
- Use output language that matches the input document language.

## Table Handling

1. Decide whether a table is metric-oriented before extracting.
2. Boost confidence when headers include terms like `Metric`, `KPI`, `Threshold`, `Target`, `Unit`, `Formula`, `Frequency`, `Acceptance Criteria`.
3. Lower confidence when rows are mostly names, IDs, categories, ownership, references, or narrative notes.
4. Extract only metric rows from mixed tables.
5. Use section title, heading, and caption context to disambiguate row meaning.

## Output Contract

- Emit metric objects exactly as defined in `references/extraction-spec.md`.
- Map each object to `kb.metrics` storage fields.
- Include additional details in `ext_info` JSON when useful (e.g., source excerpts, parser hints, ambiguity notes).
- Keep extraction conservative; false positives are worse than misses.

## Reference

- Read [references/extraction-spec.md](references/extraction-spec.md) for:
  - full metric definition criteria
  - non-metric exclusions
  - required output fields
  - storage mapping to `kb.metrics`
