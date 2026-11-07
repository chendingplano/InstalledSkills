#!/usr/bin/env python3
"""Validate independently authored product relations; save an immutable benchmark snapshot.

A run is one row in testbed.product_benchmark_runs (audit record: ledger, coverage, reviews)
plus its gold rows in testbed.products and its excluded and duplicate candidates in
testbed.products_dropped, inserted in one transaction. One gold row is one
(product, relation_type) pair; rows of one product share product_key."""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys


# Vocabularies stored in kb.products (prompt-enrich-product-mention-v4 / merged-v2 long names).
PRODUCT_TYPES = {'specific_product', 'product_class', 'component', 'material', 'software', 'system',
                 'equipment', 'consumable', 'packaging', 'other'}
RELATION_TYPES = {'scope', 'regulated_object', 'requirement_target', 'performance_requirement',
                  'design_requirement', 'material_requirement', 'testing_requirement',
                  'certification_requirement', 'usage_condition', 'installation_requirement',
                  'maintenance_requirement', 'storage_requirement', 'prohibited_product',
                  'exempted_product', 'component_of', 'contains_product', 'compatible_with',
                  'replacement_or_alternative', 'measurement_object', 'risk_source', 'other'}
INTER_PRODUCT = {'component_of', 'contains_product', 'compatible_with', 'replacement_or_alternative'}
RELATIONSHIPS = INTER_PRODUCT | {'compared_with', 'other'}
OBLIGATIONS = {'mandatory', 'recommended', 'permitted', 'prohibited', 'conditional', 'descriptive'}
# The R rule that decides each relation type (rules 1.0.0 §3.2).
RELATION_RULE = {'performance_requirement': 'R1', 'design_requirement': 'R1', 'material_requirement': 'R1',
                 'testing_requirement': 'R1', 'certification_requirement': 'R1', 'usage_condition': 'R1',
                 'installation_requirement': 'R1', 'maintenance_requirement': 'R1',
                 'storage_requirement': 'R1', 'requirement_target': 'R2', 'prohibited_product': 'R3',
                 'exempted_product': 'R3', 'component_of': 'R4', 'contains_product': 'R4',
                 'compatible_with': 'R4', 'replacement_or_alternative': 'R4',
                 'measurement_object': 'R5', 'risk_source': 'R5', 'regulated_object': 'R6',
                 'scope': 'R7', 'other': 'R8'}

TEXT_FIELDS = '''product_rel_id product_key section product_name canonical_name product_type relation_type
relation_summary evidence_quote obligation_level requirement_text responsible_actor rule_id'''.split()
OPTIONAL_TEXT_FIELDS = ['relation_summary_en', 'requirement_text_en']
LIST_FIELDS = ['conditions', 'exceptions', 'parameters', 'related_products']
# English companions: required on non-English documents, null on English ones.
EN_FIELDS = ['product_name_en', 'canonical_name_en']
NONEMPTY_FIELDS = ['product_name', 'canonical_name', 'relation_summary', 'evidence_quote']
PART_SEPARATOR = ' … '

RUN_ID_FORMAT = '%Y%m%d_%H%M%S'
RUN_ID_PATTERN = re.compile(r'[0-9]{8}_[0-9]{6}')
RULE_PREFIX = {'accepted': 'A', 'excluded': 'X', 'duplicate': 'D'}
LINE_SPAN = re.compile(r'([1-9][0-9]*)(?:-([1-9][0-9]*))?')
EVIDENCE_SPAN = re.compile(r'([1-9][0-9]*)(?:-([1-9][0-9]*)|#([hr](?:0|[1-9][0-9]*)))?')
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
    """Decision rule IDs (A1, X3, D1, R2, ...) declared in bold in a rules file."""
    entry = rules_manifest()['versions'][version]
    text = SKILL_DIR.joinpath('rules', entry['rules']).read_text(encoding='utf-8')
    return set(re.findall(r'\*\*([ADXR][0-9]+)\*\*', text))


