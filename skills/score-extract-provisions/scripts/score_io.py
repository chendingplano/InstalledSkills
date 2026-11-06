#!/usr/bin/env python3
"""Score extract_provisions output (kb.provisions) for one document against its gold provisions
(testbed.provisions).

export: write the full input.json audit snapshot and compact matching-input.json.
project: regenerate matching-input.json from a finalized audit snapshot.
score: expand/validate matches.json, compute the 1-100 score, write expanded decisions and report.
"""
import argparse
from datetime import datetime
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unicodedata


SKILL_DIR = Path(__file__).resolve().parent.parent
GOLD_SKILL = 'extract-provisions-benchmark'
BENCHMARK_DIR = SKILL_DIR.parent / GOLD_SKILL
WORKSPACE = SKILL_DIR.parents[2]
MIN_GOLD_VERSION = '1.0.0'
# Field checks on a matched pair. Weights are relative (normalized to sum 1.0), set in weights.json
# next to SKILL.md. text and lines earn partial credit; the others are pass/fail. lines is left out
# (and the rest renormalized) when the line file changed since the gold run.
DEFAULT_WEIGHTS = {'provision_type': 30, 'text': 20, 'lines': 20, 'subject': 15, 'location_type': 10,
                   'is_explicit': 5}
WEIGHTS_FILE = SKILL_DIR / 'weights.json'
# Only wording can differ for the subject; every other check is an enum, a boolean or computed.
OVERRIDABLE = {'subject'}
FP_CAUSES = {'gold_excluded', 'duplicate', 'split', 'not_in_gold', 'invalid'}
TYPES = ('mandatory', 'recommended', 'optional')
KINDS = ('requirement', 'prohibition', 'instruction', 'recommendation', 'permission')
GOLD_FIELDS = '''prov_id section source_line_spans source_table_rows evidence provision provision_en
prov_name prov_name_en provision_type provision_kind provision_subject provision_subject_en
location_type is_explicit confidence'''.split()
PRED_FIELDS = '''prov_id source_line_spans provision source_text prov_name prov_name_en provision_type
provision_subject provision_subject_en location_type is_explicit confidence'''.split()
CLAUSE_NUMBER = re.compile(r'^(?:[a-z]\)|[0-9]+\)|[a-z](?:\.[0-9]+)+|[0-9]+(?:\.[0-9]+)+|——|—|-)\s*')
EXIT_NO_GOLD = 3
EXIT_NO_PREDICTIONS = 4


class ScoreError(Exception):
    exit_code = 1


class NoGold(ScoreError):
    exit_code = EXIT_NO_GOLD


class NoPredictions(ScoreError):
    exit_code = EXIT_NO_PREDICTIONS


def require(condition, message):
    if not condition:
        raise ScoreError(message)


