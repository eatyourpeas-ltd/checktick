---
title: AI-Assisted Survey Generator
category: features
priority: 3
---

The AI-assisted survey generator helps you create healthcare surveys through natural conversation with a large language model (LLM). This feature is available alongside the manual markdown import option.

> **Note:** This feature requires configuration of an LLM API endpoint. If you don't see the "AI Assistant" tab in the Import Questions page, the feature may not be enabled for your instance. See [Self-Hosting Configuration](/docs/self-hosting-configuration/) for setup details.

## Overview

Instead of writing markdown manually, you can describe your survey requirements in plain English to the AI assistant. The assistant will:

1. Ask clarifying questions about your survey goals
2. Generate properly formatted survey questions in CheckTick markdown
3. Refine the survey based on your feedback
4. Help you iterate until you have exactly what you need

**Important:** The AI generates markdown for you to review and import. It cannot directly modify your surveys - you remain in full control.

## Who Can Use This Feature

Access to the AI survey generator is restricted to:

- **Organisation administrators** - Can create surveys for their organisation
- **Survey creators** - Can create surveys they own
- **Individual account holders** - Can create their own surveys

Organisation viewers/members cannot use this feature.

## How to Use

### 1. Access the AI Assistant

Navigate to your survey's "Import Questions" page. If the feature is enabled, you'll see two tabs:

- **Manual Input** - Traditional markdown import (see [Bulk Survey Import](/docs/import/))
- **AI Assistant** - Conversational survey generation

Click the **AI Assistant** tab to begin.

### 2. Start a Conversation

The AI assistant will greet you and ask about your survey requirements. Describe what you need in natural language, for example:

```
I need a patient satisfaction survey for our pediatric diabetes clinic.
We want to know about appointment experience, staff interactions,
and understanding of care instructions.
```

### 3. Provide Details

The assistant will ask clarifying questions such as:

- What is your target population?
- What clinical area are you focusing on?
- Do you need specific validated scales?
- How many questions are appropriate?
- Should any questions be required?

Answer these questions to help the AI generate a relevant survey.

### 4. Review Generated Markdown

The AI will generate survey questions in CheckTick markdown format. The markdown will appear in the conversation and automatically sync to the markdown input field on the left.

Example output:

```markdown
# Patient Satisfaction {patient-satisfaction}

## How would you rate your overall experience?* {overall-rating}
(likert number)
min: 1
max: 5
left: Very dissatisfied
right: Very satisfied

## The appointment time was convenient {appointment-time}
(yesno)
```

### 5. Refine and Iterate

You can ask the AI to:

- Add or remove questions
- Change question types
- Adjust wording
- Add branching logic
- Include follow-up text inputs
- Make questions required/optional

Example refinement requests:

```
Can you make the rating question use categories instead of numbers?

Add a question about wait times that only shows if they rated less than 3.

Include a "prefer not to answer" option for the demographic questions.
```

### 6. Import the Survey

Once satisfied with the markdown:

1. Review the preview on the right side
2. Click the **Import Questions** button
3. Confirm the import to create your survey

The import works exactly like the manual markdown import - all existing questions will be replaced.

## What the AI Can Do

### Question Types

The AI can generate all CheckTick question types:

- Text input (short and numeric)
- Multiple choice (single and multi-select)
- Dropdown menus
- Yes/No toggles
- Likert scales (numeric and categorical)
- Orderable lists
- Image choices

### Advanced Features

The AI understands and can generate:

- **Required questions** - Marked with `*`
- **Follow-up text inputs** - Using `+` notation
- **Conditional branching** - Questions that show based on answers
- **Repeatable collections** - For multiple entries (visits, patients, etc.)
- **Nested repeat groups** - Up to one level of nesting
- **Validated scales** - PHQ-9, GAD-7, and other standardized instruments

### Healthcare Best Practices

The AI is trained to follow healthcare survey best practices:

- Uses 8th grade reading level language
- Avoids medical jargon unless necessary
- One concept per question
- Suggests "Prefer not to answer" for sensitive topics
- Keeps surveys concise (typically under 20 questions)
- Groups questions logically
- Applies validated clinical scales appropriately

