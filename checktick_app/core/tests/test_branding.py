"""Tests for branding configuration functionality."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from checktick_app.core.models import SiteBranding, UserProfile

User = get_user_model()

TEST_PASSWORD = "x"


class BrandingConfigurationTestCase(TestCase):
    """Test branding configuration functionality."""

    def setUp(self):
        """Set up test users with different tiers."""
        self.free_user = User.objects.create_user(
            username="freeuser", email="free@test.com", password=TEST_PASSWORD
        )
        self.free_user.profile.account_tier = UserProfile.AccountTier.FREE
        self.free_user.profile.save()

        self.pro_user = User.objects.create_user(
            username="prouser", email="pro@test.com", password=TEST_PASSWORD
        )
        self.pro_user.profile.account_tier = UserProfile.AccountTier.PRO
        self.pro_user.profile.save()

        self.org_user = User.objects.create_user(
            username="orguser", email="org@test.com", password=TEST_PASSWORD
        )
        self.org_user.profile.account_tier = UserProfile.AccountTier.ORGANIZATION
        self.org_user.profile.save()

        self.enterprise_user = User.objects.create_user(
            username="entuser", email="ent@test.com", password=TEST_PASSWORD
        )
        self.enterprise_user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
        self.enterprise_user.profile.save()

        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password=TEST_PASSWORD
        )

    @override_settings(SELF_HOSTED=False)
    def test_free_user_cannot_access_branding(self):
        """FREE tier users cannot access branding configuration."""
        self.client.login(username="freeuser", password=TEST_PASSWORD)

        response = self.client.get(reverse("core:configure_branding"))
        self.assertEqual(response.status_code, 302)  # Redirected
        self.assertEqual(response.url, reverse("core:profile"))

    @override_settings(SELF_HOSTED=False)
    def test_pro_user_cannot_access_branding(self):
        """PRO tier users cannot access branding configuration."""
        self.client.login(username="prouser", password=TEST_PASSWORD)

        response = self.client.get(reverse("core:configure_branding"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:profile"))

    @override_settings(SELF_HOSTED=False)
    def test_org_user_cannot_access_branding(self):
        """ORGANIZATION tier users cannot access branding configuration."""
        self.client.login(username="orguser", password=TEST_PASSWORD)

        response = self.client.get(reverse("core:configure_branding"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:profile"))

    def test_enterprise_user_can_access_branding(self):
        """ENTERPRISE tier users CAN access branding configuration in hosted mode."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.get(reverse("core:configure_branding"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Configure Site Branding")

    def test_superuser_can_access_branding_self_hosted(self):
        """Superusers CAN access branding in self-hosted mode."""
        self.client.login(username="admin", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=True):
            response = self.client.get(reverse("core:configure_branding"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Configure Site Branding")

    def test_non_superuser_cannot_access_branding_self_hosted(self):
        """Non-superusers cannot access branding in self-hosted mode."""
        self.client.login(username="freeuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=True):
            response = self.client.get(reverse("core:configure_branding"))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("core:profile"))

    def test_update_branding_theme(self):
        """Enterprise users can update theme configuration."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.post(
                reverse("core:configure_branding"),
                {
                    "default_theme": "checktick-dark",
                    "theme_preset_light": "nord",
                    "theme_preset_dark": "business",
                },
            )
            self.assertEqual(response.status_code, 302)

            # Verify branding was updated
            branding = SiteBranding.objects.get(pk=1)
            self.assertEqual(branding.default_theme, "checktick-dark")
            self.assertEqual(branding.theme_preset_light, "nord")
            self.assertEqual(branding.theme_preset_dark, "business")

    def test_update_branding_logo_url(self):
        """Enterprise users can set logo URLs."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.post(
                reverse("core:configure_branding"),
                {
                    "default_theme": "checktick-light",
                    "icon_url": "https://example.com/logo.png",
                    "icon_url_dark": "https://example.com/logo-dark.png",
                },
            )
            self.assertEqual(response.status_code, 302)

            branding = SiteBranding.objects.get(pk=1)
            self.assertEqual(branding.icon_url, "https://example.com/logo.png")
            self.assertEqual(branding.icon_url_dark, "https://example.com/logo-dark.png")

    def test_update_branding_fonts(self):
        """Enterprise users can configure custom fonts."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.post(
                reverse("core:configure_branding"),
                {
                    "default_theme": "checktick-light",
                    "font_heading": "'Roboto', sans-serif",
                    "font_body": "'Open Sans', sans-serif",
                    "font_css_url": "https://fonts.googleapis.com/css2?family=Roboto",
                },
            )
            self.assertEqual(response.status_code, 302)

            branding = SiteBranding.objects.get(pk=1)
            self.assertEqual(branding.font_heading, "'Roboto', sans-serif")
            self.assertEqual(branding.font_body, "'Open Sans', sans-serif")
            self.assertEqual(
                branding.font_css_url,
                "https://fonts.googleapis.com/css2?family=Roboto",
            )

    def test_branding_singleton_created(self):
        """SiteBranding singleton is created on first access."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        # Ensure no branding exists
        SiteBranding.objects.all().delete()

        with override_settings(SELF_HOSTED=False):
            response = self.client.get(reverse("core:configure_branding"))
            self.assertEqual(response.status_code, 200)

            # Verify singleton was created
            self.assertEqual(SiteBranding.objects.count(), 1)
            branding = SiteBranding.objects.get(pk=1)
            self.assertEqual(branding.default_theme, "checktick-light")

    def test_branding_link_shown_for_enterprise(self):
        """Branding link is shown on profile page for Enterprise users."""
        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.get(reverse("core:profile"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Configure Branding")
            self.assertContains(response, "Site Branding")

    def test_branding_link_not_shown_for_free_user(self):
        """Branding link is NOT shown on profile page for FREE users."""
        self.client.login(username="freeuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.get(reverse("core:profile"))
            self.assertEqual(response.status_code, 200)
            # Should not contain branding section
            self.assertNotContains(response, "Configure Branding")

    def test_branding_link_shown_for_superuser_self_hosted(self):
        """Branding link is shown for superusers in self-hosted mode."""
        self.client.login(username="admin", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=True):
            response = self.client.get(reverse("core:profile"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Configure Branding")
            self.assertContains(response, "Site Branding")

    def test_form_displays_current_branding(self):
        """Branding form displays current configuration."""
        # Set up existing branding
        branding = SiteBranding.objects.create(
            pk=1,
            default_theme="checktick-dark",
            theme_preset_light="nord",
            theme_preset_dark="business",
            icon_url="https://example.com/logo.png",
        )

        self.client.login(username="entuser", password=TEST_PASSWORD)

        with override_settings(SELF_HOSTED=False):
            response = self.client.get(reverse("core:configure_branding"))
            self.assertEqual(response.status_code, 200)

            # Verify form is populated with current values
            self.assertContains(response, 'value="checktick-dark"')
            self.assertContains(response, 'value="nord"')
            self.assertContains(response, 'value="business"')
            self.assertContains(response, "https://example.com/logo.png")
