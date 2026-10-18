#!/usr/bin/env python3
"""Validate independently authored metrics; save an immutable benchmark snapshot.

A run is one row in testbed.metric_benchmark_runs (audit record: ledger, coverage, reviews)
plus its metric rows in testbed.metrics, inserted in one transaction."""
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
import unicodedata


TEXT_FIELDS = '''metric_id metric_name metric_subject metric_desc metric_context
location_type metric_unit metric_value value_data_type value_range_type value_class
condition formula_or_definition threshold_or_target measurement_frequency
table_name_or_section'''.split()
ARRAY_FIELDS = ['metric_keywords', 'metric_categories', 'reasoning_tags', 'source_line_spans']
EN_FIELDS = '''metric_name_en metric_subject_en metric_desc_en metric_context_en
metric_unit_en value_class_en condition_en'''.split()
RANGE_TYPES = {'lower_bound', 'upper_bound', 'exact', 'range', 'qualitative', 'limit_absent'}
CLASSES = {'observation', 'requirement', 'target', 'reference', 'design_capability', 'definition'}
# Rules 4.1.0+: an A4 row (value left to a declaration or agreement) is a metric with no value.
# Benchmark-only: kb.metrics stores the same assertion as requirement + limit_absent.
NO_VALUE_CLASS = 'metric-with-no-value'
# Rules 9.0.0+: the metric frame (ChenWeb openspec change metric-frame, kb.metrics.frame).
FRAME_ROLES = {'agent', 'material', 'apparatus', 'reagent', 'medium', 'sample', 'device'}
# Qualifier labels that are frame facets from 9.0.0 on, never conditions.
FRAME_CONDITION_LABELS = {'试验装置', '试验设备', '试验介质', '溶媒', '试剂', '药物', '试验方法', '检验方法',
                          '给药途径', '给药方式', '给氧方式', '操作', '治疗阶段', '用药时机', '药物浓度'}
NO_VALUE_CLASS_EN = 'metric with no value'
TYPICAL_VALUE_MARKERS = ('典型值（领域经验，非本文件规定）：',
                         'Typical values (domain knowledge, not stated by this document):')
# Rules 5.1.0+: the typical values are a numeric range, or this phrase followed by a reason.
NO_TYPICAL_VALUE = re.compile(r'(无可比典型值（原因：|No comparable typical value \(reason:)\s*[^\s）)]')


def typical_values_given(desc):
    """Rules 5.1.0+: the text after the typical-values marker holds a number, or a reasoned escape."""
    tail = ''.join(desc.split(marker, 1)[1] for marker in TYPICAL_VALUE_MARKERS if marker in desc)
    return bool(re.search(r'[0-9]', tail) or NO_TYPICAL_VALUE.search(tail))
LOCATIONS = {'sentence', 'bullet', 'table_row', 'table_cell', 'heading_context', 'mixed'}
# benchmark_run_id: local time the run was prepared. A run is identified by
# (skill_name, skill_version, model_name, benchmark_run_id) and is never overwritten.
RUN_ID_FORMAT = '%Y%m%d_%H%M%S'
RUN_ID_PATTERN = re.compile(r'[0-9]{8}_[0-9]{6}')
# Rules 2.0.0+: metric_value is the bare number; the comparator lives in value_range_type.
COMPARATORS = re.compile(r'[<>≤≥＜＞≦≧]')
RULE_PREFIX = {'accepted': 'A', 'excluded': 'X', 'duplicate': 'D'}
NUMERIC_RANGE_TYPES = {'lower_bound', 'upper_bound', 'exact', 'range'}
# Statement kinds of ADR 2026100603. 'definition' and 'unclassified' exist in the application's
# vocabulary but never describe an accepted gold row (term definitions are X3).
STATEMENT_KINDS = {'requirement_with_criterion', 'requirement_value_open', 'inspection_requirement',
                   'delegated_requirement', 'test_parameter', 'metric_definition', 'metric_value',
                   'observation'}
