"""Opt-in integration test using a disposable PostgreSQL cluster, never the project DB.

BENCHMARK_TEST_POSTGRES=1 python3 -m unittest discover -s <skill>/scripts
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import test_benchmark_io as fixtures


@unittest.skipUnless(os.environ.get('BENCHMARK_TEST_POSTGRES') == '1' and
                     all(shutil.which(x) for x in ('initdb', 'pg_ctl', 'psql')),
                     'Set BENCHMARK_TEST_POSTGRES=1 with local PostgreSQL binaries')
class PostgresIOTests(unittest.TestCase):
    def test_migration_and_atomic_save(self):
        fixtures.BenchmarkIOTests.setUpClass()
        fixture = fixtures.BenchmarkIOTests()
        fixture.setUp()
        self.addCleanup(fixture.tmp.cleanup)
        workspace = Path(__file__).resolve().parents[4]
        up, down = (workspace / 'ChenWeb/project_migrations/20261011000003_create_testbed_ref_mentions.sql'
                    ).read_text().split('-- +goose Down')
        with tempfile.TemporaryDirectory(prefix='reference-benchmark-pg-') as scratch:
            root = Path(scratch)
            data = root / 'data'
            env = os.environ.copy()
            env.update(PGHOST=scratch, PGPORT='55438', PGDATABASE='postgres',
                       PGUSER=env.get('USER', 'cding'), PGSSLMODE='disable')
            env.pop('PGPASSWORD', None)
            env.pop('PGSERVICE', None)

            def run(cmd):
                return subprocess.run(cmd, capture_output=True, text=True, check=True)

            def sql(body, succeeds=True):
                result = subprocess.run(['psql', '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1'],
                                        input=body, capture_output=True, text=True, env=env)
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                return result.stdout.strip()

            run(['initdb', '-D', str(data), '--no-locale', '--encoding=UTF8', '--auth=trust'])
            run(['pg_ctl', '-D', str(data), '-l', str(root / 'server.log'),
                 '-o', f"-F -k {scratch} -h '' -p 55438", '-w', 'start'])
            try:
                sql('CREATE SCHEMA kb; CREATE SCHEMA testbed; CREATE TABLE kb.inputs (id bigint primary key, '
                    'result_filename text, staging_filename text, parser_name text);')
                sql('BEGIN;\n' + up + '\nCOMMIT;')
                sql('BEGIN;\n' + down + '\nCOMMIT;')
                self.assertEqual(sql("SELECT to_regclass('testbed.ref_mentions') IS NULL;"), 't')
                sql('BEGIN;\n' + up + '\nCOMMIT;')
                record, payload = fixture.record, fixture.payload
                payload['candidates'].append(
                    {'candidate_id': 'c6', 'decision': 'duplicate', 'rule_id': 'D1', 'ref_ids': ['123_gref_3'],
                     'source_line_spans': ['6'], 'cited_raw': 'GB 7959', 'reason': 'Seen by two windows.'})
                quote = lambda text: "'" + text.replace("'", "''") + "'"
                sql('INSERT INTO kb.inputs VALUES (' + str(record['id']) + ', ' +
                    ', '.join(quote(record[k]) for k in
                              ('result_filename', 'staging_filename', 'parser_name')) + ');')
                rows = fixture.io.validate(record, payload)
                save = fixture.io.save_sql(record, payload, rows)
                sql(save)
                saved = json.loads(sql('SELECT jsonb_agg(to_jsonb(m) ORDER BY ref_id) FROM testbed.ref_mentions m;'))
                self.assertEqual(len(saved), 4)
                for row, stored in zip(sorted(rows, key=lambda r: r['ref_id']), saved):
                    for key, value in row.items():
                        self.assertEqual(stored[key], value, key)
                run_row = json.loads(sql('SELECT to_jsonb(r) FROM testbed.reference_benchmark_runs r;'))
                self.assertEqual(run_row['candidates'], payload['candidates'])
                self.assertEqual(run_row['document_identifier'], 'GB/T 46121-2025')
                dropped = json.loads(sql('SELECT jsonb_agg(to_jsonb(d) ORDER BY candidate_id) '
                                         'FROM testbed.ref_mentions_dropped d;'))
                self.assertEqual([d['candidate_id'] for d in dropped], ['c5', 'c6'])
                self.assertEqual([d['drop_reason'] for d in dropped], ['X2', 'D1'])
                self.assertEqual(dropped[0]['candidate_data'], payload['candidates'][4])
                # A run key is used once; a wrong source identity or a bad row saves nothing.
                sql(save, succeeds=False)
                sql(fixture.io.save_sql(dict(record, staging_filename='wrong.pdf'), payload, rows), succeeds=False)
                sql(fixture.io.save_sql(record, dict(payload, run_id='20000101_000000'),
                                        [dict(rows[0], normativity='binding')]), succeeds=False)
                self.assertEqual(sql('SELECT count(*) FROM testbed.reference_benchmark_runs;'), '1')
                self.assertEqual(sql('SELECT count(*) FROM testbed.ref_mentions;'), '4')
                # A new run key appends a new snapshot.
                rerun = dict(payload, run_id='20000101_000000')
                sql(fixture.io.save_sql(record, rerun, fixture.io.validate(record, rerun)))
                self.assertEqual(sql('SELECT count(DISTINCT run_id) FROM testbed.ref_mentions;'), '2')
                self.assertEqual(sql('SELECT count(*) FROM testbed.ref_mentions_dropped;'), '4')
            finally:
                run(['pg_ctl', '-D', str(data), '-m', 'immediate', '-w', 'stop'])


if __name__ == '__main__':
    unittest.main()
