from pathlib import Path
import re

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
import markdown as mdlib

from checktick_app.core.models import SiteBranding


# --- Documentation views ---
# Resolve project root (repository root). In some production builds the module path
# can point into site-packages; prefer settings.BASE_DIR (project/checktick_app) and
# then step up one directory to reach the repo root containing manage.py and docs/.
def _resolve_repo_root() -> Path:
    candidates = [
        Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent))
    ]
    # Prefer the parent of BASE_DIR as the repository root (where manage.py lives)
    candidates.append(candidates[0].parent)
    # Also consider the path derived from this file (source tree execution)
    candidates.append(Path(__file__).resolve().parent.parent.parent)
    # Pick the first candidate that contains a docs directory or a manage.py file
    for c in candidates:
        if (c / "docs").is_dir() or (c / "manage.py").exists():
            return c
    # Fallback to the first candidate
    return candidates[0]


REPO_ROOT = _resolve_repo_root()
DOCS_DIR = REPO_ROOT / "docs"


def _doc_title(slug: str) -> str:
    """Convert slug to Title Case words (e.g., 'getting-started' -> 'Getting Started')."""
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-"))


# Category definitions for organizing documentation
# Each category can have an optional icon and display order
DOC_CATEGORIES = {
    "getting-started": {
        "title": "Getting Started",
        "order": 1,
        "icon": "📚",
    },
    "features": {
        "title": "Features",
        "order": 2,
        "icon": "✨",
    },
    "self-hosting": {
        "title": "Self-Hosting",
        "order": 3,
        "icon": "🖥️",
    },
    "configuration": {
        "title": "Configuration",
        "order": 4,
        "icon": "⚙️",
    },
    "security": {
        "title": "Security",
        "order": 5,
        "icon": "🔒",
    },
    "data-governance": {
        "title": "Data Governance",
        "order": 6,
        "icon": "🗂️",
    },
    "api": {
        "title": "API & Development",
        "order": 7,
        "icon": "🔧",
    },
    "testing": {
        "title": "Testing",
        "order": 8,
        "icon": "🧪",
    },
    "internationalisation": {
        "title": "Internationalisation",
        "order": 9,
        "icon": "🌍",
    },
    "accessibility-and-inclusion": {
        "title": "Accessibility and Inclusion",
        "order": 10,
        "icon": "♿",
    },
    "getting-involved": {
        "title": "Getting Involved",
        "order": 11,
        "icon": "🤝",
    },
    # DSPT (Data Security and Protection Toolkit) categories
    # These map to the 10 NHS DSPT standards
    "dspt-overview": {
        "title": "DSPT Overview",
        "order": 12,
        "icon": "📋",
    },
    "dspt-1-confidential-data": {
        "title": "1. Personal Confidential Data",
        "order": 13,
        "icon": "🔐",
    },
    "dspt-2-staff-responsibilities": {
        "title": "2. Staff Responsibilities",
        "order": 14,
        "icon": "👥",
    },
    "dspt-3-training": {
        "title": "3. Training",
        "order": 15,
        "icon": "🎓",
    },
    "dspt-4-managing-access": {
        "title": "4. Managing Data Access",
        "order": 16,
        "icon": "🔑",
    },
    "dspt-5-process-reviews": {
        "title": "5. Process Reviews",
        "order": 17,
        "icon": "📊",
    },
    "dspt-6-incidents": {
        "title": "6. Responding to Incidents",
        "order": 18,
        "icon": "🚨",
    },
    "dspt-7-continuity": {
        "title": "7. Continuity Planning",
        "order": 19,
        "icon": "🔄",
    },
    "dspt-8-unsupported-systems": {
        "title": "8. Unsupported Systems",
        "order": 20,
        "icon": "⚠️",
    },
    "dspt-9-it-protection": {
        "title": "9. IT Protection",
        "order": 21,
        "icon": "🛡️",
    },
    "dspt-10-suppliers": {
        "title": "10. Accountable Suppliers",
        "order": 22,
        "icon": "🤝",
    },
}

