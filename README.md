# Claude Code Skills Repository

**Central Git repository for managing skills across all coding assistants.**

## Overview

This repository serves as the **single source of truth** for all coding assistant skills in your development environment. Instead of maintaining separate copies of skills for each AI assistant (Claude Code, Qwen Code Companion, Codex, etc.), this central repository uses **symbolic links** to share skills across all tools.

### Key Principles

1. **One Git Repository** — All skills versioned in `~/Workspace/.agents/skills/`
2. **No Duplication** — Each assistant links to this central repo via symlinks
3. **Universal Access** — Update once, available to all coding assistants
4. **Assistant-Specific Setup** — Each tool has its own symlink structure

## Directory Structure

```
.agents/skills/
├── README.md           # This file
├── SKILL.md            # Skills documentation guide
├── SKILLINDEX.md       # Complete index of available skills
└── <skill-name>/       # Individual skill directories
    ├── SKILL.md        # Skill-specific documentation
    └── ...             # Skill implementation files
```

## Available Skills

| Skill | Description |
|-------|-------------|
| `algorithmic-art` | Create generative art using p5.js with seeded randomness and interactive parameters |
| `allium` | LLM-native language for intent alongside implementation |
| `brand-guidelines` | Apply Anthropic brand colors, typography, and style to artifacts |
| `canvas-design` | Create visual art, posters, and designs as .png/.pdf using design philosophy |
| `doc-coauthoring` | Structured workflow for co-authoring docs, proposals, specs, and decision docs |
| `docx` | Create, read, edit or manipulate Word documents |
| `frontend-design` | Create distinctive, production-grade frontend interfaces avoiding generic AI aesthetics |
| `intent-layer` | Set up hierarchical AGENTS.md files for codebases |
| `internal-comms` | Write internal communications: status reports, 3P updates, newsletters, FAQs |
| `mcp-builder` | Guide for creating MCP servers to integrate external APIs/services |
| `pdf` | Read, merge, split, create, OCR PDF files |
| `pptx` | Create, read, edit PowerPoint presentations |
| `skill-creator` | Guide for creating and updating Claude skills |
| `slack-gif-creator` | Create animated GIFs optimized for Slack emoji and messages |
| `theme-factory` | Apply professional font/color themes to slides, docs, HTML, and other artifacts |
| `ui-ux-pro-max` | UI/UX design intelligence (styles, palettes, stacks) |
| `web-artifacts-builder` | Build multi-component React/Tailwind/shadcn artifacts for claude.ai |
| `webapp-testing` | Test local web apps using Playwright with screenshots and browser logs |
| `xlsx` | Create, read, edit spreadsheets |

See [`SKILLINDEX.md`](./SKILLINDEX.md) for the complete index.

---

## Setup by Coding Assistant

Each coding assistant has its own skill directory structure. Use the appropriate setup commands below for your tool.

### 1. Qwen Code Companion

Qwen Code loads skills from `.qwen/skills/` directories (both global and workspace-level).

#### Global Setup (All Workspaces)

```bash
# Create global skills directory if it doesn't exist
mkdir -p ~/.qwen/skills

# Create symlinks for all skills
cd ~/Workspace/.agents/skills/
for skill in */; do
    ln -s "$(pwd)/${skill}" ~/.qwen/skills/"${skill}"
done
```

#### Workspace-Level Setup

```bash
# From your workspace root
cd ~/Workspace/
mkdir -p .qwen/skills

# Create relative symlinks (recommended for portability)
for skill in .agents/skills/*/; do
    ln -s "../../.agents/skills/$(basename "${skill}")" .qwen/skills/"$(basename "${skill}")"
done
```

#### Verify Setup

```bash
ls -la ~/.qwen/skills/
ls -la ~/Workspace/.qwen/skills/
```

All symlinks should point to `~/Workspace/.agents/skills/<skill-name>`.

#### Custom Skills Directory

To use a different skills directory for Qwen Code:

**Option A: Environment Variable**
```bash
export QWEN_SKILLS_DIR="/path/to/your/skills"
# Add to ~/.zshrc or ~/.bashrc for persistence
```

**Option B: Workspace Configuration**
Add to `.qwen/QWEN.md`:
```markdown
## Skills Configuration
Custom skills directory: `/path/to/your/skills`
```

---

### 2. Claude Code

Claude Code loads skills from `~/.claude/skills/` (global) and `<workspace>/.claude/skills/` (workspace-level).

