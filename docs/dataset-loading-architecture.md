---
title: Dataset Loading Architecture
category: api
priority: 4
---

# Dataset Loading Architecture

This document describes how datasets are stored, fetched, and rendered in two
contexts: the **dataset browser** (staff/admin view) and the **survey builder /
survey respondent view** (where datasets power dropdown questions).

---

## Dataset categories

| Category       | `DataSet.options`                             | Live query?                 | Example                     |
| -------------- | --------------------------------------------- | --------------------------- | --------------------------- |
| `nhs_dd`       | `{"code": "name", …}` dict                    | No                          | NHS Trusts, ICBs            |
| `user_created` | List of strings or `{"value", "label"}` dicts | No                          | Bespoke checklist           |
| `snomed`       | `[]` (always empty)                           | Yes — live from `snomed.db` | QOF Antiepileptic Drug List |

SNOMED datasets never store options in Postgres. Options are always fetched live
from the read-only SQLite database (`snomed.db`) maintained by the `sct` Rust
binary. This keeps the Postgres schema stable across SNOMED release cycles and
avoids duplicating tens of thousands of rows per refset.

---

## 1 — Dataset browser (`/datasets/`)

### List view

`dataset_list` (surveys/views.py) builds the queryset from Postgres and passes
it straight to the template. The member count displayed in the table comes from:

- Non-SNOMED: `dataset.options|length` (template filter — count from the JSONField)
- SNOMED: `dataset.snomed_member_count` (integer stored at seed time by
  `seed_snomed_datasets`)

### Detail view

`dataset_detail` (surveys/views.py) branches on `dataset.category`:

```
if dataset.category == "snomed":
    raw = snomed_get_options(dataset)     # live SQLite query
    snomed_options = [(sctid, term), …]  # passed as context variable
else:
    # template iterates dataset.options dict/list directly
```

The template `dataset_detail.html` renders SNOMED options from `snomed_options`
(a list of `(sctid, preferred_term)` tuples) and non-SNOMED options from
`dataset.options`.

---

## 2 — REST API (`/api/datasets/{key}/`)

`DataSetViewSet` (api/views.py) exposes datasets to:

- The `professional-fields.js` frontend (professional field dropdowns in surveys)
- External integrations via the REST API

The `DataSetSerializer` serialises `DataSet.options` as-is from Postgres. For
SNOMED datasets this is `[]`, so **the API currently returns empty options for
SNOMED datasets**. See the fix described in §4 below.

---

## 3 — Survey builder

### Attaching a dataset to a dropdown question

In `group_builder.html` a `<select name="prefilled_dataset">` lets the builder
pick from all accessible datasets. On question save/update:

1. `_parse_builder_question_form()` extracts the `dataset_key` string.
2. The view looks up the `DataSet` object (access-controlled) and stores it as
   `SurveyQuestion.dataset` (a ForeignKey).
3. `SurveyQuestion.options` is stored as `[]`; the canonical options live on the
   dataset, not duplicated on every question.

### Builder preview / question row

The builder template `question_row.html` shows `• Dataset: <name>` as metadata.
It does **not** render a live preview of the options — that is intentional, as
SNOMED options may be large and the builder is a configuration surface.

---

## 4 — Survey respondent view (survey take / preview)

When a respondent opens a published survey, `_handle_participant_submission` (GET)
and `survey_preview` both call `_inject_dataset_options(questions)` before
rendering the `detail.html` template.

### `_inject_dataset_options(questions)`

Defined in surveys/views.py. Iterates every question and, if `q.dataset` is set,
materialises the options onto `q.options` so the template can render them:

```python
if dataset.category == "snomed":
    raw = snomed_get_options(dataset)          # live snomed.db query
    q.options = [{"value": sctid, "label": term}, …]
elif isinstance(dataset.options, dict):
    q.options = [{"value": k, "label": v} for k, v in dataset.options.items()]
elif isinstance(dataset.options, list):
    q.options = dataset.options
```

The template then iterates `q.options|as_list` and renders each `<option>` with
`opt|option_value` (the SCTID for SNOMED) and `opt|option_label` (the preferred
term).

### What gets stored on submission

```python
answers[str(q.id)] = request.POST.get(f"q_{q.id}")
```

For SNOMED dropdowns the `<option value="…">` is the **SCTID** (e.g.
`372687004`). The stored answer is therefore the SCTID — a stable, unambiguous
identifier that does not change when SNOMED terminology is updated. The human-
readable preferred term can be recovered at any time by querying `snomed.db`.

---

## 5 — Professional field dropdowns (special case)

Professional fields (employing trust, health board, etc.) use a different
mechanism: the `detail.html` template renders an empty `<select
data-dataset-key="…">` and `professional-fields.js` fetches options
asynchronously from `GET /api/datasets/{key}/` after page load. This is the
only case where the REST API is used at runtime to populate a dropdown in the
survey respondent view.

This pattern is **not used** for regular survey dropdown questions. Those rely on
`_inject_dataset_options()` at render time.

---

## 6 — API SNOMED options fix

`GET /api/datasets/{key}/` returns `options: []` for SNOMED datasets because
`DataSet.options` is always empty. To support API consumers that need the full
option list, `DataSetSerializer.to_representation()` resolves live SNOMED options
when the category is `snomed`:

```python
if obj.category == "snomed":
    representation["options"] = options_as_dict(snomed_get_options(obj))
```

`options_as_dict` returns `{"sctid": "preferred_term", …}` for consistency
with the dict format used by other categories. If `snomed.db` is unavailable
the serializer returns `{}` with an additional `snomed_unavailable: true` flag.

---

## Data flow summary

```
SNOMED refset request
        │
        ▼
  snomed.db (SQLite, read-only)
  SnomedResolver.get_options()
        │
        ├── dataset_detail view ──────────► dataset_detail.html (snomed_options table)
        │
        ├── _inject_dataset_options() ───► detail.html <select> (respondent view)
        │
        └── DataSetSerializer ───────────► /api/datasets/{key}/ JSON response

Non-SNOMED datasets
        │
        ▼
  DataSet.options (Postgres JSONField)
        │
        ├── dataset_detail.html (options table)
        ├── _inject_dataset_options() ──► detail.html <select>
        └── DataSetSerializer ──────────► /api/datasets/{key}/ JSON
```