def load_benchmark_io():
    """The gold skill's helper: version_key, resolve_source and sql_text stay defined once."""
    spec = importlib.util.spec_from_file_location('benchmark_io', BENCHMARK_DIR / 'scripts' / 'benchmark_io.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bio = load_benchmark_io()


def load_weights(path=None):
    """Relative weights from weights.json (or --weights FILE), normalized to sum 1."""
    raw = dict(DEFAULT_WEIGHTS)
    file = Path(path) if path else WEIGHTS_FILE
    if file.exists():
        raw.update(json.loads(file.read_text(encoding='utf-8')))
    unknown = sorted(set(raw) - set(DEFAULT_WEIGHTS))
    require(not unknown, f'unknown weight names {unknown}; valid: {sorted(DEFAULT_WEIGHTS)}')
    require(all(isinstance(v, (int, float)) and v >= 0 for v in raw.values()), 'weights must be numbers >= 0')
    total = sum(raw.values())
    require(total > 0, 'weights must not all be 0')
    return {name: raw[name] / total for name in DEFAULT_WEIGHTS}


# ---------- database ----------

def db_env():
    """PG* variables for psql; fall back to ChenWeb/.env names. Values never reach argv or output."""
    env = dict(os.environ)
    if env.get('PGUSER') and env.get('PGDATABASE'):
        return env
    dotenv = WORKSPACE / 'ChenWeb' / '.env'
    values = {}
    if dotenv.exists():
        for line in dotenv.read_text(encoding='utf-8').splitlines():
            match = re.match(r'\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
            if match:
                values[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    for pg, name in (('PGUSER', 'PG_USER_NAME'), ('PGPASSWORD', 'PG_PASSWORD'),
                     ('PGDATABASE', 'PG_DB_NAME'), ('PGHOST', 'PG_HOST'), ('PGPORT', 'PG_PORT')):
        if not env.get(pg) and values.get(name):
            env[pg] = values[name]
    require(env.get('PGUSER') and env.get('PGDATABASE'),
            'No database settings: set PG* variables or ChenWeb/.env PG_USER_NAME/PG_DB_NAME')
    return env


def ensure_data_home():
    """Relative result paths need DATA_HOME_DIR; ChenWeb's mise environment defines it."""
    if os.environ.get('DATA_HOME_DIR'):
        return
    try:
        done = subprocess.run(['mise', 'env', '--json'], cwd=WORKSPACE / 'ChenWeb', text=True,
                              capture_output=True, timeout=60)
        value = json.loads(done.stdout or '{}').get('DATA_HOME_DIR') if done.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        value = None
    if value:
        os.environ['DATA_HOME_DIR'] = value


def query_json(sql):
    """Run one SELECT that returns a single JSON value; SQL goes through stdin."""
    done = subprocess.run(['psql', '-X', '-A', '-t', '-q', '-v', 'ON_ERROR_STOP=1'], input=sql,
                          text=True, capture_output=True, env=db_env())
    require(done.returncode == 0, f'psql failed: {done.stderr.strip()}')
    out = done.stdout.strip()
    return json.loads(out) if out else None


def fetch_input(record_id):
    return query_json(f'''SELECT json_build_object('id', id, 'result_filename', result_filename,
 'staging_filename', staging_filename, 'parser_name', parser_name, 'title', title,
 'doc_no', doc_no, 'doc_metadata', doc_metadata) FROM kb.inputs WHERE id = {record_id};''')


def fetch_gold_runs(record_id):
    """Runs from the audit table, so a run with zero gold provisions is still found."""
    return query_json(f'''SELECT COALESCE(json_agg(x ORDER BY x.benchmark_run_id), '[]') FROM (
 SELECT r.skill_version, r.model_name, r.run_id AS benchmark_run_id, r.source_sha256, r.language,
        (SELECT count(*) FROM testbed.provisions p
          WHERE (p.skill_name, p.skill_version, p.model_name, p.run_id)
              = (r.skill_name, r.skill_version, r.model_name, r.run_id)) AS rows
 FROM testbed.provision_benchmark_runs r
 WHERE r.input_record_id = {record_id} AND r.skill_name = '{GOLD_SKILL}') x;''')


def run_key_sql(run, alias):
    return ' AND '.join(f"{alias}.{column} = {bio.sql_text(run[key])}" for column, key in
                        (('skill_name', 'skill_name'), ('skill_version', 'skill_version'),
                         ('model_name', 'model_name'), ('run_id', 'benchmark_run_id')))


def fetch_gold(record_id, run):
    """Gold provisions of one run and the run's candidate ledger."""
    run = {**run, 'skill_name': GOLD_SKILL}
    cols = ', '.join(f'p.{c}' for c in GOLD_FIELDS)
    return query_json(f'''SELECT json_build_object(
 'rows', (SELECT COALESCE(json_agg(row_to_json(g) ORDER BY g.id), '[]') FROM (
   SELECT p.id, {cols} FROM testbed.provisions p
   WHERE p.input_record_id = {record_id} AND {run_key_sql(run, 'p')}) g),
 'candidates', (SELECT r.candidates FROM testbed.provision_benchmark_runs r
   WHERE {run_key_sql(run, 'r')}));''')


def fetch_predictions(record_id):
    cols = ', '.join(f'p.{c}' for c in PRED_FIELDS)
    return query_json(f'''SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.id), '[]') FROM (
 SELECT p.id, {cols}, p.extract_id, p.model_name, p.prompt_name, p.created_at
 FROM kb.provisions p WHERE p.input_record_id = {record_id} AND p.status = 'active') x;''')


# ---------- gold run selection ----------

def select_gold_run(runs, version=None, model=None, run_id=None):
    """Return the gold run to score against. Raise NoGold when nothing usable exists."""
    if not runs:
        raise NoGold('NO_GOLD: no gold provisions in testbed.provision_benchmark_runs for this document; '
                     'build them first with the extract-provisions-benchmark skill')
    floor = bio.version_key(MIN_GOLD_VERSION)
    if version or model or run_id:
        chosen = [r for r in runs if (not version or r['skill_version'] == version)
                  and (not model or r['model_name'] == model) and (not run_id or r['benchmark_run_id'] == run_id)]
        if not chosen:
            raise NoGold(f'NO_GOLD: no gold run matches the requested filters; available: {describe_runs(runs)}')
        run = max(chosen, key=lambda r: r['benchmark_run_id'])
        if bio.version_key(run['skill_version']) < floor:
            raise NoGold(f'NO_GOLD: gold run {run["benchmark_run_id"]} uses rules {run["skill_version"]}; '
                         f'scoring needs >= {MIN_GOLD_VERSION}')
        return run
    current = [r for r in runs if bio.version_key(r['skill_version']) >= floor and '-' not in r['skill_version']]
    if not current:
        raise NoGold(f'NO_GOLD: no released gold run under rules >= {MIN_GOLD_VERSION}; available: '
                     f'{describe_runs(runs)}. Name a pre-release run with --gold-version, or re-run '
                     'extract-provisions-benchmark')
    return max(current, key=lambda r: (bio.version_key(r['skill_version']), r['benchmark_run_id']))


def describe_runs(runs):
    return ', '.join(f'{r["skill_version"]}/{r["model_name"]}/{r["benchmark_run_id"]} ({r["rows"]} rows)'
                     for r in runs) or 'none'


# ---------- normalization and field checks ----------

def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text or '')).strip().lower())


