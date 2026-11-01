# Changelog — extract-provisions-benchmark

Two kinds of change are tracked separately:

- **Rules versions**: the annotation rules in `rules/<version>.md`. A rules file is frozen once
  released and is listed with its SHA-256 in `rules/versions.json`.
  `testbed.provisions.skill_version` is the rules version a run used.
- **Tooling changes**: the `SKILL.md` procedure, `references/`, `scripts/` and storage. Tooling is
  shared by all versions and always the latest, so it must keep every released rules version
  runnable.

## Rules versions

| Version | Rules file | Notes |
|---|---|---|
| 1.0.0 | `rules/1.0.0.md` | First release. See below. |

Default when no version is named: the newest released version (currently 1.0.0). Pre-releases are
never the default.

### 1.0.0 — 2026-11-06

First release. It follows the provision model of `extract_provisions` (capsule
`extract-provisions-spec.md`, prompt `prompt-extract-provisions-v3.md`) and the provision types
of GB/T 1.1—2020 §9 and ISO/IEC Directives Part 2 clause 7.

User rulings (openspec change `extract-provisions-benchmark`):

- Imperative test-method steps are provisions: kind `instruction`, type `mandatory`.
- One provision per normative statement. That is a sentence, or a list item or table cell that is
  not a full sentence. A sentence is split only where its provision type or its subject changes.

The rules define:

- **Accept rules.** A1 requirement/prohibition, A2 instruction, A3 recommendation, A4 permission,
  A5 implicit requirement (`is_explicit = false`).
- **Exclude rules.** X1 statements about the document, X2 scope, X3 reference boilerplate and
  lists, X4 definitions/classifications/descriptions, X5 pointers/headings/captions,
  X6 objectives and principles, X7 possibility/capability/fact, X8 value rows invoked by another
  provision (those belong to the metrics benchmark).
- **Duplicates.** D1.
- **Labels.** `provision_kind` → `provision_type` mapping, `location_type` from the parser's line
  types, and the subject is the bound party or object.

## Tooling changes

### 2026-11-06

- First version of `scripts/benchmark_io.py` (prepare / validate / save) and its tests.
- Storage in `testbed.provision_benchmark_runs`, `testbed.provisions` and
  `testbed.provisions_dropped` (ChenWeb migration `20261106000101_create_testbed_provisions.sql`).
