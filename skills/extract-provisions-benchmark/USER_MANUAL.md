# Extract Provisions Benchmark — User Manual

| Field | Value |
|---|---|
| title | Extract Provisions Benchmark — User Manual |
| language | en |
| format | markdown |
| version | 1.0 |
| status | Draft |
| author | Not specified |
| owner | Not specified |
| audience | People who run or review gold-provision benchmarks through a coding assistant; no programming needed |
| create-time | 2026-11-06T12:00:00-06:00 |
| last-modify-time | 2026-11-06T12:00:00-06:00 |
| keywords | gold provisions, benchmark, ground truth, extract_provisions, requirements, normative statements, testbed.provisions, rules version, Claude Code, Codex |

This manual has its own version number (1.0). The skill's rules versions are numbered separately
and listed under [Available versions](#5-available-versions).

## 1. What this skill is

Standards, regulations and contracts are full of **provisions**: statements that say what must,
should, may or must not be done. The production system finds these automatically, using the
processor `extract_provisions`. To know how good it is, you need an answer key: a carefully
checked list of every provision the document really makes, each with the right labels. These are
the **gold provisions**.

This skill builds that answer key for one document. Your coding assistant:

1. reads the whole document line by line;
2. finds every provision, including requirements, prohibitions, test-method steps,
   recommendations and permissions;
3. labels each one;
4. checks its own work twice: once for anything missed, once for mistakes;
5. saves the result.

- **Who it is for:** anyone who wants to measure or improve provision extraction.
- **When to use it:** when a document needs an answer key for provisions.
- **What it does not do:** it never changes production data. Results go to a separate test area
  (`testbed.provisions`), not to the production table `kb.provisions`.

It works like the metrics and references benchmark skills, but for provisions.

## 2. Key ideas

- **Document ID:** every document has a number, its `kb.inputs.id` (for example `416`). You always
  give the skill one document ID.
- **Run:** each answer key is saved as a separate snapshot, called a run. A run is identified by
  the date and time it started (for example `20261106_143005`). Runs are never overwritten.
- **Rules version:** the rules for what counts as a provision and how to label it are numbered
  (1.0.0, …). A released version never changes, and every run records the version it used.
- **Model:** each run records which AI model did the work.
- **One provision = one normative statement:** usually one sentence. A sentence is split only when
  its strength changes (must → may) or when it binds a different party or object.
- **What each provision records:**
  - its exact text and source lines;
  - its strength: mandatory, recommended or optional;
  - its kind: requirement, prohibition, instruction, recommendation or permission;
  - who or what it binds (the subject);
  - where it sits: sentence, list item, paragraph, table cell, …;
  - whether it is stated explicitly (with 应 / shall / 宜 / 可 …) or only implied by the section
    it is in.

## 3. Before you start

Check that:

- you are working in this workspace (`/Users/cding/Workspace`);
- the ChenWeb database is reachable (the assistant uses the settings in `ChenWeb/.env` or
  `mise env`);
- the document has been parsed, so its line file exists.

## 4. How to run it

Ask your assistant:

> Use $extract-provisions-benchmark for document 416

or, for a specific rules version:

> Use $extract-provisions-benchmark, version 1.0.0 for document 416

The assistant reads the document, builds the answer key, checks it, saves it and reads it back.
It then reports the run ID, how many provisions it saved (by strength and kind), and any doubts.
You can view the result in ChenWeb under System Admin › Benchmark › Provisions › Gold Provisions.
To score the production extraction against it, use System Admin › Benchmark › Provisions ›
Benchmark, or the `score-extract-provisions` skill.

## 5. Available versions

| Version | Released | What it is |
|---|---|---|
| 1.0.0 | 2026-11-06 | First release. Test-method steps count as provisions; one provision per normative statement. |

## 6. Change Log

| Manual version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-06 | First version. |
