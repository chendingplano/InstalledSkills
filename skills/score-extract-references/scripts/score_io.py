#!/usr/bin/env python3
"""Score extract_references output (kb.ref_mentions) for one document against its gold references
(testbed.ref_mentions).

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
BENCHMARK_DIR = SKILL_DIR.parent / 'extract-references-benchmark'
WORKSPACE = SKILL_DIR.parents[2]
GOLD_SKILL = 'extract-references-benchmark'
MIN_GOLD_VERSION = '1.0.0'
# Field checks on a matched pair and their weights (sum 1.0). A check that does not apply
# (quantity, unless both rows are criterion rows) is left out and the rest renormalized.
# relationships earns partial credit (set overlap); every other check is pass/fail.
WEIGHTS = {'target_content': 0.25, 'in_requirement': 0.10, 'identifiers': 0.10, 'relationships': 0.10,
           'mechanism': 0.05, 'target_type': 0.05, 'target_subtype': 0.05, 'target_scope': 0.05,
           'ref_form': 0.05, 'normativity': 0.05, 'list_link': 0.05, 'list_mismatch': 0.05,
           'quantity': 0.05}
# Only wording can differ for these; every other field is an enum, a mismatch is always real.
OVERRIDABLE = {'identifiers', 'quantity'}
FP_CAUSES = {'gold_excluded', 'duplicate', 'not_in_gold', 'invalid'}
# Detection groups, reported separately (extract-references-benchmark SKILL.md, "Scoring").
GROUPS = ('listed', 'external_in_text', 'internal')
REF_FIELDS = '''ref_id section source_line_spans source_table_rows evidence ref_form list_kind
normativity in_requirement list_mismatch mechanism cited_raw identifiers target_type target_subtype
target_subtype_label target_title target_version relationships target_scope target_locator
target_content metric_name metric_name_en metric_subject metric_subject_en condition internal
confidence'''.split()
DASHES = re.compile(r'[‐-―−－﹘﹣]')
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
    """Runs from the audit table, so a run with zero gold references is still found."""
    return query_json(f'''SELECT COALESCE(json_agg(x ORDER BY x.benchmark_run_id), '[]') FROM (
 SELECT r.skill_version, r.model_name, r.run_id AS benchmark_run_id, r.source_sha256,
        r.document_identifier, r.language,
        (SELECT count(*) FROM testbed.ref_mentions m
          WHERE (m.skill_name, m.skill_version, m.model_name, m.run_id)
              = (r.skill_name, r.skill_version, r.model_name, r.run_id)) AS rows
 FROM testbed.reference_benchmark_runs r
 WHERE r.input_record_id = {record_id} AND r.skill_name = '{GOLD_SKILL}') x;''')


def run_key_sql(run, alias):
    return ' AND '.join(f"{alias}.{column} = {bio.sql_text(run[key])}" for column, key in
                        (('skill_name', 'skill_name'), ('skill_version', 'skill_version'),
                         ('model_name', 'model_name'), ('run_id', 'benchmark_run_id')))


def fetch_gold(record_id, run):
    """Gold references of one run and the run's candidate ledger."""
    run = {**run, 'skill_name': GOLD_SKILL}
    cols = ', '.join(f'm.{c}' for c in REF_FIELDS)
    return query_json(f'''SELECT json_build_object(
 'rows', (SELECT COALESCE(json_agg(row_to_json(g) ORDER BY g.id), '[]') FROM (
   SELECT m.id, {cols}, m.list_entry_ref_id, m.list_label FROM testbed.ref_mentions m
   WHERE m.input_record_id = {record_id} AND {run_key_sql(run, 'm')}) g),
 'candidates', (SELECT r.candidates FROM testbed.reference_benchmark_runs r
   WHERE {run_key_sql(run, 'r')}));''')


def fetch_predictions(record_id):
    # list_entry_id is a kb.ref_mentions.id; it is mapped to the entry's ref_id for comparison.
    cols = ', '.join(f'm.{c}' for c in REF_FIELDS)
    return query_json(f'''SELECT COALESCE(json_agg(row_to_json(p) ORDER BY p.id), '[]') FROM (
 SELECT m.id, {cols}, COALESCE(e.ref_id, '') AS list_entry_ref_id, m.event_id, m.created_at
 FROM kb.ref_mentions m LEFT JOIN kb.ref_mentions e ON e.id = m.list_entry_id
 WHERE m.input_record_id = {record_id}) p;''')


