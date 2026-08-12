---
name: user-manual-writer
description: Use when creating, revising, translating, or localizing end-user manuals, especially when the requester needs accessible explanations, examples, keywords, metadata, versioned files, or Markdown, Typst, or HTML output.
---

# User Manual Writer

## Purpose

Create or modify user manuals for people who normally do not code. Explain what a product, feature, service, or concept is and why it matters. Include how-to information only when it makes the “what” easier to understand; avoid code unless it is the clearest possible example.

## Workflow

1. Identify the operation: create a manual or modify an existing one.
2. Gather the product, audience, scope, source material, requested language(s), format, filename, and requested version behavior.
3. For modifications, locate the named manual under `KnowledgeStore/doc-repo/user-manuals`, read the complete current file, preserve accurate content, and apply only justified changes. Record the stated reason for each meaningful change.
4. Draft content in a format-neutral outline, then render it in the requested format.
5. Review for plain language, useful examples, unsupported claims, consistent terminology, and audience fit.
6. Save each language and format as a separate file under `KnowledgeStore/doc-repo/user-manuals`.

## Audience and Content Rules

- Lead with the user’s goal, the thing being explained, who it is for, and when it is useful.
- Describe concepts, capabilities, choices, limits, expected results, and examples before procedures.
- Use short sections, descriptive headings, definitions, examples, and “what to expect” notes.
- Use “how” steps only to clarify a capability or outcome; do not turn the manual into developer documentation.
- Never invent behavior, dates, roles, permissions, guarantees, or product limits. Mark unknowns as needing confirmation.
- Translate meaning naturally rather than mechanically. Keep section order, metadata meaning, examples, and terminology aligned across languages.

## Keywords

Accept requester-supplied keywords and preserve them unless they are irrelevant. Generate additional keywords from the product name, audience language, major concepts, features, tasks, synonyms, and likely search terms. Keep keywords concise, deduplicated, and useful for discovery; label them in metadata as supplied, generated, or both when that distinction matters.

## Metadata and Versioning

Place metadata near the beginning of every manual. Include, when known:

`Title`, `Language`, `Format`, `Version`, `Status`, `Author`, `Owner`, `Audience`, `Created`, `Last updated`, and `Keywords`.

Use the current date for new or modified files. Do not guess people or dates; use `Not specified` or ask when the value is important. Start a new manual at `1.0`. For modifications, increment the version when requested or when the change is substantial; otherwise preserve the version and update `Last updated`. When generating a new version, include the version in the filename while keeping the language code immediately before the extension, for example `billing-guide-v2.0-en.md`.

Always include a `## Change Log` section with newest entries first. Each entry records version, date, author or responsible party, reason, and a concise summary of changes. Preserve prior entries when modifying a manual.

## Output Formats and Filenames

Support exactly `markdown`, `typst`, and `html` unless the requester asks for another format and confirms an exception. Use these extensions:

- Markdown: `.md`
- Typst: `.typ`
- HTML: `.html`

Use a lowercase, descriptive slug and always end the stem with the language code: `<slug>-<language>.<extension>` or `<slug>-v<version>-<language>.<extension>`. Examples: `account-overview-en.md`, `account-overview-es.html`, `account-overview-v2.0-en.typ`. For multiple languages, create one file per language; do not put several languages into one file unless explicitly requested.

For Typst, use readable headings, lists, emphasis, and tables that compile cleanly. For HTML, produce a complete readable document with a title, metadata, semantic headings, lists, tables, and minimal accessible styling when useful. Keep the same content and metadata across formats.

## Modification Requests

Use the requester’s manual name to identify the source file. Treat these as separate decisions: content changes, reason for change, keywords, language, format, and whether to overwrite or generate a new version. If the requested change conflicts with the current manual, flag the conflict rather than silently deleting established information. When a new version is requested, retain the old file and create the new version; otherwise modify the named file in place unless the requester says otherwise.

## Final Checklist

- Correct output directory, format, extension, slug, and language suffix.
- Metadata is present and internally consistent.
- Keywords include supplied terms plus relevant generated terms.
- Examples clarify the subject without assuming coding knowledge.
- `Change Log` exists and is preserved or updated correctly.
- New versions do not overwrite prior versions.
- Every factual claim is supported by the provided source material or clearly marked for confirmation.
