"""
Django management command to split custodian component into Shamir shares.

This should be run ONCE during initial setup or when rotating keys.
It takes the current PLATFORM_CUSTODIAN_COMPONENT and splits it into
4 shares using Shamir's Secret Sharing (threshold: need 3 to reconstruct).

Usage:
    python manage.py split_custodian_component --custodian-component=<hex>

Output:
    4 shares that should be distributed among admins
"""

from django.core.management.base import BaseCommand, CommandError

from checktick_app.surveys.shamir import split_secret


class Command(BaseCommand):
    help = (
        "Split custodian component into Shamir shares "
        "(4 shares, need 3 to reconstruct)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--custodian-component",
            type=str,
            required=True,
            help="64-byte hex string of the custodian component to split",
        )
        parser.add_argument(
            "--shares",
            type=int,
            default=4,
            help="Total number of shares to create (default: 4)",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=3,
            help="Number of shares needed to reconstruct (default: 3)",
        )

    def handle(self, *args, **options):
        """Split custodian component into Shamir shares."""
        custodian_hex = options["custodian_component"]
        total_shares = options["shares"]
        threshold = options["threshold"]

        # Validate input
        try:
            bytes.fromhex(custodian_hex)
        except ValueError:
            raise CommandError("Invalid hex string for custodian component")

        if len(custodian_hex) != 128:  # 64 bytes = 128 hex chars
            raise CommandError(
                f"Custodian component must be 64 bytes (128 hex chars), "
                f"got {len(custodian_hex)} chars"
            )

        if threshold > total_shares:
            raise CommandError("Threshold cannot exceed total shares")

        if threshold < 2:
            raise CommandError("Threshold must be at least 2")

        self.stdout.write(self.style.MIGRATE_HEADING("Splitting Custodian Component"))
        self.stdout.write("")
        self.stdout.write(
            f"Configuration: {total_shares} shares, need {threshold} to reconstruct"
        )
        self.stdout.write("")

        # Split using Shamir's Secret Sharing
        try:
            custodian_bytes = bytes.fromhex(custodian_hex)
            shares = split_secret(custodian_bytes, threshold, total_shares)

            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully created {len(shares)} shares")
            )
            self.stdout.write("")

            # Display shares
            self.stdout.write(
                self.style.WARNING("⚠️  CRITICAL: Store these shares securely!")
            )
            self.stdout.write(
                self.style.WARNING("⚠️  Need any 3 shares to reconstruct the key")
            )
            self.stdout.write("")

            for i, share in enumerate(shares, 1):
                self.stdout.write(self.style.MIGRATE_LABEL(f"Share {i}:"))
                self.stdout.write(f"  {share}")
                self.stdout.write("")

            # Distribution recommendations
            self.stdout.write(self.style.MIGRATE_HEADING("Recommended Distribution:"))
            self.stdout.write("")
            self.stdout.write("  Share 1 → Admin 1's password manager")
            self.stdout.write("  Share 2 → Admin 2's password manager")
            self.stdout.write("  Share 3 → Physical safe (printed, sealed envelope)")
            self.stdout.write("  Share 4 → Encrypted cloud backup (spare)")
            self.stdout.write("")

            self.stdout.write(self.style.MIGRATE_HEADING("Next Steps:"))
            self.stdout.write("")
            self.stdout.write("1. Distribute shares to designated custodians")
            self.stdout.write("2. Remove PLATFORM_CUSTODIAN_COMPONENT from .env")
            self.stdout.write("3. Restart Django application")
            self.stdout.write(
                "4. Test recovery with: python manage.py test_recovery_reconstruction"
            )
            self.stdout.write("")

            self.stdout.write(
                self.style.WARNING(
                    "⚠️  After distributing shares, securely delete the original "
                    "custodian component from your .env file and any backups"
                )
            )

        except Exception as e:
            raise CommandError(f"Failed to split custodian component: {e}")