def fetch_own_identifier(record_id):
    """The identifier extract_references attached the document to (design D5): the identity key
    and edition of the resource holding its kb_input identifier."""
    return query_json(f'''SELECT COALESCE(json_agg(json_build_object('identity_key', r.identity_key,
   'edition', v.version_label)), '[]')
 FROM kb.ref_resource_identifiers ri JOIN kb.ref_resources r ON r.id = ri.resource_id
 LEFT JOIN kb.ref_resource_versions v ON v.id = ri.version_id
 WHERE ri.kind = 'kb_input' AND ri.value = '{record_id}';''')


# ---------- gold run selection ----------

def select_gold_run(runs, version=None, model=None, run_id=None):
    """Return the gold run to score against. Raise NoGold when nothing usable exists."""
    if not runs:
        raise NoGold('NO_GOLD: no gold references in testbed.reference_benchmark_runs for this document; '
                     'build them first with the extract-references-benchmark skill')
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
                     'extract-references-benchmark')
    return max(current, key=lambda r: (bio.version_key(r['skill_version']), r['benchmark_run_id']))


def describe_runs(runs):
    return ', '.join(f'{r["skill_version"]}/{r["model_name"]}/{r["benchmark_run_id"]} ({r["rows"]} rows)'
                     for r in runs) or 'none'


# ---------- normalization and field checks ----------

def norm(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text or '')).strip().lower())


def tight(text):
    """Notation-blind form of an identifier: NFKC, lower case, one dash, no spaces."""
    return DASHES.sub('-', norm(text)).replace(' ', '')


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
        if isinstance(span, (int, float)) and span > 0:
            lines.add(int(span))
        elif isinstance(span, str) and re.fullmatch(r'\s*[0-9]+\s*(?::\s*[0-9]+\s*)?', span):
            bounds = [int(x) for x in span.split(':')]
            lines.update(range(bounds[0], bounds[-1] + 1))
    lines.discard(0)
    return lines


def group_of(row):
    if row['ref_form'] == 'listed':
        return 'listed'
    return 'internal' if row['internal'] else 'external_in_text'


def identifier_set(row):
    return {(i.get('kind'), tight(i.get('value')), tight(i.get('edition')))
            for i in as_list(row.get('identifiers')) if isinstance(i, dict)}


def quantity_ok(gold, pred):
    if norm(gold.get('metric_name')) == norm(pred.get('metric_name')) and norm(gold.get('metric_name')):
        return True
    return bool(norm(gold.get('metric_name_en'))) and norm(gold.get('metric_name_en')) == norm(pred.get('metric_name_en'))


def jaccard(a, b):
    a, b = set(as_list(a)), set(as_list(b))
    return len(a & b) / len(a | b) if a | b else 1.0


def field_checks(gold, pred, linked=None):
    """linked: the gold ref_id the predicted row's list entry is paired with ('' for no link), or
    None to leave the list-link check out (suggestions, before pairs exist)."""
    same = lambda f: norm(gold.get(f)) == norm(pred.get(f))
    criterion = gold['target_content'] == 'criterion' and pred['target_content'] == 'criterion'
    return {'target_content': same('target_content'),
            'in_requirement': bool(gold['in_requirement']) == bool(pred['in_requirement']),
            'identifiers': identifier_set(gold) == identifier_set(pred),
            'relationships': jaccard(gold.get('relationships'), pred.get('relationships')),
            'mechanism': same('mechanism'), 'target_type': same('target_type'),
            'target_subtype': same('target_subtype'), 'target_scope': same('target_scope'),
            'ref_form': same('ref_form'), 'normativity': same('normativity'),
            'list_link': None if linked is None else (gold.get('list_entry_ref_id') or '') == linked,
            'list_mismatch': same('list_mismatch'),
            'quantity': quantity_ok(gold, pred) if criterion else None}


def pair_credit(checks):
    used = {f: ok for f, ok in checks.items() if ok is not None}
    total = sum(WEIGHTS[f] for f in used)
    return sum(WEIGHTS[f] * float(ok) for f, ok in used.items()) / total if total else 0.0


# ---------- export ----------

def compact(row):
    out = {k: row.get(k) for k in REF_FIELDS + ['list_entry_ref_id']}
    out['list_entry_ref_id'] = out['list_entry_ref_id'] or ''
    out['group'] = group_of(row)
    return out


def suggestions(gold_rows, pred_rows):
    """For each gold row, predicted rows sharing a source line, best agreement first: the same
    cited_raw ranks above field agreement."""
    result = {}
    for g in gold_rows:
        gl = line_set(g['source_line_spans'])
        near = []
        for p in pred_rows:
            if gl & line_set(p['source_line_spans']):
                near.append({'pred': p['ref_id'], 'same_cited_raw': tight(g['cited_raw']) == tight(p['cited_raw']),
                             'credit': round(pair_credit(field_checks(g, p)), 2)})
        result[g['ref_id']] = sorted(near, key=lambda s: (not s['same_cited_raw'], -s['credit']))[:5]
    return result


