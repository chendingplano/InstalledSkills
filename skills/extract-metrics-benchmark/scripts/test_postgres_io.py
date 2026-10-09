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
        script = Path(__file__).resolve()
        workspace = script.parents[4]
        migrations = [path.read_text().split('-- +goose Down') for path in
                      sorted((workspace / 'ChenWeb/project_migrations').glob('*testbed_metrics.sql'))]
        self.assertGreaterEqual(len(migrations), 6)
        up = '\n'.join(m[0] for m in migrations)
        down = '\n'.join(m[1] for m in reversed(migrations))
        with tempfile.TemporaryDirectory(prefix='metric-benchmark-pg-') as scratch:
            root = Path(scratch)
            data = root / 'data'
            env = os.environ.copy()
            env.update(PGHOST=scratch, PGPORT='55437', PGDATABASE='postgres',
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
                 '-o', f"-F -k {scratch} -h '' -p 55437", '-w', 'start'])
            try:
                sql('CREATE SCHEMA kb; CREATE TABLE kb.inputs (id bigint primary key, '
                    'result_filename text, staging_filename text, parser_name text);')
                sql('BEGIN;\n' + up + '\nCOMMIT;')
                sql('BEGIN;\n' + down + '\nCOMMIT;')
                self.assertEqual(sql("SELECT to_regclass('testbed.metrics') IS NULL;"), 't')
                self.assertEqual(sql("SELECT to_regclass('testbed.metric_benchmark_runs') IS NULL;"), 't')
                sql('BEGIN;\n' + up + '\nCOMMIT;')
                record = fixture.record
                quote = lambda text: "'" + text.replace("'", "''") + "'"
                sql('INSERT INTO kb.inputs VALUES (' + str(record['id']) + ', ' +
                    ', '.join(quote(record[k]) for k in
                              ('result_filename', 'staging_filename', 'parser_name')) + ');')
                rows = fixture.io.validate(record, fixture.payload)
                save = fixture.io.save_sql(record, fixture.payload, rows)
                sql(save)
                saved = json.loads(sql('SELECT jsonb_agg(to_jsonb(m)) FROM testbed.metrics m;'))
                self.assertEqual(len(saved), 1)
                for key, value in rows[0].items():
                    self.assertEqual(saved[0][key], value, key)
                self.assertEqual(saved[0]['skill_version'], fixture.io.newest_version())
                self.assertEqual(saved[0]['skill_name'], fixture.io.skill_name())
                self.assertEqual(saved[0]['model_name'], 'test-model')
                self.assertEqual(saved[0]['run_id'], fixture.payload['benchmark_run_id'])
                saved_run = json.loads(sql('SELECT to_jsonb(r) FROM testbed.metric_benchmark_runs r;'))
                self.assertEqual(saved_run['candidates'], fixture.payload['candidates'])
                self.assertEqual(saved_run['coverage'], fixture.payload['coverage'])
                self.assertEqual(saved_run['benchmark_run_id'], fixture.payload['benchmark_run_id'])
                self.assertNotIn('candidates', saved[0]['ext_info'])
                sql(save, succeeds=False)
                sql(fixture.io.save_sql(dict(record, staging_filename='wrong.pdf'),
                                        fixture.payload, rows), succeeds=False)
                broken = [dict(rows[0], benchmark_run_id='not-a-timestamp'),
                          dict(rows[0], metric_id='broken', source_line_spans={})]
                sql(fixture.io.save_sql(record, fixture.payload, broken), succeeds=False)
                self.assertEqual(sql('SELECT count(*) FROM testbed.metrics;'), '1')
                self.assertEqual(sql('SELECT count(*) FROM testbed.metric_benchmark_runs;'), '1')
                # A new run key appends a new snapshot; the first run is untouched.
                rerun = dict(fixture.payload, benchmark_run_id='20000101_000000')
                sql(fixture.io.save_sql(record, rerun, fixture.io.validate(record, rerun)))
                self.assertEqual(sql('SELECT count(DISTINCT benchmark_run_id) FROM testbed.metrics;'), '2')
                self.assertEqual(sql('SELECT count(*) FROM testbed.metric_benchmark_runs;'), '2')
                self.assertEqual(sql('SELECT count(*) FROM testbed.metrics WHERE run_id IS DISTINCT FROM benchmark_run_id;'), '0')
                # Dropping/re-adding the alias preserves runs and populates existing rows.
                alias = migrations[-1]
                sql('BEGIN;\n' + alias[1] + '\nCOMMIT;')
                self.assertEqual(sql("SELECT count(*) FROM information_schema.columns WHERE table_schema='testbed' AND table_name='metrics' AND column_name='run_id';"), '0')
                sql('BEGIN;\n' + alias[0] + '\nCOMMIT;')
                self.assertEqual(sql('SELECT count(*) FROM testbed.metrics WHERE run_id = benchmark_run_id;'), '2')
                # Down restores the per-row audit record; Up collapses it again.
                last = next(m for m in migrations if
                            'CREATE TABLE IF NOT EXISTS testbed.metric_benchmark_runs' in m[0])
                sql('BEGIN;\n' + last[1] + '\nCOMMIT;')
                self.assertEqual(sql("SELECT count(*) FROM testbed.metrics WHERE ext_info ? 'candidates';"), '2')
                sql('BEGIN;\n' + last[0] + '\nCOMMIT;')
                self.assertEqual(sql('SELECT count(*) FROM testbed.metric_benchmark_runs;'), '2')
                self.assertEqual(sql("SELECT count(*) FROM testbed.metrics WHERE ext_info ? 'candidates';"), '0')
            finally:
                run(['pg_ctl', '-D', str(data), '-m', 'immediate', '-w', 'stop'])


if __name__ == '__main__':
    unittest.main()
