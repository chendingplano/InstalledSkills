#!/usr/bin/env python3
"""Score extract_metrics output (kb.metrics) for one document against its gold metrics (testbed.metrics).

export: pick the gold run, fetch gold and predicted rows, write input.json for the matching step.
score:  check the reviewed matches.json, compute the 1-100 score, write score.json and report.md.
"""
import argparse
from datetime import datetime
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
BENCHMARK_DIR = SKILL_DIR.parent / 'extract-metrics-benchmark'
WORKSPACE = SKILL_DIR.parents[2]
GOLD_SKILL = 'extract-metrics-benchmark'
# Gold rules 3.0.0+ exclude pure requirements, as extract_metrics does since candidates v11 /
# enrich v8. A 2.1.0 run stands in only after its pure-requirement rows are dropped.
MIN_GOLD_VERSION = '3.0.0'
STAND_IN_VERSION = '2.1.0'
STAND_IN_DROPPED_KINDS = {'inspection_requirement', 'delegated_requirement'}
# Field checks on a matched pair and their weights (sum 1.0). A check that cannot be made
# (lines, when the source changed since the gold run) is left out and the rest renormalized.
# Scoring version 2 (2026-10-16) adds the condition check; scores of version 1 (no condition:
# value .30, range_type .20, kind .20, unit .15, lines .15) are not comparable with version 2.
SCORING_VERSION = 2
WEIGHTS = {'value': 0.25, 'range_type': 0.15, 'kind': 0.15, 'unit': 0.15, 'lines': 0.10, 'condition': 0.20}
# Only notation or wording can differ for these; range_type and kind are enums, a mismatch is
# always real.
OVERRIDABLE = {'value', 'unit', 'lines', 'condition'}
FP_CAUSES = {'gold_excluded', 'duplicate', 'not_in_gold', 'invalid'}
COMPARATORS = re.compile(r'[<>≤≥＜＞≦≧=]')
METRIC_FIELDS = '''metric_id metric_name metric_subject metric_desc metric_unit metric_value
value_range_type value_class value_min value_max condition formula_or_definition
threshold_or_target source_line_spans reasoning_tags'''.split()
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
    """The gold skill's helper: statement_kind, version_key and resolve_source stay defined once."""
    spec = importlib.util.spec_from_file_location('benchmark_io', BENCHMARK_DIR / 'scripts' / 'benchmark_io.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bio = load_benchmark_io()


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
    return query_json(f'''SELECT COALESCE(json_agg(r ORDER BY r.benchmark_run_id), '[]') FROM (
 SELECT skill_version, model_name, run_id AS benchmark_run_id, count(*) AS rows,
        min(source_sha256) AS source_sha256
 FROM testbed.metrics WHERE input_record_id = {record_id} AND skill_name = '{GOLD_SKILL}'
 GROUP BY 1, 2, 3) r;''')


def fetch_gold_rows(record_id, run):
    """Gold rows of one run; each carries the run's candidate ledger from testbed.metric_benchmark_runs."""
    key = ' AND '.join(f"m.{column} = {bio.sql_text(run[key])}" for column, key in
                       (('skill_version', 'skill_version'), ('model_name', 'model_name'),
                        ('run_id', 'benchmark_run_id')))
    cols = ', '.join(f'm.{c}' for c in METRIC_FIELDS)
    return query_json(f'''SELECT COALESCE(json_agg(row_to_json(g) ORDER BY g.id), '[]') FROM (
 SELECT m.id, {cols}, r.candidates FROM testbed.metrics m
 JOIN testbed.metric_benchmark_runs r
   ON (m.skill_name, m.skill_version, m.model_name, m.run_id)
    = (r.skill_name, r.skill_version, r.model_name, r.benchmark_run_id)
 WHERE m.input_record_id = {record_id} AND m.skill_name = '{GOLD_SKILL}' AND {key}) g;''')


def fetch_predictions(record_id):
    # Resolved reference rows (ref_mention_id set) carry another document's value and are never
    # scored (ChenWeb openspec change extract-references-processor).
    cols = ', '.join(METRIC_FIELDS)
    return query_json(f'''SELECT COALESCE(json_agg(row_to_json(m) ORDER BY m.id), '[]') FROM (
 SELECT id, {cols}, model_name, prompt_name, event_id, created_at FROM kb.metrics
 WHERE input_record_id = {record_id} AND ref_mention_id IS NULL) m;''')


def fetch_dropped_rows(record_id):
    """Rows extract_metrics set aside for the record (kb.metrics_dropped, ChenWeb openspec change
    metric-row-soft-drop-decision-model). Empty when the table does not exist yet."""
    return query_json(f'''SELECT CASE WHEN to_regclass('kb.metrics_dropped') IS NULL THEN '[]'::json ELSE (
 SELECT COALESCE(json_agg(json_build_object('drop_id', drop_id, 'drop_stage', drop_stage,
   'drop_reason', drop_reason, 'event_id', event_id, 'decision', decision,
   'metric_name', row_data->>'metric_name', 'subject', row_data->>'subject',
   'threshold_or_target', row_data->>'threshold_or_target', 'context', row_data->>'context',
   'source_line_spans', row_data->'source_line_spans') ORDER BY id), '[]'::json)
 FROM kb.metrics_dropped WHERE input_record_id = {record_id}) END;''')


def exclusion_from_dropped(dropped):
    """Pure requirements the extractor dropped, in the shape of the old exclude_pure_requirements log."""
    return [{'kind': d['drop_reason'], 'metric_name': d.get('metric_name'), 'subject': d.get('subject'),
             'threshold_or_target': d.get('threshold_or_target'), 'context': d.get('context'),
             'source_line_spans': d.get('source_line_spans')}
            for d in dropped if d.get('drop_stage') == 'statement_kind']


def fetch_extraction_logs(record_id):
    """The latest extract_metrics run that saved rows, and its exclude_pure_requirements entries
    (written by runs before kb.metrics_dropped existed)."""
    return query_json(f'''WITH last AS (
 SELECT run_id, max(create_time) AS saved_at FROM kb.doc_proc_logs
 WHERE record_id = {record_id} AND doc_proc_name = 'extract_metrics'
   AND activity_name = 'extract_metrics_final' AND run_id IS NOT NULL
 GROUP BY run_id ORDER BY saved_at DESC LIMIT 1)
SELECT json_build_object('run_id', (SELECT run_id FROM last), 'saved_at', (SELECT saved_at FROM last),
 'excluded', COALESCE((SELECT json_agg(e) FROM kb.doc_proc_logs l,
   jsonb_array_elements(l.artifact->'excluded') e
   WHERE l.record_id = {record_id} AND l.activity_name = 'exclude_pure_requirements'
     AND l.run_id = (SELECT run_id FROM last)), '[]'));''')


# ---------- gold run selection ----------

def select_gold_run(runs, version=None, model=None, run_id=None):
    """Return (run, stand_in). Raise NoGold when nothing usable exists."""
    if not runs:
        raise NoGold('NO_GOLD: no gold metrics in testbed.metrics for this document; '
                     'build them first with the extract-metrics-benchmark skill')
    chosen = [r for r in runs if (not version or r['skill_version'] == version)
              and (not model or r['model_name'] == model) and (not run_id or r['benchmark_run_id'] == run_id)]
    if version or model or run_id:
        if not chosen:
            raise NoGold(f'NO_GOLD: no gold run matches the requested filters; available: {describe_runs(runs)}')
        if len(chosen) > 1 and not run_id:
            chosen = sorted(chosen, key=lambda r: r['benchmark_run_id'])[-1:]
        run = chosen[0]
        floor = bio.version_key(STAND_IN_VERSION)
        if bio.version_key(run['skill_version']) < floor:
            raise NoGold(f'NO_GOLD: gold run {run["benchmark_run_id"]} uses rules {run["skill_version"]}, '
                         f'which cannot score current extract_metrics (needs >= {MIN_GOLD_VERSION}, '
                         f'or {STAND_IN_VERSION} as a stand-in)')
        return run, bio.version_key(run['skill_version']) < bio.version_key(MIN_GOLD_VERSION)
    current = [r for r in runs if bio.version_key(r['skill_version']) >= bio.version_key(MIN_GOLD_VERSION)
               and '-' not in r['skill_version']]
    if current:
        return max(current, key=lambda r: (bio.version_key(r['skill_version']), r['benchmark_run_id'])), False
    stand_in = [r for r in runs if r['skill_version'] == STAND_IN_VERSION]
    if stand_in:
        return max(stand_in, key=lambda r: r['benchmark_run_id']), True
    raise NoGold(f'NO_GOLD: no compatible gold metrics for this document. Scoring needs a run under rules '
                 f'>= {MIN_GOLD_VERSION} (or {STAND_IN_VERSION} as a stand-in); available: {describe_runs(runs)}. '
                 'Re-run extract-metrics-benchmark under the current rules')


def describe_runs(runs):
    return ', '.join(f'{r["skill_version"]}/{r["model_name"]}/{r["benchmark_run_id"]} ({r["rows"]} rows)'
                     for r in runs) or 'none'


# ---------- normalization and field checks ----------

def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text or '')).strip().lower())


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
    lines = set()
    for span in as_list(spans):
        if isinstance(span, dict):
            span = span.get('line_number') or span.get('line')
        if isinstance(span, (int, float)) and span > 0:
            lines.add(int(span))
        elif isinstance(span, str) and re.fullmatch(r'\s*[0-9]+\s*(?::\s*[0-9]+\s*)?', span):
            bounds = [int(x) for x in span.split(':')]
            lines.update(range(bounds[0], bounds[-1] + 1))
    lines.discard(0)
    return lines