# Rules 3.0.0+: requirements with nothing to measure are excluded (X15, X16), as extract_metrics
# drops them; a non-numeric observation is X15.
PURE_REQUIREMENT_KINDS = {'inspection_requirement', 'delegated_requirement', 'observation'}


def statement_kind(metric):
    """Kind of a metric row, by the same rules as ChenWeb web/src/lib/metric-statement-kind.ts
    and server/api/doc-processing/metric_statement_kind.go; change all three together."""
    value_class = metric['value_class'].strip().lower()
    if value_class == NO_VALUE_CLASS:
        # Gold-only class (rules 4.1.0+), classified as the requirement + limit_absent row
        # extract_metrics stores; the ChenWeb mirrors map it the same way.
        value_class = 'requirement'
    range_type = metric['value_range_type'].strip().lower()
    numeric = range_type in NUMERIC_RANGE_TYPES
    tags = [t.strip().lower() for t in metric['reasoning_tags']]
    if 'test_condition' in tags:
        return 'test_parameter'
    if value_class == 'definition':
        return 'metric_definition' if metric['formula_or_definition'].strip() else 'definition'
    if value_class == 'reference' or any(t == 'external_reference' or t.startswith('cited_doc:')
                                         for t in tags):
        return 'metric_value' if numeric else 'delegated_requirement'
    if value_class in ('requirement', 'target'):
        if numeric:
            return 'requirement_with_criterion'
        return 'requirement_value_open' if range_type == 'limit_absent' else 'inspection_requirement'
    if value_class in ('observation', 'design_capability'):
        return 'metric_value' if numeric else 'observation'
    return 'unclassified'


SKILL_DIR = Path(__file__).resolve().parent.parent


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
    """Decision rule IDs (A1, X3, D1, ...) declared in bold in a rules file; empty before 2.0.0."""
    entry = rules_manifest()['versions'][version]
    text = SKILL_DIR.joinpath('rules', entry['rules']).read_text(encoding='utf-8')
    return set(re.findall(r'\*\*([ADX][0-9]+)\*\*', text))


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


def new_run_id(now=None):
    return (now or datetime.now()).strftime(RUN_ID_FORMAT)


def prepare(record, model_name, version=None):
    require(isinstance(model_name, str) and model_name.strip(),
            'model_name required: the exact ID of the model running this skill')
    version, rules_sha256 = resolve_rules(version)
    path, digest, lines = load_lines(record)
    return {'record_id': record['id'], 'benchmark_run_id': new_run_id(),
            'skill_name': skill_name(), 'skill_version': version, 'rules_sha256': rules_sha256,
            'model_name': model_name.strip(),
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


def validate_frame(metric, language):
    """Rules 9.0.0+: frame is null or {uses, method, procedure} in the kb.metrics.frame shape."""
    frame, mid = metric.get('frame'), metric['metric_id']
    if frame is None:
        return None
    require(isinstance(frame, dict), f'{mid}: frame must be an object or null')
    unknown = sorted(set(frame) - {'uses', 'method', 'procedure'})
    require(not unknown, f'{mid}: unknown frame keys {unknown}')
    english = language.lower() == 'en'
    for res in frame.get('uses') or []:
        require(isinstance(res, dict) and isinstance(res.get('name'), str) and res['name'].strip(),
                f'{mid}: every frame.uses entry needs a name')
        require(res.get('role') in FRAME_ROLES, f'{mid}: frame.uses role must be one of {sorted(FRAME_ROLES)}')
        require(english or (res.get('name_en') or '').strip(), f'{mid}: frame.uses {res["name"]} needs name_en')
        require(not re.match(r'^\s*\d', res['name']), f'{mid}: frame.uses name {res["name"]!r} starts with its '
                                                     'strength or grade; put that in spec')
        for spec in res.get('spec') or []:
            require(isinstance(spec, dict) and str(spec.get('value') or '').strip()
                    and str(spec.get('property') or '').strip(),
                    f'{mid}: every spec of {res["name"]} needs a property and a value')
    for q in frame.get('method') or []:
        require(isinstance(q, dict) and str(q.get('value') or '').strip() and str(q.get('label') or '').strip(),
                f'{mid}: every frame.method entry needs a label and a value')
    proc = frame.get('procedure')
    require(proc is None or (isinstance(proc, dict) and
                             not set(proc) - {'step', 'stage', 'stage_en', 'after', 'after_en'}),
            f'{mid}: frame.procedure has only step, stage, stage_en, after, after_en')
    require(not re.search(r'\d+(\.\d+)?\s*[%％]', metric['metric_name'] or '') or not frame.get('uses'),
            f'{mid}: metric_name carries a strength; keep it in frame.uses spec (rules 9.0.0)')
    return frame


VALUE_STRUCTURE_KINDS = {'alternatives', 'required_points', 'composite', 'expression', 'unresolved'}


def structure_members_in_display(structure, display):
    """Mirror metricvalue.ValidateForValue: all numeric tokens, ordered for composites."""
    if structure.get('kind') not in {'alternatives', 'required_points', 'composite'}:
        return True
    numbers = lambda text: [float(token) for token in re.findall(
        r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',
        unicodedata.normalize('NFKC', str(text or '')))]
    values = structure.get('values') or []
    want, got = numbers(' '.join(values)), numbers(display)
    if not want:
        compact = lambda text: re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(text or '')))
        return all(compact(value) in compact(display) for value in values)
    if not all(math.isfinite(n) for n in want + got):
        return False
    if structure.get('kind') != 'composite':
        want, got = sorted(want), sorted(got)
    return want == got


