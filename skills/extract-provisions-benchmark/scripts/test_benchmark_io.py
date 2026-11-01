import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


TABLE = ('<table><tr><td>处理模式</td><td>技术要求</td></tr>'
         '<tr><td>卫生填埋</td><td>处理技术应符合GB 50869的要求。</td></tr></table>')
LINES = [
    (1, 'paragraph', '本标准适用于农村生活垃圾分类处理。'),
    (2, 'heading-2', '7.1 投放要求'),
    (3, 'list-item', '7.1.1 垃圾分类收集容器应有盖，应在显著位置印制垃圾分类标志。'),
    (4, 'list-item', '7.1.2 可回收物运输至资源回收处理单位。也可预约上门'),
    (5, 'paragraph', '收集。'),
    (6, 'table', TABLE),
]


def prov(pid, **fields):
    row = {'prov_id': pid, 'section': '7.1 投放要求', 'source_line_spans': ['3'], 'source_table_rows': [],
           'evidence': [{'line': 3, 'quote': '垃圾分类收集容器应有盖'}],
           'provision': '垃圾分类收集容器应有盖，应在显著位置印制垃圾分类标志。', 'provision_en': '',
           'prov_name': '容器有盖', 'prov_name_en': 'Containers have lids',
           'provision_type': 'mandatory', 'provision_kind': 'requirement',
           'provision_subject': '垃圾分类收集容器', 'provision_subject_en': 'Collection container',
           'location_type': 'bullet', 'is_explicit': True, 'confidence': 0.9}
    row.update(fields)
    return row


class BenchmarkIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('benchmark_io.py')
        spec = importlib.util.spec_from_file_location('provision_benchmark_io', path)
        cls.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.io)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.record = {'id': 123, 'result_filename': str(root / 'waste.json'),
                       'staging_filename': 'waste.pdf', 'parser_name': 'mineru',
                       'title': '农村生活垃圾分类处理规范', 'doc_metadata': {}}
        self.source = root / 'waste_mineru.txt'
        self.source.write_text(''.join(f'{n}\t1\t{kind}\tSimSun\t10\t[0,0,100,20]\t{text}\n'
                                       for n, kind, text in LINES), encoding='utf-8')
        self.payload = self.io.prepare(self.record, 'test-model')
        self.payload.update(language='zh', completeness_review='Read every line; marker search done.',
                            correctness_review='Checked kinds and subjects. Consistency: none.')
        self.payload['coverage'] = [{'source_line_spans': ['1-6'], 'reason': 'Whole document reviewed.'}]
        self.payload['candidates'] = [
            {'candidate_id': 'c1', 'decision': 'excluded', 'rule_id': 'X2', 'prov_ids': [],
             'source_line_spans': ['1'], 'text': '本标准适用于农村生活垃圾分类处理。', 'reason': 'Scope.'},
            {'candidate_id': 'c2', 'decision': 'accepted', 'rule_id': 'A1', 'prov_ids': ['123_gprv_1'],
             'source_line_spans': ['3'], 'text': '垃圾分类收集容器应有盖', 'reason': '应.'},
            {'candidate_id': 'c3', 'decision': 'accepted', 'rule_id': 'A5', 'prov_ids': ['123_gprv_2'],
             'source_line_spans': ['4'], 'text': '可回收物运输至资源回收处理单位。', 'reason': 'Implicit.'},
            {'candidate_id': 'c4', 'decision': 'accepted', 'rule_id': 'A4', 'prov_ids': ['123_gprv_3'],
             'source_line_spans': ['4-5'], 'text': '也可预约上门收集。', 'reason': 'Permission.'},
            {'candidate_id': 'c5', 'decision': 'accepted', 'rule_id': 'A1', 'prov_ids': ['123_gprv_4'],
             'source_line_spans': ['6'], 'text': '处理技术应符合GB 50869的要求。', 'reason': 'Table cell.'},
        ]
        self.payload['provisions'] = [
            prov('123_gprv_1'),
            prov('123_gprv_2', source_line_spans=['4'], provision='可回收物运输至资源回收处理单位。',
                 evidence=[{'line': 4, 'quote': '可回收物运输至资源回收处理单位。'}],
                 provision_subject='可回收物', location_type='sentence', is_explicit=False),
            prov('123_gprv_3', source_line_spans=['4-5'], provision='也可预约上门收集',
                 evidence=[{'line': 4, 'quote': '也可预约上门'}, {'line': 5, 'quote': '收集。'}],
                 provision_type='optional', provision_kind='permission', location_type='sentence'),
            prov('123_gprv_4', source_line_spans=['6'], provision='处理技术应符合GB 50869的要求。',
                 source_table_rows=[{'line': 6, 'rows': ['r1']}], section='9.2 处理模式',
                 evidence=[{'line': 6, 'quote': '处理技术应符合GB 50869的要求。'}],
                 provision_subject='处理技术', location_type='table_cell'),
        ]

    def validate(self, payload=None):
        return self.io.validate(self.record, payload or self.payload)

    def broken(self, mutate):
        payload = copy.deepcopy(self.payload)
        mutate(payload)
        return payload

    def test_valid_payload_produces_rows(self):
        rows = self.validate()
        self.assertEqual([r['prov_id'] for r in rows], ['123_gprv_1', '123_gprv_2', '123_gprv_3', '123_gprv_4'])
        self.assertEqual(rows[0]['ext_info']['candidate_ids'], ['c2'])
        self.assertEqual(rows[2]['evidence'], '也可预约上门 收集。')

    def test_kind_type_mismatch_is_refused(self):
        payload = self.broken(lambda p: p['provisions'][2].update(provision_type='mandatory'))
        with self.assertRaisesRegex(ValueError, 'means provision_type optional'):
            self.validate(payload)

    def test_table_line_needs_table_location(self):
        payload = self.broken(lambda p: p['provisions'][3].update(location_type='sentence'))
        with self.assertRaisesRegex(ValueError, 'table_row or table_cell'):
            self.validate(payload)

    def test_table_location_on_text_line_is_refused(self):
        payload = self.broken(lambda p: p['provisions'][0].update(location_type='table_cell'))
        with self.assertRaisesRegex(ValueError, 'needs table lines only'):
            self.validate(payload)

    def test_table_provision_needs_rows(self):
        payload = self.broken(lambda p: p['provisions'][3].update(source_table_rows=[]))
        with self.assertRaisesRegex(ValueError, 'names its source_table_rows'):
            self.validate(payload)

    def test_paraphrased_provision_is_refused(self):
        payload = self.broken(lambda p: p['provisions'][0].update(provision='收集容器必须有盖子'))
        with self.assertRaisesRegex(ValueError, 'not source text'):
            self.validate(payload)

    def test_non_contiguous_parts(self):
        payload = self.broken(lambda p: p['provisions'][0].update(provision='垃圾分类收集容器应有盖 … 印制垃圾分类标志'))
        self.validate(payload)
        payload['provisions'][0]['provision'] = '垃圾分类收集容器应有盖印制垃圾分类标志'
        with self.assertRaisesRegex(ValueError, 'not source text'):
            self.validate(payload)

    def test_uncovered_line_is_refused(self):
        payload = self.broken(lambda p: p['coverage'][0].update(source_line_spans=['1-5']))
        with self.assertRaisesRegex(ValueError, 'Coverage does not account'):
            self.validate(payload)

    def test_colon_spans_are_refused(self):
        payload = self.broken(lambda p: p['provisions'][2].update(source_line_spans=['4:5']))
        with self.assertRaisesRegex(ValueError, 'use N or N-M'):
            self.validate(payload)

    def test_rule_prefix_must_match_decision(self):
        payload = self.broken(lambda p: p['candidates'][0].update(rule_id='A1'))
        with self.assertRaisesRegex(ValueError, 'must be a X rule'):
            self.validate(payload)

    def test_unknown_rule_is_refused(self):
        payload = self.broken(lambda p: p['candidates'][0].update(rule_id='X99'))
        with self.assertRaisesRegex(ValueError, 'rule_id'):
            self.validate(payload)

    def test_every_provision_needs_accepted_candidate(self):
        payload = self.broken(lambda p: p['candidates'].pop(1))
        with self.assertRaisesRegex(ValueError, 'Every provision needs an accepted candidate'):
            self.validate(payload)

    def test_english_companions_required_for_chinese(self):
        payload = self.broken(lambda p: p['provisions'][0].update(provision_subject_en=None))
        with self.assertRaisesRegex(ValueError, 'provision_subject_en required'):
            self.validate(payload)

    def test_duplicate_provision_is_refused(self):
        payload = self.broken(lambda p: p['provisions'].append(prov('123_gprv_5')))
        payload['candidates'][1]['prov_ids'].append('123_gprv_5')
        with self.assertRaisesRegex(ValueError, 'duplicate provision'):
            self.validate(payload)

    def test_prov_id_format(self):
        payload = self.broken(lambda p: p['provisions'][0].update(prov_id='123_prv_1'))
        payload['candidates'][1]['prov_ids'] = ['123_prv_1']
        with self.assertRaisesRegex(ValueError, '123_gprv_<n>'):
            self.validate(payload)

    def test_limitations_block_saving(self):
        payload = self.broken(lambda p: p.update(limitations=['parser damage on line 4']))
        with self.assertRaisesRegex(ValueError, 'limitations'):
            self.validate(payload)

    def test_edited_rules_are_refused(self):
        original = self.io.rules_manifest

        def tampered():
            manifest = original()
            manifest['versions']['1.0.0']['sha256'] = '0' * 64
            return manifest
        self.io.rules_manifest = tampered
        self.addCleanup(setattr, self.io, 'rules_manifest', original)
        with self.assertRaisesRegex(ValueError, 'released rules are frozen'):
            self.io.resolve_rules('1.0.0')

    def test_save_sql_shape(self):
        rows = self.validate()
        sql = self.io.save_sql(self.record, self.payload, rows)
        self.assertTrue(sql.startswith('BEGIN;') and sql.rstrip().endswith('COMMIT;'))
        self.assertIn('INSERT INTO testbed.provision_benchmark_runs', sql)
        self.assertIn('INSERT INTO testbed.provisions (', sql)
        self.assertIn('INSERT INTO testbed.provisions_dropped', sql)
        self.assertIn('benchmark_run_key_unused', sql)
        self.assertNotIn('kb.provisions', sql)


if __name__ == '__main__':
    unittest.main()
