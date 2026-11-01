#!/usr/bin/env python3
"""Validate independently authored provisions; save an immutable benchmark snapshot.

A run is one row in testbed.provision_benchmark_runs (audit record: ledger, coverage, reviews)
plus its gold provisions in testbed.provisions and its excluded and duplicate candidates in
testbed.provisions_dropped, inserted in one transaction."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys


TEXT_FIELDS = '''prov_id section provision provision_en prov_name provision_type provision_kind
provision_subject location_type'''.split()
BOOL_FIELDS = ['is_explicit']
# English companions: required on non-English documents, null on English ones.
EN_FIELDS = ['prov_name_en', 'provision_subject_en']
NONEMPTY_FIELDS = ['provision', 'prov_name', 'provision_subject']

# provision_kind (gold-only) decides provision_type, the field kb.provisions stores (rules §3.1).
KIND_TYPE = {'requirement': 'mandatory', 'prohibition': 'mandatory', 'instruction': 'mandatory',
             'recommendation': 'recommended', 'permission': 'optional'}
# The extractor's location vocabulary (prompt-extract-provisions-v3); rules §3.5.
LOCATIONS = {'sentence', 'paragraph', 'bullet', 'table_row', 'table_cell', 'heading_context', 'mixed'}
TABLE_LOCATIONS = {'table_row', 'table_cell'}
PART_SEPARATOR = ' … '

RUN_ID_FORMAT = '%Y%m%d_%H%M%S'
RUN_ID_PATTERN = re.compile(r'[0-9]{8}_[0-9]{6}')
RULE_PREFIX = {'accepted': 'A', 'excluded': 'X', 'duplicate': 'D'}
SKILL_DIR = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def skill_name():
    """The skill name, declared once in SKILL.md frontmatter."""
    text = SKILL_DIR.joinpath('SKILL.md').read_text(encoding='utf-8')
    front = re.match(r'---\n(.*?)\n---\n', text, re.S)
    name = front and re.search(r'^name:\s*(\S+)\s*$', front.group(1), re.M)
    if not name:
        raise ValueError('SKILL.md frontmatter has no name')
    return name.group(1)


def rules_manifest():
    return json.loads(SKILL_DIR.joinpath('rules', 'versions.json').read_text(encoding='utf-8'))


def version_key(version):
    """Numeric ordering key for MAJOR.MINOR.PATCH[-pre]; a pre-release sorts before its release."""
    match = re.fullmatch(r'([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z.-]+))?', version)
    require(match, f'Invalid skill version {version!r}; use MAJOR.MINOR.PATCH[-pre]')
    pre = match.group(4)
    return tuple(int(x) for x in match.groups()[:3]) + ((1,) if pre is None else (0, pre))


def newest_version(manifest=None):
    """The default: the newest released version, ignoring pre-releases (they must be named)."""
    versions = [v for v in (manifest or rules_manifest())['versions'] if '-' not in v]
    require(versions, 'No released skill version in rules/versions.json')
    return max(versions, key=version_key)


def resolve_rules(version=None):
    """Return (version, rules_sha256) for a released rules version; refuse edited rules files."""
    manifest = rules_manifest()
    version = version or newest_version(manifest)
    entry = manifest['versions'].get(version)
    require(entry, f'Unknown skill version {version!r}; released: {sorted(manifest["versions"])}')
    digest = hashlib.sha256(SKILL_DIR.joinpath('rules', entry['rules']).read_bytes()).hexdigest()
    require(digest == entry['sha256'],
            f'rules/{entry["rules"]} differs from released version {version}; released rules are frozen')
    return version, digest


def rule_ids(version):
    """Decision rule IDs (A1, X3, D1, ...) declared in bold in a rules file."""
    entry = rules_manifest()['versions'][version]
    text = SKILL_DIR.joinpath('rules', entry['rules']).read_text(encoding='utf-8')
    return set(re.findall(r'\*\*([ADX][0-9]+)\*\*', text))


def resolve_source(record):
    require(type(record.get('id')) is int and record['id'] > 0, 'Invalid kb.inputs.id')
    result = record.get('result_filename') or ''
    parser = (record.get('parser_name') or '').strip()
    require(result and parser, 'Missing result_filename or parser_name')
    result = Path(result)
    if not result.is_absolute():
        require(os.environ.get('DATA_HOME_DIR'), 'DATA_HOME_DIR required for relative result_filename')
        result = Path(os.environ['DATA_HOME_DIR']) / result
    root = Path(record.get('staging_filename') or result.name).stem
    return (result.parent / f'{root}_{parser}.txt').resolve()


def load_lines(record):
    path = resolve_source(record)
    raw = path.read_bytes()
    lines = {}
    previous = 0
    for physical, text in enumerate(raw.decode('utf-8').split('\n'), 1):
        text = text.removesuffix('\r')
        if not text.strip():
            continue
        parts = text.split('\t')
        require(len(parts) == 7, f'Record {physical}: expected seven TAB fields')
        number, page, kind, font, size, box, content = parts
        require(re.fullmatch(r'[1-9][0-9]*', number) and re.fullmatch(r'[1-9][0-9]*', page),
                f'Record {physical}: invalid line/page number')
        number, page = int(number), int(page)
        require(number > previous, f'Record {physical}: duplicate or non-increasing line number')
        require(kind.strip() and font.strip(), f'Record {physical}: empty type/font')
        size = float(size)
        require(math.isfinite(size) and size > 0, f'Record {physical}: invalid font size')
        box = json.loads(box)
        require(isinstance(box, list) and len(box) == 4 and
                all(type(x) in (int, float) and math.isfinite(x) for x in box),
                f'Record {physical}: invalid coordinates')
        lines[number] = {'line': number, 'page': page, 'type': kind, 'content': content}
        previous = number
    require(lines, 'Empty line file')
    return path, hashlib.sha256(raw).hexdigest(), lines


def new_run_id(now=None):
    return (now or datetime.now()).strftime(RUN_ID_FORMAT)


def prepare(record, model_name, version=None):
    require(isinstance(model_name, str) and model_name.strip(),
            'model_name required: the exact ID of the model running this skill')
    version, rules_sha256 = resolve_rules(version)
    path, digest, lines = load_lines(record)
    return {'record_id': record['id'], 'run_id': new_run_id(),
            'skill_name': skill_name(), 'skill_version': version, 'rules_sha256': rules_sha256,
            'model_name': model_name.strip(),
            'source_filename': str(path), 'source_sha256': digest,
            'language': '', 'completeness_review': '', 'correctness_review': '',
            'limitations': [], 'coverage': [], 'candidates': [], 'provisions': []}


def expand_spans(spans, lines):
    """Production span form: "N" or "N-M" (kb.provisions.source_line_spans)."""
    require(isinstance(spans, list) and spans, 'Nonempty source_line_spans required')
    expanded = []
    for span in spans:
        require(isinstance(span, str) and re.fullmatch(r'[1-9][0-9]*(?:-[1-9][0-9]*)?', span),
                f'Invalid span: {span!r}; use N or N-M')
        bounds = [int(x) for x in span.split('-')]
        start, end = bounds[0], bounds[-1]
        require(start <= end and end <= max(lines), f'Invalid span bounds: {span}')
        expanded.extend(range(start, end + 1))
    require(len(expanded) == len(set(expanded)), 'Overlapping or duplicate spans')
    require(set(expanded) <= lines.keys(), 'Span cites absent source lines')
    return set(expanded)


def string_list(value, name, nonempty=False):
    require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value),
            f'{name} must be an array of nonempty strings')
    require(not nonempty or value, f'{name} must not be empty')


def compact(text):
    """Whitespace-free form: line wraps and the parser's spacing never decide a text match."""
    return re.sub(r'\s+', '', text)


