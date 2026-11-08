"""Browser tab icon (favicon) precedence on respondent survey pages.

Precedence: per-survey icon (survey.style.icon_url) wins over the brand
icon (brand.icon_url), which wins over the platform icon served from the
components/icons/checktick.html component (core:platform_favicon).
"""

import xml.etree.ElementTree as ET

from django.urls import reverse
import pytest

from checktick_app.core.models import SiteBranding
from checktick_app.surveys.models import Survey


def _public_survey(user, slug, style=None):
    return Survey.objects.create(
        owner=user,
        name="Favicon survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
        style=style or {},
    )


@pytest.mark.django_db
def test_platform_favicon_serves_component_svg(client):
    """The favicon endpoint renders the icon component as a standalone SVG."""
    resp = client.get(reverse("core:platform_favicon"))

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("image/svg+xml")
    assert "public" in resp["Cache-Control"]
    body = resp.content.decode()
    # The platform wordmark component, not the old clipboard favicon.
    assert 'viewBox="0 0 236.71 174.37"' in body
    # Served as an image document, the SVG must be well-formed XML.
    ET.fromstring(resp.content)


@pytest.mark.django_db
def test_take_page_favicon_falls_back_to_platform_icon(client, django_user_model):
    """Without a survey or brand icon, the tab icon is the platform icon."""
    user = django_user_model.objects.create_user(username="fav-owner", password="p")
    survey = _public_survey(user, "favicon-fallback")

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    html = resp.content.decode()
    assert f'<link rel="icon" href="{reverse("core:platform_favicon")}"' in html
    # The old static favicon file must no longer be linked.
    assert "checktick_brand_favicon.svg" not in html


@pytest.mark.django_db
def test_thank_you_page_favicon_falls_back_to_platform_icon(client, django_user_model):
    user = django_user_model.objects.create_user(username="fav-owner2", password="p")
    survey = _public_survey(user, "favicon-thanks")

    resp = client.get(reverse("surveys:thank_you", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    html = resp.content.decode()
    assert f'<link rel="icon" href="{reverse("core:platform_favicon")}"' in html


@pytest.mark.django_db
def test_survey_icon_wins_for_favicon(client, django_user_model):
    """A per-survey icon overrides the brand and platform icons."""
    user = django_user_model.objects.create_user(username="fav-owner3", password="p")
    survey = _public_survey(
        user, "favicon-survey-icon", style={"icon_url": "/static/favicon.ico"}
    )

    for url_name in ("surveys:take", "surveys:thank_you"):
        resp = client.get(reverse(url_name, kwargs={"slug": survey.slug}))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert '<link rel="icon" href="/static/favicon.ico"' in html


@pytest.mark.django_db
def test_unsafe_survey_icon_url_never_reaches_favicon_link(client, django_user_model):
    """Defence in depth: a javascript: URI stored directly in style.icon_url
    (bypassing the write-time validator) must not reach the favicon link on
    any respondent page; the platform icon is served instead.
    """
    user = django_user_model.objects.create_user(username="fav-owner5", password="p")
    survey = _public_survey(
        user, "favicon-unsafe", style={"icon_url": "javascript:alert(document.cookie)"}
    )

    for url_name in ("surveys:take", "surveys:thank_you"):
        resp = client.get(reverse(url_name, kwargs={"slug": survey.slug}))
        assert resp.status_code == 200
        assert b"javascript:" not in resp.content
        assert (
            f'<link rel="icon" href="{reverse("core:platform_favicon")}"'
            in resp.content.decode()
        )


@pytest.mark.django_db
def test_brand_icon_used_when_survey_has_none(client, django_user_model):
    """The brand icon sits between the survey icon and the platform icon."""
    SiteBranding.objects.create(icon_url="https://example.com/brand-icon.png")
    user = django_user_model.objects.create_user(username="fav-owner4", password="p")
    survey = _public_survey(user, "favicon-brand")

    resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200

    html = resp.content.decode()
    assert '<link rel="icon" href="https://example.com/brand-icon.png"' in html
    assert reverse("core:platform_favicon") not in html