def tight_text(text):
    """Provision text for the similarity check: NFKC, lower case, no whitespace, no leading clause
    number or list dash, no final full stop."""
    text = CLAUSE_NUMBER.sub('', norm(text))
    return re.sub(r'\s+', '', text).rstrip('。.;；')


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]
    return value if isinstance(value, list) else [value]


def line_set(spans):
    """Lines of "N", "N-M" (production and gold) or "N:M" spans."""
    lines = set()
    for span in as_list(spans):
        if isinstance(span, (int, float)) and span > 0:
            lines.add(int(span))
        elif isinstance(span, str) and re.fullmatch(r'\s*[0-9]+\s*(?:[-:]\s*[0-9]+\s*)?', span):
            bounds = [int(x) for x in re.split(r'[-:]', span)]
            lines.update(range(bounds[0], bounds[-1] + 1))
    lines.discard(0)
    return lines


def pred_text(row):
    return row.get('provision') or row.get('source_text') or ''


def text_similarity(gold, pred):
    a, b = tight_text(gold.get('provision')), tight_text(pred_text(pred))
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def field_checks(gold, pred, lines_comparable=True):
    same = lambda f: norm(gold.get(f)) == norm(pred.get(f))
    explicit = pred.get('is_explicit')
    return {'provision_type': same('provision_type'),
            'text': text_similarity(gold, pred),
            'lines': jaccard(line_set(gold.get('source_line_spans')), line_set(pred.get('source_line_spans')))
            if lines_comparable else None,
            'subject': bool(norm(gold.get('provision_subject'))) and same('provision_subject'),
            'location_type': same('location_type'),
            'is_explicit': explicit is not None and bool(explicit) == bool(gold.get('is_explicit'))}


def pair_credit(checks, weights):
    used = {f: ok for f, ok in checks.items() if ok is not None}
    total = sum(weights[f] for f in used)
    return sum(weights[f] * float(ok) for f, ok in used.items()) / total if total else 0.0


# ---------- export ----------

def compact_gold(row):
    return {k: row.get(k) for k in GOLD_FIELDS}


def compact_pred(row):
    out = {k: row.get(k) for k in PRED_FIELDS}
    out['provision'] = pred_text(row)
    out.pop('source_text', None)
    return out


def matching_view(inp):
    """LLM-only projection. Array order is the persisted, one-based ID mapping."""
    def rows(name):
        return [[r.get('source_line_spans') or [], pred_text(r), r.get('provision_subject') or '']
                for r in inp[name]]
    return {'v': 2, 'lc': inp['source']['lines_comparable'],
            'sa': inp['source'].get('available', bool(inp.get('source_text') or inp['source'].get('path'))),
            'g': rows('gold'),
            'p': rows('predictions'),
            'c': [[r.get('source_line_spans') or [], r.get('text') or '',
                   r['rule_id'], r.get('reason') or ''] for r in inp['gold_ledger']]}


