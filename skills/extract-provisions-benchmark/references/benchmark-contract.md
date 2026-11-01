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
  -o /tmp/prov-123-record.json <<'SQL'
SELECT json_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name,
 'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata)
FROM kb.inputs WHERE id = :'record_id'::bigint;
SQL

python3 .agents/skills/extract-provisions-benchmark/scripts/benchmark_io.py prepare \
  --record /tmp/prov-123-record.json --output /tmp/prov-123-benchmark.json \
  --skill-version <released version; omit for the newest> \
  --model-name <invoking model identity> > /tmp/prov-123-source.json
```

- An empty query result means an unknown ID.
- `DATA_HOME_DIR` is required for relative result paths.
- The source stdout lists every validated line; read it in bounded portions.

## Reviewed JSON envelope

Populate the prepared payload. Keep its record ID, run ID, skill name and version, rules hash,
model name, source path and hash. This abbreviated example (a Chinese standard) shows the shape:

```json
{
  "record_id": 123,
  "run_id": "<yyyymmdd_hhmmss from prepare>",
  "skill_name": "extract-provisions-benchmark",
  "skill_version": "<version from prepare>",
  "rules_sha256": "<from prepare>",
  "model_name": "<from prepare --model-name>",
  "source_filename": "<resolved working .txt path>",
  "source_sha256": "<from prepare>",
  "language": "zh",
  "completeness_review": "All lines read; marker search (应/不得/宜/可…) and A5 sweep reconciled.",
  "correctness_review": "Checked text, kind/type, subject, location. Consistency: …",
  "limitations": [],
  "coverage": [{"source_line_spans": ["1-60"], "reason": "Cover, foreword, scope, clause 5."}],
  "candidates": [
    {"candidate_id": "c1", "source_line_spans": ["41"], "decision": "accepted", "rule_id": "A1",
     "text": "垃圾分类收集容器应有盖", "prov_ids": ["123_gprv_1"], "reason": "应: requirement on the container."},
    {"candidate_id": "c2", "source_line_spans": ["18"], "decision": "excluded", "rule_id": "X2",
     "text": "本标准适用于农村生活垃圾分类处理。", "prov_ids": [], "reason": "Scope statement."}
  ],
  "provisions": [
    {
      "prov_id": "123_gprv_1", "section": "7.1 投放要求",
      "source_line_spans": ["41"], "source_table_rows": [],
      "evidence": [{"line": 41, "quote": "垃圾分类收集容器应有盖"}],
      "provision": "垃圾分类收集容器应有盖，应在显著位置印制垃圾分类标志。",
      "provision_en": "Sorted-waste collection containers shall have lids and shall carry the waste-sorting mark in a prominent position.",
      "prov_name": "分类收集容器有盖并印制标志", "prov_name_en": "Collection containers have lids and sorting marks",
      "provision_type": "mandatory", "provision_kind": "requirement",
      "provision_subject": "垃圾分类收集容器", "provision_subject_en": "Sorted-waste collection container",
      "location_type": "bullet", "is_explicit": true, "confidence": 0.95,
      "annotation_notes": "Optional interpretation notes; saved in ext_info."
    }
  ]
}
```

**IDs and links.**
- The benchmark-local `prov_id` convention is `<record_id>_gprv_<seqno>`. It is not a production
  `prov_id` (`<rec>_prv_<n>`).
- Candidate IDs are unique within a run.
- Accepted candidates link their provisions (`prov_ids`), excluded candidates link none, and
  duplicate candidates link the retained provision. Every provision needs an accepted candidate.
- Uncertain decisions or a nonempty `limitations` block saving.

| Field | Contract |
|---|---|
| `section` | Heading of the containing section as written; `""` before the first heading |
| `source_line_spans` | `N` / `N-M` strings (production form); no page numbers or row suffixes |
| `source_table_rows` | `[{"line": 121, "rows": ["r2"]}]` for a provision inside an HTML table line (IDs as `ParseTableGrid`: data rows `r1…`); required on table lines, `[]` otherwise |
| `evidence` | Exact source substrings `[{line, quote}]` on lines inside the spans. Saved joined by a space in the `evidence` column and as the list in `ext_info.evidence` |
| `provision` | The statement as written. Non-contiguous parts are joined with ` … `; each part must occur in the cited lines joined in line order (whitespace-insensitive; table markup removed) |
| `provision_en` | English translation for non-English documents (may be `""`); `""` for English documents |
| `prov_name`, `prov_name_en` | Short name of what is regulated; `_en` required for non-English documents, null otherwise |
| `provision_kind` | `requirement prohibition instruction recommendation permission` |
| `provision_type` | `mandatory` (requirement, prohibition, instruction), `recommended` (recommendation) or `optional` (permission); enforced |
| `provision_subject`, `provision_subject_en` | Who or what the provision binds; `_en` required for non-English documents, null otherwise |
| `location_type` | `sentence paragraph bullet table_row table_cell heading_context mixed`. Table lines only ↔ `table_row`/`table_cell`; table plus other lines ↔ `mixed` |
| `is_explicit` | Boolean: false only for implicit requirements (A5) |
| `confidence` | Finite number 0–1 |
| `annotation_notes` | Optional string, saved in `ext_info` |
| candidate `text` | The candidate statement as source text (same check as `provision`) |

**Run row.** The run row stores `language`, `title`/`doc_no` (from `doc_metadata`, falling back
to the top-level columns), `coverage`, `candidates`, both reviews, `rules_sha256` and
`reviewed_at`. Per-row `ext_info` (schema `1`) holds `evidence`, `annotation_notes` and
`candidate_ids`.

## Table provisioning and save

**Schema.** `ChenWeb/project_migrations/20261106000101_create_testbed_provisions.sql`, applied by
the Goose project track (`ChenWeb/project_migrations`, version table `project_db_migration`) at
server start-up or through the db-migration skill. It creates:

- `testbed.provision_benchmark_runs`: one row per run, primary key (`skill_name`,
  `skill_version`, `model_name`, `run_id`);
- `testbed.provisions`: the gold provisions, unique per run key and `prov_id`, with a foreign key
  to the run;
- `testbed.provisions_dropped`: excluded and duplicate candidates. `drop_reason` is the
  candidate's `rule_id`; `candidate_data` is the complete ledger entry.

Inspect the tables before saving:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'testbed' AND table_name IN ('provision_benchmark_runs', 'provisions', 'provisions_dropped')
ORDER BY table_name, ordinal_position;
```

