# Filing a devdoc

Devdocs live in `KnowledgeStore/doc-repo/devdocs/`, one subdirectory per month
(`YYYYMM/`), per the workspace CLAUDE.md's "Documents" section.

## Filename

```
YYYYMMDDSS-devdoc-<slug>.md
```

- `YYYYMMDD` — today's date.
- `SS` — a two-digit sequence number, `01`, `02`, ... for the Nth devdoc filed that
  day. Check the target month directory for the highest existing `SS` on that date
  before picking the next one.
- `<slug>` — lowercase, hyphenated, short description of the feature (matches the
  doc's title loosely). Look at existing filenames in the same month directory for
  the house style, e.g. `2026092401-devdoc-holiday-calendar-admin.md`.

## Before creating

1. Confirm `KnowledgeStore/doc-repo/devdocs/YYYYMM/` exists for the current month;
   create it if it doesn't (this is expected on the first devdoc of a new month).
2. Confirm no doc with the same `YYYYMMDDSS` prefix already exists — list the month
   directory and check today's date against existing filenames.
3. Pick a slug that doesn't collide with an existing devdoc covering the same
   feature. If one already exists for this feature, prefer updating it over creating
   a near-duplicate — devdocs describe current behavior, not a changelog, so an
   existing doc for the same feature should be edited in place when behavior changes.

## Committing

`KnowledgeStore` is its own git repo. Commit through `jj`, never `git commit`
directly, per the workspace's Git Workflow rules.
