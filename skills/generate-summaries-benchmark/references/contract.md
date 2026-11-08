# Commands and persistence

Run from `/Users/cding/Workspace`. Use the configured ChenWeb project PostgreSQL connection, supplying standard `PG*` environment variables privately. Map project names such as `PG_USER_NAME`, `PG_PASSWORD` and `PG_DB_NAME` as needed. Do not print `.env` or put credentials in command arguments.

Export the input metadata to a fresh local file (replace 416 with the requested positive integer):

```sh
psql -X -A -t -v ON_ERROR_STOP=1 -v record_id=416 \
  -o /tmp/summary-416-record.json <<'SQL'
SELECT jsonb_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name,
 'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata)
FROM kb.inputs WHERE id = :'record_id'::bigint;
SQL

python3 .agents/skills/generate-summaries-benchmark/scripts/benchmark_io.py prepare \
  --record /tmp/summary-416-record.json --model-name '<invoking model>' \
  --output /tmp/summary-416-gold.json > /tmp/summary-416-source.json
```

`prepare` accepts `--line-file` to verify a supplied filename, `--chunks` to select the exact document chunk artifact, `--budget-chars` (default 600) and `--skill-version` (default 1.0.0). It refuses to overwrite the payload. Choose fresh output paths on every run. Resolve relative `result_filename` against `DATA_HOME_DIR`. Chunk paths default to `ARTIFACT_DIR/<group>/<record>/<stem>_<parser>.chunks`. Do not use glob-first resolution. If supplied filename and metadata disagree, resolve the disagreement before proceeding. Only line IDs in the file are valid evidence; IDs need not be contiguous.

For a filename-only request, query `kb.inputs` metadata to identify the record whose resolved canonical filename equals the supplied absolute path. Zero or multiple matches require clarification. The helper intentionally requires an exported record rather than guessing an ID.

## Payload

Preserve prepared identity, record/source/chunk fingerprints, chunk sequence and coverage. Fill each summary's `language`, `summary_text`, `summary_text_en`, `keywords`, `keywords_en`, `units`, `empty_reason`, `completeness_review` and `correctness_review`. `source_line_spans` is the ordered full input as compact strings: a contiguous run is one `"a-b"` range and an isolated line is a singleton, e.g. `["88-103"]` or `["2", "4"]`, never one string per line; `regular_lines` and `overlap_lines` are integer arrays. These spans describe input coverage, not selected evidence. No parent or child summaries exist in this contract.

Example unit (fictional source content: `Storage shall remain at or below 8°C.`):

```json
{
  "id": "u1",
  "claim": "Storage temperature must not exceed 8°C.",
  "weight": 3,
  "critical": true,
  "included": true,
  "omission_reason": "",
  "evidence": [{"line": 12, "start": 0, "end": 36,
    "quote": "Storage shall remain at or below 8°C."}]
}
```

Evidence offsets index the original content, not serialized record text or UTF-8 bytes. Both reviews have the form `{"reviewer":"actual agent/session identity (model)","notes":"Concrete findings and corrections."}`. Reviewers may share an underlying model but must be separate agents to claim independent review. Set run `review_mode` to `independent` or `self`, list known limitations, and leave no unresolved `blocking_issues`. Mechanical validation cannot certify semantic completeness or reviewer independence.

## Schema and saving

The project Goose migration is `ChenWeb/project_migrations/20261021000003_create_testbed_summaries.sql`. Normal ChenWeb startup invokes `RunProjectMigrations` from `server/cmd/config/config.go` using the project migration track and its existing version table. If the tables are absent, apply project migrations through established project tooling; do not use runtime CREATE TABLE or edit an applied migration. Never test Down against real benchmark data.

`testbed.summary_benchmark_runs` stores the full reviewed payload once, including hashes, budget, model, rules version and audits. `testbed.summaries` stores queryable leaf rows with standard summary columns and their evidence, original chunk membership and reviews. Full run key is `(skill_name, skill_version, model_name, run_id)`; `run_id` is local preparation time `yyyymmdd_hhmmss`. The input ID and chunk sequence identify rows within that run. New snapshots append; a duplicate full key fails atomically. No production search triggers or automatic processor updates are installed.

```sh
python3 .agents/skills/generate-summaries-benchmark/scripts/benchmark_io.py validate \
  --record /tmp/summary-416-record.json --payload /tmp/summary-416-gold.json
python3 .agents/skills/generate-summaries-benchmark/scripts/benchmark_io.py save \
  --record /tmp/summary-416-record.json --payload /tmp/summary-416-gold.json
python3 .agents/skills/generate-summaries-benchmark/scripts/benchmark_io.py readback \
  --payload /tmp/summary-416-gold.json
```

The helper uses `psql` stdin and quotes data as SQL standard strings, locks the input row, rereads its metadata and rehashes both source files before inserting the run and every summary in one transaction. File updates are not database-transactional; serialize same-document processing operationally. A failed transaction preserves earlier snapshots. After a connection error, use readback before retrying. Do not count multiple snapshots together when comparing candidate outputs.

Readback compares the stored run payload and every substantive leaf field with the reviewed JSON; database-managed IDs/timestamps are excluded. Generated/paraphrased summaries need semantic review. The offline extractive scorer under `ChenWeb/benchmark/summaries/` expects a different frozen case/span contract and must not be applied directly to these rows.