#### Global Setup (All Workspaces)

```bash
# Create global skills directory if it doesn't exist
mkdir -p ~/.claude/skills

# Create symlinks for all skills
cd ~/Workspace/.agents/skills/
for skill in */; do
    ln -s "$(pwd)/${skill}" ~/.claude/skills/"${skill}"
done
```

#### Workspace-Level Setup

```bash
# From your workspace root
cd ~/Workspace/
mkdir -p .claude/skills

# Create relative symlinks (recommended for portability)
for skill in .agents/skills/*/; do
    ln -s "../../.agents/skills/$(basename "${skill}")" .claude/skills/"$(basename "${skill}")"
done
```

#### Verify Setup

```bash
ls -la ~/.claude/skills/
ls -la ~/Workspace/.claude/skills/
```

All symlinks should point to `~/Workspace/.agents/skills/<skill-name>`.

#### Refresh Skills

If Claude Code doesn't pick up new skills, restart the session or run:
```bash
# Touch the skills directory to trigger reload
touch ~/.claude/skills/
```

---

### 3. Codex (OpenAI)

Codex uses the OpenAI Codex CLI configuration for custom instructions and skills.

#### Setup via Codex CLI

```bash
# Create Codex skills directory
mkdir -p ~/.codex/skills

# Create symlinks for all skills
cd ~/Workspace/.agents/skills/
for skill in */; do
    ln -s "$(pwd)/${skill}" ~/.codex/skills/"${skill}"
done
```

#### Workspace-Level Setup

```bash
# From your workspace root
cd ~/Workspace/
mkdir -p .codex/skills

# Create relative symlinks
for skill in .agents/skills/*/; do
    ln -s "../../.agents/skills/$(basename "${skill}")" .codex/skills/"$(basename "${skill}")"
done
```

#### Configure Codex Rules

Add to `~/.codex/config.json` or project-level `.codex/config.json`:

```json
{
  "skills": {
    "directory": "~/.codex/skills"
  }
}
```

#### Verify Setup

```bash
ls -la ~/.codex/skills/
cat ~/.codex/config.json
```

---

## Setup Scripts

### Quick Setup for All Assistants

Run this script to set up symlinks for all coding assistants at once:

```bash
#!/bin/bash
# setup-all-skills.sh

SKILLS_SOURCE="$HOME/Workspace/.agents/skills"

echo "Setting up skills from: $SKILLS_SOURCE"

# Qwen Code
echo "Setting up Qwen Code skills..."
mkdir -p ~/.qwen/skills
for skill in "$SKILLS_SOURCE"/*/; do
    ln -sf "$skill" ~/.qwen/skills/$(basename "$skill")
done

# Claude Code
echo "Setting up Claude Code skills..."
mkdir -p ~/.claude/skills
for skill in "$SKILLS_SOURCE"/*/; do
    ln -sf "$skill" ~/.claude/skills/$(basename "$skill")
done

# Codex
echo "Setting up Codex skills..."
mkdir -p ~/.codex/skills
for skill in "$SKILLS_SOURCE"/*/; do
    ln -sf "$skill" ~/.codex/skills/$(basename "$skill")
done

echo "✓ All skills set up successfully!"
```

Save as `setup-all-skills.sh` and run:
```bash
chmod +x setup-all-skills.sh
./setup-all-skills.sh
```

### Remove All Skills

```bash
#!/bin/bash
# remove-all-skills.sh

echo "Removing skill symlinks..."

# Qwen Code
rm -rf ~/.qwen/skills/*

# Claude Code
rm -rf ~/.claude/skills/*

# Codex
rm -rf ~/.codex/skills/*

echo "✓ All skill symlinks removed!"
```

---

## Mise Tasks

