# Benchmark payload and storage

## Connection and source preparation

Run from the workspace root. Use the configured ChenWeb project database. For `psql`, provide credentials through `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` and `PGSSLMODE` in the environment. ChenWeb's `.env` uses names including `PG_USER_NAME`, `PG_PASSWORD` and `PG_DB_NAME`; map those privately. Never print `.env`, put passwords/DSNs in process arguments, or commit connection settings.

For document ID 123 (use fresh paths per invocation; `prepare` refuses to overwrite its payload):

```bash
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=123 \
  -o /tmp/refs-123-record.json <<'SQL'
SELECT json_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name,
 'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata)
FROM kb.inputs WHERE id = :'record_id'::bigint;
SQL

python3 .agents/skills/extract-references-benchmark/scripts/benchmark_io.py prepare \
  --record /tmp/refs-123-record.json --output /tmp/refs-123-benchmark.json \
  --skill-version <released version; omit for the newest> \
  --model-name <invoking model identity> > /tmp/refs-123-source.json
```

Empty query results mean an unknown ID. `DATA_HOME_DIR` is required for relative result paths. The source stdout lists every validated line; read it in bounded portions.

## Reviewed JSON envelope

Populate the prepared payload; keep its record ID, run ID, skill name/version, rules hash, model name, source path and hash. This abbreviated example (a Chinese standard with a normative references list) illustrates the shape:

```json
{
  "record_id": 123,
  "run_id": "<yyyymmdd_hhmmss from prepare>",
  "skill_name": "extract-references-benchmark",
  "skill_version": "<version from prepare>",
  "rules_sha256": "<from prepare>",
  "model_name": "<from prepare --model-name>",
  "source_filename": "<resolved working .txt path>",
  "source_sha256": "<from prepare>",
  "language": "zh",
  "document_identifier": "GB/T 46121-2025",
  "completeness_review": "All lines read; second-pass search for prefixes, 《》, 表/附录 pointers reconciled.",
  "correctness_review": "Checked labels, identifiers, content tests. Consistency: …",
  "limitations": [],
  "coverage": [{"source_line_spans": ["1:60"], "reason": "Cover, foreword, scope, normative references, clause 5."}],
  "candidates": [
    {"candidate_id": "c1", "source_line_spans": ["12"], "decision": "accepted", "rule_id": "A2",
     "cited_raw": "GB 7959", "ref_ids": ["123_gref_1"], "reason": "Entry of the 规范性引用文件 list."},
    {"candidate_id": "c2", "source_line_spans": ["40"], "decision": "accepted", "rule_id": "A1",
     "cited_raw": "GB 7959", "ref_ids": ["123_gref_2"], "reason": "Takes the limit of one named quantity."},
    {"candidate_id": "c3", "source_line_spans": ["2"], "decision": "excluded", "rule_id": "X2",
     "cited_raw": "GB/T 46121—2025", "ref_ids": [], "reason": "The document's own number on the cover."}
  ],
  "references": [
    {
      "ref_id": "123_gref_1", "section": "2 规范性引用文件",
      "source_line_spans": ["12"], "source_table_rows": [],
      "evidence": [{"line": 12, "quote": "GB 7959 粪便无害化卫生要求"}],
      "ref_form": "listed", "list_kind": "normative", "list_label": "", "list_entry_ref_id": "",
      "normativity": "normative", "in_requirement": false, "list_mismatch": "",
      "mechanism": "standard_number", "cited_raw": "GB 7959",
      "identifiers": [{"kind": "standard", "value": "GB 7959"}],
      "target_type": "standard", "target_subtype": "national_standard", "target_subtype_label": "",
      "target_title": "粪便无害化卫生要求", "target_version": "",
      "relationships": ["references"], "target_scope": "document", "target_locator": "",
      "target_content": "general",
      "metric_name": "", "metric_name_en": null, "metric_subject": "", "metric_subject_en": null,
      "condition": "", "internal": false, "confidence": 1.0
    },
    {
      "ref_id": "123_gref_2", "section": "5.3 卫生要求",
      "source_line_spans": ["40"], "source_table_rows": [],
      "evidence": [{"line": 40, "quote": "粪大肠菌群数应符合GB 7959的要求"}],
      "ref_form": "in_text", "list_kind": "", "list_label": "", "list_entry_ref_id": "123_gref_1",
      "normativity": "normative", "in_requirement": true, "list_mismatch": "",
      "mechanism": "standard_number", "cited_raw": "GB 7959",
      "identifiers": [{"kind": "standard", "value": "GB 7959"}],
      "target_type": "standard", "target_subtype": "national_standard", "target_subtype_label": "",
      "target_title": "", "target_version": "",
      "relationships": ["requires"], "target_scope": "data_element", "target_locator": "",
      "target_content": "criterion",
      "metric_name": "粪大肠菌群数", "metric_name_en": "Faecal coliform count",
      "metric_subject": "堆肥产品", "metric_subject_en": "Compost product",
      "condition": "", "internal": false, "confidence": 0.95,
      "annotation_notes": "Optional interpretation notes; saved in ext_info."
    }
  ]
}
```

Benchmark-local `ref_id` convention: `<record_id>_gref_<seqno>`; not a production `ref_id` (`<rec>_ref_<n>`). Candidate IDs are unique within a run. Accepted candidates link their references (`ref_ids`); excluded candidates link none; duplicate candidates link the retained reference. Every reference needs an accepted candidate. Uncertain decisions or nonempty `limitations` block saving.

