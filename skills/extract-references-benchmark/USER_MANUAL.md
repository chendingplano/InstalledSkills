# Extract References Benchmark — User Manual

| Field | Value |
|---|---|
| title | Extract References Benchmark — User Manual |
| language | en |
| format | markdown |
| version | 1.0 |
| status | Draft |
| author | Not specified |
| owner | Not specified |
| audience | People who run or review gold-reference benchmarks through a coding assistant; no programming needed |
| create-time | 2026-10-11T12:00:00-05:00 |
| last-modify-time | 2026-10-11T12:00:00-05:00 |
| keywords | gold references, benchmark, ground truth, extract_references, citations, normative references, testbed.ref_mentions, rules version, Claude Code, Codex |

This manual has its own version number (1.0), separate from the skill's rules versions listed under
[Available versions](#5-available-versions).

## 1. What this skill is

Documents point at other documents all the time: a standard requires compliance with another
standard, a paper cites earlier papers, a clause says "see Table 1". The production system finds
these **references** automatically (`extract_references`). To know how good that is, you need an
answer key: a carefully checked list of every reference a document really makes, with the right
labels. These are called **gold references**.

This skill builds that answer key for one document. Your coding assistant reads the whole document
line by line, finds every reference (citations in the text, entries of reference lists, and
pointers to other parts of the same document), labels each one, checks its own work twice (once for
anything missed, once for mistakes), and saves the result.

- **Who it is for:** anyone who wants to measure or improve reference extraction.
- **When to use it:** when a document needs an answer key for references.
- **What it does not do:** it never changes production data. Results go to a separate test area
  (`testbed.ref_mentions`), not to the production reference tables.

It works like the metrics benchmark skill (`extract-metrics-benchmark`), but for references.

## 2. Key ideas

- **Document ID:** every document has a number (its `kb.inputs.id`, for example `753`). You always
  give the skill one document ID.
- **Run:** each answer key is saved as a separate snapshot, a run, identified by the date and time it
  started (for example `20261011_143005`). Runs are never overwritten.
- **Rules version:** the rules for what counts as a reference and how to label it are numbered
  (1.0.0, …). A released version never changes. Every run records the version it used.
- **Model:** each run records which AI model did the work.
- **What each reference records:** what is cited (a standard, a law, a paper, a web page, a table of
  this document…), how it is written (a standard number, `[12]`, a URL, "see 5.2"), what the
  document takes from it (a limit for one quantity, a set of limits, a test method, term
  definitions, a body of requirements, data, or nothing specific), whether it sits inside a
  requirement ("shall"), and whether the cited document is a formal normative reference.

## 3. Before you start

Check that:

- you are working in this workspace (`/Users/cding/Workspace`);
- the ChenWeb database is reachable (the assistant uses the settings in `ChenWeb/.env`);
- you know the document ID;
- the document's source text exists. If the assistant reports that `DATA_HOME_DIR` is missing, tell it
  where document data lives.

## 4. Using the skill in a coding assistant

### 4.1 Claude Code

Type the skill name as a slash command, followed by your request:

`/extract-references-benchmark document 753`, or
`/extract-references-benchmark build the gold references for document 753, version 1.0.0`

The skill does not start by itself; ask for it by name.

### 4.2 Codex

`Use $extract-references-benchmark for kb.inputs.id 753, version 1.0.0`

### 4.3 Other coding assistants

*"Read `.agents/skills/extract-references-benchmark/SKILL.md` and follow it to build the gold
references for document 753."*

### 4.4 What to expect

- **It takes a while.** The assistant reads every line and audits its work.
- **It saves without asking again.** A request for a document includes saving and checking the saved
  result. Say "draft only" or "do not save" if you only want local files.
- **It reports back** with the document ID, run ID, rules version, model, and the number of
  references saved (list entries, citations in the text, internal pointers), plus anything it could
  not resolve.
- **It may stop and ask** when something blocks a complete answer key: the database is unreachable,
  the source text is damaged, or a passage is genuinely ambiguous. It never saves a partial answer
  key as if it were complete.
- **Where to see results:** there is no page for gold references yet. Ask the assistant to show a run,
  or query `testbed.ref_mentions`.

### 4.5 Example requests

| You want to… | Ask |
|---|---|
| Build an answer key with the newest rules | "Build the gold references for document 753." |
| Use a specific rules version | "Build the gold references for document 753 using version 1.0.0." |
| Score the automatic extraction (`score-extract-references` skill) | "Use $score-extract-references for document 753." |
| Review a saved result | "Show me gold reference 753_gref_12 and check whether its labels are right." |

## 5. Available versions

The list of record is `rules/versions.json` in the skill directory.

| Version | Rules file | Released | Notes |
|---|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | 2026-10-11 | First release. Follows the reference model of `extract_references` (devdoc 2026101002). Counts citations in the text, reference-list entries, pointers to other parts of the document, and unnamed pointers to one specific document ("the manufacturer's instructions"). Leaves out the table of contents, the document's own number, who drafted it, vague "relevant regulations", and people or organizations that are only part of the content. Pointers to this document's own tables never count as borrowing a limit. |

If you don't name a version, the newest released version is used.

## 6. Limits

- **One document per run.**
- **Old answer keys stay as they were.** If the rules change, run the document again with the new
  version.
- **Answer keys are judgments.** The tool checks the format and recomputes which references are
  normative, but whether every reference was found, and whether "borrows a limit" versus "uses a
  method" was decided right, rests on the assistant's review.
- **Only what the document says.** The skill does not check what the cited documents contain or
  whether the user holds a copy of them; that is the resolution step of `extract_references`, not part
  of this answer key.

## 7. Further reading

- How the skill works, for maintainers: `SKILL.md` and `references/benchmark-contract.md`.
- History of rule and tooling changes: `CHANGELOG.md`.
- The reference model: `KnowledgeStore/doc-repo/devdocs/202610/2026101002-devdoc-extract-references-processor.md`.

## 8. Change Log

| Version | Timestamp | Author | Reason | Summary |
|---|---|---|---|---|
| 1.0 | 2026-10-11T12:00:00-05:00 | Not specified (drafted by Claude Code) | New skill | First edition: purpose, key ideas, use in Claude Code, Codex and other assistants, rules version 1.0.0, limits. |
