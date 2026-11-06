import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_score_io


class CompactIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_score_io.ScoreIOTests.setUpClass()
        cls.io = test_score_io.ScoreIOTests.io

    def setUp(self):
        test_score_io.ScoreIOTests.setUp(self)
        self.wire = {'v': 2, 'p': [[1, 1], [2, 2], [3, 3]], 'm': [],
                     'f': [[4, 'x', 1]], 'o': []}

    def test_projection_is_minimal_and_does_not_mutate_audit(self):
        original = copy.deepcopy(self.inp)
        self.assertTrue(callable(getattr(self.io, 'matching_view', None)), 'missing compact projection')
        view = self.io.matching_view(self.inp)
        self.assertEqual(view['g'][0], [['3'], '垃圾分类收集容器应有盖。', '容器'])
        self.assertEqual(view['c'][0], [[], '', 'X2', ''])
        self.assertEqual(set(view), {'v', 'lc', 'sa', 'g', 'p', 'c'})
        self.assertEqual(self.inp, original)
        self.inp['source']['lines_comparable'] = False
        self.assertFalse(self.io.matching_view(self.inp)['lc'])

    def test_source_available_and_changed_are_distinct(self):
        self.inp['source'].update(lines_comparable=False, available=False)
        self.assertFalse(self.io.matching_view(self.inp)['sa'])
        self.inp['source']['available'] = True
        self.assertTrue(self.io.matching_view(self.inp)['sa'])
        self.assertFalse(self.io.matching_view(self.inp)['lc'])

    def test_duplicate_cycle_is_rejected(self):
        self.wire['p'] = [[1, 1]]
        self.wire['m'] = [[2, 0, 'missing'], [3, 0, 'missing']]
        self.wire['f'] = [[2, 'd', 3], [3, 'd', 2], [4, 'x', 1]]
        with self.assertRaisesRegex(self.io.ScoreError, 'cycle'):
            self.decode()

    def decode(self, wire=None, inp=None):
        self.assertTrue(callable(getattr(self.io, 'expand_matches', None)), 'missing compact decoder')
        return self.io.expand_matches(inp or self.inp, self.wire if wire is None else wire)

    def test_expansion_preserves_scores_and_ledger_rule(self):
        decoded = self.decode()
        self.assertEqual(decoded['false_positives'][0]['gold_candidate_id'], 'c9')
        self.assertEqual(decoded['false_positives'][0]['rule_id'], 'X2')
        for field in ('score', 'main', 'groups', 'recall_by_kind', 'field_accuracy'):
            self.assertEqual(self.io.score(self.inp, self.matches)[field],
                             self.io.score(self.inp, decoded)[field])

    def test_merge_links_generate_localized_notes_and_keep_exceptional_notes(self):
        self.inp['source']['lines_comparable'] = False
        self.inp['provenance'] = {'lang': 'zh-cn'}
        self.wire['p'] = [[1, 1, '特殊说明']]
        self.wire['m'] = [[2, 1], [3, 0, '确实遗漏']]
        self.wire['f'] = [[2, 's', 1], [3, 'd', 2, 'duplicate chain'], [4, 'x', 1]]
        decoded = self.decode()
        self.io.check_matches(self.inp, decoded)
        self.assertIn('合并', decoded['missed'][0]['note'])
        self.assertIn('1_prv_1', decoded['missed'][0]['note'])
        self.assertEqual(decoded['pairs'][0]['note'], '特殊说明')
        self.assertEqual(decoded['false_positives'][1]['note'], 'duplicate chain')

    def test_subject_override_is_the_only_override(self):
        self.wire['o'] = [[1, True, 'same object']]
        decoded = self.decode()
        self.assertEqual(decoded['overrides'][0]['field'], 'subject')
        self.assertTrue(self.io.score(self.inp, decoded)['pairs'][0]['checks']['subject'])

    def test_strict_wire_validation(self):
        variants = []
        for key, value in [('v', True), ('v', 3), ('extra', []), ('p', [[True, 1]]),
                           ('p', [[0, 1]]), ('p', [[99, 1]]), ('p', [[1, -1]]),
                           ('p', [[1.0, 1]]), ('p', [[1, 1, '', 'extra']]),
                           ('m', [[2, None]]), ('m', [[2, 0]]), ('m', [[2, 4]]),
                           ('f', [[4, 'unknown', 1]]), ('f', [[4, 'x', 99]]),
                           ('f', [[4, 'n', None]]), ('f', [[4, 'i', 1, 'reason']]),
                           ('f', [[4, 'd', 4]]), ('o', [[1, 'true', 'x']]),
                           ('o', [[1, True, '']]), ('o', [[1, True, 'x'], [1, False, 'y']])]:
            wire = copy.deepcopy(self.wire)
            wire[key] = value
            variants.append(wire)
        for key in ('p', 'm', 'f', 'o'):
            wire = copy.deepcopy(self.wire)
            del wire[key]
            variants.append(wire)
        for wire in variants:
            with self.subTest(wire=wire):
                with self.assertRaises(self.io.ScoreError):
                    self.decode(wire)

    def test_exhaustive_accounting_and_no_silent_pair_repair(self):
        for pairs in ([[1, 1]], [[1, 1], [2, 1], [3, 3]], [[1, 1], [1, 2], [3, 3]]):
            self.wire['p'] = pairs
            with self.assertRaises(self.io.ScoreError):
                self.io.check_matches(self.inp, self.decode())

    def test_nonoverlap_and_changed_source(self):
        self.inp['predictions'][0]['source_line_spans'] = ['999']
        with self.assertRaises(self.io.ScoreError):
            self.io.check_matches(self.inp, self.decode())
        self.inp['source']['lines_comparable'] = False
        self.io.check_matches(self.inp, self.decode())

    def test_not_in_gold_and_invalid_require_explanations(self):
        for cause in ('n', 'i'):
            self.wire['f'] = [[4, cause, None, 'gold appears to miss a real provision']]
            self.io.check_matches(self.inp, self.decode())

    def test_captured_event_replay(self):
        fixture = Path(__file__).with_name('testdata') / 'llm-6adc0b65.json.gz'
        captured = json.loads(gzip.decompress(fixture.read_bytes()))
        inp, original, wire = (captured[k] for k in ('input', 'matches', 'compact'))
        decoded = self.decode(wire, inp)
        before, after = self.io.score(inp, original), self.io.score(inp, decoded)
        self.assertEqual(after['score'], 57)
        for field in ('score', 'main', 'groups', 'recall_by_kind', 'field_accuracy', 'weights'):
            self.assertEqual(before[field], after[field])
        self.assertEqual(len(decoded['missed']), 32)
        self.assertEqual(sum('merged into' in x['note'] for x in decoded['missed']), 31)
        self.assertTrue(any('government-purchase' in x['note'] for x in decoded['false_positives']))
        self.assertLess(len(json.dumps(self.io.matching_view(inp), ensure_ascii=False)), 18000)
        self.assertLess(len(json.dumps(wire, ensure_ascii=False)), 1500)

    def test_zero_gold_and_duplicate_ledger_candidate(self):
        self.inp['gold'] = []
        self.inp['gold_ledger'][0].update(decision='duplicate', rule_id='D1', reason='same as accepted')
        self.wire.update(p=[], f=[[n, 'x', 1] for n in range(1, 5)])
        result = self.io.score(self.inp, self.decode())
        self.assertEqual(result['score'], 1)
        self.assertEqual(result['false_positives'][0]['rule_id'], 'D1')
        self.assertEqual(result['false_positives'][0]['note'], 'same as accepted')

    def test_cli_projects_and_scores_compact_without_database(self):
        script = Path(__file__).with_name('score_io.py')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'input.json').write_text(json.dumps(self.inp))
            (directory / 'matches.json').write_text(json.dumps(self.wire))
            for args in (['project', '--dir', tmp], ['score', '--dir', tmp, '--scorer-model', 'test']):
                result = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            view = json.loads((directory / 'matching-input.json').read_text())
            self.assertEqual(view['v'], 2)
            expanded = json.loads((directory / 'matches-expanded.json').read_text())
            self.io.check_matches(self.inp, expanded)
            self.assertEqual(json.loads((directory / 'matches.json').read_text()), self.wire)
            # Legacy snapshots stay replayable, but new UI calls cannot silently accept them.
            (directory / 'matches.json').write_text(json.dumps(self.matches))
            args = [sys.executable, str(script), 'score', '--dir', tmp, '--scorer-model', 'test']
            result = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([*args, '--require-compact'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('compact matches:', result.stderr)


if __name__ == '__main__':
    unittest.main()