class _TableHTML(HTMLParser):
    """Collects <tr> rows and their <td>/<th> cells, as ParseTableGrid walks the HTML tree."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
            self.rows.append(self.row)
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = {'tag': tag, 'attrs': dict(attrs), 'text': []}
            self.row.append(self.cell)
        elif tag in ('br', 'p', 'div') and self.cell is not None:
            self.cell['text'].append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.cell = None
        elif tag == 'tr':
            self.row, self.cell = None, None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'].append(data)


def _span_attr(attrs, name):
    try:
        value = int(str(attrs.get(name, '1')).strip())
    except ValueError:
        return 1
    return value if value >= 1 else 1


def parse_table_grid(content):
    """Row IDs and cells of a single-line HTML table, assigned exactly as ChenWeb's
    docprocessing.ParseTableGrid (TableGridVersion 3): header rows h0…, data rows r1….
    Returns {row_id: [cell, ...]} or None when the content has no <tr>."""
    parser = _TableHTML()
    parser.feed(content)
    parser.close()
    if not parser.rows:
        return None
    pending, raws, width = {}, [], 0
    for tr in parser.rows:
        row = {'cells': [], 'spans': [], 'th': False, 'colspan': False, 'rowspan': 0, 'plain': []}
        col = 0

        def place(text, span):
            nonlocal col
            while len(row['cells']) <= col:
                row['cells'].append('')
                row['spans'].append(1)
            row['cells'][col] = text
            row['spans'][col] = span
            col += 1

        def fill_carried():
            while col in pending:
                carry = pending[col]
                place(carry[0], 1)
                carry[1] -= 1
                if carry[1] <= 0:
                    del pending[col - 1]

        for cell in tr:
            fill_carried()
            row['th'] = row['th'] or cell['tag'] == 'th'
            text = ' '.join(''.join(cell['text']).split())
            rs, cs = _span_attr(cell['attrs'], 'rowspan'), _span_attr(cell['attrs'], 'colspan')
            row['colspan'] = row['colspan'] or cs > 1
            row['rowspan'] = max(row['rowspan'], rs)
            if cs == 1 and rs == 1:
                row['plain'].append(col)
            for i in range(cs):
                if rs > 1:
                    pending[col] = [text, rs - 1]
                place(text, cs if i == 0 else 0)
        fill_carried()
        width = max(width, len(row['cells']))
        raws.append(row)
    for row in raws:
        row['cells'] += [''] * (width - len(row['cells']))

    headers = 0
    while headers < len(raws) and raws[headers]['th']:
        headers += 1
    headers = headers or 1

    def spans_past_header():
        return any(i + raws[i]['rowspan'] > headers for i in range(headers))

    def followed_by_subheader(i):
        if not raws[i]['colspan'] or i + 1 >= len(raws):
            return False
        return all(not (c < len(raws[i + 1]['cells']) and raws[i + 1]['cells'][c]) for c in raws[i]['plain'])

    while headers < len(raws) - 1 and headers < 3 and (followed_by_subheader(headers - 1) or spans_past_header()):
        headers += 1
    headers = min(headers, len(raws))
    return {(f'h{i}' if i < headers else f'r{i - headers + 1}'): row['cells'] for i, row in enumerate(raws)}


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
        entry = {'line': number, 'page': page, 'type': kind, 'content': content}
        if kind == 'table':
            entry['rows'] = parse_table_grid(content) or {}
        lines[number] = entry
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
            'limitations': [], 'coverage': [], 'candidates': [], 'products': []}


def source_listing(lines):
    """prepare stdout: every line, with a table line's rows labelled as the extractor sees them."""
    listing = []
    for entry in lines.values():
        item = {key: entry[key] for key in ('line', 'page', 'type', 'content')}
        if 'rows' in entry:
            item['rows'] = {rid: ' | '.join(cells) for rid, cells in entry['rows'].items()}
        listing.append(item)
    return listing


def expand_line_spans(spans, lines):
    """Coverage spans: "N" or "N-M"."""
    require(isinstance(spans, list) and spans, 'Nonempty source_line_spans required')
    expanded = []
    for span in spans:
        match = isinstance(span, str) and LINE_SPAN.fullmatch(span)
        require(match, f'Invalid span: {span!r}; use N or N-M')
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        require(start <= end and end <= max(lines), f'Invalid span bounds: {span}')
        expanded.extend(range(start, end + 1))
    require(len(expanded) == len(set(expanded)), 'Overlapping or duplicate spans')
    require(set(expanded) <= lines.keys(), 'Span cites absent source lines')
    return set(expanded)


