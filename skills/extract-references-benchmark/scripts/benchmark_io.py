#!/usr/bin/env python3
"""Validate independently authored references; save an immutable benchmark snapshot.

A run is one row in testbed.reference_benchmark_runs (audit record: ledger, coverage, reviews,
the document's own identifier) plus its gold references in testbed.ref_mentions and its excluded
and duplicate candidates in testbed.ref_mentions_dropped, inserted in one transaction."""
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


TEXT_FIELDS = '''ref_id section ref_form list_kind list_label list_entry_ref_id normativity
list_mismatch mechanism cited_raw target_type target_subtype target_subtype_label target_title
target_version target_scope target_locator target_content metric_name metric_subject
condition'''.split()
BOOL_FIELDS = ['in_requirement', 'internal']
EN_FIELDS = ['metric_name_en', 'metric_subject_en']
METRIC_FIELDS = ['metric_name', 'metric_subject', 'condition']

# Governed vocabularies of ChenWeb server/api/doc-processing/reference_model.go; change both together.
TARGET_SUBTYPES = {
    'document': '''report specification proposal manual file internal_document document_section
        document_element document_version document_collection''',
    'web_resource': '''website web_page blog blog_post online_article wiki_page online_forum forum_post
        social_media_post online_documentation web_archive''',
    'publication': '''journal_article conference_paper preprint working_paper technical_report thesis book
        book_chapter review_article dataset_paper poster_or_abstract research_protocol''',
    'standard': '''international_standard national_standard industry_standard technical_specification
        internet_standard draft_standard standard_amendment standard_corrigendum standard_part
        standard_clause technical_guideline conformance_profile''',
    'legal': '''law regulation directive administrative_rule legal_code_provision court_decision legal_case
        regulatory_guidance regulatory_notice government_policy treaty legislative_document''',
    'general_publication': '''book encyclopedia_entry dictionary_entry handbook magazine_article
        newspaper_article white_paper newsletter press_release brochure_or_catalog''',
    'software': '''software_project source_code_file source_code_element commit branch_or_tag pull_request
        issue_or_ticket software_release software_package api api_endpoint software_dependency
        configuration container_image build_artifact''',
    'data': '''dataset database database_record database_table database_row data_field statistical_series
        spreadsheet spreadsheet_element data_repository knowledge_graph_entity ontology_concept''',
    'media': '''image diagram chart audio_recording video presentation slide webinar transcript map
        geospatial_layer''',
    'communication': '''email email_thread chat_message discussion_thread meeting_record decision_record memo
        announcement shared_workspace_item''',
    'business_record': '''organization product product_model product_specification patent trademark contract
        procurement_document certification audit_report safety_document test_report''',
    'other': '''person event location concept_or_term definition measurement_or_metric mathematical_formula
        procedure experiment physical_sample clinical_trial''',
}
TARGET_SUBTYPES = {k: set(v.split()) for k, v in TARGET_SUBTYPES.items()}
SUBTYPE_OTHERS = 'others'
MECHANISMS = set('''url hyperlink doi isbn issn arxiv_id pmid standard_number rfc_number legal_citation
    patent_number repository_path file_path relative_path anchor numbered_citation author_year citation_key
    footnote named_reference structural_reference indirect_reference identifier
    cross_reference_field'''.split())
RELATIONSHIPS = set('''cites references quotes defines_in based_on implements complies_with requires
    supersedes amends supports refutes extends uses depends_on derived_from see_also'''.split())
SCOPES = {'collection', 'document', 'section', 'requirement', 'data_element'}
CONTENTS = {'criterion', 'criteria_set', 'method', 'term', 'requirements', 'data', 'general'}
METRIC_CONTENTS = {'criterion', 'criteria_set'}
# Citations that only point at an entry of the document's own list (reference_normativity.go).
LABEL_MECHANISMS = {'numbered_citation', 'author_year', 'citation_key', 'footnote'}
# Identifier kinds (reference_identifiers.go): public kinds in identity-key priority order.
PUBLIC_KINDS = ['standard', 'rfc', 'legal', 'doi', 'arxiv', 'pmid', 'isbn', 'issn', 'patent', 'url']
PRIVATE_KINDS = ['file_path', 'repository']
EDITION = re.compile(r'(?:19|20)[0-9]{2}')

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
            'language': '', 'document_identifier': '', 'completeness_review': '',
            'correctness_review': '', 'limitations': [], 'coverage': [], 'candidates': [],
            'references': []}


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


def norm_key(text):
    return ' '.join(text.lower().split())