def validate_value_structure(metric):
    structure = metric.get('value_structure')
    if structure is None:
        return None
    mid = metric['metric_id']
    require(isinstance(structure, dict) and not set(structure) - {'kind', 'values'},
            f'{mid}: value_structure permits kind and values only')
    kind = structure.get('kind')
    require(kind in VALUE_STRUCTURE_KINDS, f'{mid}: invalid value_structure kind')
    values = structure.get('values')
    if 'values' in structure:
        string_list(values, f'{mid}: value_structure.values')
        if kind != 'composite':
            require(len(set(v.strip() for v in values)) == len(values), f'{mid}: duplicate structure member')
    if kind in {'alternatives', 'required_points', 'composite'}:
        require(isinstance(values, list) and len(values) >= 2,
                f'{mid}: value_structure needs at least two members')
    if kind in {'alternatives', 'required_points'}:
        require(metric['value_range_type'] == 'exact', f'{mid}: a discrete collection is exact, never a range')
        require(metric.get('value_min') is None and metric.get('value_max') is None,
                f'{mid}: a discrete collection has no interval endpoints')
    require(structure_members_in_display(structure, metric['metric_value']),
            f'{mid}: value_structure members disagree with the complete metric_value')
    return structure


def string_list(value, name, nonempty=False):
    require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value),
            f'{name} must be an array of nonempty strings')
    require(not nonempty or value, f'{name} must not be empty')


