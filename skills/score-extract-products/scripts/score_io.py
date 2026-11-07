#!/usr/bin/env python3
"""Score extract_products output (kb.products) for one document against its gold product relations
(testbed.products).

export: write the full input.json audit snapshot and compact matching-input.json.
project: regenerate matching-input.json from a finalized audit snapshot.
score: expand/validate matches.json, compute the 1-100 score and product detection, write expanded
decisions and report.
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
GOLD_SKILL = 'extract-products-benchmark'
BENCHMARK_DIR = SKILL_DIR.parent / GOLD_SKILL
WORKSPACE = SKILL_DIR.parents[2]
MIN_GOLD_VERSION = '1.0.0'
# Field checks on a matched pair. Weights are relative (normalized over the checks that apply to a
# pair), set in weights.json next to SKILL.md. requirement_text, lines, parameters, conditions and
# related_products earn partial credit; the others are pass/fail. A check that does not apply to a
# pair (None) is left out and the rest renormalized.
DEFAULT_WEIGHTS = {'relation_type': 20, 'requirement_text': 15, 'product_type': 10, 'name': 10, 'lines': 10,
                   'obligation_level': 10, 'parameters': 10, 'conditions': 5, 'related_products': 5,
                   'responsible_actor': 5}
WEIGHTS_FILE = SKILL_DIR / 'weights.json'
# Only wording can differ for these; every other check is an enum or computed.
OVERRIDABLE = {'name', 'related_products', 'responsible_actor'}
FP_CAUSES = {'gold_excluded', 'extra_relation', 'duplicate', 'not_in_gold', 'invalid'}
INTER_PRODUCT = {'component_of', 'contains_product', 'compatible_with', 'replacement_or_alternative'}
GOLD_FIELDS = '''product_rel_id product_key section product_name product_name_en canonical_name canonical_name_en
product_type relation_type relation_summary evidence_quote evidence_lines obligation_level requirement_text
conditions exceptions parameters related_products responsible_actor confidence'''.split()
PRED_FIELDS = '''product_rel_id product_name product_name_en canonical_name canonical_name_en product_type
relation_type relation_summary evidence_quote evidence_lines obligation_level requirement_text conditions
exceptions parameters related_products responsible_actor confidence'''.split()
SIMILAR_ITEM = 0.6
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
    """Runs from the audit table, so a run with zero gold rows is still found."""
    return query_json(f'''SELECT COALESCE(json_agg(x ORDER BY x.benchmark_run_id), '[]') FROM (
 SELECT r.skill_version, r.model_name, r.run_id AS benchmark_run_id, r.source_sha256, r.language,
        (SELECT count(*) FROM testbed.products p
          WHERE (p.skill_name, p.skill_version, p.model_name, p.run_id)
              = (r.skill_name, r.skill_version, r.model_name, r.run_id)) AS rows
 FROM testbed.product_benchmark_runs r
 WHERE r.input_record_id = {record_id} AND r.skill_name = '{GOLD_SKILL}') x;''')


def run_key_sql(run, alias):
    return ' AND '.join(f"{alias}.{column} = {bio.sql_text(run[key])}" for column, key in
                        (('skill_name', 'skill_name'), ('skill_version', 'skill_version'),
                         ('model_name', 'model_name'), ('run_id', 'benchmark_run_id')))


def fetch_gold(record_id, run):
    """Gold rows of one run and the run's candidate ledger."""
    run = {**run, 'skill_name': GOLD_SKILL}
    cols = ', '.join(f'p.{c}' for c in GOLD_FIELDS)
    return query_json(f'''SELECT json_build_object(
 'rows', (SELECT COALESCE(json_agg(row_to_json(g) ORDER BY g.id), '[]') FROM (
   SELECT p.id, {cols} FROM testbed.products p
   WHERE p.input_record_id = {record_id} AND {run_key_sql(run, 'p')}) g),
 'candidates', (SELECT r.candidates FROM testbed.product_benchmark_runs r
   WHERE {run_key_sql(run, 'r')}));''')


