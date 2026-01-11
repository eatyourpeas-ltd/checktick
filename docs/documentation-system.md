---
title: Documentation System
category: getting-involved
priority: 3
---

The CheckTick documentation system automatically discovers and organizes all markdown files in the `docs/` folder.

## How It Works

### YAML Frontmatter (Required)

**All documentation files MUST include YAML frontmatter** at the top with `title` and `category` fields. Files without proper frontmatter will not appear in the documentation.

```markdown
---
title: My Feature Guide
category: features
priority: 5
---

Your documentation content starts here...
```

**Required Fields:**

- `title` (required): The display title in navigation and page header
- `category` (required): Which section to display in
  - Must match one of the valid categories listed below
  - Set to `None` to hide from sidebar while keeping the page accessible via URL

**Optional Fields:**

- `priority` (optional): Sort order within category (lower numbers appear first)
  - Default: 999 (appears at end)
  - Example: priority 1 appears before priority 5

**Valid Categories:**

- `getting-started` - Getting Started guides
- `features` - Feature documentation
- `self-hosting` - Self-hosting guides
- `configuration` - Configuration guides
- `security` - Security documentation
- `data-governance` - Data governance guides
- `api` - API & development docs
- `testing` - Testing guides
- `internationalisation` - i18n documentation
- `accessibility-and-inclusion` - Accessibility and inclusion documentation
- `getting-involved` - Contributing guides
- `None` - Hide from menu (accessible via URL only)

**DSPT Compliance Documentation:**

DSPT (NHS Data Security and Protection Toolkit) documentation is served from a separate `/compliance/` section, keeping the main docs focused on user and developer documentation.

The DSPT categories map to the 10 NHS standards:

- `dspt-overview` - DSPT overview and master index
- `dspt-1-confidential-data` - Personal confidential data policies
- `dspt-2-staff-responsibilities` - Staff responsibilities and agreements
- `dspt-3-training` - Training records and analysis
- `dspt-4-managing-access` - Managing data access and asset registers
- `dspt-5-process-reviews` - Process reviews and audits
- `dspt-6-incidents` - Responding to incidents
- `dspt-7-continuity` - Continuity planning and disaster recovery
- `dspt-8-unsupported-systems` - Unsupported systems and patching
- `dspt-9-it-protection` - IT protection and security controls
- `dspt-10-suppliers` - Accountable suppliers

DSPT docs are stored in `docs/compliance/` and accessed via `/compliance/<slug>/`.

### Template Variables

Documentation files support template variable interpolation for platform-specific content. This allows self-hosters to see their own platform name in policy documents.

**Supported Variables:**

- `{{ platform_name }}` - Replaced with the platform name from SiteBranding or settings

**Example:**

```markdown
---
title: Getting Started
category: getting-started
priority: 1
---

Welcome to CheckTick! This guide will help you get started...
```

### Auto-Discovery

Simply add a new `.md` file to the `docs/` folder with proper YAML frontmatter and it will automatically appear in the documentation navigation. No code changes needed!

**Example:**
```bash
# Add a new guide
touch docs/my-new-feature.md

# Edit the file with YAML frontmatter and content
cat > docs/my-new-feature.md << 'EOF'
---
title: My New Feature
category: features
priority: 10
---

This is a guide to using my new feature...
EOF

# Restart the web container
docker compose restart web

# The page will now appear in the docs!
```

**Important:** Files without proper YAML frontmatter will be ignored and will not appear in the documentation.

## Manual Overrides

If you need more control over specific pages (e.g., including files from outside the `docs/` folder), you can override settings in `checktick_app/core/views.py`:

### Custom Page Configuration

Edit the `DOC_PAGE_OVERRIDES` dictionary:

```python
DOC_PAGE_OVERRIDES = {
    "my-special-doc": {
        "file": "my-special-doc.md",
        "category": "api",
        "title": "Custom Display Title",
    },
}
```

### External Files

You can include files from outside the `docs/` folder:

```python
DOC_PAGE_OVERRIDES = {
    "changelog": {
        "file": REPO_ROOT / "CHANGELOG.md",
        "category": "features",
        "title": "Changelog",
    },
}
```

### New Categories

Add new categories in the `DOC_CATEGORIES` dictionary:

```python
DOC_CATEGORIES = {
    "my-category": {
        "title": "My Custom Category",
        "order": 10,  # Controls display order
        "icon": "🎯",  # Optional emoji icon
    },
}
```

## Best Practices

### 1. Always Use YAML Frontmatter

Start every documentation file with YAML frontmatter:

```markdown
---
title: Clear Descriptive Title
category: features
priority: 5
---

Your content here...
```

This ensures consistent display and proper organization.

### 2. Hide Supporting Documentation

Use `category: None` for detailed reference pages that should be accessible but not clutter the main menu:

```markdown
---
title: Advanced Technical Details
category: None
---

This page is accessible via direct link but won't appear in sidebar.
```

Link to these pages from main documentation pages.

### 3. Use Priority for Logical Ordering

Within each category, use `priority` to control the order:

