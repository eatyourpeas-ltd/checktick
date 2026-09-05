---
title: Branching Logic & Repeating Questions
category: features
priority: 5
---

Guide to creating intelligent surveys with conditional logic and repeating sections.

## Overview

CheckTick allows you to create dynamic surveys that adapt based on user responses through two powerful features:

1. **Branching Logic** - Show, skip, or jump to questions based on previous answers
2. **Repeating Questions** - Allow users to answer the same section of questions multiple times

These features work together to create sophisticated survey workflows while keeping the user experience simple and intuitive.

## Branching Logic

Branching logic (also called conditional logic) lets you control which questions users see based on their previous answers. This creates a personalized survey experience and reduces unnecessary questions.

### How It Works

You can add conditions to any question to control when it appears. For example:

- Show a follow-up question only if someone selects "Yes"
- Skip past irrelevant questions based on earlier answers
- Jump ahead to a specific section depending on the response
- End the survey early for certain answer paths

### Types of Actions

When a condition is met, you can choose what happens:

- **Show** - Reveal a question that is hidden by default (only valid against hidden-by-default questions)
- **Hide** - Hide a question that is shown by default (only valid against shown-by-default questions)
- **Jump to** - Skip ahead to a specific question or section (forward only)
- **End Survey** - Complete the survey immediately

`Show` and `Hide` are visibility overrides on a single question. `Jump to` is the only navigation action, and it's the only one that can target a whole section. Sections themselves don't have a visibility toggle — you navigate to them with `Jump to`.

### Hidden by default

Every question has a **Hidden by default** toggle. This declares the question's default visibility on the question itself, rather than as a side-effect of conditions elsewhere:

- **Off** (default) — the question is shown unless a `Hide` condition hides it.
- **On** — the question is hidden unless a `Show` condition reveals it.

This keeps conditions simple: a `Show` condition can only target a hidden-by-default question, and a `Hide` condition can only target a shown-by-default question. You can't accidentally add contradictory conditions — the Builder only offers the action that makes sense for the target's toggle.

If you mark a question hidden by default but add no `Show` condition for it, the Builder warns you — the question would never appear.

### Creating Conditions

#### Using the Web Builder

1. Navigate to your survey in the builder
2. Click on any question to edit it
3. Click "Add Condition" in the conditions section
4. Choose:
   - **Which previous question** to check
   - **What answer** triggers the condition
   - **What action** to take
5. Save the condition

You can add multiple conditions to a single question - the survey will check them in order.

#### Using Outline

You can also define branching logic using markdown syntax. Conditions use the `?` prefix with an optional action keyword and the `->` arrow:

```markdown
## Would you like to provide feedback? {want-feedback}
(yesno)
? show when equals "Yes" -> {feedback-details}
? when equals "No" -> #Closing            # jump to the Closing section
? end  when equals "N/A"                  # end the survey

## Feedback details {feedback-details}
(text_long)
HIDDEN                                   # hidden by default, shown by the Show condition above
What would you like to tell us?
```

The action keyword is optional — if you omit it, the condition defaults to `Jump to`. So existing outlines that use `? when ... -> {target}` keep working unchanged.

**Action keywords:**

- `show` — reveal a hidden-by-default question (target must be marked `HIDDEN`)
- `hide` — hide a shown-by-default question (target must not be marked `HIDDEN`)
- `end` — end the survey (no target)
- *(no keyword)* — `jump to` the target question or section

**Targets:**

- `{question-id}` — a specific question
- `#section-name` — a whole section (resolved to its first question at build time)

For complete syntax details, see the [Import Documentation](import.md).

### The Survey Map

The survey builder includes a visual **Survey Map** diagram that shows your entire survey structure at a glance. This visualizer helps you:

- **See the flow** - Understand how questions connect
- **Identify patterns** - Spot complex branching paths
- **Catch issues** - Notice unreachable questions or logic errors
- **Share understanding** - Show stakeholders how the survey works

#### Reading the Survey Map

The Survey Map uses a git-graph style to display your survey with square connector lines:

- **Circles** represent questions (accent color for regular, primary for those with conditions)
- **Vertical lines** show the default question flow
- **Colored dashed lines** indicate conditional branches:
  - Green for "Jump to"
  - Amber for "Hide"
  - Red for "End Survey"
- **Section jumps** draw to the section header band; **question jumps** draw to the question node — so you can see at a glance whether a branch targets a whole section or a single question
- **Condition labels** appear on branch lines showing the trigger (e.g., "> 17")
- **Shaded regions** group questions together
- **Hover** over questions to see the full question text
- **Hover** over branch lines to see the full condition details