Validate and save:

```bash
python3 .agents/skills/extract-provisions-benchmark/scripts/benchmark_io.py validate \
  --record /tmp/prov-123-record.json --payload /tmp/prov-123-benchmark.json
python3 .agents/skills/extract-provisions-benchmark/scripts/benchmark_io.py save \
  --record /tmp/prov-123-record.json --payload /tmp/prov-123-benchmark.json
```

The helper sends fixed-identifier, quoted JSON SQL through `psql` stdin with `ON_ERROR_STOP=1`. It
writes the run row first, then the provisions and the dropped candidates, in one transaction. An
advisory lock on the run key and a guard abort the save if the run already exists.

Read back, substituting the run key:

```sql
SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.prov_id), '[]'::jsonb)
FROM testbed.provisions p
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-provisions-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';

SELECT to_jsonb(r) FROM testbed.provision_benchmark_runs r
WHERE run_id = :'run_id' AND skill_name = 'extract-provisions-benchmark'
  AND skill_version = :'skill_version' AND model_name = :'model_name';

SELECT COALESCE(jsonb_agg(d.candidate_data ORDER BY d.candidate_id), '[]'::jsonb)
FROM testbed.provisions_dropped d
WHERE input_record_id = :'record_id'::bigint AND run_id = :'run_id'
  AND skill_name = 'extract-provisions-benchmark' AND skill_version = :'skill_version'
  AND model_name = :'model_name';
```

**Compare** every substantive field with the validated JSON. Only database-managed IDs and
timestamps may differ, and `confidence` may deserialize as a float. If DB access is unavailable,
keep the validated JSON and report persistence pending; artifacts alone are not a saved
benchmark.
