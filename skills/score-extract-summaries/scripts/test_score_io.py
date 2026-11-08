import unittest
from unittest.mock import Mock, patch
import score_io as s


def fixture():
    gold = {'summary_seq_no': 1, 'source_line_spans': ['1'], 'empty_reason': '',
            'units': [{'id': 'u1', 'weight': 3, 'critical': True, 'included': True},
                      {'id': 'u2', 'weight': 1, 'critical': False, 'included': False}]}
    pred = {'id': 7, 'summary_seq_no': 1, 'summary_text': 'Keep cool.',
            'source_line_spans': ['1']}
    inp = {'gold': {'summaries': [gold], 'budget_chars': 20}, 'predictions': [pred],
           'source': [{'line': 1, 'content': 'Keep cool.'}]}
    review = {'input_sha256': s.fingerprint(inp), 'reviewer': 'test', 'limitations': [],
              'chunks': [{'pred': 7, 'units': [{'id': 'u1', 'credit': 1, 'reason': 'preserved',
                         'prediction_spans': [{'start': 0, 'end': 10, 'quote': 'Keep cool.'}]}],
                         'claims': [{'start': 0, 'end': 10, 'quote': 'Keep cool.',
                                     'status': 'supported', 'reason': 'source states it',
                                     'evidence': [{'line': 1, 'start': 0, 'end': 10,
                                                   'quote': 'Keep cool.'}]}],
                         'diagnostics': 'Readable; English, translation not applicable.',
                         'similarity': {'score': 1, 'reason': 'Same meaning.'}}]}
    return inp, review


