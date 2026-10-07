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
                                      'rule_id': 'A1', 'reason': 'Explicit minimum pressure.'}]
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
            'reasoning_tags': ['has_threshold', 'kind:requirement_with_criterion'],
            'evidence': [{'line': 2, 'quote': 'Pressure shall be ≥ 0.5 MPa.'}]
        }]

    def pinned(self, version):
        """The fixture payload prepared under a named rules version."""
        payload = self.io.prepare(self.record, 'test-model', version)
        payload.update({k: copy.deepcopy(self.payload[k]) for k in (
            'language', 'completeness_review', 'correctness_review', 'coverage', 'candidates', 'metrics')})
        return payload

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
        self.payload = self.pinned('2.1.0')  # delegations are metrics only before rules 3.0.0
        metric = self.payload['metrics'][0]
        metric.update(metric_name='Backup facilities configuration', metric_subject='Backup facilities',
                      value_range_type='qualitative', value_class='reference', metric_unit='',
                      metric_value='', is_explicit_metric=False, threshold_or_target=clause,
                      reasoning_tags=['external_reference', 'cited_doc:CJJ 27', 'kind:delegated_requirement'],
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

    def test_run_id_is_a_timestamp_and_a_run_key_is_never_reused(self):
        from datetime import datetime
        self.assertRegex(self.payload['benchmark_run_id'], r'^[0-9]{8}_[0-9]{6}$')
        self.assertEqual(self.io.new_run_id(datetime(2026, 10, 6, 9, 5, 7)), '20261006_090507')
        rows = self.io.validate(self.record, self.payload)
        sql = self.io.save_sql(self.record, self.payload, rows)
        self.assertIn('benchmark_run_key_unused', sql)
        self.assertIn(f"benchmark_run_id = '{self.payload['benchmark_run_id']}'", sql)
        self.assertNotIn('ON CONFLICT', sql)
        for legacy in ('22aa157c-d712-46be-abc8-d7f195cff483', '20261006-090507', None):
            payload = copy.deepcopy(self.payload)
            payload['benchmark_run_id'] = legacy
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_every_released_rules_file_is_unchanged(self):
        for version in self.io.rules_manifest()['versions']:
            self.assertEqual(self.io.resolve_rules(version)[0], version)

    def test_default_is_newest_release_not_prerelease(self):
        manifest = {'versions': {v: {} for v in ('1.0.0', '1.10.0', '1.9.0', '2.0.0-rc.1')}}
        self.assertEqual(self.io.newest_version(manifest), '1.10.0')
        self.assertEqual(self.payload['skill_version'], self.io.newest_version())
        self.assertLess(self.io.version_key('2.0.0-rc.1'), self.io.version_key('2.0.0'))

    def test_named_version_is_run_and_recorded(self):
        payload = self.io.prepare(self.record, 'test-model', '1.0.0')
        payload.update({k: self.payload[k] for k in ('language', 'completeness_review',
                        'correctness_review', 'coverage', 'candidates', 'metrics')})
        rows = self.io.validate(self.record, payload)
        self.assertEqual(rows[0]['skill_version'], '1.0.0')
        self.assertEqual(rows[0]['ext_info']['rules_sha256'], payload['rules_sha256'])
        with self.assertRaises(ValueError):
            self.io.prepare(self.record, 'test-model', '9.9.9')

    def test_edited_released_rules_are_refused(self):
        import shutil
        original = self.io.SKILL_DIR
        copy_dir = Path(self.tmp.name) / 'skill'
        shutil.copytree(original, copy_dir, ignore=shutil.ignore_patterns('__pycache__'))
        version = self.io.newest_version()
        rules = copy_dir / 'rules' / self.io.rules_manifest()['versions'][version]['rules']
        rules.write_text(rules.read_text() + '\nEdited.\n')
        self.io.SKILL_DIR = copy_dir
        self.addCleanup(setattr, self.io, 'SKILL_DIR', original)
        with self.assertRaises(ValueError):
            self.io.prepare(self.record, 'test-model')
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_payload_without_rules_hash_from_older_tooling_still_validates(self):
        del self.payload['rules_sha256']
        rows = self.io.validate(self.record, self.payload)
        self.assertEqual(rows[0]['ext_info']['rules_sha256'],
                         self.io.resolve_rules(self.payload['skill_version'])[1])

    def test_rules_2_require_a_matching_rule_id_per_candidate(self):
        self.payload = self.pinned('2.0.0')
        self.assertTrue({'A1', 'A6', 'X1', 'X14', 'D1'} <= self.io.rule_ids('2.0.0'))
        self.assertEqual(self.io.rule_ids('1.0.0'), set())
        self.io.validate(self.record, self.payload)
        for rule in (None, 'X1', 'A99'):
            payload = copy.deepcopy(self.payload)
            payload['candidates'][0]['rule_id'] = rule
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)
        self.payload['candidates'].append({'candidate_id': 'c2', 'decision': 'excluded',
                                           'source_line_spans': ['1'], 'rule_id': 'X14',
                                           'reason': 'Heading only.'})
        self.io.validate(self.record, self.payload)

    def test_rules_2_bounds_tags_and_definitions(self):
        self.payload = self.pinned('2.0.0')
        metric = self.payload['metrics'][0]
        for field, value in (('metric_value', '≥0.5'), ('metric_value', '<100')):
            payload = copy.deepcopy(self.payload)
            payload['metrics'][0][field] = value
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)
        metric['reasoning_tags'] = ['has_threshold', 'strict_bound', 'test_condition']
        self.io.validate(self.record, self.payload)
        for mutate in (
            lambda m: m.update(value_range_type='exact'),
            lambda m: m.update(value_class='definition'),
            lambda m: m.update(value_range_type='qualitative', metric_value='', metric_unit='',
                               is_explicit_metric=False, reasoning_tags=['test_condition'])):
            payload = copy.deepcopy(self.payload)
            mutate(payload['metrics'][0])
            with self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_rules_2_0_payloads_need_no_statement_kind(self):
        payload = self.pinned('2.0.0')
        payload['metrics'][0]['reasoning_tags'] = ['has_threshold']
        self.io.validate(self.record, payload)

    def test_statement_kind_matches_the_application_classifier(self):
        cases = (
            ({'value_class': 'requirement', 'value_range_type': 'upper_bound'}, 'requirement_with_criterion'),
            ({'value_class': 'target', 'value_range_type': 'exact'}, 'requirement_with_criterion'),
            ({'value_class': 'requirement', 'value_range_type': 'limit_absent'}, 'requirement_value_open'),
            ({'value_class': 'requirement', 'value_range_type': 'qualitative'}, 'inspection_requirement'),
            ({'value_class': 'reference', 'value_range_type': 'qualitative',
              'reasoning_tags': ['cited_doc:CJJ 52']}, 'delegated_requirement'),
            ({'value_class': 'requirement', 'value_range_type': 'exact',
              'reasoning_tags': ['test_condition']}, 'test_parameter'),
            ({'value_class': 'definition', 'value_range_type': 'upper_bound',
              'formula_or_definition': 'GI < 100% means phytotoxic'}, 'metric_definition'),
            ({'value_class': 'definition', 'value_range_type': 'qualitative'}, 'definition'),
            ({'value_class': 'observation', 'value_range_type': 'exact'}, 'metric_value'),
            ({'value_class': 'design_capability', 'value_range_type': 'qualitative'}, 'observation'),
            ({'value_class': 'other', 'value_range_type': 'exact'}, 'unclassified'),
        )
        for fields, kind in cases:
            row = {'reasoning_tags': [], 'formula_or_definition': '', **fields}
            with self.subTest(row=row):
                self.assertEqual(self.io.statement_kind(row), kind)

    def test_rules_2_1_require_a_matching_statement_kind(self):
        self.payload = self.pinned('2.1.0')
        self.io.validate(self.record, self.payload)
        for tags in (['has_threshold'],
                     ['kind:requirement_with_criterion', 'kind:metric_value'],
                     ['kind:inspection_requirement'],
                     ['kind:not_a_kind']):
            payload = copy.deepcopy(self.payload)
            payload['metrics'][0]['reasoning_tags'] = tags
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                self.io.validate(self.record, payload)

    def test_rules_2_1_interpretation_cutoff_is_a_definition_bound(self):
        metric = self.payload['metrics'][0]
        metric.update(value_class='definition', formula_or_definition='≥ 0.5 MPa reads as adequate',
                      reasoning_tags=['interpretation_bound', 'kind:metric_definition'])
        self.io.validate(self.record, self.payload)
        payload = copy.deepcopy(self.payload)
        payload['metrics'][0].update(value_class='reference', formula_or_definition='',
                                     reasoning_tags=['interpretation_bound', 'kind:metric_value'])
        with self.assertRaises(ValueError):
            self.io.validate(self.record, payload)

    def test_rules_2_1_cited_doc_identifier_has_a_space(self):
        clause = 'Backup facilities shall comply with NY884.'
        self.source.write_text(
            '1\t1\theading\tArial\t12\t[0,0,100,20]\tPump requirements\n'
            f'2\t1\tparagraph\tArial\t10\t[0,20,100,40]\t{clause}\n', encoding='utf-8')
        self.payload = self.pinned('2.1.0')
        self.payload['metrics'][0].update(
            metric_name='Backup facilities', metric_subject='Backup facilities',
            value_range_type='qualitative', value_class='reference', metric_unit='', metric_value='',
            is_explicit_metric=False, threshold_or_target=clause,
            reasoning_tags=['external_reference', 'cited_doc:NY 884', 'kind:delegated_requirement'],
            evidence=[{'line': 2, 'quote': clause}])
        self.io.validate(self.record, self.payload)
        self.payload['metrics'][0]['reasoning_tags'][1] = 'cited_doc:NY884'
        with self.assertRaises(ValueError):
            self.io.validate(self.record, self.payload)

    def test_rules_3_retire_a2_a3_as_x15_x16(self):
        for version in ('3.0.0', '3.1.0', '4.0.0'):
            with self.subTest(version=version):
                self.assertTrue({'X15', 'X16'} <= self.io.rule_ids(version))
                self.assertFalse({'A2', 'A3'} & self.io.rule_ids(version))
                base = self.pinned(version)
                base['candidates'].append({'candidate_id': 'c2', 'decision': 'excluded',
                                           'metric_ids': [], 'source_line_spans': ['2'],
                                           'rule_id': 'X15', 'reason': 'Pump housing shall be sealed.'})
                self.io.validate(self.record, base)
                for rule in ('A2', 'A3'):
                    payload = copy.deepcopy(base)
                    payload['candidates'][0]['rule_id'] = rule
                    with self.subTest(rule=rule), self.assertRaises(ValueError):
                        self.io.validate(self.record, payload)

    def test_rules_4_sizing_duty_is_x17(self):
        self.assertIn('X17', self.io.rule_ids('4.0.0'))
        self.assertNotIn('X17', self.io.rule_ids('3.1.0'))
        base = self.pinned('4.0.0')
        base['candidates'].append({'candidate_id': 'c2', 'decision': 'excluded', 'metric_ids': [],
                                   'source_line_spans': ['2'], 'rule_id': 'X17',
                                   'reason': 'Tank volume sized for daily throughput; no value.'})
        self.io.validate(self.record, base)
        old = self.pinned('3.1.0')
        old['candidates'].append(dict(base['candidates'][-1]))
        with self.assertRaises(ValueError):
            self.io.validate(self.record, old)

    def test_rules_3_refuse_rows_with_nothing_to_measure(self):
        clause = 'Backup facilities shall comply with CJJ 27.'
        self.source.write_text(
            '1\t1\theading\tArial\t12\t[0,0,100,20]\tPump requirements\n'
            f'2\t1\tparagraph\tArial\t10\t[0,20,100,40]\t{clause}\n', encoding='utf-8')
        delegated = dict(metric_name='Backup facilities', metric_subject='Backup facilities',
                         value_range_type='qualitative', value_class='reference', metric_unit='',
                         metric_value='', is_explicit_metric=False, threshold_or_target=clause,
                         reasoning_tags=['external_reference', 'cited_doc:CJJ 27',
                                         'kind:delegated_requirement'],
                         evidence=[{'line': 2, 'quote': clause}])
        inspection = dict(delegated, value_class='requirement',
                          reasoning_tags=['kind:inspection_requirement'])
        for fields, rule in ((delegated, 'A3'), (inspection, 'A2')):
            old = self.pinned('2.1.0')
            old['metrics'][0].update(copy.deepcopy(fields))
            old['candidates'][0]['rule_id'] = rule
            self.io.validate(self.record, old)
            new = self.pinned('3.0.0')
            new['metrics'][0].update(copy.deepcopy(fields))
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                self.io.validate(self.record, new)
        # A delegation stored as a value-open requirement (how extract_metrics escaped its filter
        # on record 416) is still refused: its cited_doc tag makes it a delegation.
        disguised = self.pinned('3.0.0')
        disguised['metrics'][0].update(copy.deepcopy(delegated))
        disguised['metrics'][0].update(value_class='requirement', value_range_type='limit_absent',
                                       reasoning_tags=['cited_doc:CJJ 27', 'kind:requirement_value_open'])
        with self.assertRaises(ValueError):
            self.io.validate(self.record, disguised)

    def test_rules_1_payloads_keep_their_original_checks(self):
        payload = self.io.prepare(self.record, 'test-model', '1.0.0')
        payload.update({k: copy.deepcopy(self.payload[k]) for k in ('language', 'completeness_review',
                        'correctness_review', 'coverage', 'candidates', 'metrics')})
        del payload['candidates'][0]['rule_id']
        payload['metrics'][0]['metric_value'] = '≥0.5'
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