def identity_key(ref):
    """kind:value of the highest-priority identifier, else title:<normalized title>, else ''
    (refIdentityKey in reference_identifiers.go). Editions never enter the key."""
    for kind in PUBLIC_KINDS + PRIVATE_KINDS:
        for ident in ref['identifiers']:
            if ident['kind'] == kind:
                return f'{kind}:{ident["value"]}'
    title = norm_key(ref['target_title'])
    return f'title:{title}' if title else ''


def publicly_identified(ref):
    return any(i['kind'] in PUBLIC_KINDS for i in ref['identifiers'])


def check_identifiers(rid, identifiers):
    require(isinstance(identifiers, list), f'{rid}: identifiers must be an array')
    seen = set()
    for ident in identifiers:
        require(isinstance(ident, dict) and set(ident) <= {'kind', 'value', 'edition'},
                f'{rid}: an identifier is {{kind, value[, edition]}}')
        kind, value = ident.get('kind'), ident.get('value')
        require(kind in PUBLIC_KINDS + PRIVATE_KINDS, f'{rid}: unknown identifier kind {kind!r}')
        require(isinstance(value, str) and value.strip() == value and value, f'{rid}: empty identifier value')
        require((kind, value) not in seen, f'{rid}: duplicate identifier {kind}:{value}')
        seen.add((kind, value))
        edition = ident.get('edition')
        require(edition is None or (isinstance(edition, str) and edition),
                f'{rid}: omit edition when the citation is undated')
        if kind == 'standard':
            require(not re.search(r'[-—–:](?:19|20)[0-9]{2}$', value),
                    f'{rid}: put the edition year of {value!r} in edition, not value')
            require(re.fullmatch(r'\S+(?: \S+)* [A-Z]?[0-9][0-9.]*(?:-[0-9]{1,3})*', value),
                    f'{rid}: standard {value!r} needs prefix, one space, number[-part] (GB/T 755, ISO 14253-1)')
            require(edition is None or EDITION.fullmatch(edition), f'{rid}: standard edition is a year')
        if kind == 'doi':
            require(value == value.lower(), f'{rid}: DOIs are lower-case')


