# Benchmark payload and storage

## Connection and source preparation

Run from the workspace root and use the configured ChenWeb project database.

For `psql`, provide credentials through `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
and `PGSSLMODE` in the environment. ChenWeb's `.env` (and `mise env` from `ChenWeb/`) uses names
such as `PG_USER_NAME`, `PG_PASSWORD` and `PG_DB_NAME`; map those privately. Never print `.env`,
put passwords or DSNs in process arguments, or commit connection settings.

For document ID 123 (use fresh paths per invocation; `prepare` refuses to overwrite its payload):

```bash
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=123 \
  -o /tmp/prd-123-record.json <<'SQL'
SELECT json_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name,
 'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata)
FROM kb.inputs WHERE id = :'record_id'::bigint;
SQL

python3 .agents/skills/extract-products-benchmark/scripts/benchmark_io.py prepare \
  --record /tmp/prd-123-record.json --output /tmp/prd-123-benchmark.json \
  --skill-version <released version; omit for the newest> \
  --model-name <invoking model identity> > /tmp/prd-123-source.json
```

- An empty query result means an unknown ID.
- `DATA_HOME_DIR` is required for relative result paths.
- The source stdout lists every validated line; a table line also has `rows`, its rows by ID
  (`"r3": "3 | 垃圾桶"`). Read it in bounded portions.

## Reviewed JSON envelope

Populate the prepared payload. Keep its record ID, run ID, skill name and version, rules hash,
model name, source path and hash. This abbreviated example (a Chinese standard) shows the shape:

```json
{
  "record_id": 123,
  "run_id": "<yyyymmdd_hhmmss from prepare>",
  "skill_name": "extract-products-benchmark",
  "skill_version": "<version from prepare>",
  "rules_sha256": "<from prepare>",
  "model_name": "<from prepare --model-name>",
  "source_filename": "<resolved working .txt path>",
  "source_sha256": "<from prepare>",
  "language": "zh",
  "completeness_review": "All lines read; head-noun and waste-word search reconciled.",
  "correctness_review": "Checked names, types, relations, obligation, text. Consistency: …",
  "limitations": [],
  "coverage": [{"source_line_spans": ["1-60"], "reason": "Cover, foreword, scope, clause 5."}],
  "candidates": [
    {"candidate_id": "c1", "source_line_spans": ["89"], "decision": "accepted", "rule_id": "A1",
     "text": "垃圾分类收集容器", "product_keys": ["123_gp_1"], "reason": "A movable container."},
    {"candidate_id": "c2", "source_line_spans": ["50"], "decision": "excluded", "rule_id": "X1",
     "text": "垃圾转运站", "product_keys": [], "reason": "A station built at a site."}
  ],
  "products": [
    {
      "product_rel_id": "123_gprd_1", "product_key": "123_gp_1", "section": "7.1 投放要求",
      "product_name": "垃圾分类收集容器", "product_name_en": "Sorted-waste collection container",
      "canonical_name": "垃圾分类收集容器", "canonical_name_en": "Sorted-waste collection container",
      "product_type": "equipment", "relation_type": "design_requirement",
      "relation_summary": "文件要求垃圾分类收集容器有盖。", "relation_summary_en": "",
      "evidence_lines": ["89"], "evidence_quote": "垃圾分类收集容器应有盖",
      "obligation_level": "mandatory", "requirement_text": "垃圾分类收集容器应有盖",
      "requirement_text_en": "", "conditions": [], "exceptions": [], "parameters": [],
      "related_products": [], "responsible_actor": "", "confidence": 0.95, "rule_id": "R1",
      "annotation_notes": "Optional interpretation notes; saved in ext_info."
    }
  ]
}
```

**IDs and links.**
- The benchmark-local IDs are `<record_id>_gprd_<seqno>` (one per row) and `<record_id>_gp_<seqno>`
  (one per product). They are not production IDs (`<rec>_prd_<n>`).
- Candidate IDs are unique within a run.
- Accepted candidates link their products (`product_keys`; a coordination can link several),
  excluded candidates link none, and duplicate candidates link the retained product. Every
  product key needs an accepted candidate.
- Uncertain decisions or a nonempty `limitations` block saving.

| Field | Contract |
|---|---|
| `section` | Heading of the section of the first evidence line as written; `""` before the first heading |
| `product_name` | The product noun phrase as written (rules §2.4); must occur in the cited lines, whitespace-insensitive |
| `name_expanded`, `name_source` | Optional: `true` and the exact source phrase for an expanded conjunct of an elided coordination; saved in `ext_info` |
| `canonical_name` | Normalized base name (rules §2.4) |
| `product_name_en`, `canonical_name_en` | Required for non-English documents, null otherwise |
| `product_type` | `specific_product product_class component material software system equipment consumable packaging other` |
| `relation_type` | The 21 `kb.products` values; `rule_id` must be its R rule (R1–R8) |
| `relation_summary`, `relation_summary_en` | One sentence in the document's language; `_en` optional |
| `evidence_lines` | Production spans `N`, `N-M`, `N#rK`, `N#hK`. A table line is cited by its rows only, with IDs as `ParseTableGrid` assigns them |
| `evidence_quote` | Exact substring (whitespace-insensitive) of one cited line, or of one cited row's cells |
| `obligation_level` | `mandatory recommended permitted prohibited conditional descriptive` (never `unknown`) |
| `requirement_text`, `requirement_text_en` | As written; ` … ` joins parts; each part must occur in the cited lines; `""` exactly for descriptive rows. `_en` optional |
| `conditions`, `exceptions` | Arrays of nonempty strings |
| `parameters` | `[{"name", "value", "unit"}]`; `unit` a nonempty string or null |
| `related_products` | `[{"product_name", "relationship"}]`, nonempty exactly for `component_of contains_product compatible_with replacement_or_alternative` |
| `responsible_actor` | Party named as obliged; `""` when none, and always for descriptive rows |
| `confidence` | Finite number 0–1 |
| `annotation_notes` | Optional string, saved in `ext_info` |
| candidate `text` | The candidate noun phrase as source text of its spans (same span forms as evidence) |

