import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('score_io', Path(__file__).with_name('score_io.py'))
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)


def run(version, run_id, model='m', rows=1):
    return {'skill_version': version, 'model_name': model, 'benchmark_run_id': run_id, 'rows': rows,
            'source_sha256': 'h', 'document_identifier': ''}


def ref(ref_id, **kw):
    base = {'ref_id': ref_id, 'source_line_spans': ['52'], 'ref_form': 'in_text', 'list_kind': '',
            'list_entry_ref_id': '', 'normativity': 'unlisted', 'in_requirement': True, 'list_mismatch': '',
            'mechanism': 'standard_number', 'cited_raw': 'CJJ 27',
            'identifiers': [{'kind': 'standard', 'value': 'CJJ 27'}], 'target_type': 'standard',
            'target_subtype': 'industry_standard', 'relationships': ['complies_with'],
            'target_scope': 'document', 'target_locator': '', 'target_content': 'requirements',
            'metric_name': '', 'metric_name_en': None, 'internal': False}
    base.update(kw)
    base['group'] = io.group_of(base)
    return base


def entry(ref_id, line, cited, **kw):
    return ref(ref_id, source_line_spans=[line], ref_form='listed', list_kind='normative', normativity='normative',
               in_requirement=False, cited_raw=cited, identifiers=[{'kind': 'standard', 'value': cited}],
               relationships=['references'], target_content='general', **kw)


class SelectGoldRunTests(unittest.TestCase):
    def test_no_runs_is_no_gold(self):
        with self.assertRaises(io.NoGold) as ctx:
            io.select_gold_run([])
        self.assertEqual(ctx.exception.exit_code, io.EXIT_NO_GOLD)

    def test_newest_version_then_latest_run_skipping_prereleases(self):
        runs = [run('1.0.0', '20261011_095742'), run('1.1.0', '20261012_080000'),
                run('1.1.0', '20261012_090000', 'other'), run('2.0.0-rc.1', '20261013_000000')]
        self.assertEqual(io.select_gold_run(runs)['benchmark_run_id'], '20261012_090000')

    def test_prerelease_only_needs_naming(self):
        runs = [run('2.0.0-rc.1', '20261013_000000')]
        with self.assertRaises(io.NoGold):
            io.select_gold_run(runs)
        self.assertEqual(io.select_gold_run(runs, version='2.0.0-rc.1')['benchmark_run_id'], '20261013_000000')

    def test_unmatched_filter_is_no_gold(self):
        with self.assertRaises(io.NoGold):
            io.select_gold_run([run('1.0.0', 'a')], run_id='b')


class FieldCheckTests(unittest.TestCase):
    def test_exact_match_earns_full_credit(self):
        checks = io.field_checks(ref('g'), ref('p'), '')
        self.assertTrue(all(v for v in checks.values() if v is not None))
        self.assertIsNone(checks['quantity'])
        self.assertEqual(io.pair_credit(checks), 1.0)

    def test_identifier_notation_is_normalized(self):
        g = ref('g', identifiers=[{'kind': 'standard', 'value': 'GB/T 1.1', 'edition': '2009'}])
        p = ref('p', identifiers=[{'kind': 'standard', 'value': 'GB/T1.1', 'edition': '2009'}])
        self.assertTrue(io.field_checks(g, p)['identifiers'])
        p['identifiers'][0].pop('edition')
        self.assertFalse(io.field_checks(g, p)['identifiers'])

    def test_relationships_earn_overlap(self):
        checks = io.field_checks(ref('g', relationships=['requires']),
                                 ref('p', relationships=['complies_with', 'requires']), '')
        self.assertEqual(checks['relationships'], 0.5)
        self.assertAlmostEqual(io.pair_credit(checks), 0.90 / 0.95)

    def test_quantity_only_on_criterion_pairs(self):
        g = ref('g', target_content='criterion', metric_name='粪大肠菌群数', metric_name_en='Faecal coliform count')
        p = ref('p', target_content='criterion', metric_name='粪大肠菌数', metric_name_en='faecal coliform count')
        self.assertTrue(io.field_checks(g, p)['quantity'])
        self.assertIsNone(io.field_checks(g, ref('p'))['quantity'])

    def test_groups(self):
        self.assertEqual(io.group_of(entry('e', '22', 'CJJ 27')), 'listed')
        self.assertEqual(io.group_of(ref('i', internal=True)), 'internal')
        self.assertEqual(io.group_of(ref('x')), 'external_in_text')