## What the AI Cannot Do

### Security Restrictions

For your safety and data protection:

- **No internet access** - The AI cannot search the web or access external resources
- **No external tools** - Cannot run code or access databases
- **Read-only operations** - Cannot directly modify your surveys
- **No patient data** - Cannot and should not see patient information
- **No medical advice** - Designed for survey structure only, not clinical guidance

### Format Limitations

The AI can only generate markdown in CheckTick format. It cannot:

- Import surveys from other platforms
- Convert from other markdown flavors
- Generate surveys in other formats (Word, PDF, etc.)
- Create custom question types beyond those supported

## Transparency: How the AI Works

### The System Prompt

To ensure transparency about what the AI can and cannot do, we publish the complete system prompt that guides the AI's behavior.

**Last Updated:** 2025-11-17

The AI receives the following instructions for every conversation:

---

<!-- SYSTEM_PROMPT_START -->
You are a healthcare survey design assistant. Your role is to help users create surveys by generating questions in a specific markdown format.

CORE RESPONSIBILITIES:
1. Ask clarifying questions about survey goals, target audience, and question requirements
2. Generate survey questions ONLY in the specified markdown format
3. Refine questions based on user feedback
4. Ensure questions are clear, unbiased, and appropriate for healthcare contexts

MARKDOWN FORMAT YOU MUST USE:

# Group Name {group-id}
Optional group description

## Question Text {question-id}*
(question_type)
- Option 1
- Option 2
  + Follow-up text prompt
? when = value -> {target-id}

ALLOWED QUESTION TYPES:
- text: Short text input
- text number: Numeric input with validation
- mc_single: Single choice (radio buttons)
- mc_multi: Multiple choice (checkboxes)
- dropdown: Select dropdown menu
- orderable: Orderable list
- yesno: Yes/No toggle
- image: Image choice
- likert number: Scale (e.g., 1-5, 1-10) with min:/max:/left:/right: labels
- likert categories: Scale with custom labels listed with -

MARKDOWN RULES:
- Use `*` after question text for required questions
- Group related questions under `# Group Name {group-id}`
- Each question needs unique {question-id}
- Options start with `-`
- Follow-up text inputs use `+` indented under options
- Branching uses `? when <operator> <value> -> {target-id}`
- Operators: equals, not_equals, contains, greater_than, less_than, greater_than_or_equal, less_than_or_equal
- For REPEAT collections: Add REPEAT or REPEAT-N above group heading
- For nested collections: Use `>` prefix for child groups

HEALTHCARE BEST PRACTICES:
- Use 8th grade reading level language
- Avoid medical jargon unless necessary
- One topic per question
- Include "Prefer not to answer" for sensitive topics
- Keep surveys under 20 questions when possible
- Group logically (demographics, symptoms, satisfaction, etc.)
- Use validated scales when applicable (PHQ-9, GAD-7, etc.)

CONVERSATION APPROACH:
1. First message: Ask about survey goal, target population, clinical area
2. Clarify question types needed and any specific requirements
3. Generate initial markdown survey
4. Refine based on user feedback
5. When outputting markdown, wrap it in ```markdown code fences for clarity

IMPORTANT:
- You cannot access the internet or use external tools
- When users ask about survey content, respond in plain English without using markdown format terminology
- If users ask specific questions about the markdown format syntax, you MAY provide format guidance and examples
- Otherwise, avoid referencing the format language - ask directly about features (e.g., "Do you need branching?" instead of "Do you need conditional logic syntax?")
- When summarising the survey structure, explain in plain English what you've created rather than using technical markdown terms
- You can only generate markdown in the format specified above
- You cannot provide medical advice or clinical guidance
- Focus on survey design and question clarity only
- When providing survey markdown, wrap it in ```markdown...``` code blocks
- You can include conversational text before or after the markdown block
- Example response format: "Here's your survey:\n\n```markdown\n# Group...\n```"
<!-- SYSTEM_PROMPT_END -->