def source_texts(spans, lines):
    """The cited lines joined in line order, raw and with table markup removed (cell text)."""
    joined = ''.join(lines[n]['content'] for n in sorted(spans))
    return compact(joined), compact(html.unescape(re.sub(r'<[^>]+>', '', joined)))


def is_source_text(text, spans, lines):
    """Every ' … '-separated part of text occurs in the cited lines (rules §3.2)."""
    texts = source_texts(spans, lines)
    parts = [compact(part) for part in text.split(PART_SEPARATOR)]
    return all(part and any(part in t for t in texts) for part in parts)


def check_location(pid, location, spans, lines, table_rows):
    require(location in LOCATIONS, f'{pid}: unknown location_type {location!r}')
    table = {n for n in spans if lines[n]['type'] == 'table'}
    if location in TABLE_LOCATIONS:
        require(table == spans, f'{pid}: {location} needs table lines only')
    elif table == spans:
        require(False, f'{pid}: a provision on table lines is table_row or table_cell, not {location}')
    elif table:
        require(location == 'mixed', f'{pid}: a provision on table and non-table lines is mixed')
    require(isinstance(table_rows, list), f'{pid}: source_table_rows must be an array')
    for tref in table_rows:
        require(isinstance(tref, dict) and type(tref.get('line')) is int and tref['line'] in table,
                f'{pid}: source_table_rows names a line that is not a cited table line')
        string_list(tref.get('rows'), f'{pid}: table row IDs', True)
        require(all(re.fullmatch(r'r[1-9][0-9]*', x) for x in tref['rows']), f'{pid}: invalid table row ID')
    require(not table or table_rows, f'{pid}: a provision on a table line names its source_table_rows')


