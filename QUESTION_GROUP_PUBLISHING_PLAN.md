# Question Group Publishing Feature Plan

**Version:** 1.0
**Date:** 18 November 2025
**Status:** Planning & Review

## Executive Summary

This document outlines the implementation plan for allowing users to publish Question Groups as reusable Question Group Templates. Users can share validated question sets (PHQ-9, GAD-7, etc.) with proper attribution, available at two levels: organization-wide or globally.

**Key Design Decisions:**
- Publish Question Groups as Question Group Templates (simpler, more practical than full Surveys)
- Two publication levels: organization and global
- Static copies on import (no dynamic linking)
- Attribution preserved through markdown and displayed to survey participants
- Tag system for discoverability (base tags + user/org customizable)
- All templates use consistent checkbox selection UI for choosing questions to import
- Question Group Template Library accessible via "Browse Question Group Templates" button in builder
- Existing Patient/Professional templates remain as quick-access buttons, also discoverable in library
- Consistent terminology: Question Group → Question Group Template → Question Group Template Library

---

## 1. Markdown Parsing Architecture Review

### Current System Assessment

**Where Markdown→Model Conversion Happens:**

1. **Python Parser** (`/checktick_app/surveys/markdown_import.py`):
   - `parse_bulk_markdown(md_text)` - Core parser (491 lines total)
   - `parse_bulk_markdown_with_collections(md_text)` - Extended parser for REPEAT markers
   - Returns Python data structures (lists/dicts) representing groups and questions
   - Handles: Custom IDs `{id}`, branching `? when operator value -> {target}`, required fields `*`, follow-ups `+`, repeats `REPEAT-N`
   - **Does NOT create model instances** - just parses and validates

2. **Model Creation** (`/checktick_app/surveys/views.py`):
   - `bulk_upload()` view (line ~5334+) calls parser, then creates models
   - Creates QuestionGroup, SurveyQuestion, SurveyQuestionCondition instances
   - Handles ID reference resolution and collision avoidance
   - Links questions to groups and surveys

3. **JavaScript Parser** (`/checktick_app/static/js/bulk-upload-preview.js`):
   - `parseStructure(md)` - Client-side parser for live preview
   - Mirrors Python parsing logic for instant feedback
   - **Does NOT create models** - only renders preview HTML

4. **Markdown Export** (`/checktick_app/surveys/views.py`):
   - `_export_survey_to_markdown(survey)` function (line 5986+)
   - Converts existing Survey with QuestionGroups back to markdown
   - Handles collections (REPEAT markers), branching, options, follow-ups

### Recommendation: Keep Current System

**✅ The markdown parsing architecture should stay as-is because:**

1. **Clean Separation of Concerns:**
   - Parser validates and structures data
   - Views handle model creation
   - This separation is ideal for our new feature

2. **Already Handles Complex Features:**
   - Custom IDs, branching, repeats, follow-ups all work
   - Collections (REPEAT) properly supported
   - Reference resolution robust

3. **Two-Way Conversion Working:**
   - Import: Markdown → Python data → Models
   - Export: Models → Markdown
   - Round-trip integrity maintained

4. **For Published QuestionGroups:**
   - We can export QuestionGroup to markdown (slight modification of `_export_survey_to_markdown`)
   - Users copy markdown
   - Existing `parse_bulk_markdown()` imports it
   - Model creation logic stays the same

**Minor Enhancements Needed:**

1. **Add QuestionGroup Export Method:**
   ```python
   def export_question_group_to_markdown(group: QuestionGroup, survey: Survey) -> str:
       """Export a single QuestionGroup to markdown format."""
   ```
   - Similar to `_export_survey_to_markdown()` but for single group
   - Include attribution as HTML comment: `<!-- Attribution: ... -->`

2. **Attribution Preservation in Parser:**
   - Parser already handles unknown lines gracefully
   - HTML comments `<!-- ... -->` will be ignored by parser (safe)
   - Need to extract attribution comments during import for display purposes

3. **Add Model Methods:**
   ```python
   class QuestionGroup(models.Model):
       def to_markdown(self, survey=None) -> str:
           """Export this group to markdown format."""

       @classmethod
       def from_markdown_with_attribution(cls, md_text: str, owner: User) -> tuple[QuestionGroup, dict]:
           """Parse markdown and return group + attribution metadata."""
   ```

---

## 2. Specialist Templates Handling

### Current Implementation

**Patient Demographics Template** (`TEMPLATE_PATIENT`):
- Question type: `template_patient`
- Fields stored in `QuestionGroup.schema` JSONField
- Structure: `{"template": "patient_details_encrypted", "fields": [...]}`
- UI: Checkboxes to select which demographic fields to include
- Fields: first_name, surname, date_of_birth, ethnicity, sex, gender, NHS number, hospital number, post code, address, etc.
- Special handling: `include_imd` flag when post code selected

