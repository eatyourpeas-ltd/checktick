---
title: Surveys
category: features
priority: 1
---

This guide explains how to create an organisation, create a survey, and how content is structured into question groups and questions.

## Organisations

Organisations own surveys and manage access. Each organisation has:

- Owner — the user who created the org
- Members — users with roles: Admin, Creator, Viewer

Admins can manage members and surveys. Creators can build and manage surveys. Viewers can view responses/analytics (when enabled) but cannot edit structure.

## Create an organisation

1. Sign up or log in
2. Go to Profile
3. Click “Upgrade to organisation” and enter a name

You’ll become an Admin and can invite others from the User management area.

## Create a survey

1. Go to Surveys
2. Click "Create survey"
3. Choose an organisation (optional), name, and slug (this is the name that appears in the url so should have no spaces but words can be hyphenated)
4. Save to open the survey dashboard

From the dashboard you can set style/branding, manage members, and build content.

## Create a copy

You can create a copy of any survey you own or have Creator access to. This is useful for:

- Creating variations of a survey for different audiences
- Making a template for reuse
- Starting a new survey based on an existing structure

**How to clone a survey:**

1. Open the survey dashboard
2. Click the "Create a copy" button
3. The copy opens immediately with a new slug (original-slug-copy)
4. Edit the name and slug as needed

**What gets copied:**

- All question groups and questions
- Question types, options, and logic
- Follow-up text configurations
- Conditional branching rules
- Repeat/collection structures
- Styling and branding settings

**What does NOT get copied:**