def derive_lists(refs):
    """Normativity, list links and mismatches recomputed from the rows (rules §3.6, mirroring
    deriveRefNormativity in reference_normativity.go). Returns {ref_id: (normativity,
    allowed list_entry_ref_ids, list_mismatch)}."""
    by_id = {r['ref_id']: r for r in refs}
    listed = [r for r in refs if r['ref_form'] == 'listed']
    labels = {norm_key(r['list_label']): r['ref_id'] for r in listed if r['list_label'].strip()}
    entries = {'normative': {}, 'informative': {}}
    for r in listed:
        key = identity_key(r)
        if key:
            entries[r['list_kind']].setdefault(key, []).append(r['ref_id'])
    derived, used = {}, set()
    for r in refs:
        rid = r['ref_id']
        if r['ref_form'] == 'listed':
            derived[rid] = (r['list_kind'], {''}, '')
            continue
        allowed = {''}
        if not r['internal']:
            key = identity_key(r)
            if r['mechanism'] in LABEL_MECHANISMS and norm_key(r['cited_raw']) in labels:
                allowed = {labels[norm_key(r['cited_raw'])]}
            elif key and key in entries['normative']:
                allowed = set(entries['normative'][key])
            elif key and key in entries['informative']:
                allowed = set(entries['informative'][key])
            if r['mechanism'] in LABEL_MECHANISMS and allowed == {''}:
                # A range such as [12-15] links each entry it covers; trust a link to a listed entry.
                link = r['list_entry_ref_id']
                if link in by_id and by_id[link]['ref_form'] == 'listed':
                    allowed = {link}
        link = r['list_entry_ref_id'] if r['list_entry_ref_id'] in allowed else sorted(allowed)[-1]
        normativity = by_id[link]['list_kind'] if link else 'unlisted'
        if link:
            used.add(link)
        derived[rid] = (normativity, allowed, '')
    if entries['normative']:
        for r in refs:
            rid = r['ref_id']
            normativity, allowed, _ = derived[rid]
            if (r['ref_form'] == 'in_text' and not r['internal'] and r['in_requirement'] and
                    normativity != 'normative' and publicly_identified(r)):
                derived[rid] = (normativity, allowed, 'not_listed')
            elif r['ref_form'] == 'listed' and r['list_kind'] == 'normative' and rid not in used:
                derived[rid] = (normativity, allowed, 'never_cited')
    return derived


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
    require(isinstance(payload.get('document_identifier'), str),
            'document_identifier must be a string ("" when the document shows none)')
    require(payload.get('limitations') == [], 'Unresolved limitations prevent benchmark publication')
    english = payload['language'].lower() == 'en'
    covered = set()
    for region in payload['coverage']:
        require(region.get('reason', '').strip(), 'Coverage region needs review notes')
        region_lines = expand_spans(region['source_line_spans'], lines)
        require(not covered.intersection(region_lines), 'Coverage regions overlap')
        covered.update(region_lines)
    require(covered == lines.keys(), 'Coverage does not account for every source line')

    refs, rows, ids, identities = payload['references'], [], set(), set()
    for ref in refs:
        for field in TEXT_FIELDS:
            require(isinstance(ref.get(field), str), f'Missing/string field: {field}')
        rid = ref['ref_id']
        require(rid.strip() and rid not in ids, f'Empty or duplicate ref_id {rid!r}')
        ids.add(rid)
        for field in BOOL_FIELDS:
            require(type(ref.get(field)) is bool, f'{rid}: {field} must be boolean')
        spans = expand_spans(ref.get('source_line_spans'), lines)
        require(ref['cited_raw'].strip(), f'{rid}: empty cited_raw')
        joined = ''.join(lines[n]['content'] for n in sorted(spans))
        require(ref['cited_raw'] in joined, f'{rid}: cited_raw is not written in its source lines')

        # Labels from the governed vocabularies.
        require(ref['target_type'] in TARGET_SUBTYPES, f'{rid}: unknown target_type {ref["target_type"]!r}')
        subtype, label = ref['target_subtype'], ref['target_subtype_label']
        require(subtype in TARGET_SUBTYPES[ref['target_type']] or subtype == SUBTYPE_OTHERS,
                f'{rid}: {subtype!r} is not a governed subtype of {ref["target_type"]}; use others + label')
        require((subtype == SUBTYPE_OTHERS) == bool(label.strip()),
                f'{rid}: target_subtype_label is given exactly when target_subtype is others')
        require(ref['mechanism'] in MECHANISMS, f'{rid}: unknown mechanism {ref["mechanism"]!r}')
        rels = ref.get('relationships')
        string_list(rels, f'{rid}: relationships', True)
        require(set(rels) <= RELATIONSHIPS, f'{rid}: relationships outside the asserted vocabulary: '
                f'{sorted(set(rels) - RELATIONSHIPS)}')
        require(rels == sorted(set(rels)), f'{rid}: relationships must be sorted and unique')
        require(ref['target_scope'] in SCOPES, f'{rid}: unknown target_scope')
        require(ref['target_content'] in CONTENTS, f'{rid}: unknown target_content')

        # Form and internal references.
        listed = ref['ref_form'] == 'listed'
        require(ref['ref_form'] in ('listed', 'in_text'), f'{rid}: ref_form is listed or in_text')
        require(ref['list_kind'] in (('normative', 'informative') if listed else ('',)),
                f'{rid}: list_kind is normative/informative for listed entries, "" for in-text')
        require(listed or not ref['list_label'], f'{rid}: list_label is for listed entries')
        require(ref['internal'] == (ref['mechanism'] == 'structural_reference'),
                f'{rid}: internal exactly when mechanism is structural_reference')
        if listed:
            require(ref['target_content'] == 'general' and not ref['in_requirement'] and
                    not ref['internal'] and not ref['list_entry_ref_id'],
                    f'{rid}: a listed entry is general, not in a requirement, not internal, links no entry')
        if ref['internal']:
            require(ref['target_type'] == 'document' and
                    subtype in ('document_section', 'document_element'),
                    f'{rid}: an internal reference targets document/document_section|document_element')
            require(ref['target_content'] not in METRIC_CONTENTS,
                    f'{rid}: an internal reference is never criterion/criteria_set (rules §3.5)')
            require(ref['target_locator'].strip(), f'{rid}: an internal reference names the part it points at')
        check_identifiers(rid, ref.get('identifiers'))
        require(not (ref['internal'] or ref['mechanism'] == 'indirect_reference') or not ref['identifiers'],
                f'{rid}: internal and indirect references carry no identifiers')

        # The named quantity belongs to criterion rows only.
        criterion = ref['target_content'] == 'criterion'
        require(not criterion or (ref['metric_name'].strip() and ref['metric_subject'].strip()),
                f'{rid}: a criterion names its quantity (metric_name, metric_subject)')
        require(criterion or not any(ref[f].strip() for f in METRIC_FIELDS),
                f'{rid}: metric_name/metric_subject/condition are for criterion rows only')
        for field in EN_FIELDS:
            value = ref.get(field)
            require(value is None or isinstance(value, str), f'{rid}: invalid {field}')
            if english or not criterion:
                require(not value, f'{rid}: {field} is only for criterion rows of non-English documents')
            else:
                require(value and value.strip(), f'{rid}: {field} required on a non-English criterion row')

        confidence = ref.get('confidence')
        require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1,
                f'{rid}: invalid confidence')
        evidence = ref.get('evidence')
        require(isinstance(evidence, list) and evidence, f'{rid}: exact source evidence required')
        for excerpt in evidence:
            line = excerpt.get('line')
            require(type(line) is int and line in spans, f'{rid}: evidence line outside source spans')
            quote = excerpt.get('quote')
            require(isinstance(quote, str) and quote and quote in lines[line]['content'],
                    f'{rid}: evidence does not match source line {line}')
        table_rows = ref.get('source_table_rows', [])
        require(isinstance(table_rows, list), f'{rid}: source_table_rows must be an array')
        for tref in table_rows:
            require(type(tref.get('line')) is int and tref['line'] in spans and
                    lines[tref['line']]['type'] == 'table', f'{rid}: invalid source_table_rows line')
            string_list(tref.get('rows'), 'table row IDs', True)
            require(all(re.fullmatch(r'r[1-9][0-9]*', x) for x in tref['rows']), f'{rid}: invalid table row ID')

        identity = (tuple(sorted(spans)), norm_key(ref['cited_raw']), ref['list_entry_ref_id'],
                    norm_key(ref['target_locator']), ref['target_content'], norm_key(ref['metric_name']),
                    norm_key(ref['condition']), json.dumps(table_rows, sort_keys=True))
        require(identity not in identities, f'{rid}: duplicate reference (same occurrence, target and content)')
        identities.add(identity)

        notes = ref.get('annotation_notes', '')
        require(isinstance(notes, str), f'{rid}: annotation_notes must be a string')
        row = {key: ref[key] for key in TEXT_FIELDS + BOOL_FIELDS}
        row.update(source_line_spans=ref['source_line_spans'], source_table_rows=table_rows,
                   identifiers=ref['identifiers'], relationships=rels, confidence=confidence,
                   evidence=' '.join(e['quote'] for e in evidence),
                   input_record_id=record['id'], run_id=payload['run_id'],
                   source_filename=str(path), source_sha256=digest,
                   skill_name=payload['skill_name'], skill_version=payload['skill_version'],
                   model_name=payload['model_name'],
                   ext_info={'schema_version': '1', 'source': 'independent-benchmark', 'evidence': evidence})
        for field in EN_FIELDS:
            row[field] = ref.get(field) or None
        if notes:
            row['ext_info']['annotation_notes'] = notes
        rows.append(row)

    # List links, normativity and mismatches are derived from the rows, never asserted.
    by_id = {r['ref_id']: r for r in refs}
    for ref in refs:
        link = ref['list_entry_ref_id']
        require(not link or (link in by_id and by_id[link]['ref_form'] == 'listed'),
                f'{ref["ref_id"]}: list_entry_ref_id must name a listed reference')
    for rid, (normativity, allowed, mismatch) in derive_lists(refs).items():
        ref = by_id[rid]
        require(ref['list_entry_ref_id'] in allowed,
                f'{rid}: list_entry_ref_id {ref["list_entry_ref_id"]!r} should be one of {sorted(allowed)} '
                '(the listed entry of the same identity key or label; rules §3.6)')
        require(ref['normativity'] == normativity,
                f'{rid}: normativity {ref["normativity"]!r} should be {normativity!r} (from the lists only)')
        require(ref['list_mismatch'] == mismatch,
                f'{rid}: list_mismatch {ref["list_mismatch"]!r} should be {mismatch!r} (rules §3.6)')

    candidate_ids, linked = set(), set()
    for candidate in payload['candidates']:
        cid = candidate.get('candidate_id')
        require(isinstance(cid, str) and cid and cid not in candidate_ids, 'Invalid/duplicate candidate_id')
        candidate_ids.add(cid)
        require(candidate.get('reason', '').strip(), f'Candidate {cid}: decision needs rationale')
        expand_spans(candidate.get('source_line_spans'), lines)
        decision = candidate.get('decision')
        require(decision in ('accepted', 'excluded', 'duplicate'), f'Candidate {cid}: unresolved')
        rule = candidate.get('rule_id')
        require(rule in rules and rule.startswith(RULE_PREFIX[decision]),
                f'Candidate {cid}: rule_id must be a {RULE_PREFIX[decision]} rule of '
                f'rules {payload["skill_version"]}, got {rule!r}')
        targets = candidate.get('ref_ids', [])
        string_list(targets, f'Candidate {cid}: ref_ids', decision != 'excluded')
        require(set(targets) <= ids, f'Candidate {cid} references a missing ref_id')
        require(decision != 'excluded' or not targets, f'Excluded candidate {cid} references a reference')
        if decision == 'accepted':
            linked.update(targets)
    require(linked == ids, 'Every reference needs an accepted candidate')
    for row in rows:
        row['ext_info']['candidate_ids'] = sorted(
            c['candidate_id'] for c in payload['candidates'] if row['ref_id'] in c.get('ref_ids', []))
    return rows