**Professional Details Template** (`TEMPLATE_PROFESSIONAL`):
- Question type: `template_professional`
- Fields stored in `QuestionGroup.schema` JSONField
- Fields: title, first_name, surname, job_title, employing_trust, health_board, ICB, NHS region, country, GP surgery
- Special handling: ODS code toggles for certain fields (trusts, health boards, ICB, GP surgery)
- UI: Checkboxes to select fields + toggles for ODS codes

**Current Code Locations:**
- Field definitions: `views.py` lines 74-155 (`DEMOGRAPHIC_FIELD_DEFS`, `PROFESSIONAL_FIELD_DEFS`)
- Template defaults: `PATIENT_TEMPLATE_DEFAULT_FIELDS`, `PROFESSIONAL_TEMPLATE_DEFAULT_FIELDS`
- Normalization: `_normalize_patient_template_options()`, similar for professional
- Views: `builder_question_template_patient_update()`, `builder_group_question_template_patient_update()`

### Recommendation: Unified Checkbox System for Published Templates

**Proposal: Extend the checkbox customization model to all published QuestionGroups**

**Why This Makes Sense:**

1. **Consistency:** Patient/Professional templates already work this way
2. **Flexibility:** Users importing published templates may not need all questions
3. **Common Use Case:** PHQ-9 has 9 questions, but some research only needs PHQ-2 (first 2 questions)
4. **Existing UI:** Checkbox interface already built and working

**Implementation Approach:**

### Option A: Schema-Based (Recommended)

**For Published QuestionGroups:**

1. **Schema Structure:**
   ```json
   {
     "template": "published_template",
     "source_group_id": 123,
     "questions": [
       {"ref": "feeling-down", "text": "Feeling down, depressed...", "selected": true},
       {"ref": "little-interest", "text": "Little interest...", "selected": true},
       ...
     ],
     "attribution": {...}
   }
   ```

2. **When User Adds Published Template:**
   - Create QuestionGroup with `schema` containing all available questions
   - Create single SurveyQuestion of type `TEMPLATE_PUBLISHED`
   - UI shows checkbox list (like Patient/Professional templates)
   - User selects which questions to include

3. **On Survey Completion:**
   - Read `schema`, identify selected questions
   - Render only selected questions to participant
   - Store responses keyed by question reference

**Advantages:**
- Consistent with existing Patient/Professional pattern
- Schema stores complete template definition
- Single database record per template instance
- Checkbox UI already exists as pattern

**Disadvantages:**
- Creates new question type (`TEMPLATE_PUBLISHED`)
- More complex response handling
- Schema can get large for big templates

### Option B: Multi-Question Import (Alternative)

**For Published QuestionGroups:**

1. **Import Process:**
   - Parse markdown as normal
   - Create actual SurveyQuestion records for each question
   - Add checkbox UI **during import preview** (before committing)
   - User deselects unwanted questions
   - Only selected questions saved to database

2. **Checkbox UI Location:**
   - In bulk import preview modal
   - Show "Customize" button for published templates
   - Renders list of all questions with checkboxes
   - User confirms selection before import

**Advantages:**
- No new question type needed
- Questions are real SurveyQuestion instances (normal database structure)
- Simpler response handling
- Works with existing markdown import flow

**Disadvantages:**
- Can't change selection after import without re-importing
- More database records (one per question)
- Deviates from Patient/Professional pattern

### Recommended: **Option A (Schema-Based)**

**Rationale:**

1. **Editable After Import:** Users can revise question selection anytime without re-importing
2. **Consistent Pattern:** Matches existing Patient/Professional template behavior
3. **Better UX:** Checkbox UI in builder for adjusting selection as survey evolves
4. **Single Source of Truth:** Schema stores complete template definition
5. **Memory of Origin:** Clear that this came from a published template

**Implementation:**

All published QuestionGroups work the same way:
- Create single `SurveyQuestion` of type `TEMPLATE_PUBLISHED` when imported
- `options` JSONField contains: complete question list, current selection, attribution
- Checkbox UI in builder to select/deselect questions
- On survey completion, only render selected questions to participant
- Attribution preserved in template metadata

**Patient/Professional Templates:**

Convert to published QuestionGroups with same approach:
- Create published entries for discovery in template library
- Keep existing `TEMPLATE_PATIENT` / `TEMPLATE_PROFESSIONAL` types
- They're just specialized published templates with extra features:
  - Encryption (Patient only)
  - Dataset integration for dropdowns
  - ODS code toggles (Professional)
