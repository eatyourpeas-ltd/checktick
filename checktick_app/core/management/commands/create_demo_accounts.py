"""
Management command to create demo accounts with different tiers for testing.

Creates users with activated subscriptions (bypassing billing) but still requiring 2FA.
Use this to quickly set up accounts for demos without going through the payment flow.

Usage:
    python manage.py create_demo_accounts

Demo accounts created:
    - demo-pro@example.com (PRO tier)
    - demo-team-small@example.com (TEAM_SMALL tier with team)
    - demo-team-medium@example.com (TEAM_MEDIUM tier with team)
    - demo-org@example.com (ORGANIZATION tier with organization)
    - demo-enterprise@example.com (ENTERPRISE tier with organization)

All users have password: demo123!pass
All users will need to set up 2FA on first login
"""

from datetime import timedelta
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from checktick_app.core.models import UserProfile

logger = logging.getLogger(__name__)

User = get_user_model()

DEMO_PASSWORD = "demo123!pass"

# Demo account configurations
DEMO_ACCOUNTS = [
    {
        "email": "demo-free@example.com",
        "tier": UserProfile.AccountTier.FREE,
        "description": "Free tier (no billing)",
        "create_team": False,
        "create_org": False,
    },
    {
        "email": "demo-pro@example.com",
        "tier": UserProfile.AccountTier.PRO,
        "description": "Individual Pro account with encryption",
        "create_team": False,
        "create_org": False,
    },
    {
        "email": "demo-team-small@example.com",
        "tier": UserProfile.AccountTier.TEAM_SMALL,
        "description": "Team Small (5 members)",
        "create_team": True,
        "team_size": "small",
        "create_org": False,
    },
    {
        "email": "demo-team-medium@example.com",
        "tier": UserProfile.AccountTier.TEAM_MEDIUM,
        "description": "Team Medium (10 members)",
        "create_team": True,
        "team_size": "medium",
        "create_org": False,
    },
    {
        "email": "demo-team-large@example.com",
        "tier": UserProfile.AccountTier.TEAM_LARGE,
        "description": "Team Large (20 members)",
        "create_team": True,
        "team_size": "large",
        "create_org": False,
    },
    {
        "email": "demo-org@example.com",
        "tier": UserProfile.AccountTier.ORGANIZATION,
        "description": "Organization with webhooks and unlimited collaboration",
        "create_team": False,
        "create_org": True,
        "org_billing_type": "per_seat",
    },
    {
        "email": "demo-enterprise@example.com",
        "tier": UserProfile.AccountTier.ENTERPRISE,
        "description": "Enterprise with custom branding and SSO",
        "create_team": False,
        "create_org": True,
        "org_billing_type": "flat_rate",
    },
]


