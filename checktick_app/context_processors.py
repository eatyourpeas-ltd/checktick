import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from checktick_app.surveys.models import OrganizationMembership, SurveyMembership

try:
    from importlib import metadata as _importlib_metadata  # Python 3.8+
except Exception:  # pragma: no cover
    _importlib_metadata = None
try:
    from checktick_app.core.models import SiteBranding
except Exception:  # pragma: no cover - tolerate missing model during migrations
    SiteBranding = None


_GIT_CACHE = None


def _get_git_info():
    global _GIT_CACHE
    if _GIT_CACHE is not None:
        return _GIT_CACHE
    info = {"commit": None, "commit_date": None, "branch": None}
    # Prefer environment variables (for Docker/CI)
    env_sha = (
        os.environ.get("GIT_COMMIT")
        or os.environ.get("GIT_SHA")
        or os.environ.get("GITHUB_SHA")
        or os.environ.get("SOURCE_VERSION")
    )
    env_time = os.environ.get("BUILD_TIMESTAMP")
    env_branch = (
        os.environ.get("GIT_BRANCH")
        or os.environ.get("BRANCH_NAME")
        or os.environ.get("SOURCE_BRANCH")
        or os.environ.get("GITHUB_REF_NAME")
    )
    if env_sha:
        info["commit"] = env_sha[:7]
    if env_time:
        info["commit_date"] = env_time
    if env_branch:
        info["branch"] = env_branch
    # Attempt to read from local git repo if available
    if info["commit"] is None:
        try:
            short = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
            info["commit"] = short or None
        except Exception:
            pass
    if info["commit_date"] is None:
        try:
            commit_date = (
                subprocess.check_output(
                    ["git", "log", "-1", "--format=%cI"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
            info["commit_date"] = commit_date or None
        except Exception:
            pass
    if info.get("branch") is None:
        try:
            branch = (
                subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
            # When in detached HEAD (e.g., CI), this may return 'HEAD'; treat that as None
            info["branch"] = branch if branch and branch != "HEAD" else None
        except Exception:
            pass
    _GIT_CACHE = info
    return info


def branding(request):
    """Inject platform branding defaults into all templates.

    These can be overridden per-survey by passing variables with the same names in a view.
    """
    # Compute a lightweight flag to show/hide the User management link
    user = getattr(request, "user", AnonymousUser())
    can_manage_any_users = False
    if user and user.is_authenticated:
        can_manage_any_users = (
            OrganizationMembership.objects.filter(
                user=user, role=OrganizationMembership.Role.ADMIN
            ).exists()
            or SurveyMembership.objects.filter(
                user=user, role=SurveyMembership.Role.CREATOR
            ).exists()
        )

    # Defaults from settings
    brand = {
        "title": getattr(settings, "BRAND_TITLE", "CheckTick"),
        # Only set when explicitly configured
        "icon_url": getattr(settings, "BRAND_ICON_URL", None),
        # Optional dark-mode icon; when present, shown when data-theme contains 'checktick-dark'
        "icon_url_dark": getattr(settings, "BRAND_ICON_URL_DARK", None),
        # Accessibility and UX metadata for the brand icon
        "icon_alt": getattr(settings, "BRAND_ICON_ALT", None),
        "icon_title": getattr(settings, "BRAND_ICON_TITLE", None),
        # Icon size (Tailwind classes). Prefer explicit class; fall back to numeric size -> w-{n} h-{n}
        "icon_size_class": None,
        "theme_name": getattr(settings, "BRAND_THEME", "checktick-light"),
        "font_heading": getattr(
            settings,
            "BRAND_FONT_HEADING",
            "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple Color Emoji', 'Segoe UI Emoji'",
        ),
        "font_body": getattr(
            settings,
            "BRAND_FONT_BODY",
            "Merriweather, ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
        ),
        "font_css_url": getattr(
            settings,
            "BRAND_FONT_CSS_URL",
            "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=Merriweather:wght@300;400;700&display=swap",
        ),
        # Optional CSS overrides injected into head to support DaisyUI builder pastes
        "theme_css_light": getattr(settings, "BRAND_THEME_CSS_LIGHT", ""),
        "theme_css_dark": getattr(settings, "BRAND_THEME_CSS_DARK", ""),
    }
    # Compute icon_size_class from settings
    try:
        size_class = getattr(settings, "BRAND_ICON_SIZE_CLASS", None)
        if not size_class:
            raw_size = getattr(settings, "BRAND_ICON_SIZE", None)
            if isinstance(raw_size, int) or (
                isinstance(raw_size, str) and raw_size.isdigit()
            ):
                size_class = f"w-{raw_size} h-{raw_size}"
            elif isinstance(raw_size, str) and ("w-" in raw_size or "h-" in raw_size):
                size_class = raw_size
        brand["icon_size_class"] = size_class or "w-6 h-6"
    except Exception:
        brand["icon_size_class"] = "w-6 h-6"
    # Overlay with DB-stored SiteBranding if present
    if SiteBranding is not None:
        try:
            sb = SiteBranding.objects.first()
            if sb:
                # Determine icon href: prefer uploaded file when present
                icon_href = brand["icon_url"]
                dark_icon_href = brand["icon_url_dark"]
                try:
                    if getattr(sb, "icon_file", None) and sb.icon_file.name:
                        from django.conf import settings as _s

                        icon_href = f"{_s.MEDIA_URL}{sb.icon_file.name}"
                    if getattr(sb, "icon_file_dark", None) and sb.icon_file_dark.name:
                        from django.conf import settings as _s2

                        dark_icon_href = f"{_s2.MEDIA_URL}{sb.icon_file_dark.name}"
                except Exception:
                    pass
                brand.update(
                    {
                        "icon_url": (sb.icon_url or icon_href) or None,
                        "icon_url_dark": (sb.icon_url_dark or dark_icon_href) or None,
                        "theme_name": sb.default_theme or brand["theme_name"],
                        "font_heading": sb.font_heading or brand["font_heading"],
                        "font_body": sb.font_body or brand["font_body"],
                        "font_css_url": sb.font_css_url or brand["font_css_url"],
                        "theme_css_light": sb.theme_light_css
                        or brand["theme_css_light"],
                        "theme_css_dark": sb.theme_dark_css or brand["theme_css_dark"],
                    }
                )
        except Exception:
            # During migrations or early setup, ignore DB failures
            pass

    # Build/version metadata
    git = _get_git_info()
    # Resolve version: env -> settings -> installed package metadata -> 'dev'
    version_val = os.environ.get("APP_VERSION") or getattr(
        settings, "APP_VERSION", None
    )
    if not version_val and _importlib_metadata is not None:
        try:
            version_val = _importlib_metadata.version("checktick")
        except Exception:
            version_val = None

    # Get CSS hash from file or environment for cache-busting
    css_hash = os.environ.get("CSS_HASH")
    if not css_hash:
        try:
            hash_file = Path("/tmp/css_hash.txt")
            if hash_file.exists():
                css_hash = hash_file.read_text().strip()
        except Exception:
            pass

    build = {
        "version": version_val or "dev",
        "timestamp": os.environ.get("BUILD_TIMESTAMP")
        or getattr(settings, "BUILD_TIMESTAMP", None),
        "commit": git.get("commit"),
        "branch": git.get("branch"),
        "commit_date": git.get("commit_date"),
        "css_hash": css_hash or "dev",
    }

    return {
        "brand": brand,
        "can_manage_any_users": can_manage_any_users,
        "build": build,
        "settings": {
            "HCAPTCHA_SITEKEY": getattr(settings, "HCAPTCHA_SITEKEY", ""),
        },
    }