class ScoringTests(unittest.TestCase):
    def test_perfect_and_omitted_unit_not_required(self):
        i, r = fixture()
        self.assertEqual(s.score(i, r)['score'], 100)

    def test_partial_critical_and_unsupported_claim(self):
        i, r = fixture()
        r['chunks'][0]['units'][0]['credit'] = .5
        r['chunks'][0]['claims'][0]['status'] = 'unsupported'
        result = s.score(i, r)
        self.assertEqual(result['components']['coverage'], .5)
        self.assertEqual(result['components']['critical'], .5)
        self.assertEqual(result['components']['faithfulness'], 0)
        self.assertEqual(result['score'], 52)

    def test_similarity_counts_and_missing_chunks_earn_zero(self):
        i, r = fixture()
        r['chunks'][0]['similarity']['score'] = .5
        result = s.score(i, r)
        self.assertEqual(result['components']['similarity'], .5)
        i['predictions'] = []
        r['chunks'] = []
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['components']['similarity'], 0)

    def test_similarity_must_be_bounded_and_explained(self):
        for bad in ({'score': 1.5, 'reason': 'x'}, {'score': True, 'reason': 'x'}, {'score': .5, 'reason': ' '}, {'score': .5}):
            with self.subTest(bad=bad):
                i, r = fixture()
                r['chunks'][0]['similarity'] = bad
                with self.assertRaises(ValueError): s.score(i, r)

    def test_zh_and_zh_cn_are_the_same_language(self):
        self.assertEqual(s.normalize_language('zh-cn'), s.normalize_language('zh'))
        self.assertEqual(s.normalize_language('zh_CN'), 'zh')
        self.assertNotEqual(s.normalize_language('en'), s.normalize_language('zh'))
        i, r = fixture()
        i['gold']['summaries'][0]['language'] = 'zh-cn'
        i['predictions'][0]['language'] = 'zh'
        r['input_sha256'] = s.fingerprint(i)
        self.assertTrue(s.score(i, r)['details'][0]['language_match'])

    def test_translations_and_keywords_do_not_affect_score(self):
        i, r = fixture()
        i['gold']['summaries'][0].update(summary_text='保持阴凉。', summary_text_en='Keep cool.',
                                         keywords=['储存'], keywords_en=['storage'])
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['score'], 100)

    def test_missing_prediction_penalized(self):
        i, r = fixture()
        i['predictions'] = []
        r['chunks'] = []
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['score'], 1)

    def test_duplicate_is_extra_not_second_match(self):
        i, r = fixture()
        i['predictions'].append({**i['predictions'][0], 'id': 8})
        r['input_sha256'] = s.fingerprint(i)
        result = s.score(i, r)
        self.assertEqual(result['extra_predictions'], [8])
        self.assertLess(result['score'], 100)

    def test_budget_and_line_provenance_are_mechanical(self):
        i, r = fixture()
        i['gold']['budget_chars'] = 2
        i['predictions'][0]['source_line_spans'] = ['2']
        r['input_sha256'] = s.fingerprint(i)
        result = s.score(i, r)
        self.assertEqual(result['components']['budget'], 0)
        self.assertEqual(result['components']['provenance'], 0)

    def test_bad_reviews_refused(self):
        for mutation in ('hash', 'coverage', 'quote', 'evidence', 'credit', 'claim_gap'):
            with self.subTest(mutation=mutation):
                i, r = fixture()
                c = r['chunks'][0]
                if mutation == 'hash': r['input_sha256'] = 'stale'
                if mutation == 'coverage': c['units'] = []
                if mutation == 'quote': c['claims'][0]['quote'] = 'false'
                if mutation == 'evidence': c['claims'][0]['evidence'][0]['line'] = 2
                if mutation == 'credit': c['units'][0]['credit'] = True
                if mutation == 'claim_gap': c['claims'][0].update(end=4, quote='Keep')
                with self.assertRaises(ValueError): s.score(i, r)

    def test_empty_gold_empty_prediction(self):
        i, r = fixture()
        i['gold']['summaries'][0].update(units=[], empty_reason='image only')
        i['predictions'][0]['summary_text'] = ''
        r['chunks'][0].update(units=[], claims=[])
        r['input_sha256'] = s.fingerprint(i)
        result = s.score(i, r)
        self.assertEqual(result['score'], 100)
        self.assertIsNone(result['components']['coverage'])

    def test_version_selection_and_no_gold(self):
        runs = [{'skill_version': v, 'run_id': '20261021_120000', 'model_name': 'test'}
                for v in ('1.2.0', '1.10.0', '2.0.0-rc1')]
        self.assertEqual(s.select_run(runs)['skill_version'], '1.10.0')
        with self.assertRaises(s.NoGold): s.select_run([])

    def test_algorithms_never_blended(self):
        rows = [{'algorithm': 'lexrank'}, {'algorithm': 'textrank'}]
        with self.assertRaises(ValueError): s.select_predictions(rows, 'extract', None)
        self.assertEqual(s.select_predictions(rows, 'extract', 'lexrank'), rows[:1])

    def test_extract_provenance_checks_source_offsets_and_selected_lines(self):
        i, r = fixture()
        i['candidate'] = 'extract'
        i['source'][0]['type'] = 'text'
        i['predictions'][0]['source_sentence_spans'] = [
            {'text': 'Keep cool.', 'spans': [{'line': 1, 'start': 0, 'end': 10}]}]
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['score'], 100)
        i['predictions'][0]['source_sentence_spans'][0]['spans'][0]['end'] = 9
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['components']['provenance'], 0)

    def test_extract_source_line_spans_must_equal_chunk_lines(self):
        i, r = fixture()
        i['candidate'] = 'extract'
        i['source'][0]['type'] = 'text'
        i['source'].append({'line': 2, 'content': 'Overlap context.', 'type': 'text'})
        i['gold']['summaries'][0]['source_line_spans'] = ['1-2']
        i['predictions'][0]['source_line_spans'] = ['1-2']
        i['predictions'][0]['source_sentence_spans'] = [
            {'text': 'Keep cool.', 'spans': [{'line': 1, 'start': 0, 'end': 10}]}]
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['components']['provenance'], 1)
        i['predictions'][0]['source_line_spans'] = ['1']
        r['input_sha256'] = s.fingerprint(i)
        self.assertEqual(s.score(i, r)['components']['provenance'], 0)

    def test_nonfinite_unknown_and_inapplicable_weights_refused(self):
        import json
        import tempfile
        from pathlib import Path
        for value in ({'coverage': float('nan')}, {'imaginary': 10}, {'chunks': -1}):
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'weights.json'
                p.write_text(json.dumps(value))
                with self.assertRaises(ValueError): s.weights(p)

    def test_export_snapshot_and_stale_chunks(self):
        import argparse
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        inp, _ = fixture()
        gold = {**inp['gold'], 'skill_version': '1.0.0', 'model_name': 'test',
                'run_id': '20261021_120000', 'source_sha256': 'source',
                'chunks_sha256': 'chunks', 'limitations': [], 'review_mode': 'self'}
        snapshot = {'record': {'id': 1}, 'runs': [gold],
                    'predictions': [{**inp['predictions'][0], 'algorithm': 'lexrank'}]}
        bio = Mock()
        bio.record_query.return_value = 'SELECT 1;'
        bio.load_source.return_value = (Path('/source'), 'source', {1: inp['source'][0]})
        bio.load_chunks.return_value = ('chunks', [])
        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(record_id=1, candidate='extract', algorithm=None,
                    gold_version=None, gold_model=None, gold_run_id=None, chunks='/chunks', out_dir=d)
            with patch.object(s, 'query', return_value=snapshot), patch.object(s, 'ensure_paths'), \
                    patch.object(s, 'load_benchmark', return_value=bio), contextlib.redirect_stdout(io.StringIO()):
                s.export(args)
                exported = json.loads((Path(d) / 'input.json').read_text())
                self.assertEqual(exported['algorithm'], 'lexrank')
                bio.validate.assert_called_once_with(snapshot['record'], gold)
                bio.readback.assert_called_once_with(gold)
                bio.load_chunks.return_value = ('changed', [])
                with self.assertRaisesRegex(ValueError, 'STALE_GOLD'):
                    s.export(args)

    def test_mise_only_database_settings_are_preserved(self):
        import json
        import os
        from types import SimpleNamespace
        values = {'DATA_HOME_DIR': '/data', 'ARTIFACT_DIR': '/artifacts',
                  'PG_USER_NAME': 'test-user', 'PG_DB_NAME': 'test-db'}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(values))
        with patch.dict(os.environ, {}, clear=True), patch.object(s, 'WORKSPACE', __import__('pathlib').Path('/missing')), \
                patch.object(s.subprocess, 'run', return_value=result):
            s.ensure_paths()
            env = s.environment()
            self.assertEqual(env['PGUSER'], 'test-user')
            self.assertEqual(env['PGDATABASE'], 'test-db')


if __name__ == '__main__':
    unittest.main()
