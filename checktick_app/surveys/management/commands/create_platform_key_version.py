"""
Django management command to create a new platform key version.

This generates a completely new platform master key with fresh cryptographic material
(Option B rotation). Use this when:
- Starting fresh after a security incident
- Regulatory requirement for key material refresh
- Setting up the first platform key

For rotating Shamir shares only (Option A), use rotate_platform_key_shares instead.

Usage:
    python manage.py create_platform_key_version --version v2 [--activate]

Security Notes:
    - The custodian component will be written to a file and must be split across
      YubiKeys/paper/USB using Shamir's Secret Sharing
    - Old custodian shares (v1, v2...) must be kept for decrypting old surveys
    - Delete the custodian component file after splitting
"""

import secrets

from django.core.management.base import BaseCommand, CommandError

from checktick_app.surveys.models import PlatformKeyVersion
from checktick_app.surveys.vault_client import VaultClient


class Command(BaseCommand):
    help = "Create a new platform key version with fresh cryptographic material"

    def add_arguments(self, parser):
        parser.add_argument(
            "--version",
            type=str,
            required=True,
            help="New version identifier (e.g., v1, v2, v3)",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Immediately activate this version for new escrows",
        )
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Administrative notes about this version",
        )

    def handle(self, *args, **options):
        version_id = options["version"]
        activate = options["activate"]
        notes = options["notes"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"Creating Platform Key Version: {version_id}")
        )
        self.stdout.write("")

        # Check if version already exists
        if PlatformKeyVersion.objects.filter(version=version_id).exists():
            raise CommandError(f"Platform key version '{version_id}' already exists")

        # Generate completely NEW platform master key (32 bytes for modern security)
        self.stdout.write("Generating new platform master key (32 bytes)...")
        platform_master_key = secrets.token_bytes(32)

        # Split into vault + custodian components using XOR
        self.stdout.write("Splitting into vault and custodian components...")
        vault_component = secrets.token_bytes(32)
        custodian_component = VaultClient.xor_bytes(
            platform_master_key, vault_component
        )

        # Store vault component in database
        self.stdout.write("Storing vault component in database...")
        platform_version = PlatformKeyVersion.objects.create(
            version=version_id,
            vault_component=vault_component,
            notes=notes,
        )

        if activate:
            platform_version.activate()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Activated version {version_id} for new escrows")
            )

        # Output custodian component to file
        output_path = f"platform_custodian_component_{version_id}.bin"
        with open(output_path, "wb") as f:
            f.write(custodian_component)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Platform key version {version_id} created successfully"
            )
        )
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write(self.style.WARNING("CRITICAL SECURITY STEPS - DO NOT SKIP"))
        self.stdout.write(self.style.WARNING("=" * 70))
        self.stdout.write("")
        self.stdout.write(f"1. Custodian component saved to: {output_path}")
        self.stdout.write("")
        self.stdout.write("2. Split this component using Shamir's Secret Sharing:")
        self.stdout.write(
            f"   python manage.py split_custodian_component {output_path}"
        )
        self.stdout.write("")
        self.stdout.write("3. Distribute shares across:")
        self.stdout.write("   - 4 YubiKeys (hardware security)")
        self.stdout.write("   - Physical paper in safe")
        self.stdout.write("   - Encrypted USB drive (backup)")
        self.stdout.write("   - Total: 4 shares with 3-of-4 threshold")
        self.stdout.write("")
        self.stdout.write("4. Store custodian shares in physically secure locations:")
        self.stdout.write("   - Bank safe deposit boxes")
        self.stdout.write("   - Different geographic locations")
        self.stdout.write("   - Trusted custodians (CEO, CTO, Security Officer, Legal)")
        self.stdout.write("")
        self.stdout.write(
            self.style.ERROR(
                f"5. DELETE {output_path} after splitting (use 'shred' or 'srm')"
            )
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "6. IMPORTANT: Keep OLD custodian shares (v1, v2...) for decrypting old surveys"
            )
        )
        self.stdout.write("")
        self.stdout.write(
            "7. Document custodian locations and update key management procedures"
        )
        self.stdout.write("")

        # Securely wipe the platform master key from memory
        del platform_master_key
