---
name: project-installer
description: 'Install open-source projects from GitHub URLs into the workspace. Triggers when the user says "install this project as a [skill or project]" followed by a URL, with an optional project name. If it is "as a skill", install it as a skill and save it to ~/Workspace/.agents/skills/; otherwise install it as a project and save it to ~/Workspace/ThirdParty/.'
---

# Project Installer

## Workflow

### 1. Gather required info

- **URL**: required (from user message)
- **Project name**: required — if not provided, prompt: "What should I name this project?"
- **Type**: ask if not obvious — "Is this a Claude skill or a general project?"
  - Skill → installs to `~/Workspace/.agents/skills/<name>`
  - General → installs to `~/Workspace/ThirdParty/<name>`

### 2. Check if already exists

```bash
ls ~/Workspace/.agents/skills/<name>   # if skill
ls ~/Workspace/ThirdParty/<name>       # if general
```

If directory exists → inform the user and **stop**. Do not overwrite.

### 3. Detect project type from URL/README

Before installing, fetch the repo's README or config files to determine language and tooling:

- Use `WebFetch` on `https://raw.githubusercontent.com/<owner>/<repo>/main/README.md` (try `/master/README.md` if main fails)
- Also check `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml` at similar raw URLs

Detect: language (Go, Python, Node/TypeScript, Rust, etc.), package manager (npm → replace with bun), and build/run commands from the README.

### 4. Create mise.toml

Write `mise.toml` to the project directory. Follow these rules:

- Use `bun` instead of `npm` / `npx` for Node/TypeScript projects
- Use `.venv` for Python (create with `python3 -m venv .venv`, activate in commands)
- Include all applicable commands: from installing, setting up, to daily operations
- Make sure mise.toml also documents how to sync the source code with the official Git repo

### 5. Create OPERATIONS.md

Write `OPERATIONS.md` for this project and save it to the project directory. The document should include:
- Quick start
- Quick reference (in form of tables) to all mise commands
- Sync source code with the official Git repo
- Daily operations
- (Add whatever appropriated)

### 6. Confirm to user

Report:
- Install location
- Tasks available via `mise run <task>`
- Any manual steps needed (e.g., set env vars, API keys, symlinks)

**For skill installs**, also remind the user to create the symlink:
```bash
ln -s ~/Workspace/.agents/skills/<name> ~/.claude/skills/<name>
```

## Edge Cases

- **No project name given**: prompt before doing anything
- **Project already exists**: inform the user and stop — do not overwrite
- **Private repo**: warn that git clone may require authentication
- **No README**: infer language from file extensions in the repo (check GitHub's language stats or root files)
- **Monorepo**: note the relevant subdirectory; adjust mise.toml paths accordingly
- **npm scripts in package.json**: translate all `npm run <x>` → `bun run <x>`, `npx <x>` → `bunx <x>`
