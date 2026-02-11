"""
Tests for platform recovery management commands.

Tests the Django management commands for custodian component splitting
and emergency platform recovery.
"""

import secrets
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from checktick_app.surveys.models import RecoveryRequest, Survey
from checktick_app.surveys.shamir import reconstruct_secret, split_secret

User = get_user_model()

# Use consistent test password constant
TEST_PASSWORD = "x"


class TestSplitCustodianComponentCommand(TestCase):
    """Test the split_custodian_component management command."""

    def test_split_command_with_valid_component(self):
        """Test splitting a valid 64-byte custodian component."""
        # Generate a valid 64-byte custodian component
        component = secrets.token_bytes(64)
        component_hex = component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component", custodian_component=component_hex, stdout=out
        )

        output = out.getvalue()

        # Verify output contains expected sections
        assert "Splitting Custodian Component" in output
        assert "4 shares" in output
        assert "need 3 to reconstruct" in output

        # Extract shares from output
        shares = self._extract_shares(output)
        assert len(shares) == 4

        # Verify shares can reconstruct the original
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == component

    def test_split_command_with_custom_thresholds(self):
        """Test splitting with different threshold configurations."""
        component = secrets.token_bytes(64)
        component_hex = component.hex()

        # Test 5 shares with 3 required
        out = StringIO()
        call_command(
            "split_custodian_component",
            custodian_component=component_hex,
            shares=5,
            threshold=3,
            stdout=out,
        )

        output = out.getvalue()
        shares = self._extract_shares(output)
        assert len(shares) == 5
        assert "5 shares" in output

    def test_split_command_with_invalid_component_length(self):
        """Test that command rejects invalid component lengths."""
        # Too short (32 bytes instead of 64)
        short_component = secrets.token_bytes(32).hex()

        with pytest.raises(CommandError, match="must be 64 bytes"):
            call_command(
                "split_custodian_component", custodian_component=short_component
            )

    def test_split_command_with_invalid_hex(self):
        """Test that command rejects invalid hex strings."""
        invalid_hex = "not_hex_at_all" * 16  # 128 chars but not hex

        with pytest.raises(CommandError, match="Invalid hex|Non-hexadecimal"):
            call_command("split_custodian_component", custodian_component=invalid_hex)

    def test_split_command_default_parameters(self):
        """Test command with default shares and threshold."""
        component = secrets.token_bytes(64)
        component_hex = component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component", custodian_component=component_hex, stdout=out
        )

        output = out.getvalue()

        # Default should be 4 shares, 3 threshold
        assert "4 shares" in output
        assert "need 3 to reconstruct" in output

    def _extract_shares(self, output: str) -> list[str]:
        """Extract share strings from command output."""
        shares = []
        lines = output.split("\n")
        for i, line in enumerate(lines):
            # Look for "Share N:" pattern, then get next line which contains the actual share
            if line.strip().startswith("Share ") and ":" in line.strip():
                # Get next non-empty line which should contain the share
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and next_line.startswith("80") and "-" in next_line:
                        shares.append(next_line)
                        break
        return shares


