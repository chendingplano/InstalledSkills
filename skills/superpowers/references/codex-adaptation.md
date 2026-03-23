# Codex Adaptation

This skill package bundles the upstream Claude Code Superpowers skill documents. Many of them mention Claude-specific tools or runtime behavior. In Codex, use the intent of those instructions and adapt the mechanics as follows.

## Tool and Runtime Mapping

| Upstream concept | In Codex |
|---|---|
| `Skill` tool | Read the referenced local `SKILL.md` file directly |
| `TodoWrite` | Use the plan tool when helpful, or track progress explicitly in the conversation while executing |
| SessionStart hook | No automatic hook exists; the user or agent invokes this skill explicitly |
| Subagents | Use available parallelization tools if appropriate; otherwise run the same workflow sequentially in one session |
| `Task` tool for separate workers | Use parallel tooling only when safe and available; otherwise decompose and execute directly |

## What to Preserve

- The workflow discipline
- TDD-first behavior when appropriate
- Root-cause debugging before fixes
- Verification before claiming completion
- Clear planning before multi-step implementation
- Structured code review and branch completion

## What Not to Preserve Literally

- Claims that the skill must auto-run at session start
- Instructions that depend on Claude-only hooks or tools
- Any instruction that conflicts with Codex system or repository instructions

## Practical Pattern

1. Announce that you are using the `superpowers` skill for the task.
2. Read the most relevant bundled upstream skill file.
3. Apply its workflow in Codex terms.
4. Read additional bundled skills only as the task expands.

## Suggested Minimal Sequence

For a typical feature:

1. `brainstorming`
2. `writing-plans`
3. `test-driven-development`
4. `requesting-code-review`
5. `verification-before-completion`
6. `finishing-a-development-branch`

For a typical bug:

1. `systematic-debugging`
2. `test-driven-development`
3. `verification-before-completion`

## Important Limitation

This package gives Codex the Superpowers content, not the Claude plugin lifecycle. The main missing behavior is automatic activation, not the workflow itself.