def fetch_predictions(record_id):
    cols = ', '.join(f'p.{c}' for c in PRED_FIELDS)
    return query_json(f'''SELECT COALESCE(json_agg(row_to_json(x) ORDER BY x.id), '[]') FROM (
 SELECT p.id, {cols}, p.model_name, p.prompt_name, p.create_time
 FROM kb.products p WHERE p.input_record_id = {record_id} AND p.status = 'active') x;''')


# ---------- gold run selection ----------

def select_gold_run(runs, version=None, model=None, run_id=None):
    """Return the gold run to score against. Raise NoGold when nothing usable exists."""
    if not runs:
        raise NoGold('NO_GOLD: no gold products in testbed.product_benchmark_runs for this document; '
                     'build them first with the extract-products-benchmark skill')
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
                     'extract-products-benchmark')
    return max(current, key=lambda r: (bio.version_key(r['skill_version']), r['benchmark_run_id']))


def describe_runs(runs):
    return ', '.join(f'{r["skill_version"]}/{r["model_name"]}/{r["benchmark_run_id"]} ({r["rows"]} rows)'
                     for r in runs) or 'none'


# ---------- normalization and field checks ----------

def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text or '')).strip().lower())


def name_key(text):
    """Names and parties: NFKC, case fold, no whitespace or punctuation."""
    return ''.join(ch for ch in norm(text) if not ch.isspace() and not unicodedata.category(ch).startswith('P'))


def tight_text(text):
    """Requirement text for the similarity check: NFKC, lower case, no whitespace, no part separator,
    no final full stop."""
    return re.sub(r'[\s…]+', '', norm(text)).rstrip('。.;；')


def value_key(value, unit):
    """A parameter's value and unit as one comparable string (a unit may sit in either field)."""
    text = norm(f'{value or ""}{unit or ""}').replace('>=', '≥').replace('<=', '≤')
    return re.sub(r'[～〜]', '~', re.sub(r'\s+', '', text))


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
    """Lines of "N", "N-M", "N#rK"/"N#hK" (a table row counts as its line) or integer spans."""
    lines = set()
    for span in as_list(spans):
        if isinstance(span, (int, float)) and span > 0:
            lines.add(int(span))
            continue
        match = isinstance(span, str) and re.fullmatch(r'\s*([0-9]+)\s*(?:[-:]\s*([0-9]+)\s*|#[hr][0-9]+\s*)?', span)
        if match:
            lines.update(range(int(match.group(1)), int(match.group(2) or match.group(1)) + 1))
    lines.discard(0)
    return lines


def item_f1(matched, n_gold, n_pred):
    return 2 * matched / (n_gold + n_pred) if n_gold + n_pred else 1.0


def greedy_matches(gold_items, pred_items, similar):
    """One-to-one matches between two lists, best similarity first."""
    scored = sorted(((similar(g, p), i, j) for i, g in enumerate(gold_items) for j, p in enumerate(pred_items)),
                    reverse=True)
    used_g, used_p, matched = set(), set(), 0
    for value, i, j in scored:
        if value and i not in used_g and j not in used_p:
            used_g.add(i)
            used_p.add(j)
            matched += 1
    return matched


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def parameters_check(gold, pred):
    g = [value_key(x.get('value'), x.get('unit')) for x in as_list(gold.get('parameters')) if isinstance(x, dict)]
    p = [value_key(x.get('value'), x.get('unit')) for x in as_list(pred.get('parameters')) if isinstance(x, dict)]
    if not g and not p:
        return None
    return item_f1(greedy_matches(g, p, lambda a, b: a == b and bool(a)), len(g), len(p))


def qualifier_items(row):
    return ([('c', tight_text(x)) for x in as_list(row.get('conditions')) if str(x or '').strip()] +
            [('e', tight_text(x)) for x in as_list(row.get('exceptions')) if str(x or '').strip()])


def conditions_check(gold, pred):
    g, p = qualifier_items(gold), qualifier_items(pred)
    if not g and not p:
        return None
    similar = lambda a, b: a[0] == b[0] and ratio(a[1], b[1]) >= SIMILAR_ITEM
    return item_f1(greedy_matches(g, p, similar), len(g), len(p))