def own_identifier_check(gold_identifier, attached):
    """Compare the gold run's document_identifier with what the processor attached the record to."""
    gold = tight(gold_identifier)
    found = [f'{a["identity_key"]}' + (f' ({a["edition"]})' if a.get('edition') else '') for a in attached or []]
    if not gold:
        return {'gold': gold_identifier, 'attached': found,
                'result': 'gold_none' if not found else 'attached_but_gold_none'}
    if not found:
        return {'gold': gold_identifier, 'attached': found, 'result': 'missing'}
    result = 'mismatch'
    for a in attached:
        value = tight(a['identity_key'].split(':', 1)[-1])
        edition = tight(a.get('edition'))
        if gold == (f'{value}-{edition}' if edition else value):
            return {'gold': gold_identifier, 'attached': found, 'result': 'match'}
        if gold.startswith(value) and (gold == value or gold[len(value)] in '-:'):
            result = 'match_without_edition' if not edition else 'edition_differs'
    return {'gold': gold_identifier, 'attached': found, 'result': result}


def default_out_dir(source_path, run):
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return (source_path.parent / 'extract-references-scores' / run['skill_version'] / run['model_name']
            / run['benchmark_run_id'] / stamp)


def export(record_id, version=None, model=None, run_id=None, out_dir=None):
    record = fetch_input(record_id)
    require(record, f'Unknown document: kb.inputs.id = {record_id} does not exist')
    runs = fetch_gold_runs(record_id)
    run = select_gold_run(runs, version, model, run_id)
    gold = fetch_gold(record_id, run)
    preds = fetch_predictions(record_id)
    if not preds:
        raise NoPredictions(f'NO_PREDICTIONS: kb.ref_mentions has no rows for document {record_id}; '
                            'run extract_references on it before scoring')
    warnings = []
    if not gold['rows']:
        warnings.append('The gold run has zero references: every predicted row is a false positive')
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
                        'not comparable, so pairs are not required to share a line')
    events = sorted({p.get('event_id') or '' for p in preds})
    if len(events) > 1:
        warnings.append(f'kb.ref_mentions rows come from {len(events)} different extraction events')
    gold_rows = [compact(r) for r in gold['rows']]
    pred_rows = [compact(r) for r in preds]
    payload = {
        'record_id': record_id, 'title': record.get('title'), 'doc_no': record.get('doc_no'),
        'gold_run': {**run, 'rows_scored': len(gold_rows)},
        'other_gold_runs': [r for r in runs if r is not run],
        'extraction': {'event_ids': events,
                       'created_at': [min(p['created_at'] for p in preds), max(p['created_at'] for p in preds)]},
        'own_identifier': own_identifier_check(run.get('document_identifier'), fetch_own_identifier(record_id)),
        'source': {'path': str(source_path) if source_path else None, 'current_sha256': current_sha,
                   'gold_sha256': run['source_sha256'], 'lines_comparable': lines_comparable},
        'warnings': warnings,
        'gold': gold_rows,
        'gold_ledger': [c for c in (gold.get('candidates') or []) if c.get('decision') in ('excluded', 'duplicate')],
        'predictions': pred_rows,
        'suggestions': suggestions(gold_rows, pred_rows),
    }
    out_dir = Path(out_dir) if out_dir else default_out_dir(source_path or Path.cwd() / 'x', run)
    out_dir.mkdir(parents=True, exist_ok=False)
    path = out_dir / 'input.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return path, payload


# ---------- score ----------

