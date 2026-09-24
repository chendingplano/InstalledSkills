---
name: db-migration
description: Database table creation and schema update skill using goose migrations. Use when any project (tax/, ChenWeb/, shared/) creates a new table, alters an existing table schema, adds/removes columns or constraints, or creates/drops indexes. Ensures every schema change is captured as a proper goose migration file.
---

# Database Migration Skill

This workspace uses [pressly/goose v3](https://github.com/pressly/goose) for database schema migrations, wrapped in `shared/go/api/goose/goose.go`.

**All schema changes use SQL goose migrations.** The existing Go-based idempotent migrations in `migrations.go` are a legacy baseline — do not add to them.

---

## Three Migration Tracks

| Track | Migrator | Database | Location |
|-------|----------|----------|----------|
| **Project** | `goose.ProjectMigrator` | `ApiTypes.ProjectDBHandle` | `<project>/server/migrations/` |
| **Shared** | `goose.SharedMigrator` | `ApiTypes.MigrationDBNandle` | `shared/migrations/` |
| **AutoTester** | `goose.AutoTesterMigrator` | `AutotesterDBHandle` | `<project>/server/migrations/autotester/` |

---

## Workflow

### Step 1 — Determine which track

- Change is in `tax/` or `ChenWeb/` app tables → **Project track** → `<project>/server/migrations/`
- Change is in `shared/go/` package tables → **Shared track** → `shared/migrations/`

### Step 2 — Migration type: always use SQL (goose)

**All new migrations must be SQL goose files.** Do not add new Go-based idempotent migrations.

Existing Go migrations in `migrations.go` (written before goose was integrated) represent the schema baseline and are kept as-is — they are already tested, idempotent, and harmless to leave running. Converting them to SQL provides no benefit and introduces unnecessary risk.

The `db_migrations` version table tracks schema history from the point of goose integration onward. That is sufficient.

### Step 3 — Create the SQL migration file

**Filename format:** `YYYYMMDDHHMMSS_short_description.sql`

Use today's date + a sequence number: e.g., `20260324000001_create_clients_table.sql`

**File skeleton:**

```sql
-- +goose Up
CREATE TABLE IF NOT EXISTS table_name (
    id         BIGSERIAL    PRIMARY KEY,
    -- ... columns ...
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_table_name_col ON table_name(col);

-- +goose Down
DROP INDEX  IF EXISTS idx_table_name_col;
DROP TABLE  IF EXISTS table_name;
```

**Rules:**
- Always use `IF NOT EXISTS` / `IF EXISTS` for idempotency
- Always use `TIMESTAMPTZ`, never `TIMESTAMP`
- `-- +goose Down` must reverse `Up` in reverse order
- For PL/pgSQL blocks or multi-statement procedures, wrap with:
  ```sql
  -- +goose StatementBegin
  ...
  -- +goose StatementEnd
  ```
- For `CREATE INDEX CONCURRENTLY` add `-- +goose NO TRANSACTION` at the top

### Step 4 — Verify startup wires the migrator

Confirm the project's `main.go` (or `server.go`) calls the appropriate `Run*Migrations()` before serving traffic:

```go
import sharedgoose "github.com/chendingplano/shared/go/api/goose"

// Project tables
if err := sharedgoose.RunProjectMigrations(ctx, logger, migrateCfg, projectDB); err != nil {
    log.Fatal("project migrations failed:", err)
}

// Shared library tables (if shared/ tables were changed)
if err := sharedgoose.RunSharedMigrations(ctx, logger, migrateCfg, sharedDB); err != nil {
    log.Fatal("shared migrations failed:", err)
}
```

### Step 5 — Test the migration

**Never put the database password or a connection string on the command line.**
goose echoes its arguments back in error messages (e.g. `goose run: "host=… password=…": no such
command`), so one mistyped command prints the password into the terminal and the agent transcript.
Command-line arguments are also visible to other users via `ps`. Instead, give the credentials to
the Postgres driver through the standard `PG*` environment variables, and pass goose a connection
string with no secrets (`sslmode=disable`). Do not `echo` or log these variables.

```bash
# Run from the project directory (ChenWeb/ or tax/); .env holds PG_USER_NAME, PG_PASSWORD, PG_DB_NAME
set -a; source .env >/dev/null 2>&1; set +a
export PGHOST="${PG_HOST:-localhost}" PGPORT="${PG_PORT:-5432}" PGUSER="$PG_USER_NAME" \
       PGPASSWORD="${PG_PASSWORD:-$PGPASSWORD}" PGDATABASE="$PG_DB_NAME"
export GOOSE_DRIVER=postgres GOOSE_DBSTRING="sslmode=disable"   # no secrets in here

# Project tables:  GOOSE_MIGRATION_DIR=$PWD/project_migrations  GOOSE_TABLE=project_db_migration
# Shared tables:   GOOSE_MIGRATION_DIR=$PWD/shared_migrations   GOOSE_TABLE=shared.shared_db_migration
export GOOSE_MIGRATION_DIR="$PWD/shared_migrations" GOOSE_TABLE=shared.shared_db_migration

goose status          # verify before applying
goose up              # apply (also happens automatically on next server start)
goose down && goose up   # test rollback
```

If `goose` isn't installed, install it to a scratch directory rather than using `go run … $ARGS`
(zsh does not word-split a command held in a variable):
`GOBIN=<scratch>/bin go install github.com/pressly/goose/v3/cmd/goose@v3.26.0`.

If any command output might still contain a connection string, pipe it through
`sed 's/password=[^ ]*/password=***/g'` before it reaches the terminal.

### Step 6 — Commit the migration file

Always commit the `.sql` file alongside the code that uses the new table. Never edit a migration file after it has been applied in any environment.

---

## Checklist

- [ ] Correct migration track chosen (Project / Shared / AutoTester)
- [ ] SQL file uses `YYYYMMDDHHMMSS_description.sql` naming
- [ ] `-- +goose Up` and `-- +goose Down` present and correct
- [ ] `IF NOT EXISTS` / `IF EXISTS` used throughout
- [ ] `TIMESTAMPTZ` used (not `TIMESTAMP`)
- [ ] Down reverses Up in reverse order
- [ ] `StatementBegin/End` wrapping added if needed
- [ ] Server startup calls `Run*Migrations()` for the affected track
- [ ] Migration file committed to version control
- [ ] Rollback tested locally

---

## Quick Reference: MigrationConfig

```go
migrateCfg := ApiTypes.MigrationConfig{
    MigrationsFS:    "migrations",       // embed.FS sub-path or dir name
    MigrationsDir:   "migrations",       // on-disk path for CreateMigration
    DBName:          "myapp",            // informational
    TableName:       "db_migrations",    // version-tracking table
    Verbose:         "false",
    AllowOutOfOrder: "false",
}
```

## Quick Reference: Programmatic Migration (runtime)

Use only for management commands or one-off deployments — not in request handlers:

```go
filename, err := goose.ProjectMigrator.CreateAndApply(ctx,
    "add_verified_at_to_users",
    `ALTER TABLE users ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;`,
    `ALTER TABLE users DROP COLUMN IF EXISTS verified_at;`,
)
// Commit the returned filename to git!
```
