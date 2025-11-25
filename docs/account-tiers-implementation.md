---
title: Account Tiers Implementation
category: api
priority: 100
---

# Account Tiers Implementation Plan

**Status**: ✅ Implemented

**Developer Note**: This document describes the design and implementation of the account tiers system. For user-facing documentation, see [Account Types & Organizations](getting-started-account-types.md).

## Overview

This document outlines the implementation of a four-tier account system for CheckTick, designed to work seamlessly for both self-hosted deployments and hosted SaaS offerings.

## Account Tiers

### 1. Individual (Free)
Entry-level account for personal use with basic features and survey limits.

### 2. Individual Pro
Paid tier for power users needing unlimited surveys and basic collaboration.

### 3. Organization
Team collaboration with full role-based access control and organization-level features.

### 4. Enterprise
Advanced features including custom branding, sub-organizations, and white-labeling.

---

## Feature Matrix

| Feature | Individual (Free) | Individual Pro | Organization | Enterprise |
|---------|------------------|----------------|--------------|------------|
| **Survey Creation** |
| Maximum Surveys | 3 | Unlimited | Unlimited | Unlimited |
| Drag & Drop Builder | ✅ | ✅ | ✅ | ✅ |
| Text Entry for Surveys | ✅ | ✅ | ✅ | ✅ |
| Survey Templates | ✅ | ✅ | ✅ | ✅ |
| Conditional Logic/Branching | ✅ | ✅ | ✅ | ✅ |
| Question Groups | ✅ | ✅ | ✅ | ✅ |
| Repeating Groups | ✅ | ✅ | ✅ | ✅ |
| **AI Features** |
| AI Survey Assistant | ✅ | ✅ | ✅ | ✅ |
| AI-Generated Survey Translations | ✅ | ✅ | ✅ | ✅ |
| **Internationalization** |
| Multi-language Interface (i18n) | ✅ | ✅ | ✅ | ✅ |
| Survey Translation Support | ✅ | ✅ | ✅ | ✅ |
| All Supported Languages | ✅ | ✅ | ✅ | ✅ |
| **Collaboration** |
| Survey Ownership | Single Owner | Single Owner | Team-based | Team-based |
| Add Collaborators | ❌ | ✅ (Editors only) | ✅ (Full roles) | ✅ (Full roles) |
| Survey Membership Roles | - | EDITOR | CREATOR, EDITOR, VIEWER | CREATOR, EDITOR, VIEWER |
| Organization Membership | ❌ | ❌ | ✅ | ✅ |
| Organization Roles | - | - | ADMIN, CREATOR, VIEWER | ADMIN, CREATOR, VIEWER |
| Sub-organizations/Departments | ❌ | ❌ | ❌ | ✅ |
| **Sharing & Publishing** |
| Question Group Sharing | ✅ | ✅ | ✅ | ✅ |
| Published Question Groups | ✅ | ✅ | ✅ | ✅ |
| Dataset Sharing | ✅ | ✅ | ✅ | ✅ |
| Published Datasets | ✅ | ✅ | ✅ | ✅ |
| Import Shared Resources | ✅ | ✅ | ✅ | ✅ |
| **Security & Encryption** |
| End-to-End Encryption | ✅ | ✅ | ✅ | ✅ |
| Personal Passphrase Encryption | ✅ | ✅ | ✅ | ✅ |
| Organization Key Management | ❌ | ❌ | ✅ | ✅ |
| Shamir Secret Sharing (Recovery) | ✅ | ✅ | ✅ | ✅ |
| Audit Logging | ✅ | ✅ | ✅ | ✅ |
| Data Governance Features | ✅ | ✅ | ✅ | ✅ |
| Legal Hold Support | ✅ | ✅ | ✅ | ✅ |
| Data Retention Policies | ✅ | ✅ | ✅ | ✅ |
| **Authentication** |
| Username/Password | ✅ | ✅ | ✅ | ✅ |
| SSO (Google/Azure) | ✅ | ✅ | ✅ | ✅ |
| SAML/Enterprise SSO | ❌ | ❌ | ❌ | ✅ (optional) |
| **Data & Analytics** |
| Response Collection | Unlimited | Unlimited | Unlimited | Unlimited |
| Data Export (CSV/JSON/Excel) | ✅ | ✅ | ✅ | ✅ |
| Advanced Analytics Dashboard | ❌ | ❌ | ❌ | ✅ |
| Organization-wide Reports | ❌ | ❌ | ✅ | ✅ |
| **API Access** |
| REST API Access | ✅ | ✅ | ✅ | ✅ |
| API Rate Limits | Standard | Standard | Standard | 10x Increased |
| API Documentation | ✅ | ✅ | ✅ | ✅ |
| **Branding & Customization** |
| Site Theme Selection | View Only | View Only | View Only | ✅ Configure |
| Custom Logo Upload | ❌ | ❌ | ❌ | ✅ |
| Custom Brand Name | ❌ | ❌ | ❌ | ✅ |
| White-labeling | ❌ | ❌ | ❌ | ✅ |
| Organization Themes/Colors | ❌ | ❌ | ✅ | ✅ |
| Survey-level Styling | ✅ | ✅ | ✅ | ✅ |
| **Support** |
| Community Support | ✅ | ✅ | ✅ | ✅ |
| Email Support | Standard | Standard | Standard | Priority |
| SLA Guarantee | ❌ | ❌ | ❌ | ✅ |
| Dedicated Onboarding | ❌ | ❌ | ❌ | ✅ |
| Training Sessions | ❌ | ❌ | ❌ | ✅ |

