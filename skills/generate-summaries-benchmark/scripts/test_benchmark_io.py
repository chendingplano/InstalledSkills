import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

import benchmark_io as io


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = dict(id=416, result_filename=str(self.root / 'doc.json'),
                           staging_filename='doc.pdf', parser_name='parser', title='Test',
                           doc_no='T1', doc_metadata={})
        self.source = self.root / 'doc_parser.txt'
        self.source.write_text(''.join(
            f'{n}\t1\t{kind}\tArial\t12\t[0,0,1,1]\t{text}\n' for n, kind, text in [
                (1, 'paragraph', 'Storage shall not exceed 8°C.'),
                (2, 'paragraph', 'Except during sealed qualification.'),
                (4, 'paragraph', '常温下应保存记录。'),
                (5, 'image', '[image]'), (6, 'toc', 'Contents')]), encoding='utf-8')
        self.chunks = self.root / 'doc_parser.chunks'
        self.chunks.write_text('overlap: []\nlines: [1-2]\n\noverlap: [2]\nlines: [4]\noverlap: []\nlines: [5]\n')
        self.payload, self.exported = io.prepare(self.record, self.chunks, 'author-model')
        self.payload.update(review_mode='independent')
        for summary in self.payload['summaries']:
            summary.update(language='en', completeness_review={'reviewer': 'agent-2 (author-model)', 'notes': 'Checked all source lines and omissions.'},
                           correctness_review={'reviewer': 'agent-3 (author-model)', 'notes': 'Checked exception, units and translation.'})
            if summary['summary_seq_no'] == 3:
                summary.update(empty_reason='Image placeholder only; no readable caption.')
                continue
            source = self.exported[summary['summary_seq_no'] - 1]['lines']
            summary.update(summary_text=' '.join(s['content'] for s in source), keywords=['storage'])
            summary['units'] = [dict(id=f'u{s["line"]}', claim=s['content'], weight=3, critical=True,
                                     included=True, omission_reason='', evidence=[dict(line=s['line'], start=0,
                                         end=len(s['content']), quote=s['content'])]) for s in source]
            if summary['summary_seq_no'] == 2:
                summary.update(language='zh-cn', summary_text='密封鉴定期间除外。常温下应保存记录。',
                               summary_text_en='Except during sealed qualification. Records shall be retained at room temperature.',
                               keywords=['记录'], keywords_en=['records'])

    def fails(self, payload=None):
        with self.assertRaises(ValueError):
            io.validate(self.record, payload or self.payload)

    def test_valid_bilingual_and_empty_chunks(self):
        self.assertIs(io.validate(self.record, self.payload), self.payload)
        self.assertEqual(self.payload['summaries'][1]['source_line_spans'], ['2', '4'])
        self.assertEqual(self.payload['summaries'][0]['source_line_spans'], ['1-2'])

    def test_compact_spans_round_trip(self):
        self.assertEqual(io.compact([1, 2, 3, 5, 7, 8]), ['1-3', '5', '7-8'])
        self.assertEqual(io.expand_spans(['1-3', '5']), [1, 2, 3, 5])
        with self.assertRaises(ValueError):
            io.expand_spans(['3-1'])

    def test_changed_source(self):
        self.source.write_text(self.source.read_text().replace('8°C', '9°C'))
        self.fails()

    def test_changed_chunk_artifact(self):
        self.chunks.write_text(self.chunks.read_text() + '\n')
        self.fails()

    def test_invalid_evidence_quote_and_coordinates(self):
        for change in ({'quote': '8°C'}, {'line': 4}, {'start': -1}, {'end': 999}, {'start': True}):
            payload = copy.deepcopy(self.payload)
            payload['summaries'][0]['units'][0]['evidence'][0].update(change)
            self.fails(payload)

    def test_critical_omission(self):
        unit = self.payload['summaries'][0]['units'][0]
        unit.update(included=False, omission_reason='Budget')
        self.fails()

    def test_noncritical_omission_requires_reason(self):
        unit = self.payload['summaries'][0]['units'][0]
        unit.update(included=False, critical=False, omission_reason='')
        self.fails()
        unit['omission_reason'] = 'Secondary context omitted within budget.'
        io.validate(self.record, self.payload)

    def test_translation_required(self):
        self.payload['summaries'][1]['summary_text_en'] = ''
        self.fails()

    def test_budget_counts_codepoints(self):
        self.payload['budget_chars'] = 1
        self.fails()

    def test_cannot_skip_chunk(self):
        self.payload['summaries'].pop()
        self.fails()

    def test_cannot_empty_readable_chunk(self):
        summary = self.payload['summaries'][0]
        summary.update(summary_text='', keywords=[], units=[], empty_reason='Skip')
        self.fails()

    def test_review_and_blocking_issues(self):
        self.payload['blocking_issues'] = ['Unresolved OCR']
        self.fails()
        self.payload['blocking_issues'] = []
        self.payload['summaries'][0]['correctness_review']['reviewer'] = 'author-model'
        self.fails()

    def test_changed_record(self):
        self.record['parser_name'] = 'other'
        self.fails()

    def test_reject_bad_canonical_records(self):
        for text in ('1 1 paragraph text', '1\t1\tp\tf\tNaN\t[0,0,1,1]\tx',
                     '1\t1\tp\tf\t12\t[0,0,1]\tx'):
            self.source.write_text(text)
            with self.assertRaises(ValueError):
                io.load_source(self.record)

    def test_unicode_separators_are_content(self):
        self.source.write_text('1\t1\tparagraph\tArial\t12\t[0,0,1,1]\tFirst\u2028second\u0085third\n')
        self.assertEqual(io.load_source(self.record)[2][1]['content'], 'First\u2028second\u0085third')

    def test_image_caption_cannot_be_empty(self):
        self.source.write_text(self.source.read_text().replace('image\tArial', 'image-caption\tArial'))
        self.payload['source_sha256'] = io.load_source(self.record)[1]
        self.fails()

    def test_reject_bad_chunk_coverage(self):
        for text in ('overlap: []\nlines: [1-2]\n',
                     'overlap: [2]\nlines: [1-2]\n',
                     'overlap: []\nlines: [1-6]\n',
                     'overlap: []\nlines: [1-2]\noverlap: []\nlines: [2,4-5]\n'):
            self.chunks.write_text(text)
            with self.assertRaises(ValueError):
                io.load_chunks(self.chunks, io.load_source(self.record)[2])


