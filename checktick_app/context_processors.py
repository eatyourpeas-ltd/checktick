import logging
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    SurveyMembership,
    TeamMembership,
)

logger = logging.getLogger(__name__)

try:
    from importlib import metadata as _importlib_metadata  # Python 3.8+
except Exception:  # pragma: no cover
    _importlib_metadata = None
try:
    from checktick_app.core.models import SiteBranding
except Exception:  # pragma: no cover - tolerate missing model during migrations
    SiteBranding = None
try:
    from checktick_app.core.themes import generate_theme_css_for_brand
except Exception:  # pragma: no cover - tolerate missing module during migrations
    generate_theme_css_for_brand = None


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
    can_create_datasets_flag = False
    if user and user.is_authenticated:
        can_manage_any_users = (
            OrganizationMembership.objects.filter(
                user=user, role=OrganizationMembership.Role.ADMIN
            ).exists()
            or TeamMembership.objects.filter(
                user=user, role=TeamMembership.Role.ADMIN
            ).exists()
            or SurveyMembership.objects.filter(
                user=user, role=SurveyMembership.Role.CREATOR
            ).exists()
        )
        # TODO: In future, restrict dataset creation to pro individual accounts
        # All authenticated users can create datasets (individual or organization-based)
        can_create_datasets_flag = True

    # All defaults are defined in settings.py - this is the single source of truth
    brand = {
        "title": settings.BRAND_TITLE or "CheckTick",
        "icon_url": settings.BRAND_ICON_URL,
        "icon_url_dark": settings.BRAND_ICON_URL_DARK,
        "icon_alt": settings.BRAND_ICON_ALT,
        "icon_title": settings.BRAND_ICON_TITLE,
        "icon_size_class": None,  # Computed below
        "theme_name": settings.BRAND_THEME or "checktick-light",
        "font_heading": settings.BRAND_FONT_HEADING,
        "font_body": settings.BRAND_FONT_BODY,
        "font_css_url": settings.BRAND_FONT_CSS_URL,
        "theme_css_light": settings.BRAND_THEME_CSS_LIGHT or "",
        "theme_css_dark": settings.BRAND_THEME_CSS_DARK or "",
        "theme_preset_light": settings.BRAND_THEME_PRESET_LIGHT or "lofi",
        "theme_preset_dark": settings.BRAND_THEME_PRESET_DARK or "dim",
    }
    # Compute icon_size_class from settings
    try:
        size_class = settings.BRAND_ICON_SIZE_CLASS
        if not size_class:
            raw_size = settings.BRAND_ICON_SIZE
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
                # Only use file reference if the file actually exists in storage
                icon_href = brand["icon_url"]
                dark_icon_href = brand["icon_url_dark"]
                try:
                    if getattr(sb, "icon_file", None) and sb.icon_file.name:
                        # Check if file actually exists in storage before using it
                        try:
                            if sb.icon_file.storage.exists(sb.icon_file.name):
                                from django.conf import settings as _s

                                icon_href = f"{_s.MEDIA_URL}{sb.icon_file.name}"
                        except Exception:
                            pass  # File doesn't exist, fall back to default
                    if getattr(sb, "icon_file_dark", None) and sb.icon_file_dark.name:
                        # Check if file actually exists in storage before using it
                        try:
                            if sb.icon_file_dark.storage.exists(sb.icon_file_dark.name):
                                from django.conf import settings as _s2

                                dark_icon_href = (
                                    f"{_s2.MEDIA_URL}{sb.icon_file_dark.name}"
                                )
                        except Exception:
                            pass  # File doesn't exist, fall back to default
                except Exception:
                    pass

                # Get theme presets
                preset_light = (
                    getattr(sb, "theme_preset_light", "")
                    or settings.BRAND_THEME_PRESET_LIGHT
                )
                preset_dark = (
                    getattr(sb, "theme_preset_dark", "")
                    or settings.BRAND_THEME_PRESET_DARK
                )

                # Generate theme CSS from presets or use custom CSS
                theme_css_light = brand["theme_css_light"]
                theme_css_dark = brand["theme_css_dark"]

                if generate_theme_css_for_brand:
                    try:
                        custom_css_light = getattr(sb, "theme_light_css", "")
                        custom_css_dark = getattr(sb, "theme_dark_css", "")

                        generated_light, generated_dark = generate_theme_css_for_brand(
                            preset_light, preset_dark, custom_css_light, custom_css_dark
                        )
                        theme_css_light = generated_light
                        theme_css_dark = generated_dark
                    except Exception:
                        # Fall back to raw CSS if generation fails
                        theme_css_light = sb.theme_light_css or brand["theme_css_light"]
                        theme_css_dark = sb.theme_dark_css or brand["theme_css_dark"]
                else:
                    # Fallback if themes module not available
                    theme_css_light = sb.theme_light_css or brand["theme_css_light"]
                    theme_css_dark = sb.theme_dark_css or brand["theme_css_dark"]

                brand.update(
                    {
                        "icon_url": (sb.icon_url or icon_href) or None,
                        "icon_url_dark": (sb.icon_url_dark or dark_icon_href) or None,
                        "theme_name": sb.default_theme or brand["theme_name"],
                        "theme_preset_light": preset_light,  # Actual daisyUI preset name
                        "theme_preset_dark": preset_dark,  # Actual daisyUI preset name
                        "font_heading": sb.font_heading or brand["font_heading"],
                        "font_body": sb.font_body or brand["font_body"],
                        "font_css_url": sb.font_css_url or brand["font_css_url"],
                        "theme_css_light": theme_css_light,
                        "theme_css_dark": theme_css_dark,
                    }
                )
        except Exception:
            # During migrations or early setup, ignore DB failures
            pass

    # Organization-level theme cascade (overrides platform defaults)
    # Only apply if user is part of an organization
    user_org = None
    if user and user.is_authenticated:
        try:
            # Get user's primary organization (prefer owned, then first membership)
            user_org = Organization.objects.filter(owner=user).first()
            if not user_org:
                membership = (
                    OrganizationMembership.objects.filter(user=user)
                    .select_related("organization")
                    .first()
                )
                if membership:
                    user_org = membership.organization
        except Exception:
            pass

    if user_org and (
        user_org.default_theme
        or user_org.theme_preset_light
        or user_org.theme_preset_dark
    ):
        # Organization has custom theme settings - apply cascade
        # Use org theme if set, otherwise fall back to platform default
        preset_light = user_org.theme_preset_light or brand.get(
            "theme_preset_light", settings.BRAND_THEME_PRESET_LIGHT
        )
        preset_dark = user_org.theme_preset_dark or brand.get(
            "theme_preset_dark", settings.BRAND_THEME_PRESET_DARK
        )

        logger.debug(
            f"Applying org theme cascade for org_id={user_org.id}: "
            f"default_theme={user_org.default_theme}, "
            f"preset_light={preset_light}, preset_dark={preset_dark}"
        )

        # Generate or use organization theme CSS
        theme_css_light = brand["theme_css_light"]
        theme_css_dark = brand["theme_css_dark"]

        if generate_theme_css_for_brand:
            try:
                custom_css_light = user_org.theme_light_css or ""
                custom_css_dark = user_org.theme_dark_css or ""

                generated_light, generated_dark = generate_theme_css_for_brand(
                    preset_light, preset_dark, custom_css_light, custom_css_dark
                )
                theme_css_light = generated_light
                theme_css_dark = generated_dark
            except Exception:
                # Fall back to raw CSS if generation fails
                theme_css_light = user_org.theme_light_css or brand["theme_css_light"]
                theme_css_dark = user_org.theme_dark_css or brand["theme_css_dark"]
        else:
            # Fallback if themes module not available
            theme_css_light = user_org.theme_light_css or brand["theme_css_light"]
            theme_css_dark = user_org.theme_dark_css or brand["theme_css_dark"]

        brand.update(
            {
                "theme_name": user_org.default_theme or brand["theme_name"],
                "theme_preset_light": preset_light,
                "theme_preset_dark": preset_dark,
                "theme_css_light": theme_css_light,
                "theme_css_dark": theme_css_dark,
            }
        )

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
        "can_create_datasets": can_create_datasets_flag,
        "build": build,
        "debug": settings.DEBUG,
        "self_hosted": getattr(settings, "SELF_HOSTED", False),
        "payment_client_token": getattr(settings, "PAYMENT_CLIENT_TOKEN", ""),
        "payment_environment": getattr(settings, "PAYMENT_ENVIRONMENT", "sandbox"),
        "settings": {
            "HCAPTCHA_SITEKEY": getattr(settings, "HCAPTCHA_SITEKEY", ""),
        },
    }
