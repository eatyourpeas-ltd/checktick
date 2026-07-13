from __future__ import annotations

from datetime import datetime
import json
import os
import secrets
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from django.utils import timezone
from django.utils.dateparse import parse_datetime as _parse_datetime


def parse_datetime_aware(value: Optional[str]) -> Optional[datetime]:
    """
    Parse a datetime string from form input into a timezone-aware datetime.

    Form fields submit values like ``2026-07-13T17:49`` with no offset, so
    ``django.utils.dateparse.parse_datetime`` returns a naive datetime, which
    triggers ``RuntimeWarning: DateTimeField received a naive datetime`` when
    ``USE_TZ`` is active. This helper localizes naive results to the current
    timezone so they can be safely assigned to model fields.

    Returns ``None`` if ``value`` is falsy or unparseable.
    """
    if not value:
        return None
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


# BIP39 English word list (first 100 words for brevity - full list has 2048)
# In production, use the complete BIP39 wordlist
BIP39_WORDLIST = [
    "abandon",
    "ability",
    "able",
    "about",
    "above",
    "absent",
    "absorb",
    "abstract",
    "absurd",
    "abuse",
    "access",
    "accident",
    "account",
    "accuse",
    "achieve",
    "acid",
    "acoustic",
    "acquire",
    "across",
    "act",
    "action",
    "actor",
    "actress",
    "actual",
    "adapt",
    "add",
    "addict",
    "address",
    "adjust",
    "admit",
    "adult",
    "advance",
    "advice",
    "aerobic",
    "affair",
    "afford",
    "afraid",
    "again",
    "age",
    "agent",
    "agree",
    "ahead",
    "aim",
    "air",
    "airport",
    "aisle",
    "alarm",
    "album",
    "alcohol",
    "alert",
    "alien",
    "all",
    "alley",
    "allow",
    "almost",
    "alone",
    "alpha",
    "already",
    "also",
    "alter",
    "always",
    "amateur",
    "amazing",
    "among",
    "amount",
    "amused",
    "analyst",
    "anchor",
    "ancient",
    "anger",
    "angle",
    "angry",
    "animal",
    "ankle",
    "announce",
    "annual",
    "another",
    "answer",
    "antenna",
    "antique",
    "anxiety",
    "any",
    "apart",
    "apology",
    "appear",
    "apple",
    "approve",
    "april",
    "arch",
    "arctic",
    "area",
    "arena",
    "argue",
    "arm",
    "armed",
    "armor",
    "army",
    "around",
    "arrange",
    "arrest",
    "arrive",
    "arrow",
    "art",
    "artefact",
    # Add more words to reach 2048 for production use
    "artist",
    "artwork",
    "ask",
    "aspect",
    "assault",
    "asset",
    "assist",
    "assume",
    "asthma",
    "athlete",
    "atom",
    "attack",
    "attend",
    "attitude",
    "attract",
    "auction",
    "audit",
    "august",
    "aunt",
    "author",
    "auto",
    "autumn",
    "average",
    "avocado",
    "avoid",
    "awake",
    "aware",
    "away",
    "awesome",
    "awful",
    "awkward",
    "axis",
    "baby",
    "bachelor",
    "bacon",
    "badge",
    "bag",
    "balance",
    "balcony",
    "ball",
    "bamboo",
    "banana",
    "banner",
    "bar",
    "barely",
    "bargain",
    "barrel",
    "base",
    "basic",
    "basket",
    "battle",
    "beach",
    "bean",
    "beauty",
    "because",
    "become",
    "beef",
    "before",
    "begin",
    "behave",
    "behind",
    "believe",
    "below",
    "belt",
    "bench",
    "benefit",
    "best",
    "betray",
    "better",
    "between",
    "beyond",
    "bicycle",
    "bid",
    "bike",
    "bind",
    "biology",
    "bird",
    "birth",
    "bitter",
    "black",
    "blade",
    "blame",
    "blanket",
    "blast",
    "bleak",
    "bless",
    "blind",
    "blood",
    "blossom",
    "blouse",
    "blue",
    "blur",
    "blush",
    "board",
    "boat",
    "body",
    "boil",
    "bomb",
    "bone",
    "bonus",
    "book",
    "boost",
    "border",
    "boring",
    "borrow",
    "boss",
    "bottom",
    "bounce",
    "box",
    "boy",
    "bracket",
    "brain",
    "brand",
    "brass",
    "brave",
    "bread",
    "breeze",
    "brick",
    "bridge",
    "brief",
    "bright",
    "bring",
    "brisk",
    "broccoli",
    "broken",
    "bronze",
    "broom",
    "brother",
    "brown",
    "brush",
    "bubble",
    "buddy",
    "budget",
    "buffalo",
    "build",
    "bulb",
    "bulk",
    "bullet",
    "bundle",
    "bunker",
    "burden",
    "burger",
    "burst",
    "bus",
    "business",
    "busy",
    "butter",
    "buyer",
    "buzz",
    "cabbage",
    "cabin",
    "cable",
]


