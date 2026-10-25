# Element document guide

Use this outline when drafting or extending the canonical code-module document. Preserve
useful sections in a supplied document. Scale the coverage to the element: consider every
area below, then document applicable controls and explicit exclusions rather than adding
irrelevant options to a primitive component.

## Document outline

1. **Identity and status.** Code module ID, classes using it, purpose, draft revision,
   design-review status and actual approval when received. Give the intended
   `kb.code_modules` row, marking proposed registration as proposed. Include known frontend
   and backend locations, related WPI design links and reusable-module identity if one exists.
2. **Purpose and behavior.** What it displays or edits, intended reuse, inputs and outputs,
   composition boundary and deliberately excluded capabilities. Explain a typical use in
   language a human designer can review.
3. **Attribute contract.** Logical sections with a table per group. For each attribute give
   its exact JSON path, data type, allowed values/units, default, requiredness, meaning,
   validation and dependencies. Add prose for behaviors a table cannot explain. Document
   class configurability, instance overrides and applicable page/module defaults.
4. **States and interactions.** Initial, loading, ready, empty, disabled, read-only, dirty,
   validating, saving, success and failure where applicable. Define transitions, focus,
   keyboard/touch behavior, asynchronous races and recovery without losing user work.
5. **Properties panel grouping.** Group names and order, member paths, control types,
   conditional visibility, preservation of hidden values, defaults/reset behavior and
   read-only display of fixed values. Provide English and Chinese labels/help. Explain
   which groups are presentation only and which correspond to nested JSON objects.
6. **Examples.** Minimal and configured class/instance examples, bilingual visible text,
   bindings and declared action instances. For a composite element, show at least one
   representative data shape and data-operation flow. Clearly distinguish shorthand
   illustrations from complete descriptors accepted by the current format.
7. **Review record.** Revision, unresolved choices/assumptions, feedback and its disposition,
   and actual human approval tied to a revision. Significant contract revisions require
   renewed approval. Do not record machine review as human approval.
8. **Implementation and verification.** Fill in after implementation: module interface,
   files, renderer and validator registration, migrations, classes/versions, module catalogue
   link, checks performed, known limits and compatibility guidance for saved class copies.

## Configuration coverage

Use these as design prompts, not a mandatory JSON vocabulary. Choose exact names from
the established schema and specify any new structures in the approved contract.

| Area | Questions the contract should answer where relevant |
| --- | --- |
| General and content | Caption, description, icon, tooltip, persistent help, placeholders, locale/fallback, formatting and selectable/copyable content? |
| Caption layout | Placement, horizontal/vertical gaps and alignment, available width, line limit, wrap/truncate behavior and access to full text on keyboard/touch? |
| Appearance | Font family/size/weight/style, foreground/background, border, radius, shadow, spacing, density and icons? Styles for hover, focus, active, selected, disabled, read-only and error states? Theme inheritance and supported override precedence? |
| Size and layout | Whole-element versus inner-control dimensions, minimum/maximum sizes, padding/gaps, alignment, overflow, responsive fallback and interaction with the element layouter? |
| Binding and values | Binding paths, record shape, read/write mode, default versus current value, null/empty/missing semantics, conversion, formatting and change propagation? |
| Events and actions | Which events run which declared WPI actions, with what payload and record context? Execution order, repeated activation, cancellation and failure feedback? |
| Validation | Types, ranges, length counting, patterns, cross-field constraints, validation timing, localized messages, client/server parity, invalid input preservation and focus on errors? |
| Accessibility and language | Accessible name/description, semantics, focus order/indicators, keyboard/touch equivalents, contrast, reduced motion where relevant, English/Chinese content and runtime language changes? |
| Lifecycle | Mount/show/refresh, preserved or reset state when cached, teardown, cancellation, stale-response handling and cleanup? |

Do not leave inheritance or defaults as an unexplained “automatic.” State what supplies
the value and how conflicting settings resolve. Distinguish an omitted setting from an
empty string, `false`, `0`, and `null` where their behavior differs.

## Additional coverage for lists and other composite elements

| Area | Decisions to specify |
| --- | --- |
| Records and retrieval | Source/load action, fields, stable row identity, result and total-count shape, initial load, refresh trigger, loading indicator and retry? Which capabilities exist today and which need new action/backend support? |
| Presentation | Table/rows/cards or supported alternatives; caption/toolbar/footer; columns and their order, visibility, width, alignment, formatting and cell renderers; header, row and cell styles; wrapping and overflow? |
| Paging and large data | Paging enabled, size/options, controls, first/last page behavior, server/client responsibility, total counts or cursors, page reset after query changes, and virtualization if in scope? |
| Search, filters and sort | Supported fields/operators, query shape, controls, debounce, clearing, default/multiple sort keys, client/server execution and ordering with paging? |
| Selection and navigation | None/single/multiple, checkbox and row activation, row identity across pages, selection persistence, keyboard navigation, row/cell actions and action payloads? |
| Editing | Whether editing is allowed, row/cell/form mode, editable fields, edit triggers, save/cancel, validation, draft storage, dirty state, concurrent updates and navigation with unsaved work? |
| Insert and update | Enable/visibility flags, new-record defaults, insert location, temporary identity, save payload, server-assigned identity and refresh/selection after success? |
| Delete and archive | Distinct meanings, single/bulk scope, confirmation if required by the product, permission checks, partial failures, undo/restore when supported and page/selection changes after removal? |
| Save and persistence | Manual/automatic/batch policy, retrieve/save actions, client/server authority, repeated submissions, optimistic versus confirmed updates, failure recovery and stale-response handling? |
| States and permissions | Empty versus no-search-results, load/save errors, per-row pending/error states, disabled actions, read-only mode and server-side authorization independent of descriptor controls? |

If an element exposes permissions as configuration, specify whether a flag hides a control,
disables it or makes a capability unavailable. Authorization still belongs on the server.
Avoid duplicating action implementations inside a list: compose existing action classes or
identify an explicit action extension needed to fulfill the approved element contract.

## Human review readiness

Before presenting the document, check that a designer can answer:

- Can this element be configured for materially different pages without code changes?
- Are look-and-feel settings and behavioral settings discoverable in logical groups?
- Does every option have a predictable default and a defined interaction with other options?
- Can the examples, normal states, edge states and failures be understood without reading code?
- Are proposed features, exclusions and implementation gaps visible?
- Are consequential open questions resolved or clearly presented for decision?

After human approval, use these same contracts to select meaningful implementation checks.
