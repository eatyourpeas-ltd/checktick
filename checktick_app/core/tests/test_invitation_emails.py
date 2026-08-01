"""Security regression tests for team and organisation invitation emails."""

from types import SimpleNamespace
from unittest.mock import patch

from django.template import TemplateDoesNotExist
import pytest

from checktick_app.core.email_utils import (
    send_org_invitation_email,
    send_team_invitation_email,
)

MALICIOUS_NAME = '<a href="https://evil.example">Verify your account</a>'
ESCAPED_NAME = (
    "&lt;a href=&quot;https://evil.example&quot;&gt;Verify your account&lt;/a&gt;"
)


@pytest.fixture
def branding():
    return {
        "title": "CheckTick Test",
        "primary_color": "#3b82f6",
        "font_heading": "Arial",
        "font_body": "Arial",
    }


@pytest.fixture
def invited_by():
    return SimpleNamespace(
        username="inviter",
        email="inviter@example.com",
        get_full_name=lambda: MALICIOUS_NAME,
    )


def _sent_html(mock_email_class):
    return mock_email_class.return_value.attach_alternative.call_args.args[0]


@pytest.mark.parametrize("invitation_type", ["team", "organisation"])
def test_invitation_email_escapes_attacker_controlled_html(
    invitation_type, branding, invited_by
):
    """Names controlled by an inviter must render as text, not trusted HTML."""
    with (
        patch(
            "checktick_app.core.email_utils.get_platform_branding",
            return_value=branding,
        ),
        patch("checktick_app.core.email_utils.EmailMultiAlternatives") as email_class,
    ):
        email_class.return_value.send.return_value = 1

        if invitation_type == "team":
            organization = SimpleNamespace(name=MALICIOUS_NAME)
            team = SimpleNamespace(name=MALICIOUS_NAME, organization=organization)
            result = send_team_invitation_email(
                "recipient@example.com", team, "viewer", invited_by
            )
        else:
            organization = SimpleNamespace(name=MALICIOUS_NAME)
            result = send_org_invitation_email(
                "recipient@example.com", organization, "viewer", invited_by
            )

    assert result is True
    html = _sent_html(email_class)
    assert MALICIOUS_NAME not in html
    assert ESCAPED_NAME in html


@pytest.mark.parametrize("invitation_type", ["team", "organisation"])
def test_invitation_email_fallback_escapes_attacker_controlled_html(
    invitation_type, branding, invited_by
):
    """A missing content template must not reintroduce HTML injection."""
    captured = {}

    def capture_email(**kwargs):
        captured.update(kwargs)
        return True

    with (
        patch(
            "checktick_app.core.email_utils.get_platform_branding",
            return_value=branding,
        ),
        patch(
            "checktick_app.core.email_utils.render_to_string",
            side_effect=TemplateDoesNotExist("invitation template"),
        ),
        patch(
            "checktick_app.core.email_utils.send_branded_email",
            side_effect=capture_email,
        ),
    ):
        if invitation_type == "team":
            organization = SimpleNamespace(name=MALICIOUS_NAME)
            team = SimpleNamespace(name=MALICIOUS_NAME, organization=organization)
            result = send_team_invitation_email(
                "recipient@example.com", team, "viewer", invited_by
            )
        else:
            organization = SimpleNamespace(name=MALICIOUS_NAME)
            result = send_org_invitation_email(
                "recipient@example.com", organization, "viewer", invited_by
            )

    assert result is True
    markdown_content = captured["markdown_content"]
    assert MALICIOUS_NAME not in markdown_content
    assert ESCAPED_NAME in markdown_content
