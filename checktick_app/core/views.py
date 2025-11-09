import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
import markdown as mdlib

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    QuestionGroup,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyResponse,
)

from .forms import SignupForm, UserEmailPreferencesForm, UserLanguagePreferenceForm
from .models import UserLanguagePreference

logger = logging.getLogger(__name__)

try:
    from .models import SiteBranding, UserEmailPreferences
except ImportError:
    SiteBranding = None
    UserEmailPreferences = None

try:
    from .theme_utils import normalize_daisyui_builder_css
except ImportError:

    def normalize_daisyui_builder_css(s: str) -> str:
        """No-op fallback if theme utils or migrations are unavailable."""
        return s


try:
    from .themes import DARK_THEMES, LIGHT_THEMES, generate_theme_css_for_brand
except ImportError:
    LIGHT_THEMES = []
    DARK_THEMES = []
    generate_theme_css_for_brand = None


# Django's session key for storing language preference
LANGUAGE_SESSION_KEY = "_language"


def home(request):
    return render(request, "core/home.html")


def hosting(request):
    return render(request, "core/hosting.html")


def healthz(request):
    """Lightweight health endpoint for load balancers and readiness probes.
    Returns 200 OK without auth or redirects.
    """
    return HttpResponse("ok", content_type="text/plain")