def check_matches(inp, matches):
    """Every gold row is paired or missed once; every predicted row is paired or a false positive
    once; paired rows share a source line when line numbers are comparable."""
    gold = {g['ref_id']: g for g in inp['gold']}
    pred = {p['ref_id']: p for p in inp['predictions']}
    ledger_ids = {c['candidate_id'] for c in inp['gold_ledger']}
    pairs, missed, fps = matches.get('pairs', []), matches.get('missed', []), matches.get('false_positives', [])
    seen_gold = [p['gold'] for p in pairs] + [m['gold'] for m in missed]
    seen_pred = [p['pred'] for p in pairs] + [f['pred'] for f in fps]
    for name, seen, expected in (('gold', seen_gold, set(gold)), ('predicted', seen_pred, set(pred))):
        dupes = sorted({x for x in seen if seen.count(x) > 1})
        require(not dupes, f'{name} rows accounted for more than once: {dupes}')
        unknown = sorted(set(seen) - expected)
        require(not unknown, f'unknown {name} ref IDs: {unknown}')
        absent = sorted(expected - set(seen))
        require(not absent, f'{name} rows not accounted for: {absent}')
    if inp['source']['lines_comparable']:
        for p in pairs:
            require(line_set(gold[p['gold']]['source_line_spans']) & line_set(pred[p['pred']]['source_line_spans']),
                    f'pair {p["gold"]}/{p["pred"]}: the rows share no source line, so they are different occurrences')
    for f in fps:
        require(f.get('cause') in FP_CAUSES, f'false positive {f["pred"]}: cause must be one of {sorted(FP_CAUSES)}')
        if f['cause'] == 'gold_excluded':
            require(f.get('gold_candidate_id') in ledger_ids,
                    f'false positive {f["pred"]}: gold_candidate_id must name an excluded/duplicate ledger candidate')
        if f['cause'] == 'duplicate':
            require(f.get('of') in pred and f.get('of') != f['pred'],
                    f'false positive {f["pred"]}: "of" must name the other predicted row')
    paired_gold = {p['gold'] for p in pairs}
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


def score(inp, matches):
    check_matches(inp, matches)
    gold = {g['ref_id']: g for g in inp['gold']}
    pred = {p['ref_id']: p for p in inp['predictions']}
    pred_to_gold = {p['pred']: p['gold'] for p in matches.get('pairs', [])}
    overrides = {(o['gold'], o['field']): o for o in matches.get('overrides', [])}
    pairs = []
    for p in matches.get('pairs', []):
        link = pred[p['pred']].get('list_entry_ref_id') or ''
        # A link to an unpaired predicted entry can never equal the gold link: mark it with its own ID.
        linked = pred_to_gold.get(link, f'unpaired:{link}') if link else ''
        checks = field_checks(gold[p['gold']], pred[p['pred']], linked)
        for field in checks:
            if (p['gold'], field) in overrides and checks[field] is not None:
                checks[field] = overrides[(p['gold'], field)]['correct']
        pairs.append({**p, 'checks': checks, 'credit': pair_credit(checks)})
    main = metrics_for(set(gold), set(pred), pairs)
    groups = {name: metrics_for({g for g, row in gold.items() if row['group'] == name},
                                {p for p, row in pred.items() if row['group'] == name}, pairs)
              for name in GROUPS}
    # The rows the metric resolver takes.
    metric_contents = {'criterion', 'criteria_set'}
    groups['criterion_or_set'] = metrics_for({g for g, row in gold.items() if row['target_content'] in metric_contents},
                                             {p for p, row in pred.items() if row['target_content'] in metric_contents},
                                             pairs)
    field_acc = {}
    for f in WEIGHTS:
        vals = [float(p['checks'][f]) for p in pairs if p['checks'][f] is not None]
        field_acc[f] = (sum(vals) / len(vals)) if vals else None
    return {'score': main['score'], 'main': main, 'groups': groups,
            'field_accuracy': field_acc, 'weights': WEIGHTS, 'pairs': pairs,
            'missed': matches.get('missed', []), 'false_positives': matches.get('false_positives', []),
            'overrides': matches.get('overrides', [])}


def pct(x):
    return '—' if x is None else f'{100 * x:.1f}%'


def show(row):
    return f'{row["cited_raw"]} [{row["target_content"]}, {row["group"]}]'


