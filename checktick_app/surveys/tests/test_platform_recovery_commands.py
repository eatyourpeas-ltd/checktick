"""
Tests for platform recovery management commands.

Tests the Django management commands for custodian component splitting
and emergency platform recovery.
"""

import os
from io import StringIO
from unittest.mock import Mock, patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from checktick_app.surveys.models import Survey, RecoveryRequest
from checktick_app.surveys.shamir import split_secret, reconstruct_secret

User = get_user_model()

# Use consistent test password constant
TEST_PASSWORD = "x"


class TestSplitCustodianComponentCommand(TestCase):
    """Test the split_custodian_component management command."""

    def test_split_command_with_valid_component(self):
        """Test splitting a valid 64-byte custodian component."""
        # Generate a valid 64-byte custodian component
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            "--shares=4",
            "--threshold=3",
            stdout=out,
        )

        output = out.getvalue()

        # Verify output contains expected sections
        assert "Custodian Component Split Successfully" in output
        assert "Share 1/4:" in output
        assert "Share 2/4:" in output
        assert "Share 3/4:" in output
        assert "Share 4/4:" in output
        assert "SECURITY INSTRUCTIONS" in output
        assert "3 of 4 shares required" in output

        # Extract shares from output
        lines = output.split("\n")
        shares = []
        for i, line in enumerate(lines):
            if line.startswith(("Share 1/4:", "Share 2/4:", "Share 3/4:", "Share 4/4:")):
                # Next line has the actual share
                share = lines[i + 1].strip()
                if share:
                    shares.append(share)

        assert len(shares) == 4

        # Verify shares can reconstruct the original
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == custodian_component

    def test_split_command_with_custom_thresholds(self):
        """Test splitting with different threshold configurations."""
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        # Test 5 shares with 3 required
        out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            "--shares=5",
            "--threshold=3",
            stdout=out,
        )

        output = out.getvalue()
        assert "Share 5/5:" in output
        assert "3 of 5 shares required" in output

    def test_split_command_with_invalid_component_length(self):
        """Test that command rejects invalid component lengths."""
        # Too short (32 bytes instead of 64)
        short_component = os.urandom(32).hex()

        with pytest.raises(CommandError, match="must be exactly 64 bytes"):
            call_command(
                "split_custodian_component",
                f"--custodian-component={short_component}",
                "--shares=4",
                "--threshold=3",
            )

    def test_split_command_with_invalid_hex(self):
        """Test that command rejects invalid hex strings."""
        invalid_hex = "not_hex_at_all" * 16  # 128 chars but not hex

        with pytest.raises(CommandError, match="Invalid hex"):
            call_command(
                "split_custodian_component",
                f"--custodian-component={invalid_hex}",
                "--shares=4",
                "--threshold=3",
            )

    def test_split_command_default_parameters(self):
        """Test command with default shares and threshold."""
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=out,
        )

        output = out.getvalue()

        # Default should be 4 shares, 3 threshold
        assert "Share 4/4:" in output
        assert "3 of 4 shares required" in output


class TestCustodianReconstructionCommand(TestCase):
    """Test the test_custodian_reconstruction management command."""

    def test_reconstruction_with_valid_shares(self):
        """Test reconstructing custodian component from valid shares."""
        # Create a custodian component and split it
        original_component = os.urandom(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Test reconstruction
        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            stdout=out,
        )

        output = out.getvalue()

        # Verify output
        assert "Testing Custodian Component Reconstruction" in output
        assert "Using 3 shares for reconstruction" in output
        assert "Reconstructed Component (hex):" in output
        assert original_component.hex() in output

    def test_reconstruction_with_original_validation(self):
        """Test reconstruction with original component validation."""
        original_component = os.urandom(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            f"--original={original_component.hex()}",
            stdout=out,
        )

        output = out.getvalue()

        # Should show success message
        assert "SUCCESS: Reconstructed component matches original" in output
        assert original_component.hex() in output

    def test_reconstruction_with_wrong_original(self):
        """Test reconstruction fails when original doesn't match."""
        original_component = os.urandom(64)
        wrong_component = os.urandom(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        out = StringIO()
        err = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            f"--original={wrong_component.hex()}",
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()

        # Should show failure message
        assert "FAILURE: Reconstructed component does NOT match original" in output

    def test_reconstruction_with_all_four_shares(self):
        """Test that reconstruction works with all 4 shares."""
        original_component = os.urandom(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            shares[3],
            stdout=out,
        )

        output = out.getvalue()

        # Should work with 4 shares
        assert "Using 4 shares for reconstruction" in output
        assert original_component.hex() in output

    def test_reconstruction_with_insufficient_shares(self):
        """Test that reconstruction with too few shares produces wrong result."""
        original_component = os.urandom(64)
        shares = split_secret(original_component, threshold=3, total_shares=4)

        # Try with only 2 shares
        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            f"--original={original_component.hex()}",
            stdout=out,
        )

        output = out.getvalue()

        # Should show failure
        assert "FAILURE: Reconstructed component does NOT match original" in output