# Manual overrides for specific files (optional)
# If a file isn't listed here, it will be auto-discovered
# Format: "slug": {"file": "filename.md", "category": "category-key", "title": "Custom Title"}
DOC_PAGE_OVERRIDES = {
    "index": {
        "file": "README.md",
        "category": None,
        "standalone": True,
        "icon": "🏠",
        "order": 0,
        "title": "Welcome",
    },  # Landing page
    "getting-help": {
        "file": "getting-help.md",
        "category": None,
        "standalone": True,
        "icon": "💬",
        "order": 0.5,
        "title": "Getting Help",
    },  # Standalone item
    "contributing": {
        "file": REPO_ROOT / "CONTRIBUTING.md",
        "category": "getting-involved",
    },
    "themes": {
        "file": "themes.md",
        "category": "api",
    },  # Developer guide for theme implementation
    "branching-and-repeats": {
        "file": "branching-and-repeats.md",
        "category": "features",
        "title": "Branching Logic & Repeating Questions",
    },
    "branching-technical": {
        "file": "branching-technical.md",
        "category": "api",
        "title": "Branching Logic - Technical Guide",
    },
    "documentation-system": {
        "file": "documentation-system.md",
        "category": "getting-involved",
    },
    "issues-vs-discussions": {
        "file": "issues-vs-discussions.md",
        "category": "getting-involved",
    },
    # Dataset documentation organization
    "api-datasets": {
        "file": "api-datasets.md",
        "category": "api",
        "title": "Dataset API Reference",
    },
    "nhs-data-dictionary-datasets": {
        "file": "nhs-data-dictionary-datasets.md",
        "category": None,  # Accessible via URL but hidden from sidebar navigation
        "title": "NHS DD Dataset Reference",
    },
    "datasets-and-dropdowns": {
        "file": "datasets-and-dropdowns.md",
        "category": "features",
        "title": "Datasets and Dropdowns",
    },
    "datasets": {
        "file": "datasets.md",
        "category": None,  # Hidden - replaced by datasets-and-dropdowns
        "title": "Using Datasets (Legacy)",
    },
}


