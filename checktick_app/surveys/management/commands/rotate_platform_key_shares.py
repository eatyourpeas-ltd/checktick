"""
Django management command to rotate Shamir shares for an existing platform key version.

This implements rotation (Option A - see docs/encryption-technical-reference/): re-split the SAME platform master key with
NEW Shamir shares. Use this when:
- Custodian employee leaves company
- Suspected compromise of physical shares
- Routine annual/biennial rotation policy
- YubiKey hardware replacement

The platform master key remains unchanged, so:
- Old surveys remain decryptable
- No need to keep multiple custodian sets
- Only active version needs custodian shares

For generating a completely new platform key, use create_platform_key_version (Option B - docs/encryption-technical-reference/).

Usage:
    python manage.py rotate_platform_key_shares --version v1 \\
        --existing-custodian-component platform_custodian_component_v1.bin

Security Notes:
    - Requires existing custodian component to reconstruct platform key
    - Generates NEW vault + custodian components (same platform key)
    - Old physical shares (YubiKeys/paper/USB) must be destroyed
    - New shares must be distributed immediately
"""

import secrets

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from checktick_app.surveys.models import PlatformKeyVersion
from checktick_app.surveys.vault_client import VaultClient


class Command(BaseCommand):
    help = "Re-split an existing platform key version with new Shamir shares"

    def add_arguments(self, parser):
        parser.add_argument(
            "--version",
            type=str,
            required=True,
            help="Platform key version to re-split (e.g., v1)",
        )
        parser.add_argument(
            "--existing-custodian-component",
            type=str,
            required=True,
            help="Path to existing custodian component file (will reconstruct vault component)",
        )

    def handle(self, *args, **options):
        version_id = options["version"]
        custodian_path = options["existing_custodian_component"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Rotating Shamir Shares for Platform Key Version: {version_id}"
            )
        )
        self.stdout.write("")

        # Check if version exists
        try:
            platform_version = PlatformKeyVersion.objects.get(version=version_id)
        except PlatformKeyVersion.DoesNotExist:
            raise CommandError(f"Platform key version '{version_id}' does not exist")

        # Load existing vault component from database
        old_vault_component = bytes(platform_version.vault_component)
        self.stdout.write(f"✓ Retrieved vault component for {version_id} from database")

        # Load existing custodian component from file
        try:
            with open(custodian_path, "rb") as f:
                old_custodian_component = f.read()
            self.stdout.write(
                f"✓ Loaded existing custodian component from {custodian_path}"
            )
        except FileNotFoundError:
            raise CommandError(
                f"Custodian component file not found: {custodian_path}\\n"
                f"You must reconstruct the custodian component from Shamir shares first."
            )

        # Validate component size
        if len(old_custodian_component) != 32:
            raise CommandError(
                f"Invalid custodian component size: {len(old_custodian_component)} bytes. "
                f"Expected 32 bytes."
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "⚠️  This will reconstruct the platform master key in memory"
            )
        )
        self.stdout.write("")

        # Reconstruct the ORIGINAL platform master key
        platform_master_key = VaultClient.xor_bytes(
            old_vault_component, old_custodian_component
        )
        self.stdout.write(self.style.SUCCESS("✓ Reconstructed platform master key"))

        # Generate NEW random split components
        self.stdout.write("")
        self.stdout.write("Generating new vault and custodian components...")
        new_vault_component = secrets.token_bytes(32)
        new_custodian_component = VaultClient.xor_bytes(
            platform_master_key, new_vault_component
        )

        # Update database with new vault component
        platform_version.vault_component = new_vault_component
        platform_version.shares_last_rotated = timezone.now()
        platform_version.save()

        self.stdout.write(self.style.SUCCESS("✓ Updated vault component in database"))

        # Output new custodian component for Shamir splitting
        output_path = f'platform_custodian_component_{version_id}_rotated_{timezone.now().strftime("%Y%m%d_%H%M%S")}.bin'
        with open(output_path, "wb") as f:
            f.write(new_custodian_component)

        self.stdout.write(
            self.style.SUCCESS(f"✓ Saved new custodian component to {output_path}")
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Share rotation complete for platform key version {version_id}"
            )
        )
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(self.style.WARNING("CRITICAL SECURITY STEPS - DO NOT SKIP"))
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write("")
        self.stdout.write(f"1. New custodian component saved to: {output_path}")
        self.stdout.write("")
        self.stdout.write("2. Split this component using Shamir's Secret Sharing:")
        self.stdout.write(
            f"   python manage.py split_custodian_component {output_path}"
        )
        self.stdout.write("")
        self.stdout.write("3. Distribute NEW shares across:")
        self.stdout.write("   - 4 new YubiKeys (replace old ones)")
        self.stdout.write("   - New physical paper in safe")
        self.stdout.write("   - New encrypted USB drive")
        self.stdout.write("   - Total: 4 shares with 3-of-4 threshold")
        self.stdout.write("")
        self.stdout.write(self.style.ERROR("4. DESTROY OLD PHYSICAL SHARES:"))
        self.stdout.write("   - Wipe old YubiKeys (factory reset)")
        self.stdout.write("   - Shred old paper shares")
        self.stdout.write("   - Securely erase old USB drives")
        self.stdout.write("")
        self.stdout.write(
            self.style.ERROR(
                f"5. DELETE {output_path} AND {custodian_path} after splitting:"
            )
        )
        self.stdout.write("   shred -vfz -n 10 *.bin")
        self.stdout.write("")
        self.stdout.write("6. Update key management documentation:")
        self.stdout.write(
            f"   - Record rotation date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.stdout.write("   - Update custodian assignments")
        self.stdout.write("   - Document new share locations")
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "7. Platform key remains the same - old surveys still decryptable ✓"
            )
        )
        self.stdout.write("")

        # Securely wipe the platform master key from memory
        del platform_master_key
