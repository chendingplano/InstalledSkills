---
name: generate-summaries-benchmark
description: Build independently reviewed gold summaries for every leaf chunk of a kb.inputs document's canonical line file and save versioned, source-backed snapshots to testbed.summaries. Use for gold summaries, ground truth or summary benchmarks; production summarization and scoring are separate workflows.
disable-model-invocation: true
---

# Generate Summaries Benchmark

Create one gold summary per original chunk of one document. Accept a positive `record_id` (`kb.inputs.id`), a line filename tied to that record, or both. Resolve an unambiguous record when only a filename is supplied; never guess from a basename. Creating this skill does not require running it on a document.

`Use $generate-summaries-benchmark for document 416` authorizes preparation, independent annotation, review, validation, saving and read-back. Honor explicit draft-only/no-save instructions. Do not invoke `generate_summaries` or `extract_summaries`, inspect production summaries, or use candidate summaries as gold. Do not modify the frozen offline dataset under `ChenWeb/benchmark/summaries/`.

## Prepare

1. Read `ChenWeb/CLAUDE.md`, `ChenWeb/KnowledgeStore/doc-repo/devdocs/202610/2026102101-devdoc-summary.md`, and `ChenWeb/KnowledgeStore/Capsules/coding-capsules/{input-management,chunking}/+CAPSULE.md` plus `doc-processor/generate-summary-spec.md` under that same capsules directory. The canonical line spec is `KnowledgeStore/doc-repo/specs/202604/2026042101-spec-line-file.md`; the capsule's old line-spec link is stale. Current summary spec requires level 0 only, even where older overview text describes parent rollups.
2. Read [the storage and command contract](references/contract.md) and the selected [rules](rules/1.0.0.md). Default to released version `1.0.0`; report it. Released rules are frozen and SHA-256 checked by the helper. New annotation behavior requires a new version and digest in `rules/versions.json`, retaining old versions.
3. Export the exact input record using the configured project PostgreSQL connection. Resolve its working canonical `.txt` through `docprocessing.ResolveInputFilePath`; `.origin` is not the working file. When the user supplies a filename, verify its resolved path equals the record's canonical path.
4. Reuse the finalized `.chunks` artifact for this document; resolve it from `ARTIFACT_DIR/<id/1000>/<id>/<staging stem>_<parser>.chunks`. The helper accepts an explicit `--chunks` path. If missing, do not improvise fixed-line chunks: report the prerequisite and use the project's chunking operation only when authorized. Missing DB access can leave a local draft but cannot produce a saved benchmark.
5. Run `prepare` with the invoking model identity and output budget. Default budget is **600 non-whitespace Unicode code points per source-language summary**, an explicit benchmark convention, not a production default. Use a caller-specified budget when supplied, and retain it across compared candidates. Obtain model identity from runtime or active-session model metadata; if only a label is exposed, use it and record that limitation. Never ask the user to choose the invoking model.

The helper validates strict seven-TAB-field lines and ordered chunk references, fingerprints source/chunks/record, and exports every chunk's full input. Read that export completely in bounded portions. `lines:` defines regular payload and sequence; `overlap:` supplies preceding context, never another chunk. Like generated leaf summaries, each gold summary covers both sets. The helper rejects stale IDs, TOC references, duplicate regular coverage, missing non-TOC lines and invalid overlap. Investigate numbering gaps and parser damage without silently reparsing or renumbering.

## Author and review

For each chunk, inventory source-backed information units before drafting, following the rules file. Give each unit exact evidence spans, importance and criticality, and an explicit included/omitted decision. Draft a readable source-language synthesis within budget, English translation for non-English chunks, and keywords. Keep full input coverage (`source_line_spans`) distinct from evidence supporting the summary's claims.

Read all source lines, including late lines, table headings, footnotes, exceptions and carried context. An overlap-only fact may explain the regular payload; avoid letting it displace that payload. No sentence may acquire an unsupported quantity, obligation or scope. An image-only or content-free chunk still gets a row with an empty summary and a reason; never skip it.

Review completeness and correctness independently of the author where delegation is available: give reviewers source, units and drafts without production predictions. Completeness checks every chunk and important omission; correctness checks every claim, evidence, qualifier, negation, unit, table frame and translation. Revise and re-review substantive changes. Record actual reviewer identities and concrete findings, not a claim of human approval. If independent review is unavailable, perform separate passes, mark `review_mode = self`, and disclose that limitation. Unresolved critical evidence or material parser ambiguity blocks publishing; retain a draft and report the exact issue.

## Validate, save and report

Run the helper's `validate`, then `save`, then `readback`. Save inserts the complete run and all summaries atomically into `testbed.summary_benchmark_runs` and `testbed.summaries`; append a fresh snapshot on reruns. The save command rechecks the current DB input record and both files under the input-row lock. It never changes production summaries, processor status, embeddings or search indexes. Following ambiguous connection failure, read back the same run before retrying; never switch IDs just to bypass duplicate protection.

Compare read-back to the validated payload, including every row, summary, evidence, review and hash. Mechanical validation checks structure and traceability; semantic faithfulness still depends on review. Report record ID, run ID, skill version, model, budget, chunk count, review mode and limitations. If persistence is pending, say so explicitly. Do not report generation or saving for any document when only installing this skill.