def number(text):
    text = COMPARATORS.sub('', norm(text)).replace(' ', '')
    try:
        return float(text)
    except ValueError:
        return None


def same_number(a, b):
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def value_ok(gold, pred):
    """The stated value: endpoints for a range, the bare number otherwise, empty for non-numeric gold."""
    range_type = norm(gold.get('value_range_type'))
    if range_type not in bio.NUMERIC_RANGE_TYPES:
        return norm(pred.get('metric_value')) == ''
    if range_type == 'range':
        endpoints = [(gold.get(k), pred.get(k)) for k in ('value_min', 'value_max')]
        if all(g is not None and p is not None for g, p in endpoints):
            return all(same_number(float(g), float(p)) for g, p in endpoints)
    g, p = number(gold.get('metric_value')), number(pred.get('metric_value'))
    if g is not None and p is not None:
        return same_number(g, p)
    strip = lambda v: COMPARATORS.sub('', norm(v)).replace(' ', '')
    return strip(gold.get('metric_value')) == strip(pred.get('metric_value'))


def unit_ok(gold, pred):
    return norm(gold.get('metric_unit')).replace(' ', '') == norm(pred.get('metric_unit')).replace(' ', '')


def condition_parts(text):
    """A condition as a set of qualifier values: labels (`适用人群：`) and whitespace ignored."""
    parts = set()
    for part in re.split(r'[;；]', norm(text).replace(' ', '')):
        if not part:
            continue
        label, sep, value = part.partition(':')  # NFKC folds the full-width colon
        parts.add(value if sep and value else part)
    return parts