@login_required
def profile(request):
    sb = None
    # Handle language preference form submission
    if request.method == "POST" and request.POST.get("action") == "update_language":
        lang_pref, created = UserLanguagePreference.objects.get_or_create(
            user=request.user
        )
        form = UserLanguagePreferenceForm(request.POST, instance=lang_pref)
        if form.is_valid():
            saved_pref = form.save()
            # Immediately activate the new language and store in session
            translation.activate(saved_pref.language)
            request.LANGUAGE_CODE = saved_pref.language
            request.session[LANGUAGE_SESSION_KEY] = saved_pref.language
            request.session.modified = True
            print(f"DEBUG: Saved language: {saved_pref.language}")
            print(
                f"DEBUG: Session key set to: {request.session.get(LANGUAGE_SESSION_KEY)}"
            )
            print(f"DEBUG: request.LANGUAGE_CODE: {request.LANGUAGE_CODE}")
            messages.success(request, _("Language preference updated successfully."))
        else:
            print(f"DEBUG: Form errors: {form.errors}")
            messages.error(
                request, _("There was an error updating your language preference.")
            )
        return redirect("core:profile")
    # Handle email preferences form submission
    if request.method == "POST" and request.POST.get("action") == "update_email_prefs":
        if UserEmailPreferences is not None:
            prefs = UserEmailPreferences.get_or_create_for_user(request.user)
            form = UserEmailPreferencesForm(request.POST, instance=prefs)
            if form.is_valid():
                form.save()
                messages.success(request, _("Email preferences updated successfully."))
            else:
                messages.error(
                    request, _("There was an error updating your email preferences.")
                )
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "upgrade_to_org":
        # Create a new organisation owned by this user, and make them ADMIN
        with transaction.atomic():
            org_name = (
                request.POST.get("org_name")
                or f"{request.user.username}'s Organisation"
            )
            org = Organization.objects.create(name=org_name, owner=request.user)
            OrganizationMembership.objects.get_or_create(
                organization=org,
                user=request.user,
                defaults={"role": OrganizationMembership.Role.ADMIN},
            )
        messages.success(
            request,
            _(
                "Organisation created. You are now an organisation admin and can host surveys and build a team."
            ),
        )
        return redirect("surveys:org_users", org_id=org.id)
    if request.method == "POST" and request.POST.get("action") == "reset_org_theme":
        # Handle organization theme reset (org owners only)
        primary_owned_org = Organization.objects.filter(owner=request.user).first()
        if primary_owned_org:
            org = primary_owned_org
            org.default_theme = ""
            org.theme_preset_light = ""
            org.theme_preset_dark = ""
            org.theme_light_css = ""
            org.theme_dark_css = ""
            org.save()
            logger.info(
                f"Organization theme reset to defaults by {request.user.username} (org_id={org.id})"
            )
            messages.success(
                request, _("Organization theme reset to platform defaults.")
            )
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "update_org_theme":
        # Handle organization theme update (org owners only)
        primary_owned_org = Organization.objects.filter(owner=request.user).first()
        if primary_owned_org:
            org = primary_owned_org
            org.theme_preset_light = (
                request.POST.get("org_theme_preset_light") or ""
            ).strip()
            org.theme_preset_dark = (
                request.POST.get("org_theme_preset_dark") or ""
            ).strip()

            # Get custom CSS (optional - overrides preset if provided)
            raw_light = request.POST.get("org_theme_light_css") or ""
            raw_dark = request.POST.get("org_theme_dark_css") or ""

            # Generate theme CSS from presets and custom overrides
            if generate_theme_css_for_brand:
                try:
                    generated_light, generated_dark = generate_theme_css_for_brand(
                        org.theme_preset_light or settings.BRAND_THEME_PRESET_LIGHT,
                        org.theme_preset_dark or settings.BRAND_THEME_PRESET_DARK,
                        raw_light,
                        raw_dark,
                    )
                    org.theme_light_css = generated_light
                    org.theme_dark_css = generated_dark
                except Exception as e:
                    logger.error(f"Failed to generate org theme CSS: {e}")
                    # Fall back to normalizing raw CSS
                    org.theme_light_css = normalize_daisyui_builder_css(raw_light)
                    org.theme_dark_css = normalize_daisyui_builder_css(raw_dark)
            else:
                # Fallback if theme generation not available
                org.theme_light_css = normalize_daisyui_builder_css(raw_light)
                org.theme_dark_css = normalize_daisyui_builder_css(raw_dark)

            org.save()
            logger.info(
                f"Organization theme updated by {request.user.username} (org_id={org.id}, "
                f"light={org.theme_preset_light}, dark={org.theme_preset_dark})"
            )
            messages.success(request, _("Organization theme saved."))
        return redirect("core:profile")
    if request.method == "POST" and request.POST.get("action") == "update_branding":
        if not request.user.is_superuser:
            return redirect("core:profile")
        if SiteBranding is not None:
            sb, created = SiteBranding.objects.get_or_create(pk=1)
            sb.default_theme = request.POST.get("default_theme") or sb.default_theme
            sb.icon_url = (request.POST.get("icon_url") or "").strip()
            if request.FILES.get("icon_file"):
                sb.icon_file = request.FILES["icon_file"]
            # Dark icon fields
            sb.icon_url_dark = (request.POST.get("icon_url_dark") or "").strip()
            if request.FILES.get("icon_file_dark"):
                sb.icon_file_dark = request.FILES["icon_file_dark"]
            sb.font_heading = (request.POST.get("font_heading") or "").strip()
            sb.font_body = (request.POST.get("font_body") or "").strip()
            sb.font_css_url = (request.POST.get("font_css_url") or "").strip()

            # Save theme presets
            sb.theme_preset_light = (
                request.POST.get("theme_preset_light") or settings.BRAND_THEME_PRESET_LIGHT
            ).strip()
            sb.theme_preset_dark = (
                request.POST.get("theme_preset_dark") or settings.BRAND_THEME_PRESET_DARK
            ).strip()

            # Get custom CSS (optional - overrides preset if provided)
            raw_light = request.POST.get("theme_light_css") or ""
            raw_dark = request.POST.get("theme_dark_css") or ""

            # Generate theme CSS from presets and custom overrides
            if generate_theme_css_for_brand:
                try:
                    generated_light, generated_dark = generate_theme_css_for_brand(
                        sb.theme_preset_light, sb.theme_preset_dark, raw_light, raw_dark
                    )
                    sb.theme_light_css = generated_light
                    sb.theme_dark_css = generated_dark
                except Exception as e:
                    logger.error(f"Failed to generate theme CSS: {e}")
                    # Fall back to normalizing raw CSS
                    sb.theme_light_css = normalize_daisyui_builder_css(raw_light)
                    sb.theme_dark_css = normalize_daisyui_builder_css(raw_dark)
            else:
                # Fallback if theme generation not available
                sb.theme_light_css = normalize_daisyui_builder_css(raw_light)
                sb.theme_dark_css = normalize_daisyui_builder_css(raw_dark)

            sb.save()
            logger.info(
                f"Platform theme updated by {request.user.username} (superuser, "
                f"theme={sb.default_theme}, light={sb.theme_preset_light}, dark={sb.theme_preset_dark})"
            )
            messages.success(request, _("Project theme saved."))
        return redirect("core:profile")
    if SiteBranding is not None and sb is None:
        try:
            sb = SiteBranding.objects.first()
        except Exception:
            sb = None
    # Lightweight stats for badges
    user = request.user
    # Pick a primary organisation if present: prefer one the user owns; else first membership
    primary_owned_org = Organization.objects.filter(owner=user).first()
    first_membership = (
        OrganizationMembership.objects.filter(user=user)
        .select_related("organization")
        .first()
    )
    org = primary_owned_org or (
        first_membership.organization if first_membership else None
    )

    # Check if user has any surveys with encryption enabled
    has_encryption_setup = Survey.objects.filter(
        owner=user,
        encrypted_kek_password__isnull=False,
        encrypted_kek_recovery__isnull=False,
    ).exists()

    # Check if user has any surveys with OIDC encryption
    has_oidc_encryption = Survey.objects.filter(
        owner=user,
        encrypted_kek_oidc__isnull=False,
    ).exists()

    stats = {
        "is_superuser": getattr(user, "is_superuser", False),
        "is_staff": getattr(user, "is_staff", False),
        "orgs_owned": Organization.objects.filter(owner=user).count(),
        "org_admin_count": OrganizationMembership.objects.filter(
            user=user, role=OrganizationMembership.Role.ADMIN
        ).count(),
        "org_memberships": OrganizationMembership.objects.filter(user=user).count(),
        "surveys_owned": Survey.objects.filter(owner=user).count(),
        "survey_creator_count": SurveyMembership.objects.filter(
            user=user, role=SurveyMembership.Role.CREATOR
        ).count(),
        "survey_viewer_count": SurveyMembership.objects.filter(
            user=user, role=SurveyMembership.Role.VIEWER
        ).count(),
        "groups_owned": QuestionGroup.objects.filter(owner=user).count(),
        "question_groups_owned": QuestionGroup.objects.filter(
            owner=user
        ).count(),  # Alias for template clarity
        "responses_submitted": SurveyResponse.objects.filter(submitted_by=user).count(),
        "tokens_created": SurveyAccessToken.objects.filter(created_by=user).count(),
        "has_encryption_setup": has_encryption_setup,
        "has_oidc_encryption": has_oidc_encryption,
    }
    # Prepare language preference form
    lang_pref, created = UserLanguagePreference.objects.get_or_create(user=user)
    language_form = UserLanguagePreferenceForm(instance=lang_pref)
    # Prepare email preferences form
    email_prefs_form = None
    if UserEmailPreferences is not None:
        prefs = UserEmailPreferences.get_or_create_for_user(user)
        email_prefs_form = UserEmailPreferencesForm(instance=prefs)

    # Prepare theme choices for template
    light_theme_choices = (
        [(theme, theme) for theme in LIGHT_THEMES] if LIGHT_THEMES else []
    )
    dark_theme_choices = (
        [(theme, theme) for theme in DARK_THEMES] if DARK_THEMES else []
    )

    return render(
        request,
        "core/profile.html",
        {
            "sb": sb,
            "stats": stats,
            "org": org,
            "language_form": language_form,
            "email_prefs_form": email_prefs_form,
            "can_safely_delete_account": can_user_safely_delete_own_account(user),
            "light_theme_choices": light_theme_choices,
            "dark_theme_choices": dark_theme_choices,
        },
    )


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # With multiple AUTHENTICATION_BACKENDS configured (e.g., ModelBackend + Axes),
            # login() requires an explicit backend unless the user was authenticated via authenticate().
            # Since we just created the user, log them in using the default ModelBackend.
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")

            # Send welcome email
            try:
                from .email_utils import send_welcome_email

                send_welcome_email(user)
            except Exception as e:
                # Don't block signup if email fails
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send welcome email to {user.username}: {e}")

            account_type = request.POST.get("account_type")
            if account_type == "org":
                with transaction.atomic():
                    org_name = (
                        request.POST.get("org_name")
                        or f"{user.username}'s Organisation"
                    )
                    org = Organization.objects.create(name=org_name, owner=user)
                    OrganizationMembership.objects.create(
                        organization=org,
                        user=user,
                        role=OrganizationMembership.Role.ADMIN,
                    )
                messages.success(
                    request, _("Organisation created. You are an organisation admin.")
                )
                return redirect("surveys:org_users", org_id=org.id)
            return redirect("core:home")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def complete_signup(request):
    """
    Complete signup for users who authenticated via OIDC from login page.
    They're already authenticated but need to choose account type and complete setup.
    """
    # Check if user needs signup completion
    if not request.session.get("needs_signup_completion"):
        # User already completed signup or came here by mistake
        return redirect("core:home")

    if request.method == "POST":
        account_type = request.POST.get("account_type")

        # Mark OIDC signup as completed
        if hasattr(request.user, "oidc"):
            request.user.oidc.signup_completed = True
            request.user.oidc.save()
            logger.info(
                f"Marked OIDC signup as completed for user: {request.user.email}"
            )

        # Send welcome email
        try:
            from .email_utils import send_welcome_email

            send_welcome_email(request.user)
        except Exception as e:
            logger.error(
                f"Failed to send welcome email to {request.user.username}: {e}"
            )

        if account_type == "org":
            with transaction.atomic():
                org_name = (
                    request.POST.get("org_name")
                    or f"{request.user.username}'s Organisation"
                )
                org = Organization.objects.create(name=org_name, owner=request.user)
                OrganizationMembership.objects.create(
                    organization=org,
                    user=request.user,
                    role=OrganizationMembership.Role.ADMIN,
                )
            messages.success(
                request, _("Organisation created. You are an organisation admin.")
            )
            # Clear the signup completion flag
            request.session.pop("needs_signup_completion", None)
            return redirect("surveys:org_users", org_id=org.id)

        # Individual account - just clear the flag and redirect home
        messages.success(request, _("Account setup complete! Welcome to CheckTick."))
        request.session.pop("needs_signup_completion", None)
        return redirect("core:home")

    return render(
        request,
        "registration/complete_signup.html",
        {
            "user": request.user,
        },
    )


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
    "internationalization": {
        "title": "Internationalization",
        "order": 9,
        "icon": "🌍",
    },
    "getting-involved": {
        "title": "Getting Involved",
        "order": 10,
        "icon": "🤝",
    },
}

