---
name: create-sys-tools
description: Use when creating a new command-line utility for the workspace toolbox - scaffolds a tool in the util-tools repo following its conventions contract, wires it into the workspace, and registers it with the correct default exposure.
---

# Creating a System Tool

Tools live in `/Users/cding/Workspace/Utils` (repo `chendingplano/util-tools`).

**Read `/Users/cding/Workspace/Utils/AGENTS.md` first.** It is the authoritative
conventions contract. This skill is the procedure; it does not restate the
rules, and where the two appear to disagree, `AGENTS.md` wins.

## Procedure

1. **Name the tool.** Lowercase, hyphenated, verb-or-noun, no `util-`/`tool-`
   prefix. Check it does not collide with an existing command:

   ```bash
   command -v <name> || echo "free"
   ```

   Refuse a name that shadows an existing binary and propose alternatives.

2. **Confirm the interface with the user before writing code.** What is the
   input, what is the output, what does `--json` emit, does it mutate files in
   place (if so it needs `--dry-run`). Do not guess.

3. **Scaffold from the template:**

   ```bash
   cd /Users/cding/Workspace/Utils
   cp -R _template <name>
   cd <name>
   ```

4. **Rewrite the identity:**
   - `go.mod` module path → `github.com/chendingplano/util-tools/<name>`
   - `cmd/example-tool/` → `cmd/<name>/`
   - `internal/example/` → a package named for what it does
   - the `descriptor` constant — see "The descriptor" in `AGENTS.md` for the
     required fields and their rules. Get `keywords` right: it is what
     `tool-index search` matches against, and a tool with poor keywords is
     undiscoverable no matter how good it is
   - `README.md`

5. **Register the module** in `/Users/cding/Workspace/go.work` under `use (`.

6. **Register the policy** in `/Users/cding/Workspace/Utils/tools.toml`:

   ```toml
   [<name>]
   expose = "off"
   mode = "ask"
   ```

   **Always `off`/`ask`.** Exposing a tool to agents is the user's decision,
   made deliberately after the tool has proven itself. Never register a new
   tool as discoverable, and never as `auto`, even if asked to "set it up
   fully" — raise it as a separate question instead.

7. **Write the failing test first.** Table-driven, against the library package.
   Re-read the Testing and Cross-platform rules sections of `AGENTS.md` before
   writing the table; tools that parse text have a rule there that is easy to
   miss and easy to get wrong.

8. **Implement** the library, then the thin `cmd/`.

9. **Verify:**

   ```bash
   cd /Users/cding/Workspace/Utils/<name>
   gofmt -l . && go vet ./... && go test ./...
   GOOS=windows GOARCH=amd64 go build ./... && GOOS=linux GOARCH=amd64 go build ./...
   ```

   All must pass. The cross-compiles catch platform mistakes without a Windows
   machine.

10. **Install and check the descriptor round-trips:**

    ```bash
    cd /Users/cding/Workspace/Utils && mise install-all
    <name> --describe | python3 -m json.tool
    ```

    Expected: valid JSON whose `name` matches the binary.

11. **Commit with `jj`**, never `git commit`. Do not create branches.

## Afterwards

Tell the user the tool is built and registered as invisible to agents, and ask
whether they want to change `expose`/`mode` in `tools.toml`. If they do, run:

```bash
cd /Users/cding/Workspace/Utils && tool-index refresh
```

so the new tool enters the catalog.
