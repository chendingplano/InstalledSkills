---
name: sys-tools
description: Use when a task involves manipulating files, documents, or other repetitive local work that a purpose-built command might already do - searches the workspace's installed system tools before writing a one-off script.
---

# Workspace System Tools

The workspace has a set of installed command-line tools for recurring local
tasks. They are discovered on demand, not listed here — the catalog grows, and
loading all of it into context would waste it.

## Before writing a one-off script

Search for an existing tool first:

```bash
tool-index search <keywords>
```

Use the words a user would actually say: `tool-index search bibtex citations`,
`tool-index search pdf extract`. Nothing found is a normal outcome — proceed
with your own approach.

## Using a tool you found

Get its full interface before calling it:

```bash
tool-index describe <name>
```

This gives arguments, flags, defaults and examples. Then run the tool
directly. Every tool supports `--json`; **use it** — parsing a tool's
human-readable output is a bug waiting to happen.

## Rules

- `tool-index` is a registry, not a dispatcher. It cannot run tools; it only
  finds and describes them. Run the tool yourself.
- A tool may prompt for permission on first use. That is expected; do not try
  to work around it.
- If a tool you expected does not appear, it may exist but be unexposed to
  agents. Tell the user rather than assuming it is absent — they control
  exposure in `Utils/tools.toml`.
- Exit codes: `0` success, `1` tool error, `2` usage error.

To build a new tool rather than find one, use the `create-sys-tools` skill.
