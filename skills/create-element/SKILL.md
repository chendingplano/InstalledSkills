---
name: create-element
description: Use when creating or extending a configurable, reusable Web Page Interpreter (WPI) frontend element, its JSON descriptor attributes, or its code-module document, from primitive buttons and inputs to complex lists with data operations. Also applies when continuing an element's human design review or implementing its approved document.
---

# Create element

An element is a highly reusable frontend component controlled by a JSON descriptor.
It can be a primitive button or a composite list with paging, search, editing and data
operations. Deliver its document first, obtain human designer approval through revisions,
then implement it as a reusable module. This workflow also applies to existing elements.

## Read the context

Resolve paths below from the workspace root, normally `~/Workspace`:

- `KnowledgeStore/doc-repo/devdocs/202610/2026102601-devdoc-web-page-interpreter.md`:
  read **Elements**, **Code modules**, **Lists**, **Input doc and data binding**,
  **Actions**, and **Validation and errors**. Follow the current design, including
  its distinction between implemented and future features.
- `KnowledgeStore/doc-repo/code_modules/interpreter-input.md`: the reference for
  document completeness, attribute contracts, behavior and Properties panel grouping.
  Match its depth where relevant; do not copy input-specific rules to other elements.
- The user's supplied element document, if any. Edit it in place when already in
  `code_modules/`; if elsewhere, use its content to create the canonical document there
  and retain a source link without deleting the original.
- Project instructions and existing element code, registries, validators and related
  module documents. Read `ChenWeb/CLAUDE.md` before inspecting or changing ChenWeb.

If a reference moved, find its current location before asking the user. Check repository
status before edits and disclose unrelated changes. Reuse an existing module when its
capabilities fit; several element classes may share one module.

## 1. Write or update the element document

Store the canonical document in `KnowledgeStore/doc-repo/code_modules/`. Keep an
existing filename and identity. For a new module, check for filename and module-ID
collisions and use the local naming convention, normally `interpreter-<slug>.md`.
If `code_modules/` is missing, report the workspace configuration error rather than
inventing another location.

Use [references/element-document.md](references/element-document.md) as the outline
and configuration coverage checklist. Cover the variables users need to control the
element's appearance and behavior across different pages, rather than hard-coding one
page's choices. For each relevant area, specify supported configuration or explain why
it is inapplicable or deferred. Keep a primitive element small; make a complex list's
data and interaction contracts explicit. Ask only about consequential unresolved choices;
write reasonable, clearly marked assumptions into the draft meanwhile.

Each attribute needs an exact JSON path, type, allowed values, default or absence
semantics, behavior, validation and interaction with other settings. Group related
attributes in the document and define their Properties panel groups and order. Grouping
is an information design decision: it does not automatically create nested JSON objects.
Preserve the current schema's flat attributes; use nested structures where an explicit
contract calls for them, such as `validation`, `columns` or per-row settings.

Assign a reasonable default to every configurable attribute that can have one, and put
it in both the document and the class descriptor's `default_value`. Use valid, predictable
values that make the element usable with minimal configuration. Leave an attribute without
a concrete default only when no reasonable value exists, such as a page-specific binding
or action; document the reason and whether the instance must supply it. Do not invent
bindings, data sources or actions merely to fill defaults. Preserve deliberate existing
defaults unless the approved change calls for different ones.

Preserve WPI's contract:

- A class has a `descriptor_id` and names its renderer with `code_module_id`.
  Instances live in pages' panels and keep complete class copies; later class edits
  affect newly placed instances only. Document how old copies behave with new module code.
- Class attribute definitions have `help_tip`, optional `default_value`, and optional
  `instance_modifiable`. `default_value: null` requires an instance value; omission
  means optional with no default. `instance_modifiable: false` fixes a non-null value
  and forbids an instance override. Do not confuse these rules with a nullable data value.
- Action-valued attributes have no concrete defaults and cannot be class-fixed. Declare
  them required with null or optional by omission; write action instances in the page.
  Keep descriptors JSON data, with no embedded JavaScript, Svelte or executable callbacks.
- Spell out precedence, including page-level `binding_mode` where applicable, module
  fallbacks and class-fixed values. Do not imply that future Page Styles already work.
- Separate proposed, implemented and unsupported capabilities. Unsupported class
  attributes must remain visible as warnings under current WPI rules; invalid supported
  values and prohibited overrides must follow the validator's error contract.

Provide valid JSON examples of a class and a page-embedded instance with its class copy.
Mark any abbreviated illustration explicitly; do not present it as a runnable descriptor.