class TestExecutePlatformRecoveryCommand(TestCase):
    """Test the execute_platform_recovery management command."""

    def setUp(self):
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
        # Create a recovery request
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.PENDING_PLATFORM_RECOVERY,
            requested_by=self.admin,
            justification="User lost both password and recovery phrase",
        )

        # Generate custodian component and shares
        custodian_component = os.urandom(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Mock the vault client
        with patch("checktick_app.surveys.management.commands.execute_platform_recovery.VaultClient") as mock_vault_class:
            mock_vault = MagicMock()
            mock_vault_class.return_value = mock_vault

            # Mock vault component retrieval
            vault_component = os.urandom(64)
            mock_vault.get_vault_component.return_value = vault_component

            # Mock the recovery method
            mock_vault.recover_user_survey_kek.return_value = True

            out = StringIO()
            call_command(
                "execute_platform_recovery",
                f"--recovery-request-id={recovery_request.id}",
                f"--custodian-share={shares[0]}",
                f"--custodian-share={shares[1]}",
                f"--custodian-share={shares[2]}",
                "--new-password=TempPassword123!",
                "--audit-approved-by=admin@example.com",
                stdout=out,
            )

            output = out.getvalue()

            # Verify output
            assert "Platform Recovery Execution" in output
            assert "Custodian component reconstructed from 3 shares" in output

    def test_recovery_command_missing_recovery_request(self):
        """Test that command fails when recovery request doesn't exist."""
        custodian_component = os.urandom(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        with pytest.raises(CommandError, match="Recovery request .* not found"):
            call_command(
                "execute_platform_recovery",
                "--recovery-request-id=99999",
                f"--custodian-share={shares[0]}",
                f"--custodian-share={shares[1]}",
                f"--custodian-share={shares[2]}",
                "--new-password=TempPassword123!",
                "--audit-approved-by=admin@example.com",
            )

    def test_recovery_command_wrong_status(self):
        """Test that command fails if recovery request has wrong status."""
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.COMPLETED,  # Wrong status
            requested_by=self.admin,
            justification="Test",
        )

        custodian_component = os.urandom(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        with pytest.raises(CommandError, match="Recovery request .* is not in PENDING_PLATFORM_RECOVERY status"):
            call_command(
                "execute_platform_recovery",
                f"--recovery-request-id={recovery_request.id}",
                f"--custodian-share={shares[0]}",
                f"--custodian-share={shares[1]}",
                f"--custodian-share={shares[2]}",
                "--new-password=TempPassword123!",
                "--audit-approved-by=admin@example.com",
            )

    def test_recovery_command_insufficient_shares(self):
        """Test that command requires at least 3 shares."""
        recovery_request = RecoveryRequest.objects.create(
            user=self.user,
            survey=self.survey,
            status=RecoveryRequest.Status.PENDING_PLATFORM_RECOVERY,
            requested_by=self.admin,
            justification="Test",
        )

        custodian_component = os.urandom(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Try with only 2 shares
        with pytest.raises(CommandError, match="At least 3 custodian shares are required"):
            call_command(
                "execute_platform_recovery",
                f"--recovery-request-id={recovery_request.id}",
                f"--custodian-share={shares[0]}",
                f"--custodian-share={shares[1]}",
                "--new-password=TempPassword123!",
                "--audit-approved-by=admin@example.com",
            )


class TestCommandIntegration(TestCase):
    """Integration tests for command workflows."""

    def test_split_and_verify_workflow(self):
        """Test the complete split → verify workflow."""
        # Step 1: Split a custodian component
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        split_out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=split_out,
        )

        split_output = split_out.getvalue()

        # Extract shares from output
        lines = split_output.split("\n")
        shares = []
        for i, line in enumerate(lines):
            if line.startswith(("Share 1/4:", "Share 2/4:", "Share 3/4:", "Share 4/4:")):
                share = lines[i + 1].strip()
                if share:
                    shares.append(share)

        # Step 2: Verify the shares reconstruct correctly
        verify_out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            f"--original={component_hex}",
            stdout=verify_out,
        )

        verify_output = verify_out.getvalue()

        # Should show success
        assert "SUCCESS: Reconstructed component matches original" in verify_output

    def test_different_share_combinations(self):
        """Test that any 3 of 4 shares work for reconstruction."""
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        # Split into shares
        split_out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=split_out,
        )

        # Extract all 4 shares
        lines = split_out.getvalue().split("\n")
        shares = []
        for i, line in enumerate(lines):
            if line.startswith(("Share 1/4:", "Share 2/4:", "Share 3/4:", "Share 4/4:")):
                share = lines[i + 1].strip()
                if share:
                    shares.append(share)

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
                combo[0],
                combo[1],
                combo[2],
                f"--original={component_hex}",
                stdout=verify_out,
            )

            verify_output = verify_out.getvalue()
            assert "SUCCESS" in verify_output


class TestCommandSecurityProperties(TestCase):
    """Test security properties of the commands."""

    def test_shares_are_different_each_time(self):
        """Test that splitting the same component twice produces different shares."""
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        # Split twice
        out1 = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=out1,
        )

        out2 = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=out2,
        )

        # Outputs should be different (different shares due to random polynomial)
        assert out1.getvalue() != out2.getvalue()

    def test_command_output_includes_security_warnings(self):
        """Test that commands include appropriate security warnings."""
        custodian_component = os.urandom(64)
        component_hex = custodian_component.hex()

        out = StringIO()
        call_command(
            "split_custodian_component",
            f"--custodian-component={component_hex}",
            stdout=out,
        )

        output = out.getvalue()

        # Should include security instructions
        assert "SECURITY INSTRUCTIONS" in output
        assert "Distribute each share to a different custodian" in output
        assert "Delete this terminal output after distribution" in output
        assert "NEVER store the original custodian component" in output

    def test_reconstruction_hides_sensitive_data_appropriately(self):
        """Test that reconstruction command displays data appropriately."""
        custodian_component = os.urandom(64)
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        out = StringIO()
        call_command(
            "test_custodian_reconstruction",
            shares[0],
            shares[1],
            shares[2],
            stdout=out,
        )

        output = out.getvalue()

        # Should show the reconstructed component (admin needs to verify)
        assert "Reconstructed Component (hex):" in output
        assert custodian_component.hex() in output