---

This prompt is loaded directly from this documentation and may be updated periodically to improve the AI's performance. Any changes to the prompt will be reflected here with an updated timestamp.

### LLM Provider

CheckTick uses the **RCPCH Ollama** service, a secure, healthcare-focused LLM endpoint maintained by the Royal College of Paediatrics and Child Health (RCPCH). This service:

- Runs in a secure, isolated environment
- Does not train on your data
- Does not retain conversation history beyond the session
- Complies with healthcare data protection requirements

## Conversation Sessions

### Session Management

Each survey import session maintains a separate conversation history:

- Sessions are isolated per user
- You cannot access another user's sessions
- Old sessions are automatically deactivated when you start a new one
- Session history is stored in your database for audit purposes

### Session Data

Each session stores:

- Conversation history (your messages and AI responses)
- Current generated markdown
- Timestamp of creation and updates
- Associated survey and user

This data is subject to your instance's data governance policies.

## Tips for Best Results

### Be Specific

Instead of:
> "I need a patient survey"

Try:
> "I need a 10-question patient satisfaction survey for pediatric outpatient appointments, focusing on wait times, staff communication, and care understanding"

### Iterate Gradually

Make one change at a time rather than requesting multiple complex modifications. This helps the AI maintain context and produces better results.

### Review Carefully

Always review the generated markdown before importing:

- Check question IDs are appropriate
- Verify branching logic is correct
- Ensure required questions are marked
- Test the preview on the right side

### Use the Preview

The real-time preview shows exactly how your survey will appear, including:

- Automatically generated question IDs
- Required field indicators
- Conditional branching paths
- Repeat collection structures

## Troubleshooting

### "AI Assistant tab not visible"

The feature requires configuration. Contact your instance administrator to enable the LLM integration. See [Self-Hosting Configuration](/docs/self-hosting-configuration/) for setup instructions.

### "Session creation failed"

Ensure you have appropriate permissions (admin, creator, or individual account holder). Organisation viewers cannot access this feature.

### "LLM is not responding"

Check that:

1. Your instance has the LLM_URL configured
2. Your instance has a valid LLM_API_KEY
3. The LLM service is operational

Contact your administrator if issues persist.

### "Generated markdown doesn't import"

The AI occasionally makes formatting errors. Common issues:

- Missing closing braces `}` in identifiers
- Invalid question type names
- Malformed branching syntax

Review the markdown manually and correct any syntax errors before importing.

## Privacy and Security

### Security Overview

The AI Survey Generator is designed with security as a priority. For comprehensive security details, see our [LLM Security Documentation](/docs/llm-security/).

**Key security features:**
- No tool access - LLM cannot access files, databases, or execute code
- Sandboxed output - Only generates markdown in validated format
- Transparent system prompt - Published in this documentation
- Prompt injection protection - Designed to resist manipulation attempts
- Output sanitization - All content validated before display

### What Data is Sent to the LLM

When you use the AI assistant, the following is sent:

- Your conversation messages
- Previous messages in the current session
- The system prompt (instructions for the AI)

**Not sent:**

- Patient data
- Other users' surveys
- Your organisation's other data
- Authentication credentials

### Data Retention

- Conversation history is stored in your CheckTick database
- The RCPCH Ollama service does not retain conversations after the API call
- Session data follows your instance's data governance policies
- Administrators can audit LLM usage via audit logs

### Audit Logging

All LLM operations are logged, including:

- Session creation
- Messages sent and received
- User who performed the action
- Timestamp of each operation

This ensures full accountability and traceability.

## Related Documentation

- [LLM Security & Safety](/docs/llm-security/) - Comprehensive security documentation
- [Bulk Survey Import](/docs/import/) - Manual markdown import syntax
- [Survey Builder](/docs/surveys/) - Visual survey editor
- [Collections](/docs/collections/) - Repeatable question groups
- [Authentication & Permissions](/docs/authentication-and-permissions/) - Access control details

## Need Help?

See the [Getting Help](/docs/getting-help/) guide for support options.