def condition_ok(gold, pred):
    return condition_parts(gold.get('condition')) == condition_parts(pred.get('condition'))


def kind_of(row):
    return bio.statement_kind({'value_class': row.get('value_class') or '',
                               'value_range_type': row.get('value_range_type') or '',
                               'formula_or_definition': row.get('formula_or_definition') or '',
                               'reasoning_tags': [str(t) for t in as_list(row.get('reasoning_tags'))]})


def field_checks(gold, pred, lines_comparable=True):
    return {'value': value_ok(gold, pred),
            'range_type': norm(gold.get('value_range_type')) == norm(pred.get('value_range_type')),
            'kind': gold['kind'] == pred['kind'],
            'unit': unit_ok(gold, pred),
            'condition': condition_ok(gold, pred),
            'lines': bool(line_set(gold.get('source_line_spans')) & line_set(pred.get('source_line_spans')))
                     if lines_comparable else None}


def pair_credit(checks):
    used = {f: ok for f, ok in checks.items() if ok is not None}
    total = sum(WEIGHTS[f] for f in used)
    return sum(WEIGHTS[f] for f, ok in used.items() if ok) / total if total else 0.0


# ---------- export ----------

def compact(row):
    out = {k: row.get(k) for k in METRIC_FIELDS}
    out['kind'] = kind_of(row)
    return out