class TestCustodianReconstructionCommand(TestCase):
    """Test the test_custodian_reconstruction management command."""

    def test_reconstruction_with_valid_shares(self):
        """Test reconstructing custodian component from valid shares."""
        # Create a custodian component and split it
        original_component = secrets.token_bytes(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Test reconstruction
        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            share_1=shares[0],
            share_2=shares[1],
            share_3=shares[2],
            stdout=out,
        )

        output = out.getvalue()

        # Verify output
        assert "Testing Custodian Component Reconstruction" in output
        assert "Reconstructing from shares" in output
        assert original_component.hex() in output

    def test_reconstruction_with_original_validation(self):
        """Test reconstruction with original component validation."""
        original_component = secrets.token_bytes(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            share_1=shares[0],
            share_2=shares[1],
            share_3=shares[2],
            original=original_component.hex(),
            stdout=out,
        )

        output = out.getvalue()

        # Should show success message
        assert "✓ Reconstruction successful" in output
        assert "✓ MATCH" in output or "matches original" in output.lower()

    def test_reconstruction_with_wrong_original(self):
        """Test reconstruction shows failure when original doesn't match."""
        original_component = secrets.token_bytes(64)
        wrong_component = secrets.token_bytes(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Command should raise an error when verification fails
        with pytest.raises(CommandError, match="(Reconstruction|verification)"):
            call_command(
                "test_custodian_reconstruction",
                share_1=shares[0],
                share_2=shares[1],
                share_3=shares[2],
                original=wrong_component.hex(),
                stdout=StringIO(),
            )

    def test_reconstruction_with_all_four_shares(self):
        """Test that reconstruction works with all 4 shares."""
        original_component = secrets.token_bytes(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Use shares 0, 1, and 3 (skipping 2)
        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            share_1=shares[0],
            share_2=shares[1],
            share_3=shares[3],
            stdout=out,
        )

        output = out.getvalue()

        # Should work
        assert "✓ Reconstruction successful" in output
        assert original_component.hex() in output

    def test_reconstruction_with_insufficient_shares(self):
        """Test that reconstruction with invalid shares fails."""
        original_component = secrets.token_bytes(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Try with an invalid third share
        with pytest.raises(CommandError):
            call_command(
                "test_custodian_reconstruction",
                **{
                    "share_1": shares[0],
                    "share_2": shares[1],
                    "share_3": "invalid-share",
                },
            )


@pytest.mark.django_db
class TestExecutePlatformRecoveryCommand:
    """Test the execute_platform_recovery management command."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password=TEST_PASSWORD,
        )
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password=TEST_PASSWORD,
        )
        self.survey = Survey.objects.create(
            name="Test Survey",
            slug="test-survey",
            owner=self.user,
        )

    def test_recovery_command_with_valid_request(self):
        """Test platform recovery with valid recovery request."""
        # Create a recovery request ready for execution
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.READY_FOR_EXECUTION,
            primary_approver=self.admin,
            secondary_approver=self.admin,  # In testing, same admin is OK
        )

        # Generate custodian component and shares
        custodian_component = secrets.token_bytes(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Mock the vault client
        with patch(
            "checktick_app.surveys.management.commands.execute_platform_recovery.get_vault_client"
        ) as mock_vault_func:
            mock_vault = MagicMock()
            mock_vault_func.return_value = mock_vault

            out = StringIO()
            call_command(
                "execute_platform_recovery",
                str(recovery_request.id),
                **{
                    "custodian_share_1": shares[0],
                    "custodian_share_2": shares[1],
                    "custodian_share_3": shares[2],
                },
                executor="admin@example.com",  # Required executor email
                dry_run=True,  # Don't actually execute recovery in test
                stdout=out,
            )

            output = out.getvalue()

            # Verify output
            assert "Platform Recovery Execution" in output
            assert recovery_request.request_code in output

    def test_recovery_command_missing_recovery_request(self):
        """Test that command fails when recovery request doesn't exist."""
        custodian_component = secrets.token_bytes(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Use a valid UUID that doesn't exist
        import uuid

        with pytest.raises(CommandError, match="(Recovery request|not found)"):
            call_command(
                "execute_platform_recovery",
                str(uuid.uuid4()),  # Valid UUID format but doesn't exist
                **{
                    "custodian_share_1": shares[0],
                    "custodian_share_2": shares[1],
                    "custodian_share_3": shares[2],
                },
            )

    def test_recovery_command_wrong_status(self):
        """Test that command fails if recovery request has wrong status."""
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.COMPLETED,  # Wrong status
        )

        custodian_component = secrets.token_bytes(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        with pytest.raises(
            CommandError, match="(already been completed|not ready|COMPLETED)"
        ):
            call_command(
                "execute_platform_recovery",
                str(recovery_request.id),
                **{
                    "custodian_share_1": shares[0],
                    "custodian_share_2": shares[1],
                    "custodian_share_3": shares[2],
                },
            )

    def test_recovery_command_insufficient_shares(self):
        """Test that command with invalid shares fails reconstruction."""
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.READY_FOR_EXECUTION,
        )

        custodian_component = secrets.token_bytes(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Try with invalid third share
        with pytest.raises(CommandError):
            call_command(
                "execute_platform_recovery",
                str(recovery_request.id),
                **{
                    "custodian_share_1": shares[0],
                    "custodian_share_2": shares[1],
                    "custodian_share_3": "invalid-share",
                },
            )


class TestCommandIntegration(TestCase):
    """Integration tests for command workflows."""

    def test_split_and_verify_workflow(self):
        """Test the complete split → verify workflow."""
        # Step 1: Split a custodian component
        custodian_component = secrets.token_bytes(64)
        component_hex = custodian_component.hex()

        split_out = StringIO()
        call_command(
            "split_custodian_component",
            custodian_component=component_hex,
            stdout=split_out,
        )

        split_output = split_out.getvalue()

        # Extract shares from output
        shares = self._extract_shares(split_output)
        assert len(shares) == 4

        # Step 2: Verify the shares reconstruct correctly
        verify_out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            share_1=shares[0],
            share_2=shares[1],
            share_3=shares[2],
            original=component_hex,
            stdout=verify_out,
        )

        verify_output = verify_out.getvalue()

        # Should show success
        assert "✓ Match verified" in verify_output or "matches" in verify_output.lower()

    def test_different_share_combinations(self):
        """Test that any 3 of 4 shares work for reconstruction."""
        custodian_component = secrets.token_bytes(64)
        component_hex = custodian_component.hex()

        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Test all combinations of 3 shares
        combinations = [
            [shares[0], shares[1], shares[2]],
            [shares[0], shares[1], shares[3]],
            [shares[0], shares[2], shares[3]],
            [shares[1], shares[2], shares[3]],
        ]

        for combo in combinations:
            verify_out = StringIO()
            call_command(
                "test_custodian_reconstruction",
                share_1=combo[0],
                share_2=combo[1],
                share_3=combo[2],
                original=component_hex,
                stdout=verify_out,
            )

            verify_output = verify_out.getvalue()
            assert "✓" in verify_output or "success" in verify_output.lower()

    def _extract_shares(self, output: str) -> list[str]:
        """Extract share strings from command output."""
        shares = []
        lines = output.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("Share ") and ":" in line.strip():
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and next_line.startswith("80") and "-" in next_line:
                        shares.append(next_line)
                        break
        return shares


class TestCommandSecurityProperties(TestCase):
    """Test security properties of the commands."""

    def test_shares_are_different_each_time(self):
        """Test that splitting the same component twice produces different shares."""
        custodian_component = secrets.token_bytes(64)
        component_hex = custodian_component.hex()

        # Split twice
        out1 = StringIO()
        call_command(
            "split_custodian_component",
            custodian_component=component_hex,
            stdout=out1,
        )

        out2 = StringIO()
        call_command(
            "split_custodian_component",
            custodian_component=component_hex,
            stdout=out2,
        )

        # Outputs should be different (different shares due to random polynomial)
        assert out1.getvalue() != out2.getvalue()

    def test_command_output_includes_security_warnings(self):
        """Test that commands include appropriate security warnings."""
        custodian_component = secrets.token_bytes(64)
        component_hex = custodian_component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component",
            custodian_component=component_hex,
            stdout=out,
        )

        output = out.getvalue()

        # Should include security warnings (using ⚠️ emoji)
        assert "CRITICAL" in output or "⚠️" in output
        assert "securely" in output.lower()

    def test_reconstruction_shows_result(self):
        """Test that reconstruction command displays result appropriately."""
        custodian_component = secrets.token_bytes(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            share_1=shares[0],
            share_2=shares[1],
            share_3=shares[2],
            stdout=out,
        )

        output = out.getvalue()

        # Should show the reconstructed component (admin needs to verify)
        assert "Reconstructed custodian component" in output
        assert custodian_component.hex() in output