# Manual overrides for specific files (optional)
# If a file isn't listed here, it will be auto-discovered
# Format: "slug": {"file": "filename.md", "category": "category-key", "title": "Custom Title"}
DOC_PAGE_OVERRIDES = {
    "index": {"file": "README.md", "category": None, "standalone": True, "icon": "🏠", "order": 0, "title": "Welcome"},  # Landing page
    "getting-help": {"file": "getting-help.md", "category": None, "standalone": True, "icon": "💬", "order": 0.5, "title": "Getting Help"},  # Standalone item
    "contributing": {"file": REPO_ROOT / "CONTRIBUTING.md", "category": "getting-involved"},
    "themes": {
        "file": "themes.md",
        "category": "api",
    },  # Developer guide for theme implementation
    "FOLLOWUP_FEATURE_SUMMARY": {
        "file": "FOLLOWUP_FEATURE_SUMMARY.md",
        "category": "features",
        "title": "Follow-up Questions & Bulk Import",
    },
    "documentation-system": {
        "file": "documentation-system.md",
        "category": "getting-involved",
    },
    "issues-vs-discussions": {
        "file": "issues-vs-discussions.md",
        "category": "getting-involved",
    },
}


def _discover_doc_pages():
    """
    Auto-discover all markdown files in docs/ directory and organize by category.

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

        # Add to category if specified
        category = config.get("category")
        if category and category in categorized:
            categorized[category].append(
                {
                    "slug": slug,
                    "title": config.get("title") or _doc_title(slug),
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

            # Determine category by filename patterns
            category = _infer_category(slug)

            # Extract title from file (first H1) or use slug
            title = _extract_title_from_file(md_file) or _doc_title(slug)

            pages[slug] = md_file
            categorized[category].append(
                {
                    "slug": slug,
                    "title": title,
                    "file": md_file,
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

    return pages, categorized


def _infer_category(slug: str) -> str:
    """Infer category from slug/filename patterns."""
    slug_lower = slug.lower()

    # Getting Started
    if any(x in slug_lower for x in ["getting-started", "quickstart"]):
        return "getting-started"

    # Self-Hosting (check before Configuration since some keywords overlap)
    if any(
        x in slug_lower
        for x in [
            "self-hosting",
            "deployment",
            "production",
            "backup",
            "database",
            "scheduled-tasks",
        ]
    ):
        return "self-hosting"

    # Features
    if any(
        x in slug_lower
        for x in ["surveys", "collections", "groups", "import", "publish"]
    ):
        return "features"

    # Configuration
    if any(
        x in slug_lower
        for x in [
            "branding",
            "theme",
            "user-management",
            "prefilled-datasets-setup",
            "email",
            "notifications",
            "oidc",
        ]
    ):
        return "configuration"

    # Security
    if any(
        x in slug_lower
        for x in [
            "security",
            "encryption",
            "patient-data",
            "authentication",
            "permissions",
        ]
    ):
        return "security"

    # Data Governance
    if any(
        x in slug_lower
        for x in [
            "data-governance",
            "data-export",
            "data-retention",
            "data-policy",
            "data-deletion",
            "data-management",
        ]
    ):
        return "data-governance"

    # API & Development
    if any(x in slug_lower for x in ["api", "adding-", "development"]):
        return "api"

    # Testing
    if any(x in slug_lower for x in ["testing", "test-"]):
        return "testing"

    # Internationalization
    if any(
        x in slug_lower
        for x in ["i18n", "internationalization", "translation", "locale"]
    ):
        return "internationalization"

    # Getting Involved (contributing, documentation, etc.)
    if any(x in slug_lower for x in ["advanced", "custom", "extend", "contributing", "documentation-system", "issues"]):
        return "getting-involved"

    # Default to features for uncategorized docs
    return "features"


def _extract_title_from_file(file_path: Path) -> str | None:
    """Extract title from first # heading in markdown file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except Exception:
        pass
    return None