def derive_key(passphrase: bytes, salt: bytes | None = None) -> Tuple[bytes, bytes]:
    if salt is None:
        salt = os.urandom(16)
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(passphrase)
    return key, salt


def encrypt_sensitive(passphrase_key: bytes, data: dict) -> bytes:
    key, salt = derive_key(passphrase_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode("utf-8")
    ct = aesgcm.encrypt(nonce, plaintext, None)
    # store salt | nonce | ct
    return salt + nonce + ct


def decrypt_sensitive(passphrase_key: bytes, blob: bytes) -> dict:
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(passphrase_key)
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(nonce, ct, None)
    return json.loads(pt.decode("utf-8"))


def make_key_hash(key: bytes) -> tuple[bytes, bytes]:
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000
    )
    digest = kdf.derive(key)
    return digest, salt


def verify_key(key: bytes, digest: bytes, salt: bytes) -> bool:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000
    )
    try:
        kdf.verify(key, digest)
        return True
    except Exception:
        return False


def demographics_fingerprint(key: bytes, demographics: dict) -> bytes:
    # Create a stable representation
    payload = json.dumps(demographics, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(payload)
    return h.finalize()


def generate_bip39_phrase(word_count: int = 12) -> list[str]:
    """
    Generate a BIP39-style mnemonic phrase.

    Args:
        word_count: Number of words (12, 15, 18, 21, or 24)

    Returns:
        List of randomly selected words from BIP39 wordlist

    Note: This is a simplified implementation. For production use with
    actual BIP39 wallets, use a proper BIP39 library that includes
    checksum validation.
    """
    if word_count not in [12, 15, 18, 21, 24]:
        raise ValueError("Word count must be 12, 15, 18, 21, or 24")

    # Use cryptographically secure random selection
    return [secrets.choice(BIP39_WORDLIST) for _ in range(word_count)]


def derive_key_from_passphrase(
    phrase: str, salt: bytes, iterations: int = 200_000
) -> bytes:
    """
    Derive a 32-byte encryption key from a BIP39 recovery phrase.

    Args:
        phrase: Space-separated recovery phrase (e.g., "word1 word2 word3...")
        salt: 16-byte salt for key derivation
        iterations: PBKDF2 iteration count (default 200,000)

    Returns:
        32-byte encryption key suitable for AES-256

    The phrase is normalized (lowercased, whitespace-stripped) before
    deriving the key to ensure consistency.
    """
    # Normalize the phrase
    normalized = " ".join(phrase.lower().split())
    phrase_bytes = normalized.encode("utf-8")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
    )
    return kdf.derive(phrase_bytes)


