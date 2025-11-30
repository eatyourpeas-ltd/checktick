"""
Django management command to test HashiCorp Vault connection.

Usage:
    python manage.py test_vault_connection
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from checktick_app.surveys.vault_client import get_vault_client, VaultConnectionError


class Command(BaseCommand):
    help = 'Test HashiCorp Vault connection and authentication'

    def handle(self, *args, **options):
        """Test Vault connection."""
        self.stdout.write(self.style.MIGRATE_HEADING('Testing Vault Connection'))
        self.stdout.write('')

        # Check configuration
        self.stdout.write(self.style.MIGRATE_LABEL('Configuration:'))
        self.stdout.write(f'  VAULT_ADDR: {settings.VAULT_ADDR}')
        self.stdout.write(f'  VAULT_ROLE_ID: {"✓ Set" if settings.VAULT_ROLE_ID else "✗ Not Set"}')
        self.stdout.write(f'  VAULT_SECRET_ID: {"✓ Set" if settings.VAULT_SECRET_ID else "✗ Not Set"}')
        self.stdout.write(f'  PLATFORM_CUSTODIAN_COMPONENT: {"✓ Set" if settings.PLATFORM_CUSTODIAN_COMPONENT else "✗ Not Set"}')
        self.stdout.write('')

        if not settings.VAULT_ROLE_ID or not settings.VAULT_SECRET_ID:
            self.stdout.write(self.style.ERROR('✗ Vault credentials not configured'))
            self.stdout.write(self.style.WARNING('Please set VAULT_ROLE_ID and VAULT_SECRET_ID in your .env file'))
            return

        # Test connection
        try:
            vault = get_vault_client()
            self.stdout.write(self.style.MIGRATE_LABEL('Connection Test:'))

            # Health check
            health = vault.health_check()

            if health.get('error'):
                self.stdout.write(self.style.ERROR(f'  ✗ Vault health check failed: {health["error"]}'))
                return

            self.stdout.write(f'  Initialized: {"✓" if health.get("initialized") else "✗"}')
            self.stdout.write(f'  Sealed: {"✓ Unsealed" if not health.get("sealed") else "✗ SEALED"}')
            self.stdout.write(f'  Standby: {"Yes" if health.get("standby") else "No"}')
            self.stdout.write(f'  Version: {health.get("version", "unknown")}')
            self.stdout.write('')

            if health.get('sealed'):
                self.stdout.write(self.style.ERROR('✗ Vault is sealed. Please unseal it first.'))
                self.stdout.write(self.style.WARNING('Run: vault operator unseal <key>'))
                return

            # Test authentication
            self.stdout.write(self.style.MIGRATE_LABEL('Authentication Test:'))
            try:
                client = vault._get_client()
                if client.is_authenticated():
                    self.stdout.write(self.style.SUCCESS('  ✓ Successfully authenticated with AppRole'))
                else:
                    self.stdout.write(self.style.ERROR('  ✗ Authentication failed'))
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Authentication failed: {e}'))
                return

            self.stdout.write('')

            # Test platform key access
            self.stdout.write(self.style.MIGRATE_LABEL('Platform Key Test:'))

            if not settings.PLATFORM_CUSTODIAN_COMPONENT:
                self.stdout.write(self.style.WARNING('  ⚠ PLATFORM_CUSTODIAN_COMPONENT not set'))
                self.stdout.write(self.style.WARNING('  Cannot test platform key reconstruction'))
            else:
                try:
                    custodian_component = bytes.fromhex(settings.PLATFORM_CUSTODIAN_COMPONENT)
                    platform_key = vault.get_platform_master_key(custodian_component)

                    if len(platform_key) == 64:
                        self.stdout.write(self.style.SUCCESS('  ✓ Platform master key reconstructed successfully'))
                        self.stdout.write(f'  Key length: {len(platform_key)} bytes')
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Invalid key length: {len(platform_key)} bytes (expected 64)'))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed to get platform key: {e}'))
                    self.stdout.write(self.style.WARNING('  Has the Vault been initialized with setup_vault.py?'))

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('━' * 60))
            self.stdout.write(self.style.SUCCESS('✓ Vault Connection Test Complete'))
            self.stdout.write(self.style.SUCCESS('━' * 60))

        except VaultConnectionError as e:
            self.stdout.write(self.style.ERROR(f'✗ Connection failed: {e}'))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Troubleshooting:'))
            self.stdout.write('  1. Check VAULT_ADDR is correct')
            self.stdout.write('  2. Check network connectivity to Vault')
            self.stdout.write('  3. Check Vault is unsealed')
            self.stdout.write('  4. Check VAULT_ROLE_ID and VAULT_SECRET_ID are correct')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Unexpected error: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
