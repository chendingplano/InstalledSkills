# Extract Metrics Benchmark — User Manual

| Field | Value |
|---|---|
| title | Extract Metrics Benchmark — User Manual |
| language | en |
| format | markdown |
| version | 1.11 |
| status | Draft |
| author | Not specified |
| owner | Not specified |
| audience | People who run or review gold-metric benchmarks through a coding assistant; no programming needed |
| create-time | 2026-10-06T08:30:04-05:00 |
| last-modify-time | 2026-10-09T10:00:00-05:00 |
| keywords | gold metrics, benchmark, ground truth, extract_metrics, metric extraction quality, testbed.metrics, skill version, rules version, Claude Code, Codex, compare versions |

This manual has its own version number (1.5), which is separate from the skill's rules versions listed
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

Both requests run extraction, audit, validation, saving to `testbed.metrics`, and read-back verification. You do not need to add “save” or confirm saving separately. The recorded model is the assistant invoking the skill; it obtains its identity from the active runtime/session without asking you. Say “draft only” or “do not save” if you want local artifacts only.

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
| 3.0.0 | `rules/3.0.0.md` | 2026-10-07 | A metric must be something you can **measure**. Requirements with nothing to measure are no longer metrics: "the bin shall have a lid" (an inspection requirement) and "shall comply with CJJ 52" (a requirement that points to another standard). This matches the automatic extraction since 2026-10-07, which no longer saves these. The answer key still lists them, as excluded requirements, so you can check that the extraction set them aside. For document 416 this leaves 35 of 2.1.0's 66 gold metrics. |
| 3.1.0 | `rules/3.1.0.md` | 2026-10-07 | Same as 3.0.0, with one clarification. A rule that only says two parties must **agree** when or how often something is done ("agree the kitchen-waste collection time and frequency") is a duty, not a metric: there is nothing to measure. 3.0.0 runs counted it as a metric with the value left open. For document 416 this leaves 33 gold metrics. |
| 4.0.0 | `rules/4.0.0.md` | 2026-10-07 | A rule that only says a quantity should be **sized to suit** something else ("size the composting room's chamber volume reasonably for the daily amount of waste") is a design requirement, not a metric: no number is given anywhere and nobody has to state one, so there is nothing to check. Requirements where the supplier must **state** a value ("the equipment shall state its energy consumption") or two parties must **agree** one still count. For document 416 this leaves 32 gold metrics. |
| 4.1.0 | `rules/4.1.0.md` | 2026-10-07 | Same choice of metrics as 4.0.0. A metric the document names but gives no value for ("the equipment shall state its specific energy consumption") is now labelled a **metric with no value** (`value_class = metric-with-no-value`) instead of a requirement, and its description explains what the metric is and gives its typical values from domain knowledge, marked as not coming from the document. For document 416 that is 比能耗 and 发酵周期. |
| 5.0.0 | `rules/5.0.0.md` | 2026-10-07 | Consistent with 4.1.0: a rule that only says a quantity should be **sized to suit** something else ("size the composting room's chamber volume for the daily amount of waste") also names a real metric without a value, so it counts again, as a metric with no value with its typical values. 4.0.0 had dropped it as a design requirement. For document 416 this gives 33 gold metrics. |
| 5.1.0 | `rules/5.1.0.md` | 2026-10-07 | Same metrics as 5.0.0. The description of a metric with no value must now give its typical values as a rough number range with a unit (for example "about 30–80 kWh/t, depending on the machine"), not "no reliable typical value". Saying there is no typical value is allowed only with a reason why no range can exist. |
| 6.0.0 | `rules/6.0.0.md` | 2026-10-09 | **A metric has at least a value.** Anything the document names without giving a value is no longer a metric: a value to be stated by the supplier, agreed or sized later ("the equipment shall state its energy consumption"), a formula or a definition of how something is calculated, and a list of things to record. So are definitions of terms wherever they appear, counts of the document's own parts ("use two test methods", "divided into four categories"), and duties to provide equipment or staff that name no number. Numbers inside definitions still count. A table that gives one value per condition gives one metric per condition. This matches the automatic extraction since 2026-10-09, which sets such rows aside. For document 416, 比能耗, 发酵周期 and 单室体积 drop out. |
| 6.1.0 | `rules/6.1.0.md` | 2026-10-14 | **± tolerances keep their sign.** Same as 6.0.0, except a tolerance written `±0.2 K` is stored with `metric_value = ±0.2` instead of `0.2`. |
| 6.2.0 | `rules/6.2.0.md` | 2026-10-15 | **One metric, every place it is stated.** Same as 6.1.0, except a metric the document states in several places (a definition, the requirement, a later clause) is one gold row listing all those lines, not a row plus "duplicate" entries. A different subject or condition is still a separate row. Also, a number stated in a sentence or table is a metric even when a formula uses the same number (the 0.065 %/hPa pressure sensitivity of document 753). |
| 6.3.0 | `rules/6.3.0.md` | 2026-10-15 | **Data dictionaries.** Same as 6.2.0, except that in a data-element catalogue each element's data format (for example `an..70` or `n4..5,1`, kept as one row) and its allowed number of occurrences are gold metrics. 6.2.0 runs treated them as definitions, so document 376 had only 6 gold metrics. |
| 6.4.0 | `rules/6.4.0.md` | 2026-10-16 | **Conditions.** Same as 6.3.0, except the condition of a metric is read broadly: who or what it applies to (for example children vs adults), the environment, the test method or device used, the body site, the load. The object stays in the subject and the rest goes into the condition, written as labelled parts such as `适用人群：幼儿`. The same test settings stated once with a simulation device and once with a simulant object (document 371, 6.5.14.1 and 6.5.14.2) are now two metrics each. |
| 6.5.0 | `rules/6.5.0.md` | 2026-10-16 | A number that only qualifies another value is its condition, not a row; a limit relative to another limit is a value (`倍`). |
| 6.6.0 | `rules/6.6.0.md` | 2026-10-16 | **No derived values.** A count the reader works out from "两端" or "四角和中心", and a "set to zero" instruction, are not metrics (X19). |
| 6.7.0 | `rules/6.7.0.md` | 2026-10-17 | **Definitions stay definitions.** A number that only says what a word means — an age band naming a user group ("3～6 周岁为幼儿"), a counting rule ("360° 计一圈") — is not a metric. A threshold on something measured on the document's object still is. |
| 6.8.0 | `rules/6.8.0.md` | 2026-10-17 | **One size, one row.** A size written as a product ("250 mm×200 mm") is one metric `250×200 mm`, not a length and a width. |
| 6.8.1 | `rules/6.8.1.md` | 2026-10-17 | Wording only: a ±5 mm written once for several sizes gives one tolerance per size. |
| 7.0.0 | `rules/7.0.0.md` | 2026-10-17 | A dose, interval, duration, cap or threshold written with 可/宜/建议/酌情/考虑 is a metric like any other (X8 only for clauses with no number); X1 excludes the action, not its numbers; new section for treatment protocols and procedures. |
| 7.1.0 | `rules/7.1.0.md` | 2026-10-17 | A bound written as a function of case parameters only (such as 收缩压＜70+年龄×2) is a metric, not a value-less formula; a formula containing a measured quantity is still excluded. |

