---
name: superpowers
description: Reference documentation for the Superpowers Claude Code plugin — a suite of 14 coding workflow skills (TDD, git worktrees, code review, planning, debugging, subagent orchestration) delivered via a SessionStart hook. Install with `claude plugin install superpowers@superpowers-marketplace`.
---

# Overview

This skill is available in Claude Code by default. It is installed in `~/.claude/plugins/marketplaces/`
superpowers-marketplace. Its README.md is copied to README.md in this
directory for reference.

## Skills

Superpowsers is a plugin. It uses a number of skills (
`https://github.com/obra/superpowers/tree/main/skills`).
As of this writing, there are 14 skills, installed in
`~/.claude/plugins/cache/superpowers/skills`.
They came bundered with the plugin when you ran "claude plugin install".

Superpowers is just a delivery mechnism for the skills + the SessionStart
hook that activates them. Once activated and a session starts, superpowers
kicks in, using these skills to guide
your software development.

## Superpowers Marketplace

Superpowers marketplace is a plugin catalog - a separate repo (
`https://github.com/obra/superpowers-marketplace`) that lists available plugins
you can install.
Think of it like an app store registry. Right now it has 3 plugins:

| Plugin | Description |
| -------- | ------------- |
| superpowers (Core) | The 14 coding skills |
| elements-of-style | Writing guidance based on Strunk's Elements of Style |
| superpowers-developing-for-claude-code | Skills for developing Claude Code plugins/skills/MCP servers |

## Installations

**Install superpowers**
```bash
  claude plugin install superpowers@superpowers-marketplace
```

**Install elements-of-style**
```bash
  claude plugin install elements-of-style@superpowers-marketplace
```

**Install developing-for-claude-code**
```bash
  claude plugin install developing-for-claude-code@superpowers-marketplace
```

**Automatic activation**
You don't need to say anything special.

The superpowers plugin uses a SessionStart hook that fires automatically at the beginning of every new session (and on resume/clear/compact). It injects the core using-superpowers skill into Claude's context with high priority (<EXTREMELY_IMPORTANT> tags).

**Breakdown**
| Category	| Skills	| Coding-specific? |
|-----------|---------|------------------|
| TDD & Testing	| test-driven-development, verification-before-completion	| Yes |
| Git Workflow	| using-git-worktrees, finishing-a-development-branch	| Yes |
| Code Review	| requesting-code-review, receiving-code-review	| Yes |
| Dev Execution	| subagent-driven-development, executing-plans, dispatching-parallel-agents	| Yes |
| Planning	| brainstorming, writing-plans	| Yes (TDD-centric plans) |
| Debugging	| systematic-debugging	| Yes |
| Meta	| using-superpowers, writing-skills	| Neutral |

The entire pipeline assumes: Brainstorm → Plan (with TDD) → Execute (with tests) → Code Review → Git merge/PR. Every skill references tests, git, commits, and production code.

**What happens in practice**

1. On session start — the using-superpowers skill is automatically loaded into context, which tells Claude to check for relevant skills before taking any action
2. During the session — Claude uses the Skill tool to load specific skills on-demand (e.g., test-driven-development, brainstorming, systematic-debugging) when they're relevant to what you're doing
3. The skill itself says: "If you think there is even a 1% chance a skill might apply, you ABSOLUTELY MUST invoke the skill"

**Enable/Disable Superpower**

Superpowers is a coding-specific skill. It's a software development workflow plugin, not a general-purpose tool. It adds values only when you are doing software development. For other tasks, you should choose the right skills/tools. Superpowers won't help there and may actually add noise by injecting irrelevant coding-workflow instructions into every session.

For this reason, you need to enable/disable superpowers manually!

**Enable**
```bash
claude plugin enable superpowers
claude plugin enable elements-of-style
claude plugin enable superpowers-developing-for-claude-code
```

**Disable**
```bash
claude plugin disable superpowers
claude plugin disable elements-of-style
claude plugin disable superpowers-developing-for-claude-code
```

**One Caveat**

This is prompt-based behavior, not hard-coded logic. If you find Claude isn't using the skills in a particular session, saying something like "check your superpowers skills" or "use the brainstorming skill first" would nudge it. But in general, the SessionStart injection should make it automatic.