# Build the pages dict and categorized structure
DOC_PAGES, DOC_CATEGORIES_WITH_PAGES = _discover_doc_pages()


def _nav_pages():
    """
    Return categorized navigation structure for documentation.

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
            standalone_items.append({
                "slug": slug,
                "title": config.get("title") or _doc_title(slug),
                "icon": config.get("icon", ""),
                "order": config.get("order", 99),
                "standalone": True,
            })

    # Add categories with pages
    for cat_key, pages_list in DOC_CATEGORIES_WITH_PAGES.items():
        if not pages_list:  # Skip empty categories
            continue

        cat_info = DOC_CATEGORIES.get(cat_key, {"title": cat_key.title(), "order": 99})

        nav.append(
            {
                "key": cat_key,
                "title": cat_info.get("title", cat_key.title()),
                "icon": cat_info.get("icon", ""),
                "order": cat_info.get("order", 99),
                "pages": sorted(pages_list, key=lambda p: p["title"]),
                "standalone": False,
            }
        )

    # Add standalone items to nav
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

    html = mdlib.markdown(
        file_path.read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables", "toc"],
    )
    return render(
        request,
        "core/docs.html",
        {"html": html, "active_slug": slug, "pages": _nav_pages()},
    )


class BrandedPasswordResetView(auth_views.PasswordResetView):
    """Password reset view that ensures brand context is available to email templates.

    We pass extra_email_context on each request so templates like
    registration/password_reset_subject.txt can use {{ brand.title }}.
    Additionally, we ensure an HTML alternative is attached via
    html_email_template_name.
    """

    template_name = "registration/password_reset_form.html"
    subject_template_name = "registration/password_reset_subject.txt"
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"

    def get_email_options(self):
        opts = super().get_email_options()
        # Merge in brand context so email templates can use {{ brand.* }}.
        try:
            from checktick_app.context_processors import branding as _branding

            ctx = _branding(self.request)
            brand = ctx.get("brand", {})
        except Exception:
            brand = {"title": getattr(settings, "BRAND_TITLE", "CheckTick")}
        extra = opts.get("extra_email_context") or {}
        # Avoid mutating the original dict in place across requests
        merged = {**extra, "brand": brand}
        opts["extra_email_context"] = merged
        return opts


## Removed DirectPasswordResetConfirmView to use Django's standard confirm flow.


# Note: User and organization deletion is handled through Django Admin interface
# by superusers only. Regular users cannot delete accounts for security reasons.
# This protects against accidental data loss and maintains audit trails.


def can_user_safely_delete_own_account(user):
    """
    Check if a user can safely delete their own account without affecting others.

    Users can delete their account if:
    - They are not in any organizations
    - None of their surveys have collaborators
    - They are not collaborators on others' surveys
    """
    if not user.is_authenticated:
        return False

    # Check org memberships
    has_org_memberships = OrganizationMembership.objects.filter(user=user).exists()
    if has_org_memberships:
        return False

    # Check if any of their surveys have collaborators
    user_surveys = Survey.objects.filter(owner=user)
    for survey in user_surveys:
        has_collaborators = (
            SurveyMembership.objects.filter(survey=survey).exclude(user=user).exists()
        )
        if has_collaborators:
            return False

    # Check if they are a collaborator on others' surveys
    is_collaborator = SurveyMembership.objects.filter(user=user).exists()
    if is_collaborator:
        return False

    return True


@login_required
def delete_account(request):
    """
    Allow individual users to delete their own account if it's safe to do so.
    Safe deletion means no impact on other users or shared data.
    """
    if request.method != "POST":
        return redirect("core:profile")

    user = request.user

    # Check if user can safely delete their account
    if not can_user_safely_delete_own_account(user):
        messages.error(
            request,
            _(
                "Cannot delete account. You are either part of an organization, "
                "have surveys with collaborators, or are a collaborator on other surveys. "
                "Please contact an administrator for assistance."
            ),
        )
        return redirect("core:profile")

    try:
        with transaction.atomic():
            # Get count of surveys for confirmation message
            survey_count = Survey.objects.filter(owner=user).count()

            # Delete user (CASCADE will handle owned surveys and responses)
            user.delete()

            # Add success message to session
            messages.success(
                request,
                _(
                    f"Your account and {survey_count} survey(s) have been permanently deleted. "
                    "Thank you for using CheckTick."
                ),
            )

        # Redirect to home page after successful deletion
        return redirect("/")

    except Exception as e:
        messages.error(
            request,
            _(
                "An error occurred while deleting your account. Please try again or contact support."
            ),
        )
        logger.error(f"Error deleting user account {user.id}: {e}")
        return redirect("core:profile")