---

## Self-Hosted Deployments

**Key Principle**: Self-hosted instances get **Enterprise tier features** without payment requirements.

### Configuration
```bash
# .env file
SELF_HOSTED=true
```

When `SELF_HOSTED=true`:
- All users automatically get Enterprise tier capabilities
- No payment integration required
- No survey limits enforced
- Full branding customization available
- All collaboration features enabled
- No tier restrictions applied

### Branding Management for Self-Hosted
Self-hosted administrators can configure branding via:
1. **UI Dashboard** (recommended): Navigate to `/admin/branding/` (requires superuser)
2. **Management Command**: `python manage.py configure_branding`
3. **Direct Database**: Edit `SiteBranding` model (not recommended)

---

## Hosted SaaS Deployments

### Configuration
```bash
# .env file
SELF_HOSTED=false
PAYMENT_PROVIDER=ryft  # or other provider
PAYMENT_API_KEY=your_api_key_here
```

### Tier Enforcement
When `SELF_HOSTED=false`:
- Survey limits enforced for FREE tier (3 surveys max)
- Collaboration features gated by tier
- Branding features restricted to Enterprise tier
- Payment integration active
- Subscription status checked

---

## Technical Implementation

### 1. UserProfile Model

**Location**: `checktick_app/core/models.py`