| Field | Contract |
|---|---|
| `section` | Heading of the containing section as written; `""` before the first heading |
| `source_line_spans` | `N`/`N:M` strings; no page numbers or row suffixes |
| `source_table_rows` | `[{"line": 116, "rows": ["r1"]}]` for references inside an HTML table line (IDs as `ParseTableGrid`) |
| `evidence` | Exact source substrings `[{line, quote}]`, lines inside the spans; saved joined by a space in the `evidence` column and as the list in `ext_info.evidence` |
| `cited_raw` | The citation as written; must occur in the cited lines (joined in line order) |
| `ref_form` / `list_kind` / `list_label` | `listed` with `normative`/`informative` and its label (or `""`); `in_text` with `""` and `""` |
| `list_entry_ref_id` | In-text, non-internal: the `ref_id` of the listed entry of the same resource (identity key or label), normative entry first; else `""`. Recomputed by `validate` |
| `normativity` | `normative` / `informative` / `unlisted`, from the lists only. Recomputed by `validate` |
| `list_mismatch` | `""`, `not_listed` or `never_cited`; only when the document has a normative list. Recomputed by `validate` |
| `in_requirement` | Boolean; false for listed entries |
| `mechanism` | Governed vocabulary; `structural_reference` exactly when `internal` is true |
| `identifiers` | `[{kind, value, edition?}]`; kinds `standard rfc legal doi arxiv pmid isbn issn patent url` (public), `file_path repository` (private); standards as `GB/T 755` + `edition: "2019"`; `[]` for internal, indirect and title-only references |
| `target_type` / `target_subtype` / `target_subtype_label` | Governed type and subtype (`reference_model.go`); `others` with a nonempty label, otherwise label `""`. Internal: `document` + `document_section` or `document_element` |
| `relationships` | Sorted, unique, nonempty subset of the asserted relationships |
| `target_scope`, `target_locator` | Scope vocabulary; locator as written or `""` (required for internal references) |
| `target_content` | `criterion criteria_set method term requirements data general`; listed entries are `general`; internal references are never `criterion`/`criteria_set` |
| `metric_name`, `metric_subject`, `condition` | Nonempty name and subject on `criterion` rows only (condition may be `""`); all empty otherwise |
| `metric_name_en`, `metric_subject_en` | Required on `criterion` rows of non-English documents; null otherwise |
| `internal` | Boolean |
| `confidence` | Finite number 0–1 |
| `annotation_notes` | Optional string, saved in `ext_info` |

The run row stores `document_identifier` (the document's own identifier as printed on it, `""` if it shows none), `language`, `title`/`doc_no` (from `doc_metadata`, falling back to top-level columns), `coverage`, `candidates`, both reviews, `rules_sha256` and `reviewed_at`. Per-row `ext_info` (schema `1`) holds `evidence`, `annotation_notes` and `candidate_ids`.

## Table provisioning and save

Schema: `ChenWeb/project_migrations/20261011000003_create_testbed_ref_mentions.sql`, applied by the Goose project track (`ChenWeb/project_migrations`, version table `project_db_migration`) at server start-up or through the db-migration skill. It creates:

- `testbed.reference_benchmark_runs`: one row per run, primary key (`skill_name`, `skill_version`, `model_name`, `run_id`);
- `testbed.ref_mentions`: the gold references, unique per run key and `ref_id`, foreign key to the run;
- `testbed.ref_mentions_dropped`: excluded and duplicate candidates, `drop_reason` = the candidate's `rule_id`, `candidate_data` = the complete ledger entry.

Inspect before saving:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'testbed' AND table_name IN ('reference_benchmark_runs', 'ref_mentions', 'ref_mentions_dropped')
ORDER BY table_name, ordinal_position;
```

Validate and save:

```bash
python3 .agents/skills/extract-references-benchmark/scripts/benchmark_io.py validate \
  --record /tmp/refs-123-record.json --payload /tmp/refs-123-benchmark.json
python3 .agents/skills/extract-references-benchmark/scripts/benchmark_io.py save \
  --record /tmp/refs-123-record.json --payload /tmp/refs-123-benchmark.json
```

The helper sends fixed-identifier, quoted JSON SQL through `psql` stdin with `ON_ERROR_STOP=1`. Run row first, then references and dropped candidates, in one transaction. An advisory lock on the run key and a guard abort the save if the run already exists.

Read back, substituting the run key:

```bash
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=123 -v run_id='<yyyymmdd_hhmmss>' \
  -v skill_version='<version>' -v model_name='<model>' \
  -o /tmp/refs-123-readback.json <<'SQL'
SELECT COALESCE(jsonb_agg(to_jsonb(m) ORDER BY m.ref_id), '[]'::jsonb)
FROM testbed.ref_mentions m
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-references-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';
SQL
```

```sql
SELECT to_jsonb(r) FROM testbed.reference_benchmark_runs r
WHERE run_id = :'run_id' AND skill_name = 'extract-references-benchmark'
  AND skill_version = :'skill_version' AND model_name = :'model_name';

SELECT COALESCE(jsonb_agg(d.candidate_data ORDER BY d.candidate_id), '[]'::jsonb)
FROM testbed.ref_mentions_dropped d
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-references-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';
```

Compare all substantive fields to the validated JSON, allowing only database-managed IDs and timestamps; `confidence` may deserialize as a float. If DB access is unavailable, keep the validated JSON and report persistence pending; artifacts alone are not a saved benchmark.
