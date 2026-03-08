# Metric Records & Metric Package — DB Schema

## PostgreSQL Schema

```sql
CREATE TABLE metric_packages (
    id            SERIAL PRIMARY KEY,
    doc_name      TEXT NOT NULL,
    doc_no        TEXT,
    page          INTEGER,
    bounding_box  INTEGER[],        -- [x1, y1, x2, y2] in PDF points
    table_caption TEXT,
    context       TEXT,             -- surrounding text from the document
    metric_names  TEXT[],           -- array of metric_name values from metric_records
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE metric_records (
    id            SERIAL PRIMARY KEY,
    package_id    INTEGER NOT NULL REFERENCES metric_packages(id),
    doc_name      TEXT NOT NULL,
    doc_no        TEXT,
    page          INTEGER,
    bounding_box  INTEGER[],        -- bounding box of this specific row/cell
    table_caption TEXT,
    context       TEXT,             -- same surrounding text as in the package
    metric_name   TEXT UNIQUE NOT NULL,
    metric_values TEXT NOT NULL,    -- the raw measurement value(s), e.g. "9500×2000×500"
    measurement   TEXT,             -- what is being measured, e.g. "内径×宽度×厚度"
    unit          TEXT,             -- unit of measurement, e.g. "毫米", "MPa", "°C"
    category      TEXT,             -- grouping context, e.g. "公路隧道", "铁路隧道"
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

## Field Reference

| Field | Table | Type | Notes |
|---|---|---|---|
| `doc_name` | both | TEXT | Full document title |
| `doc_no` | both | TEXT | Standard/document number (e.g. `GB/T 22082—2024`) |
| `page` | both | INTEGER | Page number where table appears |
| `bounding_box` | both | INTEGER[] | `[x1, y1, x2, y2]` in PDF coordinate points |
| `table_caption` | both | TEXT | Table label, e.g. `表1` |
| `context` | both | TEXT | Surrounding paragraphs that define the table's purpose |
| `metric_names` | package | TEXT[] | List of all `metric_name` values belonging to this package |
| `package_id` | record | INTEGER | FK to `metric_packages.id` |
| `metric_name` | record | TEXT | Unique slug, format: `{slug}_{sequence:03d}` |
| `metric_values` | record | TEXT | Raw value string from the table cell |
| `measurement` | record | TEXT | Physical property being measured |
| `unit` | record | TEXT | Unit of measurement; `null` if not specified |
| `category` | record | TEXT | Row grouping context from a category column; `null` if none |

## JSON Output Format

```json
{
  "metric_package": {
    "doc_name": "预制混凝土衬砌管片标准",
    "doc_no": "GB/T 22082—2024",
    "page": 10,
    "bounding_box": [463, 211, 710, 239],
    "table_caption": "表1",
    "context": "4.2 规格\n管片常用规格见表1。",
    "metric_names": ["concrete_segment_001", "concrete_segment_002", "..."]
  },
  "metric_records": [
    {
      "doc_name": "预制混凝土衬砌管片标准",
      "doc_no": "GB/T 22082—2024",
      "page": 10,
      "bounding_box": [463, 211, 710, 239],
      "table_caption": "表1",
      "context": "4.2 规格\n管片常用规格见表1。",
      "metric_name": "concrete_segment_001",
      "metric_values": "9500×2000×500",
      "measurement": "内径×宽度×厚度",
      "unit": "毫米",
      "category": "公路隧道"
    },
    {
      "doc_name": "预制混凝土衬砌管片标准",
      "doc_no": "GB/T 22082—2024",
      "page": 10,
      "bounding_box": [463, 211, 710, 239],
      "table_caption": "表1",
      "context": "4.2 规格\n管片常用规格见表1。",
      "metric_name": "concrete_segment_002",
      "metric_values": "10300×2000×500",
      "measurement": "内径×宽度×厚度",
      "unit": "毫米",
      "category": "公路隧道"
    }
  ]
}
```

## Notes

- `bounding_box` on a Metric Record may be the same as the package bounding box if per-row coordinates are unavailable.
- `context` is intentionally duplicated across all records in a package for query convenience (each record is self-contained).
- Units are often stated in the table caption or in a footnote, not in individual cells. Extract them from wherever they appear.
- When a category spans multiple rows (via `rowspan`), apply the same category value to all rows under that span.
