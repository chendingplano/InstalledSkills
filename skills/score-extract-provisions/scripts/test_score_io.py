import copy
import importlib.util
from pathlib import Path
import unittest


def gold(pid, lines, text, kind='requirement', type_='mandatory', subject='容器', location='bullet', explicit=True):
    return {'prov_id': pid, 'section': '7.1', 'source_line_spans': lines, 'source_table_rows': [],
            'evidence': text, 'provision': text, 'provision_en': '', 'prov_name': pid, 'prov_name_en': pid,
            'provision_type': type_, 'provision_kind': kind, 'provision_subject': subject,
            'provision_subject_en': 'x', 'location_type': location, 'is_explicit': explicit, 'confidence': 1.0}


def pred(pid, lines, text, type_='mandatory', subject='容器', location='bullet', explicit=True):
    return {'prov_id': pid, 'source_line_spans': lines, 'provision': text, 'prov_name': pid, 'prov_name_en': pid,
            'provision_type': type_, 'provision_subject': subject, 'provision_subject_en': 'x',
            'location_type': location, 'is_explicit': explicit, 'confidence': 0.9}


class ScoreIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('score_io.py')
        spec = importlib.util.spec_from_file_location('provision_score_io', path)
        cls.io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.io)

    def setUp(self):
        self.inp = {
            'record_id': 1, 'title': 't', 'doc_no': 'd',
            'gold_run': {'skill_version': '1.0.0', 'model_name': 'gold-model', 'benchmark_run_id': '20261106_120000'},
            'extraction': {'extract_ids': ['e1'], 'model_names': ['m'], 'prompt_names': ['p'], 'created_at': ['a', 'b']},
            'source': {'lines_comparable': True}, 'warnings': [],
            'gold': [gold('1_gprv_1', ['3'], '垃圾分类收集容器应有盖。'),
                     gold('1_gprv_2', ['4'], '可回收物运输至资源回收处理单位。', subject='可回收物',
                          location='sentence', explicit=False),
                     gold('1_gprv_3', ['4-5'], '也可预约上门收集。', kind='permission', type_='optional',
                          subject='可回收物', location='sentence')],
            'gold_ledger': [{'candidate_id': 'c9', 'decision': 'excluded', 'rule_id': 'X2'}],
            'predictions': [pred('1_prv_1', ['3'], '7.1.1 垃圾分类收集容器应有盖'),
                            pred('1_prv_2', ['4'], '可回收物运输至资源回收处理单位。', subject='可回收物',
                                 location='sentence', explicit=False),
                            pred('1_prv_3', ['5'], '也可预约上门收集。', type_='optional', subject='可回收物',
                                 location='sentence'),
                            pred('1_prv_4', ['1'], '本标准适用于农村生活垃圾分类处理。')],
        }
        self.matches = {
            'pairs': [{'gold': '1_gprv_1', 'pred': '1_prv_1', 'note': ''},
                      {'gold': '1_gprv_2', 'pred': '1_prv_2', 'note': ''},
                      {'gold': '1_gprv_3', 'pred': '1_prv_3', 'note': ''}],
            'missed': [],
            'false_positives': [{'pred': '1_prv_4', 'cause': 'gold_excluded', 'gold_candidate_id': 'c9',
                                 'rule_id': 'X2', 'note': 'scope'}],
            'overrides': [],
        }

    def test_weights_normalize(self):
        w = self.io.load_weights()
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertAlmostEqual(w['provision_type'], 0.30)

    def test_clause_number_and_stop_do_not_count(self):
        self.assertEqual(self.io.text_similarity(self.inp['gold'][0], self.inp['predictions'][0]), 1.0)
        self.assertEqual(self.io.tight_text('B.1.1 称取试样'), '称取试样')

    def test_perfect_pairs_with_one_false_positive(self):
        result = self.io.score(self.inp, self.matches)
        main = result['main']
        self.assertEqual(main['matched'], 3)
        self.assertAlmostEqual(main['soft_recall'], (1 + 1 + (1 - 0.2 * 0.5)) / 3)
        self.assertEqual(result['recall_by_kind']['permission']['matched'], 1)
        self.assertEqual(result['groups']['optional']['gold_rows'], 1)

    def test_perfect_extraction_scores_100(self):
        inp = copy.deepcopy(self.inp)
        inp['predictions'] = inp['predictions'][:2] + [pred('1_prv_3', ['4-5'], '也可预约上门收集。', type_='optional',
                                                           subject='可回收物', location='sentence')]
        matches = copy.deepcopy(self.matches)
        matches['false_positives'] = []
        self.assertEqual(self.io.score(inp, matches)['score'], 100)

    def test_field_failures(self):
        inp = copy.deepcopy(self.inp)
        inp['predictions'][1].update(provision_type='recommended', location_type='list-item', is_explicit=None)
        checks = self.io.score(inp, self.matches)['pairs'][1]['checks']
        self.assertFalse(checks['provision_type'])
        self.assertFalse(checks['location_type'])
        self.assertFalse(checks['is_explicit'])
        self.assertTrue(checks['subject'])

    def test_lines_left_out_when_not_comparable(self):
        inp = copy.deepcopy(self.inp)
        inp['source']['lines_comparable'] = False
        result = self.io.score(inp, self.matches)
        self.assertIsNone(result['pairs'][2]['checks']['lines'])
        self.assertEqual(result['pairs'][2]['credit'], 1.0)

    def test_gold_counted_twice_is_refused(self):
        matches = copy.deepcopy(self.matches)
        matches['missed'].append({'gold': '1_gprv_1', 'note': ''})
        with self.assertRaisesRegex(self.io.ScoreError, 'gold rows accounted for more than once'):
            self.io.score(self.inp, matches)

    def test_pair_must_share_a_line(self):
        matches = copy.deepcopy(self.matches)
        matches['pairs'][0]['pred'], matches['false_positives'][0]['pred'] = '1_prv_4', '1_prv_1'
        with self.assertRaisesRegex(self.io.ScoreError, 'share no source line'):
            self.io.score(self.inp, matches)

    def test_split_must_name_paired_gold(self):
        matches = copy.deepcopy(self.matches)
        matches['pairs'].pop(2)
        matches['missed'].append({'gold': '1_gprv_3', 'note': ''})
        matches['false_positives'].append({'pred': '1_prv_3', 'cause': 'split', 'gold': '1_gprv_3', 'note': ''})
        with self.assertRaisesRegex(self.io.ScoreError, 'split names the paired gold row'):
            self.io.score(self.inp, matches)
        matches['false_positives'][-1]['gold'] = '1_gprv_2'
        self.io.score(self.inp, matches)

    def test_override_only_subject(self):
        matches = copy.deepcopy(self.matches)
        matches['overrides'] = [{'gold': '1_gprv_1', 'field': 'provision_type', 'correct': True, 'reason': 'x'}]
        with self.assertRaisesRegex(self.io.ScoreError, 'override field must be one of'):
            self.io.score(self.inp, matches)
        inp = copy.deepcopy(self.inp)
        inp['predictions'][0]['provision_subject'] = '分类收集容器'
        matches['overrides'] = [{'gold': '1_gprv_1', 'field': 'subject', 'correct': True, 'reason': 'same container'}]
        self.assertTrue(self.io.score(inp, matches)['pairs'][0]['checks']['subject'])

    def test_gold_excluded_needs_ledger_candidate(self):
        matches = copy.deepcopy(self.matches)
        matches['false_positives'][0]['gold_candidate_id'] = 'c404'
        with self.assertRaisesRegex(self.io.ScoreError, 'ledger candidate'):
            self.io.score(self.inp, matches)

    def test_no_gold_runs(self):
        with self.assertRaises(self.io.NoGold):
            self.io.select_gold_run([])

    def test_report_renders(self):
        result = self.io.score(self.inp, self.matches)
        text = self.io.report(self.inp, result, 'scorer')
        self.assertIn('**Score:', text)
        self.assertIn('Recall by gold kind', text)
        self.assertIn('gold c9 X2', text)


if __name__ == '__main__':
    unittest.main()