def related_check(gold, pred):
    g = [name_key(x.get('product_name')) for x in as_list(gold.get('related_products')) if isinstance(x, dict)]
    p = [name_key(x.get('product_name')) for x in as_list(pred.get('related_products')) if isinstance(x, dict)]
    if not g and not p and gold.get('relation_type') not in INTER_PRODUCT:
        return None
    return item_f1(greedy_matches(g, p, lambda a, b: a == b and bool(a)), len(g), len(p))


def requirement_check(gold, pred):
    a = tight_text(gold.get('requirement_text'))
    if not a:
        return None
    return ratio(a, tight_text(pred.get('requirement_text')))


def name_check(gold, pred):
    names = lambda row: {name_key(row.get(f)) for f in ('product_name', 'canonical_name')} - {''}
    return bool(names(gold) & names(pred))


def actor_check(gold, pred):
    a, b = name_key(gold.get('responsible_actor')), name_key(pred.get('responsible_actor'))
    if not a and not b:
        return None
    return a == b


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def field_checks(gold, pred, lines_comparable=True):
    same = lambda f: norm(gold.get(f)) == norm(pred.get(f))
    return {'relation_type': same('relation_type'),
            'requirement_text': requirement_check(gold, pred),
            'product_type': same('product_type'),
            'name': name_check(gold, pred),
            'lines': jaccard(line_set(gold.get('evidence_lines')), line_set(pred.get('evidence_lines')))
            if lines_comparable else None,
            'obligation_level': same('obligation_level'),
            'parameters': parameters_check(gold, pred),
            'conditions': conditions_check(gold, pred),
            'related_products': related_check(gold, pred),
            'responsible_actor': actor_check(gold, pred)}


def pair_credit(checks, weights):
    used = {f: ok for f, ok in checks.items() if ok is not None}
    total = sum(weights[f] for f in used)
    return sum(weights[f] * float(ok) for f, ok in used.items()) / total if total else 0.0


# ---------- export ----------

def compact_row(row, fields):
    return {k: row.get(k) for k in fields}


def product_ordinals(gold_rows):
    """One-based gold product number per product_key, in order of first row."""
    ordinals = {}
    for row in gold_rows:
        ordinals.setdefault(row['product_key'], len(ordinals) + 1)
    return ordinals


def matching_view(inp):
    """LLM-only projection. Array order is the persisted, one-based ID mapping."""
    ordinals = product_ordinals(inp['gold'])

    def row(r):
        return [r.get('evidence_lines') or [], r.get('product_name') or '', r.get('canonical_name') or '',
                r.get('relation_type') or '', r.get('requirement_text') or '']
    return {'v': 2, 'lc': inp['source']['lines_comparable'],
            'sa': inp['source'].get('available', bool(inp.get('source_text') or inp['source'].get('path'))),
            'g': [row(r) + [ordinals[r['product_key']]] for r in inp['gold']],
            'p': [row(r) for r in inp['predictions']],
            'c': [[r.get('source_line_spans') or [], r.get('text') or '',
                   r['rule_id'], r.get('reason') or ''] for r in inp['gold_ledger']]}