All setup, management, and git workflow commands are available as [mise](https://mise.jdx.dev/) tasks defined in `mise.toml`. Run any task from the `~/Workspace/.agents/skills/` directory.

```bash
# List all available tasks
mise tasks
```

### Setup

| Task | Description |
|------|-------------|
| `mise run setup-all` | Set up global symlinks for **all** assistants at once |
| `mise run setup-claude-global` | Create global Claude Code symlinks (`~/.claude/skills/`) |
| `mise run setup-claude-workspace` | Create workspace-level Claude Code symlinks |
| `mise run setup-qwen-global` | Create global Qwen Code symlinks (`~/.qwen/skills/`) |
| `mise run setup-qwen-workspace` | Create workspace-level Qwen Code symlinks |
| `mise run setup-codex-global` | Create global Codex symlinks (`~/.codex/skills/`) |
| `mise run setup-codex-workspace` | Create workspace-level Codex symlinks |

### Verify & Refresh

| Task | Description |
|------|-------------|
| `mise run verify` | Show symlink state for all assistants (global + workspace) |
| `mise run verify-source` | List all skills in the source repository |
| `mise run refresh-claude` | Touch Claude skills directory to trigger reload |

### Remove & Fix

| Task | Description |
|------|-------------|
| `mise run remove-all` | Remove all skill symlinks from all assistants |
| `mise run fix-symlinks` | Rebuild all global symlinks (use after moving workspace) |

### Skill Management

| Task | Description |
|------|-------------|
| `mise run skill-create <name>` | Scaffold a new skill directory with a blank `SKILL.md` |
| `mise run skill-link <name>` | Create symlinks for a skill across all assistants |
| `mise run skill-unlink <name>` | Remove symlinks for a skill from all assistants |

### Git Workflow

| Task | Description |
|------|-------------|
| `mise run git-status` | Show `git status` in the skills repository |
| `mise run git-add <name>` | Stage a skill + `SKILLINDEX.md` + `README.md` |
| `mise run git-push` | Push committed changes to remote |

### Example: Adding a New Skill with Mise

```bash
cd ~/Workspace/.agents/skills/

# 1. Scaffold the skill directory and blank SKILL.md
mise run skill-create my-skill

# 2. Edit the skill files, then create symlinks for all assistants
mise run skill-link my-skill

# 3. Update SKILLINDEX.md and README.md, then stage and commit
mise run git-add my-skill
git commit -m "feat: Add my-skill skill"
mise run git-push
```

### Example: Removing a Skill with Mise

```bash
cd ~/Workspace/.agents/skills/

mise run skill-unlink my-skill
git rm -r my-skill/
# Update SKILLINDEX.md and README.md, then commit
git commit -m "chore: Remove my-skill skill"
mise run git-push
```

---

## Managing Skills

### Adding a New Skill

1. **Create the skill directory** in this repository:
   ```bash
   cd ~/Workspace/.agents/skills/
   mkdir <skill-name>
   ```

2. **Add required files**:
   - `SKILL.md` - Skill documentation and usage guide
   - Skill implementation files

3. **Update symlinks** for all assistants:
   ```bash
   # Qwen Code
   ln -s "$(pwd)/<skill-name>" ~/.qwen/skills/<skill-name>
   ln -s "../../.agents/skills/<skill-name>" ~/Workspace/.qwen/skills/<skill-name>

   # Claude Code
   ln -s "$(pwd)/<skill-name>" ~/.claude/skills/<skill-name>
   ln -s "../../.agents/skills/<skill-name>" ~/Workspace/.claude/skills/<skill-name>

   # Codex
   ln -s "$(pwd)/<skill-name>" ~/.codex/skills/<skill-name>
   ln -s "../../.agents/skills/<skill-name>" ~/Workspace/.codex/skills/<skill-name>
   ```

4. **Update documentation**:
   - Add skill to `SKILLINDEX.md`
   - Add skill to this README's skill table

5. **Commit and push**:
   ```bash
   git add <skill-name>/ SKILLINDEX.md README.md
   git commit -m "feat: Add <skill-name> skill"
   git push
   ```

### Removing a Skill

1. **Remove symlinks** from all assistants:
   ```bash
   # Qwen Code
   rm ~/.qwen/skills/<skill-name>
   rm ~/Workspace/.qwen/skills/<skill-name>

   # Claude Code
   rm ~/.claude/skills/<skill-name>
   rm ~/Workspace/.claude/skills/<skill-name>

   # Codex
   rm ~/.codex/skills/<skill-name>
   rm ~/Workspace/.codex/skills/<skill-name>
   ```

2. **Remove from repository**:
   ```bash
   git rm -r <skill-name>/
   ```

3. **Update documentation**:
   - Remove from `SKILLINDEX.md`
   - Remove from this README's skill table

4. **Commit and push**:
   ```bash
   git commit -m "chore: Remove <skill-name> skill"
   git push
   ```

### Updating a Skill

1. Make changes to the skill in `.agents/skills/<skill-name>/`
2. Test the skill with your coding assistant
3. Commit and push:
   ```bash
   git add <skill-name>/
   git commit -m "fix|feat|docs: <description>"
   git push
   ```

Changes are immediately available to all assistants (symlinks point to the updated source).

---

## Using Skills

### Automatic Invocation (Recommended)

Skills are invoked **automatically** when relevant to your task. Simply describe what you want:

| Instead of... | Say... |
|--------------|--------|
| "Use the PDF skill" | "Convert this PDF to text" |
| "Use xlsx skill" | "Read this Excel file" |
| "Use frontend-design" | "Create a landing page with hero section" |

### Manual Invocation

To explicitly request a skill:

```
"Use the `pdf` skill to merge these files"
"Invoke the `xlsx` skill for this spreadsheet"
```

---

## Troubleshooting

### Skill Not Found

1. Verify symlink exists:
   ```bash
   ls -la ~/.qwen/skills/      # Qwen Code
   ls -la ~/.claude/skills/    # Claude Code
   ls -la ~/.codex/skills/     # Codex
   ```

2. Check skill is in source repo:
   ```bash
   ls ~/Workspace/.agents/skills/
   ```

3. Recreate symlink if broken:
   ```bash
   rm ~/.qwen/skills/<skill-name>
   ln -s ~/Workspace/.agents/skills/<skill-name> ~/.qwen/skills/<skill-name>
   ```

4. Restart your coding assistant

### Broken Symlinks After Moving Workspace

If you move the `~/Workspace` directory, update symlinks:

```bash
# Remove all symlinks
rm ~/.qwen/skills/*
rm ~/.claude/skills/*
rm ~/.codex/skills/*

# Re-run setup script
./setup-all-skills.sh
```

### Skill Not Auto-Invoking

1. Ensure task matches skill's purpose
2. Try explicit invocation: "Use the `<skill>` skill to..."
3. Check skill's `SKILL.md` for trigger patterns
4. Verify skill has valid `SKILL.md` file

### Permission Issues

On macOS, if symlinks fail:
```bash
# Check System Preferences > Security & Privacy > Full Disk Access
# Ensure terminal has full disk access
```

---

## Best Practices

### For Skill Users

1. **Let assistants auto-invoke skills** — No need for explicit skill commands
2. **Check SKILLINDEX.md** — See what skills are available
3. **Read individual SKILL.md** — Each skill has detailed usage docs
4. **Report issues** — Create an issue in this repo if a skill doesn't work

### For Skill Developers

1. **Follow the skill template** — See existing skills for structure
2. **Document thoroughly** — Clear `SKILL.md` with examples
3. **Test before committing** — Verify skill works with multiple assistants
4. **Version carefully** — Skills affect all assistants and workspaces
5. **Keep skills focused** — Each skill should do one thing well

### For Multi-Assistant Users

1. **Keep symlinks in sync** — Run setup script after adding skills
2. **Test across assistants** — Skills may behave differently in each tool
3. **Document assistant-specific behavior** — Note any differences in `SKILL.md`

---

## Git Workflow

This repository is a standalone Git repo. When making changes:

```bash
cd ~/Workspace/.agents/skills/

# Check status
git status

# Stage changes
git add <skill-name>/ SKILLINDEX.md README.md

# Commit with clear message
git commit -m "<type>: <description>"

# Push to remote
git push
```

### Commit Message Types

| Type | Description |
|------|-------------|
| `feat:` | New skill or major enhancement |
| `fix:` | Bug fix in existing skill |
| `docs:` | Documentation updates |
| `refactor:` | Code restructuring (no behavior change) |
| `chore:` | Maintenance tasks |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              Central Skills Repository                      │
│           ~/Workspace/.agents/skills/                       │
│  (Git-managed, single source of truth)                      │
│                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │  pdf/     │ │  xlsx/    │ │  ...      │                  │
│  └───────────┘ └───────────┘ └───────────┘                  │
└─────────────────────────────────────────────────────────────┘
         │              │              │
         │ (symlink)    │ (symlink)    │ (symlink)
         ▼              ▼              ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Qwen Code    │ │  Claude Code  │ │    Codex      │
│  ~/.qwen/     │ │  ~/.claude/   │ │  ~/.codex/    │
│  skills/      │ │  skills/      │ │  skills/      │
└───────────────┘ └───────────────┘ └───────────────┘
```

---

## License

Skills in this repository may have individual licenses. Check each skill's directory for specific licensing terms.

---

**Maintained by:** Chen Web Development  
**Location:** `~/Workspace/.agents/skills/`  
**Assistants:** Qwen Code Companion, Claude Code, Codex