def suggestions(gold_rows, pred_rows, lines_comparable):
    """For each gold row, predicted rows sharing a source line, best field agreement first."""
    result = {}
    for g in gold_rows:
        gl = line_set(g['source_line_spans'])
        near = []
        for p in pred_rows:
            if gl & line_set(p['source_line_spans']):
                near.append({'pred': p['metric_id'],
                             'credit': round(pair_credit(field_checks(g, p, lines_comparable)), 2)})
        result[g['metric_id']] = sorted(near, key=lambda s: -s['credit'])[:5]
    return result


def default_out_dir(source_path, run):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return (source_path.parent / 'extract-metrics-scores' / run['skill_version'] / run['model_name']
            / run['benchmark_run_id'] / stamp)


def export(record_id, version=None, model=None, run_id=None, out_dir=None):
    record = fetch_input(record_id)
    require(record, f'Unknown document: kb.inputs.id = {record_id} does not exist')
    runs = fetch_gold_runs(record_id)
    run, stand_in = select_gold_run(runs, version, model, run_id)
    gold = fetch_gold_rows(record_id, run)
    require(gold, f'Gold run {run["benchmark_run_id"]} returned no rows')
    candidates = gold[0].get('candidates') or []
    preds = fetch_predictions(record_id)
    if not preds:
        raise NoPredictions(f'NO_PREDICTIONS: kb.metrics has no rows for document {record_id}; '
                            'run extract_metrics on it before scoring')
    warnings = []
    ensure_data_home()
    try:
        source_path = bio.resolve_source(record)
        current_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        source_path, current_sha = None, None
        warnings.append(f'Source line file not readable ({exc}); line checks disabled')
    lines_comparable = current_sha is not None and current_sha == run['source_sha256']
    if current_sha and not lines_comparable:
        warnings.append('The line file changed since the gold run (SHA-256 differs); line numbers are '
                        'not comparable, so the lines check is disabled and matching relies on content')
    gold_rows = [compact(r) for r in gold]
    dropped = []
    if stand_in:
        dropped = [r['metric_id'] for r in gold_rows if r['kind'] in STAND_IN_DROPPED_KINDS]
        gold_rows = [r for r in gold_rows if r['kind'] not in STAND_IN_DROPPED_KINDS]
        warnings.append(f'Gold run uses rules {STAND_IN_VERSION} as a stand-in: dropped {len(dropped)} '
                        'inspection/delegated rows')
    pred_rows = [compact(r) for r in preds]
    meta = sorted({(r.get('prompt_name') or '', r.get('model_name') or '', r.get('event_id') or '') for r in preds})
    if len(meta) > 1:
        warnings.append(f'kb.metrics rows come from {len(meta)} different extraction runs/prompts')
    logs = fetch_extraction_logs(record_id) or {}
    events = {r.get('event_id') for r in preds if r.get('event_id')}
    dropped_rows = [d for d in (fetch_dropped_rows(record_id) or []) if not events or d.get('event_id') in events]
    exclusion_log = exclusion_from_dropped(dropped_rows) if dropped_rows else (logs.get('excluded') or [])
    payload = {
        'record_id': record_id, 'title': record.get('title'), 'doc_no': record.get('doc_no'),
        'gold_run': {**run, 'stand_in': stand_in, 'dropped_metric_ids': dropped,
                     'rows_scored': len(gold_rows)},
        'other_gold_runs': [r for r in runs if r['benchmark_run_id'] != run['benchmark_run_id']],
        'extraction': {'prompts_models_events': [list(m) for m in meta],
                       'created_at': [min(r['created_at'] for r in preds), max(r['created_at'] for r in preds)],
                       'log_run_id': logs.get('run_id'), 'exclusion_log': exclusion_log,
                       'dropped_rows': dropped_rows},
        'source': {'path': str(source_path) if source_path else None, 'current_sha256': current_sha,
                   'gold_sha256': run['source_sha256'], 'lines_comparable': lines_comparable},
        'warnings': warnings,
        'gold': gold_rows,
        'gold_ledger': [c for c in candidates if c.get('decision') in ('excluded', 'duplicate')],
        'predictions': pred_rows,
        'suggestions': suggestions(gold_rows, pred_rows, lines_comparable),
    }
    out_dir = Path(out_dir) if out_dir else default_out_dir(source_path or Path.cwd() / 'x', run)
    out_dir.mkdir(parents=True, exist_ok=False)
    path = out_dir / 'input.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return path, payload