## 2. Human designer review and revision

Save a concrete, reviewable draft before requesting review. Include its path, key
configuration decisions, open questions and a concise summary of changes. Mark it
**Awaiting human design review** and identify its revision so approval has a clear scope.

Ask the user to review it or obtain feedback from the human designers they designate.
Do not contact anyone through email, chat or another external service without explicit
authorization. Agent critique or automated checks can support review but cannot replace
human designer approval.

Revise the same document from feedback, show the changes and resubmit. Repeat until a
human explicitly approves the current document. Silence, an earlier revision's approval,
or the original request to create the element does not approve a new draft. Carry a valid
approval forward across turns; do not ask again if the approved contract is unchanged.

**Before approval, do not implement the element, write its migrations, mutate catalogues
or activate classes.** Read-only feasibility inspection and document examples are allowed.
If review is pending, end with the review request and state that implementation awaits
approval under this skill's required workflow. Record actual approval and its scope;
never invent a reviewer, date or approval. A later material contract change returns to review.

## 3. Implement the approved contract

Once approved, continue implementation without another routine permission request.
Use the owning project's implementation/spec workflow, with the approved element
document as the contract. Inspect current code rather than assuming reference paths or
schema versions are still current.

- Build a reusable frontend module with a stable public interface and descriptor-driven
  behavior. Keep page-specific data and choices in instances. Put genuinely cross-project
  code in `shared/`; project reuse alone does not require moving code there.
- Wire the module into the frontend renderer registry and backend supported-attribute
  registry/validation. In ChenWeb these are normally
  `web/src/lib/wpi/elements/index.ts` and `server/api/wpi/validate.go`. Align editor
  controls, help, conditional fields, reset-to-default and fixed-value display with the doc.
- Register or update `kb.code_modules` with `module_type: element` and the canonical
  `module_doc` filename. Use the `db-migration` skill for schema changes and project
  goose migrations for catalogue seeds. The row/document precede activation; an active
  class requires implemented code and validation. Reuse rows instead of duplicating them.
- **Create or update the element class record in `kb.wpi_descriptors`.** This is required
  in addition to code-module and reusable-module registration. Look up the existing class
  by its stable `descriptor_id` and `kind: element` before writing; update that identity
  by writing a new version, never editing a stored version in place or creating a duplicate
  class identity. Use the project's current descriptor write/versioning
  mechanism and schema. Store the approved class descriptor, its `code_module_id`, attribute
  definitions, help tips, defaults and fixed/modifiable settings. Include a `default_value`
  for every attribute with a reasonable default; record justified exceptions using WPI's
  required-null or optional-omission semantics. Keep the class draft until its module and
  validators support activation. Existing page class copies remain unchanged.
- Use `create-reusable-module` for the reusable-module documentation/catalogue. The WPI
  `kb.code_modules` record and the `kb.reusable_modules` record serve different purposes;
  preserve both identities and link their documents. Extend an existing parent module
  registration when that is the established boundary, as with WPI's input module.
- Honor English/Chinese UI text, text selection, keyboard/touch operation, accessible
  names and errors, and theme/responsive states. Log operations using project conventions
  without logging secret field values. Data actions must honor backend authorization
  and validation; descriptor flags do not grant permissions.

## 4. Verify and finish

Verify observable behavior against the approved contract: defaults, overrides, fixed
attributes, invalid combinations, backward compatibility with old class copies, and
the relevant interactions and error paths. For complex lists, exercise search/paging,
record identity, editing, saving and failure recovery. Run project-required checks and
browser interaction checks where applicable; report any checks blocked by authentication
or unavailable services instead of claiming they passed.

Read back the created or updated `kb.wpi_descriptors` record and verify its identity,
version/status, module reference, attribute coverage and defaults against the approved
document. Check that every missing concrete default has a documented reason, and exercise
an instance that omits defaulted attributes. A migration file or JSON example alone does
not establish that the record exists. If the database is unavailable, report the descriptor
write/read-back as pending rather than claiming element creation is complete.

Update the canonical document with actual files, registration, supported attributes,
implementation status, verification evidence and remaining limits. Keep planned capabilities
distinct from shipped ones. Update affected specs, developer docs and reusable-module
records; identify stale docs and anything deliberately undocumented. Commit only the task's
changes through `jj`, separately in each affected repository, and inspect `jj log` for the
expected linear history. Report the document, implementation, validation and any pending
review or limits.
