import copy
import importlib.util
from pathlib import Path
import unittest


def row(rid, lines, name, relation, key=None, **fields):
    out = {'product_rel_id': rid, 'product_name': name, 'product_name_en': name, 'canonical_name': name,
           'canonical_name_en': name, 'product_type': 'equipment', 'relation_type': relation,
           'relation_summary': '', 'evidence_quote': name, 'evidence_lines': lines,
           'obligation_level': 'mandatory', 'requirement_text': '', 'conditions': [], 'exceptions': [],
           'parameters': [], 'related_products': [], 'responsible_actor': '', 'confidence': 0.9}
    if key:
        out.update(product_key=key, section='7.1')
    out.update(fields)
    return out


class ScoreIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('score_io.py')
        spec = importlib.util.spec_from_file_location('product_score_io', path)
        cls.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.io)

    def setUp(self):
        self.inp = {
            'record_id': 1, 'title': 't', 'doc_no': 'd',
            'gold_run': {'skill_version': '1.0.0', 'model_name': 'gold-model', 'benchmark_run_id': '20261108_120000'},
            'extraction': {'model_names': ['m'], 'prompt_names': ['p'], 'created_at': ['a', 'b']},
            'source': {'lines_comparable': True}, 'warnings': [],
            'gold': [row('1_gprd_1', ['89'], '垃圾分类收集容器', 'design_requirement', '1_gp_1',
                         requirement_text='垃圾分类收集容器应有盖'),
                     row('1_gprd_2', ['89'], '垃圾分类收集容器', 'certification_requirement', '1_gp_1',
                         requirement_text='应在显著位置印制垃圾分类标志'),
                     row('1_gprd_3', ['128', '131#r1', '131#r2'], '肥料', 'performance_requirement', '1_gp_2',
                         product_type='material', requirement_text='肥料其他指标应达到表 2的要求',
                         parameters=[{'name': '有机质', 'value': '≥30', 'unit': '%'},
                                     {'name': '水分', 'value': '≤30', 'unit': '%'}]),
                     row('1_gprd_4', ['64'], '报纸', 'scope', '1_gp_3', product_type='specific_product',
                         obligation_level='descriptive')],
            'gold_ledger': [{'candidate_id': 'c9', 'decision': 'excluded', 'rule_id': 'X1', 'text': '垃圾转运站'}],
            'predictions': [row('1_prd_1', ['89'], '垃圾分类收集容器', 'design_requirement',
                                requirement_text='垃圾分类收集容器应有盖'),
                            row('1_prd_2', ['89'], '垃圾分类收集容器', 'certification_requirement',
                                requirement_text='应在显著位置印制垃圾分类标志'),
                            row('1_prd_3', ['128', '131#h0', '131#r1', '131#r2'], '肥料', 'performance_requirement',
                                product_type='material', requirement_text='肥料其他指标应达到表 2的要求',
                                parameters=[{'name': '有机质质量分数', 'value': '≥30', 'unit': '%'},
                                            {'name': '水分（鲜样）', 'value': '≤ 30', 'unit': '%'}]),
                            row('1_prd_4', ['64'], '报纸', 'scope', product_type='specific_product',
                                obligation_level='descriptive'),
                            row('1_prd_5', ['50'], '垃圾转运站', 'requirement_target')],
        }
        self.matches = {
            'pairs': [{'gold': f'1_gprd_{n}', 'pred': f'1_prd_{n}', 'note': ''} for n in range(1, 5)],
            'missed': [],
            'false_positives': [{'pred': '1_prd_5', 'cause': 'gold_excluded', 'gold_candidate_id': 'c9',
                                 'rule_id': 'X1', 'note': 'facility'}],
            'overrides': [],
        }

    def test_weights_normalize(self):
        w = self.io.load_weights()
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertAlmostEqual(w['relation_type'], 0.20)

    def test_perfect_pairs_and_one_false_positive(self):
        result = self.io.score(self.inp, self.matches)
        self.assertTrue(all(p['credit'] == 1.0 for p in result['pairs']))
        self.assertEqual(result['main']['soft_recall'], 1.0)
        self.assertAlmostEqual(result['main']['soft_precision'], 0.8)
        self.assertEqual(result['score'], 89)
        det = result['product_detection']
        self.assertEqual((det['gold_products'], det['predicted_products'], det['detected']), (3, 4, 3))
        self.assertAlmostEqual(det['precision'], 0.75)

    def test_perfect_extraction_scores_100(self):
        self.inp['predictions'].pop()
        self.matches['false_positives'] = []
        result = self.io.score(self.inp, self.matches)
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['product_detection']['f1'], 1.0)

    def test_wrong_relation_keeps_other_checks(self):
        self.inp['predictions'][0]['relation_type'] = 'requirement_target'
        result = self.io.score(self.inp, self.matches)
        pair = result['pairs'][0]
        self.assertFalse(pair['checks']['relation_type'])
        # Applicable checks: relation 20, requirement 15, type 10, name 10, lines 10, obligation 10 = 75.
        self.assertAlmostEqual(pair['credit'], 55 / 75)

    def test_inapplicable_checks_are_left_out(self):
        checks = self.io.field_checks(self.inp['gold'][3], self.inp['predictions'][3])
        self.assertIsNone(checks['requirement_text'])
        self.assertIsNone(checks['parameters'])
        self.assertIsNone(checks['conditions'])
        self.assertIsNone(checks['related_products'])
        self.assertIsNone(checks['responsible_actor'])

    def test_parameters_match_on_value_and_unit(self):
        checks = self.io.field_checks(self.inp['gold'][2], self.inp['predictions'][2])
        self.assertEqual(checks['parameters'], 1.0)
        self.inp['predictions'][2]['parameters'] = [{'name': 'x', 'value': '≥30%', 'unit': ''}]
        checks = self.io.field_checks(self.inp['gold'][2], self.inp['predictions'][2])
        self.assertAlmostEqual(checks['parameters'], 2 / 3)

    def test_table_rows_count_as_lines(self):
        checks = self.io.field_checks(self.inp['gold'][2], self.inp['predictions'][2])
        self.assertEqual(checks['lines'], 1.0)
        self.inp['predictions'][2]['evidence_lines'] = ['131#h0', '131#r1']
        checks = self.io.field_checks(self.inp['gold'][2], self.inp['predictions'][2])
        self.assertAlmostEqual(checks['lines'], 1 / 2)

    def test_extra_relation_detects_product(self):
        self.matches['pairs'] = self.matches['pairs'][1:]
        self.matches['missed'] = [{'gold': '1_gprd_1', 'note': 'no design row'}]
        self.inp['predictions'][0]['relation_type'] = 'usage_condition'
        self.matches['false_positives'].append({'pred': '1_prd_1', 'cause': 'extra_relation', 'gold': '1_gprd_1'})
        result = self.io.score(self.inp, self.matches)
        self.assertEqual(result['product_detection']['detected'], 3)
        self.assertFalse(result['missed'][0]['product_missed'])

    def test_missed_product(self):
        self.matches['pairs'] = self.matches['pairs'][:3]
        self.matches['missed'] = [{'gold': '1_gprd_4', 'note': 'not extracted'}]
        self.matches['false_positives'].append({'pred': '1_prd_4', 'cause': 'not_in_gold', 'note': 'x'})
        result = self.io.score(self.inp, self.matches)
        self.assertTrue(result['missed'][0]['product_missed'])
        self.assertEqual(result['product_detection']['missed_products'],
                         [{'product_key': '1_gp_3', 'product_name': '报纸'}])

    def test_gold_counted_twice_is_refused(self):
        self.matches['missed'] = [{'gold': '1_gprd_1', 'note': 'x'}]
        with self.assertRaisesRegex(self.io.ScoreError, 'gold rows accounted for more than once'):
            self.io.score(self.inp, self.matches)

    def test_pair_without_shared_line_is_refused(self):
        self.inp['predictions'][3]['evidence_lines'] = ['65']
        with self.assertRaisesRegex(self.io.ScoreError, 'share no source line'):
            self.io.score(self.inp, self.matches)
        self.inp['source']['lines_comparable'] = False
        self.io.score(self.inp, self.matches)

    def test_override_only_for_wording_fields(self):
        self.matches['overrides'] = [{'gold': '1_gprd_1', 'field': 'relation_type', 'correct': True, 'reason': 'x'}]
        with self.assertRaisesRegex(self.io.ScoreError, 'override field'):
            self.io.score(self.inp, self.matches)
        self.inp['predictions'][3]['product_name'] = self.inp['predictions'][3]['canonical_name'] = '旧报纸'
        self.matches['overrides'] = [{'gold': '1_gprd_4', 'field': 'name', 'correct': True, 'reason': 'same article'}]
        self.assertEqual(self.io.score(self.inp, self.matches)['pairs'][3]['checks']['name'], True)

    def test_report_mentions_detection_and_causes(self):
        result = self.io.score(self.inp, self.matches)
        text = self.io.report(self.inp, result, 'scorer-model')
        self.assertIn('## Product detection', text)
        self.assertIn('gold c9 X1', text)


if __name__ == '__main__':
    unittest.main()