def evidence_units(spans, lines, label):
    """Production evidence spans: "N", "N-M", "N#rK" or "N#hK" (kb.products.evidence_lines).
    Returns the cited units in line order: (line, row_id or None)."""
    require(isinstance(spans, list) and spans, f'{label}: nonempty evidence spans required')
    units = []
    for span in spans:
        match = isinstance(span, str) and EVIDENCE_SPAN.fullmatch(span)
        require(match, f'{label}: invalid span {span!r}; use N, N-M, N#rK or N#hK')
        start = int(match.group(1))
        if match.group(3):
            entry = lines.get(start)
            require(entry and entry['type'] == 'table', f'{label}: {span} names a row of a non-table line')
            require(match.group(3) in entry['rows'], f'{label}: {span} names a table row that does not exist')
            units.append((start, match.group(3)))
            continue
        end = int(match.group(2) or start)
        require(start <= end and end <= max(lines), f'{label}: invalid span bounds {span}')
        for n in range(start, end + 1):
            require(n in lines, f'{label}: {span} cites absent source line {n}')
            require(lines[n]['type'] != 'table', f'{label}: cite table line {n} by rows (N#rK), not {span}')
            units.append((n, None))
    require(len(units) == len(set(units)), f'{label}: overlapping or duplicate spans')
    return sorted(units, key=lambda u: (u[0], u[1] or ''))


def compact(text):
    """Whitespace-free form: line wraps and the parser's spacing never decide a text match."""
    return re.sub(r'\s+', '', text)


def unit_texts(unit, lines):
    """A cited unit's text forms: a row's cells, or a line raw and with markup removed."""
    line, row = unit
    if row:
        cells = lines[line]['rows'][row]
        return [compact(''.join(cells))] + [compact(c) for c in cells]
    content = lines[line]['content']
    return [compact(content), compact(html.unescape(re.sub(r'<[^>]+>', '', content)))]


def joined_texts(units, lines):
    """The cited units joined in order: raw and markup-free (rows contribute their cells)."""
    raw, plain = [], []
    for unit in units:
        texts = unit_texts(unit, lines)
        raw.append(texts[0])
        plain.append(texts[0] if unit[1] else texts[1])
    return [''.join(raw), ''.join(plain)]


def is_source_text(text, units, lines):
    """Every ' … '-separated part of text occurs in the cited units joined in order."""
    texts = joined_texts(units, lines)
    parts = [compact(part) for part in text.split(PART_SEPARATOR)]
    return all(part and any(part in t for t in texts) for part in parts)


def in_one_unit(text, units, lines):
    part = compact(text)
    return bool(part) and any(part in t for u in units for t in unit_texts(u, lines))


def string_list(value, name, nonempty=False):
    require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value),
            f'{name} must be an array of nonempty strings')
    require(not nonempty or value, f'{name} must not be empty')


def check_parameters(pid, parameters):
    require(isinstance(parameters, list), f'{pid}: parameters must be an array')
    for item in parameters:
        require(isinstance(item, dict) and set(item) == {'name', 'value', 'unit'},
                f'{pid}: a parameter is {{"name", "value", "unit"}}')
        require(isinstance(item['name'], str) and item['name'].strip() and
                isinstance(item['value'], str) and item['value'].strip(),
                f'{pid}: a parameter needs a nonempty name and value')
        require(item['unit'] is None or (isinstance(item['unit'], str) and item['unit'].strip()),
                f'{pid}: a parameter unit is a nonempty string or null')