# ---------- score ----------

def check_matches(inp, matches):
    """Every gold row is paired or missed once; every predicted row is paired or a false positive once."""
    gold_ids = {g['metric_id'] for g in inp['gold']}
    pred_ids = {p['metric_id'] for p in inp['predictions']}
    ledger_ids = {c['candidate_id'] for c in inp['gold_ledger']}
    pairs, missed, fps = matches.get('pairs', []), matches.get('missed', []), matches.get('false_positives', [])
    seen_gold = [p['gold'] for p in pairs] + [m['gold'] for m in missed]
    seen_pred = [p['pred'] for p in pairs] + [f['pred'] for f in fps]
    for name, seen, expected in (('gold', seen_gold, gold_ids), ('predicted', seen_pred, pred_ids)):
        dupes = sorted({x for x in seen if seen.count(x) > 1})
        require(not dupes, f'{name} rows accounted for more than once: {dupes}')
        unknown = sorted(set(seen) - expected)
        require(not unknown, f'unknown {name} metric IDs: {unknown}')
        absent = sorted(expected - set(seen))
        require(not absent, f'{name} rows not accounted for: {absent}')
    for f in fps:
        require(f.get('cause') in FP_CAUSES, f'false positive {f["pred"]}: cause must be one of {sorted(FP_CAUSES)}')
        if f['cause'] == 'gold_excluded':
            require(f.get('gold_candidate_id') in ledger_ids,
                    f'false positive {f["pred"]}: gold_candidate_id must name an excluded/duplicate ledger candidate')
        if f['cause'] == 'duplicate':
            require(f.get('of') in pred_ids and f.get('of') != f['pred'],
                    f'false positive {f["pred"]}: "of" must name the other predicted row')
    paired_gold = {p['gold'] for p in pairs}
    for o in matches.get('overrides', []):
        require(o.get('gold') in paired_gold, f'override for unpaired gold row {o.get("gold")}')
        require(o.get('field') in OVERRIDABLE, f'override field must be one of {sorted(OVERRIDABLE)}')
        require(isinstance(o.get('correct'), bool), 'override "correct" must be true or false')
        require(str(o.get('reason') or '').strip(), f'override for {o["gold"]}/{o["field"]} needs a reason')


