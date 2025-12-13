---
title: Survey Translation
category: internationalization
priority: 3
---

# Survey Translation

CheckTick supports creating and publishing surveys in multiple languages. This is essential for reaching diverse populations and ensuring healthcare surveys are accessible to all respondents.

For information about CheckTick's **interface languages** (menus, buttons, labels), see [Language Support](/docs/i18n/).

## Creating Translations

You can create translations in two ways:

### AI-Assisted Translation (Recommended)

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

### Manual Translation

1. Create a translation as above
2. Go to the translation's Question Builder
3. Manually edit all text content

## Re-Translating Existing Surveys

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

## Important Notes About AI Translations

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

## Publishing Translations

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

## What Gets Translated

- Survey name and description
- Question group names and descriptions
- Question text
- Multiple choice options
- Dropdown options
- Follow-up text input labels
- Likert scale labels
- Yes/No button text

## What Stays the Same Across Languages

- Question IDs and structure
- Conditional logic rules
- Data validation rules
- Survey settings and permissions

## Security & Technical Details

For complete details on translation implementation and security, see [AI Security & Safety](/docs/llm-security/).

## Supported Languages

CheckTick translations can be created in any of the supported interface languages:

| Language | Code | RTL |
|----------|------|-----|
| English (UK) | en-gb | No |
| English (US) | en | No |
| Welsh | cy | No |
| French | fr | No |
| Spanish | es | No |
| German | de | No |
| Italian | it | No |
| Portuguese | pt | No |
| Polish | pl | No |
| Arabic | ar | Yes |
| Simplified Chinese | zh-hans | No |
| Hindi | hi | No |
| Urdu | ur | Yes |

Right-to-left (RTL) languages are fully supported with appropriate text direction handling.
