---
title: Branching Logic & Repeating Questions
category: features
priority: 5
---

Guide to creating intelligent surveys with conditional logic and repeating question groups.

## Overview

CheckTick allows you to create dynamic surveys that adapt based on user responses through two powerful features:

1. **Branching Logic** - Show, skip, or jump to questions based on previous answers
2. **Repeating Questions** - Allow users to answer the same group of questions multiple times

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

- **Show Question** - Display the next question in the sequence
- **Jump to Question** - Skip ahead to a specific question
- **Skip Question** - Hide the next question and continue
- **End Survey** - Complete the survey immediately

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

#### Using Text Entry (Bulk Import)

You can also define branching logic using markdown syntax. Add conditions using the `->` arrow notation:

```markdown
## Would you like to provide feedback?
(yesno)
-> Yes : {Feedback details}

## Feedback details
(text_long)
What would you like to tell us?
```

In this example, the "Feedback details" question only appears if the user answers "Yes" to the first question.

For complete syntax details, see the [Import Documentation](import.md).

### The Branching Visualizer

The survey builder includes a visual **Branching Flow** diagram that shows your entire survey structure at a glance. This visualizer helps you:

- **See the flow** - Understand how questions connect
- **Identify patterns** - Spot complex branching paths
- **Catch issues** - Notice unreachable questions or logic errors
- **Share understanding** - Show stakeholders how the survey works

#### Reading the Visualizer

The branching visualizer uses a git-graph style to display your survey:

- **Circles** represent questions
- **Lines** show the default question flow
- **Colored arrows** indicate conditional branches:
  - ▶ Show Question
  - Fast-forward icon for Jump to Question
  - ✕ Skip Question
  - ■ End Survey
- **Shaded regions** group questions together
- **Badges** show condition counts and repeat settings

Questions are organized into their groups, making it easy to see which questions belong together and how they flow.

## Repeating Questions

Repeating questions allow users to answer the same set of questions multiple times. This is perfect for:

- Listing multiple family members
- Recording several medications
- Documenting multiple symptoms or conditions
- Collecting information about multiple items

### How It Works

Questions are organized into **groups**. Any group can be marked as repeating, allowing users to add as many instances as they need (or up to a maximum limit you set).

For example, a "Medications" group might contain:
- Medication name
- Dosage
- Frequency
- Side effects

Users can add this information once for each medication they take.

### Setting Up Repeats

#### Using the Groups View

1. Go to the **Groups** view in your survey
2. Find the group you want to make repeatable
3. Click "Set Repeat"
4. Choose:
   - **Unlimited repeats** - Users can add as many as needed
   - **Limited repeats** - Set a maximum number (e.g., "up to 5")
5. Save your changes

The group will now show a repeat badge with the count or ∞ symbol for unlimited.

#### Using Text Entry (Bulk Import)

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

### Repeats in the Visualizer

When viewing the branching flow diagram, repeating groups are clearly marked with a repeat badge showing:
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

#### Using Text Entry

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