def metrics_for(gold_ids, pairs_credit, n_pred):
    n_gold = len(gold_ids)
    credit = sum(c for g, c in pairs_credit.items() if g in gold_ids)
    matched = sum(1 for g in pairs_credit if g in gold_ids)
    soft_r = credit / n_gold if n_gold else 0.0
    soft_p = credit / n_pred if n_pred else 0.0
    soft_f1 = 2 * soft_p * soft_r / (soft_p + soft_r) if soft_p + soft_r else 0.0
    hard_r = matched / n_gold if n_gold else 0.0
    hard_p = matched / n_pred if n_pred else 0.0
    hard_f1 = 2 * hard_p * hard_r / (hard_p + hard_r) if hard_p + hard_r else 0.0
    return {'score': max(1, min(100, round(100 * soft_f1))), 'soft_f1': soft_f1,
            'soft_precision': soft_p, 'soft_recall': soft_r, 'precision': hard_p, 'recall': hard_r,
            'f1': hard_f1, 'gold_rows': n_gold, 'predicted_rows': n_pred, 'matched': matched}


def score(inp, matches):
    check_matches(inp, matches)
    gold = {g['metric_id']: g for g in inp['gold']}
    pred = {p['metric_id']: p for p in inp['predictions']}
    comparable = inp['source']['lines_comparable']
    overrides = {(o['gold'], o['field']): o for o in matches.get('overrides', [])}
    pairs = []
    for p in matches.get('pairs', []):
        checks = field_checks(gold[p['gold']], pred[p['pred']], comparable)
        for field in checks:
            if (p['gold'], field) in overrides and checks[field] is not None:
                checks[field] = overrides[(p['gold'], field)]['correct']
        pairs.append({**p, 'checks': checks, 'credit': pair_credit(checks)})
    credit = {p['gold']: p['credit'] for p in pairs}
    main = metrics_for(set(gold), credit, len(pred))
    # Production extraction may not target test-method settings: also score without them.
    test_gold = {g for g, row in gold.items() if row['kind'] == 'test_parameter'}
    test_pred = {p['pred'] for p in pairs if p['gold'] in test_gold}
    without_tests = metrics_for(set(gold) - test_gold, credit, len(pred) - len(test_pred)) if test_gold else None
    field_acc = {}
    for f in WEIGHTS:
        vals = [p['checks'][f] for p in pairs if p['checks'][f] is not None]
        field_acc[f] = (sum(vals) / len(vals)) if vals else None
    return {'score': main['score'], 'main': main, 'without_test_parameters': without_tests,
            'field_accuracy': field_acc, 'weights': WEIGHTS, 'scoring_version': SCORING_VERSION,
            'pairs': pairs,
            'missed': matches.get('missed', []), 'false_positives': matches.get('false_positives', []),
            'overrides': matches.get('overrides', [])}


