---
name: user-manual-writer
description: Use when creating, revising, translating, or localizing end-user manuals, including requests involving plain-language explanations, examples, keywords, metadata, change history, versions, or Markdown, Typst, and HTML output.
disable-model-invocation: true
---

# User Manual Writer

## Purpose

Create or modify user manuals for people who normally do not code. Explain what a product, feature, service, or concept is and why it matters. Include how-to information only when it makes the “what” easier to understand; avoid code unless it is the clearest possible example.

## Workflow

1. Identify the operation: create a manual or modify an existing one.
2. Gather the product, audience, scope, source material, requested language(s), format, manual name, version, change reason, and whether to retain the source as a prior version.
3. For modifications, locate candidates under `/Users/cding/Workspace/KnowledgeStore/doc-repo/user-manuals`. Require the requester to identify the exact source when multiple languages, formats, or versions match; never guess which file to overwrite. Read the complete source, preserve accurate content, and apply only justified changes.
4. Draft content in a format-neutral outline, then render it in the requested format.
5. Review for plain language, useful examples, unsupported claims, consistent terminology, and audience fit.
6. Save each language and format as a separate file under `/Users/cding/Workspace/KnowledgeStore/doc-repo/user-manuals`.

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

Place metadata near the beginning of every manual. Use these field names:

`title`, `language`, `format`, `version`, `status`, `author`, `owner`, `audience`, `create-time`, `last-modify-time`, and `keywords`.

Use an ISO 8601 timestamp with timezone for `create-time` and `last-modify-time`. Set both when creating a manual. Preserve `create-time` and update only `last-modify-time` when modifying one. Do not guess people; use `Not specified` or ask when identity is important. Keep detailed modification information in Change Log rather than duplicating it in metadata.

Accept versions containing one or more non-negative integer components separated by periods, matching `^[0-9]+(?:\.[0-9]+)*$`; examples include `1`, `1.0`, and `2.12.3`. Use a requested version exactly. When modifying an existing manual, preserve its current version and update it in place by default. Create a new versioned file only when the requester explicitly asks for a new version or explicitly provides a different version. Do not infer a new version from the absence of a version request. Use `1.0` when creating a manual with no prior version. Never compare versions as strings.

Encode every version in its filename and keep filename, metadata, and Change Log versions identical. When the requester explicitly provides a different version or asks for a new version, create a new file and retain the source. Otherwise, overwrite the identified source file in place, preserving its version and `create-time`.

Always include a format-appropriate Change Log section with newest entries first. Record version, timestamp, author or responsible party, reason, and a concise summary. Preserve prior entries when modifying a manual. Use `## Change Log` in Markdown, `== Change Log` in Typst, and a semantic `<section>` containing `<h2>Change Log</h2>` in HTML.

## Output Formats and Filenames

Support exactly `markdown`, `typst`, and `html` unless the requester asks for another format and confirms an exception. Default to Markdown when no format is specified. Use these extensions:

- Markdown: `.md`
- Typst: `.typ`
- HTML: `.html`

Default to English (`en`) when no language is specified. Use lowercase BCP 47-compatible language tags such as `en`, `es`, `zh-hans`, or `pt-br`. Use a lowercase descriptive slug and always name files `<slug>-v<version>-<language>.<extension>`, for example `account-overview-v1.0-en.md`, `account-overview-v2-es.html`, or `account-overview-v2.1-zh-hans.typ`. For multiple languages, create one file per language; do not combine languages unless explicitly requested.

For Typst, use readable headings, lists, emphasis, and tables that compile cleanly. For HTML, produce a complete readable document with a title, metadata, semantic headings, lists, tables, and minimal accessible styling when useful. Keep the same content and metadata across formats.

## Modification Requests

Use the requester’s manual name to find candidates, then resolve the exact source by slug, version, language, and format. If more than one candidate remains, list the candidates and ask the requester to select one before writing. Treat content changes, reason, keywords, language, format, and version as separate inputs. Flag conflicts rather than silently deleting established information. For modifications, preserve the source version and update in place unless the requester explicitly asks for a new version or provides a different version.

## Quick Reference

| Request omits | Default or action |
|---|---|
| Language | English (`en`) |
| Format | Markdown (`.md`) |
| Version, no prior manual | `1.0` |
| Version, modifying an existing manual | Preserve the source version and update in place |
| New version explicitly requested | Use the requested version and retain the source |
| Exact source is ambiguous | Ask the requester to choose; do not write |

Example: revising `billing-guide-v1.10-en.md` without a requested new version updates `billing-guide-v1.10-en.md` in place, preserves its `create-time`, updates `last-modify-time`, and adds a `1.10` Change Log entry. If the requester explicitly asks for version `1.11`, create `billing-guide-v1.11-en.md` and retain the `v1.10` source.

## Common Mistakes

- Do not omit the version from a filename.
- Do not reset `create-time` during an in-place modification.
- Do not create or increment a version unless the requester explicitly requests a new version or provides a different version.
- Do not select among ambiguous source files by assumption.
- Do not use Markdown heading syntax in Typst or HTML output.

## Final Checklist

- Correct absolute output directory, format, extension, slug, encoded version, and language suffix.
- Metadata is present and internally consistent.
- `create-time` is preserved for in-place changes; `last-modify-time` is current.
- Keywords include supplied terms plus relevant generated terms.
- Examples clarify the subject without assuming coding knowledge.
- The format-appropriate Change Log exists and is preserved or updated correctly.
- Existing manuals are updated in place by default; new versions do not overwrite prior versions when explicitly requested.
- Ambiguous source matches are resolved by the requester before writing.
- Every factual claim is supported by the provided source material or clearly marked for confirmation.
