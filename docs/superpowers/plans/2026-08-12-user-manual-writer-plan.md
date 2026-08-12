# User Manual Writer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a reusable skill for writing and modifying accessible, multilingual user manuals in Markdown, Typst, or HTML.

**Architecture:** One focused `SKILL.md` defines trigger conditions, the authoring workflow, output naming, metadata, keyword handling, versioning, and format guidance. No scripts or bundled references are needed because the work is judgment-heavy and the output formats are straightforward.

**Tech Stack:** Markdown skill instructions; Python validation and packaging scripts supplied by `skill-creator`.

---

### Task 1: Initialize the skill scaffold

**Files:**
- Create: `skills/user-manual-writer/SKILL.md`
- Remove: generated example resources that are not needed

- [x] **Step 1: Run the required initializer**

Run: `python3 skills/skill-creator/scripts/init_skill.py user-manual-writer --path skills`

- [x] **Step 2: Replace the template with the audience-centered manual workflow**

Cover creation, modification, multilingual output, format selection, keywords, metadata, versioning, and the Change Log.

- [x] **Step 3: Remove unused example resources**

Keep the skill self-contained without placeholder scripts, references, or assets.

### Task 2: Validate and package

**Files:**
- Create: `dist/user-manual-writer.zip`

- [x] **Step 1: Run quick validation**

Run: `python3 skills/skill-creator/scripts/quick_validate.py skills/user-manual-writer`

- [x] **Step 2: Package the validated skill**

Run: `python3 skills/skill-creator/scripts/package_skill.py skills/user-manual-writer dist`

- [x] **Step 3: Inspect status and package contents**

Run: `git status --short` and `unzip -l dist/user-manual-writer.zip`.

### Task 3: Harden behavior after review

**Files:**
- Modify: `skills/user-manual-writer/SKILL.md`
- Update: `dist/user-manual-writer.zip`

- [x] **Step 1: Forward-test the original skill**

Test defaults, ambiguous source selection, and numeric version generation in fresh read-only agent sessions.

- [x] **Step 2: Fix the discovered behavioral gaps**

Define English and Markdown defaults, exact metadata names and timestamps, absolute storage path, BCP 47 tags, deterministic version generation, versioned filenames, format-specific Change Log headings, and safe source selection.

- [x] **Step 3: Re-run forward tests and package validation**

Verify the same scenarios now follow the revised contract, then rebuild and inspect the package.
