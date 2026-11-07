import copy
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
        self.wire = {'v': 2, 'p': [[1, 1], [2, 2], [3, 3], [4, 4]], 'm': [], 'f': [[5, 'x', 1]], 'o': []}

    def decode(self, wire=None, inp=None):
        return self.io.expand_matches(inp or self.inp, copy.deepcopy(wire or self.wire))

    def test_projection_is_minimal_and_groups_products(self):
        original = copy.deepcopy(self.inp)
        view = self.io.matching_view(self.inp)
        self.assertEqual(set(view), {'v', 'lc', 'sa', 'g', 'p', 'c'})
        self.assertEqual(view['g'][0], [['89'], '垃圾分类收集容器', '垃圾分类收集容器', 'design_requirement',
                                        '垃圾分类收集容器应有盖', 1])
        self.assertEqual(view['g'][1][-1], 1)
        self.assertEqual(view['g'][2][-1], 2)
        self.assertEqual(len(view['p'][0]), 5)
        self.assertEqual(view['c'][0], [[], '垃圾转运站', 'X1', ''])
        self.assertEqual(self.inp, original)

    def test_decoded_decisions_equal_verbose(self):
        expanded = self.decode()
        self.assertEqual(self.io.score(self.inp, expanded)['score'], self.io.score(self.inp, self.matches)['score'])
        self.assertEqual(expanded['false_positives'][0]['gold_candidate_id'], 'c9')

    def test_extra_relation_needs_gold_index(self):
        wire = dict(self.wire, p=[[2, 2], [3, 3], [4, 4]], m=[[1, 0, 'no design row']],
                    f=[[1, 'r', 1], [5, 'x', 1]])
        expanded = self.decode(wire)
        self.assertEqual(expanded['false_positives'][0]['product_key'], '1_gp_1')
        for target in (None, 9):
            wire['f'][0] = [1, 'r', target]
            with self.assertRaisesRegex(self.io.ScoreError, 'compact matches'):
                self.decode(wire)

    def test_override_rows(self):
        wire = dict(self.wire, o=[[4, 'name', True, 'same article']])
        self.assertEqual(self.decode(wire)['overrides'][0]['field'], 'name')
        wire['o'] = [[3, 'relation_type', True, 'close enough']]
        with self.assertRaisesRegex(self.io.ScoreError, 'override field'):
            self.decode(wire)
        wire['o'] = [[4, 'name', True, 'a'], [4, 'name', False, 'b']]
        with self.assertRaisesRegex(self.io.ScoreError, 'duplicate override'):
            self.decode(wire)

    def test_unknown_keys_and_causes_are_refused(self):
        for wire in (dict(self.wire, extra=[]), dict(self.wire, v=1), dict(self.wire, f=[[5, 's', 1]]),
                     dict(self.wire, p=[[1, 1], [2, 2], [3, 3], [4, 6]])):
            with self.assertRaisesRegex(self.io.ScoreError, 'compact matches'):
                self.decode(wire)

    def test_duplicate_cycle_is_rejected(self):
        wire = dict(self.wire, p=[[1, 1], [2, 2]], m=[[3, 0, 'missing'], [4, 0, 'missing']],
                    f=[[3, 'd', 4], [4, 'd', 3], [5, 'x', 1]])
        with self.assertRaisesRegex(self.io.ScoreError, 'cycle'):
            self.decode(wire)

    def test_merge_target_must_be_paired_and_share_a_line(self):
        wire = dict(self.wire, p=[[1, 1], [3, 3], [4, 4]], m=[[2, 1]], f=[[2, 'd', 1], [5, 'x', 1]])
        self.assertIn('merged into 1_prd_1', self.decode(wire)['missed'][0]['note'])
        wire['m'] = [[2, 4]]
        with self.assertRaisesRegex(self.io.ScoreError, 'shares no source line'):
            self.decode(wire)

    def test_cli_score_require_compact(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'input.json').write_text(json.dumps(self.inp, ensure_ascii=False), encoding='utf-8')
            Path(tmp, 'matches.json').write_text(json.dumps(self.wire), encoding='utf-8')
            script = Path(test_score_io.__file__).with_name('score_io.py')
            done = subprocess.run([sys.executable, str(script), 'score', '--dir', tmp, '--scorer-model', 'x',
                                   '--require-compact'], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout)['score'], 89)
            for name in ('matches-expanded.json', 'score.json', 'report.md'):
                self.assertTrue(Path(tmp, name).exists())


if __name__ == '__main__':
    unittest.main()