def check_related(pid, relation, related):
    require(isinstance(related, list), f'{pid}: related_products must be an array')
    require(bool(related) == (relation in INTER_PRODUCT),
            f'{pid}: related_products is nonempty exactly for {sorted(INTER_PRODUCT)}')
    for item in related:
        require(isinstance(item, dict) and set(item) == {'product_name', 'relationship'},
                f'{pid}: a related product is {{"product_name", "relationship"}}')
        require(isinstance(item['product_name'], str) and item['product_name'].strip(),
                f'{pid}: related product needs a name')
        require(item['relationship'] in RELATIONSHIPS, f'{pid}: unknown relationship {item["relationship"]!r}')


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
        region_lines = expand_line_spans(region['source_line_spans'], lines)
        require(not covered.intersection(region_lines), 'Coverage regions overlap')
        covered.update(region_lines)
    require(covered == lines.keys(), 'Coverage does not account for every source line')

    rel_pattern = re.compile(rf'{record["id"]}_gprd_[1-9][0-9]*')
    key_pattern = re.compile(rf'{record["id"]}_gp_[1-9][0-9]*')
    rows, ids, products, pairs = [], set(), {}, set()
    for item in payload['products']:
        for field in TEXT_FIELDS:
            require(isinstance(item.get(field), str), f'Missing/string field: {field}')
        pid = item['product_rel_id']
        require(rel_pattern.fullmatch(pid), f'product_rel_id {pid!r} must be {record["id"]}_gprd_<n>')
        require(pid not in ids, f'Duplicate product_rel_id {pid!r}')
        ids.add(pid)
        key = item['product_key']
        require(key_pattern.fullmatch(key), f'{pid}: product_key {key!r} must be {record["id"]}_gp_<n>')
        for field in NONEMPTY_FIELDS:
            require(item[field].strip(), f'{pid}: empty {field}')
        require(item['product_type'] in PRODUCT_TYPES, f'{pid}: unknown product_type {item["product_type"]!r}')
        relation = item['relation_type']
        require(relation in RELATION_TYPES, f'{pid}: unknown relation_type {relation!r}')
        require(item['obligation_level'] in OBLIGATIONS,
                f'{pid}: obligation_level must be one of {sorted(OBLIGATIONS)}')
        require(item['rule_id'] in rules and item['rule_id'] == RELATION_RULE[relation],
                f'{pid}: relation {relation} is decided by rule {RELATION_RULE[relation]}, got {item["rule_id"]!r}')
        identity = (key, relation)
        require(identity not in pairs, f'{pid}: product {key} already has a {relation} row')
        pairs.add(identity)
        shared = (item['product_name'], item['canonical_name'], item['product_type'])
        require(products.setdefault(key, shared) == shared,
                f'{pid}: rows of product {key} must share product_name, canonical_name and product_type')

        units = evidence_units(item.get('evidence_lines'), lines, pid)
        expanded = item.get('name_expanded', False)
        require(type(expanded) is bool, f'{pid}: name_expanded must be boolean')
        if expanded:
            source_name = item.get('name_source')
            require(isinstance(source_name, str) and is_source_text(source_name, units, lines),
                    f'{pid}: an expanded name needs name_source, the source phrase in its cited lines')
        else:
            require(is_source_text(item['product_name'], units, lines),
                    f'{pid}: product_name does not occur in its cited lines (set name_expanded for an expansion)')
        require(in_one_unit(item['evidence_quote'], units, lines),
                f'{pid}: evidence_quote is not a substring of one cited line or row')
        descriptive = item['obligation_level'] == 'descriptive'
        if descriptive:
            require(not item['requirement_text'], f'{pid}: a descriptive row has no requirement_text')
            require(not item['responsible_actor'], f'{pid}: a descriptive row has no responsible_actor')
        else:
            require(item['requirement_text'].strip(), f'{pid}: a {item["obligation_level"]} row needs requirement_text')
            require(is_source_text(item['requirement_text'], units, lines),
                    f'{pid}: requirement_text is not source text of its lines (join parts with " … ")')
        require(relation not in ('scope', 'exempted_product') or descriptive,
                f'{pid}: a {relation} row is descriptive')
        require(relation != 'prohibited_product' or item['obligation_level'] == 'prohibited',
                f'{pid}: a prohibited_product row has obligation_level prohibited')
        for field in ('conditions', 'exceptions'):
            value = item.get(field, [])
            string_list(value, f'{pid}: {field}')
        check_parameters(pid, item.get('parameters', []))
        check_related(pid, relation, item.get('related_products', []))
        for field in OPTIONAL_TEXT_FIELDS:
            require(isinstance(item.get(field, ''), str), f'{pid}: {field} must be a string')
        for field in EN_FIELDS:
            value = item.get(field)
            require(value is None or isinstance(value, str), f'{pid}: invalid {field}')
            if english:
                require(not value, f'{pid}: {field} is only for non-English documents')
            else:
                require(value and value.strip(), f'{pid}: {field} required on a non-English document')
        confidence = item.get('confidence')
        require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1,
                f'{pid}: invalid confidence')
        notes = item.get('annotation_notes', '')
        require(isinstance(notes, str), f'{pid}: annotation_notes must be a string')

        row = {field: item[field] for field in TEXT_FIELDS}
        row.update({field: item.get(field, '') for field in OPTIONAL_TEXT_FIELDS})
        row.update({field: item.get(field, []) for field in LIST_FIELDS})
        row.update({field: item.get(field) or None for field in EN_FIELDS})
        row.update(evidence_lines=item['evidence_lines'], confidence=confidence,
                   input_record_id=record['id'], run_id=payload['run_id'],
                   source_filename=str(path), source_sha256=digest,
                   skill_name=payload['skill_name'], skill_version=payload['skill_version'],
                   model_name=payload['model_name'],
                   ext_info={'schema_version': '1', 'source': 'independent-benchmark'})
        if expanded:
            row['ext_info'].update(name_expanded=True, name_source=item['name_source'])
        if notes:
            row['ext_info']['annotation_notes'] = notes
        rows.append(row)

    candidate_ids, linked = set(), set()
    for candidate in payload['candidates']:
        cid = candidate.get('candidate_id')
        require(isinstance(cid, str) and cid and cid not in candidate_ids, 'Invalid/duplicate candidate_id')
        candidate_ids.add(cid)
        require(candidate.get('reason', '').strip(), f'Candidate {cid}: decision needs rationale')
        units = evidence_units(candidate.get('source_line_spans'), lines, f'Candidate {cid}')
        text = candidate.get('text')
        require(isinstance(text, str) and is_source_text(text, units, lines),
                f'Candidate {cid}: text must be source text of its lines')
        decision = candidate.get('decision')
        require(decision in ('accepted', 'excluded', 'duplicate'), f'Candidate {cid}: unresolved')
        rule = candidate.get('rule_id')
        require(rule in rules and rule.startswith(RULE_PREFIX[decision]),
                f'Candidate {cid}: rule_id must be a {RULE_PREFIX[decision]} rule of '
                f'rules {payload["skill_version"]}, got {rule!r}')
        targets = candidate.get('product_keys', [])
        string_list(targets, f'Candidate {cid}: product_keys', decision != 'excluded')
        require(set(targets) <= products.keys(), f'Candidate {cid} references a product_key with no rows')
        require(decision != 'excluded' or not targets, f'Excluded candidate {cid} references a product')
        if decision == 'accepted':
            linked.update(targets)
    require(linked == products.keys(), 'Every product_key needs an accepted candidate')
    for row in rows:
        row['ext_info']['candidate_ids'] = sorted(
            c['candidate_id'] for c in payload['candidates'] if row['product_key'] in c.get('product_keys', []))
    return rows


