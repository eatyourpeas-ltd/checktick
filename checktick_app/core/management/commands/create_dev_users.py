"""
Management command to create development users with pre-configured 2FA.

These users are only created when DEBUG=True and provide quick access
to different user roles for testing without needing to set up 2FA manually.

All dev users share the same TOTP secret, so you can add it once to your
authenticator app and use it for any dev user.

Usage:
    python manage.py create_dev_users

Dev users created:
    - admin@eatyourpeas.co.uk (superuser)
    - admin+org_owner@eatyourpeas.co.uk (organization owner)
    - admin+org_admin@eatyourpeas.co.uk (organization admin)
    - admin+org_member@eatyourpeas.co.uk (organization member)
    - admin+team_admin@eatyourpeas.co.uk (team admin)
    - admin+team_member@eatyourpeas.co.uk (team member)
    - admin+survey_creator@eatyourpeas.co.uk (survey creator)
    - admin+survey_viewer@eatyourpeas.co.uk (survey viewer)

All users have password: devpassword123
All users share TOTP secret: JBSWY3DPEHPK3PXP (add to authenticator app)
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

# Shared TOTP secret for all dev users (base32 encoded)
# This is a well-known test secret - DO NOT use in production
DEV_TOTP_SECRET_B32 = "JBSWY3DPEHPK3PXP"
DEV_TOTP_SECRET_HEX = "48656c6c6f21deadbeef"  # Hex representation

DEV_PASSWORD = "devpassword123"

DEV_USERS = [
    {
        "email": "admin@eatyourpeas.co.uk",
        "is_superuser": True,
        "is_staff": True,
        "description": "Superuser with full access",
    },
    {
        "email": "admin+org_owner@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "org_role": "owner",
        "description": "Organization owner",
    },
    {
        "email": "admin+org_admin@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "org_role": "admin",
        "description": "Organization admin",
    },
    {
        "email": "admin+org_creator@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "org_role": "creator",
        "description": "Organization creator",
    },
    {
        "email": "admin+org_viewer@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "org_role": "viewer",
        "description": "Organization viewer",
    },
    {
        "email": "admin+team_admin@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "team_role": "admin",
        "description": "Team admin",
    },
    {
        "email": "admin+team_creator@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "team_role": "creator",
        "description": "Team creator",
    },
    {
        "email": "admin+survey_creator@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "survey_role": "creator",
        "description": "Survey creator",
    },
    {
        "email": "admin+survey_viewer@eatyourpeas.co.uk",
        "is_superuser": False,
        "is_staff": False,
        "survey_role": "viewer",
        "description": "Survey viewer",
    },
]


class Command(BaseCommand):
    help = "Create development users with pre-configured 2FA (DEBUG mode only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation even if DEBUG is False (NOT RECOMMENDED)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing dev users and recreate them",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "This command only runs in DEBUG mode. "
                "Use --force to override (NOT RECOMMENDED for production)."
            )

        if options["force"] and not settings.DEBUG:
            self.stdout.write(
                self.style.WARNING(
                    "WARNING: Creating dev users in non-DEBUG mode. "
                    "This is a security risk!"
                )
            )

        User = get_user_model()

        # Import models
        from django_otp.plugins.otp_totp.models import TOTPDevice

        from checktick_app.surveys.models import (
            Organization,
            OrganizationMembership,
            Survey,
            SurveyMembership,
            Team,
            TeamMembership,
        )

        created_count = 0
        updated_count = 0

        # Create a dev organization and team if needed
        dev_org = None
        dev_team = None
        dev_survey = None

        with transaction.atomic():
            # Delete existing dev users if --reset
            if options["reset"]:
                deleted_count = User.objects.filter(
                    email__endswith="@eatyourpeas.co.uk"
                ).delete()[0]
                if deleted_count:
                    self.stdout.write(f"Deleted {deleted_count} existing dev users")

            for user_config in DEV_USERS:
                email = user_config["email"]
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": email,
                        "is_superuser": user_config.get("is_superuser", False),
                        "is_staff": user_config.get("is_staff", False),
                    },
                )

                if created:
                    user.set_password(DEV_PASSWORD)
                    user.save()
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created: {email} ({user_config['description']})"
                        )
                    )
                else:
                    updated_count += 1
                    self.stdout.write(f"Exists: {email}")

                # Set up 2FA device if not already present
                if not TOTPDevice.objects.filter(user=user, confirmed=True).exists():
                    TOTPDevice.objects.create(
                        user=user,
                        name="Dev Authenticator",
                        key=DEV_TOTP_SECRET_HEX,
                        confirmed=True,
                    )
                    self.stdout.write("  → 2FA device created")

                # Set up organization roles
                if user_config.get("org_role"):
                    if dev_org is None:
                        dev_org, _ = Organization.objects.get_or_create(
                            name="Dev Organization",
                            defaults={
                                "owner": (
                                    user if user_config["org_role"] == "owner" else None
                                )
                            },
                        )
                        self.stdout.write(f"  → Dev Organization: {dev_org.name}")

                    if user_config["org_role"] == "owner":
                        dev_org.owner = user
                        dev_org.save()

                    role_map = {
                        "admin": OrganizationMembership.Role.ADMIN,
                        "creator": OrganizationMembership.Role.CREATOR,
                        "viewer": OrganizationMembership.Role.VIEWER,
                        "owner": OrganizationMembership.Role.ADMIN,
                    }
                    OrganizationMembership.objects.get_or_create(
                        organization=dev_org,
                        user=user,
                        defaults={
                            "role": role_map.get(
                                user_config["org_role"],
                                OrganizationMembership.Role.VIEWER,
                            )
                        },
                    )
                    self.stdout.write(f"  → Org role: {user_config['org_role']}")

                # Set up team roles
                if user_config.get("team_role"):
                    if dev_org is None:
                        dev_org, _ = Organization.objects.get_or_create(
                            name="Dev Organization",
                        )
                    if dev_team is None:
                        # Need an owner for the team - use first superuser or current user
                        team_owner = (
                            User.objects.filter(is_superuser=True).first() or user
                        )
                        dev_team, _ = Team.objects.get_or_create(
                            name="Dev Team",
                            organization=dev_org,
                            defaults={"owner": team_owner},
                        )
                        self.stdout.write(f"  → Dev Team: {dev_team.name}")

                    role_map = {
                        "admin": TeamMembership.Role.ADMIN,
                        "creator": TeamMembership.Role.CREATOR,
                        "viewer": TeamMembership.Role.VIEWER,
                    }
                    TeamMembership.objects.get_or_create(
                        team=dev_team,
                        user=user,
                        defaults={
                            "role": role_map.get(
                                user_config["team_role"], TeamMembership.Role.VIEWER
                            )
                        },
                    )
                    self.stdout.write(f"  → Team role: {user_config['team_role']}")

                # Set up survey roles
                if user_config.get("survey_role"):
                    if dev_survey is None:
                        # Need an owner for the survey
                        owner = User.objects.filter(is_superuser=True).first() or user
                        dev_survey, _ = Survey.objects.get_or_create(
                            name="Dev Survey",
                            defaults={
                                "owner": owner,
                                "slug": "dev-survey",
                                "description": "Development test survey",
                            },
                        )
                        self.stdout.write(f"  → Dev Survey: {dev_survey.name}")

                    role_map = {
                        "creator": SurveyMembership.Role.CREATOR,
                        "viewer": SurveyMembership.Role.VIEWER,
                    }
                    SurveyMembership.objects.get_or_create(
                        survey=dev_survey,
                        user=user,
                        defaults={
                            "role": role_map.get(
                                user_config["survey_role"], SurveyMembership.Role.VIEWER
                            )
                        },
                    )
                    self.stdout.write(f"  → Survey role: {user_config['survey_role']}")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} new users, {updated_count} already existed"
            )
        )
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.WARNING("DEV USER CREDENTIALS"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Password (all users): {DEV_PASSWORD}")
        self.stdout.write(f"TOTP Secret (base32): {DEV_TOTP_SECRET_B32}")
        self.stdout.write("")
        self.stdout.write(
            "Add this secret to your authenticator app (Google Authenticator, Authy, etc.)"
        )
        self.stdout.write("The same code works for all dev users.")
        self.stdout.write("=" * 60)