def run_row(record, payload):
    """The run's testbed.reference_benchmark_runs row: its audit record, stored once per run.
    Call after validate, which checks every field used here."""
    metadata = record.get('doc_metadata') or {}
    return {key: payload[key] for key in ('skill_name', 'skill_version', 'model_name', 'run_id',
                                          'source_filename', 'source_sha256', 'rules_sha256', 'language',
                                          'document_identifier', 'coverage', 'candidates',
                                          'completeness_review', 'correctness_review')} | {
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
        'source_line_spans', 'source_table_rows', 'identifiers', 'relationships', 'confidence', 'evidence',
        'input_record_id', 'run_id', 'source_filename', 'source_sha256', 'skill_name', 'skill_version',
        'model_name', 'ext_info']
    columns = ', '.join(fields)
    run = run_row(record, payload)
    run_columns = ', '.join(run)
    identity = {key: record.get(key) for key in ('result_filename', 'staging_filename', 'parser_name')}
    run_key = ' AND '.join(f'{key} = {sql_text(payload[key])}' for key in
                           ('skill_name', 'skill_version', 'model_name', 'run_id'))
    # A run key is used once: the advisory lock serializes concurrent saves of the same key,
    # and the guard aborts if the run audit already exists, even with zero gold references.
    return f'''BEGIN;
SET LOCAL standard_conforming_strings = on;
SELECT id FROM kb.inputs WHERE id = {record['id']} FOR SHARE;
CREATE TEMP TABLE benchmark_input_guard (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_input_guard SELECT EXISTS (
 SELECT 1 FROM kb.inputs WHERE id = {record['id']}
 AND jsonb_build_object('result_filename', result_filename, 'staging_filename', staging_filename,
                        'parser_name', parser_name) = {sql_json(identity)});
SELECT pg_advisory_xact_lock(hashtextextended({sql_text('reference-benchmark ' + run_key)}, 0));
CREATE TEMP TABLE benchmark_run_key_unused (ok BOOLEAN NOT NULL CHECK (ok)) ON COMMIT DROP;
INSERT INTO benchmark_run_key_unused SELECT NOT EXISTS (
 SELECT 1 FROM testbed.reference_benchmark_runs WHERE {run_key});
INSERT INTO testbed.reference_benchmark_runs ({run_columns})
 SELECT {run_columns} FROM jsonb_populate_record(NULL::testbed.reference_benchmark_runs, {sql_json(run)});
INSERT INTO testbed.ref_mentions ({columns})
 SELECT {columns} FROM jsonb_populate_recordset(NULL::testbed.ref_mentions, {sql_json(rows)});
INSERT INTO testbed.ref_mentions_dropped
 (input_record_id, skill_name, skill_version, model_name, run_id, candidate_id,
  decision, drop_reason, candidate_data)
 SELECT r.input_record_id, r.skill_name, r.skill_version, r.model_name, r.run_id,
        c->>'candidate_id', c->>'decision', c->>'rule_id', c
 FROM testbed.reference_benchmark_runs r
 CROSS JOIN LATERAL jsonb_array_elements(r.candidates) c
 WHERE {run_key} AND c->>'decision' IN ('excluded', 'duplicate');
SELECT count(*) AS saved_references FROM testbed.ref_mentions WHERE {run_key};
SELECT count(*) AS saved_dropped FROM testbed.ref_mentions_dropped WHERE {run_key};
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
                      'model_name': payload['model_name'], 'references': len(rows),
                      'dropped': sum(c['decision'] in ('excluded', 'duplicate') for c in payload['candidates'])}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'benchmark_io: {exc}', file=sys.stderr)
        sys.exit(1)
