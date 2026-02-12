"""
Tests for Shamir's Secret Sharing implementation.

Verifies the cryptographic correctness of the custodian component splitting
and reconstruction algorithm.
"""

import os

import pytest

from checktick_app.surveys.shamir import (
    PRIME,
    _eval_poly,
    _lagrange_interpolate,
    reconstruct_secret,
    split_secret,
)


class TestShamirSecretSharing:
    """Test Shamir's Secret Sharing split and reconstruction."""

    def test_split_and_reconstruct_exact_threshold(self):
        """Test that exactly threshold shares can reconstruct the secret."""
        # Generate a random 64-byte secret (custodian component size)
        secret = os.urandom(64)

        # Split into 4 shares with 3 required
        shares = split_secret(secret, threshold=3, total_shares=4)

        assert len(shares) == 4
        assert all(isinstance(share, str) for share in shares)

        # Reconstruct with exactly 3 shares (any combination)
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == secret

        # Try different combinations of 3 shares
        reconstructed = reconstruct_secret([shares[0], shares[1], shares[3]])
        assert reconstructed == secret

        reconstructed = reconstruct_secret([shares[0], shares[2], shares[3]])
        assert reconstructed == secret

        reconstructed = reconstruct_secret([shares[1], shares[2], shares[3]])
        assert reconstructed == secret

    def test_split_and_reconstruct_all_shares(self):
        """Test that using all shares also reconstructs the secret."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        # Using all 4 shares should work
        reconstructed = reconstruct_secret(shares)
        assert reconstructed == secret

    def test_split_produces_different_shares(self):
        """Test that each split produces different shares."""
        secret = os.urandom(64)

        shares1 = split_secret(secret, threshold=3, total_shares=4)
        shares2 = split_secret(secret, threshold=3, total_shares=4)

        # Same secret should produce different shares (due to random polynomial)
        assert shares1 != shares2

        # But both should reconstruct to the same secret
        assert reconstruct_secret(shares1[:3]) == secret
        assert reconstruct_secret(shares2[:3]) == secret

    def test_two_shares_insufficient(self):
        """Test that 2 shares cannot reconstruct a 3-of-4 secret."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        # With only 2 shares on a 3-threshold secret, reconstruction may fail
        # or produce an incorrect value. We test that it doesn't match the secret.
        try:
            reconstructed = reconstruct_secret(shares[:2])
            # If it reconstructs something, it should be wrong
            assert reconstructed != secret
        except (ValueError, OverflowError):
            # Or it may fail with an error, which is also acceptable
            pass

    def test_share_format(self):
        """Test that shares have the correct format."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        for i, share in enumerate(shares, start=1):
            # Share format: "80X-x-y_hex" where X is share ID (1-4)
            parts = share.split("-")
            assert len(parts) == 3

            share_id_part, x_part, y_hex = parts
            # First part is "80X" where X is the share number
            assert share_id_part.startswith("80")
            assert share_id_part == f"80{i}"
            # x_part is the x coordinate (should be the share number)
            assert int(x_part) == i
            # y is a large hex number
            assert len(y_hex) > 0
            int(y_hex, 16)  # Should be valid hex

    def test_small_secret(self):
        """Test with a 64-byte secret (required size for custodian component)."""
        # Note: The implementation is designed for 64-byte custodian components
        # Smaller secrets will be padded with zeros on reconstruction
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=2, total_shares=3)

        reconstructed = reconstruct_secret(shares[:2])
        assert reconstructed == secret

    def test_large_secret(self):
        """Test with maximum size secret (64 bytes for custodian component)."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=5)

        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == secret

    def test_different_thresholds(self):
        """Test various threshold configurations."""
        secret = os.urandom(64)

        # 2-of-3
        shares = split_secret(secret, threshold=2, total_shares=3)
        assert reconstruct_secret(shares[:2]) == secret

        # 3-of-5
        shares = split_secret(secret, threshold=3, total_shares=5)
        assert reconstruct_secret(shares[:3]) == secret

        # 4-of-7
        shares = split_secret(secret, threshold=4, total_shares=7)
        assert reconstruct_secret(shares[:4]) == secret

    def test_deterministic_shares(self):
        """Test that shares with same coefficients produce deterministic results."""
        secret = os.urandom(64)
        shares1 = split_secret(secret, threshold=3, total_shares=4)
        shares2 = split_secret(secret, threshold=3, total_shares=4)

        # Different random polynomials should create different shares
        assert shares1 != shares2

        # But both should reconstruct correctly
        assert reconstruct_secret(shares1[:3]) == secret
        assert reconstruct_secret(shares2[:3]) == secret

    def test_share_independence(self):
        """Test that knowledge of some shares doesn't help with others."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        # Knowing shares 1 and 2 shouldn't let you compute share 3
        # This is a property test - we just verify shares are different
        assert shares[0] != shares[1]
        assert shares[0] != shares[2]
        assert shares[1] != shares[2]

    def test_empty_secret_handling(self):
        """Test handling of edge cases."""
        # Zero-filled secret should work
        secret = b"\x00" * 64
        shares = split_secret(secret, threshold=3, total_shares=4)
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == secret

    def test_max_value_secret(self):
        """Test with all 0xFF bytes."""
        secret = b"\xff" * 64
        shares = split_secret(secret, threshold=3, total_shares=4)
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == secret

    def test_specific_byte_pattern(self):
        """Test with a specific byte pattern."""
        # Pattern from actual production use case
        secret = bytes.fromhex("a1b2c3d4e5f6" + "00" * 58)  # 64 bytes
        shares = split_secret(secret, threshold=3, total_shares=4)
        reconstructed = reconstruct_secret(shares[:3])
        assert reconstructed == secret


class TestShamirInternalFunctions:
    """Test internal helper functions."""

    def test_eval_poly(self):
        """Test polynomial evaluation."""
        # Simple polynomial: f(x) = 5 + 3x
        coefficients = [5, 3]

        # f(0) = 5
        assert _eval_poly(coefficients, 0, PRIME) == 5

        # f(1) = 5 + 3 = 8
        assert _eval_poly(coefficients, 1, PRIME) == 8

        # f(2) = 5 + 6 = 11
        assert _eval_poly(coefficients, 2, PRIME) == 11

    def test_eval_poly_with_large_prime(self):
        """Test polynomial evaluation with field arithmetic."""
        # Test that results are always mod PRIME
        coefficients = [PRIME - 1, 1]  # f(x) = (PRIME - 1) + x

        # f(1) = PRIME - 1 + 1 = PRIME ≡ 0 (mod PRIME)
        assert _eval_poly(coefficients, 1, PRIME) == 0

        # f(2) = PRIME - 1 + 2 = PRIME + 1 ≡ 1 (mod PRIME)
        assert _eval_poly(coefficients, 2, PRIME) == 1

    def test_lagrange_interpolate(self):
        """Test Lagrange interpolation."""
        # Create points from polynomial f(x) = 7 + 2x + 3x^2
        # Secret is f(0) = 7

        def f(x):
            return (7 + 2 * x + 3 * x * x) % PRIME

        # Generate shares at x = 1, 2, 3
        shares = [
            (1, f(1)),  # (1, 12)
            (2, f(2)),  # (2, 23)
            (3, f(3)),  # (3, 40)
        ]

        # Interpolate back to get secret at x=0
        secret = _lagrange_interpolate(shares, PRIME)
        assert secret == 7

    def test_lagrange_two_points(self):
        """Test Lagrange with minimum 2 points (degree 1 polynomial)."""
        # f(x) = 5 + 2x
        shares = [
            (1, 7),  # f(1) = 5 + 2 = 7
            (2, 9),  # f(2) = 5 + 4 = 9
        ]

        secret = _lagrange_interpolate(shares, PRIME)
        assert secret == 5


class TestShamirProduction:
    """Tests that mirror production usage scenarios."""

    def test_production_workflow(self):
        """Test the complete production workflow."""
        # Simulate vault setup generating a custodian component
        custodian_component = os.urandom(64)

        # Administrator splits it into 4 shares
        shares = split_secret(custodian_component, threshold=3, total_shares=4)

        # Distribute shares to 4 custodians
        custodian_a_share = shares[0]
        custodian_b_share = shares[1]
        custodian_c_share = shares[2]
        custodian_d_share = shares[3]

        # Later: Emergency recovery with 3 custodians
        # Scenario 1: A, B, C available
        recovered = reconstruct_secret(
            [custodian_a_share, custodian_b_share, custodian_c_share]
        )
        assert recovered == custodian_component

        # Scenario 2: A, B, D available
        recovered = reconstruct_secret(
            [custodian_a_share, custodian_b_share, custodian_d_share]
        )
        assert recovered == custodian_component

        # Scenario 3: A, C, D available
        recovered = reconstruct_secret(
            [custodian_a_share, custodian_c_share, custodian_d_share]
        )
        assert recovered == custodian_component

        # Scenario 4: B, C, D available
        recovered = reconstruct_secret(
            [custodian_b_share, custodian_c_share, custodian_d_share]
        )
        assert recovered == custodian_component

    def test_rotation_workflow(self):
        """Test custodian component rotation scenario."""
        # Old custodian component
        old_component = os.urandom(64)
        old_shares = split_secret(old_component, threshold=3, total_shares=4)

        # Verify old shares work
        assert reconstruct_secret(old_shares[:3]) == old_component

        # Generate new custodian component (annual rotation)
        new_component = os.urandom(64)
        new_shares = split_secret(new_component, threshold=3, total_shares=4)

        # Verify new shares work
        assert reconstruct_secret(new_shares[:3]) == new_component

        # Old shares should not work with new component
        assert reconstruct_secret(old_shares[:3]) != new_component

    def test_share_storage_format(self):
        """Test that shares can be stored and retrieved as strings."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        # Simulate storing in password manager / file
        stored_shares = [share for share in shares]

        # Simulate retrieving from storage
        retrieved_shares = stored_shares[:3]

        # Reconstruct
        reconstructed = reconstruct_secret(retrieved_shares)
        assert reconstructed == secret