def pct(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def report(inp, result, scorer_model):
    run, ext, src, m = inp['gold_run'], inp['extraction'], inp['source'], result['main']
    gold = {g['metric_id']: g for g in inp['gold']}
    pred = {p['metric_id']: p for p in inp['predictions']}
    lines = [f'# extract_metrics score — record {inp["record_id"]}', '',
             f'**Score: {result["score"]} / 100**', '',
             '| Item | Value |', '|---|---|',
             f'| Document | {inp["record_id"]} · {inp.get("doc_no") or ""} {inp.get("title") or ""} |',
             f'| Gold run | {run["skill_version"]} / {run["model_name"]} / `{run["benchmark_run_id"]}`'
             f'{" (2.1.0 stand-in)" if run["stand_in"] else ""} |',
             f'| Extraction | {"; ".join(" / ".join(x for x in t if x) for t in ext["prompts_models_events"])} '
             f'(saved {ext["created_at"][1]}, log run {ext["log_run_id"]}) |',
             f'| Source lines comparable | {"yes" if src["lines_comparable"] else "no"} |',
             f'| Scored by | {scorer_model} |',
             f'| Scoring version | {result.get("scoring_version", 1)} (weights: '
             f'{", ".join(f"{f} {w}" for f, w in result["weights"].items())}) |', '',
             '## Components', '',
             '| | Gold | Predicted | Matched | Soft precision | Soft recall | Soft F1 | Matched-row precision | Matched-row recall | Score |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    variants = [('All rows', m)]
    if result['without_test_parameters']:
        variants.append(('Without test parameters', result['without_test_parameters']))
    for label, v in variants:
        lines.append(f'| {label} | {v["gold_rows"]} | {v["predicted_rows"]} | {v["matched"]} '
                     f'| {pct(v["soft_precision"])} | {pct(v["soft_recall"])} | {pct(v["soft_f1"])} '
                     f'| {pct(v["precision"])} | {pct(v["recall"])} | {v["score"]} |')
    lines += ['', '## Field accuracy on matched pairs', '', '| Field | Weight | Accuracy |', '|---|---:|---:|']
    lines += [f'| {f} | {w:.2f} | {pct(result["field_accuracy"][f])} |' for f, w in WEIGHTS.items()]
    weak = [p for p in result['pairs'] if p['credit'] < 1]
    lines += ['', f'## Matched pairs with field errors ({len(weak)} of {len(result["pairs"])})', '']
    if weak:
        lines += ['| Gold | Predicted | Metric | Failed checks | Credit | Note |', '|---|---|---|---|---:|---|']
        for p in weak:
            failed = ', '.join(f for f, ok in p['checks'].items() if ok is False)
            g, pr = gold[p['gold']], pred[p['pred']]
            detail = f'gold {g["value_range_type"]} {g["metric_value"]} {g["metric_unit"]} / ' \
                     f'pred {pr["value_range_type"]} {pr["metric_value"]} {pr["metric_unit"]}'
            if p['checks'].get('condition') is False:
                detail += f'; condition gold "{g.get("condition") or ""}" / pred "{pr.get("condition") or ""}"'
            lines.append(f'| {p["gold"]} | {p["pred"]} | {g["metric_name"]} ({detail}) | {failed} | '
                         f'{p["credit"]:.2f} | {p.get("note", "")} |')
    lines += ['', f'## Missed gold rows ({len(result["missed"])})', '']
    lines += [f'- `{x["gold"]}` {gold[x["gold"]]["metric_name"]} ({gold[x["gold"]]["kind"]}): {x.get("note", "")}'
              for x in result['missed']] or ['None.']
    lines += ['', f'## False positives ({len(result["false_positives"])})', '']
    for f in result['false_positives']:
        ref = {'gold_excluded': f'gold {f.get("gold_candidate_id")} {f.get("rule_id", "")}',
               'duplicate': f'duplicate of {f.get("of")}'}.get(f['cause'], f['cause'])
        lines.append(f'- `{f["pred"]}` {pred[f["pred"]]["metric_name"]} ({pred[f["pred"]]["kind"]}) — {ref}: {f.get("note", "")}')
    if not result['false_positives']:
        lines.append('None.')
    if result['overrides']:
        lines += ['', '## Field-check overrides', '']
        lines += [f'- `{o["gold"]}` {o["field"]} → {"correct" if o["correct"] else "wrong"}: {o["reason"]}'
                  for o in result['overrides']]
    lines += ['', f'## Exclusion log (run {ext["log_run_id"]})', '',
              f'{len(ext["exclusion_log"])} pure requirement(s) dropped by the extractor; '
              f'gold ledger lists {sum(1 for c in inp["gold_ledger"] if c.get("rule_id") in ("X15", "X16"))} '
              'X15/X16 candidates. Diagnostic only; not part of the score.']
    lines += dropped_rows_section(inp, result)
    warnings = list(inp['warnings'])
    if run['model_name'] == scorer_model:
        warnings.append(f'The gold run and the matching were made by the same model ({scorer_model}); '
                        'a different scorer model would be an independent check')
    if warnings:
        lines += ['', '## Warnings', ''] + [f'- {w}' for w in warnings]
    lines += ['', '## Method', '',
              'Each matched pair earns credit = weighted share of passed field checks '
              f'({", ".join(f"{f} {w}" for f, w in WEIGHTS.items())}). Soft precision = credit / predicted rows, '
              'soft recall = credit / gold rows, score = round(100 × soft F1), clamped to 1–100.']
    return '\n'.join(lines) + '\n'


def dropped_rows_section(inp, result):
    """Report lines for the rows the extractor set aside (not scored). A dropped row on the same
    lines as a missed gold row is flagged: it may be a wrong drop."""
    dropped = inp['extraction'].get('dropped_rows') or []
    lines = ['', f'## Dropped rows ({len(dropped)})', '']
    if not dropped:
        return lines + ['None.']
    gold = {g['metric_id']: g for g in inp['gold']}
    missed = [gold[x['gold']] for x in result['missed'] if x['gold'] in gold]
    lines += ['Set aside by extract_metrics (kb.metrics_dropped); not counted in the score.', '',
              '| Drop id | Stage | Reason | Metric | P | Same lines as missed gold |', '|---|---|---|---|---:|---|']
    for d in dropped:
        probs = (d.get('decision') or {}).get('probabilities') or {}
        p = probs.get(d['drop_reason'])
        overlap = ', '.join(g['metric_id'] for g in missed if line_set(g.get('source_line_spans')) & line_set(d.get('source_line_spans')))
        lines.append(f'| {d["drop_id"]} | {d["drop_stage"]} | {d["drop_reason"]} | {d.get("metric_name") or ""} | '
                     f'{"" if p is None else f"{p:.2f}"} | {overlap} |')
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='action', required=True)
    ex = sub.add_parser('export', help='select the gold run and write input.json')
    ex.add_argument('--record-id', required=True, type=int, help='kb.inputs.id')
    ex.add_argument('--gold-version', help='gold rules version (default: newest >= 3.0.0)')
    ex.add_argument('--gold-model', help='gold run model_name')
    ex.add_argument('--gold-run-id', help='gold benchmark_run_id (yyyymmdd_hhmmss)')
    ex.add_argument('--out-dir', help='new directory for the score artifacts')
    sc = sub.add_parser('score', help='check matches.json and write score.json and report.md')
    sc.add_argument('--dir', required=True, type=Path, help='directory holding input.json and matches.json')
    sc.add_argument('--scorer-model', required=True, help='exact ID of the model that made the matches')
    args = parser.parse_args()
    if args.action == 'export':
        require(args.record_id > 0, 'record ID must be a positive integer')
        path, payload = export(args.record_id, args.gold_version, args.gold_model, args.gold_run_id, args.out_dir)
        run = payload['gold_run']
        print(json.dumps({'input': str(path), 'gold_run': f'{run["skill_version"]}/{run["model_name"]}/'
                          f'{run["benchmark_run_id"]}', 'stand_in': run['stand_in'],
                          'gold_rows': len(payload['gold']), 'predicted_rows': len(payload['predictions']),
                          'warnings': payload['warnings']}, ensure_ascii=False))
        return
    inp = json.loads((args.dir / 'input.json').read_text(encoding='utf-8'))
    matches = json.loads((args.dir / 'matches.json').read_text(encoding='utf-8'))
    result = score(inp, matches)
    result.update(record_id=inp['record_id'], gold_run=inp['gold_run'], scorer_model=args.scorer_model,
                  scored_at=datetime.now().isoformat(timespec='seconds'))
    (args.dir / 'score.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    (args.dir / 'report.md').write_text(report(inp, result, args.scorer_model), encoding='utf-8')
    m = result['main']
    print(json.dumps({'score': result['score'], 'soft_precision': round(m['soft_precision'], 3),
                      'soft_recall': round(m['soft_recall'], 3), 'soft_f1': round(m['soft_f1'], 3),
                      'matched_row_precision': round(m['precision'], 3), 'matched_row_recall': round(m['recall'], 3),
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
