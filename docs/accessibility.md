---
title: Accessibility
category: internationalization
priority: 2
---

# Accessibility

CheckTick is designed with accessibility in mind, following **WCAG 2.1 AA** guidelines to ensure surveys are usable by people with disabilities, including those using screen readers, keyboard navigation, and other assistive technologies.

## Target Audience

Our accessibility focus prioritises **survey respondents** - the patients, professionals, and public who complete surveys. Survey designers also benefit from accessible interfaces, but the primary goal is ensuring everyone can participate in data collection.

## Compliance Summary

| WCAG Criterion | Status | Implementation |
|----------------|--------|----------------|
| 1.3.1 Info & Relationships | ✅ | Semantic HTML, fieldset/legend grouping, ARIA roles |
| 1.3.5 Identify Input Purpose | ✅ | aria-label on all form inputs |
| 2.1.1 Keyboard Accessible | ✅ | All controls keyboard operable, orderable questions have keyboard alternative |
| 2.4.1 Bypass Blocks | ✅ | Skip-to-content link for survey forms |
| 2.4.6 Headings & Labels | ✅ | Proper label associations, descriptive headings |
| 3.3.1 Error Identification | ✅ | Validation errors announced to screen readers |
| 3.3.2 Labels or Instructions | ✅ | All form controls have accessible names |
| 4.1.2 Name, Role, Value | ✅ | ARIA attributes for custom widgets |
| 4.1.3 Status Messages | ✅ | aria-live regions for dynamic content |

## Survey Form Accessibility Features

### Semantic Structure

- **Fieldsets and Legends**: Question groups use `<fieldset>` and `<legend>` elements, allowing screen readers to announce the group context
- **Form Labelling**: The entire survey form is associated with the survey title via `aria-labelledby`
- **Skip Link**: A "Skip to survey questions" link appears on focus, allowing keyboard users to bypass navigation

### Question Types

#### Text Input
- `aria-labelledby` connects input to question text
- `aria-required="true"` and `required` attribute for mandatory fields
- Screen-reader-only "(required)" text alongside visual asterisks

#### Single Choice (Radio Buttons)
- Wrapped in `role="radiogroup"` with `aria-labelledby`
- Each option properly labelled
- Required attribute for mandatory questions

#### Multiple Choice (Checkboxes)
- Wrapped in `role="group"` with `aria-labelledby`
- Each checkbox has associated label

#### Dropdown/Select
- `aria-labelledby` connects to question text
- `aria-required` for mandatory fields

#### Yes/No Questions
- Same accessibility as dropdowns
- Clear labelling of options

#### Likert Scales
- **Range Slider**: `aria-valuemin`, `aria-valuemax`, `aria-valuenow` attributes
- **Radio Options**: `role="radiogroup"` with label references
- Left/right anchor labels included in `aria-labelledby`

#### Orderable (Ranking) Questions
- `role="listbox"` on container
- `role="option"` on each item
- Screen-reader instructions: "Use arrow keys or drag to reorder items"
- **Keyboard alternative**: Arrow keys for reordering (no mouse required)

#### Image Choice Questions
- `role="radiogroup"` on image grid
- Each image has `alt` text from label or default
- `focus-within` ring for keyboard navigation visibility

### Patient Demographics & Professional Details
- Wrapped in `<fieldset>` with `<legend>`
- `aria-label` on all inputs (especially those using placeholder-only design)
- Validation errors announced via aria-live

### Progress & Status
- Progress bar has `aria-label`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`
- Save status uses `aria-live="polite"` to announce changes

### Decorative Elements
- SVG icons use `aria-hidden="true"` to prevent screen reader clutter

## Colour Contrast

CheckTick uses [DaisyUI](https://daisyui.com/) themes which are designed to meet WCAG AA contrast requirements. The default themes (`checktick-light` and `checktick-dark`) provide:

- Minimum 4.5:1 contrast ratio for normal text
- Minimum 3:1 contrast ratio for large text and UI components

### Custom Themes

Organisations can create custom themes. When doing so, verify contrast using:
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- Browser developer tools accessibility audits
- [axe DevTools](https://www.deque.com/axe/devtools/)

## Keyboard Navigation

All survey functionality is available via keyboard:

| Action | Key |
|--------|-----|
| Move between questions | Tab / Shift+Tab |
| Select radio option | Arrow keys |
| Toggle checkbox | Space |
| Open dropdown | Enter / Space |
| Select dropdown option | Arrow keys, Enter |
| Reorder items | Arrow Up/Down (in orderable questions) |
| Submit survey | Enter (on submit button) |

## Screen Reader Support

Tested with:
- VoiceOver (macOS/iOS)
- NVDA (Windows)

Screen readers will announce:
- Question text and type
- Required status
- Group context (when in a question group)
- Validation errors
- Save status changes
- Progress percentage

## Testing Accessibility

### Automated Testing

Run accessibility audits using:

```bash
# Install axe-core CLI
npm install -g @axe-core/cli

# Run against local development server
axe http://localhost:8000/surveys/your-survey-slug/
```

### Manual Testing Checklist

- [ ] Complete entire survey using only keyboard
- [ ] Navigate survey with screen reader enabled
- [ ] Test at 200% and 400% zoom levels
- [ ] Verify focus indicators are visible
- [ ] Check colour contrast with browser tools
- [ ] Test with reduced motion preference enabled

## Known Limitations

1. **Drag-and-drop orderable questions**: While keyboard alternatives exist, the drag-and-drop animation may not be accessible to all users. Keyboard reordering provides equivalent functionality.

2. **CAPTCHA**: hCaptcha is used for spam prevention. While hCaptcha offers accessibility modes, CAPTCHA inherently presents challenges for some users.

3. **Rich text in questions**: Survey creators can add HTML content to questions. We recommend using semantic HTML and avoiding images without alt text.

## Reporting Issues

If you encounter accessibility barriers, please:

1. Open an issue on [GitHub](https://github.com/eatyourpeas/checktick/issues)
2. Use the label `accessibility`
3. Include your assistive technology and browser version

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [DaisyUI Accessibility](https://daisyui.com/docs/accessibility/)
- [NHS Digital Accessibility Guidelines](https://service-manual.nhs.uk/accessibility)
- [WebAIM](https://webaim.org/)
