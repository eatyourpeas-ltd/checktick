# Follow-up Questions & Bulk Import

Complete guide to creating surveys with follow-up text inputs using markdown bulk import.

## Overview

CheckTick supports follow-up text inputs on question options through three methods:

1. **API** - Programmatically create surveys with follow-ups
2. **Web Builder** - Use the visual survey builder interface
3. **Markdown Import** - Bulk import surveys from markdown files (this guide)

This guide focuses on the markdown import syntax for adding follow-up questions to your surveys.

## Quick Start

For a complete guide to bulk importing surveys, see the [Import Documentation](import.md).

Follow-up text inputs are added using indented lines starting with `+` immediately after an option:

```markdown
## Employment status
(mc_single)
- Employed full-time
- Employed part-time
  + Please specify your hours per week
- Self-employed
  + What type of business?
- Student
- Retired
```

### Key Points

- **Indentation required**: Follow-up lines must be indented (at least 2 spaces)
- **Plus sign marker**: Lines start with `+` followed by a space
- **Optional**: Not all options need follow-ups—only add where needed
- **Supported types**: Works with `mc_single`, `mc_multi`, `dropdown`, `orderable`, and `yesno`
- **Backward compatible**: Existing markdown imports without follow-ups continue to work

### Yes/No Questions

For `yesno` questions, you can optionally provide explicit options with follow-ups:

```markdown
## Open to relocation
(yesno)
- Yes
  + Which regions are you considering?
- No
  + Would you consider remote opportunities?
```

## Implementation Details

### Files Modified

1. **checktick_app/surveys/markdown_import.py**
   - Added parsing logic for `+ ` lines (follow-up text)
   - Store options as tuples: `(option_text, followup_label)` when follow-up is present
   - Added `_convert_options_to_dicts()` helper function
   - Converts tuples to dict format: `{label, value, followup_text: {enabled, label}}`
   - Updated type conversions for mc_single, mc_multi, dropdown, orderable, yesno, and image types

2. **checktick_app/surveys/views.py**
   - Updated `_bulk_upload_example_md()` to demonstrate follow-up syntax
   - Added examples in both parent and nested collection groups

3. **checktick_app/surveys/templates/surveys/bulk_upload.html**
   - Added follow-up text to format reference list
   - Created new "Optional: Follow-up text inputs" section with:
     - Syntax explanation
     - Complete example
     - Guidelines for usage
     - Supported question types

4. **docs/import.md**
   - Extended "Options and Likert metadata" section
   - Added comprehensive example showing follow-up syntax
   - Added "Follow-up guidelines" subsection with:
     - Indentation requirements
     - Supported question types
     - Usage best practices
     - Storage information

## Data Structure

Options with follow-up text are stored in the same format as API and webapp builder:

```python
{
    "label": "Employed part-time",
    "value": "Employed part-time",
    "followup_text": {
        "enabled": True,
        "label": "Please specify your hours per week"
    }
}
```

Options without follow-up text:

```python
{
    "label": "Student",
    "value": "Student"
}
```

## Testing

A comprehensive pytest test suite has been created in `test_followup_import.py`:

```bash
# Run tests
docker compose exec -T web pytest test_followup_import.py -v
```

**Test Coverage:**
- ✅ Parsing markdown with follow-up questions
- ✅ Group and question structure validation
- ✅ mc_single with follow-ups (partial)
- ✅ mc_multi with follow-ups (partial)
- ✅ dropdown with follow-ups (partial)
- ✅ yesno with follow-ups (all options)
- ✅ Data structure matches API format

**All 7 tests passing** ✓

Sample test output:
```
============================= test session starts ==============================
test_followup_import.py::test_followup_import_parses_successfully PASSED [ 14%]
test_followup_import.py::test_followup_import_creates_correct_group_structure PASSED [ 28%]
test_followup_import.py::test_followup_mc_single_option_structure PASSED [ 42%]
test_followup_import.py::test_followup_mc_multi_option_structure PASSED  [ 57%]
test_followup_import.py::test_followup_dropdown_option_structure PASSED  [ 71%]
test_followup_import.py::test_followup_yesno_option_structure PASSED     [ 85%]
test_followup_import.py::test_followup_data_structure_matches_api_format PASSED [100%]

============================== 7 passed in 0.03s ===============================
```

## Examples in Documentation

The bulk upload form now shows live examples with follow-up questions:

1. Gender question with "Non-binary" → "Please specify"
2. Visit reason (multi-select) with:
   - "Acute illness" → "Please describe symptoms"
   - "Other" → "Please specify"

These examples appear in both:
- The example markdown in the upload form
- The format reference section
- The import.md documentation

## Backward Compatibility

✓ **Fully backward compatible**
- Existing markdown imports without `+ ` lines work exactly as before
- Options without follow-ups create simple `{label, value}` structures
- No breaking changes to existing surveys or imports

## Next Steps

The feature is complete and tested. Users can now:
1. Use the visual builder (webapp forms)
2. Use the API (JSON with `has_followup`/`followup_label`)
3. Use markdown bulk import (indented `+ ` notation)

All three methods produce the same data structure and behave identically in surveys.
