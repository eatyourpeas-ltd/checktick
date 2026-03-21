---
title: Repeats (Nested, repeatable sections)
category: None
---

This document describes repeatable sections of a survey ("Repeats"): logical entities like Patient or Visit that can contain one or more question groups, and optionally one level of nested repeats (e.g., Patient → Visit).

## Goals

- Model repeatable structures like Patient → Visits → Treatments.
- Keep survey definitions relational and clear; keep responses flexible.
- Start with shallow nesting (depth ≤ 2), and allow deeper later.
- Preserve current security and SSR ergonomics; remain Postgres-first.

## Definitions (schema) vs Responses (data)

- Definitions: per-survey structure in relational tables, enabling ordering and validation.
- Responses: per-submission answers in JSONB with nested instances keyed by UUID.

## Data model (definitions)

- CollectionDefinition
  - id, survey_fk, key (slug), name
  - cardinality: one | many
  - min (default 0), max (nullable)
  - parent_fk (self FK, nullable) — enables nesting
- CollectionItem (ordered children for a collection)
  - id, collection_fk
  - item_type: 'group' | 'collection'
  - group_fk (nullable if child is a collection)
  - child_collection_fk (nullable if child is a group)
  - order (int)

Notes:

- CollectionItem lets you interleave groups and child collections under a single ordered list, which matches how the UI renders a collection instance.
- Enforce acyclic graphs (no collection can be its own ancestor).

## Response shape (JSONB)

Store nested instances inside `Response.answers`:

```json
{
  "...": "existing top-level answers",
  "collections": {
    "patient": {
      "uuid-1": {
        "answers": { "q123": "Alice", "q124": "London" },
        "collections": {
          "visit": {
            "uuid-a": { "answers": { "q200": "2025-09-20" } },
            "uuid-b": { "answers": { "q200": "2025-09-21" } }
          }
        }
      }
    }
  }
}
```

- Instance keys are UUIDs; this lets us update a specific instance idempotently.
- Non-collection groups remain at the top level as today.

## UI/UX

- Repeats are managed on the Groups page:
  - Select one or more groups and click "Create repeat from selection" to name the repeat and set min/max allowed items.
  - Optionally choose an existing repeat as parent (one-level nesting only).
  - Repeats are indicated on the Groups list with a badge and tooltip describing membership and caps.
- Filling a response:
  - For each top-level collection, display a list of instances and an "Add" button (disabled when max reached).
  - Opening an instance shows its groups and any child collections.
  - Use breadcrumbs like Patient > Visit #2 > Treatment #1.
  - Instance label template on `CollectionDefinition` (optional): e.g., `"Visit on {{ answers[q_visit_date] }}"`.

## Validation

- Enforce min/max instance counts server-side; mirror client-side for UX.
- Cardinality 'one' can auto-create the required instance.
- Prevent structural cycles; optionally prevent reusing the same group in multiple branches.
- Guard maximum depth (initially 2) in both model clean() and runtime.

## Persistence and querying

- Postgres is sufficient:
  - Definitions in relational tables (FKs, ordering, integrity).
  - Responses in JSONB, with GIN indexes for common filters if needed.
- Optional analytics index table for reporting: flattened rows `(response_id, path, collection_path, question_id, value)` for SQL-friendly dashboards.

## Security

- Same permission model as existing surveys: editors manage definitions; authenticated respondents create instances within limits.
- CSRF/CSP remain unchanged; no inline scripts.

## Authoring via Outline (REPEAT syntax)

To mark a group as repeatable in bulk markdown:

```markdown
REPEAT-5
# Patient
... group content ...

> REPEAT
> # Visit
> ... child group content ...
```

- REPEAT = unlimited; REPEAT-1 means only one allowed.
- Use "> " before REPEAT and the group heading to indicate one level of nesting.
- Nesting is limited to one level (Parent → Child) by design.

## Migration notes

- The separate Collections UI has been removed in favor of managing repeats directly on the Groups page.
- Under the hood, the data model still uses `CollectionDefinition` and `CollectionItem` to represent repeats and their ordered children.

## Open questions

- Should a group be allowed in more than one branch? (default: no, for simplicity.)
- Max depth default (2) — configurable per survey or global?
- Conflict resolution when collection structure changes after responses exist.