**If you don't name a version, the newest one is used** (the highest version number; currently 7.1.0).
Draft versions marked as pre-releases, such as `2.0.0-rc.1`, are used only when you name them. The
assistant tells you which version it used.

Because 1.0.0, 1.1.0 and 1.2.0 use identical rules, running any of them gives the same instructions
(i.e., versions 1.0.0, 1.1.0 and 1.2.0 are identical, for historical reasons). Version **2.0.0** is the
corrected rule set based on the review report. Version **2.1.0** keeps 2.0.0's decisions and adds the
requirement/metric labels. Version **3.0.0** drops the requirements that have nothing to measure; use it
to score the current automatic extraction. Version **3.1.0** also drops duties to agree when or how
often an activity is done. Version **4.0.0** also drops requirements that only say to size a quantity to
suit something else; the automatic extraction still keeps those, so expect them as its false positives. Version **4.1.0** counts the same metrics as 4.0.0 but labels
the ones the document names without a value as metrics with no value, and describes each with its typical values. Version **5.0.0** counts the sized-to-suit quantities again, as
metrics with no value, so the automatic extraction's matching rows are no longer false positives. Version **5.1.0** requires real
typical-value ranges in those metrics' descriptions. Version **6.0.0** reverses that direction: a metric must have a value, so
metrics with no value, formulas and definitions are all left out; use it to score the automatic extraction from 2026-10-09 on.

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
From a domain expert stand point of view, review the the metrics extracted by 
'extract-metrics-benchmark' skill, version <the-version> for the document 
<doc-id> by the model <model-name>. Generate an analysis report and save the report 
in the sub-directory 'analysis-reports' of the skill's directory. Report file name
format is <yyyymmdd-hhmm>-metric-extraction-analysis-report.md.