def encrypt_kek_with_passphrase(kek: bytes, passphrase: str | bytes) -> bytes:
    """
    Encrypt a Key Encryption Key (KEK) with a user passphrase or recovery phrase.

    Args:
        kek: The 32-byte survey encryption key to protect
        passphrase: User password or recovery phrase (string or bytes)

    Returns:
        Binary blob containing: salt (16) | nonce (12) | ciphertext

    This uses Scrypt for password-based key derivation and AES-GCM for encryption.
    """
    if isinstance(passphrase, str):
        # Normalize: lowercase and collapse whitespace for recovery phrases
        passphrase = " ".join(passphrase.lower().split())
        passphrase = passphrase.encode("utf-8")

    # Derive encryption key from passphrase
    derived_key, salt = derive_key(passphrase)

    # Encrypt the KEK
    aesgcm = AESGCM(derived_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, kek, None)

    # Return: salt | nonce | ciphertext
    return salt + nonce + ciphertext


def decrypt_kek_with_passphrase(
    encrypted_blob: bytes, passphrase: str | bytes
) -> bytes:
    """
    Decrypt a Key Encryption Key (KEK) using a user passphrase or recovery phrase.

    Args:
        encrypted_blob: Binary blob from encrypt_kek_with_passphrase
        passphrase: User password or recovery phrase (string or bytes)

    Returns:
        32-byte decrypted survey encryption key (KEK)

    Raises:
        cryptography.exceptions.InvalidTag: If passphrase is incorrect
    """
    # Convert memoryview to bytes (PostgreSQL BinaryField returns memoryview)
    if isinstance(encrypted_blob, memoryview):
        encrypted_blob = bytes(encrypted_blob)

    if isinstance(passphrase, str):
        # Normalize: lowercase and collapse whitespace for recovery phrases
        passphrase = " ".join(passphrase.lower().split())
        passphrase = passphrase.encode("utf-8")

    # Parse blob
    salt, nonce, ciphertext = (
        encrypted_blob[:16],
        encrypted_blob[16:28],
        encrypted_blob[28:],
    )

    # Derive decryption key from passphrase
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    derived_key = kdf.derive(passphrase)

    # Decrypt the KEK
    aesgcm = AESGCM(derived_key)
    kek = aesgcm.decrypt(nonce, ciphertext, None)

    return kek


def create_recovery_hint(phrase_words: list[str]) -> str:
    """
    Create a hint showing first and last word of recovery phrase.

    Args:
        phrase_words: List of recovery phrase words

    Returns:
        Hint string like "apple...zebra"
    """
    if not phrase_words:
        return ""
    if len(phrase_words) == 1:
        return phrase_words[0]
    return f"{phrase_words[0]}...{phrase_words[-1]}"


# OIDC Encryption Integration
def derive_key_from_oidc_identity(
    oidc_provider: str, oidc_subject: str, user_salt: bytes
) -> bytes:
    """
    Derive encryption key from OIDC identity for automatic survey unlocking.

    This creates a stable encryption key based on the user's OIDC identity
    that doesn't change when they change their password at the provider.

    Args:
        oidc_provider: Provider name (e.g., 'google', 'azure')
        oidc_subject: OIDC subject identifier (stable per user)
        user_salt: Unique salt for this user from UserOIDC.key_derivation_salt

    Returns:
        32-byte encryption key
    """
    # Combine provider + subject for uniqueness across providers
    identity = f"{oidc_provider}:{oidc_subject}".encode("utf-8")

    # Use PBKDF2 with the user's unique salt for key derivation
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=user_salt,
        iterations=100000,  # Same as password-based encryption
    )

    return kdf.derive(identity)


