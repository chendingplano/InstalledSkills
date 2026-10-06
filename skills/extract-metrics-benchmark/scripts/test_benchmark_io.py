import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


class BenchmarkIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('benchmark_io.py')
        spec = importlib.util.spec_from_file_location('benchmark_io', path)
        cls.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.io)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.record = {'id': 123, 'result_filename': str(root / 'pump.json'),
                       'staging_filename': 'pump.pdf', 'parser_name': 'mineru',
                       'title': 'Pump requirements', 'doc_metadata': {}}
        self.source = root / 'pump_mineru.txt'
        self.source.write_text(
            '1\t1\theading\tArial\t12\t[0,0,100,20]\tPump requirements\n'
            '2\t1\tparagraph\tArial\t10\t[0,20,100,40]\tPressure shall be ≥ 0.5 MPa.\n',
            encoding='utf-8')
        self.payload = self.io.prepare(self.record, 'test-model')
        self.payload.update(language='en',
                            completeness_review='Read every line twice; one pressure assertion.',
                            correctness_review='Verified subject, ≥, 0.5, MPa and supporting lines.')
        self.payload['coverage'] = [{'source_line_spans': ['1:2'],
                                     'reason': 'Heading supplies subject; pressure clause reviewed.'}]
        self.payload['candidates'] = [{'candidate_id': 'c1', 'decision': 'accepted',
                                      'metric_ids': ['123_gold_1'], 'source_line_spans': ['2'],
                                      'reason': 'Explicit minimum pressure.'}]
        self.payload['metrics'] = [{
            'metric_id': '123_gold_1', 'metric_name': 'Outlet pressure',
            'metric_subject': 'Pump', 'metric_desc': 'Minimum pressure',
            'metric_context': 'Pump requirements', 'metric_keywords': ['pressure'],
            'source_line_spans': ['1:2'], 'source_table_rows': [],
            'location_type': 'sentence', 'metric_unit': 'MPa', 'metric_value': '0.5',
            'value_data_type': 'number', 'value_range_type': 'lower_bound',
            'value_class': 'requirement', 'formula_or_definition': '',
            'threshold_or_target': 'Pressure shall be ≥ 0.5 MPa.',
            'measurement_frequency': '', 'condition': '', 'metric_categories': ['pressure'],
            'confidence': 1.0, 'is_explicit_metric': True, 'table_name_or_section': 'Pump requirements',
            'reasoning_tags': ['has_threshold'],
            'evidence': [{'line': 2, 'quote': 'Pressure shall be ≥ 0.5 MPa.'}]
        }]

    def test_valid_unicode_source_and_evidence(self):
        rows = self.io.validate(self.record, self.payload)
        self.assertEqual(rows[0]['input_record_id'], 123)
        self.assertEqual(rows[0]['ext_info']['evidence'][0]['line'], 2)
        self.assertEqual(rows[0]['metric_value'], '0.5')

    def test_refuses_partial_coverage_uncertainty_and_wrong_quotes(self):
        for mutate in (
            lambda p: p.update(coverage=[{'source_line_spans': ['2'], 'reason': 'Incomplete'}]),
            lambda p: p['candidates'][0].update(decision='uncertain'),
            lambda p: p['metrics'][0]['evidence'][0].update(quote='≤ 0.6'),
            lambda p: p['metrics'][0].update(source_line_spans=['1:3']),
            lambda p: p.update(limitations=['Table unreadable']),
            lambda p: p['metrics'][0].update(confidence=True),
            lambda p: p['metrics'][0].update(is_explicit_metric=False),
        ):
            payload = copy.deepcopy(self.payload)
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_changed_source_and_wrong_document_fail(self):
        self.source.write_text(self.source.read_text() + '\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)
        self.payload['record_id'] = 999
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_legacy_and_duplicate_lines_fail(self):
        for content in ('1 1 paragraph legacy [0,0,1,1]\n',
                        '1\t1\tparagraph\tArial\t10\t[0,0,1,1]\ta\n' * 2):
            self.source.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                self.io.prepare(self.record, 'test-model')

    def test_unicode_line_separator_inside_content_does_not_create_records(self):
        text = self.source.read_text().replace('Pressure shall', 'Note\u2028Pressure shall')
        self.source.write_text(text, encoding='utf-8')
        self.assertEqual(len(self.io.load_lines(self.record)[2]), 2)

    def test_same_span_distinct_conditions_do_not_merge(self):
        second = copy.deepcopy(self.payload['metrics'][0])
        second.update(metric_id='123_gold_2', condition='Emergency mode', metric_value='0.7')
        self.payload['metrics'].append(second)
        self.payload['candidates'][0]['metric_ids'].append('123_gold_2')
        self.assertEqual(len(self.io.validate(self.record, self.payload)), 2)

    def test_missing_metric_candidate_link_fails(self):
        self.payload['candidates'] = []
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_range_requires_finite_ordered_endpoints(self):
        metric = self.payload['metrics'][0]
        metric.update(value_range_type='range', metric_value='0.5–0.8', value_min=0.5, value_max=0.8)
        self.assertEqual(self.io.validate(self.record, self.payload)[0]['value_max'], 0.8)
        for lo, hi in ((0.8, 0.5), (True, 0.8), (0.5, float('inf')), (None, 0.8)):
            metric.update(value_min=lo, value_max=hi)
            with self.subTest(lo=lo, hi=hi), self.assertRaises(ValueError):
                self.io.validate(self.record, self.payload)

    def test_external_reference_carries_no_invented_number(self):
        clause = 'Backup facilities shall comply with CJJ 27.'
        self.source.write_text(
            '1\t1\theading\tArial\t12\t[0,0,100,20]\tPump requirements\n'
            f'2\t1\tparagraph\tArial\t10\t[0,20,100,40]\t{clause}\n', encoding='utf-8')
        self.payload['source_sha256'] = self.io.prepare(self.record, 'test-model')['source_sha256']
        metric = self.payload['metrics'][0]
        metric.update(metric_name='Backup facilities configuration', metric_subject='Backup facilities',
                      value_range_type='qualitative', value_class='reference', metric_unit='',
                      metric_value='', is_explicit_metric=False, threshold_or_target=clause,
                      reasoning_tags=['external_reference', 'cited_doc:CJJ 27'],
                      evidence=[{'line': 2, 'quote': clause}])
        self.assertEqual(self.io.validate(self.record, self.payload)[0]['value_class'], 'reference')
        metric['metric_value'] = '27'
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_table_rows_and_annotation_notes_are_preserved(self):
        table = '<table><tr><th>Mode</th><th>Pressure MPa</th></tr><tr><td>Normal</td><td>0.5</td></tr></table>'
        self.source.write_text(
            '1\t1\theading\tArial\t12\t[0,0,100,20]\tPump requirements\n'
            f'2\t1\ttable\tArial\t10\t[0,20,100,40]\t{table}\n', encoding='utf-8')
        self.payload['source_sha256'] = self.io.prepare(self.record, 'test-model')['source_sha256']
        metric = self.payload['metrics'][0]
        metric.update(location_type='table_cell', source_table_rows=[{'line': 2, 'rows': ['r1']}],
                      evidence=[{'line': 2, 'quote': '<td>Normal</td><td>0.5</td>'}],
                      annotation_notes='Header supplies unit; Normal is the stated condition.')
        row = self.io.validate(self.record, self.payload)[0]
        self.assertEqual(row['source_table_rows'][0]['rows'], ['r1'])
        self.assertEqual(row['ext_info']['annotation_notes'], metric['annotation_notes'])
        metric['source_table_rows'] = []
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_skill_version_is_recorded_and_enforced(self):
        self.assertRegex(self.payload['skill_version'], r'^[0-9]+\.[0-9]+\.[0-9]+$')
        rows = self.io.validate(self.record, self.payload)
        self.assertEqual(rows[0]['skill_version'], self.payload['skill_version'])
        self.assertIn('skill_version', self.io.save_sql(self.record, self.payload, rows))
        for stale in ('0.0.1', None):
            payload = copy.deepcopy(self.payload)
            payload['skill_version'] = stale
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_skill_name_and_model_name_are_recorded(self):
        self.assertEqual(self.payload['skill_name'], 'extract-metrics-benchmark')
        rows = self.io.validate(self.record, self.payload)
        self.assertEqual(rows[0]['skill_name'], 'extract-metrics-benchmark')
        self.assertEqual(rows[0]['model_name'], 'test-model')
        with self.assertRaises(ValueError):
            self.io.prepare(self.record, ' ')
        for key, value in (('model_name', ''), ('skill_name', 'other-skill')):
            payload = copy.deepcopy(self.payload)
            payload[key] = value
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_sql_keeps_quotes_as_data(self):
        self.payload['metrics'][0]['metric_desc'] = "Pump's value'; DROP TABLE kb.metrics; --"
        rows = self.io.validate(self.record, self.payload)
        sql = self.io.save_sql(self.record, self.payload, rows)
        self.assertIn("Pump''s value''; DROP TABLE kb.metrics; --", sql)
        self.assertNotIn('DELETE FROM', sql)
        self.assertIn('INSERT INTO testbed.metrics', sql)
        self.assertIn('COMMIT;', sql)


if __name__ == '__main__':
    unittest.main()
