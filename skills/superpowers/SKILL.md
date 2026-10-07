---
name: superpowers
description: "Use for software development work when you want the Superpowers workflow in Codex: route the task through the bundled 14 workflow skills for brainstorming, planning, TDD, debugging, code review, execution, verification, git worktrees, and branch completion."
disable-model-invocation: true
---

# Superpowers for Codex

Use this skill as a coordinator for coding work. It adapts the Claude Code `superpowers` plugin into a normal Codex skill by bundling the upstream 14 skill documents as local references.

This skill is for software development tasks only. It is not a plugin and does not auto-run. When it is used, follow the workflow below and load only the relevant reference files.

## Core Rule

For coding work, assume one of the bundled Superpowers workflow skills probably applies. Before acting, choose the most relevant skill reference and follow it.

User instructions, `AGENTS.md`, and project docs override Superpowers guidance.

## Codex Adaptation

Read [`references/codex-adaptation.md`](references/codex-adaptation.md) once when first using this skill in a session. It explains how to translate Claude-specific ideas like `Skill`, `TodoWrite`, and subagents into Codex behavior.

## Default Workflow

Use this flow unless the user explicitly wants something narrower:

1. If the user is still shaping the work, read `brainstorming/SKILL.md`.
2. Once requirements are clear and the task is multi-step, read `writing-plans/SKILL.md`.
3. Before implementation, read `test-driven-development/SKILL.md`.
4. If you hit a bug, failure, or strange behavior, read `systematic-debugging/SKILL.md`.
5. Before claiming success, read `verification-before-completion/SKILL.md`.
6. Before wrapping up a branch or handing off, read `finishing-a-development-branch/SKILL.md`.

## Skill Router

Choose the smallest relevant subset:

| Situation | Reference to load |
|---|---|
| Starting a coding task and want Superpowers discipline | `references/upstream-skills/using-superpowers/SKILL.md` |
| Clarifying or designing a feature before coding | `references/upstream-skills/brainstorming/SKILL.md` |
| Turning approved requirements into implementation steps | `references/upstream-skills/writing-plans/SKILL.md` |
| Implementing a feature or bugfix | `references/upstream-skills/test-driven-development/SKILL.md` |
| Debugging failing tests, build errors, regressions, or runtime bugs | `references/upstream-skills/systematic-debugging/SKILL.md` |
| Running a written plan in the current session | `references/upstream-skills/executing-plans/SKILL.md` |
| Breaking independent work into parallel tracks | `references/upstream-skills/dispatching-parallel-agents/SKILL.md` |
| Using isolated branches or workspaces | `references/upstream-skills/using-git-worktrees/SKILL.md` |
| Requesting review before merge or after a major task | `references/upstream-skills/requesting-code-review/SKILL.md` |
| Responding to review comments | `references/upstream-skills/receiving-code-review/SKILL.md` |
| Final proof before saying work is done | `references/upstream-skills/verification-before-completion/SKILL.md` |
| Completing, merging, or preserving a finished branch | `references/upstream-skills/finishing-a-development-branch/SKILL.md` |
| Creating or revising skills | `references/upstream-skills/writing-skills/SKILL.md` |
| Subagent-oriented plan execution | `references/upstream-skills/subagent-driven-development/SKILL.md` |

## Codex-Specific Notes

- Treat the upstream files as workflow references, not literal host integration instructions.
- Where an upstream skill says to use a Claude-only feature, adapt it using [`references/codex-adaptation.md`](references/codex-adaptation.md).
- If a skill assumes subagents and this Codex environment does not provide them, use the same sequencing and review discipline in a single session.
- Keep the Superpowers discipline, but do not violate higher-priority repository instructions.

## Bundled Upstream Source

The upstream 14 skill documents are bundled under `references/upstream-skills/` so this workspace skill is self-contained and does not depend on Claude's plugin cache.