def validate(record, payload):
    path, digest, lines = load_lines(record)
    require(payload['record_id'] == record['id'], 'Document ID mismatch')
    require(isinstance(payload.get('run_id'), str) and RUN_ID_PATTERN.fullmatch(payload['run_id']),
            'run_id must be yyyymmdd_hhmmss from prepare')
    require(payload['source_filename'] == str(path) and payload['source_sha256'] == digest,
            'Source path/hash changed; re-extract and review this source')
    _, rules_sha256 = resolve_rules(payload.get('skill_version') or '-')
    require(payload.get('rules_sha256') == rules_sha256,
            'Payload rules_sha256 does not match the released rules for its skill_version')
    require(payload.get('skill_name') == skill_name(), 'Payload skill_name does not match this skill')
    rules = rule_ids(payload['skill_version'])
    require(isinstance(payload.get('model_name'), str) and payload['model_name'].strip(),
            'Missing model_name')
    for key in ('language', 'completeness_review', 'correctness_review'):
        require(isinstance(payload.get(key), str) and payload[key].strip(), f'Missing {key}')
    require(payload.get('limitations') == [], 'Unresolved limitations prevent benchmark publication')
    english = payload['language'].lower() == 'en'
    covered = set()
    for region in payload['coverage']:
        require(region.get('reason', '').strip(), 'Coverage region needs review notes')
        region_lines = expand_spans(region['source_line_spans'], lines)
        require(not covered.intersection(region_lines), 'Coverage regions overlap')
        covered.update(region_lines)
    require(covered == lines.keys(), 'Coverage does not account for every source line')

    id_pattern = re.compile(rf'{record["id"]}_gprv_[1-9][0-9]*')
    provisions, rows, ids, identities = payload['provisions'], [], set(), set()
    for prov in provisions:
        for field in TEXT_FIELDS:
            require(isinstance(prov.get(field), str), f'Missing/string field: {field}')
        pid = prov['prov_id']
        require(id_pattern.fullmatch(pid), f'prov_id {pid!r} must be {record["id"]}_gprv_<n>')
        require(pid not in ids, f'Duplicate prov_id {pid!r}')
        ids.add(pid)
        for field in BOOL_FIELDS:
            require(type(prov.get(field)) is bool, f'{pid}: {field} must be boolean')
        for field in NONEMPTY_FIELDS:
            require(prov[field].strip(), f'{pid}: empty {field}')
        spans = expand_spans(prov.get('source_line_spans'), lines)
        require(is_source_text(prov['provision'], spans, lines),
                f'{pid}: provision is not source text of its lines (join non-contiguous parts with " … ")')
        kind = prov['provision_kind']
        require(kind in KIND_TYPE, f'{pid}: unknown provision_kind {kind!r}')
        require(prov['provision_type'] == KIND_TYPE[kind],
                f'{pid}: provision_kind {kind} means provision_type {KIND_TYPE[kind]}, not {prov["provision_type"]!r}')
        table_rows = prov.get('source_table_rows', [])
        check_location(pid, prov['location_type'], spans, lines, table_rows)
        for field in EN_FIELDS:
            value = prov.get(field)
            require(value is None or isinstance(value, str), f'{pid}: invalid {field}')
            if english:
                require(not value, f'{pid}: {field} is only for non-English documents')
            else:
                require(value and value.strip(), f'{pid}: {field} required on a non-English document')
        require(not english or not prov['provision_en'], f'{pid}: provision_en is "" for English documents')

        confidence = prov.get('confidence')
        require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1,
                f'{pid}: invalid confidence')
        evidence = prov.get('evidence')
        require(isinstance(evidence, list) and evidence, f'{pid}: exact source evidence required')
        for excerpt in evidence:
            line = excerpt.get('line')
            require(type(line) is int and line in spans, f'{pid}: evidence line outside source spans')
            quote = excerpt.get('quote')
            require(isinstance(quote, str) and quote and quote in lines[line]['content'],
                    f'{pid}: evidence does not match source line {line}')

        identity = (tuple(sorted(spans)), compact(prov['provision']))
        require(identity not in identities, f'{pid}: duplicate provision (same lines and text)')
        identities.add(identity)

        notes = prov.get('annotation_notes', '')
        require(isinstance(notes, str), f'{pid}: annotation_notes must be a string')
        row = {key: prov[key] for key in TEXT_FIELDS + BOOL_FIELDS}
        row.update(source_line_spans=prov['source_line_spans'], source_table_rows=table_rows,
                   confidence=confidence, evidence=' '.join(e['quote'] for e in evidence),
                   input_record_id=record['id'], run_id=payload['run_id'],
                   source_filename=str(path), source_sha256=digest,
                   skill_name=payload['skill_name'], skill_version=payload['skill_version'],
                   model_name=payload['model_name'],
                   ext_info={'schema_version': '1', 'source': 'independent-benchmark', 'evidence': evidence})
        for field in EN_FIELDS:
            row[field] = prov.get(field) or None
        if notes:
            row['ext_info']['annotation_notes'] = notes
        rows.append(row)

    candidate_ids, linked = set(), set()
    for candidate in payload['candidates']:
        cid = candidate.get('candidate_id')
        require(isinstance(cid, str) and cid and cid not in candidate_ids, 'Invalid/duplicate candidate_id')
        candidate_ids.add(cid)
        require(candidate.get('reason', '').strip(), f'Candidate {cid}: decision needs rationale')
        spans = expand_spans(candidate.get('source_line_spans'), lines)
        text = candidate.get('text')
        require(isinstance(text, str) and is_source_text(text, spans, lines),
                f'Candidate {cid}: text must be source text of its lines')
        decision = candidate.get('decision')
        require(decision in ('accepted', 'excluded', 'duplicate'), f'Candidate {cid}: unresolved')
        rule = candidate.get('rule_id')
        require(rule in rules and rule.startswith(RULE_PREFIX[decision]),
                f'Candidate {cid}: rule_id must be a {RULE_PREFIX[decision]} rule of '
                f'rules {payload["skill_version"]}, got {rule!r}')
        targets = candidate.get('prov_ids', [])
        string_list(targets, f'Candidate {cid}: prov_ids', decision != 'excluded')
        require(set(targets) <= ids, f'Candidate {cid} references a missing prov_id')
        require(decision != 'excluded' or not targets, f'Excluded candidate {cid} references a provision')
        if decision == 'accepted':
            linked.update(targets)
    require(linked == ids, 'Every provision needs an accepted candidate')
    for row in rows:
        row['ext_info']['candidate_ids'] = sorted(
            c['candidate_id'] for c in payload['candidates'] if row['prov_id'] in c.get('prov_ids', []))
    return rows


