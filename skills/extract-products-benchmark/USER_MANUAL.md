# Extract Products Benchmark — User Manual

| Field | Value |
|---|---|
| title | Extract Products Benchmark — User Manual |
| language | en |
| format | markdown |
| version | 1.0 |
| status | Draft |
| author | Not specified |
| owner | Not specified |
| audience | People who run or review gold-product benchmarks through a coding assistant; no programming needed |
| create-time | 2026-11-08T12:00:00-06:00 |
| last-modify-time | 2026-11-08T12:00:00-06:00 |
| keywords | gold products, benchmark, ground truth, extract_products, product relations, testbed.products, rules version, Claude Code, Codex |

This manual has its own version number (1.0). The skill's rules versions are numbered separately
and listed under [Available versions](#5-available-versions).

## 1. What this skill is

Documents name products: equipment, containers, materials, appliances, waste categories. They
also say things about them: a product is in scope, must be designed a certain way, must be stored
or transported a certain way, must meet limits. The production system finds these automatically,
using the processor `extract_products`. To know how good it is, you need an answer key: a
carefully checked list of every product the document names and every relation it has with each
one. These are the **gold products**.

This skill builds that answer key for one document. Your coding assistant:

1. reads the whole document line by line;
2. decides which things are products (a movable article, material or waste stream) and which are
   not (facilities, places, organizations, things only mentioned in a cited document's title);
3. records each relation the document has with each product, with its obligation, requirement
   text, conditions, parameters and responsible party;
4. checks its own work twice: once for anything missed, once for mistakes;
5. saves the result.

- **Who it is for:** anyone who wants to measure or improve product extraction.
- **When to use it:** when a document needs an answer key for products.
- **What it does not do:** it never changes production data. Results go to a separate test area
  (`testbed.products`), not to the production table `kb.products`.

It works like the metrics, references and provisions benchmark skills, but for products.

## 2. Key ideas

- **Document ID:** every document has a number, its `kb.inputs.id` (for example `416`). You always
  give the skill one document ID.
- **Run:** each answer key is saved as a separate snapshot, called a run. A run is identified by
  the date and time it started (for example `20261108_143005`). Runs are never overwritten.
- **Rules version:** the rules for what counts as a product and how to label it are numbered
  (1.0.0, …). A released version never changes, and every run records the version it used.
- **Model:** each run records which AI model did the work.
- **One row = one product and one relation:** a waste bin that must have a lid and must carry a
  label gives two rows (design, labelling). All rows of the same product share a product key, so
  the score can tell "found the product" apart from "found every relation".
- **Waste counts:** waste categories (recyclables, hazardous waste) and waste streams (leachate,
  slag) are products under rules 1.0.0.

## 3. Before you start

Check that:

- you are working in this workspace (`/Users/cding/Workspace`);
- the ChenWeb database is reachable (the assistant uses the settings in `ChenWeb/.env` or
  `mise env`);
- the document has been parsed, so its line file exists.

## 4. How to run it

Ask your assistant:

> Use $extract-products-benchmark for document 416

or, for a specific rules version:

> Use $extract-products-benchmark, version 1.0.0 for document 416

The assistant reads the document, builds the answer key, checks it, saves it and reads it back.
It then reports the run ID, how many rows and products it saved, and any doubts. You can view the
result in ChenWeb under System Admin › Benchmark › Products › Gold Products. To score the
production extraction against it, use System Admin › Benchmark › Products › Benchmark, or the
`score-extract-products` skill.

## 5. Available versions

| Version | Released | What it is |
|---|---|---|
| 1.0.0 | 2026-11-08 | First release. One row per product and relation; waste categories and streams are products; enrichment fields recorded for grading. |

## 6. Change Log

| Manual version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-08 | First version. |
