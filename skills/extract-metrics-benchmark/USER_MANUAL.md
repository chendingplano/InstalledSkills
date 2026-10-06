# Extract Metrics Benchmark — User Manual

| Field | Value |
|---|---|
| title | Extract Metrics Benchmark — User Manual |
| language | en |
| format | markdown |
| version | 1.3 |
| status | Draft |
| author | Not specified |
| owner | Not specified |
| audience | People who run or review gold-metric benchmarks through a coding assistant; no programming needed |
| create-time | 2026-10-06T08:30:04-05:00 |
| last-modify-time | 2026-10-07T05:30:00-05:00 |
| keywords | gold metrics, benchmark, ground truth, extract_metrics, metric extraction quality, testbed.metrics, skill version, rules version, Claude Code, Codex, compare versions |

This manual has its own version number (1.3), which is separate from the skill's rules versions listed
under [Available versions](#available-versions).

## 1. What this skill is

The production system reads documents (standards, specifications, regulations) and automatically
pulls out their **metrics**: measurable items such as limits, targets, rates and test conditions.
To know how good that automatic extraction (`extract_metrics`) is, you need an answer key: a carefully
checked list of the metrics a document really contains. These are called **gold metrics**.

This skill builds that answer key for one document. Your coding assistant reads the entire document
line by line, decides what is and isn't a metric, checks its own work twice (once for anything missed,
once for mistakes), and saves the result.

- **Who it is for:** anyone who wants to measure or improve metric extraction quality.
- **When to use it:** when a document needs an answer key, or when you want to see how a change to
  the annotation rules affects the answer key.
- **What it does not do:** it never changes production data. Results go to a separate test area
  (`testbed.metrics`), not to the production metrics table.

## 2. Key ideas

- **Document ID:** every document in the system has a number (its `kb.inputs.id`, for example `416`).
  You always give the skill one document ID.
- **Run:** each time the skill builds an answer key, the result is saved as a new, separate snapshot
  called a run, with its own run ID: the date and time the run started, such as `20261006_085331`
  (6 October 2026, 08:53:31). Runs are never overwritten. Running the same document twice gives two
  runs side by side.
- **Rules version:** the rules for deciding what counts as a metric are written down and numbered
  (1.0.0, 2.0.0, …). Once released, a version never changes, so any version can be run again later
  with exactly the same rules. Every run records the rules version it used.
- **Model:** each run also records which AI model did the work (for example `claude-opus-5-5` or
  `gpt-6.1-sol`), because different models can make different judgments under the same rules.

## 3. Before you start

Check that:

- you are working in this workspace (`/Users/cding/Workspace`), where the skill is installed;
- the ChenWeb database is reachable (the assistant uses the connection settings in `ChenWeb/.env`);
- you know the document ID;
- the document's source text exists. If the assistant reports that `DATA_HOME_DIR` is missing, tell it
  where document data lives (on this machine it has been `/Users/cding/Apps/SemOS`; please confirm for
  your setup).

## 4. Using the skill in a coding assistant

You don't type commands. You ask the assistant in plain words, and it follows the skill.

### 4.1 Claude Code

The skill is available to Claude Code in this workspace and in your user settings. Either:

- type the skill name as a slash command, followed by your request:
  `/extract-metrics-benchmark document 416, version <version>`, or 
  `/extract-metrics-benchmark build the gold metrics for document 416, version <version>`
- or simply ask: *"Build the gold metrics for document 416."* Claude Code recognises the request and
  loads the skill itself.

### 4.2 Codex

The skill is installed for Codex as well. Mention it with a `$` sign:

`Use $extract-metrics-benchmark for kb.inputs.id 416, version <version>`, or

`Use $extract-metrics-benchmark to extract and audit metrics for kb.inputs.id 416, version <version> 
and save the benchmark to testbed.metrics.`

### 4.3 Other coding assistants

Any assistant that can read files and run commands in this workspace can follow the skill. Point it to
the instructions file explicitly:

*"Read `.agents/skills/extract-metrics-benchmark/SKILL.md` and follow it to build the gold metrics for
document 416."*

### 4.4 Example requests

| You want to… | Ask |
|---|---|
| Build an answer key with the newest rules | "Build the gold metrics for document 416." |
| Use a specific rules version | "Build the gold metrics for document 416 using skill version 1.0.0." |
| Compare two rules versions | "Run the benchmark for document 416 with versions 1.0.0 and 2.0.0, then compare the two runs." |
| See which versions exist | "Which versions of extract-metrics-benchmark are available?" |
| Review a saved result | "Show me gold metric 416_gold_5 and check whether it is really a metric." |

### 4.5 What to expect

- **It takes a while.** The assistant reads every line of the document and audits its work, so a run
  takes much longer than an automatic extraction.
- **It reports back** with the document ID, run ID, rules version, model, and number of metrics saved,
  plus anything it could not resolve.
- **It may stop and ask** when something blocks a complete answer key: the database is unreachable,
  the source text is damaged, or a passage is genuinely ambiguous. It will not save a partial or
  uncertain answer key as if it were complete.
- **Where to see results:** in ChenWeb, open **/development → LLM → Metrics → Gold Metrics**. Above
  the document list, pick a **Skill version** (the newest is chosen for you) and a **Model name** (you
  must choose one; the page asks you to). The document list shows only documents that have gold
  metrics for that version (and model, once chosen), and the page shows the latest run of that version
  and model for the document you select.

## 5. Available versions

The skill currently has these rules versions. The list of record is
`rules/versions.json` in the skill directory; ask the assistant to read it if this table may be out of
date.