class Command(BaseCommand):
    help = "Create demo accounts with different tiers (bypasses billing, requires 2FA)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation even if DEBUG is False (NOT RECOMMENDED)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo accounts and recreate them",
        )
        parser.add_argument(
            "--tier",
            type=str,
            choices=[
                "free",
                "pro",
                "team_small",
                "team_medium",
                "team_large",
                "organization",
                "enterprise",
            ],
            help="Create only accounts with this specific tier",
        )

    def handle(self, *args, **options):
        # Check environment - NEVER allow in production
        import os

        environment = os.environ.get("ENVIRONMENT", "development").lower()

        # Block production explicitly
        if environment == "production" and not options["force"]:
            raise CommandError(
                "SECURITY: This command is disabled in production environments. "
                "Demo accounts with known passwords are a critical security risk. "
                "If you absolutely must use this (NOT RECOMMENDED), use --force."
            )

        # Also check DEBUG mode for additional safety
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "This command only runs in DEBUG mode. "
                "Use --force to override (NOT RECOMMENDED for production)."
            )

        if options["force"] and (not settings.DEBUG or environment == "production"):
            self.stdout.write(self.style.ERROR("⚠️  CRITICAL SECURITY WARNING ⚠️"))
            self.stdout.write(
                self.style.WARNING(
                    "Creating demo accounts with known passwords in production. "
                    "This is a CRITICAL security risk! "
                    "Anyone can login with demo123!pass and access paid features."
                )
            )

        # Import models here to avoid circular imports
        from checktick_app.surveys.models import (
            Organization,
            OrganizationMembership,
            Team,
            TeamMembership,
        )

        created_count = 0
        updated_count = 0
        tier_filter = options.get("tier")

        with transaction.atomic():
            # Delete existing demo accounts if --reset
            if options["reset"]:
                deleted_users = User.objects.filter(
                    email__startswith="demo-", email__endswith="@example.com"
                )
                # Delete related teams and orgs first
                Team.objects.filter(owner__in=deleted_users).delete()
                Organization.objects.filter(owner__in=deleted_users).delete()
                deleted_count = deleted_users.delete()[0]
                if deleted_count:
                    self.stdout.write(f"Deleted {deleted_count} existing demo accounts")

            # Filter accounts if specific tier requested
            accounts_to_create = DEMO_ACCOUNTS
            if tier_filter:
                accounts_to_create = [
                    acc for acc in DEMO_ACCOUNTS if acc["tier"] == tier_filter
                ]

            for account_config in accounts_to_create:
                email = account_config["email"]
                tier = account_config["tier"]
                description = account_config["description"]

                # Create or get user
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email.split("@")[0],  # username from email prefix
                    },
                )

                if created:
                    # Safe: Demo accounts intentionally use known weak password for testing.
                    # Protected by ENVIRONMENT check - blocked in production.
                    user.set_password(DEMO_PASSWORD)  # nosemgrep
                    user.save()
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created user: {email} ({description})")
                    )
                else:
                    updated_count += 1
                    self.stdout.write(f"User exists: {email}")

                # Get or create profile
                profile, _ = UserProfile.objects.get_or_create(user=user)

                # Set up subscription details (bypass billing)
                profile.account_tier = tier
                profile.payment_provider = "demo"
                profile.payment_customer_id = f"demo-cust-{user.id}"
                profile.tier_changed_at = timezone.now()

                # Set subscription details for paid tiers
                if tier != UserProfile.AccountTier.FREE:
                    profile.payment_subscription_id = f"demo-sub-{user.id}"
                    profile.subscription_status = UserProfile.SubscriptionStatus.ACTIVE
                    # Set subscription end date 1 year from now
                    profile.subscription_current_period_end = (
                        timezone.now() + timedelta(days=365)
                    )
                else:
                    profile.subscription_status = UserProfile.SubscriptionStatus.NONE

                # Enable custom branding for Enterprise
                if tier == UserProfile.AccountTier.ENTERPRISE:
                    profile.custom_branding_enabled = True

                profile.save()

                # Create team if configured
                if account_config.get("create_team"):
                    team_size = account_config.get("team_size", "small")
                    team_name = f"{user.username}'s Team"

                    # Check if team already exists
                    team, team_created = Team.objects.get_or_create(
                        owner=user,
                        defaults={
                            "name": team_name,
                            "size": team_size,
                            "subscription_id": f"demo-team-sub-{user.id}",
                        },
                    )

                    if team_created:
                        # Create admin membership for owner
                        TeamMembership.objects.get_or_create(
                            team=team,
                            user=user,
                            defaults={"role": TeamMembership.Role.ADMIN},
                        )
                        self.stdout.write(f"  ✓ Created team: {team_name}")
                    else:
                        self.stdout.write(f"  Team exists: {team_name}")

                # Create organization if configured
                if account_config.get("create_org"):
                    org_name = f"{user.username}'s Organization"
                    billing_type = account_config.get(
                        "org_billing_type", Organization.BillingType.PER_SEAT
                    )

                    # Check if org already exists
                    org, org_created = Organization.objects.get_or_create(
                        owner=user,
                        defaults={
                            "name": org_name,
                            "billing_type": billing_type,
                            "subscription_status": Organization.SubscriptionStatus.ACTIVE,
                            "payment_customer_id": f"demo-org-cust-{user.id}",
                            "payment_subscription_id": f"demo-org-sub-{user.id}",
                            "price_per_seat": (
                                500 if billing_type == "per_seat" else None
                            ),  # £5.00
                            "flat_rate_price": (
                                10000 if billing_type == "flat_rate" else None
                            ),  # £100.00
                        },
                    )

                    if org_created:
                        # Create admin membership for owner
                        OrganizationMembership.objects.get_or_create(
                            organization=org,
                            user=user,
                            defaults={"role": OrganizationMembership.Role.ADMIN},
                        )
                        self.stdout.write(f"  ✓ Created organization: {org_name}")
                    else:
                        self.stdout.write(f"  Organization exists: {org_name}")

        # Print summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDemo accounts ready! Created: {created_count}, Updated: {updated_count}"
            )
        )
        self.stdout.write("\nAccount credentials:")
        self.stdout.write(f"  Password (all accounts): {DEMO_PASSWORD}")
        self.stdout.write("\nNOTE: All accounts require 2FA setup on first login")
        self.stdout.write("\nDemo accounts created:")

        for account in accounts_to_create:
            self.stdout.write(f"  • {account['email']}: {account['description']}")

        self.stdout.write("\nTo log in:")
        self.stdout.write("  1. Visit the login page")
        self.stdout.write("  2. Use the email and password above")
        self.stdout.write("  3. Set up 2FA with your authenticator app")
        self.stdout.write("  4. Start using the account!")
        self.stdout.write("\n" + "=" * 70)