def validate(record, payload):
    path, digest, lines = load_lines(record)
    require(payload['record_id'] == record['id'], 'Document ID mismatch')
    require(isinstance(payload.get('benchmark_run_id'), str) and
            RUN_ID_PATTERN.fullmatch(payload['benchmark_run_id']),
            'benchmark_run_id must be yyyymmdd_hhmmss from prepare; re-run prepare for a UUID payload')
    require(payload['source_filename'] == str(path) and payload['source_sha256'] == digest,
            'Source path/hash changed; re-extract and review this source')
    _, rules_sha256 = resolve_rules(payload.get('skill_version') or '-')
    # Payloads prepared before rules_sha256 existed (tooling <= 1.2.0) carry no hash; the
    # manifest check above already proves the rules file is the released one.
    payload_rules = payload.get('rules_sha256', rules_sha256)
    require(payload_rules == rules_sha256,
            'Payload rules_sha256 does not match the released rules for its skill_version')
    require(payload.get('skill_name') == skill_name(), 'Payload skill_name does not match this skill')
    # Checks introduced with rules 2.0.0; earlier versions keep validating as they were released.
    gated = version_key(payload['skill_version'])[0] >= 2
    # Checks introduced with rules 2.1.0: statement kind, reference rows, interpretation cut-offs.
    gated_2_1 = version_key(payload['skill_version'])[:3] >= (2, 1, 0)
    # Checks introduced with rules 3.0.0: only rows with a measurable property are metrics.
    gated_3 = version_key(payload['skill_version'])[0] >= 3
    # Checks introduced with rules 4.1.0: A4 rows are metrics with no value, with typical values.
    gated_4_1 = version_key(payload['skill_version'])[:3] >= (4, 1, 0)
    # Checks introduced with rules 5.1.0: typical values are a numeric range (or a reasoned escape).
    gated_5_1 = version_key(payload['skill_version'])[:3] >= (5, 1, 0)
    # Checks introduced with rules 6.0.0: a metric states a value (A4 and A5 retired, X18).
    gated_6 = version_key(payload['skill_version'])[0] >= 6
    # Checks introduced with rules 6.1.0: a symmetric ± tolerance keeps its sign in metric_value.
    gated_6_1 = version_key(payload['skill_version'])[:3] >= (6, 1, 0)
    # Checks introduced with rules 6.2.0: one row per metric, with the lines of all its occurrences.
    gated_6_2 = version_key(payload['skill_version'])[:3] >= (6, 2, 0)
    # Checks introduced with rules 6.4.0: a condition of a non-English source has its English rendering
    # in condition_en, as kb.metrics.condition_en does since extract_metrics enrich prompt v13.
    gated_6_4 = version_key(payload['skill_version'])[:3] >= (6, 4, 0)
    # Checks introduced with rules 9.0.0: the metric frame, and no frame label left in condition.
    gated_9 = version_key(payload['skill_version'])[0] >= 9
    gated_10 = version_key(payload['skill_version'])[0] >= 10
    rules = rule_ids(payload['skill_version']) if gated else set()
    require(isinstance(payload.get('model_name'), str) and payload['model_name'].strip(),
            'Missing model_name')
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
        require(metric['value_class'] in CLASSES or
                (gated_4_1 and metric['value_class'] == NO_VALUE_CLASS), 'Invalid value_class')
        if gated_4_1:
            no_value = metric['value_class'] == NO_VALUE_CLASS
            require(no_value == (metric['value_range_type'] == 'limit_absent'),
                    f'{metric["metric_id"]}: limit_absent rows (A4) and only they are {NO_VALUE_CLASS}')
            if no_value:
                english = payload['language'].lower() == 'en'
                descs = [metric['metric_desc']] + ([] if english else [metric.get('metric_desc_en') or ''])
                require(all(any(m in d for m in TYPICAL_VALUE_MARKERS) for d in descs),
                        f'{metric["metric_id"]}: metric_desc{"" if english else " and metric_desc_en"} '
                        'must explain the metric and give marked typical values (rules §3.2)')
                require(not gated_5_1 or all(typical_values_given(d) for d in descs),
                        f'{metric["metric_id"]}: typical values must be a numeric range with unit, or '
                        '"无可比典型值（原因：…）" / "No comparable typical value (reason: …)" (rules §3.2)')
                require(english or metric.get('value_class_en') == NO_VALUE_CLASS_EN,
                        f'{metric["metric_id"]}: value_class_en must be {NO_VALUE_CLASS_EN!r}')
        confidence = metric.get('confidence')
        require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1,
                'Invalid confidence')
        explicit = metric.get('is_explicit_metric')
        require(type(explicit) is bool, 'is_explicit_metric must be boolean')
        numeric = metric['value_range_type'] not in ('qualitative', 'limit_absent')
        require(explicit == numeric, 'is_explicit_metric contradicts value_range_type')
        require(not gated_6 or numeric,
                f'{metric["metric_id"]}: a metric states a value; a value-less candidate is X18 (rules §3.2)')
        require(not gated_6 or metric['value_class'] != 'definition' or
                'interpretation_bound' in metric['reasoning_tags'],
                f'{metric["metric_id"]}: value_class definition is only for interpretation cut-offs; '
                'a formula or definition without a value is X18, a term definition X3')
        if numeric:
            require(re.search(r'\d', metric['metric_value']), 'Numeric metric needs a source value')
            require(not gated or not COMPARATORS.search(metric['metric_value']),
                    'metric_value must not carry a comparator; use value_range_type')
            if gated_6_1 and metric['value_range_type'] != 'range':
                bare = metric['metric_value'].strip()
                signed = re.search(r'±\s*' + re.escape(bare) + r'(?![0-9.])', metric['threshold_or_target'])
                require(not signed, f'{metric["metric_id"]}: the source states ±{bare}; metric_value keeps '
                        'the ± sign (rules 6.1.0)')
        else:
            require(not metric['metric_value'] and not metric['metric_unit'],
                    'Qualitative/limit_absent value and unit must be empty')
        tags = metric['reasoning_tags']
        if gated:
            require('strict_bound' not in tags or
                    metric['value_range_type'] in ('lower_bound', 'upper_bound'),
                    'strict_bound is only for lower_bound/upper_bound metrics')
            require('test_condition' not in tags or numeric,
                    'test_condition metrics are numeric; carry qualitative settings as condition')
            require(metric['value_class'] != 'definition' or metric['formula_or_definition'].strip(),
                    'value_class definition needs formula_or_definition')
        if gated_2_1:
            kinds = [t[len('kind:'):] for t in tags if t.startswith('kind:')]
            require(len(kinds) == 1 and kinds[0] in STATEMENT_KINDS,
                    f'{metric["metric_id"]}: exactly one kind:<kind> tag from {sorted(STATEMENT_KINDS)}')
            derived = statement_kind(metric)
            require(kinds[0] == derived,
                    f'{metric["metric_id"]}: kind:{kinds[0]} disagrees with the row shape ({derived}); '
                    'fix the representation, not the tag')
            require(metric['value_class'] != 'reference' or 'external_reference' in tags,
                    f'{metric["metric_id"]}: value_class reference is only for A3 delegations')
            require('interpretation_bound' not in tags or (
                        metric['value_class'] == 'definition' and
                        metric['value_range_type'] in NUMERIC_RANGE_TYPES),
                    f'{metric["metric_id"]}: interpretation_bound rows are numeric definitions')
            if gated_3:
                require(kinds[0] not in PURE_REQUIREMENT_KINDS,
                        f'{metric["metric_id"]}: kind:{kinds[0]} has nothing to measure; '
                        'record it as an X15/X16 candidate, not a metric')
                require(metric['value_class'] != 'reference' and not any(
                            t == 'external_reference' or t.startswith('cited_doc:') for t in tags),
                        f'{metric["metric_id"]}: a delegation to a cited document is X16, not a metric')
            for tag in tags:
                if tag.startswith('cited_doc:'):
                    require(not re.match(r'[A-Za-z/]+[0-9]', tag[len('cited_doc:'):]),
                            f'{metric["metric_id"]}: write {tag} with a space before the number')
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
                          'value_range_type', 'value_class', 'condition'))
        if gated_10:
            identity += (json.dumps(validate_value_structure(metric), sort_keys=True),
                         json.dumps(validate_frame(metric, payload['language']), sort_keys=True))
        if not gated_6_2:                  # before 6.2.0 the same assertion at another location was a row
            identity += (tuple(sorted(spans)), json.dumps(table_rows, sort_keys=True))
        else:
            # The comparator includes strictness: <40 and ≤40 are different assertions.
            identity += ('strict_bound' in tags,)
        require(identity not in identities,
                'Duplicate assertion' if not gated_6_2 else
                f'{metric["metric_id"]}: the same metric is stated more than once; keep one row and list '
                'every occurrence line in source_line_spans (rules 6.2.0, Occurrences)')
        identities.add(identity)
        row = {key: metric[key] for key in TEXT_FIELDS + ARRAY_FIELDS}
        row.update(source_table_rows=table_rows, confidence=confidence, is_explicit_metric=explicit,
                   value_min=metric.get('value_min'), value_max=metric.get('value_max'))
        for key in EN_FIELDS:
            require(metric.get(key) is None or isinstance(metric[key], str), f'Invalid {key}')
            if payload['language'].lower() != 'en':
                row[key] = metric.get(key)
        row['value_structure'] = validate_value_structure(metric) if gated_10 else None
        row['frame'] = validate_frame(metric, payload['language']) if gated_9 else None
        if gated_9:
            labels = {re.split(r'[：:]', q.strip(), 1)[0].strip()
                      for q in re.split(r'[；;]', metric['condition']) if re.search(r'[：:]', q)}
            moved = sorted(labels & FRAME_CONDITION_LABELS)
            require(not moved, f'{metric["metric_id"]}: {", ".join(moved)} belong in frame, not condition (rules 9.0.0)')
        if gated_6_4 and payload['language'].lower() != 'en' and metric['condition'].strip():
            require((metric.get('condition_en') or '').strip(),
                    f'{metric["metric_id"]}: condition_en is required for a non-English condition (rules 6.4.0)')
        if payload['language'].lower() != 'en':
            string_list(metric.get('metric_keywords_en', []), 'metric_keywords_en')
            row['metric_keywords_en'] = metric.get('metric_keywords_en', [])
        row.update(input_record_id=record['id'], run_id=payload['benchmark_run_id'],
                   source_filename=str(path), source_sha256=digest,
                   skill_name=payload['skill_name'], skill_version=payload['skill_version'],
                   model_name=payload['model_name'],
                   # Per-row data only; the run's audit record goes to testbed.metric_benchmark_runs
                   # once (run_row). candidate_ids is filled after the ledger is checked.
                   ext_info={'schema_version': '3', 'source': 'independent-benchmark',
                             'evidence': evidence})
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
        if gated:
            rule = candidate.get('rule_id')
            require(rule in rules and rule.startswith(RULE_PREFIX[decision]),
                    f'Candidate {cid}: rule_id must be a {RULE_PREFIX[decision]} rule of '
                    f'rules {payload["skill_version"]}, got {rule!r}')
        targets = candidate.get('metric_ids', [])
        string_list(targets, 'candidate metric_ids', decision != 'excluded')
        require(set(targets) <= ids, 'Candidate references missing metric')
        require(decision != 'excluded' or not targets, 'Excluded candidate references a metric')
        if decision == 'accepted':
            linked.update(targets)
            if gated_6_2:
                cited = expand_spans(candidate['source_line_spans'], lines)
                for target in targets:
                    own = next(r for r in rows if r['metric_id'] == target)
                    require(cited <= expand_spans(own['source_line_spans'], lines),
                            f'Candidate {cid}: an occurrence of {target} must be listed in its '
                            'source_line_spans (rules 6.2.0, Occurrences)')
    require(linked == ids, 'Every metric needs an accepted candidate')
    for row in rows:
        row['ext_info']['candidate_ids'] = sorted(
            c['candidate_id'] for c in payload['candidates'] if row['metric_id'] in c.get('metric_ids', []))
    return rows