```python
class UserProfile(models.Model):
    """
    User account tier and subscription tracking.

    Handles both self-hosted (free Enterprise features) and hosted SaaS
    (payment-gated tiers) deployments.
    """

    class AccountTier(models.TextChoices):
        FREE = 'free', 'Individual (Free)'
        PRO = 'pro', 'Individual Pro'
        ORGANIZATION = 'organization', 'Organization'
        ENTERPRISE = 'enterprise', 'Enterprise'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    account_tier = models.CharField(
        max_length=20,
        choices=AccountTier.choices,
        default=AccountTier.FREE
    )

    # Generic payment tracking (provider-agnostic)
    payment_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment provider name (e.g., 'ryft', 'stripe')"
    )
    payment_customer_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Customer ID in payment provider system"
    )
    payment_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Subscription ID in payment provider system"
    )
    subscription_status = models.CharField(
        max_length=20,
        default='inactive',
        help_text="active, inactive, cancelled, past_due, etc."
    )
    subscription_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When current subscription period ends"
    )

    # Enterprise branding (only for ENTERPRISE tier)
    custom_brand_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom brand name to replace 'CheckTick'"
    )
    custom_logo_url = models.URLField(
        blank=True,
        help_text="URL to custom logo image"
    )
    custom_logo_file = models.FileField(
        upload_to='enterprise_branding/',
        blank=True,
        null=True,
        help_text="Uploaded custom logo file"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} - {self.get_account_tier_display()}"

    def get_effective_tier(self):
        """
        Returns the effective tier, accounting for self-hosted instances.

        Self-hosted instances get Enterprise features without payment.
        """
        from django.conf import settings
        if getattr(settings, 'SELF_HOSTED', False):
            return self.AccountTier.ENTERPRISE
        return self.account_tier

    def can_create_survey(self):
        """
        Check if user can create another survey based on their tier.

        Returns:
            bool: True if user can create a survey, False otherwise
        """
        from django.conf import settings
        from checktick_app.surveys.models import Survey

        if getattr(settings, 'SELF_HOSTED', False):
            return True  # No limits for self-hosted

        tier = self.account_tier
        if tier == self.AccountTier.FREE:
            survey_count = Survey.objects.filter(owner=self.user).count()
            return survey_count < 3

        # PRO, ORGANIZATION, ENTERPRISE have unlimited surveys
        return True

    def can_add_collaborators(self):
        """
        Check if user can add collaborators to their surveys.

        Returns:
            bool: True if user can add collaborators
        """
        from django.conf import settings

        if getattr(settings, 'SELF_HOSTED', False):
            return True

        tier = self.account_tier
        return tier in [
            self.AccountTier.PRO,
            self.AccountTier.ORGANIZATION,
            self.AccountTier.ENTERPRISE
        ]

    def can_add_viewers(self):
        """
        Check if user can add VIEWER role collaborators.

        Only ORGANIZATION and ENTERPRISE tiers support the VIEWER role.
        PRO tier can only add EDITORs.

        Returns:
            bool: True if user can add viewers
        """
        from django.conf import settings

        if getattr(settings, 'SELF_HOSTED', False):
            return True

        tier = self.account_tier
        return tier in [
            self.AccountTier.ORGANIZATION,
            self.AccountTier.ENTERPRISE
        ]

    def can_customize_branding(self):
        """
        Check if user can customize site branding.

        Available to:
        - Enterprise tier in hosted mode
        - Any superuser in self-hosted mode

        Returns:
            bool: True if user can customize branding
        """
        from django.conf import settings

        if getattr(settings, 'SELF_HOSTED', False):
            return self.user.is_superuser

        return self.account_tier == self.AccountTier.ENTERPRISE

    def get_branding_settings(self):
        """
        Get the branding settings for this user.

        Returns:
            dict or None: Branding configuration or None if not available
        """
        if not self.can_customize_branding():
            return None

        logo_url = self.custom_logo_url
        if not logo_url and self.custom_logo_file:
            logo_url = self.custom_logo_file.url

        return {
            'brand_name': self.custom_brand_name or 'CheckTick',
            'logo_url': logo_url,
        }

    def get_api_rate_limit(self):
        """
        Get API rate limit multiplier for this user's tier.

        Returns:
            int: Rate limit multiplier (1 for standard, 10 for enterprise)
        """
        from django.conf import settings

        if getattr(settings, 'SELF_HOSTED', False):
            return 10  # Enterprise limits for self-hosted

        if self.account_tier == self.AccountTier.ENTERPRISE:
            return 10

        return 1  # Standard rate limits
```

### 2. Database Migration

**Location**: `checktick_app/core/migrations/000X_add_user_profile.py`

```python
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_user_profiles(apps, schema_editor):
    """Create UserProfile for all existing users with FREE tier."""
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model('core', 'UserProfile')

    for user in User.objects.all():
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'account_tier': 'free'}
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_tier', models.CharField(
                    choices=[
                        ('free', 'Individual (Free)'),
                        ('pro', 'Individual Pro'),
                        ('organization', 'Organization'),
                        ('enterprise', 'Enterprise')
                    ],
                    default='free',
                    max_length=20
                )),
                ('payment_provider', models.CharField(blank=True, max_length=50)),
                ('payment_customer_id', models.CharField(blank=True, max_length=255)),
                ('payment_subscription_id', models.CharField(blank=True, max_length=255)),
                ('subscription_status', models.CharField(default='inactive', max_length=20)),
                ('subscription_period_end', models.DateTimeField(blank=True, null=True)),
                ('custom_brand_name', models.CharField(blank=True, max_length=255)),
                ('custom_logo_url', models.URLField(blank=True)),
                ('custom_logo_file', models.FileField(blank=True, null=True, upload_to='enterprise_branding/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'User Profile',
                'verbose_name_plural': 'User Profiles',
            },
        ),
        migrations.RunPython(create_user_profiles, reverse_code=migrations.RunPython.noop),
    ]
```

### 3. Signal Handler for Auto-Profile Creation

**Location**: `checktick_app/core/signals.py`