- Users can add via template library OR existing dedicated buttons
- Both paths lead to same schema-based implementation

---

## 3. Database Schema Changes

### New Models

#### PublishedQuestionGroup

```python
class PublishedQuestionGroup(models.Model):
    """A published, reusable QuestionGroup template."""

    class PublicationLevel(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        GLOBAL = "global", "Global"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DELETED = "deleted", "Deleted (Soft Delete)"

    # Source
    source_group = models.ForeignKey(
        QuestionGroup,
        on_delete=models.SET_NULL,
        null=True,
        related_name="published_versions"
    )

    # Ownership & Permissions
    publisher = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    publication_level = models.CharField(
        max_length=20,
        choices=PublicationLevel.choices
    )

    # Content (snapshot at publication time)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    markdown = models.TextField(help_text="Markdown representation")

    # Attribution
    attribution = models.JSONField(default=dict, blank=True)
    # Structure: {
    #   "authors": [{"name": "...", "orcid": "..."}],
    #   "citation": "...",
    #   "pmid": "...",
    #   "doi": "...",
    #   "license": "...",
    #   "year": 2020
    # }

    # Metadata
    tags = models.JSONField(default=list, blank=True)  # ["depression", "screening", "validated"]
    language = models.CharField(max_length=10, default="en")
    version = models.CharField(max_length=50, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    # Usage tracking
    import_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['publication_level', 'status']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(publication_level='organization', organization__isnull=False) |
                    models.Q(publication_level='global')
                ),
                name='org_required_for_org_level'
            )
        ]
```

### Extended Models

#### QuestionGroup Extensions

```python
class QuestionGroup(models.Model):
    # ... existing fields ...

    # New field for imported templates
    imported_from = models.ForeignKey(
        'PublishedQuestionGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_copies'
    )

    def to_markdown(self, survey=None) -> str:
        """Export this group to markdown format."""
        pass

    def can_publish(self, user: User, level: str) -> bool:
        """Check if user can publish this group at given level."""
        pass
```

---

## 4. Publication Workflow

### 4.1 Publishing a QuestionGroup

**User Permissions:**

| User Type | Can Publish Organization | Can Publish Global |
|-----------|-------------------------|-------------------|
| Individual User | ❌ No | ✅ Yes (immediate) |
| Organization VIEWER | ❌ No | ❌ No |
| Organization CREATOR | ✅ Yes (immediate) | ✅ Yes (immediate) |
| Organization ADMIN | ✅ Yes (immediate) | ✅ Yes (immediate) |
| Superuser | ✅ Yes (immediate) | ✅ Yes (immediate) |

**Publication Flow:**

1. **User Initiates Publication:**
   - From QuestionGroup detail page or survey builder
   - Button: "Publish as Template"
   - Modal opens with form

2. **Publication Form:**
   ```
   [ ] Organization-level (visible to [OrgName] members)
   [ ] Global (visible to all users, requires approval)

   Attribution (optional but recommended):
   - Authors: [Add author] [Name] [ORCID ID]
   - Citation: [text]
   - PMID: [number]
   - DOI: [text]
   - License: [dropdown: CC0, CC-BY-4.0, etc.]
   - Year: [number]

   Tags: [tag1] [tag2] [+]
   Base tags: depression, anxiety, screening, validated, research

   Version: [1.0]
   Language: [en] (detected from survey)
   ```

3. **Validation:**
   - Check user has permission for selected level
   - Validate QuestionGroup has questions
   - Check for duplicate (same name + org/global)
   - Rate limit: 10 publications per user per day

4. **Create Publication:**
   - Generate markdown from QuestionGroup
   - Include attribution as HTML comment
   - Set status: `APPROVED` (immediate publication for all levels)
   - No approval workflow needed

5. **Success:**
   - Show confirmation message: "Template published successfully!"
   - Display markdown preview
   - "Copy markdown" button
   - Link to published template page
   - Template immediately visible in library

### 4.2 Moderation (Future Enhancement)

**Note:** Initial release has no approval workflow. All publications are immediate. Future versions may add:
- Flagging system for inappropriate content
- Community reporting
- Superuser moderation interface for flagged content
- Optional organization-level approval workflow (configurable)

---

## 5. Discovery & Import Workflow

### 5.1 Published Templates Library

**Page: `/templates/` (or `/published-question-groups/`)**