def expand_matches(inp, wire, lang=None):
    """Decode strict v2 decisions to the scorer/report format; never infer omissions."""
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
        g, p = at(gold, value[0])['product_rel_id'], at(pred, value[1])['product_rel_id']
        result['pairs'].append({'gold': g, 'pred': p,
                                'note': note(value[2]) if len(value) == 3 else ''})
        paired_pred[value[1]] = g
    for value in wire['m']:
        row(value, (2, 3))
        g = at(gold, value[0])['product_rel_id']
        valid(type(value[1]) is int, 'miss target must be a prediction index or 0')
        if value[1] == 0:
            valid(len(value) == 3, 'genuine miss needs an explanation')
            text = note(value[2])
        else:
            p = at(pred, value[1])
            valid(value[1] in paired_pred, 'merge target must be paired')
            if inp['source']['lines_comparable']:
                valid(bool(line_set(at(gold, value[0])['evidence_lines']) &
                           line_set(p['evidence_lines'])), 'merge target shares no source line')
            text = (f'合并到 {p["product_rel_id"]}（已配对 {paired_pred[value[1]]}）' if zh else
                    f'merged into {p["product_rel_id"]} (paired with {paired_pred[value[1]]})')
            if len(value) == 3:
                text += ': ' + note(value[2])
        result['missed'].append({'gold': g, 'note': text})
    causes = {'x': 'gold_excluded', 'r': 'extra_relation', 'd': 'duplicate', 'n': 'not_in_gold', 'i': 'invalid'}
    for value in wire['f']:
        row(value, (3, 4))
        pid = at(pred, value[0])['product_rel_id']
        valid(isinstance(value[1], str) and value[1] in causes, 'unknown false-positive cause')
        code, target = value[1:3]
        out = {'pred': pid, 'cause': causes[code]}
        if code == 'x':
            candidate = at(ledger, target)
            out.update(gold_candidate_id=candidate['candidate_id'], rule_id=candidate['rule_id'])
            text = candidate.get('reason') or candidate['rule_id']
        elif code == 'r':
            g = at(gold, target)
            out.update(gold=g['product_rel_id'], product_key=g['product_key'])
            text = (f'产品 {g["product_name"]} 正确，但金标准没有关系 {at(pred, value[0]).get("relation_type")}' if zh else
                    f'product {g["product_name"]} is right; gold has no {at(pred, value[0]).get("relation_type")} relation')
        elif code == 'd':
            out['of'] = at(pred, target)['product_rel_id']
            valid(target != value[0], 'duplicate cannot refer to itself')
            text = ('重复 ' if zh else 'duplicate of ') + out['of']
        else:
            valid(target is None and len(value) == 4, 'not-in-gold/invalid require null target and explanation')
            text = ''
        out['note'] = note(value[3]) if len(value) == 4 else text
        result['false_positives'].append(out)
    seen_overrides = set()
    for value in wire['o']:
        row(value, (4,))
        g = at(gold, value[0])['product_rel_id']
        valid(value[1] in OVERRIDABLE, f'override field must be one of {sorted(OVERRIDABLE)}')
        valid(type(value[2]) is bool, 'override must contain a boolean')
        valid((g, value[1]) not in seen_overrides, 'duplicate override')
        seen_overrides.add((g, value[1]))
        result['overrides'].append({'gold': g, 'field': value[1], 'correct': value[2], 'reason': note(value[3])})
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
    """For each gold row, predicted rows sharing a source line, same-name rows first."""
    result = {}
    for g in gold_rows:
        gl = line_set(g['evidence_lines'])
        near = []
        for p in pred_rows:
            if gl & line_set(p['evidence_lines']):
                near.append({'pred': p['product_rel_id'], 'same_name': name_check(g, p),
                             'same_relation': norm(g['relation_type']) == norm(p.get('relation_type')),
                             'credit': round(pair_credit(field_checks(g, p), weights), 2)})
        result[g['product_rel_id']] = sorted(
            near, key=lambda s: (not s['same_name'], not s['same_relation'], -s['credit']))[:5]
    return result


def default_out_dir(source_path, run):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return (source_path.parent / 'extract-products-scores' / run['skill_version'] / run['model_name']
            / run['benchmark_run_id'] / stamp)


def extraction_info(preds):
    stamps = sorted(str(p.get('create_time') or '') for p in preds)
    return {'model_names': sorted({p.get('model_name') or '' for p in preds}),
            'prompt_names': sorted({p.get('prompt_name') or '' for p in preds}),
            'created_at': [stamps[0], stamps[-1]]}


