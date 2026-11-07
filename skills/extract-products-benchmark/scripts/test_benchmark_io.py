import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


TABLE = ('<table><tr><td>项目</td><td>技术指标</td></tr>'
         '<tr><td>有机质的质量分数，%</td><td>≥30</td></tr>'
         '<tr><td>水分的质量分数，%</td><td>≤30</td></tr></table>')
SPAN_TABLE = ('<table><tr><td>序号</td><td>类型</td><td>模式</td></tr>'
              '<tr><td rowspan="2">1</td><td rowspan="2">易腐垃圾</td><td>堆肥</td></tr>'
              '<tr><td>沼气</td></tr></table>')
LINES = [
    (1, 'paragraph', 'NY 884 生物有机肥'),
    (2, 'list-item', '7.1.1 垃圾分类收集容器应有盖，应在显著位置印制垃圾分类标志。'),
    (3, 'list-item', '电视机、冰箱、电话'),
    (4, 'paragraph', '机等废弃电器电子产品；'),
    (5, 'list-item', '8.2.2 收运单位应配备相应的收集、运输设备。'),
    (6, 'paragraph', '机器成肥产出的肥料其他指标应达到表 2的要求。'),
    (7, 'table', TABLE),
    (8, 'table', SPAN_TABLE),
]


def item(rid, key, **fields):
    row = {'product_rel_id': rid, 'product_key': key, 'section': '7.1 投放要求',
           'product_name': '垃圾分类收集容器', 'product_name_en': 'Sorted waste collection container',
           'canonical_name': '垃圾分类收集容器', 'canonical_name_en': 'Sorted waste collection container',
           'product_type': 'equipment', 'relation_type': 'design_requirement',
           'relation_summary': '文件要求收集容器有盖。', 'evidence_quote': '垃圾分类收集容器应有盖',
           'evidence_lines': ['2'], 'obligation_level': 'mandatory',
           'requirement_text': '垃圾分类收集容器应有盖', 'conditions': [], 'exceptions': [],
           'parameters': [], 'related_products': [], 'responsible_actor': '', 'confidence': 0.9,
           'rule_id': 'R1'}
    row.update(fields)
    return row


class BenchmarkIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('benchmark_io.py')
        spec = importlib.util.spec_from_file_location('product_benchmark_io', path)
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
        self.payload.update(language='zh', completeness_review='Read every line; head-noun search done.',
                            correctness_review='Checked names, types and relations. Consistency: none.')
        self.payload['coverage'] = [{'source_line_spans': ['1-8'], 'reason': 'Whole document reviewed.'}]
        self.payload['candidates'] = [
            {'candidate_id': 'c1', 'decision': 'excluded', 'rule_id': 'X2', 'product_keys': [],
             'source_line_spans': ['1'], 'text': '生物有机肥', 'reason': 'Citation only.'},
            {'candidate_id': 'c2', 'decision': 'accepted', 'rule_id': 'A1', 'product_keys': ['123_gp_1'],
             'source_line_spans': ['2'], 'text': '垃圾分类收集容器', 'reason': 'A container.'},
            {'candidate_id': 'c3', 'decision': 'accepted', 'rule_id': 'A1', 'product_keys': ['123_gp_2'],
             'source_line_spans': ['3-4'], 'text': '电话机', 'reason': 'Appliance split over two lines.'},
            {'candidate_id': 'c4', 'decision': 'accepted', 'rule_id': 'A1',
             'product_keys': ['123_gp_3', '123_gp_4'], 'source_line_spans': ['5'], 'text': '收集、运输设备',
             'reason': 'Elided coordination.'},
            {'candidate_id': 'c5', 'decision': 'accepted', 'rule_id': 'A4', 'product_keys': ['123_gp_5'],
             'source_line_spans': ['6'], 'text': '肥料', 'reason': 'A fertilizer.'},
            {'candidate_id': 'c6', 'decision': 'excluded', 'rule_id': 'X5', 'product_keys': [],
             'source_line_spans': ['7#r1'], 'text': '有机质', 'reason': 'A measured property.'},
            {'candidate_id': 'c7', 'decision': 'accepted', 'rule_id': 'A3', 'product_keys': ['123_gp_6'],
             'source_line_spans': ['8#r2'], 'text': '易腐垃圾', 'reason': 'Waste category.'},
        ]
        self.payload['products'] = [
            item('123_gprd_1', '123_gp_1'),
            item('123_gprd_2', '123_gp_1', relation_type='certification_requirement',
                 relation_summary='文件要求收集容器印制分类标志。', evidence_quote='应在显著位置印制垃圾分类标志',
                 requirement_text='应在显著位置印制垃圾分类标志'),
            item('123_gprd_3', '123_gp_2', product_name='电话机', product_name_en='Telephone',
                 canonical_name='电话机', canonical_name_en='Telephone', product_type='specific_product',
                 relation_type='scope', relation_summary='电话机属于废弃电器电子产品。', evidence_quote='电话',
                 evidence_lines=['3-4'], obligation_level='descriptive', requirement_text='', rule_id='R7'),
            item('123_gprd_4', '123_gp_3', product_name='收集设备', product_name_en='Collection equipment',
                 canonical_name='收集设备', canonical_name_en='Collection equipment',
                 relation_type='requirement_target', relation_summary='收运单位应配备收集设备。',
                 evidence_quote='应配备相应的收集、运输设备', evidence_lines=['5'],
                 requirement_text='收运单位应配备相应的收集、运输设备', responsible_actor='收运单位',
                 rule_id='R2', name_expanded=True, name_source='收集、运输设备'),
            item('123_gprd_5', '123_gp_4', product_name='运输设备', product_name_en='Transport equipment',
                 canonical_name='运输设备', canonical_name_en='Transport equipment',
                 relation_type='requirement_target', relation_summary='收运单位应配备运输设备。',
                 evidence_quote='应配备相应的收集、运输设备', evidence_lines=['5'],
                 requirement_text='收运单位应配备相应的收集、运输设备', responsible_actor='收运单位',
                 rule_id='R2'),
            item('123_gprd_6', '123_gp_5', product_name='肥料', product_name_en='Fertilizer',
                 canonical_name='肥料', canonical_name_en='Fertilizer', product_type='material',
                 relation_type='performance_requirement', relation_summary='肥料指标应达到表 2。',
                 evidence_quote='机器成肥产出的肥料其他指标应达到表 2的要求',
                 evidence_lines=['6', '7#h0', '7#r1', '7#r2'],
                 requirement_text='机器成肥产出的肥料其他指标应达到表 2的要求',
                 parameters=[{'name': '有机质的质量分数', 'value': '≥30', 'unit': '%'},
                             {'name': '水分的质量分数', 'value': '≤30', 'unit': '%'}]),
            item('123_gprd_7', '123_gp_6', product_name='易腐垃圾', product_name_en='Biodegradable waste',
                 canonical_name='易腐垃圾', canonical_name_en='Biodegradable waste', product_type='product_class',
                 relation_type='scope', relation_summary='表中列出易腐垃圾的处理模式。', evidence_quote='易腐垃圾',
                 evidence_lines=['8#r2'], obligation_level='descriptive', requirement_text='', rule_id='R7'),
        ]

    def validate(self, payload=None):
        return self.io.validate(self.record, payload or self.payload)

    def broken(self, mutate):
        payload = copy.deepcopy(self.payload)
        mutate(payload)
        return payload

    def refused(self, mutate, message):
        with self.assertRaisesRegex(ValueError, message):
            self.validate(self.broken(mutate))

    def test_valid_payload_produces_rows(self):
        rows = self.validate()
        self.assertEqual([r['product_rel_id'] for r in rows], [f'123_gprd_{n}' for n in range(1, 8)])
        self.assertEqual(rows[0]['ext_info']['candidate_ids'], ['c2'])
        self.assertEqual(rows[3]['ext_info']['name_source'], '收集、运输设备')
        self.assertIsNone(rows[0]['relation_summary_en'] or None)

    def test_table_grid_matches_parse_table_grid(self):
        grid = self.io.parse_table_grid(SPAN_TABLE)
        self.assertEqual(grid, {'h0': ['序号', '类型', '模式'], 'r1': ['1', '易腐垃圾', '堆肥'],
                                'r2': ['1', '易腐垃圾', '沼气']})
        th = '<table><tr><th>a</th><th>b</th></tr><tr><th>c</th><th>d</th></tr><tr><td>1</td><td>2</td></tr></table>'
        self.assertEqual(list(self.io.parse_table_grid(th)), ['h0', 'h1', 'r1'])
        self.assertIsNone(self.io.parse_table_grid('no table'))

    def test_type_mismatch_within_product_is_refused(self):
        self.refused(lambda p: p['products'][1].update(product_type='packaging'),
                     'must share product_name, canonical_name and product_type')

    def test_repeated_relation_within_product_is_refused(self):
        self.refused(lambda p: p['products'][1].update(relation_type='design_requirement'),
                     'already has a design_requirement row')

    def test_relation_needs_its_rule(self):
        self.refused(lambda p: p['products'][0].update(rule_id='R2'), 'decided by rule R1')

    def test_unknown_vocabulary_is_refused(self):
        self.refused(lambda p: p['products'][0].update(product_type='unknown'), 'unknown product_type')
        self.refused(lambda p: p['products'][0].update(relation_type='facility'), 'unknown relation_type')
        self.refused(lambda p: p['products'][0].update(obligation_level='unknown'), 'obligation_level must be')

    def test_related_products_only_for_inter_product_relations(self):
        self.refused(lambda p: p['products'][2].update(
            related_products=[{'product_name': '电器电子产品', 'relationship': 'component_of'}]),
            'related_products is nonempty exactly')
        self.refused(lambda p: p['products'][0].update(relation_type='component_of', rule_id='R4'),
                     'related_products is nonempty exactly')

    def test_paraphrased_requirement_text_is_refused(self):
        self.refused(lambda p: p['products'][0].update(requirement_text='收集容器必须有盖子'), 'not source text')

    def test_requirement_text_parts(self):
        payload = self.broken(lambda p: p['products'][0].update(
            requirement_text='垃圾分类收集容器应有盖 … 印制垃圾分类标志'))
        self.validate(payload)

    def test_descriptive_rows(self):
        self.refused(lambda p: p['products'][2].update(requirement_text='电话'), 'descriptive row has no requirement_text')
        self.refused(lambda p: p['products'][2].update(obligation_level='mandatory', requirement_text='电话'),
                     'scope row is descriptive')
        self.refused(lambda p: p['products'][0].update(requirement_text=''), 'needs requirement_text')

    def test_name_must_be_source_text_unless_expanded(self):
        self.refused(lambda p: p['products'][3].update(name_expanded=False), 'product_name does not occur')
        self.refused(lambda p: p['products'][3].update(name_source='收集运输车辆'), 'name_source')

    def test_evidence_quote_must_be_in_one_unit(self):
        self.refused(lambda p: p['products'][0].update(evidence_quote='容器应有盖子'), 'evidence_quote')

    def test_table_line_must_be_cited_by_rows(self):
        self.refused(lambda p: p['products'][5].update(evidence_lines=['6', '7']), 'by rows')
        self.refused(lambda p: p['products'][5].update(evidence_lines=['6-7']), 'by rows')

    def test_unknown_table_row_is_refused(self):
        self.refused(lambda p: p['products'][5].update(evidence_lines=['6', '7#r9']), 'does not exist')
        self.refused(lambda p: p['products'][0].update(evidence_lines=['2#r1']), 'non-table line')

    def test_parameter_shape(self):
        self.refused(lambda p: p['products'][5].update(parameters=[{'name': '水分', 'value': ''}]), 'parameter')
        self.refused(lambda p: p['products'][5].update(parameters=[{'name': '水分', 'value': '≤30', 'unit': ''}]),
                     'unit is a nonempty string or null')

    def test_uncovered_line_is_refused(self):
        self.refused(lambda p: p['coverage'][0].update(source_line_spans=['1-7']), 'Coverage does not account')

    def test_rule_prefix_must_match_decision(self):
        self.refused(lambda p: p['candidates'][0].update(rule_id='A1'), 'must be a X rule')

    def test_unknown_rule_is_refused(self):
        self.refused(lambda p: p['candidates'][0].update(rule_id='X99'), 'rule_id')

    def test_every_product_needs_accepted_candidate(self):
        self.refused(lambda p: p['candidates'].pop(1), 'Every product_key needs an accepted candidate')

    def test_excluded_candidate_links_nothing(self):
        self.refused(lambda p: p['candidates'][0].update(product_keys=['123_gp_1']), 'references a product')

    def test_english_companions_required_for_chinese(self):
        self.refused(lambda p: p['products'][0].update(product_name_en=None), 'product_name_en required')

    def test_id_formats(self):
        self.refused(lambda p: p['products'][0].update(product_rel_id='123_prd_1'), '123_gprd_<n>')
        self.refused(lambda p: p['products'][0].update(product_key='123_p_1'), '123_gp_<n>')

    def test_limitations_block_saving(self):
        self.refused(lambda p: p.update(limitations=['parser damage on line 4']), 'limitations')

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

    def test_default_version_skips_prereleases(self):
        manifest = {'versions': {'1.0.0': {}, '2.0.0-rc.1': {}, '1.10.0': {}}}
        self.assertEqual(self.io.newest_version(manifest), '1.10.0')

    def test_save_sql_shape(self):
        rows = self.validate()
        sql = self.io.save_sql(self.record, self.payload, rows)
        self.assertTrue(sql.startswith('BEGIN;') and sql.rstrip().endswith('COMMIT;'))
        self.assertIn('INSERT INTO testbed.product_benchmark_runs', sql)
        self.assertIn('INSERT INTO testbed.products (', sql)
        self.assertIn('INSERT INTO testbed.products_dropped', sql)
        self.assertIn('benchmark_run_key_unused', sql)
        self.assertNotIn('kb.products', sql)
        self.assertNotIn('kb.product_names', sql)


if __name__ == '__main__':
    unittest.main()
