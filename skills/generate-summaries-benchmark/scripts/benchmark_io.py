#!/usr/bin/env python3
"""Prepare, validate and atomically persist source-backed gold chunk summaries."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SKILL = 'generate-summaries-benchmark'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def record_hash(record):
    return digest(json.dumps(record, sort_keys=True, ensure_ascii=False).encode())


def rules(version):
    manifest = json.loads((ROOT / 'rules/versions.json').read_text())
    require(version in manifest['versions'], 'Unknown rules version')
    item = manifest['versions'][version]
    require(digest((ROOT / 'rules' / item['rules']).read_bytes()) == item['sha256'],
            'Released rules have changed')
    return item['sha256']


def source_path(record):
    require(type(record.get('id')) is int and record['id'] > 0, 'Invalid kb.inputs.id')
    require(record.get('result_filename') and record.get('parser_name'), 'Missing source metadata')
    result = Path(record['result_filename'])
    if not result.is_absolute():
        require(os.environ.get('DATA_HOME_DIR'), 'DATA_HOME_DIR required')
        result = Path(os.environ['DATA_HOME_DIR']) / result
    stem = Path(record.get('staging_filename') or result.name).stem
    return (result.parent / f"{stem}_{record['parser_name']}.txt").resolve()


def load_source(record):
    path = source_path(record)
    raw = path.read_bytes()
    lines = {}
    previous = 0
    for index, text in enumerate(raw.decode('utf-8').split('\n'), 1):
        text = text.removesuffix('\r')
        if not text.strip():
            continue
        fields = text.split('\t')
        require(len(fields) == 7, f'Record {index}: expected seven TAB fields')
        number, page, kind, font, size, box, content = fields
        require(re.fullmatch(r'[1-9][0-9]*', number) and re.fullmatch(r'[1-9][0-9]*', page),
                f'Record {index}: invalid line/page')
        number, page, size = int(number), int(page), float(size)
        box = json.loads(box)
        require(number > previous and kind.strip() and font.strip(), f'Record {index}: invalid order/type/font')
        require(math.isfinite(size) and size > 0, f'Record {index}: invalid font size')
        require(isinstance(box, list) and len(box) == 4 and
                all(type(x) in (int, float) and math.isfinite(x) for x in box),
                f'Record {index}: invalid box')
        lines[number] = {'line': number, 'page': page, 'type': kind, 'content': content}
        previous = number
    require(lines, 'Empty line file')
    return path, digest(raw), lines


def expand(text):
    require(text.startswith('[') and text.endswith(']'), 'Expected bracketed chunk ranges')
    result = []
    for part in text[1:-1].split(','):
        part = part.strip()
        if not part and text == '[]':
            break
        require(re.fullmatch(r'[1-9][0-9]*(?:-[1-9][0-9]*)?', part), 'Invalid chunk range')
        bounds = [int(n) for n in part.split('-')]
        require(bounds[0] <= bounds[-1] and bounds[-1] - bounds[0] < 1000000, 'Invalid chunk bounds')
        result.extend(range(bounds[0], bounds[-1] + 1))
    require(result == sorted(set(result)), 'Unordered or duplicate chunk lines')
    return result


def load_chunks(path, lines):
    raw = Path(path).read_bytes()
    entries = [text.strip() for text in raw.decode('utf-8').splitlines() if text.strip()]
    require(entries and len(entries) % 2 == 0, 'Expected overlap/lines pairs')
    chunks, seen = [], []
    previous_full = []
    for i in range(0, len(entries), 2):
        require(entries[i].startswith('overlap:') and entries[i + 1].startswith('lines:'),
                'Expected overlap then lines')
        overlap = expand(entries[i].split(':', 1)[1].strip())
        regular = expand(entries[i + 1].split(':', 1)[1].strip())
        require(regular, 'Empty regular chunk')
        full = overlap + regular
        require(full == sorted(set(full)), 'Invalid overlap ordering')
        require(set(full) <= lines.keys(), 'Stale chunk: absent source line')
        require(all(lines[n]['type'].lower() != 'toc' for n in full), 'Stale chunk: TOC reference')
        require(not overlap or overlap == previous_full[-len(overlap):], 'Invalid carried overlap')
        seen.extend(regular)
        chunks.append({'summary_seq_no': len(chunks) + 1, 'overlap_lines': overlap,
                       'regular_lines': regular, 'source_line_spans': [str(n) for n in full]})
        previous_full = full
    expected = [n for n, line in lines.items() if line['type'].lower() != 'toc']
    require(seen == expected, 'Missing, repeated or reordered regular source coverage')
    return digest(raw), chunks


def default_chunks(record):
    require(os.environ.get('ARTIFACT_DIR'), 'ARTIFACT_DIR or --chunks required')
    source = source_path(record)
    return Path(os.environ['ARTIFACT_DIR']) / str(record['id'] // 1000) / str(record['id']) / (source.stem + '.chunks')


def prepare(record, chunks_path, model, version='1.0.0', budget=600):
    require(isinstance(model, str) and model.strip(), 'Invoking model identity required')
    require(type(budget) is int and budget > 0, 'Positive budget required')
    path, source_sha, lines = load_source(record)
    chunk_sha, chunks = load_chunks(chunks_path, lines)
    for chunk in chunks:
        chunk.update(language='', summary_text='', summary_text_en='', keywords=[], keywords_en=[],
                     units=[], empty_reason='', completeness_review={}, correctness_review={})
    payload = dict(record_id=record['id'], run_id=datetime.now().strftime('%Y%m%d_%H%M%S'),
                   skill_name=SKILL, skill_version=version, rules_sha256=rules(version), model_name=model,
                   record_sha256=record_hash(record), source_filename=str(path), source_sha256=source_sha,
                   chunks_filename=str(Path(chunks_path).resolve()), chunks_sha256=chunk_sha,
                   budget_chars=budget, review_mode='', limitations=[], blocking_issues=[], summaries=chunks)
    exported = [{**c, 'lines': [lines[int(n)] for n in c['source_line_spans']]} for c in chunks]
    return payload, exported


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(record, payload):
    require(payload['record_id'] == record['id'] and payload['record_sha256'] == record_hash(record),
            'Input record changed')
    require(payload['skill_name'] == SKILL and payload['rules_sha256'] == rules(payload['skill_version']),
            'Rules identity mismatch')
    require(nonempty(payload['model_name']) and re.fullmatch(r'[0-9]{8}_[0-9]{6}', payload['run_id']),
            'Invalid model/run identity')
    datetime.strptime(payload['run_id'], '%Y%m%d_%H%M%S')
    path, sha, lines = load_source(record)
    require(str(path) == payload['source_filename'] and sha == payload['source_sha256'], 'Source changed')
    sha, chunks = load_chunks(payload['chunks_filename'], lines)
    require(sha == payload['chunks_sha256'], 'Chunks changed')
    require(type(payload['budget_chars']) is int and payload['budget_chars'] > 0, 'Invalid budget')
    require(payload['review_mode'] in ('independent', 'self'), 'Review mode required')
    require(isinstance(payload['limitations'], list) and all(nonempty(x) for x in payload['limitations']),
            'Invalid limitations')
    require(payload['blocking_issues'] == [], 'Unresolved blocking issues')
    summaries = payload['summaries']
    require(len(summaries) == len(chunks), 'One summary per chunk required')
    for summary, chunk in zip(summaries, chunks):
        require(all(summary[k] == v for k, v in chunk.items()), 'Chunk identity/coverage changed')
        require(nonempty(summary['language']), 'Language required')
        for field in ('summary_text', 'summary_text_en', 'empty_reason'):
            require(isinstance(summary[field], str), f'Invalid {field}')
        for field in ('keywords', 'keywords_en'):
            require(isinstance(summary[field], list) and all(nonempty(x) for x in summary[field]),
                    f'Invalid {field}')
        for field in ('completeness_review', 'correctness_review'):
            review = summary[field]
            require(isinstance(review, dict) and nonempty(review.get('reviewer')) and nonempty(review.get('notes')),
                    'Concrete reviews required')
            if payload['review_mode'] == 'independent':
                require(review['reviewer'] != payload['model_name'], 'Reviewer must differ from author')
        require(isinstance(summary['units'], list), 'Units must be an array')
        full = {int(n) for n in chunk['source_line_spans']}
        if summary['empty_reason'].strip():
            require(not any(summary[k] for k in ('summary_text', 'summary_text_en', 'keywords', 'keywords_en', 'units')),
                    'Empty chunk contains summary content')
            # Image placeholders are reviewed semantically; visible prose is never auto-discarded.
            require(all(not lines[n]['content'].strip() or
                        (lines[n]['type'].strip().lower() == 'image' and
                         (lines[n]['content'].strip().lower() in ('[image]', '<image>') or
                          re.fullmatch(r'!\[\]\([^\n]+\)', lines[n]['content'].strip()))) for n in full),
                    'Readable chunk cannot be marked empty')
            continue
        require(nonempty(summary['summary_text']) and summary['units'] and summary['keywords'],
                'Readable chunk needs summary, units and keywords')
        require(sum(not c.isspace() for c in summary['summary_text']) <= payload['budget_chars'],
                'Summary exceeds budget')
        if summary['language'] == 'en':
            require(summary['summary_text_en'] == '' and summary['keywords_en'] == [], 'English translation must be empty')
        else:
            require(nonempty(summary['summary_text_en']) and summary['keywords_en'], 'English translation required')
        ids, included = set(), 0
        for unit in summary['units']:
            require(nonempty(unit['id']) and unit['id'] not in ids and nonempty(unit['claim']), 'Invalid unit ID/claim')
            ids.add(unit['id'])
            require(type(unit['weight']) is int and unit['weight'] in (1, 2, 3), 'Invalid importance')
            require(type(unit['critical']) is bool and type(unit['included']) is bool, 'Invalid unit flags')
            require(isinstance(unit['omission_reason'], str), 'Omission reason must be text')
            require(unit['included'] or (not unit['critical'] and nonempty(unit['omission_reason'])),
                    'Critical unit omitted or omission unexplained')
            included += unit['included']
            require(isinstance(unit['evidence'], list) and unit['evidence'], 'Evidence required')
            for span in unit['evidence']:
                n, start, end = span['line'], span['start'], span['end']
                require(type(n) is int and n in full and type(start) is int and type(end) is int,
                        'Invalid evidence coordinates')
                text = lines[n]['content']
                require(0 <= start < end <= len(text) and text[start:end] == span['quote'], 'Evidence mismatch')
        require(included, 'Summary needs an included unit')
    return payload


def psql(sql):
    result = subprocess.run(['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1'],
                            input=sql, text=True, capture_output=True)
    # Avoid reflecting connection diagnostics/credentials into transcripts.
    require(result.returncode == 0, 'PostgreSQL operation failed; inspect connection/schema privately')
    return result.stdout.strip()


def sql_text(value):
    return "'" + value.replace("'", "''") + "'"


def key_where(payload):
    return ' AND '.join(f'{k} = {sql_text(payload[k])}' for k in
                        ('skill_name', 'skill_version', 'model_name', 'run_id'))


def record_query(record_id, lock=False):
    require(type(record_id) is int and record_id > 0, 'Invalid record ID')
    return ("SELECT jsonb_build_object('id', id, 'result_filename', result_filename, "
            "'staging_filename', staging_filename, 'parser_name', parser_name, "
            "'title', title, 'doc_no', doc_no, 'doc_metadata', doc_metadata) "
            f"FROM kb.inputs WHERE id = {record_id}" + (' FOR UPDATE' if lock else '') + ';')


def save(record, payload):
    validate(record, payload)
    # Keep the row lock alive while checking current DB metadata and filesystem fingerprints.
    process = subprocess.Popen(['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        process.stdin.write('BEGIN;\n' + record_query(record['id'], lock=True) + '\n\\echo __LOCKED__\n')
        process.stdin.flush()
        output = []
        for line in process.stdout:
            if line.strip() == '__LOCKED__':
                break
            if line.strip():
                output.append(line)
        require(output, 'Input row unavailable')
        current = json.loads(''.join(output))
        validate(current, payload)
        encoded = sql_text(json.dumps(payload, ensure_ascii=False))
        # Fixed table/column names; JSON values use SQL standard string quoting.
        sql = f"SET LOCAL standard_conforming_strings = on;\nINSERT INTO testbed.summary_benchmark_runs "
        sql += '(skill_name, skill_version, model_name, run_id, input_record_id, payload) '
        sql += f"SELECT p->>'skill_name', p->>'skill_version', p->>'model_name', p->>'run_id', (p->>'record_id')::bigint, p FROM (SELECT {encoded}::jsonb p) q;\n"
        sql += 'INSERT INTO testbed.summaries (skill_name, skill_version, model_name, run_id, input_record_id, summary_seq_no, summary_id, summary_level, source_line_spans, overlap_lines, regular_lines, summary_text, summary_text_en, language, keywords, keywords_en, units, empty_reason, completeness_review, correctness_review) '
        sql += "SELECT r.skill_name, r.skill_version, r.model_name, r.run_id, r.input_record_id, (s->>'summary_seq_no')::int, r.input_record_id::text || '_sum_0_' || lpad(s->>'summary_seq_no', greatest(4, length(s->>'summary_seq_no')), '0'), 0, s->'source_line_spans', s->'overlap_lines', s->'regular_lines', s->>'summary_text', s->>'summary_text_en', s->>'language', s->'keywords', s->'keywords_en', s->'units', s->>'empty_reason', s->'completeness_review', s->'correctness_review' FROM testbed.summary_benchmark_runs r CROSS JOIN LATERAL jsonb_array_elements(r.payload->'summaries') s WHERE "
        sql += key_where(payload) + ';\nCOMMIT;\n'
        process.stdin.write(sql)
        process.stdin.close()
        process.stdout.read()
        require(process.wait(timeout=60) == 0, 'Save failed; check readback before retrying')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def readback(payload):
    where = key_where(payload)
    run = psql(f'SELECT payload FROM testbed.summary_benchmark_runs WHERE {where};')
    require(run and json.loads(run) == payload, 'Saved run missing or differs')
    raw = psql(f"SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY summary_seq_no), '[]'::jsonb) FROM testbed.summaries s WHERE {where};")
    rows = json.loads(raw)
    require(len(rows) == len(payload['summaries']), 'Readback count mismatch')
    for row, summary in zip(rows, payload['summaries']):
        require(all(row.get(k) == v for k, v in summary.items()), 'Saved summary differs')
        require(row['input_record_id'] == payload['record_id'] and row['summary_level'] == 0,
                'Saved summary identity differs')
        require(row['summary_id'] == f"{payload['record_id']}_sum_0_{summary['summary_seq_no']:04d}",
                'Saved summary ID differs')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'validate', 'save', 'readback'):
        sub = subs.add_parser(command)
        if command != 'readback':
            sub.add_argument('--record', required=True)
        if command == 'prepare':
            sub.add_argument('--chunks')
            sub.add_argument('--line-file')
            sub.add_argument('--model-name', required=True)
            sub.add_argument('--skill-version', default='1.0.0')
            sub.add_argument('--budget-chars', type=int, default=600)
            sub.add_argument('--output', required=True)
        else:
            sub.add_argument('--payload', required=True)
    args = parser.parse_args()
    try:
        if args.command != 'readback':
            record = json.loads(Path(args.record).read_text())
        if args.command == 'prepare':
            if args.line_file:
                require(Path(args.line_file).resolve() == source_path(record), 'Filename does not match input record')
            payload, source = prepare(record, args.chunks or default_chunks(record), args.model_name,
                                      args.skill_version, args.budget_chars)
            with open(args.output, 'x', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
            print(json.dumps(source, ensure_ascii=False, indent=2))
        else:
            payload = json.loads(Path(args.payload).read_text())
            if args.command == 'readback':
                rows = readback(payload)
                print(json.dumps({'verified_rows': len(rows), 'run_id': payload['run_id']}))
            else:
                validate(record, payload)
                if args.command == 'save':
                    save(record, payload)
                print(json.dumps({'status': args.command, 'summaries': len(payload['summaries'])}))
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