def encrypt_kek_with_oidc(
    kek: bytes, oidc_provider: str, oidc_subject: str, user_salt: bytes
) -> bytes:
    """
    Encrypt a Key Encryption Key (KEK) with OIDC-derived key for automatic unlock.

    Args:
        kek: The 32-byte survey encryption key to protect
        oidc_provider: OIDC provider name
        oidc_subject: OIDC subject identifier
        user_salt: User's unique salt from UserOIDC

    Returns:
        Binary blob containing encrypted KEK (nonce + ciphertext)
    """
    # Derive encryption key from OIDC identity
    derived_key = derive_key_from_oidc_identity(oidc_provider, oidc_subject, user_salt)

    # Encrypt the KEK
    aesgcm = AESGCM(derived_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, kek, None)

    # Return: nonce | ciphertext (no salt needed since user_salt is stored separately)
    return nonce + ciphertext


def decrypt_kek_with_oidc(
    encrypted_blob: bytes, oidc_provider: str, oidc_subject: str, user_salt: bytes
) -> bytes:
    """
    Decrypt a Key Encryption Key (KEK) using OIDC-derived key.

    Args:
        encrypted_blob: Binary blob from encrypt_kek_with_oidc
        oidc_provider: OIDC provider name
        oidc_subject: OIDC subject identifier
        user_salt: User's unique salt from UserOIDC

    Returns:
        32-byte decrypted survey encryption key (KEK)

    Raises:
        cryptography.exceptions.InvalidTag: If OIDC identity doesn't match
    """
    # Convert memoryview to bytes (PostgreSQL BinaryField returns memoryview)
    if isinstance(encrypted_blob, memoryview):
        encrypted_blob = bytes(encrypted_blob)

    # Parse blob: nonce (12) | ciphertext
    nonce, ciphertext = encrypted_blob[:12], encrypted_blob[12:]

    # Derive decryption key from OIDC identity
    derived_key = derive_key_from_oidc_identity(oidc_provider, oidc_subject, user_salt)

    # Decrypt the KEK
    aesgcm = AESGCM(derived_key)
    kek = aesgcm.decrypt(nonce, ciphertext, None)

    return kek


def encrypt_kek_with_org_key(kek: bytes, org_master_key: bytes) -> bytes:
    """
    Encrypt a Key Encryption Key (KEK) with organization master key.

    Args:
        kek: The 32-byte survey encryption key to protect
        org_master_key: Organization's master key (32 bytes)
                       In production, this should come from KMS (AWS/Azure)

    Returns:
        Binary blob containing encrypted KEK (nonce + ciphertext)
    """
    # Convert memoryview to bytes if needed
    if isinstance(org_master_key, memoryview):
        org_master_key = bytes(org_master_key)

    # Validate key size
    if len(org_master_key) != 32:
        raise ValueError("Organization master key must be 32 bytes")

    # Encrypt the KEK with organization master key
    aesgcm = AESGCM(org_master_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, kek, None)

    # Return: nonce | ciphertext
    return nonce + ciphertext


def decrypt_kek_with_org_key(encrypted_blob: bytes, org_master_key: bytes) -> bytes:
    """
    Decrypt a Key Encryption Key (KEK) using organization master key.

    Args:
        encrypted_blob: Binary blob from encrypt_kek_with_org_key
        org_master_key: Organization's master key (32 bytes)
                       In production, this should come from KMS (AWS/Azure)

    Returns:
        32-byte decrypted survey encryption key (KEK)

    Raises:
        cryptography.exceptions.InvalidTag: If organization key doesn't match
    """
    # Convert memoryview to bytes if needed
    if isinstance(encrypted_blob, memoryview):
        encrypted_blob = bytes(encrypted_blob)
    if isinstance(org_master_key, memoryview):
        org_master_key = bytes(org_master_key)

    # Validate key size
    if len(org_master_key) != 32:
        raise ValueError("Organization master key must be 32 bytes")

    # Parse blob: nonce (12) | ciphertext
    nonce, ciphertext = encrypted_blob[:12], encrypted_blob[12:]

    # Decrypt the KEK with organization master key
    aesgcm = AESGCM(org_master_key)
    kek = aesgcm.decrypt(nonce, ciphertext, None)

    return kek
