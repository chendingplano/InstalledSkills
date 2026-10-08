import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('score_io', Path(__file__).with_name('score_io.py'))
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


def run(version, run_id, model='m'):
    return {'skill_version': version, 'model_name': model, 'benchmark_run_id': run_id, 'rows': 1,
            'source_sha256': 'h'}


def row(metric_id, **kw):
    base = {'metric_id': metric_id, 'metric_name': metric_id, 'metric_value': '15', 'metric_unit': 'mg/kg',
            'value_range_type': 'upper_bound', 'value_class': 'requirement', 'value_min': None,
            'value_max': None, 'formula_or_definition': '', 'reasoning_tags': [],
            'source_line_spans': ['134']}
    base.update(kw)
    base['kind'] = io.kind_of(base)
    return base


class SelectGoldRunTests(unittest.TestCase):
    def test_no_runs_is_no_gold(self):
        with self.assertRaises(io.NoGold):
            io.select_gold_run([])

    def test_only_old_rules_is_no_gold(self):
        with self.assertRaises(io.NoGold) as ctx:
            io.select_gold_run([run('1.1.0', '20261006_081536'), run('2.0.0', '20261006_121911')])
        self.assertEqual(ctx.exception.exit_code, io.EXIT_NO_GOLD)

    def test_newest_version_then_latest_run(self):
        runs = [run('3.0.0', '20261007_083500'), run('4.0.0', '20261007_115911'),
                run('4.0.0', '20261007_120000', 'other'), run('2.1.0', '20261007_054115'),
                run('10.0.0-rc.1', '20261008_000000')]
        chosen, stand_in = io.select_gold_run(runs)
        self.assertEqual(chosen['benchmark_run_id'], '20261007_120000')
        self.assertFalse(stand_in)

    def test_two_one_zero_is_a_stand_in(self):
        chosen, stand_in = io.select_gold_run([run('2.1.0', '20261007_054115'), run('1.0.0', '20261006_071048')])
        self.assertEqual(chosen['skill_version'], '2.1.0')
        self.assertTrue(stand_in)

    def test_named_run_below_floor_is_refused(self):
        with self.assertRaises(io.NoGold):
            io.select_gold_run([run('1.1.0', 'a'), run('4.0.0', 'b')], run_id='a')


