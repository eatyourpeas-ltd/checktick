"""
Django management command to test custodian component reconstruction.

This verifies that the Shamir shares can correctly reconstruct the original
custodian component.

Usage:
    python manage.py test_custodian_reconstruction \
        --share-1=<share1> \
        --share-2=<share2> \
        --share-3=<share3> \
        --original=<original_hex> (optional, to verify)
"""

from django.core.management.base import BaseCommand, CommandError

from checktick_app.surveys.shamir import reconstruct_secret


class Command(BaseCommand):
    help = "Test reconstruction of custodian component from shares"

    def add_arguments(self, parser):
        parser.add_argument(
            "--share-1",
            type=str,
            required=True,
            help="First custodian share",
        )
        parser.add_argument(
            "--share-2",
            type=str,
            required=True,
            help="Second custodian share",
        )
        parser.add_argument(
            "--share-3",
            type=str,
            required=True,
            help="Third custodian share",
        )
        parser.add_argument(
            "--original",
            type=str,
            help="Original custodian component hex (optional, for verification)",
        )

    def handle(self, *args, **options):
        """Test reconstruction of custodian component."""
        share1 = options["share_1"]
        share2 = options["share_2"]
        share3 = options["share_3"]
        original_hex = options.get("original")

        self.stdout.write(
            self.style.MIGRATE_HEADING("Testing Custodian Component Reconstruction")
        )
        self.stdout.write("")

        # Test reconstruction
        try:
            self.stdout.write(self.style.MIGRATE_LABEL("Reconstructing from shares:"))
            self.stdout.write(f"  Share 1: {share1[:20]}...")
            self.stdout.write(f"  Share 2: {share2[:20]}...")
            self.stdout.write(f"  Share 3: {share3[:20]}...")
            self.stdout.write("")

            reconstructed = reconstruct_secret([share1, share2, share3])
            reconstructed_hex = reconstructed.hex()

            self.stdout.write(self.style.SUCCESS("✓ Reconstruction successful!"))
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_LABEL("Reconstructed custodian component:")
            )
            self.stdout.write(f"  {reconstructed_hex}")
            self.stdout.write("")

            # Verify against original if provided
            if original_hex:
                self.stdout.write(self.style.MIGRATE_LABEL("Verification:"))

                # Normalize hex strings (remove any whitespace, make lowercase)
                original_normalized = original_hex.replace(" ", "").lower()
                reconstructed_normalized = reconstructed_hex.lower()

                if original_normalized == reconstructed_normalized:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "✓ MATCH: Reconstructed value matches original!"
                        )
                    )
                    self.stdout.write("")
                    self.stdout.write(
                        "The shares are working correctly. You can safely:"
                    )
                    self.stdout.write("  1. Distribute shares to custodians")
                    self.stdout.write(
                        "  2. Remove PLATFORM_CUSTODIAN_COMPONENT from .env"
                    )
                    self.stdout.write("  3. Restart your application")
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "✗ MISMATCH: Reconstructed value does NOT match original!"
                        )
                    )
                    self.stdout.write("")
                    self.stdout.write("Expected:")
                    self.stdout.write(f"  {original_normalized}")
                    self.stdout.write("")
                    self.stdout.write("Got:")
                    self.stdout.write(f"  {reconstructed_normalized}")
                    raise CommandError("Reconstruction verification failed")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "ℹ️  No original provided - cannot verify correctness"
                    )
                )
                self.stdout.write(
                    "  Run again with --original=<hex> to verify reconstruction"
                )

        except Exception as e:
            raise CommandError(f"Reconstruction failed: {e}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("✓ Test Complete"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