def report(inp, result, scorer_model):
    run, ext, src, own = inp['gold_run'], inp['extraction'], inp['source'], inp['own_identifier']
    gold = {g['ref_id']: g for g in inp['gold']}
    pred = {p['ref_id']: p for p in inp['predictions']}
    lines = [f'# extract_references score — record {inp["record_id"]}', '',
             f'**Score: {result["score"]} / 100**', '',
             '| Item | Value |', '|---|---|',
             f'| Document | {inp["record_id"]} · {inp.get("doc_no") or ""} {inp.get("title") or ""} |',
             f'| Gold run | {run["skill_version"]} / {run["model_name"]} / `{run["benchmark_run_id"]}` |',
             f'| Extraction | events {", ".join(ext["event_ids"]) or "—"} (saved {ext["created_at"][1]}) |',
             f'| Source lines comparable | {"yes" if src["lines_comparable"] else "no"} |',
             f'| Document identifier | gold `{own["gold"]}` · attached {", ".join(own["attached"]) or "none"} '
             f'→ **{own["result"]}** (diagnostic, not scored) |',
             f'| Scored by | {scorer_model} |', '',
             '## Components', '',
             '| | Gold | Predicted | Matched | Soft precision | Soft recall | Soft F1 | Matched-row precision | Matched-row recall | Score |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    labels = {'listed': 'Listed entries', 'external_in_text': 'External in-text', 'internal': 'Internal',
              'criterion_or_set': 'criterion / criteria_set'}
    for label, v in [('All references', result['main'])] + [(labels[k], v) for k, v in result['groups'].items()]:
        lines.append(f'| {label} | {v["gold_rows"]} | {v["predicted_rows"]} | {v["matched"]} '
                     f'| {pct(v["soft_precision"])} | {pct(v["soft_recall"])} | {pct(v["soft_f1"])} '
                     f'| {pct(v["precision"])} | {pct(v["recall"])} | {v["score"]} |')
    lines += ['', 'Group rows count a pair under its gold row for recall and its predicted row for precision.',
              '', '## Field accuracy on matched pairs', '', '| Field | Weight | Accuracy |', '|---|---:|---:|']
    lines += [f'| {f} | {w:.2f} | {pct(result["field_accuracy"][f])} |' for f, w in WEIGHTS.items()]
    weak = [p for p in result['pairs'] if p['credit'] < 1]
    lines += ['', f'## Matched pairs with field errors ({len(weak)} of {len(result["pairs"])})', '']
    if weak:
        lines += ['| Gold | Predicted | Reference | Failed checks (gold → predicted) | Credit | Note |',
                  '|---|---|---|---|---:|---|']
        for p in weak:
            g, pr = gold[p['gold']], pred[p['pred']]
            failed = []
            for f, ok in p['checks'].items():
                if ok is None or ok == 1:
                    continue
                if f == 'identifiers':
                    show_f = lambda r: '; '.join(f'{i.get("kind")}:{i.get("value")}' + (f' ({i["edition"]})' if i.get('edition') else '')
                                                 for i in as_list(r.get('identifiers'))) or '[]'
                    failed.append(f'identifiers {show_f(g)} → {show_f(pr)}')
                elif f == 'list_link':
                    failed.append(f'list_link {g.get("list_entry_ref_id") or "—"} → {pr.get("list_entry_ref_id") or "—"}')
                elif f == 'quantity':
                    failed.append(f'quantity {g.get("metric_name")} → {pr.get("metric_name")}')
                elif f == 'relationships':
                    failed.append(f'relationships {",".join(as_list(g.get(f)))} → {",".join(as_list(pr.get(f)))}')
                else:
                    failed.append(f'{f} {g.get(f)} → {pr.get(f)}')
            lines.append(f'| {p["gold"]} | {p["pred"]} | {g["cited_raw"]} | {"; ".join(failed)} | '
                         f'{p["credit"]:.2f} | {p.get("note", "")} |')
    lines += ['', f'## Missed gold references ({len(result["missed"])})', '']
    lines += [f'- `{x["gold"]}` {show(gold[x["gold"]])} line {",".join(as_list(gold[x["gold"]]["source_line_spans"]))}: '
              f'{x.get("note", "")}' for x in result['missed']] or ['None.']
    lines += ['', f'## False positives ({len(result["false_positives"])})', '']
    for f in result['false_positives']:
        ref = {'gold_excluded': f'gold {f.get("gold_candidate_id")} {f.get("rule_id", "")}',
               'duplicate': f'duplicate of {f.get("of")}'}.get(f['cause'], f['cause'])
        lines.append(f'- `{f["pred"]}` {show(pred[f["pred"]])} — {ref}: {f.get("note", "")}')
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
              f'({", ".join(f"{f} {w}" for f, w in WEIGHTS.items())}); relationships earns its set overlap, '
              'quantity applies only when both rows are criterion rows. Soft precision = credit / predicted rows, '
              'soft recall = credit / gold rows, score = round(100 × soft F1), clamped to 1–100.']
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
    args = parser.parse_args()
    if args.action == 'export':
        require(args.record_id > 0, 'record ID must be a positive integer')
        path, payload = export(args.record_id, args.gold_version, args.gold_model, args.gold_run_id, args.out_dir)
        run = payload['gold_run']
        print(json.dumps({'input': str(path), 'gold_run': f'{run["skill_version"]}/{run["model_name"]}/'
                          f'{run["benchmark_run_id"]}', 'gold_rows': len(payload['gold']),
                          'predicted_rows': len(payload['predictions']),
                          'own_identifier': payload['own_identifier']['result'],
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