def run_row(record, payload):
    """The run's testbed.metric_benchmark_runs row: its audit record, stored once per run.
    Call after validate, which checks every field used here."""
    metadata = record.get('doc_metadata') or {}
    _, rules_sha256 = resolve_rules(payload['skill_version'])
    return {key: payload[key] for key in ('skill_name', 'skill_version', 'model_name', 'benchmark_run_id',
                                          'source_filename', 'source_sha256', 'language', 'coverage',
                                          'candidates', 'completeness_review', 'correctness_review')} | {
        'input_record_id': record['id'], 'rules_sha256': payload.get('rules_sha256', rules_sha256),
        'title': metadata.get('title') or record.get('title') or '',
        'doc_no': metadata.get('doc_no') or record.get('doc_no') or '',
        'reviewed_at': datetime.now(timezone.utc).isoformat()}


def sql_json(value):
    return "'" + json.dumps(value, ensure_ascii=False, allow_nan=False).replace("'", "''") + "'::jsonb"


def sql_text(value):
    return "'" + str(value).replace("'", "''") + "'"


def save_sql(record, payload, rows):
    # Fixed SQL identifiers and quoted JSON data; psql receives no credentials or SQL on argv.
    fields = TEXT_FIELDS + ARRAY_FIELDS + EN_FIELDS + ['metric_keywords_en', 'source_table_rows',
              'confidence', 'is_explicit_metric', 'value_min', 'value_max', 'input_record_id',
              'run_id', 'source_filename', 'source_sha256', 'skill_name', 'skill_version', 'model_name',
              'ext_info', 'frame', 'value_structure']
    columns = ', '.join(fields)
    run = run_row(record, payload)
    run_columns = ', '.join(run)
    identity = {key: record.get(key) for key in ('result_filename', 'staging_filename', 'parser_name')}
    run_key = ' AND '.join(f"{key} = {sql_text(payload[key])}" for key in
                           ('skill_name', 'skill_version', 'model_name', 'benchmark_run_id'))
    metric_run_key = ' AND '.join(f"{column} = {sql_text(payload[key])}" for column, key in
                                 (('skill_name', 'skill_name'), ('skill_version', 'skill_version'),
                                  ('model_name', 'model_name'), ('run_id', 'benchmark_run_id')))
    # A run key is used once: the advisory lock serializes concurrent saves of the same key,
    # and the guard aborts if the run audit already exists, even with zero gold rows.
    return f'''BEGIN;
SET LOCAL standard_conforming_strings = on;
SELECT id FROM kb.inputs WHERE id = {record['id']} FOR SHARE;
CREATE TEMP TABLE benchmark_input_guard (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_input_guard SELECT EXISTS (
 SELECT 1 FROM kb.inputs WHERE id = {record['id']}
 AND jsonb_build_object('result_filename', result_filename, 'staging_filename', staging_filename,
                        'parser_name', parser_name) = {sql_json(identity)});
SELECT pg_advisory_xact_lock(hashtextextended({sql_text(run_key)}, 0));
CREATE TEMP TABLE benchmark_run_key_unused (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_run_key_unused SELECT NOT EXISTS (
 SELECT 1 FROM testbed.metric_benchmark_runs WHERE {run_key});
INSERT INTO testbed.metric_benchmark_runs ({run_columns})
 SELECT {run_columns} FROM jsonb_populate_record(NULL::testbed.metric_benchmark_runs, {sql_json(run)});
INSERT INTO testbed.metrics ({columns})
 SELECT {columns} FROM jsonb_populate_recordset(NULL::testbed.metrics, {sql_json(rows)});
INSERT INTO testbed.metrics_dropped
 (input_record_id, skill_name, skill_version, model_name, run_id, candidate_id,
  decision, drop_reason, candidate_data)
 SELECT r.input_record_id, r.skill_name, r.skill_version, r.model_name, r.benchmark_run_id,
        c->>'candidate_id', c->>'decision', COALESCE(NULLIF(c->>'rule_id', ''), c->>'decision'), c
 FROM testbed.metric_benchmark_runs r
 CROSS JOIN LATERAL jsonb_array_elements(r.candidates) c
 WHERE {run_key} AND c->>'decision' IN ('excluded', 'duplicate');
SELECT count(*) AS saved_metrics FROM testbed.metrics
 WHERE {metric_run_key};
SELECT count(*) AS saved_dropped FROM testbed.metrics_dropped
 WHERE skill_name = {sql_text(payload['skill_name'])}
   AND skill_version = {sql_text(payload['skill_version'])}
   AND model_name = {sql_text(payload['model_name'])}
   AND run_id = {sql_text(payload['benchmark_run_id'])};
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
    print(json.dumps({'action': args.action, 'record_id': record['id'],
                      'benchmark_run_id': payload['benchmark_run_id'],
                      'skill_name': payload['skill_name'], 'skill_version': payload['skill_version'],
                      'model_name': payload['model_name'], 'metrics': len(rows),
                      'dropped': sum(c['decision'] in ('excluded', 'duplicate') for c in payload['candidates'])}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'benchmark_io: {exc}', file=sys.stderr)
        sys.exit(1)