IMPORTANT: The purpose of this review is to review the skill, whether
it extracts the gold metrics correctly, accurately and completely.
Thus do not judge the quality of the gold metrics based on the rules and 
instructions from this skill. Judge it as a human domain expert.
```

## 8. Limits

- **One document per run.**
- **Old answer keys stay as they were.** If the rules improve, older runs are not corrected
  automatically. Run the document again with the new version.
- **Answer keys are judgments.** The skill checks its work, but a run is only as good as its rules
  version. Runs made with version 1.0.0, 1.1.0 or 1.2.0 include many items that are not real metrics,
  so don't use them to score `extract_metrics`. Re-run the document with version 2.0.0 or later.
- **Score today's automatic extraction with version 3.0.0 or later.** Since 2026-10-07 the extraction
  no longer saves inspection requirements or requirements that point to another standard. Version 2.x
  answer keys still count them as metrics, so they would make the extraction look worse than it is.
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
| 1.20 | 2026-10-17T16:10:00-05:00 | Not specified (drafted by Claude Code) | Rules version 7.1.0 released | Added 7.1.0 to Available versions; it is now the default. |
| 1.19 | 2026-10-17T14:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 7.0.0 released | Added 7.0.0 to Available versions (modality is not part of the metric gate); it is now the default. |
| 1.18 | 2026-10-17T10:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.8.1 released | Added 6.8.1 to Available versions; it is now the default. |
| 1.17 | 2026-10-17T09:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.8.0 released | Added 6.8.0 to Available versions; it is now the default. |
| 1.16 | 2026-10-17T10:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.7.0 released | Added 6.7.0 to Available versions; it is now the default. Corrected the stated default (was 6.4.0). |
| 1.15 | 2026-10-16T06:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.4.0 released | Added 6.4.0 to Available versions; it is now the default. |
| 1.14 | 2026-10-15T14:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.3.0 released | Added 6.3.0 to Available versions; it is now the default. |
| 1.13 | 2026-10-15T12:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.2.0 released | Added 6.2.0 to Available versions; it is now the default. |
| 1.12 | 2026-10-14T12:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.1.0 released | Added 6.1.0 to Available versions; it is now the default. |
| 1.11 | 2026-10-09T10:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 6.0.0 released | Added 6.0.0 to Available versions; it is now the default. |
| 1.10 | 2026-10-07T13:45:00-05:00 | Not specified (drafted by Claude Code) | Rules version 5.1.0 released | Added 5.1.0 to Available versions; it is now the default. |
| 1.9 | 2026-10-07T13:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 5.0.0 released | Added 5.0.0 to Available versions; it is now the default. |
| 1.8 | 2026-10-07T13:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 4.1.0 released | Added 4.1.0 to Available versions; it is now the default. |
| 1.7 | 2026-10-07T10:15:00-05:00 | Not specified (drafted by Claude Code) | Rules version 4.0.0 released | Added 4.0.0 to Available versions; it is now the default. |
| 1.6 | 2026-10-07T09:20:00-05:00 | Not specified (drafted by Claude Code) | Rules version 3.1.0 released | Added 3.1.0 to Available versions; it is now the default. |
| 1.5 | 2026-10-07T09:00:00-05:00 | Not specified (drafted by Claude Code) | Rules version 3.0.0 released | Added 3.0.0 to Available versions; it is now the default. Added a limit: score the current extraction with 3.0.0 or later. |
| 1.4 | 2026-10-07T05:41:52-05:00 | Codex | Clarify document invocation and model provenance | A document invocation includes saving and read-back; the invoking assistant resolves its own model identity without asking the user. Annotation rules are unchanged. |
| 1.3 | 2026-10-07T05:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 2.1.0 released | Added 2.1.0 to Available versions; it is now the default. Explained the requirement/metric labels and added a limit noting that only 2.1.0 runs carry them. |
| 1.2 | 2026-10-06T10:30:00-05:00 | Not specified (drafted by Claude Code) | Rules version 2.0.0 released | Added 2.0.0 to Available versions; it is now the default. Limits now say to re-run with 2.0.0. |
| 1.1 | 2026-10-06T09:15:00-05:00 | Not specified (drafted by Claude Code) | Gold Metrics page gained version and model filters | "Where to see results" explains the Skill version and Model name pull-downs and that the document list shows only documents with gold metrics; the limit about not showing version or model is replaced. Run IDs are now date-times. |
| 1.0 | 2026-10-06T08:40:00-05:00 | Not specified (drafted by Claude Code) | Default version rule changed | When no version is named, the newest released version is used; removed the Default column. Owner added slash-command and Codex examples with a version. |
| 1.0 | 2026-10-06T08:30:04-05:00 | Not specified (drafted by Claude Code) | Users need to know how to run the skill and which versions exist | First edition: purpose, key ideas, use in Claude Code, Codex and other assistants, available versions, comparing versions, limits. |