class FieldCheckTests(unittest.TestCase):
    def test_exact_match_earns_full_credit(self):
        checks = io.field_checks(row('g'), row('p'))
        self.assertTrue(all(checks.values()))
        self.assertEqual(io.pair_credit(checks), 1.0)

    def test_value_normalization(self):
        self.assertTrue(io.value_ok(row('g', metric_value='20.0'), row('p', metric_value='≤20')))
        self.assertTrue(io.value_ok(row('g', value_range_type='exact', metric_value='1:10'),
                                    row('p', metric_value='1：10')))
        self.assertFalse(io.value_ok(row('g', value_range_type='exact', metric_value='1'),
                                     row('p', metric_value='每日')))
        rng = dict(value_range_type='range', value_min=0, value_max=4)
        self.assertTrue(io.value_ok(row('g', metric_value='0~4', **rng), row('p', metric_value='0～4', **rng)))
        self.assertTrue(io.value_ok(row('g', value_range_type='limit_absent', metric_value=''),
                                    row('p', metric_value='')))

    def test_kind_and_lines(self):
        test = row('g', value_range_type='exact', reasoning_tags=['test_condition', 'kind:test_parameter'])
        checks = io.field_checks(test, row('p', value_range_type='exact', source_line_spans=['130:134']))
        self.assertFalse(checks['kind'])
        self.assertTrue(checks['lines'])
        self.assertIsNone(io.field_checks(test, row('p'), lines_comparable=False)['lines'])

    def test_disabled_check_renormalizes(self):
        credit = io.pair_credit({'value': True, 'range_type': True, 'kind': False, 'unit': True, 'lines': None})
        self.assertAlmostEqual(credit, 0.65 / 0.85)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.inp = {'gold': [row('g1'), row('g2', metric_value='2'),
                             row('g3', value_range_type='exact', reasoning_tags=['test_condition'])],
                    'predictions': [row('p1'), row('p2', metric_value='3'), row('p3')],
                    'gold_ledger': [{'candidate_id': 'c9', 'decision': 'excluded', 'rule_id': 'X15'}],
                    'source': {'lines_comparable': True}}
        self.matches = {'pairs': [{'gold': 'g1', 'pred': 'p1'}, {'gold': 'g2', 'pred': 'p2'}],
                        'missed': [{'gold': 'g3'}],
                        'false_positives': [{'pred': 'p3', 'cause': 'gold_excluded', 'gold_candidate_id': 'c9'}]}

    def test_score_formula(self):
        result = io.score(self.inp, self.matches)
        credit = 1.0 + 0.7  # g2/p2: value wrong
        p = r = credit / 3
        self.assertAlmostEqual(result['main']['soft_f1'], 2 * p * r / (p + r))
        self.assertEqual(result['score'], round(100 * credit / 3))
        self.assertEqual(result['without_test_parameters']['gold_rows'], 2)

    def test_perfect_and_floor(self):
        inp = copy.deepcopy(self.inp)
        inp['gold'], inp['predictions'] = [row('g1')], [row('p1')]
        perfect = {'pairs': [{'gold': 'g1', 'pred': 'p1'}], 'missed': [], 'false_positives': []}
        self.assertEqual(io.score(inp, perfect)['score'], 100)
        nothing = {'pairs': [], 'missed': [{'gold': 'g1'}],
                   'false_positives': [{'pred': 'p1', 'cause': 'not_in_gold'}]}
        self.assertEqual(io.score(inp, nothing)['score'], 1)

    def test_override_changes_credit(self):
        self.matches['overrides'] = [{'gold': 'g2', 'field': 'value', 'correct': True, 'reason': 'notation'}]
        self.assertEqual(io.score(self.inp, self.matches)['score'], 67)

    def test_accounting_is_enforced(self):
        bad = copy.deepcopy(self.matches)
        bad['missed'] = []
        with self.assertRaisesRegex(io.ScoreError, 'not accounted for'):
            io.score(self.inp, bad)
        bad = copy.deepcopy(self.matches)
        bad['false_positives'].append({'pred': 'p1', 'cause': 'duplicate', 'of': 'p2'})
        with self.assertRaisesRegex(io.ScoreError, 'more than once'):
            io.score(self.inp, bad)
        bad = copy.deepcopy(self.matches)
        bad['false_positives'][0]['gold_candidate_id'] = 'c404'
        with self.assertRaisesRegex(io.ScoreError, 'ledger candidate'):
            io.score(self.inp, bad)

    def test_kind_override_is_refused(self):
        self.matches['overrides'] = [{'gold': 'g1', 'field': 'kind', 'correct': True, 'reason': 'x'}]
        with self.assertRaisesRegex(io.ScoreError, 'override field'):
            io.score(self.inp, self.matches)


class DroppedRowsTests(unittest.TestCase):
    dropped = [
        {'drop_id': '416_drp_1', 'drop_stage': 'statement_kind', 'drop_reason': 'inspection_requirement',
         'metric_name': '垃圾桶加盖', 'threshold_or_target': '垃圾桶应加盖', 'source_line_spans': ['90']},
        {'drop_id': '416_drp_2', 'drop_stage': 'decision_model', 'drop_reason': 'activity_schedule',
         'metric_name': '餐厨垃圾收运时间和频次', 'source_line_spans': ['101'],
         'decision': {'choice': 'activity_schedule', 'probabilities': {'activity_schedule': 0.97}}},
    ]

    def test_exclusion_log_keeps_only_pure_requirements(self):
        log = io.exclusion_from_dropped(self.dropped)
        self.assertEqual([e['kind'] for e in log], ['inspection_requirement'])
        self.assertEqual(log[0]['threshold_or_target'], '垃圾桶应加盖')

    def test_section_flags_drop_on_missed_gold_lines(self):
        inp = {'extraction': {'dropped_rows': self.dropped},
               'gold': [row('g7', source_line_spans=['101:102'])]}
        lines = io.dropped_rows_section(inp, {'missed': [{'gold': 'g7'}]})
        text = '\n'.join(lines)
        self.assertIn('## Dropped rows (2)', text)
        self.assertIn('| 416_drp_2 | decision_model | activity_schedule | 餐厨垃圾收运时间和频次 | 0.97 | g7 |', text)
        self.assertIn('| 416_drp_1 | statement_kind | inspection_requirement | 垃圾桶加盖 |  |  |', text)

    def test_section_without_dropped_rows(self):
        self.assertEqual(io.dropped_rows_section({'extraction': {}, 'gold': []}, {'missed': []})[-1], 'None.')


if __name__ == '__main__':
    unittest.main()
