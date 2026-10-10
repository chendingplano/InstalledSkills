import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


LINES = [
    (1, 'text', 'GB/T 46121—2025 堆肥技术规范'),
    (2, 'heading', '2 规范性引用文件'),
    (3, 'text', 'GB 7959 粪便无害化卫生要求'),
    (4, 'text', 'CJJ 184 餐厨垃圾处理技术规范'),
    (5, 'heading', '5 技术要求'),
    (6, 'text', '5.1 粪大肠菌群数应符合GB 7959的要求，其他指标应符合表1的规定。'),
]


def ref(rid, **fields):
    row = {'ref_id': rid, 'section': '', 'source_line_spans': ['3'], 'source_table_rows': [],
           'evidence': [], 'ref_form': 'in_text', 'list_kind': '', 'list_label': '',
           'list_entry_ref_id': '', 'normativity': 'unlisted', 'in_requirement': False,
           'list_mismatch': '', 'mechanism': 'standard_number', 'cited_raw': '', 'identifiers': [],
           'target_type': 'standard', 'target_subtype': 'national_standard', 'target_subtype_label': '',
           'target_title': '', 'target_version': '', 'relationships': ['references'],
           'target_scope': 'document', 'target_locator': '', 'target_content': 'general',
           'metric_name': '', 'metric_name_en': None, 'metric_subject': '', 'metric_subject_en': None,
           'condition': '', 'internal': False, 'confidence': 1.0}
    row.update(fields)
    return row


class BenchmarkIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('benchmark_io.py')
        spec = importlib.util.spec_from_file_location('reference_benchmark_io', path)
        cls.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.io)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.record = {'id': 123, 'result_filename': str(root / 'compost.json'),
                       'staging_filename': 'compost.pdf', 'parser_name': 'mineru',
                       'title': '堆肥技术规范', 'doc_metadata': {}}
        self.source = root / 'compost_mineru.txt'
        self.source.write_text(''.join(f'{n}\t1\t{kind}\tSimSun\t10\t[0,0,100,20]\t{text}\n'
                                       for n, kind, text in LINES), encoding='utf-8')
        self.payload = self.io.prepare(self.record, 'test-model')
        self.payload.update(language='zh', document_identifier='GB/T 46121-2025',
                            completeness_review='Read every line; searched prefixes and 表 pointers.',
                            correctness_review='Checked labels and identifiers. Consistency: none.')
        self.payload['coverage'] = [{'source_line_spans': ['1:6'], 'reason': 'Whole document reviewed.'}]
        self.payload['candidates'] = [
            {'candidate_id': 'c1', 'decision': 'accepted', 'rule_id': 'A2', 'ref_ids': ['123_gref_1'],
             'source_line_spans': ['3'], 'cited_raw': 'GB 7959', 'reason': 'Normative list entry.'},
            {'candidate_id': 'c2', 'decision': 'accepted', 'rule_id': 'A2', 'ref_ids': ['123_gref_2'],
             'source_line_spans': ['4'], 'cited_raw': 'CJJ 184', 'reason': 'Normative list entry.'},
            {'candidate_id': 'c3', 'decision': 'accepted', 'rule_id': 'A1', 'ref_ids': ['123_gref_3'],
             'source_line_spans': ['6'], 'cited_raw': 'GB 7959', 'reason': 'Criterion of one quantity.'},
            {'candidate_id': 'c4', 'decision': 'accepted', 'rule_id': 'A3', 'ref_ids': ['123_gref_4'],
             'source_line_spans': ['6'], 'cited_raw': '表1', 'reason': 'Pointer to table 1.'},
            {'candidate_id': 'c5', 'decision': 'excluded', 'rule_id': 'X2', 'ref_ids': [],
             'source_line_spans': ['1'], 'cited_raw': 'GB/T 46121—2025', 'reason': 'Own number.'},
        ]
        listed = dict(ref_form='listed', list_kind='normative', normativity='normative',
                      section='2 规范性引用文件')
        self.payload['references'] = [
            ref('123_gref_1', source_line_spans=['3'], cited_raw='GB 7959', target_title='粪便无害化卫生要求',
                identifiers=[{'kind': 'standard', 'value': 'GB 7959'}],
                evidence=[{'line': 3, 'quote': 'GB 7959 粪便无害化卫生要求'}], **listed),
            ref('123_gref_2', source_line_spans=['4'], cited_raw='CJJ 184', target_title='餐厨垃圾处理技术规范',
                target_subtype='industry_standard', identifiers=[{'kind': 'standard', 'value': 'CJJ 184'}],
                evidence=[{'line': 4, 'quote': 'CJJ 184 餐厨垃圾处理技术规范'}], list_mismatch='never_cited',
                **listed),
            ref('123_gref_3', section='5 技术要求', source_line_spans=['6'], cited_raw='GB 7959',
                identifiers=[{'kind': 'standard', 'value': 'GB 7959'}], list_entry_ref_id='123_gref_1',
                normativity='normative', in_requirement=True, relationships=['requires'],
                target_scope='data_element', target_content='criterion', metric_name='粪大肠菌群数',
                metric_name_en='Faecal coliform count', metric_subject='堆肥产品',
                metric_subject_en='Compost product',
                evidence=[{'line': 6, 'quote': '粪大肠菌群数应符合GB 7959的要求'}]),
            ref('123_gref_4', section='5 技术要求', source_line_spans=['6'], cited_raw='表1',
                mechanism='structural_reference', internal=True, target_type='document',
                target_subtype='document_element', in_requirement=True, relationships=['requires'],
                target_scope='section', target_locator='表1', target_content='requirements',
                evidence=[{'line': 6, 'quote': '其他指标应符合表1的规定'}]),
        ]

    def validate(self, mutate):
        payload = copy.deepcopy(self.payload)
        mutate(payload)
        return self.io.validate(self.record, payload)

    def refuses(self, mutate, fragment=''):
        with self.assertRaises(ValueError) as caught:
            self.validate(mutate)
        self.assertIn(fragment, str(caught.exception))

    def test_valid_payload(self):
        rows = self.io.validate(self.record, self.payload)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2]['evidence'], '粪大肠菌群数应符合GB 7959的要求')
        self.assertEqual(rows[2]['ext_info']['candidate_ids'], ['c3'])
        self.assertEqual(rows[0]['metric_name_en'], None)
        self.assertEqual(rows[0]['skill_name'], 'extract-references-benchmark')

    def test_normativity_and_links_are_recomputed(self):
        self.refuses(lambda p: p['references'][2].update(normativity='unlisted'), 'normativity')
        self.refuses(lambda p: p['references'][2].update(list_entry_ref_id=''), 'list_entry_ref_id')
        self.refuses(lambda p: p['references'][2].update(list_entry_ref_id='123_gref_2'), 'list_entry_ref_id')
        self.refuses(lambda p: p['references'][1].update(list_mismatch=''), 'never_cited')
        self.refuses(lambda p: p['references'][0].update(list_mismatch='never_cited'), 'list_mismatch')
        self.refuses(lambda p: p['references'][3].update(normativity='normative'), 'normativity')

    def test_not_listed_when_a_normative_list_exists(self):
        def add_unlisted(p):
            p['references'][2].update(identifiers=[{'kind': 'standard', 'value': 'GB 7960'}],
                                      list_entry_ref_id='', normativity='unlisted')
            p['references'][0]['list_mismatch'] = 'never_cited'
        self.refuses(add_unlisted, 'not_listed')

        def flagged(p):
            add_unlisted(p)
            p['references'][2]['list_mismatch'] = 'not_listed'
        self.validate(flagged)

    def test_no_mismatch_without_a_normative_list(self):
        def informative(p):
            for r in p['references'][:2]:
                r.update(list_kind='informative', normativity='informative', list_mismatch='')
            p['references'][2]['normativity'] = 'informative'
        self.validate(informative)

    def test_governed_vocabularies(self):
        self.refuses(lambda p: p['references'][0].update(target_type='norm'), 'target_type')
        self.refuses(lambda p: p['references'][0].update(target_subtype='gb_standard'), 'others')
        self.refuses(lambda p: p['references'][0].update(target_subtype='others'), 'label')
        self.validate(lambda p: p['references'][0].update(target_subtype='others',
                                                          target_subtype_label='gb_standard'))
        self.refuses(lambda p: p['references'][2].update(relationships=['contradicts']), 'asserted')
        self.refuses(lambda p: p['references'][2].update(relationships=['uses', 'requires']), 'sorted')
        self.refuses(lambda p: p['references'][2].update(mechanism='standard'), 'mechanism')
        self.refuses(lambda p: p['references'][2].update(target_content='value'), 'target_content')

    def test_form_internal_and_quantity_constraints(self):
        self.refuses(lambda p: p['references'][3].update(target_content='criteria_set'), 'internal')
        self.refuses(lambda p: p['references'][3].update(mechanism='named_reference'), 'structural_reference')
        self.refuses(lambda p: p['references'][0].update(target_content='requirements'), 'listed entry')
        self.refuses(lambda p: p['references'][2].update(metric_name=''), 'criterion')
        self.refuses(lambda p: p['references'][2].update(metric_name_en=None), 'metric_name_en')
        self.refuses(lambda p: p['references'][3].update(condition='高温'), 'criterion rows only')
        self.refuses(lambda p: p['references'][2].update(list_kind='normative'), 'list_kind')

    def test_identifiers_and_source_text(self):
        self.refuses(lambda p: p['references'][0].update(
            identifiers=[{'kind': 'standard', 'value': 'GB 7959-2012'}]), 'edition')
        self.refuses(lambda p: p['references'][0].update(
            identifiers=[{'kind': 'standard', 'value': 'GB7959'}]), 'one space')
        self.refuses(lambda p: p['references'][0].update(
            identifiers=[{'kind': 'doi', 'value': '10.1/ABC'}]), 'lower-case')
        self.refuses(lambda p: p['references'][3].update(
            identifiers=[{'kind': 'standard', 'value': 'GB 7959'}]), 'no identifiers')
        self.refuses(lambda p: p['references'][2].update(cited_raw='GB 7960'), 'cited_raw')
        self.refuses(lambda p: p['references'][2]['evidence'][0].update(quote='应符合 GB 7959'), 'evidence')

    def test_ledger_coverage_and_publication_blocks(self):
        self.refuses(lambda p: p.update(coverage=[{'source_line_spans': ['2:6'], 'reason': 'Partial'}]),
                     'Coverage')
        self.refuses(lambda p: p['candidates'][0].update(decision='uncertain'), 'unresolved')
        self.refuses(lambda p: p['candidates'][4].update(rule_id='A1'), 'rule_id')
        self.refuses(lambda p: p['candidates'][3].update(ref_ids=[]), 'ref_ids')
        self.refuses(lambda p: p.update(limitations=['Table unreadable']), 'limitations')
        self.refuses(lambda p: p['references'].append(dict(copy.deepcopy(p['references'][2]),
                                                           ref_id='123_gref_5')), 'duplicate')

    def test_changed_source_and_frozen_rules(self):
        self.refuses(lambda p: p.update(source_sha256='0' * 64), 'Source')
        self.refuses(lambda p: p.update(skill_version='9.9.9'), 'Unknown skill version')
        self.assertEqual(self.io.newest_version(), self.payload['skill_version'])
        manifest = self.io.rules_manifest()
        for version, entry in manifest['versions'].items():
            self.assertEqual(self.io.resolve_rules(version)[1], entry['sha256'])

    def test_save_sql_is_one_guarded_transaction(self):
        rows = self.io.validate(self.record, self.payload)
        sql = self.io.save_sql(self.record, self.payload, rows)
        self.assertTrue(sql.startswith('BEGIN;') and sql.rstrip().endswith('COMMIT;'))
        for table in ('testbed.reference_benchmark_runs', 'testbed.ref_mentions', 'testbed.ref_mentions_dropped'):
            self.assertIn(f'INSERT INTO {table}', sql)
        self.assertIn('pg_advisory_xact_lock', sql)
        self.assertIn("'GB/T 46121-2025'", json.dumps(sql, ensure_ascii=False).replace('\\"', "'"))


if __name__ == '__main__':
    unittest.main()