| Version | Rules file | Released | Notes |
|---|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | 2026-10-06 | The original rules. A review of document 416 found that roughly half of its gold metrics are not real metrics; see the review report below. |
| 1.1.0 | `rules/1.0.0.md` | 2026-10-06 | Same rules as 1.0.0. Exists only because a run was saved under this label. |
| 1.2.0 | `rules/1.0.0.md` | 2026-10-06 | Same rules as 1.0.0. Exists only because of an earlier labelling step. |
| 2.0.0 | `rules/2.0.0.md` | 2026-10-06 | Corrected rules from the review report. A metric must name an object, a property you can measure or inspect, and a value or concrete criterion. Instructions to people, duties, plans, slogans, licences and "tidy"-type wording are no longer metrics. Expect about half as many gold metrics as 1.x. Each decision records the rule that made it. |
| 2.1.0 | `rules/2.1.0.md` | 2026-10-07 | Same choice of what counts as a metric as 2.0.0. Each gold metric now also says what it is to an expert: a requirement (with a number, with the value set elsewhere, inspection-only, or pointing to another standard), a metric value, a test setting or a definition. These are the same labels the ChenWeb pages show, so you can score requirements and metrics separately. It also fixes how a few things are written down (interpretation thresholds, conditions, measurement basis, "daily" schedules, standard numbers). |

**If you don't name a version, the newest one is used** (the highest version number; currently 2.1.0).
Draft versions marked as pre-releases, such as `2.0.0-rc.1`, are used only when you name them. The
assistant tells you which version it used.

Because 1.0.0, 1.1.0 and 1.2.0 use identical rules, running any of them gives the same instructions
(i.e., versions 1.0.0, 1.1.0 and 1.2.0 are identical, for historical reasons). Version **2.0.0** is the
corrected rule set based on the review report. Version **2.1.0** keeps 2.0.0's decisions and adds the
requirement/metric labels.

If you ask for a version that isn't in the list, the assistant will refuse and show you the versions
that exist.

## 6. Comparing versions

To see how a rules change affects results:

1. Run the same document once per version, keeping the same model where possible, so the rules are the
   only difference.
2. Ask the assistant to compare the two runs by run ID: which metrics appear in only one run, and which
   changed.
3. When scoring the automatic extraction against an answer key, always name the run (and its version).
   Never combine runs.

```text
Please compare the metrics extracted by:
- version 1.0.0, model: gpt-6.1-sol
- version 2.0.0, model: gpt-6.1-sol
for document <ddd>.

Generate an analysis report and save the report in the sub-directory 'analysis-reports' of the
skill's directory. Report file name format: <yyyymmdd-hhmm>-metric-extraction-analysis-report.md
```

## 7. Analyze Extraction
```text
Review the the metrics extracted by 'extract-metrics-benchmark' skill, version <the-version>
for the document <doc-id> by the model <model-name>. Generate an analysis report and save the report 
in the sub-directory 'analysis-reports' of the skill's directory. Report file name
format is <yyyymmdd-hhmm>-metric-extraction-analysis-report.md.
```

## 8. Limits

- **One document per run.**
- **Old answer keys stay as they were.** If the rules improve, older runs are not corrected
  automatically. Run the document again with the new version.
- **Answer keys are judgments.** The skill checks its work, but a run is only as good as its rules
  version. Runs made with version 1.0.0, 1.1.0 or 1.2.0 include many items that are not real metrics,
  so don't use them to score `extract_metrics`. Re-run the document with version 2.0.0 or later.
- **Requirement/metric labels exist only from version 2.1.0.** Runs made with 2.0.0 or earlier don't
  carry them; re-run the document with 2.1.0 to get them.
- **The Gold Metrics page shows one run per document**: the latest run for the chosen skill version
  and model. Earlier runs with the same version and model are not shown; ask the assistant if you
  need them.

## 9. Further reading

- How the skill works, for maintainers: `SKILL.md` and `references/benchmark-contract.md` in the skill
  directory.
- History of rule and tooling changes: `CHANGELOG.md` in the skill directory.
- Review of the version 1.0.0 answer key for document 416:
  `KnowledgeStore/doc-repo/devdocs/202610/2026100601-devdoc-gold-metrics-416-review.md`.

## 10. Change Log

| Version | Timestamp | Author | Reason | Summary |
|---|---|---|---|---|
| 1.3 | 2026-10-07T05:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 2.1.0 released | Added 2.1.0 to Available versions; it is now the default. Explained the requirement/metric labels and added a limit noting that only 2.1.0 runs carry them. |
| 1.2 | 2026-10-06T10:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 2.0.0 released | Added 2.0.0 to Available versions; it is now the default. Limits now say to re-run with 2.0.0. |
| 1.1 | 2026-10-06T09:15:00-05:00 | Not specified (drafted by Claude Code) | Gold Metrics page gained version and model filters | "Where to see results" explains the Skill version and Model name pull-downs and that the document list shows only documents with gold metrics; the limit about not showing version or model is replaced. Run IDs are now date-times. |
| 1.0 | 2026-10-06T08:40:00-05:00 | Not specified (drafted by Claude Code) | Default version rule changed | When no version is named, the newest released version is used; removed the Default column. Owner added slash-command and Codex examples with a version. |
| 1.0 | 2026-10-06T08:30:04-05:00 | Not specified (drafted by Claude Code) | Users need to know how to run the skill and which versions exist | First edition: purpose, key ideas, use in Claude Code, Codex and other assistants, available versions, comparing versions, limits. |
