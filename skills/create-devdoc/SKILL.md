---
name: create-devdoc
description: Use when writing a developer document (devdoc) that explains a feature or system in the workspace after it has been built — for a feature just implemented, or an existing one that lacks documentation. Devdocs are filed under KnowledgeStore/doc-repo/devdocs/ and are read by both human developers and agents, so this skill governs voice (plain language for humans, rigorous detail only where warranted) and where OpenSpec should carry the formal contract instead of the devdoc repeating it.
---

# Creating a devdoc

A devdoc is the durable record of what a feature *is*, for whoever opens the
workspace next — a human developer or an agent. It is written after the work is
done, not as a design or planning document.

## Who reads a devdoc, and how that shapes it

Two audiences read the same file:

- **Human readers** are technical people who may not read code. Write for them in
  plain language: no jargon, no unexplained acronyms, no assumption that the reader
  can parse a schema or a diff. Explain what the feature does and why it exists the
  way a knowledgeable colleague would explain it out loud.
- **Agents** read the same file and benefit from — and can easily parse — formal,
  precise, technical prose: exact names, tables, invariants, edge cases.

Do not pick one voice for the whole document. Structure the doc so each audience
gets what it needs (see "Choosing a structure" below).

## Choosing a structure

**Small or simple feature, no OpenSpec change behind it:**
Use `assets/template-simple.md`. Lead with a short plain-language **Summary**, then
a **Details** section that can be as formal and rigorous as the feature warrants —
exact endpoint paths, schema, config keys. It's fine for Details to be brief if the
feature is genuinely small.

**Feature implemented via an OpenSpec change:**
Use `assets/template-with-openspec.md`. The OpenSpec proposal/design/spec documents
already carry the rigorous, agent-oriented content — do not duplicate that material
in the devdoc. The devdoc instead:
- Links to the change's `proposal.md`, `design.md`, `tasks.md`, and the resulting
  `spec.md` under `openspec/specs/`.
- Is written **mainly for human readers** — plain-language summary and orientation
  (what it does, why, where to find it).
- Tells the reader plainly that the spec file is the contract: if behavior changes
  later, the spec must be updated, not just the devdoc.

When unsure which template applies, check whether the project has an
`openspec/changes/archive/` entry for this feature. If yes, use the OpenSpec
template. If the feature was built without going through OpenSpec, use the simple
template.

## Writing it

1. Gather the facts by reading the actual code/config/schema involved — a devdoc
   describes what was built, not what was planned. Do not copy proposal language
   without verifying it still matches what shipped.
2. Fill in the chosen template. Keep the plain-language section genuinely free of
   jargon — read it back and ask whether a technical person with zero programming
   background would follow it.
3. Note real, by-design limitations plainly; don't bury them in the technical
   section only.
4. File and name it per `references/filing.md` (path, month subdirectory, sequence
   number, collision check).
5. Commit through `jj` per the workspace Git Workflow rules — `KnowledgeStore` is
   its own repo.

## Updating an existing devdoc

Devdocs describe current behavior, not a changelog. If a devdoc already exists for
the feature being changed, update it in place rather than filing a new one — unless
the change is substantial enough to warrant its own dated entry (use judgment; when
unsure, ask).
