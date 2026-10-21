---
name: create-reusable-module
description: Use when a frontend component, backend package or script is built (or already exists) to be reused by more than one page, service or project and needs to be documented and catalogued as a reusable module, or when a catalogued module's version, files, configuration or status (active, under-dev, retired) changes. Covers KnowledgeStore/doc-repo/modules/ and the kb.reusable_modules table.
---

# Creating a reusable module

A reusable module has two records, and they must agree:

- **A doc** at `KnowledgeStore/doc-repo/modules/module-<slug>.md` — what it is and how to use it.
- **A row** in `kb.reusable_modules` (ChenWeb project database) — the catalogue entry,
  keyed by a stable `module_id`.

Code used by more than one *project* belongs in `shared/` (workspace `CLAUDE.md`); register
it there, not a copy in each project.

## Row fields

| Column | Value |
|---|---|
| `module_id` | `YYYYMMDD-NN`, allocated by the insert below. `YYYYMMDD` = today, or the doc's **Created** date when registering an existing module. Never changes, never reused. |
| `module_name` | Human name, same as the doc title (`Name-Value Visualizer`). |
| `module_type` | `frontend` (UI components, client code), `backend` (server packages, handlers, services), `script` (standalone runnable script or CLI). |
| `prog_language` | Main language, lowercase: `svelte`, `typescript`, `go`, `python`, `bash`, `sql`. |
| `description` | One or two sentences: what it does and when to use it. |
| `files` | JSON array of workspace-relative paths of every file in the module, tests included. |
| `version` | Semver, starts at `1.0.0`. |
| `config_json` | JSON object of the module's settings with their defaults (props, `config.toml` keys, env vars, CLI flags). `{}` if none. |
| `status` | `under-dev`, `active` (in use, safe to reuse) or `retired`. |
| `doc_path` | Workspace-relative path of the doc. |
| `created_by` / `updated_by` | `whoami`. |

## Steps

1. **Read the module's code.** The doc and row describe what was built, not what was planned.
2. **Check it is not catalogued already** (query below, by a distinctive word of the name and
   by its directory). Found → follow *Updating*; do not create a second row or doc.
3. **Pick the doc name** `module-<slug>.md` (slug = lowercase, hyphenated module name) and
   confirm it is unused: `ls KnowledgeStore/doc-repo/modules/`. If the name is taken by a
   different module, choose a more specific slug. Never overwrite another module's doc.
   If it is this module's own doc (registering an existing module), keep the name and, in
   step 5, add the template's header lines to it instead of rewriting it.
4. **Insert the row** (below). It returns the `module_id`.
5. **Write the doc** from [references/doc-template.md](references/doc-template.md), with that
   `module_id` in the header. The doc's **Files** table lists the same paths as `files`, and
   its **Configuration** section the same keys as `config_json`.
6. **Commit the doc** in `KnowledgeStore` through jj, naming the path:
   `jj commit -m "Document reusable module <name> (<module_id>)" doc-repo/modules/module-<slug>.md`.
   Then `jj log` to confirm one linear commit.

## Database access

Run from `ChenWeb/`. Credentials go to `psql` through `PG*` variables, never on the command
line; do not print `.env`.

```bash
set -a; source .env >/dev/null 2>&1; set +a
export PGHOST="${PG_HOST:-localhost}" PGPORT="${PG_PORT:-5432}" PGUSER="$PG_USER_NAME" \
       PGPASSWORD="${PG_PASSWORD:-$PGPASSWORD}" PGDATABASE="$PG_DB_NAME"
```

**Look up** (step 2):

```bash
psql -X -v ON_ERROR_STOP=1 -v q='name-value' <<'SQL'
SELECT module_id, module_name, status, version, doc_path FROM kb.reusable_modules
WHERE module_name ILIKE '%' || :'q' || '%' OR files::text ILIKE '%' || :'q' || '%';
SQL
```

**Insert** (step 4) — allocates the next sequence number for the day in the same statement:

```bash
psql -X -v ON_ERROR_STOP=1 -v day=20261025 -v who="$(whoami)" \
  -v name='Name-Value Visualizer' -v type=frontend -v lang=svelte \
  -v descr='Shows one record as name-value pairs.' \
  -v files='["ChenWeb/web/src/lib/components/shared-ui/name-value/name-value-visualizer.svelte"]' \
  -v config='{"labelWidth": "13rem"}' -v status=active \
  -v doc='KnowledgeStore/doc-repo/modules/module-name-value-visualizer.md' <<'SQL'
INSERT INTO kb.reusable_modules (module_id, module_name, module_type, prog_language,
    description, files, config_json, status, doc_path, created_by, updated_by)
SELECT :'day' || '-' || lpad((COALESCE(MAX(split_part(module_id, '-', 2)::int), 0) + 1)::text, 2, '0'),
       :'name', :'type', :'lang', :'descr', :'files'::jsonb, :'config'::jsonb, :'status',
       :'doc', :'who', :'who'
FROM kb.reusable_modules WHERE module_id LIKE :'day' || '-%'
RETURNING module_id;
SQL
```

A unique-violation on `module_id` means another insert took the number first: run it again.
A shell value containing `'` needs `'\''`.

## Updating

When the module changes, update both records in the same piece of work:

- `UPDATE kb.reusable_modules SET ..., updated_by = :'who', updated_at = NOW() WHERE module_id = :'id';`
- Bump `version`: patch for fixes, minor for additions, major when callers must change.
- Keep `files`, `config_json`, `status` and the doc's header, **Files** and **Configuration**
  sections in step.
- Retiring: `status = 'retired'`; keep the doc and add which module replaces it.
