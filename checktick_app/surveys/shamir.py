"""
Shamir's Secret Sharing implementation for custodian component splitting.

This implements a simple, secure Shamir's Secret Sharing scheme for splitting
the custodian component into multiple shares with a threshold for reconstruction.

Based on Adi Shamir's "How to Share a Secret" (1979).
"""

import secrets
from typing import List, Tuple

# Use a large prime for the field (1024-bit prime to support 64-byte/512-bit secrets)
# RFC 3526 MODP Group 2 - well-known safe prime
PRIME = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)


def _eval_poly(coefficients: List[int], x: int, prime: int) -> int:
    """Evaluate polynomial at x using Horner's method."""
    result = 0
    for coeff in reversed(coefficients):
        result = (result * x + coeff) % prime
    return result


def _lagrange_interpolate(shares: List[Tuple[int, int]], prime: int) -> int:
    """
    Reconstruct secret using Lagrange interpolation at x=0.

    Args:
        shares: List of (x, y) coordinate tuples
        prime: Prime modulus for field arithmetic

    Returns:
        The secret value (polynomial value at x=0)
    """
    secret = 0
    x_values = [share[0] for share in shares]

    for i, (x_i, y_i) in enumerate(shares):
        # Calculate Lagrange basis polynomial at x=0
        numerator = 1
        denominator = 1

        for j, x_j in enumerate(x_values):
            if i != j:
                numerator = (numerator * (0 - x_j)) % prime
                denominator = (denominator * (x_i - x_j)) % prime

        # Compute modular inverse of denominator
        lagrange_basis = (numerator * pow(denominator, -1, prime)) % prime
        secret = (secret + y_i * lagrange_basis) % prime

    return secret


def split_secret(secret_bytes: bytes, threshold: int, total_shares: int) -> List[str]:
    """
    Split a secret into multiple shares using Shamir's Secret Sharing.

    Args:
        secret_bytes: The secret to split (arbitrary length)
        threshold: Minimum number of shares needed to reconstruct
        total_shares: Total number of shares to create

    Returns:
        List of share strings in format "ID-X-Y" where:
        - ID is the share index (1-based)
        - X is the x-coordinate
        - Y is the y-coordinate (hex)

    Raises:
        ValueError: If parameters are invalid
    """
    if threshold > total_shares:
        raise ValueError("Threshold cannot exceed total shares")
    if threshold < 2:
        raise ValueError("Threshold must be at least 2")
    if total_shares < 2:
        raise ValueError("Must create at least 2 shares")
    if not secret_bytes:
        raise ValueError("Secret cannot be empty")

    # Convert secret bytes to integer
    secret_int = int.from_bytes(secret_bytes, byteorder="big")

    if secret_int >= PRIME:
        raise ValueError("Secret too large for field")

    # Generate random polynomial coefficients
    # f(x) = secret + c1*x + c2*x^2 + ... + c(threshold-1)*x^(threshold-1)
    coefficients = [secret_int]
    for _ in range(threshold - 1):
        coeff = secrets.randbelow(PRIME)
        coefficients.append(coeff)

    # Generate shares by evaluating polynomial at different x values
    shares = []
    for i in range(1, total_shares + 1):
        x = i
        y = _eval_poly(coefficients, x, PRIME)

        # Format: "shareID-x-y_hex" (256 hex chars for 1024-bit field)
        share_str = f"80{i}-{x}-{y:0256x}"
        shares.append(share_str)

    return shares


def reconstruct_secret(share_strings: List[str]) -> bytes:
    """
    Reconstruct the secret from shares.

    Args:
        share_strings: List of share strings in format "ID-X-Y"

    Returns:
        The original secret as bytes

    Raises:
        ValueError: If shares are invalid or insufficient
    """
    if len(share_strings) < 2:
        raise ValueError("Need at least 2 shares to reconstruct")

    # Parse shares
    shares = []
    for share_str in share_strings:
        try:
            parts = share_str.split("-")
            if len(parts) != 3:
                raise ValueError(f"Invalid share format: {share_str}")

            # parts[0] is ID (80X), parts[1] is x, parts[2] is y in hex
            x = int(parts[1])
            y = int(parts[2], 16)
            shares.append((x, y))
        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to parse share: {share_str}. Error: {e}")

    # Reconstruct secret using Lagrange interpolation
    secret_int = _lagrange_interpolate(shares, PRIME)

    # Convert back to bytes (64 bytes for custodian component)
    secret_bytes = secret_int.to_bytes(64, byteorder="big")

    return secret_bytes