def export(record_id, version=None, model=None, run_id=None, out_dir=None):
    record = fetch_input(record_id)
    require(record, f'Unknown document: kb.inputs.id = {record_id} does not exist')
    runs = fetch_gold_runs(record_id)
    run = select_gold_run(runs, version, model, run_id)
    gold = fetch_gold(record_id, run)
    preds = fetch_predictions(record_id)
    if not preds:
        raise NoPredictions(f'NO_PREDICTIONS: kb.products has no active rows for document {record_id}; '
                            'run extract_products on it before scoring')
    warnings = []
    if not gold['rows']:
        warnings.append('The gold run has zero rows: every predicted row is a false positive')
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
    extraction = extraction_info(preds)
    if len(extraction['model_names']) > 1 or len(extraction['prompt_names']) > 1:
        warnings.append(f'kb.products rows come from several extractions (models {extraction["model_names"]}, '
                        f'prompts {extraction["prompt_names"]})')
    no_relation = sum(1 for p in preds if not (p.get('relation_type') or '').strip())
    if no_relation:
        warnings.append(f'{no_relation} kb.products rows have no relation_type (a Pass-1-only run); '
                        'they are graded like any other row')
    gold_rows = [compact_row(r, GOLD_FIELDS) for r in gold['rows']]
    pred_rows = [compact_row(r, PRED_FIELDS) for r in preds]
    payload = {
        'record_id': record_id, 'title': record.get('title'), 'doc_no': record.get('doc_no'),
        'gold_run': {**run, 'rows_scored': len(gold_rows),
                     'products': len({r['product_key'] for r in gold_rows})},
        'other_gold_runs': [r for r in runs if r is not run],
        'extraction': extraction,
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
    gold = {g['product_rel_id']: g for g in inp['gold']}
    pred = {p['product_rel_id']: p for p in inp['predictions']}
    ledger_ids = {c['candidate_id'] for c in inp['gold_ledger']}
    pairs, missed, fps = matches.get('pairs', []), matches.get('missed', []), matches.get('false_positives', [])
    seen_gold = [p['gold'] for p in pairs] + [m['gold'] for m in missed]
    seen_pred = [p['pred'] for p in pairs] + [f['pred'] for f in fps]
    for name, seen, expected in (('gold', seen_gold, set(gold)), ('predicted', seen_pred, set(pred))):
        dupes = sorted({x for x in seen if seen.count(x) > 1})
        require(not dupes, f'{name} rows accounted for more than once: {dupes}')
        unknown = sorted(set(seen) - expected)
        require(not unknown, f'unknown {name} product IDs: {unknown}')
        absent = sorted(expected - set(seen))
        require(not absent, f'{name} rows not accounted for: {absent}')
    if inp['source']['lines_comparable']:
        for p in pairs:
            require(line_set(gold[p['gold']]['evidence_lines']) & line_set(pred[p['pred']]['evidence_lines']),
                    f'pair {p["gold"]}/{p["pred"]}: the rows share no source line, so they are different relations')
    paired_gold = {p['gold'] for p in pairs}
    for f in fps:
        require(f.get('cause') in FP_CAUSES, f'false positive {f["pred"]}: cause must be one of {sorted(FP_CAUSES)}')
        if f['cause'] == 'gold_excluded':
            require(f.get('gold_candidate_id') in ledger_ids,
                    f'false positive {f["pred"]}: gold_candidate_id must name an excluded/duplicate ledger candidate')
        if f['cause'] == 'duplicate':
            require(f.get('of') in pred and f.get('of') != f['pred'],
                    f'false positive {f["pred"]}: "of" must name the other predicted row')
        if f['cause'] == 'extra_relation':
            require(f.get('gold') in gold,
                    f'false positive {f["pred"]}: an extra relation names a gold row of the same product ("gold")')
            f.setdefault('product_key', gold[f['gold']]['product_key'])
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


def group_key(row):
    return name_key(row.get('canonical_name') or row.get('product_name'))


def product_detection(inp, matches):
    """Unweighted product-level detection from the same matches: a gold product is detected when one
    of its rows is paired or named by an extra-relation false positive; a prediction group (rows with
    the same normalized canonical name) is correct when one of its rows is paired or an extra relation."""
    gold = {g['product_rel_id']: g for g in inp['gold']}
    pred = {p['product_rel_id']: p for p in inp['predictions']}
    products = {}
    for row in inp['gold']:
        products.setdefault(row['product_key'], row['product_name'])
    detected, good_preds = set(), set()
    for p in matches.get('pairs', []):
        detected.add(gold[p['gold']]['product_key'])
        good_preds.add(p['pred'])
    for f in matches.get('false_positives', []):
        if f['cause'] == 'extra_relation':
            detected.add(gold[f['gold']]['product_key'])
            good_preds.add(f['pred'])
    groups = {}
    for pid, row in pred.items():
        groups.setdefault(group_key(row), set()).add(pid)
    correct = {k for k, ids in groups.items() if ids & good_preds}
    precision = len(correct) / len(groups) if groups else 0.0
    recall = len(detected) / len(products) if products else 0.0
    return {'gold_products': len(products), 'predicted_products': len(groups),
            'detected': len(detected), 'correct_predicted': len(correct),
            'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            'missed_products': [{'product_key': k, 'product_name': n} for k, n in products.items() if k not in detected]}


def score(inp, matches, weights=None):
    weights = weights or load_weights()
    check_matches(inp, matches)
    gold = {g['product_rel_id']: g for g in inp['gold']}
    pred = {p['product_rel_id']: p for p in inp['predictions']}
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

    def grouped(field):
        values = sorted({norm(r.get(field)) for r in list(gold.values()) + list(pred.values())} - {''})
        return {v: metrics_for({g for g, row in gold.items() if norm(row.get(field)) == v},
                               {p for p, row in pred.items() if norm(row.get(field)) == v}, pairs)
                for v in values}
    detection = product_detection(inp, matches)
    missed_products = {m['product_key'] for m in detection['missed_products']}
    missed = [{**m, 'product_missed': gold[m['gold']]['product_key'] in missed_products}
              for m in matches.get('missed', [])]
    field_acc = {}
    for f in weights:
        vals = [float(p['checks'][f]) for p in pairs if p['checks'][f] is not None]
        field_acc[f] = (sum(vals) / len(vals)) if vals else None
    return {'score': main['score'], 'main': main, 'groups': grouped('relation_type'),
            'groups_by_product_type': grouped('product_type'), 'product_detection': detection,
            'field_accuracy': field_acc, 'weights': weights, 'pairs': pairs, 'missed': missed,
            'false_positives': matches.get('false_positives', []), 'overrides': matches.get('overrides', [])}


def pct(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def short(text, n=60):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text if len(text) <= n else text[:n - 1] + '…'


def spans(row):
    return ','.join(str(x) for x in as_list(row.get('evidence_lines')))


def report(inp, result, scorer_model):
    run, ext, src = inp['gold_run'], inp['extraction'], inp['source']
    gold = {g['product_rel_id']: g for g in inp['gold']}
    pred = {p['product_rel_id']: p for p in inp['predictions']}
    weights, det = result['weights'], result['product_detection']
    lines = [f'# extract_products score — record {inp["record_id"]}', '',
             f'**Score: {result["score"]} / 100** · product detection F1 {pct(det["f1"])}', '',
             '| Item | Value |', '|---|---|',
             f'| Document | {inp["record_id"]} · {inp.get("doc_no") or ""} {inp.get("title") or ""} |',
             f'| Gold run | {run["skill_version"]} / {run["model_name"]} / `{run["benchmark_run_id"]}` |',
             f'| Extraction | {", ".join(ext["model_names"]) or "—"} · {", ".join(ext["prompt_names"]) or "—"} '
             f'(saved {ext["created_at"][1]}) |',
             f'| Source lines comparable | {"yes" if src["lines_comparable"] else "no"} |',
             f'| Scored by | {scorer_model} |', '',
             '## Product detection', '',
             '| Gold products | Predicted products | Detected | Correct predicted | Precision | Recall | F1 |',
             '|---:|---:|---:|---:|---:|---:|---:|',
             f'| {det["gold_products"]} | {det["predicted_products"]} | {det["detected"]} | {det["correct_predicted"]} '
             f'| {pct(det["precision"])} | {pct(det["recall"])} | {pct(det["f1"])} |', '',
             'A gold product is detected when one of its rows is paired or named by an extra-relation false '
             'positive. Predicted products are rows grouped by normalized canonical name.', '',
             '## Relation rows', '',
             '| | Gold | Predicted | Matched | Soft precision | Soft recall | Soft F1 | Matched-row precision | Matched-row recall | Score |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    rows = [('All rows', result['main'])] + list(result['groups'].items())
    for label, v in rows:
        lines.append(f'| {label} | {v["gold_rows"]} | {v["predicted_rows"]} | {v["matched"]} '
                     f'| {pct(v["soft_precision"])} | {pct(v["soft_recall"])} | {pct(v["soft_f1"])} '
                     f'| {pct(v["precision"])} | {pct(v["recall"])} | {v["score"]} |')
    lines += ['', 'Relation-type rows count a pair under its gold row for recall and its predicted row for precision.',
              '', '## By product type', '', '| Product type | Gold | Predicted | Matched | Soft F1 |', '|---|---:|---:|---:|---:|']
    lines += [f'| {k} | {v["gold_rows"]} | {v["predicted_rows"]} | {v["matched"]} | {pct(v["soft_f1"])} |'
              for k, v in result['groups_by_product_type'].items()]
    lines += ['', '## Field accuracy on matched pairs', '', '| Field | Weight | Accuracy |', '|---|---:|---:|']
    lines += [f'| {f} | {w:.2f} | {pct(result["field_accuracy"][f])} |' for f, w in weights.items()]
    weak = [p for p in result['pairs'] if p['credit'] < 1]
    lines += ['', f'## Matched pairs with field errors ({len(weak)} of {len(result["pairs"])})', '']
    if weak:
        lines += ['| Gold | Predicted | Product | Failed checks (gold → predicted) | Credit | Note |',
                  '|---|---|---|---|---:|---|']
        for p in weak:
            g, pr = gold[p['gold']], pred[p['pred']]
            failed = []
            for f, ok in p['checks'].items():
                if ok is None or ok == 1:
                    continue
                if f in ('requirement_text', 'parameters', 'conditions', 'related_products'):
                    failed.append(f'{f} {pct(ok)}')
                elif f == 'lines':
                    failed.append(f'lines {spans(g)} → {spans(pr)}')
                elif f == 'name':
                    failed.append(f'name {g.get("product_name")} → {pr.get("product_name")}')
                else:
                    failed.append(f'{f} {g.get(f)} → {pr.get(f)}')
            lines.append(f'| {p["gold"]} | {p["pred"]} | {short(g["product_name"], 30)} | {"; ".join(failed)} | '
                         f'{p["credit"]:.2f} | {p.get("note", "")} |')
    missed_products = [m for m in result['missed'] if m['product_missed']]
    missed_relations = [m for m in result['missed'] if not m['product_missed']]
    for title, items in ((f'## Missed products ({len(det["missed_products"])} products, {len(missed_products)} rows)',
                          missed_products),
                         (f'## Missed relations of detected products ({len(missed_relations)})', missed_relations)):
        lines += ['', title, '']
        lines += [f'- `{x["gold"]}` {gold[x["gold"]]["product_name"]} [{gold[x["gold"]]["relation_type"]}] '
                  f'line {spans(gold[x["gold"]])}: {x.get("note", "")}' for x in items] or ['None.']
    lines += ['', f'## False positives ({len(result["false_positives"])})', '']
    for f in result['false_positives']:
        ref = {'gold_excluded': f'gold {f.get("gold_candidate_id")} {f.get("rule_id", "")}',
               'duplicate': f'duplicate of {f.get("of")}',
               'extra_relation': f'extra relation of {f.get("product_key")}'}.get(f['cause'], f['cause'])
        row = pred[f['pred']]
        lines.append(f'- `{f["pred"]}` {row.get("product_name")} [{row.get("relation_type") or "—"}] — {ref}: '
                     f'{f.get("note", "")}')
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
              'Each matched pair earns credit = weighted share of the field checks that apply to it '
              f'({", ".join(f"{f} {w:.2f}" for f, w in weights.items())}, renormalized over the applicable '
              'checks). requirement_text earns its similarity, lines its line-set overlap, and parameters, '
              'conditions and related_products their item F1. Soft precision = credit / predicted rows, soft '
              'recall = credit / gold rows, score = round(100 × soft F1), clamped to 1–100.']
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
                          'gold_products': run['products'],
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
    m, det = result['main'], result['product_detection']
    print(json.dumps({'score': result['score'], 'soft_precision': round(m['soft_precision'], 3),
                      'soft_recall': round(m['soft_recall'], 3), 'soft_f1': round(m['soft_f1'], 3),
                      'matched_row_precision': round(m['precision'], 3), 'matched_row_recall': round(m['recall'], 3),
                      'product_detection': {k: round(det[k], 3) for k in ('precision', 'recall', 'f1')},
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
