"""
Django management command to activate a platform key version.

This makes a specific version active for new escrows. Any previously active
version will be automatically retired.

Usage:
    python manage.py activate_platform_key_version --version v2

Notes:
    - Only one version can be active at a time
    - Retired versions are still used for decrypting old surveys
    - Cannot activate a version that doesn't exist
"""

from django.core.management.base import BaseCommand, CommandError

from checktick_app.surveys.models import PlatformKeyVersion


class Command(BaseCommand):
    help = "Activate a platform key version for new escrows"

    def add_arguments(self, parser):
        parser.add_argument(
            "--version",
            type=str,
            required=True,
            help="Version identifier to activate (e.g., v1, v2)",
        )

    def handle(self, *args, **options):
        version_id = options["version"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Activating Platform Key Version: {version_id}")
        )
        self.stdout.write("")

        # Check if version exists
        try:
            platform_version = PlatformKeyVersion.objects.get(version=version_id)
        except PlatformKeyVersion.DoesNotExist:
            raise CommandError(
                f"Platform key version '{version_id}' does not exist. "
                f"Create it first with: python manage.py create_platform_key_version --version {version_id}"
            )

        # Check if already active
        if platform_version.is_active():
            self.stdout.write(
                self.style.WARNING(f"Version {version_id} is already active")
            )
            return

        # Get currently active version
        current_active = PlatformKeyVersion.get_active_version()
        if current_active:
            self.stdout.write(f"Currently active version: {current_active.version}")
            self.stdout.write(f"Retiring version {current_active.version}...")

        # Activate the new version (automatically retires current)
        platform_version.activate()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"✓ Platform key version {version_id} is now active")
        )
        self.stdout.write("")
        self.stdout.write("New user survey KEK escrows will use this version.")
        self.stdout.write("")

        if current_active:
            self.stdout.write(
                self.style.WARNING(
                    f"Version {current_active.version} has been retired but is still "
                    f"needed for decrypting surveys created before "
                    f"{platform_version.activated_at.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            )
            self.stdout.write("")
            self.stdout.write(
                f"Keep custodian shares for version {current_active.version} "
                f"in secure storage."
            )