- Survey responses
- Translations (you'll need to create these separately for the cloned survey)
- Member access (only you have access to the new survey)
- Publication status (clone starts as draft)
- Access tokens

## Edit survey title

You can update the survey title after creation:

1. From the survey dashboard, click the edit icon next to the survey name
2. Enter the new title in the dialog
3. Save - the title updates immediately

**Note:** Only users with Creator or Admin permissions can edit survey titles.

## Question groups vs questions

Question Groups are the building blocks for structuring a survey. They act like chapters: each group has a title, optional description, and an ordered list of questions. Groups keep longer surveys manageable, let you show section-specific instructions, and provide obvious breakpoints when branching to different parts of a journey. Questions can be reordered within a group, and groups themselves can be reordered from the builder sidebar.

Questions live inside a single group. When you add a question, the builder automatically associates it with the group you have open. Moving a question to another group updates that association immediately—there is no detached “question bank.” If you delete a group, its questions are also deleted. This ensures that every question always has a clear place in the survey hierarchy.

You can use Text Entry when you already have content drafted. Text Entry lets you specify groups and questions in a single text document: top-level headings become groups, and nested headings/items become questions. After import you can continue refining groups and questions in the Question Builder.

## Question types

Supported types (as of now):

- Free text (`text`) or (`number`): short/long text answers or numbers
- Multiple choice — single (`mc_single`)
- Multiple choice — multiple (`mc_multi`)
- Dropdown (`dropdown`)
- Likert scale (`likert`): numeric or descriptor/categorical scales
- Yes/No (`yesno`)
- Orderable list (`orderable`): reorder options
- Image choice (`image`): choose from visual options

Some types use options metadata. Examples:

- `mc_single` / `mc_multi` / `dropdown` / `image`: provide a list of options
- `likert`: provide min/max, labels (e.g., 1–5 with left/right captions)
- `text`: optional format hint (e.g., constrained formats) used in previews

You can preview questions in the builder, reorder them, and group them as needed.

### Follow-up text inputs

For certain question types, you can configure **follow-up text inputs** that appear conditionally based on the respondent's answer. This is useful when you need additional detail for specific options (e.g., "If you selected 'Other', please explain").

**Supported question types:**

- Multiple choice — single (`mc_single`)
- Multiple choice — multiple (`mc_multi`)
- Dropdown (`dropdown`)
- Yes/No (`yesno`)
- Orderable list (`orderable`)

**How to configure follow-up inputs:**

1. In the question builder, select a question of a supported type
2. For each option where you want a follow-up text input, check the "Enable follow-up text" checkbox
3. Enter a custom label for the follow-up input (e.g., "Please describe your concerns")
4. Save the question

**How it works for respondents:**

When a respondent selects an option that has follow-up text enabled, a text input field appears with your custom label. The field is hidden if they select a different option. For multiple-choice questions with multiple selections, they can see follow-up fields for each selected option that has it enabled.

**Visual indicator:**

Questions with follow-up inputs configured will show a badge in the question card listing which options have follow-up text. This helps you quickly identify questions with this feature when managing your survey.

### Conditional branching

Individual questions can define conditional logic that determines what a respondent sees next. Branching is configured per question from the “Logic” tab in the builder:

- **Show/Hide conditions** — Display a question only when previous answers match the criteria you set (e.g., show follow-up questions when someone answers "Yes").
- **Skip logic** — Jump the respondent to another question group once they pick a certain answer. This is useful for ending a survey early or routing different audiences to tailored sections.
- **Option-level rules** — For multiple-choice questions you can create separate rules for each option. For free-text or numeric answers, use comparators (equals, greater than, contains, etc.) to match values.

The logic engine evaluates conditions in order, so place the most specific rule first. A question without any conditions simply follows the survey’s default ordering. When branching sends a respondent to a later group, intervening groups are skipped automatically.

**Tip:** Keep at least one unconditional path through every group so respondents cannot get trapped. In testing environments the builder logs a warning when conditional tables are missing—run the latest migrations before enabling branching in production.

## Managing access to surveys

- Add survey members with roles (Creator, Viewer)
- Organisation Admins can manage any survey within their org
- Survey Creators can edit structure and manage members for that survey

## Progress tracking

CheckTick automatically saves respondents' progress as they complete surveys, allowing them to:

- See their completion progress with a visual progress bar
- Leave and return later without losing their work
- Have previous answers automatically restored

Progress tracking works with all survey access methods (authenticated, unlisted, and token-based) and all question types. The feature uses auto-save (3 seconds after changes) and provides real-time feedback on save status.

For complete technical details, see [Survey Progress Tracking](/docs/survey-progress-tracking/).

## Multi-language surveys

CheckTick supports creating and publishing surveys in multiple languages. This is essential for reaching diverse populations and ensuring healthcare surveys are accessible to all respondents.

### Creating translations

You can create translations in two ways:

**1. AI-assisted translation (recommended for initial draft):**

1. Open the survey dashboard
2. Go to "Manage Translations"
3. Click "Create translation"
4. Select the target language
5. The system uses AI (LLM) to translate all content:
   - Survey name and description
   - Question group names and descriptions
   - Question text
   - Multiple choice options
   - Follow-up text prompts
6. Review and edit the translation (see important notes below)

**2. Manual translation:**

1. Create a translation as above
2. Go to the translation's Question Builder
3. Manually edit all text content

### Re-translating existing surveys

If you need to update an existing translation (for example, after changing the source survey or improving terminology):

1. Open the **translated** survey's dashboard (not the original)
2. Click the "Translate Again" button
3. Confirm you want to overwrite existing translations
4. The system will:
   - Re-translate all content using the current source survey
   - Preserve the survey structure and settings
   - Keep the same URL and slug
   - Maintain any responses already collected

**Important:** "Translate Again" overwrites the translated text but preserves:
- Survey settings and permissions
- Question structure and IDs
- Conditional logic
- All collected responses
- Publication status

**Use cases for Translate Again:**
- Source survey was updated after initial translation
- You want to try a different translation approach
- Medical terminology needs updating
- LLM produced better translations with improved prompts

**Note:** If the re-translation fails, your existing translation is preserved unchanged. The system only updates the translation if the process completes successfully.

### Important notes about AI translations

**AI translations should always be reviewed by a native speaker before publication**, especially for:

- Medical terminology accuracy
- Cultural appropriateness
- Idiomatic expressions
- Technical precision

The AI provides confidence levels:

- **High**: Generally accurate, but still review
- **Medium**: Some terms may need professional review
- **Low**: Significant uncertainty, professional translator recommended

**Best practice:** Have a healthcare professional who speaks the target language review all AI-generated translations before publishing to patients.

### Publishing translations

Each language version can be published independently:

1. Go to the survey's Publish Settings
2. You'll see separate sections for:
   - **Published translations** (live versions with view links)
   - **Draft translations** (not yet published)
3. Test draft translations using the preview link
4. Publish translations individually or together
5. Each translation gets its own URL: `/surveys/{slug}/take/`

**Language badges:**

Throughout the interface, you'll see language flags indicating:

- Which languages are published (green badge)
- Which are still in draft (yellow badge)
- Click flags to switch between language versions

### What gets translated

- Survey name and description
- Question group names and descriptions
- Question text
- Multiple choice options
- Dropdown options
- Follow-up text input labels
- Likert scale labels
- Yes/No button text

### What stays the same across languages

- Question IDs and structure
- Conditional logic rules
- Data validation rules
- Survey settings and permissions

For complete details on translation implementation and security, see [AI Security & Safety](/docs/llm-security/).

## Repeats (nested, repeatable sections)

Repeats allow you to model repeatable structures in surveys, such as collecting data for multiple patients, visits, or treatments. Key features:

- Create collections from question groups (e.g., "Patient" collection)
- Support one level of nesting (e.g., Patient → Visits)
- Set minimum and maximum instances
- Respondents can add/remove instances as needed
- Answers stored as nested JSON structures

Repeats are managed from the Groups page using the "Create repeat from selection" button. For complete details on data models, response structure, and implementation, see [Repeats (Nested, Repeatable Sections)](/docs/collections/).

## Next steps

- See [Question Groups](/docs/groups-view/) to learn about organizing and sharing questions
- See [Branding and Theme Settings](/docs/branding-and-theme-settings/) to customize appearance
- See [Getting Started with the API](/docs/getting-started-api/) to seed questions programmatically
