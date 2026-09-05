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
| `rcpch`        | `{"code": "name", …}` dict                    | No                          | Hospitals, Welsh LHBs       |
| `reference`    | `{"code": "name", …}` dict                    | No                          | Countries (ISO 3166), UK Counties, Local Authority Districts |
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

- The survey builder (`builder.js` "Load options" button, authenticated session)
- External integrations via the REST API (API key)

All dataset API endpoints require authentication (`DataSetAccess` permission
class) — there is no anonymous access. Anonymous survey respondents never
call this API: all dataset-backed dropdowns are rendered server-side (see
§4 and §5).

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

## 5 — Professional field dropdowns

Professional fields (employing trust, health board, etc.) are rendered
server-side, like regular dataset-backed dropdowns: the views build a
`professional_dataset_options` context map via
`_get_professional_dataset_options()` (surveys/views.py), and `detail.html`
renders the `<option>`s directly into the page. If a mapped dataset is
missing or inactive, the template falls back to a plain text input.

Historical note: these fields previously used a client-side fetch
(`professional-fields.js` → `GET /api/datasets/{key}/`), which required
anonymous access to the datasets API. That was removed in August 2026
(security review finding F8) so the API could be restricted to
authenticated users only.

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