```python
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create UserProfile when User is created."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()
```

**Register signals in**: `checktick_app/core/apps.py`

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'checktick_app.core'

    def ready(self):
        import checktick_app.core.signals  # noqa
```

### 4. Management Command: configure_branding

**Location**: `checktick_app/core/management/commands/configure_branding.py`

```python
from django.core.management.base import BaseCommand
from django.core.files import File

from checktick_app.core.models import SiteBranding


class Command(BaseCommand):
    help = 'Configure site branding (logo, theme, colors)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--theme-light',
            type=str,
            help='DaisyUI theme preset for light mode (e.g., nord, cupcake, light)'
        )
        parser.add_argument(
            '--theme-dark',
            type=str,
            help='DaisyUI theme preset for dark mode (e.g., business, dark, synthwave)'
        )
        parser.add_argument(
            '--logo',
            type=str,
            help='Path to logo file'
        )
        parser.add_argument(
            '--logo-dark',
            type=str,
            help='Path to dark mode logo file'
        )
        parser.add_argument(
            '--brand-name',
            type=str,
            help='Custom brand name (stored in SiteBranding for display purposes)'
        )
        parser.add_argument(
            '--default-theme',
            type=str,
            choices=['checktick-light', 'checktick-dark'],
            help='Default theme selection'
        )

    def handle(self, *args, **options):
        branding, created = SiteBranding.objects.get_or_create(pk=1)

        if created:
            self.stdout.write(self.style.SUCCESS('Created new SiteBranding configuration'))

        updated = False

        if options['theme_light']:
            branding.theme_preset_light = options['theme_light']
            updated = True
            self.stdout.write(f"Set light theme to: {options['theme_light']}")

        if options['theme_dark']:
            branding.theme_preset_dark = options['theme_dark']
            updated = True
            self.stdout.write(f"Set dark theme to: {options['theme_dark']}")

        if options['logo']:
            with open(options['logo'], 'rb') as f:
                branding.icon_file.save(options['logo'].split('/')[-1], File(f), save=False)
            updated = True
            self.stdout.write(f"Uploaded logo: {options['logo']}")

        if options['logo_dark']:
            with open(options['logo_dark'], 'rb') as f:
                branding.icon_file_dark.save(options['logo_dark'].split('/')[-1], File(f), save=False)
            updated = True
            self.stdout.write(f"Uploaded dark logo: {options['logo_dark']}")

        if options['default_theme']:
            branding.default_theme = options['default_theme']
            updated = True
            self.stdout.write(f"Set default theme to: {options['default_theme']}")

        if updated:
            branding.save()
            self.stdout.write(self.style.SUCCESS('✓ Branding configuration updated successfully'))
        else:
            self.stdout.write(self.style.WARNING('No changes specified'))
            self.stdout.write('\nCurrent configuration:')
            self.stdout.write(f"  Default theme: {branding.default_theme}")
            self.stdout.write(f"  Light theme preset: {branding.theme_preset_light or '(not set)'}")
            self.stdout.write(f"  Dark theme preset: {branding.theme_preset_dark or '(not set)'}")
            self.stdout.write(f"  Logo: {branding.icon_file.url if branding.icon_file else '(not set)'}")
```

### 5. Branding Configuration View

**Location**: `checktick_app/core/views.py` (new or existing)

```python
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .models import SiteBranding
from .forms import BrandingConfigForm


def can_configure_branding(user):
    """Check if user can access branding configuration."""
    if not user.is_authenticated:
        return False

    # Self-hosted: superusers can configure
    from django.conf import settings
    if getattr(settings, 'SELF_HOSTED', False):
        return user.is_superuser

    # Hosted: Enterprise tier users can configure
    if hasattr(user, 'profile'):
        return user.profile.account_tier == 'enterprise'

    return False


@login_required
@user_passes_test(can_configure_branding)
@require_http_methods(["GET", "POST"])
def configure_branding(request):
    """View to configure site branding."""
    branding, created = SiteBranding.objects.get_or_create(pk=1)

    if request.method == 'POST':
        form = BrandingConfigForm(request.POST, request.FILES, instance=branding)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branding configuration updated successfully!')
            return redirect('core:configure_branding')
    else:
        form = BrandingConfigForm(instance=branding)

    return render(request, 'core/configure_branding.html', {
        'form': form,
        'branding': branding,
    })