def _discover_doc_pages():
    """
    Auto-discover all markdown files in docs/ directory and organize by category.

    All markdown files MUST have YAML frontmatter with 'title' and 'category' fields.
    Files without frontmatter or with invalid categories will be skipped.

    Returns a dict mapping slug -> file path, and a categorized structure for navigation.
    """
    pages = {}
    categorized = {cat: [] for cat in DOC_CATEGORIES.keys()}

    # First, add manual overrides
    for slug, config in DOC_PAGE_OVERRIDES.items():
        file_path = config["file"]
        if isinstance(file_path, str):
            file_path = DOCS_DIR / file_path
        pages[slug] = file_path

        # Add to category if specified and valid
        category = config.get("category")
        if category and category in categorized:
            categorized[category].append(
                {
                    "slug": slug,
                    "title": config.get("title") or slug.replace("-", " ").title(),
                    "file": file_path,
                }
            )

    # Auto-discover markdown files in docs/
    if DOCS_DIR.exists():
        for md_file in sorted(DOCS_DIR.glob("*.md")):
            # Skip README.md as it's the index
            if md_file.name == "README.md":
                continue

            # Generate slug from filename
            slug = md_file.stem

            # Skip if already manually configured
            if slug in pages:
                continue

            # Parse frontmatter - REQUIRED for all docs
            frontmatter = _parse_frontmatter(md_file)

            # Skip files without required frontmatter
            if not frontmatter:
                continue

            # Get category from frontmatter (required)
            category = frontmatter.get("category")

            # Skip if no category specified (must be explicit, even if None)
            if "category" not in frontmatter:
                continue

            # Handle category: None (hide from menu but keep accessible via URL)
            if category == "None" or category is None:
                pages[slug] = md_file
                continue

            # Validate category exists in DOC_CATEGORIES
            if category not in categorized:
                # Invalid category - skip this file
                continue

            # Get title from frontmatter (required)
            title = frontmatter.get("title")
            if not title:
                # No title in frontmatter - skip this file
                continue

            # Get priority for sorting (default to 999 for items without priority)
            priority = frontmatter.get("priority", 999)

            pages[slug] = md_file
            categorized[category].append(
                {
                    "slug": slug,
                    "title": title,
                    "file": md_file,
                    "priority": priority,
                }
            )

    # Auto-discover translation files in docs/languages/
    # These are added to pages (accessible via URL) but NOT added to categorized (hidden from sidebar)
    # i18n.md provides links to these pages
    languages_dir = DOCS_DIR / "languages"
    if languages_dir.exists():
        for md_file in sorted(languages_dir.glob("*.md")):
            # Generate slug from filename with languages prefix
            slug = f"languages-{md_file.stem}"

            # Skip if already manually configured
            if slug in pages:
                continue

            # Make page accessible via URL but don't add to sidebar navigation
            pages[slug] = md_file

    # Auto-discover compliance documentation in docs/compliance/
    # These are DSPT evidence documents that self-hosters can also use as templates
    compliance_dir = DOCS_DIR / "compliance"
    if compliance_dir.exists():
        for md_file in sorted(compliance_dir.glob("*.md")):
            # Generate slug from filename with compliance prefix
            slug = f"compliance-{md_file.stem}"

            # Skip if already manually configured
            if slug in pages:
                continue

            # Parse frontmatter - REQUIRED for all docs
            frontmatter = _parse_frontmatter(md_file)

            # Skip files without required frontmatter
            if not frontmatter:
                continue

            # Get category from frontmatter (required)
            category = frontmatter.get("category")

            # Skip if no category specified
            if "category" not in frontmatter:
                continue

            # Handle category: None (hide from menu but keep accessible via URL)
            if category == "None" or category is None:
                pages[slug] = md_file
                continue

            # Validate category exists in DOC_CATEGORIES
            if category not in categorized:
                continue

            # Get title from frontmatter (required)
            title = frontmatter.get("title")
            if not title:
                continue

            # Get priority for sorting (default to 999 for items without priority)
            priority = frontmatter.get("priority", 999)

            pages[slug] = md_file
            categorized[category].append(
                {
                    "slug": slug,
                    "title": title,
                    "file": md_file,
                    "priority": priority,
                }
            )

    # Hide old consolidated files from sidebar (accessible via URL only)
    # These have been consolidated into comprehensive guides but remain accessible for backward compatibility
    hidden_files = [
        # Old data governance files (consolidated into data-governance.md)
        "data-governance-overview",
        "data-governance-policy",
        "data-governance-implementation",
        "data-governance-export",
        "data-governance-retention",
        "data-governance-security",
        "data-governance-special-cases",
        # Old encryption files (consolidated into encryption.md)
        "encryption-quick-reference",
        "encryption-individual-users",
        "encryption-organisation-users",
        # Old getting-started files (consolidated into getting-started.md)
        "getting-started-account-types",
        "getting-started-api",
        # Old self-hosting files (consolidated into self-hosting.md)
        "self-hosting-quickstart",
        "self-hosting-production",
        "self-hosting-database",
        "self-hosting-configuration",
        "self-hosting-scheduled-tasks",
        "self-hosting-backup",
        "self-hosting-themes",
    ]

    for hidden_slug in hidden_files:
        hidden_path = DOCS_DIR / f"{hidden_slug}.md"
        if hidden_path.exists() and hidden_slug not in pages:
            # Make accessible via URL but don't add to sidebar
            pages[hidden_slug] = hidden_path
        # Remove from all categories if it was auto-discovered
        for category_name in categorized.keys():
            categorized[category_name] = [
                p for p in categorized[category_name] if p.get("slug") != hidden_slug
            ]

    # Sort items within each category by priority (lower priority = earlier in list)
    for category_name in categorized.keys():
        categorized[category_name].sort(
            key=lambda x: (x.get("priority", 999), x.get("title", ""))
        )

    return pages, categorized


