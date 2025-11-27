from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import SiteBranding, UserEmailPreferences, UserLanguagePreference

User = get_user_model()


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required")
        if User.objects.filter(email__iexact=email).exists():
            from django.urls import reverse
            from django.utils.safestring import mark_safe

            login_url = reverse("login")
            raise forms.ValidationError(
                mark_safe(
                    f"An account with this email already exists. "
                    f'<a href="{login_url}" class="link link-primary font-medium">Sign in instead</a> '
                    f"or use a different email address."
                )
            )
        return email

    def save(self, commit=True):
        email = self.cleaned_data["email"].strip().lower()
        user = User()
        user.username = email
        user.email = email
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEmailPreferencesForm(forms.ModelForm):
    """Form for managing user email notification preferences."""

    class Meta:
        model = UserEmailPreferences
        fields = [
            "send_welcome_email",
            "send_password_change_email",
            "send_survey_created_email",
            "send_survey_deleted_email",
            "send_survey_published_email",
            "send_team_invitation_email",
            "send_survey_invitation_email",
            "notify_on_error",
            "notify_on_critical",
        ]
        widgets = {
            "send_welcome_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_password_change_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_survey_created_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_survey_deleted_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_survey_published_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_team_invitation_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "send_survey_invitation_email": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "notify_on_error": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
            "notify_on_critical": forms.CheckboxInput(
                attrs={"class": "checkbox checkbox-primary"}
            ),
        }


class UserLanguagePreferenceForm(forms.ModelForm):
    """Form for managing user language preference."""

    class Meta:
        model = UserLanguagePreference
        fields = ["language"]
        widgets = {
            "language": forms.Select(
                attrs={"class": "select select-bordered w-full"},
                choices=settings.LANGUAGES,
            ),
        }
        labels = {
            "language": "Preferred Language",
        }


## Removed BrandedPasswordResetForm in favor of Django's default behavior for
## PasswordResetView with html_email_template_name.
## No custom password reset form required; use Django defaults.


class BrandingConfigForm(forms.ModelForm):
    """Form for configuring site branding.

    Available to Enterprise tier users (hosted) or superusers (self-hosted).
    Allows customization of themes, logos, and typography.
    """

    class Meta:
        model = SiteBranding
        fields = [
            "default_theme",
            "theme_preset_light",
            "theme_preset_dark",
            "icon_file",
            "icon_file_dark",
            "icon_url",
            "icon_url_dark",
            "font_heading",
            "font_body",
            "font_css_url",
        ]
        widgets = {
            "default_theme": forms.Select(
                attrs={
                    "class": "select select-bordered w-full",
                }
            ),
            "theme_preset_light": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "e.g., nord, cupcake, light",
                }
            ),
            "theme_preset_dark": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "e.g., business, dark, synthwave",
                }
            ),
            "icon_url": forms.URLInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "https://example.com/logo.png",
                }
            ),
            "icon_url_dark": forms.URLInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "https://example.com/logo-dark.png",
                }
            ),
            "font_heading": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "e.g., 'Roboto', sans-serif",
                }
            ),
            "font_body": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "e.g., 'Open Sans', sans-serif",
                }
            ),
            "font_css_url": forms.URLInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "https://fonts.googleapis.com/css2?family=...",
                }
            ),
            "icon_file": forms.FileInput(
                attrs={
                    "class": "file-input file-input-bordered w-full",
                    "accept": "image/*",
                }
            ),
            "icon_file_dark": forms.FileInput(
                attrs={
                    "class": "file-input file-input-bordered w-full",
                    "accept": "image/*",
                }
            ),
        }
        help_texts = {
            "default_theme": "Select the default theme for the site",
            "theme_preset_light": "DaisyUI preset theme for light mode",
            "theme_preset_dark": "DaisyUI preset theme for dark mode",
            "icon_url": "Alternative to file upload - provide direct URL",
            "icon_url_dark": "Alternative to file upload for dark mode",
            "font_css_url": "Google Fonts URL or custom font stylesheet",
        }
