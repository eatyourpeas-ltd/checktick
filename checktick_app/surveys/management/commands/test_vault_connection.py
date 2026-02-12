"""
Django management command to test HashiCorp Vault connection.

Usage:
    python manage.py test_vault_connection
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from checktick_app.surveys.vault_client import VaultConnectionError, get_vault_client


class Command(BaseCommand):
    help = "Test HashiCorp Vault connection and authentication"

    def handle(self, *args, **options):
        """Test Vault connection."""
        self.stdout.write(self.style.MIGRATE_HEADING("Testing Vault Connection"))
        self.stdout.write("")

        # Check configuration
        self.stdout.write(self.style.MIGRATE_LABEL("Configuration:"))
        self.stdout.write(f"  VAULT_ADDR: {settings.VAULT_ADDR}")
        self.stdout.write(
            f'  VAULT_ROLE_ID: {"✓ Set" if settings.VAULT_ROLE_ID else "✗ Not Set"}'
        )
        self.stdout.write(
            f'  VAULT_SECRET_ID: {"✓ Set" if settings.VAULT_SECRET_ID else "✗ Not Set"}'
        )
        self.stdout.write(
            "  PLATFORM_CUSTODIAN: Split into shares (not in environment)"
        )
        self.stdout.write("")

        if not settings.VAULT_ROLE_ID or not settings.VAULT_SECRET_ID:
            self.stdout.write(self.style.ERROR("✗ Vault credentials not configured"))
            self.stdout.write(
                self.style.WARNING(
                    "Please set VAULT_ROLE_ID and VAULT_SECRET_ID in your .env file"
                )
            )
            return

        # Test connection
        try:
            vault = get_vault_client()
            self.stdout.write(self.style.MIGRATE_LABEL("Connection Test:"))

            # Health check
            health = vault.health_check()

            if health.get("error"):
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Vault health check failed: {health["error"]}'
                    )
                )
                return

            self.stdout.write(
                f'  Initialized: {"✓" if health.get("initialized") else "✗"}'
            )
            self.stdout.write(
                f'  Sealed: {"✓ Unsealed" if not health.get("sealed") else "✗ SEALED"}'
            )
            self.stdout.write(f'  Standby: {"Yes" if health.get("standby") else "No"}')
            self.stdout.write(f'  Version: {health.get("version", "unknown")}')
            self.stdout.write("")

            if health.get("sealed"):
                self.stdout.write(
                    self.style.ERROR("✗ Vault is sealed. Please unseal it first.")
                )
                self.stdout.write(
                    self.style.WARNING("Run: vault operator unseal <key>")
                )
                return

            # Test authentication
            self.stdout.write(self.style.MIGRATE_LABEL("Authentication Test:"))
            try:
                client = vault._get_client()
                if client.is_authenticated():
                    self.stdout.write(
                        self.style.SUCCESS(
                            "  ✓ Successfully authenticated with AppRole"
                        )
                    )
                else:
                    self.stdout.write(self.style.ERROR("  ✗ Authentication failed"))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Authentication failed: {e}"))
                return

            self.stdout.write("")

            # Test platform key access
            self.stdout.write(self.style.MIGRATE_LABEL("Platform Key Test:"))
            self.stdout.write("  ℹ️  Platform key reconstruction test skipped")
            self.stdout.write(
                "  Custodian component now split into Shamir shares (not in environment)"
            )
            self.stdout.write(
                "  Use: python manage.py execute_platform_recovery --help"
            )

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("━" * 60))
            self.stdout.write(self.style.SUCCESS("✓ Vault Connection Test Complete"))
            self.stdout.write(self.style.SUCCESS("━" * 60))

        except VaultConnectionError as e:
            self.stdout.write(self.style.ERROR(f"✗ Connection failed: {e}"))
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Troubleshooting:"))
            self.stdout.write("  1. Check VAULT_ADDR is correct")
            self.stdout.write("  2. Check network connectivity to Vault")
            self.stdout.write("  3. Check Vault is unsealed")
            self.stdout.write(
                "  4. Check VAULT_ROLE_ID and VAULT_SECRET_ID are correct"
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Unexpected error: {e}"))
            import traceback

            self.stdout.write(traceback.format_exc())
