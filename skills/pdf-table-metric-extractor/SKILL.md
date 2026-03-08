---
name: pdf-table-metric-extractor
description: "Analyze tables extracted from PDF engineering or standards documents to identify whether the table defines quantifiable metrics (measurements, specifications, dimensional data, performance limits, tolerance values, etc.), extract each metric into a Metric Record, and group all records into a Metric Package for relational database storage. Use when given an HTML table from a PDF along with surrounding context text and document metadata (DocName, DocNo, Page, BoundingBox, TableCaption), and the task is to extract structured metric data. Applies to Chinese and English engineering standards, technical specifications, product standards, and similar documents."
---

# PDF Table Metric Extractor

## Step 1: Determine if the table defines metrics

A table defines metrics if it contains **quantifiable engineering measurements or specifications** — values that characterize physical, operational, or performance properties of a system, product, or environment.

**Tables that define metrics (extract):**
- Dimensional specifications (e.g., inner diameter × width × thickness per product type)
- Performance limits (e.g., max/min temperature, humidity, load per environment class)
- Material property tables (e.g., strength, density, conductivity per grade)
- Tolerance, allowance, or rating tables with numeric values

**Tables that do NOT define metrics (skip):**
- Tables of contents, indexes, or section references
- Classification/naming tables where all values are labels or descriptions
- Organizational, administrative, or process tables
- Tables where every cell is text with no measurable quantity

If the table does not define metrics, output:
```json
{"defines_metrics": false, "reason": "<brief explanation>"}
```
and stop.

## Step 2: Identify the metric structure

From the table and surrounding context, determine:

- **Measurement** — what physical property is being measured (e.g., `内径×宽度×厚度`, `temperature range`, `compressive strength`)
- **Unit** — look in the table caption, header row, footnotes, or surrounding text (e.g., `单位为毫米`, `MPa`, `°C`); set to `null` if not found
- **Category** — any grouping column that contextualizes each row (e.g., `工程类别`: 公路隧道, 铁路隧道, 水工隧道)

## Step 3: Generate MetricName for each row

Each data row becomes one Metric Record with a unique `metric_name`. Format:

```
{meaningful_english_slug}_{sequence:03d}
```

- Derive the slug from the document subject + table content (e.g., `concrete_segment`, `highway_tunnel_dim`, `env_temp_limit`)
- Lowercase, underscores only, no special characters
- Sequence starts at `001` and increments across all rows in the table

Example: `concrete_segment_001`, `concrete_segment_002`, ...

## Step 4: Build Metric Records and Metric Package

See [references/schema.md](references/schema.md) for:
- Field definitions and data types for both `metric_records` and `metric_packages`
- Full PostgreSQL schema (CREATE TABLE statements)
- A complete worked example from a real standards document

## Step 5: Output

Produce a JSON object with two keys:

```json
{
  "metric_package": { ... },
  "metric_records": [ { ... }, { ... } ]
}
```

All field names use `snake_case`. Full field list is in [references/schema.md](references/schema.md).