```

**Form Location**: `checktick_app/core/forms.py`

```python
from django import forms
from .models import SiteBranding


class BrandingConfigForm(forms.ModelForm):
    """Form for configuring site branding."""

    class Meta:
        model = SiteBranding
        fields = [
            'default_theme',
            'theme_preset_light',
            'theme_preset_dark',
            'icon_file',
            'icon_file_dark',
            'icon_url',
            'icon_url_dark',
            'font_heading',
            'font_body',
            'font_css_url',
        ]
        widgets = {
            'theme_preset_light': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., nord, cupcake, light'
            }),
            'theme_preset_dark': forms.TextInput(attrs={
                'class': 'input input-bordered w-full',
                'placeholder': 'e.g., business, dark, synthwave'
            }),
        }
```

### 6. Permission Checks Integration

Update existing permission functions to check tier restrictions:

**Location**: `checktick_app/surveys/permissions.py`

```python
def can_manage_survey_users(user, survey):
    """
    Check if user can manage survey collaborators.

    Enhanced to check account tier restrictions:
    - Individual accounts (FREE tier): Cannot manage users
    - Individual Pro: Can add editors only
    - Organization/Enterprise: Full user management
    """
    if not user.is_authenticated:
        return False

    # Check tier restrictions
    if hasattr(user, 'profile'):
        if not user.profile.can_add_collaborators():
            return False

    # Survey without organization (individual survey)
    if not survey.organization:
        # Individual surveys: only owner can manage, and only if tier allows
        if survey.owner == user:
            return hasattr(user, 'profile') and user.profile.can_add_collaborators()
        return False

    # Organization survey: existing logic
    org = survey.organization
    membership = OrganizationMembership.objects.filter(
        user=user, organization=org
    ).first()

    if not membership:
        return False

    return membership.role in [
        OrganizationMembership.Role.ADMIN,
        OrganizationMembership.Role.CREATOR
    ]
```

**Location**: `checktick_app/surveys/views.py` (survey creation)

```python
@login_required
@require_http_methods(["GET", "POST"])
def create_survey(request):
    """Create a new survey with tier limit checks."""

    # Check if user can create another survey
    if hasattr(request.user, 'profile'):
        if not request.user.profile.can_create_survey():
            messages.error(
                request,
                'You have reached your survey limit. Upgrade to Pro for unlimited surveys.'
            )
            return redirect('surveys:list')

    # ... existing survey creation logic
```

### 7. Settings Configuration

**Location**: `checktick_app/settings.py`

```python
import os

# Self-hosting configuration
SELF_HOSTED = os.environ.get('SELF_HOSTED', 'false').lower() == 'true'

# Payment provider configuration (only for hosted SaaS)
PAYMENT_PROVIDER = os.environ.get('PAYMENT_PROVIDER', '')  # 'ryft', etc.
PAYMENT_API_KEY = os.environ.get('PAYMENT_API_KEY', '')
PAYMENT_WEBHOOK_SECRET = os.environ.get('PAYMENT_WEBHOOK_SECRET', '')

# Default tier for new users (only applicable when not self-hosted)
DEFAULT_ACCOUNT_TIER = 'free'
```

### 8. Admin Interface

**Location**: `checktick_app/core/admin.py`

```python
from django.contrib import admin
from .models import SiteBranding, UserProfile