**Run row.** The run row stores `language`, `title`/`doc_no` (from `doc_metadata`, falling back
to the top-level columns), `coverage`, `candidates`, both reviews, `rules_sha256` and
`reviewed_at`. Per-row `ext_info` (schema `1`) holds `candidate_ids`, `annotation_notes`, and
`name_expanded`/`name_source` for expanded names.

## Table provisioning and save

**Schema.** `ChenWeb/project_migrations/20261108000101_create_testbed_products.sql`, applied by
the Goose project track (`ChenWeb/project_migrations`, version table `project_db_migration`) at
server start-up or through the db-migration skill. It creates:

- `testbed.product_benchmark_runs`: one row per run, primary key (`skill_name`, `skill_version`,
  `model_name`, `run_id`);
- `testbed.products`: the gold rows, unique per run key and `product_rel_id`, and per run key,
  `product_key` and `relation_type`, with a foreign key to the run;
- `testbed.products_dropped`: excluded and duplicate candidates. `drop_reason` is the candidate's
  `rule_id`; `candidate_data` is the complete ledger entry.

Inspect the tables before saving:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'testbed' AND table_name IN ('product_benchmark_runs', 'products', 'products_dropped')
ORDER BY table_name, ordinal_position;
```

Validate and save:

```bash
python3 .agents/skills/extract-products-benchmark/scripts/benchmark_io.py validate \
  --record /tmp/prd-123-record.json --payload /tmp/prd-123-benchmark.json
python3 .agents/skills/extract-products-benchmark/scripts/benchmark_io.py save \
  --record /tmp/prd-123-record.json --payload /tmp/prd-123-benchmark.json
```

The helper sends fixed-identifier, quoted JSON SQL through `psql` stdin with `ON_ERROR_STOP=1`. It
writes the run row first, then the gold rows and the dropped candidates, in one transaction. An
advisory lock on the run key and a guard abort the save if the run already exists.

Read back, substituting the run key:

```sql
SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.id), '[]'::jsonb)
FROM testbed.products p
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-products-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';

SELECT to_jsonb(r) FROM testbed.product_benchmark_runs r
WHERE run_id = :'run_id' AND skill_name = 'extract-products-benchmark'
  AND skill_version = :'skill_version' AND model_name = :'model_name';

SELECT COALESCE(jsonb_agg(d.candidate_data ORDER BY d.candidate_id), '[]'::jsonb)
FROM testbed.products_dropped d
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-products-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';
```

**Compare** every substantive field with the validated JSON. Only database-managed IDs and
timestamps may differ, and `confidence` may deserialize as a float. If DB access is unavailable,
keep the validated JSON and report persistence pending; artifacts alone are not a saved
benchmark.