```markdown
# In getting-started.md
---
title: Getting Started
category: getting-started
priority: 1
---

# In getting-started-api.md
---
title: Getting Started with API
category: getting-started
priority: 2
---
```

Lower priority values appear first in the menu.

### 4. Descriptive Filenames

Use descriptive, kebab-case filenames:
- ✅ `datasets-and-dropdowns.md`
- ✅ `authentication-and-permissions.md`
- ❌ `doc1.md`
- ❌ `README.md` (reserved for index)

### 5. Clear Titles

Use clear, concise titles in frontmatter:
- ✅ `title: Getting Started`
- ✅ `title: API Reference`
- ❌ `title: Docs`
- ❌ `title: Untitled Document`

### 6. Consistent Naming Patterns

Use consistent prefixes for related docs:
- `self-hosting.md` (priority: 1)
- `self-hosting-quickstart.md` (priority: 2)
- `self-hosting-configuration.md` (priority: 3)

This helps organize related documentation together in the same category.

## Linking Between Documentation Pages

When linking from one documentation page to another, **always use the `/docs/slug/` URL format**, not the `.md` file extension.

### ✅ Correct Link Format

```markdown
See the [Bulk Survey Import](/docs/import/) for details.
Check [Authentication & Permissions](/docs/authentication-and-permissions/) guide.
Read about [Collections](/docs/collections/) for repeatable questions.
```

### ❌ Incorrect Link Format

```markdown
See the [Bulk Survey Import](import.md) for details.  <!-- Will 404 -->
Check [Authentication](../authentication-and-permissions.md) guide.  <!-- Won't work -->
```

### How It Works

- The slug is the filename without the `.md` extension
- URLs follow the pattern: `/docs/<slug>/`
- Django handles the routing and markdown rendering
- Links work correctly in both development and production

### Examples

| Markdown File | Slug | URL |
|--------------|------|-----|
| `import.md` | `import` | `/docs/import/` |
| `authentication-and-permissions.md` | `authentication-and-permissions` | `/docs/authentication-and-permissions/` |
| `api-datasets.md` | `api-datasets` | `/docs/api-datasets/` |
| `self-hosting-quickstart.md` | `self-hosting-quickstart` | `/docs/self-hosting-quickstart/` |

### Finding the Correct Slug

1. Look at the filename in `docs/` folder
2. Remove the `.md` extension
3. Use the result as the slug in `/docs/slug/`

## Navigation Structure

The documentation sidebar is organized hierarchically:

```
Documentation
├── 📚 Getting Started
│   ├── Getting Started
│   └── Getting Started Api
├── ✨ Features
│   ├── Collections
│   ├── Groups View
│   └── Surveys
├── ⚙️ Configuration
│   ├── Branding And Theme Settings
│   └── User Management
├── 🔒 Security
│   ├── Authentication And Permissions
│   └── Patient Data Encryption
├── 🔧 API & Development
│   ├── Adding External Datasets
│   └── Api
├── 🧪 Testing
│   ├── Testing Api
│   └── Testing Webapp
├── 🌍 Internationalisation
│   ├── I18n
│   └── I18n Progress
├── ♿ Accessibility and Inclusion
│   ├── Accessibility
│   └── Survey Translation
└── 📄 Other
    └── Releases
```

Categories are sorted by their `order` value (lower numbers appear first).

## Troubleshooting

### Page Not Appearing

1. **Check the filename**: Must be `.md` extension
2. **Restart the container**: `docker compose restart web`
3. **Check for errors**: `docker compose logs web | grep -i error`

### Wrong Category

1. Check filename patterns in `_infer_category()` function
2. Add manual override in `DOC_PAGE_OVERRIDES`
3. Update filename to include category keywords

### Custom Title Not Showing

1. Check the first line starts with `# ` (must have space after #)
2. Verify markdown syntax is correct
3. Add manual title override in `DOC_PAGE_OVERRIDES`

## Implementation Details

The system consists of three main components:

1. **`_discover_doc_pages()`**: Scans `docs/` folder and builds page registry
2. **`_infer_category()`**: Categorizes pages based on filename patterns
3. **`_nav_pages()`**: Builds categorized navigation structure for templates

This runs once at Django startup, so changes require a container restart.

## Migration from Old System

The old system required manually updating the `DOC_PAGES` dictionary. The new system is backward compatible:

- Old manual entries moved to `DOC_PAGE_OVERRIDES`
- All existing docs auto-discovered
- No changes needed to existing markdown files

## Future Enhancements

Potential improvements:

- **Frontmatter support**: Add YAML metadata to markdown files for explicit categorization
- **Hot reload**: Auto-discover without container restart (development mode)
- **Search**: Full-text search across all documentation
- **Related pages**: Suggest related documentation based on content
- **Breadcrumbs**: Show navigation path for nested topics

## Related Files

- `checktick_app/core/views.py` - Documentation discovery logic
- `checktick_app/core/templates/core/docs.html` - Navigation template
- `checktick_app/core/urls.py` - URL routing for docs
- `docs/README.md` - Documentation index page