@admin.register(SiteBranding)
class SiteBrandingAdmin(admin.ModelAdmin):
    list_display = ['default_theme', 'theme_preset_light', 'theme_preset_dark', 'updated_at']
    fieldsets = (
        ('Theme Configuration', {
            'fields': ('default_theme', 'theme_preset_light', 'theme_preset_dark')
        }),
        ('Logo/Icon', {
            'fields': ('icon_file', 'icon_url', 'icon_file_dark', 'icon_url_dark')
        }),
        ('Typography', {
            'fields': ('font_heading', 'font_body', 'font_css_url')
        }),
        ('Custom CSS', {
            'fields': ('theme_light_css', 'theme_dark_css'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_tier', 'subscription_status', 'payment_provider', 'created_at']
    list_filter = ['account_tier', 'subscription_status', 'payment_provider']
    search_fields = ['user__username', 'user__email', 'payment_customer_id']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'account_tier')
        }),
        ('Subscription', {
            'fields': ('payment_provider', 'payment_customer_id', 'payment_subscription_id',
                      'subscription_status', 'subscription_period_end')
        }),
        ('Enterprise Branding', {
            'fields': ('custom_brand_name', 'custom_logo_file', 'custom_logo_url'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
```

---

## URL Configuration

**Location**: `checktick_app/core/urls.py`

```python
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # ... existing URLs
    path('branding/', views.configure_branding, name='configure_branding'),
]
```

---

## Templates

### Branding Configuration Template

**Location**: `checktick_app/templates/core/configure_branding.html`

```django
{% extends 'base.html' %}
{% load i18n %}

{% block title %}Configure Branding{% endblock %}

{% block content %}
<div class="container mx-auto px-4 py-8 max-w-4xl">
  <h1 class="text-3xl font-bold mb-6">Site Branding Configuration</h1>

  <div class="alert alert-info mb-6">
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-current shrink-0 w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
    <span>Customize your CheckTick instance branding. Changes will apply site-wide.</span>
  </div>

  <form method="post" enctype="multipart/form-data" class="space-y-6">
    {% csrf_token %}

    <div class="card bg-base-200">
      <div class="card-body">
        <h2 class="card-title">Theme Settings</h2>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Default Theme</span>
          </label>
          {{ form.default_theme }}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Light Theme Preset</span>
            <span class="label-text-alt">DaisyUI preset (e.g., nord, cupcake)</span>
          </label>
          {{ form.theme_preset_light }}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Dark Theme Preset</span>
            <span class="label-text-alt">DaisyUI preset (e.g., business, dark)</span>
          </label>
          {{ form.theme_preset_dark }}
        </div>
      </div>
    </div>

    <div class="card bg-base-200">
      <div class="card-body">
        <h2 class="card-title">Logo & Icons</h2>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Logo File (Light Mode)</span>
          </label>
          {{ form.icon_file }}
          {% if branding.icon_file %}
            <div class="mt-2">
              <img src="{{ branding.icon_file.url }}" alt="Current logo" class="h-12">
            </div>
          {% endif %}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Logo File (Dark Mode)</span>
          </label>
          {{ form.icon_file_dark }}
          {% if branding.icon_file_dark %}
            <div class="mt-2">
              <img src="{{ branding.icon_file_dark.url }}" alt="Current dark logo" class="h-12">
            </div>
          {% endif %}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Logo URL (Light Mode)</span>
            <span class="label-text-alt">Alternative to file upload</span>
          </label>
          {{ form.icon_url }}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Logo URL (Dark Mode)</span>
          </label>
          {{ form.icon_url_dark }}
        </div>
      </div>
    </div>

    <div class="card bg-base-200">
      <div class="card-body">
        <h2 class="card-title">Typography</h2>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Heading Font</span>
          </label>
          {{ form.font_heading }}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Body Font</span>
          </label>
          {{ form.font_body }}
        </div>

        <div class="form-control">
          <label class="label">
            <span class="label-text">Font CSS URL</span>
            <span class="label-text-alt">Google Fonts or custom CSS</span>
          </label>
          {{ form.font_css_url }}
        </div>
      </div>
    </div>

    <div class="flex gap-4">
      <button type="submit" class="btn btn-primary">Save Changes</button>
      <a href="{% url 'surveys:list' %}" class="btn btn-ghost">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

---

## Testing Strategy

### Unit Tests

**Location**: `checktick_app/core/tests/test_user_profile.py`

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.conf import settings

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import Survey

User = get_user_model()


class UserProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_profile_created_automatically(self):
        """Test that UserProfile is created automatically with User."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.account_tier, UserProfile.AccountTier.FREE)

    def test_self_hosted_gets_enterprise_tier(self):
        """Test that self-hosted instances get Enterprise features."""
        with self.settings(SELF_HOSTED=True):
            effective_tier = self.user.profile.get_effective_tier()
            self.assertEqual(effective_tier, UserProfile.AccountTier.ENTERPRISE)

    def test_free_tier_survey_limit(self):
        """Test that FREE tier is limited to 3 surveys."""
        with self.settings(SELF_HOSTED=False):
            # Create 3 surveys
            for i in range(3):
                Survey.objects.create(
                    owner=self.user,
                    name=f'Survey {i}',
                    slug=f'survey-{i}'
                )

            # Should not be able to create 4th survey
            self.assertFalse(self.user.profile.can_create_survey())

    def test_pro_tier_unlimited_surveys(self):
        """Test that PRO tier has unlimited surveys."""
        self.user.profile.account_tier = UserProfile.AccountTier.PRO
        self.user.profile.save()

        with self.settings(SELF_HOSTED=False):
            # Create many surveys
            for i in range(10):
                Survey.objects.create(
                    owner=self.user,
                    name=f'Survey {i}',
                    slug=f'survey-{i}'
                )

            # Should still be able to create more
            self.assertTrue(self.user.profile.can_create_survey())

    def test_free_tier_no_collaborators(self):
        """Test that FREE tier cannot add collaborators."""
        with self.settings(SELF_HOSTED=False):
            self.assertFalse(self.user.profile.can_add_collaborators())

    def test_pro_tier_can_add_collaborators(self):
        """Test that PRO tier can add collaborators."""
        self.user.profile.account_tier = UserProfile.AccountTier.PRO
        self.user.profile.save()

        with self.settings(SELF_HOSTED=False):
            self.assertTrue(self.user.profile.can_add_collaborators())

    def test_pro_tier_cannot_add_viewers(self):
        """Test that PRO tier cannot add VIEWER role."""
        self.user.profile.account_tier = UserProfile.AccountTier.PRO
        self.user.profile.save()

        with self.settings(SELF_HOSTED=False):
            self.assertFalse(self.user.profile.can_add_viewers())

    def test_enterprise_branding_access(self):
        """Test that only Enterprise tier can customize branding."""
        with self.settings(SELF_HOSTED=False):
            # FREE tier cannot customize
            self.assertFalse(self.user.profile.can_customize_branding())

            # Enterprise can customize
            self.user.profile.account_tier = UserProfile.AccountTier.ENTERPRISE
            self.user.profile.save()
            self.assertTrue(self.user.profile.can_customize_branding())

    def test_self_hosted_superuser_can_brand(self):
        """Test that superusers in self-hosted can customize branding."""
        self.user.is_superuser = True
        self.user.save()

        with self.settings(SELF_HOSTED=True):
            self.assertTrue(self.user.profile.can_customize_branding())
```

---

## Migration Path

### For Existing Deployments

1. **Run migration** to create `UserProfile` table and profiles for existing users
2. **All existing users default to FREE tier**
3. **Self-hosted instances**: Set `SELF_HOSTED=true` in environment
4. **Hosted instances**: Manual upgrade of specific users to PRO/ORGANIZATION/ENTERPRISE as needed

### Commands to Run

```bash
# Generate migration
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Configure branding (self-hosted)
python manage.py configure_branding --theme-light=nord --theme-dark=business --logo=path/to/logo.png

# Or use Django admin at /admin/core/sitebranding/
```

---

## API Endpoints (Future)

For hosted SaaS, we'll need API endpoints for:

1. **Check tier status**: `GET /api/account/tier/`
2. **Upgrade tier**: `POST /api/account/upgrade/`
3. **Payment webhook**: `POST /api/webhooks/payment/`
4. **Usage stats**: `GET /api/account/usage/`

These will be implemented in a separate phase after the core tier system is in place.

---

## Documentation Updates Required

1. **Getting Started**: Update account types comparison
2. **Self-Hosting Guide**: Document `SELF_HOSTED` setting and branding configuration
3. **API Documentation**: Document tier-specific rate limits
4. **User Guide**: Explain tier features and upgrade paths
5. **Admin Guide**: Document branding configuration UI

---

## Summary

This implementation provides:

✅ **Flexible tier system** (FREE, PRO, ORGANIZATION, ENTERPRISE)
✅ **Self-hosted support** with full Enterprise features
✅ **Generic payment integration** (Ryft or others)
✅ **UI-based branding configuration** (no .env editing)
✅ **Management command** for CLI configuration
✅ **Automatic profile creation** for all users
✅ **Backward compatible** with existing deployments
✅ **Comprehensive feature matrix** with all current features
✅ **Security-first approach** (all tiers get encryption & audit logging)

The system is designed to be:
- **Self-hosting friendly**: No payment barriers, full features
- **SaaS ready**: Payment integration, tier enforcement
- **User-friendly**: UI configuration instead of environment variables
- **Healthcare compliant**: Security features available to all tiers
