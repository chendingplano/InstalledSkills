---
name: prod-release
description: "Prepare and publish a production release for a workspace project. Triggers when the user says 'prepare production release for PROJECT-NAME' or similar, optionally with 'use jj' or 'use git'. Supports both jj and git repos, auto-detecting which VCS is in use. Handles validating the project exists, computing a unique release name (rel-yyyymmdd), updating CHANGELOG.md, pushing both the project repo and shared/ repo to GitHub, and creating version tags in both repos."
disable-model-invocation: true
---

# Production Release Skill

## Overview

Releases two repos together:
- `~/Workspace/<project-name>/` — the project repo
- `~/Workspace/shared/` — the shared library repo

Supports both **jj** and **git**. VCS is auto-detected per repo (`.jj` → jj, `.git` only → git). The user can override with "use jj" or "use git".

## Step 1 — Validate, Detect VCS & Compute Release Name

Run the helper script:

```bash
bash ~/.claude/skills/prod-release/scripts/release.sh <project-name> [jj|git]
```

Pass the VCS override as the second argument only if the user explicitly specified one; otherwise omit it.

Output is tab-separated: `<release-name>\t<vcs>` (e.g. `rel-20260323\tjj`).

- If it exits non-zero, report the error to the user and stop.
- Parse stdout into `$RELEASE_NAME` and `$PROJECT_VCS`.
- The script also auto-detects the VCS for `shared/` independently.

## Step 2 — Summarize Changes

For each repo, collect commits since the last tag. Use the detected VCS for each repo.

**jj:**
```bash
cd ~/Workspace/<repo>
jj log --revisions 'tags(..@)..@' --no-graph --template 'description ++ "\n"' 2>/dev/null | head -50
```

**git:**
```bash
cd ~/Workspace/<repo>
git log $(git describe --tags --abbrev=0 2>/dev/null || echo '')..HEAD --oneline 2>/dev/null | head -50
```

Write a release note in markdown format and save it in <project-name>/docs/release-notes. Use the release name as the file name.

If neither repo has any new commits since the last tag, inform the user and confirm before proceeding.

## Step 3 — Update CHANGELOG.md

Append a new section to `~/Workspace/<project-name>/CHANGELOG.md`. Create the file if it doesn't exist.

Format:

```markdown
## <RELEASE_NAME> — <YYYY-MM-DD>

### Project changes (<project-name>)
- <bullet per meaningful commit from project log>

### Shared library changes
- <bullet per meaningful commit from shared log, or "No changes" if none>
```

Use commit messages from Step 2. Keep bullets concise. If a commit has no description, write "Minor update".

## Step 4 — Commit CHANGELOG in Project Repo (if needed)

**jj:** jj auto-snapshots, so the edit is already in `@`.
- If `@` has no description: `jj describe -m "Release $RELEASE_NAME"`
- If `@` already has a description and CHANGELOG.md isn't in its diff, create a child commit:
  ```bash
  jj new -m "Release $RELEASE_NAME: update CHANGELOG"
  # re-write CHANGELOG.md so it lands in this new commit
  ```

**git:**
```bash
cd ~/Workspace/<project-name>
git add CHANGELOG.md
git commit -m "Release $RELEASE_NAME: update CHANGELOG"
```

## Step 5 — Push Both Repos

For each repo:
1. First commit any outstanding working-copy changes
2. Then push if there are unpushed commits

Use the VCS detected for each repo.

**Step 5a — Commit outstanding working-copy changes (if any):**

jj:
```bash
# Check for uncommitted changes in @
PENDING=$(jj diff --name-only 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PENDING" -gt 0 ]]; then
  DESC=$(jj log --revisions '@' --no-graph --template 'description' 2>/dev/null)
  if [[ -z "$DESC" ]]; then
    jj describe -m "Release $RELEASE_NAME: pre-release changes"
  fi
  # @ now has a description; jj will treat it as a proper commit
fi
```

git:
```bash
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  git add -A
  git commit -m "Release $RELEASE_NAME: pre-release changes"
fi
```

**Step 5b — Check for unpushed commits:**

jj:
```bash
jj git fetch 2>/dev/null || true
jj log --revisions 'remote_bookmarks()..bookmarks()' --no-graph 2>/dev/null | grep -c '.' || echo "0"
```

git:
```bash
git fetch 2>/dev/null || true
git log @{u}..HEAD --oneline 2>/dev/null | wc -l
```

**Step 5c — Push if changes exist:**

jj:
```bash
jj bookmark set main -r @
jj git push --all
```

git:
```bash
git push
```

If push fails because the remote is ahead, report to the user — do not force push.

**Apply to both repos:**
- `~/Workspace/<project-name>/` — use `$PROJECT_VCS`
- `~/Workspace/shared/` — use its independently detected VCS; always check for both uncommitted changes AND unpushed commits

## Step 6 — Create Tags

**jj:**
```bash
cd ~/Workspace/<repo>
jj tag set "$RELEASE_NAME" -r @
jj git push --all   # pushes tags along with bookmarks
```

**git:**
```bash
cd ~/Workspace/<repo>
git tag "$RELEASE_NAME"
git push origin "$RELEASE_NAME"
```

Apply to both repos, using each repo's own detected VCS.

## Step 7 — Report to User

```
Release: <RELEASE_NAME>  (VCS: <jj|git>)

Project repo (~/Workspace/<project-name>):
  ✓ CHANGELOG.md updated
  ✓ Pushed to GitHub  (or: No changes to push)
  ✓ Tagged: <RELEASE_NAME>

Shared repo (~/Workspace/shared):
  ✓ Pushed to GitHub  (or: No changes to push)
  ✓ Tagged: <RELEASE_NAME>
```

## Error Handling

| Situation | Action |
|-----------|--------|
| Project dir not found or no `.jj`/`.git` | Stop, report error |
| Push fails (remote ahead) | Stop, show error, suggest fetch + merge |
| Tag already exists | Script handles name collision automatically |
| CHANGELOG.md already has this release section | Skip writing, warn user |
| `shared/` has no `.jj` or `.git` | Skip shared repo, warn user |