class OwnIdentifierTests(unittest.TestCase):
    def test_dash_and_space_forms_match(self):
        check = io.own_identifier_check('DB33/T 2030—2018', [{'identity_key': 'standard:DB33/T 2030', 'edition': '2018'}])
        self.assertEqual(check['result'], 'match')

    def test_other_outcomes(self):
        self.assertEqual(io.own_identifier_check('DB33/T 2030—2018', [])['result'], 'missing')
        self.assertEqual(io.own_identifier_check('DB33/T 2030—2018',
                         [{'identity_key': 'standard:DB33/T 2030', 'edition': None}])['result'], 'match_without_edition')
        self.assertEqual(io.own_identifier_check('DB33/T 2030—2018',
                         [{'identity_key': 'standard:DB33/T 2030', 'edition': '2010'}])['result'], 'edition_differs')
        self.assertEqual(io.own_identifier_check('DB33/T 2030—2018',
                         [{'identity_key': 'standard:DB33/T 20301', 'edition': None}])['result'], 'mismatch')
        self.assertEqual(io.own_identifier_check('', [])['result'], 'gold_none')


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.inp = {'gold': [entry('g1', '28', 'CJJ 27'), ref('g2', list_entry_ref_id='g1', normativity='normative'),
                             ref('g3', source_line_spans=['55'], internal=True, mechanism='structural_reference',
                                 identifiers=[], target_type='document', target_subtype='document_element')],
                    'predictions': [entry('p1', '28', 'CJJ 27'),
                                    ref('p2', list_entry_ref_id='p1', normativity='normative'),
                                    ref('p3', source_line_spans=['2'], cited_raw='DB33/T 2030')],
                    'gold_ledger': [{'candidate_id': 'c3', 'decision': 'excluded', 'rule_id': 'X2'}],
                    'source': {'lines_comparable': True}}
        self.matches = {'pairs': [{'gold': 'g1', 'pred': 'p1'}, {'gold': 'g2', 'pred': 'p2'}],
                        'missed': [{'gold': 'g3'}],
                        'false_positives': [{'pred': 'p3', 'cause': 'gold_excluded', 'gold_candidate_id': 'c3'}]}

    def test_score_formula_and_groups(self):
        result = io.score(self.inp, self.matches)
        self.assertEqual(result['score'], round(100 * 2 / 3))
        self.assertEqual(result['groups']['listed']['score'], 100)
        self.assertEqual(result['groups']['internal']['gold_rows'], 1)
        self.assertEqual(result['groups']['internal']['score'], 1)
        self.assertAlmostEqual(result['groups']['external_in_text']['soft_precision'], 0.5)

    def test_list_link_follows_the_pairs(self):
        inp = copy.deepcopy(self.inp)
        inp['predictions'][1]['list_entry_ref_id'] = ''
        pair = io.score(inp, self.matches)['pairs'][1]
        self.assertFalse(pair['checks']['list_link'])
        # A link to a predicted entry that is not paired with the gold entry is wrong too.
        inp['predictions'][1]['list_entry_ref_id'] = 'p3'
        self.assertFalse(io.score(inp, self.matches)['pairs'][1]['checks']['list_link'])

    def test_perfect_and_floor(self):
        inp = copy.deepcopy(self.inp)
        inp['gold'], inp['predictions'] = [ref('g1')], [ref('p1')]
        perfect = {'pairs': [{'gold': 'g1', 'pred': 'p1'}], 'missed': [], 'false_positives': []}
        self.assertEqual(io.score(inp, perfect)['score'], 100)
        nothing = {'pairs': [], 'missed': [{'gold': 'g1'}],
                   'false_positives': [{'pred': 'p1', 'cause': 'not_in_gold'}]}
        self.assertEqual(io.score(inp, nothing)['score'], 1)

    def test_override_changes_credit(self):
        inp = copy.deepcopy(self.inp)
        inp['predictions'][1]['identifiers'] = [{'kind': 'standard', 'value': 'CJJ27-2006'}]
        self.assertLess(io.score(inp, self.matches)['pairs'][1]['credit'], 1)
        self.matches['overrides'] = [{'gold': 'g2', 'field': 'identifiers', 'correct': True, 'reason': 'x'}]
        self.assertEqual(io.score(inp, self.matches)['pairs'][1]['credit'], 1)

    def test_enum_override_is_refused(self):
        self.matches['overrides'] = [{'gold': 'g1', 'field': 'target_content', 'correct': True, 'reason': 'x'}]
        with self.assertRaisesRegex(io.ScoreError, 'override field'):
            io.score(self.inp, self.matches)

    def test_pair_must_share_a_line(self):
        bad = copy.deepcopy(self.matches)
        bad['pairs'][1] = {'gold': 'g2', 'pred': 'p3'}
        bad['false_positives'] = [{'pred': 'p2', 'cause': 'not_in_gold'}]
        with self.assertRaisesRegex(io.ScoreError, 'share no source line'):
            io.score(self.inp, bad)
        inp = copy.deepcopy(self.inp)
        inp['source']['lines_comparable'] = False
        io.score(inp, bad)

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


if __name__ == '__main__':
    unittest.main()