**UI Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Published Question Group Templates                 │
│                                                      │
│  Search: [________________]  [🔍]                   │
│                                                      │
│  Filters:                                           │
│  Level: [ All | Organization | Global ]             │
│  Tags:  [ depression ] [ anxiety ] [ + ]            │
│  Language: [ All | English | Welsh | ... ]          │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ 📋 Patient Health Questionnaire (PHQ-9)      │  │
│  │    Depression screening - 9 questions        │  │
│  │    Tags: depression, screening, validated    │  │
│  │    👤 Dr Smith | 🏢 Global | 📥 234 uses    │  │
│  │    🏆 Acknowledgement                        │  │
│  │    [Preview] [Import] [Copy Markdown]        │  │
│  └──────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │ 📋 Generalized Anxiety Disorder (GAD-7)      │  │
│  │    Anxiety screening - 7 questions           │  │
│  │    ...                                        │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Features:**

1. **Search:** Full-text search on name, description, tags
2. **Filters:** Level, tags, language
3. **Sorting:** Popularity (import_count), date, alphabetical
4. **Attribution Badge:** "Acknowledgement" badge with tooltip on hover
5. **Preview:** Modal showing markdown and attribution details
6. **Import Options:**
   - "Import to Survey" - Add to current survey builder
   - "Copy Markdown" - Copy to clipboard for bulk import

### 5.2 Import to Survey Builder

**Flow A: Direct Import (From Templates Page)**

