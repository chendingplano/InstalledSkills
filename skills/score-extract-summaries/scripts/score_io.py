#!/usr/bin/env python3
"""Export one summary candidate; validate semantic judgments and compute a reproducible score."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
VERSION = '1.1.0'
DEFAULT_WEIGHTS = {'chunks': 10, 'coverage': 30, 'faithfulness': 30, 'similarity': 10,
                   'critical': 15, 'provenance': 10, 'budget': 5}
# Language tags that name the same language for comparison purposes.
LANGUAGE_ALIASES = {'zh-cn': 'zh'}


class NoGold(ValueError):
    pass


class NoPredictions(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalize_language(tag):
    text = str(tag or '').strip().lower().replace('_', '-')
    return LANGUAGE_ALIASES.get(text, text)


def load_benchmark():
    path = ROOT.parent / 'generate-summaries-benchmark/scripts/benchmark_io.py'
    spec = importlib.util.spec_from_file_location('summary_benchmark_io', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_run(runs, version=None, model=None, run_id=None):
    selected = [r for r in runs if (not version or r['skill_version'] == version)
                and (not model or r['model_name'] == model) and (not run_id or r['run_id'] == run_id)]
    if not version:
        selected = [r for r in selected if re.fullmatch(r'\d+\.\d+\.\d+', r['skill_version'])]
    if not selected:
        raise NoGold('NO_GOLD: no matching released summary benchmark; create gold separately')
    def key(r):
        nums = re.match(r'(\d+)\.(\d+)\.(\d+)', r['skill_version'])
        require(nums is not None, 'Invalid gold version')
        return tuple(map(int, nums.groups())), r['run_id'], r['model_name']
    return max(selected, key=key)


def select_predictions(rows, candidate, algorithm):
    if candidate == 'extract':
        algorithms = sorted({r['algorithm'] for r in rows})
        require(algorithm or len(algorithms) <= 1,
                'Multiple algorithms present; choose --algorithm: ' + ', '.join(algorithms))
        rows = [r for r in rows if not algorithm or r['algorithm'] == algorithm]
    else:
        require(not algorithm, '--algorithm applies only to extracts')
    if not rows:
        raise NoPredictions('NO_PREDICTIONS: no rows for the selected candidate')
    return rows


def environment():
    env = dict(os.environ)
    dotenv = WORKSPACE / 'ChenWeb/.env'
    values = {}
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            m = re.match(r'\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
            if m:
                values[m[1]] = m[2].strip().strip('"').strip("'")
    for pg, name in (('PGUSER', 'PG_USER_NAME'), ('PGPASSWORD', 'PG_PASSWORD'),
                     ('PGDATABASE', 'PG_DB_NAME'), ('PGHOST', 'PG_HOST'), ('PGPORT', 'PG_PORT')):
        if not env.get(pg):
            value = env.get(name) or values.get(name)
            if value:
                env[pg] = value
    env['PGOPTIONS'] = env.get('PGOPTIONS', '') + ' -c default_transaction_read_only=on'
    return env


def query(sql):
    env = environment()
    require(env.get('PGUSER') and env.get('PGDATABASE'),
            'Configure PGUSER/PGDATABASE or ChenWeb PG_USER_NAME/PG_DB_NAME')
    result = subprocess.run(['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1'],
                            input=sql, text=True, capture_output=True, env=env, timeout=60)
    require(result.returncode == 0, 'PostgreSQL read failed; inspect connection/schema privately')
    return json.loads(result.stdout) if result.stdout.strip() else None


def ensure_paths():
    env = environment()
    if all(os.environ.get(k) for k in ('DATA_HOME_DIR', 'ARTIFACT_DIR')) and env.get('PGUSER') and env.get('PGDATABASE'):
        return
    result = subprocess.run(['mise', 'env', '--json'], cwd=WORKSPACE / 'ChenWeb',
                            capture_output=True, text=True, timeout=60)
    require(result.returncode == 0, 'Set DATA_HOME_DIR and ARTIFACT_DIR or configure ChenWeb mise')
    values = json.loads(result.stdout)
    for key in ('DATA_HOME_DIR', 'ARTIFACT_DIR', 'PGUSER', 'PGDATABASE', 'PGPASSWORD', 'PGHOST', 'PGPORT',
                'PG_USER_NAME', 'PG_DB_NAME', 'PG_PASSWORD', 'PG_HOST', 'PG_PORT'):
        if not os.environ.get(key) and values.get(key):
            os.environ[key] = values[key]


def export(args):
    require(args.record_id > 0, 'Positive record ID required')
    bio = load_benchmark()
    ensure_paths()
    # Read the record, gold payloads and predictions within one SQL snapshot.
    table = 'kb.ex_summaries' if args.candidate == 'extract' else 'kb.summaries'
    rec_sql = bio.record_query(args.record_id).rstrip(';')
    snapshot = query(f"""SELECT jsonb_build_object(
      'record', ({rec_sql}),
      'runs', (SELECT coalesce(jsonb_agg(payload), '[]'::jsonb)
        FROM testbed.summary_benchmark_runs WHERE input_record_id = {args.record_id}
        AND skill_name = 'generate-summaries-benchmark'),
      'predictions', (SELECT coalesce(jsonb_agg(to_jsonb(s) - 'search_vector' - 'search_document'
        ORDER BY s.id), '[]'::jsonb) FROM {table} s
        WHERE input_record_id = {args.record_id} AND summary_level = 0));""")
    record = snapshot['record']
    require(record is not None, 'Unknown kb.inputs.id')
    gold = select_run(snapshot['runs'], args.gold_version, args.gold_model, args.gold_run_id)
    # Validate frozen rules, source, chunks, record metadata, reviews and saved rows.
    bio.validate(record, gold)
    # This helper uses standard PG variables; supply the same connection privately.
    old_env = dict(os.environ)
    try:
        os.environ.update(environment())
        bio.readback(gold)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    current_chunks = Path(args.chunks) if args.chunks else bio.default_chunks(record)
    _, sha, source = bio.load_source(record)
    chunk_sha, _ = bio.load_chunks(current_chunks, source)
    require(sha == gold['source_sha256'] and chunk_sha == gold['chunks_sha256'],
            'STALE_GOLD: current canonical source/chunks differ; do not score')
    predictions = select_predictions(snapshot['predictions'], args.candidate, args.algorithm)
    warnings = list(gold['limitations'])
    warnings.append('Gold review mode: ' + gold['review_mode'])
    warnings.append('Production rows do not prove a frozen source or generation run; verify provenance before comparing.')
    configurations = {fingerprint(row.get('extraction_config') or {}) for row in predictions}
    if len(configurations) > 1:
        warnings.append('Candidate rows contain different extraction configurations; inspect input.json before comparison.')
    for row in predictions:
        config = row.get('extraction_config') or {}
        for field in ('source_sha256', 'chunks_sha256'):
            if field in config:
                require(config[field] == gold[field], 'STALE_PREDICTIONS: ' + field)
    inp = {'scoring_version': VERSION, 'record': record, 'candidate': args.candidate,
           'algorithm': predictions[0].get('algorithm'), 'gold': gold,
           'predictions': predictions, 'source': list(source.values()), 'warnings': warnings,
           'exported_at': datetime.now(timezone.utc).isoformat()}
    out = Path(args.out_dir) if args.out_dir else Path(gold['source_filename']).parent / 'extract-summaries-scores' / (
        str(args.record_id) + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'input.json'
    with path.open('x') as f:
        json.dump(inp, f, ensure_ascii=False, indent=2)
    print(path)


def line_set(spans):
    require(isinstance(spans, list), 'Line spans must be a list')
    result = set()
    for span in spans:
        require(isinstance(span, str) and re.fullmatch(r'[1-9]\d*(?:-[1-9]\d*)?', span), 'Invalid line span')
        bounds = list(map(int, span.split('-')))
        require(bounds[0] <= bounds[-1] and bounds[-1] - bounds[0] < 1000000, 'Invalid line bounds')
        result.update(range(bounds[0], bounds[-1] + 1))
    return result


def align(inp):
    gold = {g['summary_seq_no']: g for g in inp['gold']['summaries']}
    require(len(gold) == len(inp['gold']['summaries']) and gold, 'Invalid gold chunks')
    ids, pairs, extras = set(), {}, []
    for pred in inp['predictions']:
        require(type(pred['id']) is int and pred['id'] not in ids, 'Invalid/duplicate prediction ID')
        ids.add(pred['id'])
        seq = pred['summary_seq_no']
        require(type(seq) is int and seq > 0, 'Invalid prediction chunk sequence')
        if seq in gold and seq not in pairs:
            pairs[seq] = pred
        else:
            extras.append(pred['id'])
    return gold, pairs, extras


def span(text, item):
    start, end = item.get('start'), item.get('end')
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Invalid span offsets')
    require(text[start:end] == item.get('quote'), 'Span quote mismatch')
    return set(range(start, end))


def validate_review(inp, review):
    require(review['input_sha256'] == fingerprint(inp), 'Review refers to different input')
    require(isinstance(review.get('reviewer'), str) and review['reviewer'].strip(), 'Reviewer required')
    require(isinstance(review.get('limitations'), list) and
            all(isinstance(x, str) and x.strip() for x in review['limitations']), 'Limitations must be strings')
    gold, pairs, extras = align(inp)
    judgments = review['chunks']
    require(len(judgments) == len(pairs) and {j['pred'] for j in judgments} == {p['id'] for p in pairs.values()},
            'Review every aligned prediction exactly once')
    source = {x['line']: x['content'] for x in inp['source']}
    by_id = {j['pred']: j for j in judgments}
    for seq, pred in pairs.items():
        g, j, text = gold[seq], by_id[pred['id']], pred['summary_text']
        require(isinstance(text, str), 'Prediction text required')
        require(isinstance(j.get('diagnostics'), str) and j['diagnostics'].strip(), 'Chunk diagnostics required')
        similarity = j.get('similarity')
        require(isinstance(similarity, dict) and type(similarity.get('score')) in (int, float)
                and 0 <= similarity['score'] <= 1 and isinstance(similarity.get('reason'), str)
                and similarity['reason'].strip(), 'Similarity score in [0,1] and reason required')
        units = {u['id']: u for u in g['units'] if u['included']}
        require(len(j['units']) == len(units) and {u['id'] for u in j['units']} == units.keys(),
                'Judge every included gold unit exactly once')
        for u in j['units']:
            require(type(u['credit']) in (int, float) and u['credit'] in (0, .5, 1), 'Credit must be 0, 0.5 or 1')
            require(isinstance(u.get('reason'), str) and u['reason'].strip(), 'Unit reason required')
            require(isinstance(u.get('prediction_spans'), list), 'Prediction spans required')
            require(u['credit'] == 0 or u['prediction_spans'], 'Positive coverage requires prediction evidence')
            for item in u['prediction_spans']:
                span(text, item)
        covered = set()
        for claim in j['claims']:
            chars = span(text, claim)
            require(not covered.intersection(chars), 'Overlapping claims')
            covered.update(chars)
            require(claim['status'] in ('supported', 'contradicted', 'unsupported'), 'Invalid claim status')
            require(isinstance(claim.get('reason'), str) and claim['reason'].strip(), 'Claim reason required')
            require(isinstance(claim.get('evidence'), list), 'Evidence list required')
            require(claim['status'] != 'supported' or claim['evidence'], 'Supported claims require source evidence')
            for evidence in claim['evidence']:
                require(evidence['line'] in source and evidence['line'] in line_set(g['source_line_spans']),
                        'Claim evidence outside chunk')
                span(source[evidence['line']], evidence)
        require(all(c.isspace() or n in covered for n, c in enumerate(text)), 'Unreviewed prediction text')
    return gold, pairs, extras, by_id


def weights(path=None):
    result = dict(DEFAULT_WEIGHTS)
    if path:
        supplied = json.loads(Path(path).read_text())
        require(isinstance(supplied, dict) and supplied.keys() <= result.keys(), 'Unknown weight names')
        result.update(supplied)
    require(all(type(v) in (int, float) and 0 <= v < float('inf') for v in result.values())
            and sum(result.values()) > 0, 'Invalid weights')
    return result


def extract_provenance(pred, expected, source):
    """Check the production sentence-span contract without inferring semantic support."""
    try:
        sentences = pred.get('source_sentence_spans') or []
        selected, texts, previous = set(), [], (-1, -1)
        for sentence in sentences:
            pieces = []
            require(sentence['spans'] and sentence['text'].strip(), 'Empty extraction sentence')
            for item in sentence['spans']:
                line, start, end = item['line'], item['start'], item['end']
                require(line in expected and line in source and source[line]['type'].lower() != 'image',
                        'Extract span outside readable chunk')
                text = source[line]['content']
                require(type(start) is int and type(end) is int and 0 <= start < end <= len(text),
                        'Invalid extract offsets')
                require((line, start) >= previous, 'Extract spans repeated/reordered')
                previous = (line, end)
                selected.add(line)
                pieces.append(text[start:end])
            require(' '.join(sentence['text'].split()) == ' '.join(' '.join(pieces).split()),
                    'Extract sentence differs from source')
            texts.append(sentence['text'])
        return pred['summary_text'] == '\n'.join(texts) and selected <= line_set(pred['source_line_spans'])
    except (ValueError, KeyError, TypeError):
        return False


def score(inp, review, configured=None):
    gold, pairs, extras, judgments = validate_review(inp, review)
    w = weights() if configured is None else configured
    n, p, matched = len(gold), len(inp['predictions']), len(pairs)
    comps = {'chunks': 2 * matched / (n + p)}
    totals = {'coverage': [0, 0], 'critical': [0, 0]}
    faith, similar, provenance, within = 0, 0, 0, 0
    details = []
    for seq, g in gold.items():
        pred = pairs.get(seq)
        j = judgments[pred['id']] if pred else None
        credits = {u['id']: u['credit'] for u in j['units']} if j else {}
        for unit in g['units']:
            if not unit['included']:
                continue
            for component in ('coverage', 'critical') if unit['critical'] else ('coverage',):
                totals[component][0] += unit['weight'] * credits.get(unit['id'], 0)
                totals[component][1] += unit['weight']
        if pred:
            claims = j['claims']
            faithful = sum(c['status'] == 'supported' for c in claims) / len(claims) if claims else (
                1 if g['empty_reason'] else 0)
            faith += faithful
            similar += j['similarity']['score']
            actual, expected = line_set(pred['source_line_spans']), line_set(g['source_line_spans'])
            # Extracts cite selected passages; generated summaries cite the full chunk input.
            if inp.get('candidate', 'generate') == 'extract':
                evidence_lines = {e['line'] for c in claims for e in c['evidence']}
                source = {line['line']: line for line in inp['source']}
                # Stored lines are the whole chunk; selected sentence lines must lie inside them.
                provenance += bool(actual == expected and evidence_lines <= expected and
                                   extract_provenance(pred, expected, source))
            else:
                provenance += actual == expected
            within += sum(not c.isspace() for c in pred['summary_text']) <= inp['gold']['budget_chars']
            details.append({'seq': seq, 'pred': pred['id'], 'faithfulness': faithful,
                            'similarity': j['similarity'], 'units': j['units'], 'claims': claims,
                            'diagnostics': j['diagnostics'],
                            'language_match': normalize_language(pred.get('language')) == normalize_language(g.get('language'))})
    for name, (num, den) in totals.items():
        comps[name] = num / den if den else None
    # Missing chunks and extras cannot earn these components; use the larger row count.
    denominator = max(n, p)
    comps.update(faithfulness=faith / denominator, similarity=similar / denominator,
                 provenance=provenance / denominator, budget=within / denominator)
    active = {k: v for k, v in w.items() if comps[k] is not None}
    require(sum(active.values()) > 0, 'No applicable positive weights')
    total = 100 * sum(comps[k] * v for k, v in active.items()) / sum(active.values())
    return {'scoring_version': VERSION, 'score': max(1, min(100, int(total + .5))),
            'components': comps, 'weights': w, 'active_weights': active,
            'matched': matched, 'gold_count': n, 'prediction_count': p,
            'missing_chunks': sorted(set(gold) - pairs.keys()), 'extra_predictions': extras,
            'details': details, 'input_sha256': fingerprint(inp), 'review_sha256': fingerprint(review)}


def report(inp, review, result, model):
    gold = inp['gold']
    lines = [f"# Summary score: {result['score']}/100", '',
             f"Record: {inp.get('record', {}).get('id', gold.get('record_id', 'unknown'))}",
             f"Scoring: {VERSION}; scorer: {model}; reviewer: {review['reviewer']}",
             f"Gold: {gold.get('skill_version')} / {gold.get('model_name')} / {gold.get('run_id')}",
             f"Candidate: {inp.get('candidate')} / {inp.get('algorithm')}; budget: {gold['budget_chars']}", '',
             '| Component | Value | Weight |', '|---|---:|---:|']
    for name, value in result['components'].items():
        lines.append(f"| {name} | {'N/A' if value is None else f'{value:.4f}'} | {result['weights'][name]} |")
    lines += ['', f"Aligned: {result['matched']}; gold: {result['gold_count']}; predictions: {result['prediction_count']}",
              f"Missing chunks: {result['missing_chunks']}",
              f"Extra predictions: {result['extra_predictions']}", '', '## Warnings and limitations', '']
    lines += ['- ' + x for x in inp.get('warnings', []) + review['limitations']]
    for item in result['details']:
        lines += ['', f"## Chunk {item['seq']} (prediction {item['pred']})", '', item['diagnostics'],
                  f"- Similarity {item['similarity']['score']:.2f} — {item['similarity']['reason']}",
                  f"- Language {'matches' if item['language_match'] else 'differs from'} gold (zh and zh-cn are the same)"]
        lines += [f"- Unit {u['id']}: {u['credit']} — {u['reason']}" for u in item['units']]
        lines += [f"- {c['status']}: {c['quote']} — {c['reason']}" for c in item['claims']]
    lines += ['', '## Snapshot identity', '',
              f"Source SHA-256: {gold.get('source_sha256', 'unknown')}",
              f"Chunks SHA-256: {gold.get('chunks_sha256', 'unknown')}",
              f"Input SHA-256: {result['input_sha256']}",
              f"Review SHA-256: {result['review_sha256']}"]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    exp = subs.add_parser('export')
    exp.add_argument('--record-id', type=int, required=True)
    exp.add_argument('--candidate', choices=('extract', 'generate'), default='extract')
    for name in ('algorithm', 'gold-version', 'gold-model', 'gold-run-id', 'out-dir', 'chunks'):
        exp.add_argument('--' + name)
    calc = subs.add_parser('score')
    calc.add_argument('--dir', required=True)
    calc.add_argument('--scorer-model', required=True)
    calc.add_argument('--weights')
    args = parser.parse_args()
    try:
        if args.command == 'export':
            export(args)
        else:
            directory = Path(args.dir)
            inp = json.loads((directory / 'input.json').read_text())
            require(inp['scoring_version'] == VERSION, 'Scoring version mismatch')
            review = json.loads((directory / 'judgments.json').read_text())
            require(args.scorer_model.strip(), 'Scorer model required')
            configured = weights(args.weights or ROOT / 'weights.json')
            result = score(inp, review, configured)
            result.update(scorer_model=args.scorer_model, reviewer=review['reviewer'],
                          scored_at=datetime.now(timezone.utc).isoformat())
            (directory / 'score.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            (directory / 'report.md').write_text(report(inp, review, result, args.scorer_model))
            print(json.dumps({'score': result['score'], 'report': str(directory / 'report.md')}))
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 3 if isinstance(exc, NoGold) else 4 if isinstance(exc, NoPredictions) else 1


if __name__ == '__main__':
    sys.exit(main())