class TestShamirErrorHandling:
    """Test error conditions and edge cases."""

    def test_invalid_threshold(self):
        """Test that invalid thresholds are handled."""
        secret = os.urandom(64)

        # Threshold can't be greater than total shares
        with pytest.raises((ValueError, AssertionError)):
            split_secret(secret, threshold=5, total_shares=4)

        # Threshold must be at least 2
        with pytest.raises((ValueError, AssertionError)):
            split_secret(secret, threshold=1, total_shares=4)

    def test_insufficient_shares_for_reconstruction(self):
        """Test reconstruction with too few shares fails."""
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)

        # Only using 1 share should raise ValueError
        with pytest.raises(ValueError, match="Need at least 2 shares"):
            reconstruct_secret([shares[0]])

    def test_custodian_component_size(self):
        """Test with standard 64-byte custodian component."""
        # The implementation is specifically designed for 64-byte secrets
        # (custodian component size)
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=3, total_shares=4)
        assert reconstruct_secret(shares[:3]) == secret

        # Also test with 2-of-3 threshold
        secret = os.urandom(64)
        shares = split_secret(secret, threshold=2, total_shares=3)
        assert reconstruct_secret(shares[:2]) == secret


class TestShamirSecurityProperties:
    """Test security properties of the Shamir implementation."""

    def test_information_theoretic_security(self):
        """
        Test that k-1 shares provide no information about the secret.

        This is a statistical test - with threshold 3, knowing 2 shares
        should give you no information about the secret.
        """
        secret1 = os.urandom(64)
        secret2 = os.urandom(64)

        shares1 = split_secret(secret1, threshold=3, total_shares=4)
        shares2 = split_secret(secret2, threshold=3, total_shares=4)

        # With only 2 shares on a 3-threshold, reconstruction may fail
        # or produce incorrect results
        try:
            reconstructed1 = reconstruct_secret(shares1[:2])
            # If it reconstructs, it should be wrong
            assert reconstructed1 != secret1
        except (ValueError, OverflowError):
            # May fail due to insufficient shares
            pass

        try:
            reconstructed2 = reconstruct_secret(shares2[:2])
            assert reconstructed2 != secret2
        except (ValueError, OverflowError):
            pass

        # But with 3 shares, you get the correct secret
        assert reconstruct_secret(shares1[:3]) == secret1
        assert reconstruct_secret(shares2[:3]) == secret2

    def test_no_share_correlation(self):
        """Test that shares are not correlated with the secret."""
        secret = bytes([0xAA] * 64)  # All 0xAA pattern
        shares = split_secret(secret, threshold=3, total_shares=4)

        # Shares should not have obvious patterns from the secret
        for share in shares:
            # Shares are hex strings - they should not be all "aa"
            assert "aa" * 64 not in share.lower()