def run_row(record, payload):
    """The run's testbed.provision_benchmark_runs row: its audit record, stored once per run.
    Call after validate, which checks every field used here."""
    metadata = record.get('doc_metadata') or {}
    return {key: payload[key] for key in ('skill_name', 'skill_version', 'model_name', 'run_id',
                                          'source_filename', 'source_sha256', 'rules_sha256', 'language',
                                          'coverage', 'candidates', 'completeness_review',
                                          'correctness_review')} | {
        'input_record_id': record['id'],
        'title': metadata.get('title') or record.get('title') or '',
        'doc_no': metadata.get('doc_no') or record.get('doc_no') or '',
        'reviewed_at': datetime.now(timezone.utc).isoformat()}


def sql_json(value):
    return "'" + json.dumps(value, ensure_ascii=False, allow_nan=False).replace("'", "''") + "'::jsonb"


def sql_text(value):
    return "'" + str(value).replace("'", "''") + "'"


def save_sql(record, payload, rows):
    # Fixed SQL identifiers and quoted JSON data; psql receives no credentials or SQL on argv.
    fields = TEXT_FIELDS + BOOL_FIELDS + EN_FIELDS + [
        'source_line_spans', 'source_table_rows', 'confidence', 'evidence', 'input_record_id', 'run_id',
        'source_filename', 'source_sha256', 'skill_name', 'skill_version', 'model_name', 'ext_info']
    columns = ', '.join(fields)
    run = run_row(record, payload)
    run_columns = ', '.join(run)
    identity = {key: record.get(key) for key in ('result_filename', 'staging_filename', 'parser_name')}
    run_key = ' AND '.join(f'{key} = {sql_text(payload[key])}' for key in
                           ('skill_name', 'skill_version', 'model_name', 'run_id'))
    # A run key is used once: the advisory lock serializes concurrent saves of the same key,
    # and the guard aborts if the run audit already exists, even with zero gold provisions.
    return f'''BEGIN;
SET LOCAL standard_conforming_strings = on;
SELECT id FROM kb.inputs WHERE id = {record['id']} FOR SHARE;
CREATE TEMP TABLE benchmark_input_guard (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_input_guard SELECT EXISTS (
 SELECT 1 FROM kb.inputs WHERE id = {record['id']}
 AND jsonb_build_object('result_filename', result_filename, 'staging_filename', staging_filename,
                        'parser_name', parser_name) = {sql_json(identity)});
SELECT pg_advisory_xact_lock(hashtextextended({sql_text('provision-benchmark ' + run_key)}, 0));
CREATE TEMP TABLE benchmark_run_key_unused (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_run_key_unused SELECT NOT EXISTS (
 SELECT 1 FROM testbed.provision_benchmark_runs WHERE {run_key});
INSERT INTO testbed.provision_benchmark_runs ({run_columns})
 SELECT {run_columns} FROM jsonb_populate_record(NULL::testbed.provision_benchmark_runs, {sql_json(run)});
INSERT INTO testbed.provisions ({columns})
 SELECT {columns} FROM jsonb_populate_recordset(NULL::testbed.provisions, {sql_json(rows)});
INSERT INTO testbed.provisions_dropped
 (input_record_id, skill_name, skill_version, model_name, run_id, candidate_id,
  decision, drop_reason, candidate_data)
 SELECT r.input_record_id, r.skill_name, r.skill_version, r.model_name, r.run_id,
        c->>'candidate_id', c->>'decision', c->>'rule_id', c
 FROM testbed.provision_benchmark_runs r
 CROSS JOIN LATERAL jsonb_array_elements(r.candidates) c
 WHERE {run_key} AND c->>'decision' IN ('excluded', 'duplicate');
SELECT count(*) AS saved_provisions FROM testbed.provisions WHERE {run_key};
SELECT count(*) AS saved_dropped FROM testbed.provisions_dropped WHERE {run_key};
COMMIT;
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'validate', 'save'])
    parser.add_argument('--record', required=True, type=Path, help='JSON exported from kb.inputs')
    parser.add_argument('--payload', type=Path, help='Reviewed benchmark JSON')
    parser.add_argument('--output', type=Path, help='New payload path for prepare')
    parser.add_argument('--model-name', help='prepare: exact ID of the model running this skill')
    parser.add_argument('--skill-version', help='prepare: released rules version (default: newest released, non-pre-release)')
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding='utf-8'))
    if args.action == 'prepare':
        require(args.output, '--output required for prepare')
        payload = prepare(record, args.model_name or '', args.skill_version)
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        _, _, lines = load_lines(record)
        print(json.dumps({'payload': str(args.output), 'lines': list(lines.values())}, ensure_ascii=False))
        return
    require(args.payload, '--payload required')
    payload = json.loads(args.payload.read_text(encoding='utf-8'))
    rows = validate(record, payload)
    if args.action == 'save':
        subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1'], input=save_sql(record, payload, rows),
                       text=True, check=True)
    print(json.dumps({'action': args.action, 'record_id': record['id'], 'run_id': payload['run_id'],
                      'skill_name': payload['skill_name'], 'skill_version': payload['skill_version'],
                      'model_name': payload['model_name'], 'provisions': len(rows),
                      'dropped': sum(c['decision'] in ('excluded', 'duplicate') for c in payload['candidates'])}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'benchmark_io: {exc}', file=sys.stderr)
        sys.exit(1)
