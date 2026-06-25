import re
import secrets

from django.contrib.auth.models import User
from django.urls import reverse
import pytest


@pytest.mark.django_db
class TestPasswordResetFlow:
    def test_password_reset_pages_render(self, client):
        assert client.get(reverse("password_reset")).status_code == 200
        assert client.get(reverse("password_reset_done")).status_code == 200
        assert client.get(reverse("password_reset_complete")).status_code == 200

    def test_request_reset_sends_email(self, client, mailoutbox):
        # Generate passwords and unique identifiers at runtime to avoid conflicts in parallel tests
        initial_password = secrets.token_urlsafe(12)
        new_password = secrets.token_urlsafe(16)
        unique_id = secrets.token_hex(8)
        email = f"alice_{unique_id}@example.com"
        user = User.objects.create_user(
            username=email,
            email=email,
            password=initial_password,
        )
        resp = client.post(reverse("password_reset"), {"email": user.email})
        # Redirect to done
        assert resp.status_code == 302
        assert resp.url == reverse("password_reset_done")
        # Email sent
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert "Reset your password" in msg.subject
        # Ensure an HTML alternative is present and includes the CTA button.
        assert msg.alternatives, "Expected HTML alternative email"
        assert any("Reset your password" in alt[0] for alt in msg.alternatives)
        # Extract token URL from email body (Django includes a token URL that redirects)
        m = re.search(r"/accounts/reset/[^\s]+/[^\s/]+/", msg.body)
        assert m, msg.body
        token_path = m.group(0)
        # First GET to token URL typically redirects to the set-password URL
        resp2 = client.get(token_path)
        assert resp2.status_code == 302
        set_password_path = resp2.url
        # Follow to the set-password page which should render 200
        resp3 = client.get(set_password_path)
        assert resp3.status_code == 200
        # Post new password on the set-password URL
        post2 = client.post(
            set_password_path,
            {"new_password1": new_password, "new_password2": new_password},
        )
        assert post2.status_code == 302
        assert post2.url == reverse("password_reset_complete")
        # Can login with new password (username field holds the email address)
        login = client.post(
            "/accounts/login/", {"username": user.email, "password": new_password}
        )
        assert login.status_code == 302

    def test_password_reset_email_subject_includes_brand_name(self, client, mailoutbox):
        """Test that password reset email subject includes the platform brand name."""
        unique_id = secrets.token_hex(8)
        email = f"brand_test_{unique_id}@example.com"
        user = User.objects.create_user(
            username=email,
            email=email,
            password=secrets.token_urlsafe(12),
        )
        client.post(reverse("password_reset"), {"email": user.email})
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        # Subject should include the brand name (e.g., "CheckTick: Reset your password")
        assert (
            "CheckTick" in msg.subject
        ), f"Expected brand name 'CheckTick' in subject, got: '{msg.subject}'"
        assert "Reset your password" in msg.subject

    def test_password_reset_email_body_includes_brand_name(self, client, mailoutbox):
        """Test that password reset email body includes the platform brand name."""
        unique_id = secrets.token_hex(8)
        email = f"brand_body_{unique_id}@example.com"
        user = User.objects.create_user(
            username=email,
            email=email,
            password=secrets.token_urlsafe(12),
        )
        client.post(reverse("password_reset"), {"email": user.email})
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        # Plain text body should include the brand name
        assert (
            "CheckTick" in msg.body
        ), "Expected brand name 'CheckTick' in plain text body"
        # HTML alternative should also include the brand name
        assert msg.alternatives, "Expected HTML alternative email"
        html_content = msg.alternatives[0][0]
        assert (
            "CheckTick" in html_content
        ), "Expected brand name 'CheckTick' in HTML body"
