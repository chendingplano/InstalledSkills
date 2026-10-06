---
name: project-installer
description: Install a project or a skill from a URL. Triggers when the user says "install this project" or "install this skill" followed by a URL, with an optional project or skill name.
---

# Project Installer

## Environment

The environment uses:
- Nix 
- Bun 

## Workflow

### 1. Gather required info

- **URL**: required (from user message)
- **Project or Skill name**: optional — if not provided, derive the name from the open-source project.

### 2. Install Directory
- If it is to install a project, install it in '~/Workspace/ThirdParty-2/<project-name>/' unless users specify the directory. 
- If it is to install a skill, install it in '~/Workspace/.agents/skills/<skill-name>/'.

If the directory exists → inform the user and **stop**. Do not overwrite.

### 3. Detect project type from URL/README

Before installing, fetch the repo's README or config files to determine language and tooling:

- Use `WebFetch` on `https://raw.githubusercontent.com/<owner>/<repo>/main/README.md` (try `/master/README.md` if main fails)
- Also check `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml` at similar raw URLs

Detect: language (Go, Python, Node/TypeScript, Rust, etc.), package manager (npm → replace with bun), and build/run commands from the README.

### 4. Python Project

If it is a Python project or needs to run Python programs, make sure:
- We use uv
- Create a virtual environment for this project (i.e., create .venv)

### 5. Create mise.toml

If it is to install a skill, do not create `mise.toml`.

Write `mise.toml` to the project directory. Follow these rules:

- Use `bun` instead of `npm` / `npx` for Node/TypeScript projects
- Use `.venv` for Python (create with `python3 -m venv .venv`, activate in commands)
- Include all applicable commands: from installing, setting up, to daily operations
- Make sure mise.toml also documents how to sync the source code with the official Git repo

### 6. Environment Variables
- If the project needs environment variables, define them in mise.local.toml.
- Do not modify ~/.zshrc. In my system, ~/.zshrc is not used. It is moved to ~/.config/zsh/.zshrc. Note that ~/.config/zsh/.zshrc is read-only. Its content is determined by Nix.

### 7. Create USER_MANUAL.md

Write `USER_MANUAL.md` for this project and save it to the project directory. The document should include:
- Quick start
- Quick reference (in form of tables) to all mise commands
- Sync source code with the official Git repo
- Daily operations
- (Add whatever appropriated)

IMPORTANT: explain all the commands, steps, etc. Users know nothing about the project.
Well documenting is very important!

Note that if the original project already have 'USER_MANUAL.dm', use 'USER_MANUAL_NEW.md'.

### 8. Confirm to user

Report:
- Install location
- Commands available via `mise run <command>`
- Any manual steps needed (e.g., set env vars, API keys, symlinks)

## Edge Cases

- **Project already exists**: inform the user and stop — do not overwrite
- **Private repo**: warn that git clone may require authentication
- **No README**: infer language from file extensions in the repo (check GitHub's language stats or root files)
- **Monorepo**: note the relevant subdirectory; adjust mise.toml paths accordingly
- **npm scripts in package.json**: translate all `npm run <x>` → `bun run <x>`, `npx <x>` → `bunx <x>`