@unittest.skipUnless(os.environ.get('SUMMARY_BENCHMARK_TEST_DB') == '1', 'Requires isolated PostgreSQL')
class PostgresTests(unittest.TestCase):
    """Run only in a disposable cluster: these tests own kb/testbed schemas."""

    setUp = BenchmarkTests.setUp

    def test_roundtrip_atomicity_and_migration(self):
        self.payload['model_name'] = "model's\\revision"
        migration = Path(__file__).resolve().parents[4] / 'ChenWeb/project_migrations/20261021000003_create_testbed_summaries.sql'
        up, down = migration.read_text().split('-- +goose Down')
        up = up.replace('-- +goose Up', '')
        io.psql('CREATE SCHEMA kb; CREATE TABLE kb.inputs (id bigint PRIMARY KEY, result_filename text, staging_filename text, parser_name text, title text, doc_no text, doc_metadata jsonb);')
        try:
            io.psql(up)
            io.psql(down)
            io.psql(up)
            value = io.sql_text(json.dumps(self.record, ensure_ascii=False))
            io.psql(f'INSERT INTO kb.inputs SELECT * FROM jsonb_populate_record(NULL::kb.inputs, {value}::jsonb);')
            io.save(self.record, self.payload)
            self.assertEqual(len(io.readback(self.payload)), 3)
            self.assertEqual(io.psql("SELECT lpad('10000', greatest(4, length('10000')), '0');"), '10000')
            with self.assertRaises(ValueError):
                io.save(self.record, self.payload)
            self.assertEqual(len(io.readback(self.payload)), 3)
            # A failed leaf insert must roll back the run insert as well.
            failed = copy.deepcopy(self.payload)
            failed['run_id'] = '20261021_235959'
            io.psql('ALTER TABLE testbed.summaries ADD CONSTRAINT reject_test CHECK (summary_seq_no <> 2) NOT VALID;')
            with self.assertRaises(ValueError):
                io.save(self.record, failed)
            self.assertEqual(io.psql("SELECT count(*) FROM testbed.summary_benchmark_runs WHERE run_id='20261021_235959';"), '0')
            io.psql('ALTER TABLE testbed.summaries DROP CONSTRAINT reject_test;')
            io.psql("UPDATE kb.inputs SET title='changed' WHERE id=416;")
            with self.assertRaises(ValueError):
                io.save(self.record, failed)
        finally:
            io.psql(down)
            io.psql('DROP SCHEMA testbed; DROP TABLE kb.inputs; DROP SCHEMA kb;')


if __name__ == '__main__':
    unittest.main()
