#!/usr/bin/env python3
"""Validate independently authored metrics; save an immutable benchmark snapshot."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


TEXT_FIELDS = '''metric_id metric_name metric_subject metric_desc metric_context
location_type metric_unit metric_value value_data_type value_range_type value_class
condition formula_or_definition threshold_or_target measurement_frequency
table_name_or_section'''.split()
ARRAY_FIELDS = ['metric_keywords', 'metric_categories', 'reasoning_tags', 'source_line_spans']
EN_FIELDS = '''metric_name_en metric_subject_en metric_desc_en metric_context_en
metric_unit_en value_class_en'''.split()
RANGE_TYPES = {'lower_bound', 'upper_bound', 'exact', 'range', 'qualitative', 'limit_absent'}
CLASSES = {'observation', 'requirement', 'target', 'reference', 'design_capability', 'definition'}
LOCATIONS = {'sentence', 'bullet', 'table_row', 'table_cell', 'heading_context', 'mixed'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


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


def prepare(record):
    path, digest, lines = load_lines(record)
    return {'record_id': record['id'], 'benchmark_run_id': str(uuid.uuid4()),
            'source_filename': str(path), 'source_sha256': digest,
            'language': '', 'completeness_review': '', 'correctness_review': '',
            'limitations': [], 'coverage': [], 'candidates': [], 'metrics': []}


def expand_spans(spans, lines):
    require(isinstance(spans, list) and spans, 'Nonempty source_line_spans required')
    expanded = []
    for span in spans:
        require(isinstance(span, str) and re.fullmatch(r'[1-9][0-9]*(?::[1-9][0-9]*)?', span),
                f'Invalid span: {span!r}; use N or N:M')
        bounds = [int(x) for x in span.split(':')]
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


def validate(record, payload):
    path, digest, lines = load_lines(record)
    require(payload['record_id'] == record['id'], 'Document ID mismatch')
    uuid.UUID(payload['benchmark_run_id'])
    require(payload['source_filename'] == str(path) and payload['source_sha256'] == digest,
            'Source path/hash changed; re-extract and review this source')
    for key in ('language', 'completeness_review', 'correctness_review'):
        require(isinstance(payload.get(key), str) and payload[key].strip(), f'Missing {key}')
    require(payload.get('limitations') == [], 'Unresolved limitations prevent benchmark publication')
    covered = set()
    for region in payload['coverage']:
        require(region.get('reason', '').strip(), 'Coverage region needs review notes')
        region_lines = expand_spans(region['source_line_spans'], lines)
        require(not covered.intersection(region_lines), 'Coverage regions overlap')
        covered.update(region_lines)
    require(covered == lines.keys(), 'Coverage does not account for every source line')
    rows, ids, identities = [], set(), set()
    now = datetime.now(timezone.utc).isoformat()
    for metric in payload['metrics']:
        for field in TEXT_FIELDS:
            require(isinstance(metric.get(field), str), f'Missing/string field: {field}')
        for field in ('metric_id', 'metric_name', 'metric_subject'):
            require(metric[field].strip(), f'Empty {field}')
        for field in ARRAY_FIELDS:
            string_list(metric.get(field), field, field in ('source_line_spans', 'metric_categories'))
        spans = expand_spans(metric['source_line_spans'], lines)
        require(metric['metric_id'] not in ids, 'Duplicate metric_id')
        ids.add(metric['metric_id'])
        require(metric['location_type'] in LOCATIONS, 'Invalid location_type')
        require(metric['value_range_type'] in RANGE_TYPES, 'Invalid value_range_type')
        require(metric['value_class'] in CLASSES, 'Invalid value_class')
        confidence = metric.get('confidence')
        require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1,
                'Invalid confidence')
        explicit = metric.get('is_explicit_metric')
        require(type(explicit) is bool, 'is_explicit_metric must be boolean')
        numeric = metric['value_range_type'] not in ('qualitative', 'limit_absent')
        require(explicit == numeric, 'is_explicit_metric contradicts value_range_type')
        if numeric:
            require(re.search(r'\d', metric['metric_value']), 'Numeric metric needs a source value')
        else:
            require(not metric['metric_value'] and not metric['metric_unit'],
                    'Qualitative/limit_absent value and unit must be empty')
        if metric['value_range_type'] == 'range':
            lo, hi = metric.get('value_min'), metric.get('value_max')
            require(type(lo) in (int, float) and type(hi) in (int, float) and
                    math.isfinite(lo) and math.isfinite(hi) and lo <= hi, 'Invalid range endpoints')
        else:
            require(metric.get('value_min') is None and metric.get('value_max') is None,
                    'Endpoints are for range metrics only')
        evidence = metric.get('evidence')
        require(isinstance(evidence, list) and evidence, 'Exact source evidence required')
        for excerpt in evidence:
            line = excerpt['line']
            require(type(line) is int and line in spans, 'Evidence line outside source spans')
            quote = excerpt['quote']
            require(isinstance(quote, str) and quote and quote in lines[line]['content'],
                    f'Evidence does not match source line {line}')
        table_rows = metric.get('source_table_rows', [])
        require(isinstance(table_rows, list), 'source_table_rows must be an array')
        for ref in table_rows:
            require(type(ref.get('line')) is int and ref['line'] in spans and
                    lines[ref['line']]['type'] == 'table', 'Invalid source_table_rows line')
            string_list(ref.get('rows'), 'table row IDs', True)
            require(all(re.fullmatch(r'r[1-9][0-9]*', x) for x in ref['rows']), 'Invalid table row ID')
        if metric['location_type'] in ('table_row', 'table_cell'):
            require(table_rows, 'Table metrics need logical row references')
        if 'external_reference' in metric['reasoning_tags']:
            require(metric['value_class'] == 'reference' and not numeric and
                    metric['value_range_type'] == 'qualitative' and not metric['formula_or_definition'] and
                    metric['threshold_or_target'] and
                    any(x.startswith('cited_doc:') for x in metric['reasoning_tags']),
                    'Incorrect external-reference metric')
        identity = tuple(metric[x].strip().lower() for x in
                         ('metric_name', 'metric_subject', 'metric_unit', 'metric_value',
                          'value_range_type', 'value_class', 'condition')) + (
                              tuple(sorted(spans)), json.dumps(table_rows, sort_keys=True))
        require(identity not in identities, 'Duplicate assertion')
        identities.add(identity)
        row = {key: metric[key] for key in TEXT_FIELDS + ARRAY_FIELDS}
        row.update(source_table_rows=table_rows, confidence=confidence, is_explicit_metric=explicit,
                   value_min=metric.get('value_min'), value_max=metric.get('value_max'))
        for key in EN_FIELDS:
            require(metric.get(key) is None or isinstance(metric[key], str), f'Invalid {key}')
            if payload['language'].lower() != 'en':
                row[key] = metric.get(key)
        if payload['language'].lower() != 'en':
            string_list(metric.get('metric_keywords_en', []), 'metric_keywords_en')
            row['metric_keywords_en'] = metric.get('metric_keywords_en', [])
        metadata = record.get('doc_metadata') or {}
        row.update(input_record_id=record['id'], benchmark_run_id=payload['benchmark_run_id'],
                   source_filename=str(path), source_sha256=digest,
                   ext_info={'schema_version': '2', 'source': 'independent-benchmark',
                             'language': payload['language'], 'reviewed_at': now,
                             'title': metadata.get('title') or record.get('title') or '',
                             'doc_no': metadata.get('doc_no') or record.get('doc_no') or '',
                             'evidence': evidence,
                             'coverage': payload['coverage'], 'candidates': payload['candidates'],
                             'completeness_review': payload['completeness_review'],
                             'correctness_review': payload['correctness_review']})
        notes = metric.get('annotation_notes', '')
        require(isinstance(notes, str), 'annotation_notes must be a string')
        if notes:
            row['ext_info']['annotation_notes'] = notes
        rows.append(row)
    candidate_ids, linked = set(), set()
    for candidate in payload['candidates']:
        cid = candidate.get('candidate_id')
        require(isinstance(cid, str) and cid and cid not in candidate_ids, 'Invalid/duplicate candidate_id')
        candidate_ids.add(cid)
        require(candidate.get('reason', '').strip(), 'Candidate decision needs rationale')
        expand_spans(candidate['source_line_spans'], lines)
        decision = candidate['decision']
        require(decision in ('accepted', 'excluded', 'duplicate'), 'Unresolved candidate')
        targets = candidate.get('metric_ids', [])
        string_list(targets, 'candidate metric_ids', decision != 'excluded')
        require(set(targets) <= ids, 'Candidate references missing metric')
        require(decision != 'excluded' or not targets, 'Excluded candidate references a metric')
        if decision == 'accepted':
            linked.update(targets)
    require(linked == ids, 'Every metric needs an accepted candidate')
    return rows


def sql_json(value):
    return "'" + json.dumps(value, ensure_ascii=False, allow_nan=False).replace("'", "''") + "'::jsonb"


def save_sql(record, payload, rows):
    # Fixed SQL identifiers and quoted JSON data; psql receives no credentials or SQL on argv.
    fields = TEXT_FIELDS + ARRAY_FIELDS + EN_FIELDS + ['metric_keywords_en', 'source_table_rows',
              'confidence', 'is_explicit_metric', 'value_min', 'value_max', 'input_record_id',
              'benchmark_run_id', 'source_filename', 'source_sha256', 'ext_info']
    columns = ', '.join(fields)
    identity = {key: record.get(key) for key in ('result_filename', 'staging_filename', 'parser_name')}
    return f'''BEGIN;
SET LOCAL standard_conforming_strings = on;
SELECT id FROM kb.inputs WHERE id = {record['id']} FOR SHARE;
CREATE TEMP TABLE benchmark_input_guard (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_input_guard SELECT EXISTS (
 SELECT 1 FROM kb.inputs WHERE id = {record['id']}
 AND jsonb_build_object('result_filename', result_filename, 'staging_filename', staging_filename,
                        'parser_name', parser_name) = {sql_json(identity)});
INSERT INTO testbed.metrics ({columns})
 SELECT {columns} FROM jsonb_populate_recordset(NULL::testbed.metrics, {sql_json(rows)});
SELECT count(*) AS saved_metrics FROM testbed.metrics
 WHERE input_record_id = {record['id']} AND benchmark_run_id = '{payload['benchmark_run_id']}';
COMMIT;
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'validate', 'save'])
    parser.add_argument('--record', required=True, type=Path, help='JSON exported from kb.inputs')
    parser.add_argument('--payload', type=Path, help='Reviewed benchmark JSON')
    parser.add_argument('--output', type=Path, help='New payload path for prepare')
    args = parser.parse_args()
    record = json.loads(args.record.read_text(encoding='utf-8'))
    if args.action == 'prepare':
        require(args.output, '--output required for prepare')
        payload = prepare(record)
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        _, _, lines = load_lines(record)
        print(json.dumps({'payload': str(args.output), 'lines': list(lines.values())}, ensure_ascii=False))
        return
    require(args.payload, '--payload required')
    payload = json.loads(args.payload.read_text(encoding='utf-8'))
    rows = validate(record, payload)
    if args.action == 'save':
        require(rows, 'Zero metrics: retain the audit JSON; no benchmark rows to save')
        subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1'], input=save_sql(record, payload, rows),
                       text=True, check=True)
    print(json.dumps({'action': args.action, 'record_id': record['id'],
                      'benchmark_run_id': payload['benchmark_run_id'], 'metrics': len(rows)}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'benchmark_io: {exc}', file=sys.stderr)
        sys.exit(1)
