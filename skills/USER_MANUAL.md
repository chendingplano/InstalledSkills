# Awesome Claude Skills — User Manual

This document covers the **19 skills** installed from [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) on 2026-04-12, plus how to manage and sync them going forward.

## Quick Start

Skills are already installed and symlinked. They load automatically when you start a Claude Code session. No additional setup is required.

To verify everything is working:

```bash
cd ~/Workspace/.agents/skills
mise run verify
```

## Installed Skills (from awesome-claude-skills)

| Skill | Description |
|-------|-------------|
| `artifacts-builder` | Build multi-component web artifacts (React, Tailwind, shadcn) |
| `changelog-generator` | Generate changelogs from git history |
| `competitive-ads-extractor` | Extract and analyze competitor ad campaigns |
| `connect` | Connect Claude to external apps via Composio |
| `connect-apps` | Pre-built Composio integrations for SaaS apps |
| `content-research-writer` | Research topics and produce content drafts |
| `developer-growth-analysis` | Analyze developer activity and growth metrics |
| `domain-name-brainstormer` | Brainstorm and check domain name availability |
| `file-organizer` | Organize files by type, date, or custom rules |
| `image-enhancer` | Enhance, resize, and optimize images |
| `invoice-organizer` | Parse and organize invoice documents |
| `langsmith-fetch` | Fetch traces and data from LangSmith |
| `lead-research-assistant` | Research leads and compile prospect profiles |
| `meeting-insights-analyzer` | Analyze meeting transcripts for insights and action items |
| `raffle-winner-picker` | Randomly select raffle winners with verification |
| `skill-share` | Share and export skills between environments |
| `tailored-resume-generator` | Generate tailored resumes for specific job postings |
| `twitter-algorithm-optimizer` | Optimize content for Twitter/X algorithm visibility |
| `video-downloader` | Download videos from various platforms |

### Skipped Entries (not installed)

| Entry | Reason |
|-------|--------|
| `composio-skills` | Contains 500+ individual SaaS automations (not standalone skills) |
| `connect-apps-plugin` | Plugin scaffolding (no SKILL.md) |
| `document-skills` | Umbrella for docx/pdf/pptx/xlsx — already installed individually |
| `template-skill` | Blank template, not a usable skill |

## Mise Commands Reference

All commands run from `~/Workspace/.agents/skills/`.

### Syncing with Upstream

| Command | Description |
|---------|-------------|
| `mise run sync-awesome` | Pull **new** skills from the upstream repo (non-destructive, won't overwrite existing) |
| `mise run sync-awesome-update` | Pull new skills **and** update existing ones from upstream (overwrites local with upstream versions) |

### Symlink Management

| Command | Description |
|---------|-------------|
| `mise run setup-all` | Create global symlinks for all assistants (Claude, Qwen, Codex) |
| `mise run setup-claude-global` | Create global Claude Code symlinks (`~/.claude/skills/`) |
| `mise run setup-claude-workspace` | Create workspace Claude Code symlinks (`~/Workspace/.claude/skills/`) |
| `mise run skill-link <name>` | Create symlinks for a single new skill across all assistants |
| `mise run skill-unlink <name>` | Remove symlinks for a skill from all assistants |
| `mise run fix-symlinks` | Fix broken symlinks after moving workspace |
| `mise run remove-all` | Remove ALL skill symlinks from all assistants |

### Verification

| Command | Description |
|---------|-------------|
| `mise run verify` | Show all symlinks across all assistants (global + workspace) |
| `mise run verify-source` | List all skills in the source directory |

### Skill Creation

| Command | Description |
|---------|-------------|
| `mise run skill-create <name>` | Scaffold a new skill with blank SKILL.md |

### Git Workflow

| Command | Description |
|---------|-------------|
| `mise run git-status` | Show git status in the skills repo |
| `mise run git-add <name>` | Stage a skill + index files for commit |
| `mise run git-push` | Push committed changes to remote |

## Syncing with the Official Repo

To pull the latest skills from [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills):

### Add new skills only (safe, non-destructive)

```bash
cd ~/Workspace/.agents/skills
mise run sync-awesome
# Then create symlinks for any new skills:
mise run setup-all
```

### Update existing + add new skills

```bash
cd ~/Workspace/.agents/skills
mise run sync-awesome-update
mise run setup-all
```

### Manual sync (single skill)

```bash
# Clone to temp
git clone --depth 1 https://github.com/ComposioHQ/awesome-claude-skills.git /tmp/acs

# Copy the skill
cp -r /tmp/acs/<skill-name> ~/Workspace/.agents/skills/

# Create symlinks
cd ~/Workspace/.agents/skills
mise run skill-link <skill-name>

# Clean up
rm -rf /tmp/acs
```

## Daily Operations

### Using a skill in Claude Code

Skills are invoked automatically when Claude detects a relevant task. You can also invoke them explicitly:

```
/skill-name
```

For example: `/changelog-generator`, `/file-organizer`, `/meeting-insights-analyzer`

### Adding a custom skill

1. `mise run skill-create my-skill`
2. Edit `~/Workspace/.agents/skills/my-skill/SKILL.md`
3. `mise run skill-link my-skill`
4. Restart Claude Code session

### Removing a skill

1. `mise run skill-unlink <skill-name>`
2. `rm -rf ~/Workspace/.agents/skills/<skill-name>`
3. Update README.md if needed

## File Structure

```
~/Workspace/.agents/skills/
├── mise.toml              # Task runner configuration
├── README.md              # Skills index (loaded by assistants)
├── USER_MANUAL.md         # This file
├── artifacts-builder/     # Installed skill
│   └── SKILL.md
├── changelog-generator/
│   └── SKILL.md
├── ...                    # (one directory per skill)
```

### Symlink Locations

- **Global:** `~/.claude/skills/<skill>` → `~/Workspace/.agents/skills/<skill>`
- **Workspace:** `~/Workspace/.claude/skills/<skill>` → `../../.agents/skills/<skill>`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Skill not showing in Claude Code | Run `mise run verify` to check symlinks; restart session |
| Broken symlinks after moving files | Run `mise run fix-symlinks` |
| Want to reset all skills | Run `mise run remove-all` then `mise run setup-all` |
| Upstream has new skills | Run `mise run sync-awesome` then `mise run setup-all` |

# Resources

[1] https://github.com/ComposioHQ/awesome-claude-skills/tree/master: it listed many skills.