def expand_matches(inp, wire, lang=None):
    """Decode strict v2 decisions to the existing scorer/report format; never infer omissions."""
    def valid(condition, message):
        require(condition, 'compact matches: ' + message)

    valid(isinstance(wire, dict) and set(wire) == {'v', 'p', 'm', 'f', 'o'},
          'expected exactly v,p,m,f,o')
    valid(type(wire['v']) is int and wire['v'] == 2, 'unsupported version')
    for key in ('p', 'm', 'f', 'o'):
        valid(isinstance(wire[key], list), f'{key} must be an array')
    gold, pred, ledger = inp['gold'], inp['predictions'], inp['gold_ledger']
    zh = (lang or inp.get('provenance', {}).get('lang', 'en')) == 'zh-cn'

    def at(rows, index):
        valid(type(index) is int, 'index must be an integer')
        valid(1 <= index <= len(rows), f'index {index} outside 1..{len(rows)}')
        return rows[index - 1]

    def row(value, lengths):
        valid(isinstance(value, list) and len(value) in lengths, f'decision row needs {lengths} elements')

    def note(value):
        valid(isinstance(value, str) and bool(value.strip()), 'explanation must be a nonempty string')
        return value

    result = {'pairs': [], 'missed': [], 'false_positives': [], 'overrides': []}
    paired_pred = {}
    for value in wire['p']:
        row(value, (2, 3))
        g, p = at(gold, value[0])['prov_id'], at(pred, value[1])['prov_id']
        result['pairs'].append({'gold': g, 'pred': p,
                                'note': note(value[2]) if len(value) == 3 else ''})
        paired_pred[value[1]] = g
    for value in wire['m']:
        row(value, (2, 3))
        g = at(gold, value[0])['prov_id']
        valid(type(value[1]) is int, 'miss target must be a prediction index or 0')
        if value[1] == 0:
            valid(len(value) == 3, 'genuine miss needs an explanation')
            text = note(value[2])
        else:
            p = at(pred, value[1])
            valid(value[1] in paired_pred, 'merge target must be paired')
            if inp['source']['lines_comparable']:
                valid(bool(line_set(at(gold, value[0])['source_line_spans']) &
                           line_set(p['source_line_spans'])), 'merge target shares no source line')
            text = (f'合并到 {p["prov_id"]}（已配对 {paired_pred[value[1]]}）' if zh else
                    f'merged into {p["prov_id"]} (paired with {paired_pred[value[1]]})')
            if len(value) == 3:
                text += ': ' + note(value[2])
        result['missed'].append({'gold': g, 'note': text})
    causes = {'x': 'gold_excluded', 's': 'split', 'd': 'duplicate', 'n': 'not_in_gold', 'i': 'invalid'}
    for value in wire['f']:
        row(value, (3, 4))
        pid = at(pred, value[0])['prov_id']
        valid(isinstance(value[1], str) and value[1] in causes, 'unknown false-positive cause')
        code, target = value[1:3]
        out = {'pred': pid, 'cause': causes[code]}
        if code == 'x':
            candidate = at(ledger, target)
            out.update(gold_candidate_id=candidate['candidate_id'], rule_id=candidate['rule_id'])
            text = candidate.get('reason') or candidate['rule_id']
        elif code == 's':
            out['gold'] = at(gold, target)['prov_id']
            text = ('拆分自 ' if zh else 'split from ') + out['gold']
        elif code == 'd':
            out['of'] = at(pred, target)['prov_id']
            valid(target != value[0], 'duplicate cannot refer to itself')
            text = ('重复 ' if zh else 'duplicate of ') + out['of']
        else:
            valid(target is None and len(value) == 4, 'not-in-gold/invalid require null target and explanation')
            text = ''
        out['note'] = note(value[3]) if len(value) == 4 else text
        result['false_positives'].append(out)
    seen_overrides = set()
    for value in wire['o']:
        row(value, (3,))
        g = at(gold, value[0])['prov_id']
        valid(type(value[1]) is bool, 'subject override must contain a boolean')
        valid(g not in seen_overrides, 'duplicate subject override')
        seen_overrides.add(g)
        result['overrides'].append({'gold': g, 'field': 'subject', 'correct': value[1],
                                    'reason': note(value[2])})
    check_matches(inp, result)
    duplicates = {r['pred']: r['of'] for r in result['false_positives'] if r['cause'] == 'duplicate'}
    for pid in duplicates:
        seen = set()
        while pid in duplicates:
            valid(pid not in seen, 'duplicate references form a cycle')
            seen.add(pid)
            pid = duplicates[pid]
    return result


def suggestions(gold_rows, pred_rows, weights):
    """For each gold row, predicted rows sharing a source line, the most similar text first."""
    result = {}
    for g in gold_rows:
        gl = line_set(g['source_line_spans'])
        near = []
        for p in pred_rows:
            if gl & line_set(p['source_line_spans']):
                near.append({'pred': p['prov_id'], 'text_similarity': round(text_similarity(g, p), 2),
                             'credit': round(pair_credit(field_checks(g, p), weights), 2)})
        result[g['prov_id']] = sorted(near, key=lambda s: (-s['text_similarity'], -s['credit']))[:5]
    return result