def _parse_frontmatter(file_path: Path) -> dict:
    """
    Parse YAML frontmatter from markdown file.

    Returns dict with 'title', 'category', 'priority' if found in frontmatter,
    otherwise returns empty dict.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Check if file starts with ---
        if not lines or lines[0].strip() != "---":
            return {}

        # Find closing ---
        frontmatter_lines = []
        in_frontmatter = False
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                in_frontmatter = True
                break
            frontmatter_lines.append(line)

        if not in_frontmatter:
            return {}

        # Parse simple YAML (key: value pairs)
        result = {}
        for line in frontmatter_lines:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Handle quoted values
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Convert None string to actual None
                if value == "None":
                    value = None
                # Try to convert to int for priority
                elif key == "priority":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        pass

                result[key] = value

        return result
    except Exception:
        return {}


# Build the pages dict and categorized structure
DOC_PAGES, DOC_CATEGORIES_WITH_PAGES = _discover_doc_pages()


def _nav_pages(include_dspt=False):
    """
    Return categorized navigation structure for documentation.

    Args:
        include_dspt: If True, include DSPT categories. If False, exclude them.
                      Default False to keep main docs clean.

    Returns a list of categories and standalone items with their pages.
    """
    nav = []

    # Add standalone items from DOC_PAGE_OVERRIDES
    standalone_items = []
    for slug, config in DOC_PAGE_OVERRIDES.items():
        if config.get("standalone"):
            file_path = config["file"]
            if isinstance(file_path, str):
                file_path = DOCS_DIR / file_path
            standalone_items.append(
                {
                    "slug": slug,
                    "title": config.get("title") or _doc_title(slug),
                    "icon": config.get("icon", ""),
                    "order": config.get("order", 99),
                    "standalone": True,
                }
            )

    # Add categories with pages
    for cat_key, pages_list in DOC_CATEGORIES_WITH_PAGES.items():
        if not pages_list:  # Skip empty categories
            continue

        # Filter based on include_dspt flag
        is_dspt = cat_key.startswith("dspt-")
        if is_dspt and not include_dspt:
            continue
        if not is_dspt and include_dspt:
            continue

        cat_info = DOC_CATEGORIES.get(cat_key, {"title": cat_key.title(), "order": 99})

        nav.append(
            {
                "key": cat_key,
                "title": cat_info.get("title", cat_key.title()),
                "icon": cat_info.get("icon", ""),
                "order": cat_info.get("order", 99),
                "pages": pages_list,  # Already sorted by priority in _discover_doc_pages()
                "standalone": False,
            }
        )

    # Add standalone items to nav (only for main docs, not DSPT)
    if not include_dspt:
        nav.extend(standalone_items)

    # Sort all items by order
    nav.sort(key=lambda c: c["order"])

    return nav


def docs_index(request):
    """Render docs index from docs/README.md with a simple TOC."""
    index_file = DOCS_DIR / DOC_PAGES["index"]
    if not index_file.exists():
        raise Http404("Documentation not found")
    html = mdlib.markdown(
        index_file.read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables", "toc"],
    )
    return render(
        request,
        "core/docs.html",
        {"html": html, "active_slug": "index", "pages": _nav_pages()},
    )


def docs_page(request, slug: str):
    """Render a specific documentation page by slug."""
    if slug not in DOC_PAGES:
        raise Http404("Page not found")

    # DOC_PAGES values are already Path objects from _discover_doc_pages
    file_path = DOC_PAGES[slug]

    if not file_path.exists():
        raise Http404("Page not found")

    # Read file and strip YAML frontmatter before rendering
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Check if file starts with YAML frontmatter
    if lines and lines[0].strip() == "---":
        # Find closing --- and skip frontmatter
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # Skip frontmatter and join remaining content
                content = "\n".join(lines[i + 1 :])
                break

    # Interpolate platform variables for compliance docs and templates
    # This allows self-hosters to see their own platform name in policy documents
    platform_name = settings.BRAND_TITLE or "CheckTick"
    if SiteBranding is not None:
        try:
            sb = SiteBranding.objects.first()
            if sb and sb.title:
                platform_name = sb.title
        except Exception:
            pass
    content = content.replace("{{ platform_name }}", platform_name)

    html = mdlib.markdown(
        content,
        extensions=["fenced_code", "tables", "toc"],
    )

    # Rewrite internal .md links to proper /docs/slug/ URLs
    # Convert patterns like href="filename.md" or href="path/filename.md" to href="/docs/filename/"
    import re

    html = re.sub(
        r'href="([^"]*?)\.md(#[^"]*)?(")',
        lambda m: f'href="/docs/{m.group(1).split("/")[-1]}/{m.group(2) or ""}{m.group(3)}',
        html,
    )

    return render(
        request,
        "core/docs.html",
        {"html": html, "active_slug": slug, "pages": _nav_pages()},
    )


def compliance_index(request):
    """Render compliance index showing the DSPT master document."""
    # Look for the master/index compliance doc
    master_slug = "compliance-master"
    if master_slug not in DOC_PAGES:
        raise Http404("Compliance documentation not found")

    file_path = DOC_PAGES[master_slug]
    if not file_path.exists():
        raise Http404("Compliance documentation not found")

    # Read and process the file
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Strip YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                content = "\n".join(lines[i + 1 :])
                break

    # Interpolate platform name
    platform_name = settings.BRAND_TITLE or "CheckTick"
    if SiteBranding is not None:
        try:
            sb = SiteBranding.objects.first()
            if sb and sb.title:
                platform_name = sb.title
        except Exception:
            pass
    content = content.replace("{{ platform_name }}", platform_name)

    html = mdlib.markdown(
        content,
        extensions=["fenced_code", "tables", "toc"],
    )

    # Rewrite internal links for compliance pages
    import re

    html = re.sub(
        r'href="/docs/compliance-([^"]+)/"',
        r'href="/compliance/\1/"',
        html,
    )

    return render(
        request,
        "core/compliance.html",
        {
            "html": html,
            "active_slug": "master",
            "pages": _nav_pages(include_dspt=True),
        },
    )


def compliance_page(request, slug: str):
    """Render a specific DSPT compliance page by slug."""
    # Compliance pages are stored with 'compliance-' prefix
    full_slug = f"compliance-{slug}"
    if full_slug not in DOC_PAGES:
        raise Http404("Page not found")

    file_path = DOC_PAGES[full_slug]
    if not file_path.exists():
        raise Http404("Page not found")

    # Read and process the file
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extract title from YAML frontmatter and strip it
    doc_title = slug.replace("-", " ").title()  # fallback
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # Parse frontmatter for title
                frontmatter = "\n".join(lines[1:i])
                for fm_line in frontmatter.split("\n"):
                    if fm_line.startswith("title:"):
                        doc_title = (
                            fm_line.split(":", 1)[1].strip().strip('"').strip("'")
                        )
                        break
                content = "\n".join(lines[i + 1 :])
                break

    # Interpolate platform name
    platform_name = settings.BRAND_TITLE or "CheckTick"
    if SiteBranding is not None:
        try:
            sb = SiteBranding.objects.first()
            if sb and sb.title:
                platform_name = sb.title
        except Exception:
            pass
    content = content.replace("{{ platform_name }}", platform_name)

    # Interpolate governance roles from settings
    content = content.replace(
        "{{ dpo_name }}", getattr(settings, "DPO_NAME", "[DPO Name]")
    )
    content = content.replace(
        "{{ dpo_email }}", getattr(settings, "DPO_EMAIL", "dpo@example.com")
    )
    content = content.replace(
        "{{ siro_name }}", getattr(settings, "SIRO_NAME", "[SIRO Name]")
    )
    content = content.replace(
        "{{ siro_email }}", getattr(settings, "SIRO_EMAIL", "siro@example.com")
    )
    content = content.replace(
        "{{ caldicott_name }}",
        getattr(settings, "CALDICOTT_NAME", "[Caldicott Guardian]"),
    )
    content = content.replace(
        "{{ caldicott_email }}",
        getattr(settings, "CALDICOTT_EMAIL", "caldicott@example.com"),
    )
    content = content.replace(
        "{{ ig_lead_name }}", getattr(settings, "IG_LEAD_NAME", "[IG Lead]")
    )
    content = content.replace(
        "{{ ig_lead_email }}", getattr(settings, "IG_LEAD_EMAIL", "ig@example.com")
    )
    content = content.replace(
        "{{ cto_name }}", getattr(settings, "CTO_NAME", "[CTO Name]")
    )
    content = content.replace(
        "{{ cto_email }}", getattr(settings, "CTO_EMAIL", "cto@example.com")
    )

    html = mdlib.markdown(
        content,
        extensions=["fenced_code", "tables", "toc"],
    )

    # Rewrite internal links for compliance pages
    import re

    html = re.sub(
        r'href="/docs/compliance-([^"]+)/"',
        r'href="/compliance/\1/"',
        html,
    )

    return render(
        request,
        "core/compliance.html",
        {
            "html": html,
            "active_slug": slug,
            "doc_title": doc_title,
            "pages": _nav_pages(include_dspt=True),
        },
    )


@require_GET
def doc_search_index(request):
    """
    Generate a searchable index of all documentation pages.
    Returns JSON with title, slug, category, content, and headings.
    """
    # _discover_doc_pages returns (pages, categorized) tuple
    pages_dict, categorized = _discover_doc_pages()
    search_index = []

    # Iterate through the pages dictionary
    for slug, file_path in pages_dict.items():
        try:
            # file_path is already a Path object
            if not file_path.exists():
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract frontmatter and content
            frontmatter = _parse_frontmatter(file_path)

            # Read markdown content (skip frontmatter)
            lines = content.split("\n")
            if lines[0].strip() == "---":
                # Find end of frontmatter
                end_idx = 1
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        end_idx = i + 1
                        break
                markdown_content = "\n".join(lines[end_idx:])
            else:
                markdown_content = content

            # Skip hidden pages (category: None)
            category = frontmatter.get("category")
            if category == "None" or category is None:
                continue

            # Get title from frontmatter or slug
            title = frontmatter.get("title", slug.replace("-", " ").title())

            # Determine URL based on slug prefix
            if slug.startswith("compliance-"):
                # Compliance docs use /compliance/ URL
                clean_slug = slug.replace("compliance-", "")
                url = f"/compliance/{clean_slug}/"
            elif slug.startswith("languages-"):
                # Language docs use /docs/languages-* URL
                url = f"/docs/{slug}/"
            else:
                # Regular docs use /docs/ URL
                url = f"/docs/{slug}/"

            # Extract headings for better search relevance
            headings = re.findall(r"^#{1,6}\s+(.+)$", markdown_content, re.MULTILINE)

            # Clean markdown for search (remove code blocks, links, etc.)
            clean_content = _clean_markdown_for_search(markdown_content)

            search_index.append(
                {
                    "slug": slug,
                    "title": title,
                    "category": category or "other",
                    "url": url,
                    "content": clean_content[:5000],  # Limit content size
                    "headings": headings[:20],  # Limit headings
                }
            )

        except Exception as e:
            # Skip problematic files
            print(f"Error indexing {slug}: {e}")
            continue

    return JsonResponse({"index": search_index})


def _discover_compliance_docs():
    """
    Compliance docs are already discovered by _discover_doc_pages()
    with the "compliance-" prefix, so this function is not needed.
    """
    return {}


def _clean_markdown_for_search(markdown_content):
    """
    Clean markdown content to make it more searchable.
    Removes code blocks, images, links but keeps the text.
    """
    # Remove code blocks
    content = re.sub(r"```[\s\S]*?```", "", markdown_content)
    content = re.sub(r"`[^`]+`", "", content)

    # Remove images but keep alt text
    content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", content)

    # Remove links but keep text
    content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)

    # Remove HTML tags
    content = re.sub(r"<[^>]+>", "", content)

    # Remove markdown formatting
    content = re.sub(r"[*_~]", "", content)

    # Remove extra whitespace
    content = re.sub(r"\s+", " ", content)

    return content.strip()