1. User clicks "Import to Survey" on published template
2. Redirect to survey selection: "Which survey?" [Dropdown of user's surveys] [Create New]
3. Parse markdown using existing `parse_bulk_markdown()`
4. **Customization Step (Option B from Specialist Templates):**
   - Show preview with checkboxes for each question
   - "Select All" / "Deselect All" buttons
   - User selects which questions to include
5. Create QuestionGroup and SurveyQuestion instances (only selected)
6. Set `imported_from` reference
7. Increment `import_count` on PublishedQuestionGroup
8. Redirect to survey builder with success message

**Flow B: From Survey Builder (Inline)**

1. In survey builder, button: "Add from Templates"
2. Modal opens with template library (same as `/templates/` but in modal)
3. User searches, finds, clicks "Add to Survey"
4. Same customization step as Flow A
5. Questions added to current survey
6. Modal closes, builder updates

**Flow C: Bulk Import (Existing Markdown Upload)**

1. User goes to bulk import page
2. Pastes markdown (may include attribution comments)
3. Preview shows parsed structure
4. **Attribution Detection:**
   - If markdown contains `<!-- Attribution: ... -->`, parse and display
   - Show attribution card in preview
   - Note: "This content includes attribution that will be preserved"
5. User clicks "Import"
6. Questions created as normal
7. Attribution stored in QuestionGroup metadata (if needed)

### 5.3 Attribution Display

**In Survey Builder:**

```
┌────────────────────────────────────────────────┐
│ Question Group: PHQ-9 Depression Screening     │
│ [Edit] [Delete] [Reorder]                     │
│                                                 │
│ ℹ️ Acknowledgement (hover for details)         │
│   ┌─────────────────────────────────────────┐ │
│   │ Kroenke, K., Spitzer, R. L., &          │ │
│   │ Williams, J. B. (2001)                   │ │
│   │ PMID: 11556941                           │ │
│   │ License: Public Domain                   │ │
│   └─────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**In Published Survey (Participant View):**

At the end of the survey, before submit button:

```
─────────────────────────────────────────────────

Acknowledgements

This survey includes validated screening tools:

• Patient Health Questionnaire (PHQ-9)
  Kroenke, K., Spitzer, R. L., & Williams, J. B. (2001).
  The PHQ-9: validity of a brief depression severity measure.
  PMID: 11556941

• Generalized Anxiety Disorder Scale (GAD-7)
  Spitzer, R. L., et al. (2006).
  PMID: 16717171

─────────────────────────────────────────────────

[Submit Survey]
```

---

## 6. API Endpoints

### Public API (Existing Pattern)

```
GET    /api/published-templates/                 - List approved published templates
GET    /api/published-templates/{id}/            - Get specific template details
GET    /api/published-templates/{id}/markdown/   - Get markdown representation
POST   /api/published-templates/{id}/import/     - Import template to survey
```

**Query Parameters:**
- `level`: `organization` | `global`
- `tags`: Comma-separated
- `language`: Language code
- `search`: Search term
- `ordering`: `name` | `-created_at` | `-import_count`

### Authenticated API (Survey Builder)

```
POST   /api/question-groups/{id}/publish/        - Publish a question group
GET    /api/published-templates/my/              - User's published templates
PATCH  /api/published-templates/{id}/            - Update template metadata
DELETE /api/published-templates/{id}/            - Delete published template (if no dependents)
```

### Admin API (Superusers)

```
GET    /api/admin/published-templates/              - List all templates (including soft-deleted)
DELETE /api/admin/published-templates/{id}/         - Soft delete any template (moderation)
```

---

## 7. Rate Limiting

**Using existing `django-ratelimit`:**

```python
@ratelimit(key="user", rate="10/d", block=True)
def publish_question_group(request, group_id):
    """Publish a question group. Limit: 10 publications per user per day."""
    pass

@ratelimit(key="user", rate="50/h", block=True)
def import_published_template(request, template_id):
    """Import published template. Limit: 50 imports per user per hour."""
    pass

@ratelimit(key="ip", rate="30/h", block=True)
def published_templates_list(request):
    """Browse templates library. Limit: 30 requests per IP per hour (public)."""
    pass
```

---

## 8. Tag System

### Base Tags (Pre-defined)

```python
BASE_TAGS = [
    # Clinical domains
    "depression", "anxiety", "mental-health", "wellbeing",
    "pain", "quality-of-life", "symptom-assessment",

    # Types
    "screening", "diagnostic", "outcome-measure", "feedback",
    "demographic", "administrative",

    # Validation
    "validated", "research", "clinical-trial-ready",

    # Populations
    "adult", "pediatric", "elderly", "primary-care", "specialist",

    # Specialties
    "cardiology", "oncology", "psychiatry", "neurology",
]
```

### User/Organization Custom Tags

- Users can add custom tags when publishing
- Tags are stored as list in `PublishedQuestionGroup.tags`
- Autocomplete suggests existing tags (from all publications user can see)
- Organizations can optionally define preferred tags (future enhancement)

### Tag UI

**When Publishing:**
```
Tags: [depression ×] [screening ×] [+Add tag]
      ↓ (autocomplete dropdown appears on typing)
      depression
      depression-screening
      depressive-disorder
```

**When Browsing:**
```
Popular tags: [depression] [anxiety] [pain] [wellbeing] [screening]
              (clicking adds to active filters)
```

---

## 9. Security & Permissions

### Permission Checks

```python
# In permissions.py

def can_publish_question_group(user: User, group: QuestionGroup, level: str) -> bool:
    """Check if user can publish a question group at given level."""
    if not group.owner == user:
        return False

    if level == "global":
        # Anyone can publish globally (immediate)
        return True

    if level == "organization":
        if not group.organization:
            return False
        membership = OrganizationMembership.objects.filter(
            user=user,
            organization=group.organization,
            role__in=['admin', 'creator']
        ).exists()
        return membership

    return False

def can_import_published_template(user: User, template: PublishedQuestionGroup) -> bool:
    """Check if user can import a published template."""
    if template.status != PublishedQuestionGroup.Status.ACTIVE:
        return False

    if template.publication_level == "global":
        return True

    if template.publication_level == "organization":
        if template.organization:
            return OrganizationMembership.objects.filter(
                user=user,
                organization=template.organization
            ).exists()

    return False
```

### Data Validation

1. **Markdown Sanitization:**
   - Existing parser already validates structure
   - No executable code in markdown
   - HTML comments safe (not rendered)

2. **Attribution Validation:**
   - Optional fields
   - ORCID format check: `^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$`
   - PMID format check: `^\d+$`
   - DOI format check: `^10\.\d{4,}/[^\s]+$`

3. **Tag Validation:**
   - Max 10 tags per template
   - Max 50 characters per tag
   - Lowercase, alphanumeric + hyphens only

4. **Rate Limiting:**
   - As defined in section 7

---

## 10. Migration Strategy

### Phase 1: Database Migration

1. Create `PublishedQuestionGroup` model
2. Add `imported_from` field to `QuestionGroup`
3. Create indexes

### Phase 2: Convert Existing Templates

**Patient Demographics & Professional Details:**

```python
# Migration script
def convert_specialist_templates():
    admin_user = User.objects.filter(is_superuser=True).first()

    # Create PublishedQuestionGroup for Patient Demographics
    patient_template = PublishedQuestionGroup.objects.create(
        name="Patient Demographics (Encrypted)",
        description="Secure patient identification and demographic data collection",
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        status=PublishedQuestionGroup.Status.ACTIVE,
        publisher=admin_user,
        markdown=generate_patient_template_markdown(),
        tags=["demographic", "patient-details", "encrypted", "administrative"],
        language="en",
        version="1.0",
        attribution={},  # Public domain / system template
    )

    # Same for Professional Details
    professional_template = PublishedQuestionGroup.objects.create(...)
```

**Keep existing schema-based implementation:**
- These templates still use `TEMPLATE_PATIENT` / `TEMPLATE_PROFESSIONAL` types
- Still render with checkbox UI
- **Also available** in published templates library
- Users can discover and add them like other published templates
- Both paths (template button OR published library) work

### Phase 3: Rollout

1. **Staff/Superuser Testing:**
   - Enable feature for superusers
   - Test publication, approval, import workflows
   - Verify attribution display

2. **Beta Release (Selected Organizations):**
   - Enable for 2-3 pilot organizations
   - Gather feedback on UX
   - Monitor performance and usage

3. **General Release:**
   - Enable for all users
   - Announce in docs and help center
   - Monitor support requests

---

## 11. UI/UX Design

### 11.1 Publication Button Placement

**Option A: QuestionGroup Detail Page**
```
┌────────────────────────────────────────┐
│ Question Group: PHQ-9                  │
│ [Edit] [Delete] [🌐 Publish]          │
└────────────────────────────────────────┘
```

**Option B: Survey Builder (Inline)**
```
┌────────────────────────────────────────┐
│ PHQ-9 Depression Screening             │
│ ⋮ [Reorder] [Edit] [🌐 Publish] [×]   │
└────────────────────────────────────────┘
```

**Recommendation: Both**
- Include button in both locations
- Consistent iconography and labeling

### 11.2 Templates Library Design

**Key Elements:**

1. **Cards with Clear Hierarchy:**
   - Title (large, bold)
   - Description (2 lines max, ellipsis)
   - Metadata row (publisher, level, usage count)
   - Tags (pills)
   - Attribution badge (if present)

2. **Visual Indicators:**
   - 🏢 Organization icon for org-level
   - 🌍 Globe icon for global
   - 🏆 Trophy/ribbon for attribution
   - 📥 Download/import icon for usage count

3. **Responsive Design:**
   - Grid layout (3 columns on desktop, 1 on mobile)
   - DaisyUI cards with hover effects

### 11.3 Attribution Display

**Badge + Tooltip Pattern:**

```html
<div class="badge badge-info tooltip" data-tip="Kroenke et al. (2001), PMID: 11556941">
  🏆 Acknowledgement
</div>
```

**Footer in Participant View:**

```html
<div class="bg-base-200 p-4 rounded-lg mt-6">
  <h3 class="font-bold mb-2">{% trans "Acknowledgements" %}</h3>
  <p class="text-sm">{% trans "This survey includes:" %}</p>
  <ul class="list-disc list-inside text-sm space-y-1">
    {% for attribution in survey.attributions %}
      <li>{{ attribution.citation }}</li>
    {% endfor %}
  </ul>
</div>
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
class PublishedQuestionGroupTests(TestCase):
    def test_individual_user_can_publish_global(self):
        """Individual user can publish global immediately."""

    def test_org_creator_can_publish_org_immediate(self):
        """Org CREATOR can publish to organization immediately."""

    def test_soft_delete_hides_from_library(self):
        """Soft deleting template removes it from library but preserves record."""

    def test_import_increments_counter(self):
        """Importing template increments import_count."""

    def test_attribution_preserved_in_markdown(self):
        """Attribution included as HTML comment in exported markdown."""

    def test_markdown_roundtrip_integrity(self):
        """QuestionGroup -> Markdown -> QuestionGroup preserves structure."""
```

### 12.2 Integration Tests

```python
class PublicationWorkflowTests(TestCase):
    def test_full_publication_workflow(self):
        """Test complete flow: create group, publish, approve, import."""

    def test_org_level_visibility(self):
        """Org-level templates only visible to org members."""

    def test_rate_limiting(self):
        """Rate limits enforced on publication and import."""
```

### 12.3 UI Tests (Playwright/Selenium)

- Test publication form submission
- Test template library search and filters
- Test import with question selection checkboxes
- Test attribution display in builder and participant view

---

## 13. Documentation Updates

### 13.1 User Documentation

1. **New Page: Publishing Question Groups**
   - How to publish
   - Attribution guidelines
   - Organization vs. global levels
   - Tag best practices

2. **New Page: Using Published Templates**
   - Browsing the library
   - Importing templates
   - Customizing imported questions
   - Attribution requirements

3. **Update: Survey Builder Guide**
   - Add section on "Add from Templates" button
   - Link to published templates library

### 13.2 API Documentation

- Add endpoints to API docs
- Include request/response examples
- Document rate limits

### 13.3 Self-Hosting Guide

- Environment variables (if any)
- Migration instructions
- Superuser approval workflow

---

## 14. Future Enhancements (Out of Scope for v1)

### 14.1 Versioning

- Allow updating published templates
- Track version history
- Users can choose which version to import

### 14.2 Collections/Bundles

- Publish multiple related QuestionGroups as a bundle
- E.g., "Mental Health Screening Suite" with PHQ-9, GAD-7, PSS-10

### 14.3 Analytics

- View statistics on template popularity
- See which templates used in which surveys (privacy-preserving)

### 14.4 Community Features

- Comments on templates
- Ratings/reviews (with moderation)
- Featured templates showcase

### 14.5 Import from External Sources

- Import from FHIR Questionnaire
- Import from REDCap instruments
- Import from PROMIS item banks

---

## 15. Implementation Checklist

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Create `PublishedQuestionGroup` model (with show_publisher_credit field)
- [x] Add `imported_from` to `QuestionGroup`
- [x] Run migrations (0026, 0027)
- [x] Add permission helper functions
- [x] Write model methods: `to_markdown()`, `from_markdown_with_attribution()`

### Phase 2: Publication Workflow ✅ COMPLETE
- [x] Create publication form view
- [x] Create publication submission endpoint
- [x] Add validation logic
- [x] Implement rate limiting (10/day publish, 50/hr import)
- [x] Add success notifications

### Phase 3: Discovery & Import ✅ COMPLETE
- [x] Create templates library page (with pagination)
- [x] Implement search and filtering (tags, level, language, search)
- [x] Create import endpoint
- [x] Add question selection checkboxes (import preview step)
- [x] Update survey builder with "Browse & Import Templates" button

### Phase 4: Attribution ✅ COMPLETE
- [x] Add attribution fields to publication form
- [x] Include attribution in markdown export
- [x] Display attribution badge in builder (tooltip with info icon)
- [x] Display attribution in template listings
- [x] Add attribution parsing in import flow

### Phase 4.5: Global Template Repository ✅ COMPLETE (BONUS)
- [x] Create sync_global_question_group_templates management command
- [x] Add YAML frontmatter support for template metadata
- [x] Create PHQ-9 template in docs/
- [x] Create documentation (publish-question-groups.md, templates index)
- [x] Add publisher credit system with privacy controls

### Phase 5: API ⏳ NOT STARTED
- [ ] Implement API endpoints
- [ ] Add API documentation
- [ ] Add API rate limiting
- [ ] Write API tests

### Phase 6: UI/UX Polish ⏳ PARTIAL
- [x] Design and implement template cards
- [x] Add icons and badges
- [x] Implement responsive layouts
- [ ] Add loading states and error handling
- [ ] i18n for all new strings (partially done)

### Phase 7: Testing ✅ SUBSTANTIAL COVERAGE
- [x] Write unit tests for models and permissions
- [x] Write integration tests for publication workflow
- [x] Test markdown export
- [x] Test template discovery and filtering
- [x] Test attribution display
- [x] Test global template sync command
- [x] Test republishing prevention (copyright protection)
- [ ] Write UI tests for template library and import
- [ ] Test rate limiting enforcement
- [ ] Manual QA testing
- [ ] Accessibility testing

### Phase 8: Documentation
- [ ] Write user documentation
- [ ] Update API docs
- [ ] Update self-hosting guide
- [ ] Create video tutorials (optional)

### Phase 9: Specialist Template Conversion ⏳ NEXT PRIORITY

**UI Strategy:**
- Keep existing "Add Patient Demographics" and "Add Professional Details" buttons for quick access
- Add "Browse Question Group Templates" button that links to existing `/templates/` page
- Patient/Professional templates appear in Question Group Template Library for discoverability
- All templates (including Patient/Professional) use same checkbox selection UI on import
- Consistent terminology throughout: "Question Group Template Library"

**Implementation Tasks:**
- [ ] Convert Patient Demographics template to published format
- [ ] Convert Professional Details template to published format
- [ ] Add "Browse Question Group Templates" button to question builder
- [ ] Ensure import flow redirects back to builder after import
- [ ] Write tests for converted templates
- [ ] Update documentation with consistent terminology
- [ ] Verify backward compatibility

### Phase 10: GitHub Issue Templates
- [ ] Ensure issue templates include dataset options
- [ ] Ensure issue templates include question group options

### Phase 11: Deployment
- [ ] Deploy to staging
- [ ] Beta test with pilot organizations
- [ ] Deploy to production
- [ ] Monitor and iterate

---

## 16. Open Questions & Decisions Needed

### Decision 1: Specialist Templates (RESOLVED)
✅ **Decision:** Use Option A (Schema-Based) for all published templates. Users can revise question selection after import without re-importing. Patient/Professional templates converted to published QuestionGroups using same schema-based pattern.

### Decision 2: Markdown Architecture (RESOLVED)
✅ **Decision:** Keep existing markdown parsing system. Add QuestionGroup export method and minor enhancements for attribution handling.

### Decision 3: Delete Behavior (RESOLVED)
✅ **Decision:** Option A - Soft delete (mark as deleted, hide from library, keep record for integrity)

**Rationale:** Preserves audit trail, attribution in existing surveys, and provides clear "Template no longer available" messaging if users try to view the source.

### Decision 4: Update Behavior (RESOLVED)
✅ **Decision:** Option A - No updates after approval (immutable)

**Rationale:** Published templates are immutable after approval. If publishers need to make changes, they must publish a new version. This ensures imported templates remain consistent with their source and simplifies versioning in future enhancements.

### Decision 5: Organization-Level Approval (RESOLVED)
✅ **Decision:** Option A - No approval needed for organization-level OR individual global publications

**Rationale:**
- Organization-level: CREATOR/ADMIN can publish immediately to their org (simpler workflow, only visible to org members)
- Individual global: Individual users can also publish globally immediately without superuser approval
- Trust-based model appropriate for sandbox/early adoption phase
- Can add approval workflow later if abuse becomes an issue

### Decision 6: Template Visibility (RESOLVED)
✅ **Decision:** Option A - Completely hidden from non-members

**Rationale:** Organization templates are completely invisible to non-members. Privacy by default in healthcare context, simpler query logic, no confusion about inaccessible templates.

### Decision 7: Markdown Attribution Format (RESOLVED)
✅ **Decision:** Option C - Both human-readable and machine-readable JSON

**Format:**
```markdown
<!-- Attribution: Kroenke et al. (2001), PMID: 11556941
     {"authors": [{"name": "Kurt Kroenke", "orcid": "0000-0002-0393-2664"}], "pmid": "11556941"} -->
```

**Rationale:** Human-readable first line for easy reading, optional JSON on following lines for structured parsing. Parser can extract either format as needed.

---

## 17. Success Metrics

**v1 Goals (6 months post-launch):**

1. **Adoption:**
   - 50+ published templates (global + organization)
   - 20+ organizations publishing templates
   - 500+ template imports

2. **Quality:**
   - 80%+ of global templates include attribution
   - <5% rejection rate for global submissions
   - <10 support tickets related to publishing feature

3. **Performance:**
   - Template library loads in <2 seconds
   - Import completes in <5 seconds
   - No impact on existing survey builder performance

4. **User Satisfaction:**
   - Feature mentioned in 25%+ of user feedback
   - Positive sentiment on published templates feature

---

## Appendix A: Example Attribution

### PHQ-9 (Patient Health Questionnaire)

```json
{
  "authors": [
    {"name": "Kurt Kroenke", "orcid": "0000-0002-0393-2664"},
    {"name": "Robert L. Spitzer", "orcid": null},
    {"name": "Janet B.W. Williams", "orcid": null}
  ],
  "citation": "Kroenke, K., Spitzer, R. L., & Williams, J. B. (2001). The PHQ-9: validity of a brief depression severity measure. Journal of General Internal Medicine, 16(9), 606-613.",
  "pmid": "11556941",
  "doi": "10.1046/j.1525-1497.2001.016009606.x",
  "license": "Public Domain",
  "year": 2001
}
```

### GAD-7 (Generalized Anxiety Disorder Scale)

```json
{
  "authors": [
    {"name": "Robert L. Spitzer", "orcid": null},
    {"name": "Kurt Kroenke", "orcid": "0000-0002-0393-2664"},
    {"name": "Janet B.W. Williams", "orcid": null},
    {"name": "Bernd Löwe", "orcid": null}
  ],
  "citation": "Spitzer, R. L., Kroenke, K., Williams, J. B., & Löwe, B. (2006). A brief measure for assessing generalized anxiety disorder: the GAD-7. Archives of Internal Medicine, 166(10), 1092-1097.",
  "pmid": "16717171",
  "doi": "10.1001/archinte.166.10.1092",
  "license": "Public Domain",
  "year": 2006
}
```

---

## Appendix B: Markdown Format with Attribution

```markdown
<!-- Attribution: {"authors": [{"name": "Kurt Kroenke", "orcid": "0000-0002-0393-2664"}], "citation": "Kroenke, K., et al. (2001)", "pmid": "11556941", "license": "Public Domain", "year": 2001} -->

# PHQ-9 Depression Screening {phq9}

Over the last 2 weeks, how often have you been bothered by any of the following problems?

## Little interest or pleasure in doing things* {phq9-q1}
(likert categories)
- Not at all
- Several days
- More than half the days
- Nearly every day

## Feeling down, depressed, or hopeless* {phq9-q2}
(likert categories)
- Not at all
- Several days
- More than half the days
- Nearly every day

## Trouble falling or staying asleep, or sleeping too much* {phq9-q3}
(likert categories)
- Not at all
- Several days
- More than half the days
- Nearly every day

...
```

---

**End of Plan Document**

**Next Steps:**
1. Review and approve this plan
2. Discuss and finalize open questions (Section 16)
3. Prioritize phases for implementation
4. Begin Phase 1: Core Infrastructure