def default_out_dir(source_path, run):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return (source_path.parent / 'extract-provisions-scores' / run['skill_version'] / run['model_name']
            / run['benchmark_run_id'] / stamp)


def export(record_id, version=None, model=None, run_id=None, out_dir=None):
    record = fetch_input(record_id)
    require(record, f'Unknown document: kb.inputs.id = {record_id} does not exist')
    runs = fetch_gold_runs(record_id)
    run = select_gold_run(runs, version, model, run_id)
    gold = fetch_gold(record_id, run)
    preds = fetch_predictions(record_id)
    if not preds:
        raise NoPredictions(f'NO_PREDICTIONS: kb.provisions has no active rows for document {record_id}; '
                            'run extract_provisions on it before scoring')
    warnings = []
    if not gold['rows']:
        warnings.append('The gold run has zero provisions: every predicted row is a false positive')
    ensure_data_home()
    try:
        source_path = bio.resolve_source(record)
        current_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        source_path, current_sha = None, None
        warnings.append(f'Source line file not readable ({exc}); pairs are not required to share a line')
    lines_comparable = current_sha is not None and current_sha == run['source_sha256']
    if current_sha and not lines_comparable:
        warnings.append('The line file changed since the gold run (SHA-256 differs); line numbers are '
                        'not comparable, so pairs are not required to share a line and lines is not checked')
    extracts = sorted({p.get('extract_id') or '' for p in preds})
    if len(extracts) > 1:
        warnings.append(f'kb.provisions rows come from {len(extracts)} different extractions')
    gold_rows = [compact_gold(r) for r in gold['rows']]
    pred_rows = [compact_pred(r) for r in preds]
    payload = {
        'record_id': record_id, 'title': record.get('title'), 'doc_no': record.get('doc_no'),
        'gold_run': {**run, 'rows_scored': len(gold_rows)},
        'other_gold_runs': [r for r in runs if r is not run],
        'extraction': {'extract_ids': extracts,
                       'model_names': sorted({p.get('model_name') or '' for p in preds}),
                       'prompt_names': sorted({p.get('prompt_name') or '' for p in preds}),
                       'created_at': [min(p['created_at'] for p in preds), max(p['created_at'] for p in preds)]},
        'source': {'path': str(source_path) if source_path else None, 'current_sha256': current_sha,
                   'gold_sha256': run['source_sha256'], 'lines_comparable': lines_comparable,
                   'available': source_path is not None},
        'warnings': warnings,
        'gold': gold_rows,
        'gold_ledger': [c for c in (gold.get('candidates') or []) if c.get('decision') in ('excluded', 'duplicate')],
        'predictions': pred_rows,
        'suggestions': suggestions(gold_rows, pred_rows, load_weights()),
    }
    out_dir = Path(out_dir) if out_dir else default_out_dir(source_path or Path.cwd() / 'x', run)
    out_dir.mkdir(parents=True, exist_ok=False)
    path = out_dir / 'input.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    (out_dir / 'matching-input.json').write_text(
        json.dumps(matching_view(payload), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return path, payload


# ---------- score ----------

def check_matches(inp, matches):
    """Every gold row is paired or missed once; every predicted row is paired or a false positive
    once; paired rows share a source line when line numbers are comparable."""
    gold = {g['prov_id']: g for g in inp['gold']}
    pred = {p['prov_id']: p for p in inp['predictions']}
    ledger_ids = {c['candidate_id'] for c in inp['gold_ledger']}
    pairs, missed, fps = matches.get('pairs', []), matches.get('missed', []), matches.get('false_positives', [])
    seen_gold = [p['gold'] for p in pairs] + [m['gold'] for m in missed]
    seen_pred = [p['pred'] for p in pairs] + [f['pred'] for f in fps]
    for name, seen, expected in (('gold', seen_gold, set(gold)), ('predicted', seen_pred, set(pred))):
        dupes = sorted({x for x in seen if seen.count(x) > 1})
        require(not dupes, f'{name} rows accounted for more than once: {dupes}')
        unknown = sorted(set(seen) - expected)
        require(not unknown, f'unknown {name} provision IDs: {unknown}')
        absent = sorted(expected - set(seen))
        require(not absent, f'{name} rows not accounted for: {absent}')
    if inp['source']['lines_comparable']:
        for p in pairs:
            require(line_set(gold[p['gold']]['source_line_spans']) & line_set(pred[p['pred']]['source_line_spans']),
                    f'pair {p["gold"]}/{p["pred"]}: the rows share no source line, so they are different statements')
    paired_gold = {p['gold'] for p in pairs}
    for f in fps:
        require(f.get('cause') in FP_CAUSES, f'false positive {f["pred"]}: cause must be one of {sorted(FP_CAUSES)}')
        if f['cause'] == 'gold_excluded':
            require(f.get('gold_candidate_id') in ledger_ids,
                    f'false positive {f["pred"]}: gold_candidate_id must name an excluded/duplicate ledger candidate')
        if f['cause'] == 'duplicate':
            require(f.get('of') in pred and f.get('of') != f['pred'],
                    f'false positive {f["pred"]}: "of" must name the other predicted row')
        if f['cause'] == 'split':
            require(f.get('gold') in paired_gold,
                    f'false positive {f["pred"]}: a split names the paired gold row it is part of ("gold")')
    for o in matches.get('overrides', []):
        require(o.get('gold') in paired_gold, f'override for unpaired gold row {o.get("gold")}')
        require(o.get('field') in OVERRIDABLE, f'override field must be one of {sorted(OVERRIDABLE)}')
        require(isinstance(o.get('correct'), bool), 'override "correct" must be true or false')
        require(str(o.get('reason') or '').strip(), f'override for {o["gold"]}/{o["field"]} needs a reason')


def metrics_for(gold_ids, pred_ids, pairs):
    """Soft and matched-row precision/recall over a subset: recall counts pairs whose gold row is in
    the subset, precision pairs whose predicted row is."""
    n_gold, n_pred = len(gold_ids), len(pred_ids)
    credit_r = sum(p['credit'] for p in pairs if p['gold'] in gold_ids)
    credit_p = sum(p['credit'] for p in pairs if p['pred'] in pred_ids)
    matched_r = sum(1 for p in pairs if p['gold'] in gold_ids)
    matched_p = sum(1 for p in pairs if p['pred'] in pred_ids)
    f1 = lambda p, r: 2 * p * r / (p + r) if p + r else 0.0
    soft_r = credit_r / n_gold if n_gold else 0.0
    soft_p = credit_p / n_pred if n_pred else 0.0
    hard_r = matched_r / n_gold if n_gold else 0.0
    hard_p = matched_p / n_pred if n_pred else 0.0
    return {'score': max(1, min(100, round(100 * f1(soft_p, soft_r)))), 'soft_f1': f1(soft_p, soft_r),
            'soft_precision': soft_p, 'soft_recall': soft_r, 'precision': hard_p, 'recall': hard_r,
            'f1': f1(hard_p, hard_r), 'gold_rows': n_gold, 'predicted_rows': n_pred, 'matched': matched_r}


def score(inp, matches, weights=None):
    weights = weights or load_weights()
    check_matches(inp, matches)
    gold = {g['prov_id']: g for g in inp['gold']}
    pred = {p['prov_id']: p for p in inp['predictions']}
    overrides = {(o['gold'], o['field']): o for o in matches.get('overrides', [])}
    comparable = inp['source']['lines_comparable']
    pairs = []
    for p in matches.get('pairs', []):
        checks = field_checks(gold[p['gold']], pred[p['pred']], comparable)
        for field in checks:
            if (p['gold'], field) in overrides and checks[field] is not None:
                checks[field] = overrides[(p['gold'], field)]['correct']
        pairs.append({**p, 'checks': checks, 'credit': pair_credit(checks, weights)})
    main = metrics_for(set(gold), set(pred), pairs)
    groups = {t: metrics_for({g for g, row in gold.items() if row['provision_type'] == t},
                             {p for p, row in pred.items() if norm(row.get('provision_type')) == t}, pairs)
              for t in TYPES}
    # Production stores no kind, so a kind has recall only.
    paired = {p['gold']: p for p in pairs}
    recall_by_kind = {}
    for kind in KINDS:
        ids = [g for g, row in gold.items() if row['provision_kind'] == kind]
        if ids:
            recall_by_kind[kind] = {'gold_rows': len(ids), 'matched': sum(g in paired for g in ids),
                                    'soft_recall': sum(paired[g]['credit'] for g in ids if g in paired) / len(ids)}
    field_acc = {}
    for f in weights:
        vals = [float(p['checks'][f]) for p in pairs if p['checks'][f] is not None]
        field_acc[f] = (sum(vals) / len(vals)) if vals else None
    return {'score': main['score'], 'main': main, 'groups': groups, 'recall_by_kind': recall_by_kind,
            'field_accuracy': field_acc, 'weights': weights, 'pairs': pairs,
            'missed': matches.get('missed', []), 'false_positives': matches.get('false_positives', []),
            'overrides': matches.get('overrides', [])}


def pct(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def short(text, n=60):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text if len(text) <= n else text[:n - 1] + '…'


def report(inp, result, scorer_model):
    run, ext, src = inp['gold_run'], inp['extraction'], inp['source']
    gold = {g['prov_id']: g for g in inp['gold']}
    pred = {p['prov_id']: p for p in inp['predictions']}
    weights = result['weights']
    lines = [f'# extract_provisions score — record {inp["record_id"]}', '',
             f'**Score: {result["score"]} / 100**', '',
             '| Item | Value |', '|---|---|',
             f'| Document | {inp["record_id"]} · {inp.get("doc_no") or ""} {inp.get("title") or ""} |',
             f'| Gold run | {run["skill_version"]} / {run["model_name"]} / `{run["benchmark_run_id"]}` |',
             f'| Extraction | {", ".join(ext["model_names"]) or "—"} · {", ".join(ext["prompt_names"]) or "—"} '
             f'(saved {ext["created_at"][1]}) |',
             f'| Source lines comparable | {"yes" if src["lines_comparable"] else "no"} |',
             f'| Scored by | {scorer_model} |', '',
             '## Components', '',
             '| | Gold | Predicted | Matched | Soft precision | Soft recall | Soft F1 | Matched-row precision | Matched-row recall | Score |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for label, v in [('All provisions', result['main'])] + list(result['groups'].items()):
        lines.append(f'| {label} | {v["gold_rows"]} | {v["predicted_rows"]} | {v["matched"]} '
                     f'| {pct(v["soft_precision"])} | {pct(v["soft_recall"])} | {pct(v["soft_f1"])} '
                     f'| {pct(v["precision"])} | {pct(v["recall"])} | {v["score"]} |')
    lines += ['', 'Type rows count a pair under its gold row for recall and its predicted row for precision.',
              '', '## Recall by gold kind', '', '| Kind | Gold | Matched | Soft recall |', '|---|---:|---:|---:|']
    lines += [f'| {k} | {v["gold_rows"]} | {v["matched"]} | {pct(v["soft_recall"])} |'
              for k, v in result['recall_by_kind'].items()]
    lines += ['', '## Field accuracy on matched pairs', '', '| Field | Weight | Accuracy |', '|---|---:|---:|']
    lines += [f'| {f} | {w:.2f} | {pct(result["field_accuracy"][f])} |' for f, w in weights.items()]
    weak = [p for p in result['pairs'] if p['credit'] < 1]
    lines += ['', f'## Matched pairs with field errors ({len(weak)} of {len(result["pairs"])})', '']
    if weak:
        lines += ['| Gold | Predicted | Provision | Failed checks (gold → predicted) | Credit | Note |',
                  '|---|---|---|---|---:|---|']
        for p in weak:
            g, pr = gold[p['gold']], pred[p['pred']]
            failed = []
            for f, ok in p['checks'].items():
                if ok is None or ok == 1:
                    continue
                if f == 'text':
                    failed.append(f'text {pct(ok)} similar')
                elif f == 'lines':
                    failed.append(f'lines {",".join(as_list(g.get("source_line_spans")))} → '
                                  f'{",".join(str(x) for x in as_list(pr.get("source_line_spans")))}')
                elif f == 'subject':
                    failed.append(f'subject {g.get("provision_subject")} → {pr.get("provision_subject")}')
                else:
                    failed.append(f'{f} {g.get(f)} → {pr.get(f)}')
            lines.append(f'| {p["gold"]} | {p["pred"]} | {short(g["provision"])} | {"; ".join(failed)} | '
                         f'{p["credit"]:.2f} | {p.get("note", "")} |')
    lines += ['', f'## Missed gold provisions ({len(result["missed"])})', '']
    lines += [f'- `{x["gold"]}` [{gold[x["gold"]]["provision_kind"]}] {short(gold[x["gold"]]["provision"])} '
              f'line {",".join(as_list(gold[x["gold"]]["source_line_spans"]))}: {x.get("note", "")}'
              for x in result['missed']] or ['None.']
    lines += ['', f'## False positives ({len(result["false_positives"])})', '']
    for f in result['false_positives']:
        ref = {'gold_excluded': f'gold {f.get("gold_candidate_id")} {f.get("rule_id", "")}',
               'duplicate': f'duplicate of {f.get("of")}', 'split': f'split of {f.get("gold")}'}.get(f['cause'], f['cause'])
        lines.append(f'- `{f["pred"]}` {short(pred[f["pred"]]["provision"])} — {ref}: {f.get("note", "")}')
    if not result['false_positives']:
        lines.append('None.')
    if result['overrides']:
        lines += ['', '## Field-check overrides', '']
        lines += [f'- `{o["gold"]}` {o["field"]} → {"correct" if o["correct"] else "wrong"}: {o["reason"]}'
                  for o in result['overrides']]
    warnings = list(inp['warnings'])
    if run['model_name'] == scorer_model:
        warnings.append(f'The gold run and the matching were made by the same model ({scorer_model}); '
                        'a different scorer model would be an independent check')
    if warnings:
        lines += ['', '## Warnings', ''] + [f'- {w}' for w in warnings]
    lines += ['', '## Method', '',
              'Each matched pair earns credit = weighted share of passed field checks '
              f'({", ".join(f"{f} {w:.2f}" for f, w in weights.items())}); text earns its similarity and lines '
              'its line-set overlap; lines is left out when line numbers are not comparable. Soft precision = '
              'credit / predicted rows, soft recall = credit / gold rows, score = round(100 × soft F1), '
              'clamped to 1–100.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    ex = sub.add_parser('export', help='select the gold run and write input.json')
    ex.add_argument('--record-id', required=True, type=int, help='kb.inputs.id')
    ex.add_argument('--gold-version', help=f'gold rules version (default: newest released >= {MIN_GOLD_VERSION})')
    ex.add_argument('--gold-model', help='gold run model_name')
    ex.add_argument('--gold-run-id', help='gold run_id (yyyymmdd_hhmmss)')
    ex.add_argument('--out-dir', help='new directory for the score artifacts')
    sc = sub.add_parser('score', help='check matches.json and write score.json and report.md')
    sc.add_argument('--dir', required=True, type=Path, help='directory holding input.json and matches.json')
    sc.add_argument('--scorer-model', required=True, help='exact ID of the model that made the matches')
    sc.add_argument('--weights', help=f'JSON file of relative weights (default: {WEIGHTS_FILE.name} in the skill dir)')
    sc.add_argument('--require-compact', action='store_true', help='require the strict v2 decision contract')
    sc.add_argument('--lang', choices=('en', 'zh-cn'), help='language for expanded diagnostic notes')
    project = sub.add_parser('project', help='derive matching-input.json from the complete input.json snapshot')
    project.add_argument('--dir', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'export':
        require(args.record_id > 0, 'record ID must be a positive integer')
        path, payload = export(args.record_id, args.gold_version, args.gold_model, args.gold_run_id, args.out_dir)
        run = payload['gold_run']
        print(json.dumps({'input': str(path), 'matching_input': str(path.parent / 'matching-input.json'),
                          'source_path': payload['source']['path'],
                          'lines_comparable': payload['source']['lines_comparable'],
                          'gold_run': f'{run["skill_version"]}/{run["model_name"]}/'
                          f'{run["benchmark_run_id"]}', 'gold_rows': len(payload['gold']),
                          'predicted_rows': len(payload['predictions']), 'warnings': payload['warnings']},
                         ensure_ascii=False))
        return
    inp = json.loads((args.dir / 'input.json').read_text(encoding='utf-8'))
    if args.action == 'project':
        (args.dir / 'matching-input.json').write_text(
            json.dumps(matching_view(inp), ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        return
    matches = json.loads((args.dir / 'matches.json').read_text(encoding='utf-8'))
    if args.require_compact or (isinstance(matches, dict) and set(matches) & {'v', 'p', 'm', 'f', 'o'}):
        matches = expand_matches(inp, matches, args.lang)
    else:
        check_matches(inp, matches)
    (args.dir / 'matches-expanded.json').write_text(
        json.dumps(matches, ensure_ascii=False, indent=2), encoding='utf-8')
    result = score(inp, matches, load_weights(args.weights))
    result.update(record_id=inp['record_id'], gold_run=inp['gold_run'], scorer_model=args.scorer_model,
                  scored_at=datetime.now().isoformat(timespec='seconds'))
    (args.dir / 'score.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    (args.dir / 'report.md').write_text(report(inp, result, args.scorer_model), encoding='utf-8')
    m = result['main']
    print(json.dumps({'score': result['score'], 'soft_precision': round(m['soft_precision'], 3),
                      'soft_recall': round(m['soft_recall'], 3), 'soft_f1': round(m['soft_f1'], 3),
                      'matched_row_precision': round(m['precision'], 3), 'matched_row_recall': round(m['recall'], 3),
                      'groups': {k: v['score'] for k, v in result['groups'].items()},
                      'report': str(args.dir / 'report.md')}))


if __name__ == '__main__':
    try:
        main()
    except ScoreError as exc:
        print(f'score_io: {exc}', file=sys.stderr)
        sys.exit(exc.exit_code)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f'score_io: {exc}', file=sys.stderr)
        sys.exit(1)