Questions are organised into their sections, making it easy to see which questions belong together and how they flow.

## Repeating Questions

Repeating questions allow users to answer the same set of questions multiple times. This is perfect for:

- Listing multiple family members
- Recording several medications
- Documenting multiple symptoms or conditions
- Collecting information about multiple items

### How It Works

Questions are organised into **sections**. Any section can be marked as repeating, allowing users to add as many instances as they need (or up to a maximum limit you set).

For example, a "Medications" section might contain:
- Medication name
- Dosage
- Frequency
- Side effects

Users can add this information once for each medication they take.

### Setting Up Repeats

#### Using the Sections page

1. Go to the **Sections** page in your survey
2. Find the section you want to make repeatable
3. Click "Set Repeat"
4. Choose:
   - **Unlimited repeats** - Users can add as many as needed
   - **Limited repeats** - Set a maximum number (e.g., "up to 5")
5. Save your changes

The group will now show a repeat badge with the count or ∞ symbol for unlimited.

#### Using Outline

Mark a collection (group) as repeating using the `REPEAT` keyword:

```markdown
# Medications
REPEAT

## Medication name
(text)

## Dosage
(text)

## Frequency
(mc_single)
- Once daily
- Twice daily
- Three times daily
- As needed
```

For a limited repeat count, use `REPEAT-5` (or any number).

### Repeats in the Survey Map

When viewing the Survey Map diagram, repeating groups are clearly marked with a repeat badge showing:
- A circular arrow icon
- The maximum repeat count (or ∞ for unlimited)

This makes it easy to see which parts of your survey can be repeated.

## Combining Branching and Repeats

The real power comes from combining these features. For example:

1. Ask if someone has children (Yes/No)
2. If Yes, show a repeating group for child details
3. Within each child's questions, use branching logic for age-specific questions

This creates sophisticated surveys that feel simple to users - they only see relevant questions and can provide as much or as little detail as needed.

## Follow-up Text Inputs

A special type of branching is the follow-up text input attached to specific options. This is perfect for "Other (please specify)" or "Yes (please explain)" scenarios.

Follow-up inputs appear immediately below the option when selected, making the connection clear to users.

### Adding Follow-ups

#### Using the Web Builder

When editing question options, you can enable a follow-up text field for any option and customize its label.

#### Using Outline

Use the `+` symbol on an indented line after an option:

```markdown
## How did you hear about us?
(mc_single)
- Search engine
- Social media
- Friend or colleague
- Advertisement
- Other
  + Please specify where
```

### Question-level Follow-ups (Dataset-backed Options)

When a dropdown's options come from an imported dataset (for example an NHS specialty list with hundreds of entries), enabling a follow-up for individual options doesn't scale. For these questions the builder offers a single question-level toggle instead: **"Offer a follow-up text box after the options"**.

When enabled:

- One optional free-text box (with a customisable label, default "Please specify") is shown below the options once the respondent has made a selection.
- It applies regardless of which option was chosen — ideal for "tell us more" or "anything not listed?" prompts.
- The per-option follow-up list is hidden in the builder while dataset options are loaded.

### Viewing Follow-up Responses

Follow-up text is stored alongside the question's answer and is reported wherever the answer is:

- **CSV export** — includes a `"{question text} (follow-up)"` column with each entry rendered as `Label: text`.
- **Dashboard insights and summary report** — chartable questions show a collapsible "follow-up responses" list under the chart, with each response labelled using its configured follow-up label.

## Best Practices

### Branching Logic

- **Keep it simple** - Too many conditions can confuse both you and your users
- **Test thoroughly** - Use the visualizer to check for logic errors
- **Provide escape routes** - Don't trap users in impossible situations
- **Consider mobile** - Complex branching should still work on small screens

### Repeating Questions

- **Set sensible limits** - Unlimited repeats are flexible but can create very long surveys
- **Group logically** - Only related questions should repeat together
- **Provide clear labels** - Users should understand what they're repeating
- **Consider data analysis** - Think about how you'll analyze multiple responses

### General Tips

- **Use the visualizer** - It's your best tool for understanding and debugging survey flow
- **Start simple** - Add branching gradually as you understand your needs
- **Test with real users** - What seems clear to you might confuse others
- **Document your logic** - Use question descriptions to explain why conditions exist

## Technical Details

For developers and technical users who need to understand the implementation, see the [Branching Logic - Technical Guide](branching-technical.md) which covers:

- Database models and relationships
- API endpoints and data structures
- Implementation details
- Testing considerations