def run_row(record, payload):
    """The run's testbed.product_benchmark_runs row: its audit record, stored once per run.
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
    fields = TEXT_FIELDS + OPTIONAL_TEXT_FIELDS + LIST_FIELDS + EN_FIELDS + [
        'evidence_lines', 'confidence', 'input_record_id', 'run_id', 'source_filename', 'source_sha256',
        'skill_name', 'skill_version', 'model_name', 'ext_info']
    columns = ', '.join(fields)
    run = run_row(record, payload)
    run_columns = ', '.join(run)
    identity = {key: record.get(key) for key in ('result_filename', 'staging_filename', 'parser_name')}
    run_key = ' AND '.join(f'{key} = {sql_text(payload[key])}' for key in
                           ('skill_name', 'skill_version', 'model_name', 'run_id'))
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
SELECT pg_advisory_xact_lock(hashtextextended({sql_text('product-benchmark ' + run_key)}, 0));
CREATE TEMP TABLE benchmark_run_key_unused (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_run_key_unused SELECT NOT EXISTS (
 SELECT 1 FROM testbed.product_benchmark_runs WHERE {run_key});
INSERT INTO testbed.product_benchmark_runs ({run_columns})
 SELECT {run_columns} FROM jsonb_populate_record(NULL::testbed.product_benchmark_runs, {sql_json(run)});
INSERT INTO testbed.products ({columns})
 SELECT {columns} FROM jsonb_populate_recordset(NULL::testbed.products, {sql_json(rows)});
INSERT INTO testbed.products_dropped
 (input_record_id, skill_name, skill_version, model_name, run_id, candidate_id,
  decision, drop_reason, candidate_data)
 SELECT r.input_record_id, r.skill_name, r.skill_version, r.model_name, r.run_id,
        c->>'candidate_id', c->>'decision', c->>'rule_id', c
 FROM testbed.product_benchmark_runs r
 CROSS JOIN LATERAL jsonb_array_elements(r.candidates) c
 WHERE {run_key} AND c->>'decision' IN ('excluded', 'duplicate');
SELECT count(*) AS saved_products FROM testbed.products WHERE {run_key};
SELECT count(*) AS saved_dropped FROM testbed.products_dropped WHERE {run_key};
COMMIT;
'''


def summary(payload, rows):
    return {'rows': len(rows), 'products': len({r['product_key'] for r in rows}),
            'dropped': sum(c['decision'] in ('excluded', 'duplicate') for c in payload['candidates'])}


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
        print(json.dumps({'payload': str(args.output), 'lines': source_listing(lines)}, ensure_ascii=False))
        return
    require(args.payload, '--payload required')
    payload = json.loads(args.payload.read_text(encoding='utf-8'))
    rows = validate(record, payload)
    if args.action == 'save':
        subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1'], input=save_sql(record, payload, rows),
                       text=True, check=True)
    print(json.dumps({'action': args.action, 'record_id': record['id'], 'run_id': payload['run_id'],
                      'skill_name': payload['skill_name'], 'skill_version': payload['skill_version'],
                      'model_name': payload['model_name']} | summary(payload, rows)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'benchmark_io: {exc}', file=sys.stderr)
        sys.exit(1)
