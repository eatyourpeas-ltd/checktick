"""Tests for custom password validators."""

from pathlib import Path

from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError
import pytest

from checktick_app.core.password_validators import (
    ComplexityValidator,
    NoRepeatingCharactersValidator,
    NoSequentialCharactersValidator,
)


class TestComplexityValidator:
    """Tests for ComplexityValidator."""

    def test_valid_password_with_three_types(self):
        """Password with 3 character types should pass."""
        validator = ComplexityValidator(min_character_types=3)
        # uppercase, lowercase, digit
        validator.validate("Abcdefgh123")
        # uppercase, lowercase, special
        validator.validate("Abcdefgh!@#")
        # lowercase, digit, special
        validator.validate("abcdefgh123!")

    def test_valid_password_with_four_types(self):
        """Password with all 4 character types should pass."""
        validator = ComplexityValidator(min_character_types=3)
        validator.validate("Abcdefgh123!")

    def test_invalid_password_lowercase_only(self):
        """Lowercase only should fail."""
        validator = ComplexityValidator(min_character_types=3)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("abcdefghijkl")
        assert exc_info.value.code == "password_too_simple"

    def test_invalid_password_two_types(self):
        """Only 2 character types should fail."""
        validator = ComplexityValidator(min_character_types=3)
        # lowercase + uppercase only
        with pytest.raises(ValidationError):
            validator.validate("Abcdefghijkl")
        # lowercase + digits only
        with pytest.raises(ValidationError):
            validator.validate("abcdefgh1234")

    def test_special_characters_recognized(self):
        """Various special characters should be recognized."""
        validator = ComplexityValidator(min_character_types=3)
        special_chars = "!@#$%^&*()-_=+[]{}|;:'\",.<>/?"
        for char in special_chars:
            # lowercase + uppercase + special
            validator.validate(f"Abcdefghijk{char}")

    def test_get_help_text(self):
        """Help text should be returned."""
        validator = ComplexityValidator(min_character_types=3)
        help_text = validator.get_help_text()
        assert "3" in help_text
        assert "uppercase" in help_text.lower()


class TestNoRepeatingCharactersValidator:
    """Tests for NoRepeatingCharactersValidator."""

    def test_valid_password_no_repeats(self):
        """Password without repeating chars should pass."""
        validator = NoRepeatingCharactersValidator(max_consecutive=3)
        validator.validate("Abcdefgh123!")

    def test_valid_password_short_repeats(self):
        """Password with 3 or fewer repeats should pass."""
        validator = NoRepeatingCharactersValidator(max_consecutive=3)
        validator.validate("Abcaaabcd123!")  # 3 a's is ok

    def test_invalid_password_many_repeats(self):
        """Password with 4+ repeating chars should fail."""
        validator = NoRepeatingCharactersValidator(max_consecutive=3)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("Abcaaaabcd123!")  # 4 a's
        assert exc_info.value.code == "password_too_repetitive"

    def test_invalid_password_all_same(self):
        """Password with all same char should fail."""
        validator = NoRepeatingCharactersValidator(max_consecutive=3)
        with pytest.raises(ValidationError):
            validator.validate("aaaaaaaaaaaa")

    def test_get_help_text(self):
        """Help text should be returned."""
        validator = NoRepeatingCharactersValidator(max_consecutive=3)
        help_text = validator.get_help_text()
        assert "3" in help_text
        assert "consecutive" in help_text.lower()


class TestNoSequentialCharactersValidator:
    """Tests for NoSequentialCharactersValidator."""

    def test_valid_password_no_sequences(self):
        """Password without sequences should pass."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        validator.validate("Xbvnmqw789!")

    def test_valid_password_short_sequence(self):
        """Password with 3-char sequence should pass (limit is 4)."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        validator.validate("Xabc789!")  # 'abc' is only 3 chars

    def test_invalid_password_numeric_sequence(self):
        """Password with '1234' should fail."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("Xbvnm1234!")
        assert exc_info.value.code == "password_too_sequential"

    def test_invalid_password_alpha_sequence(self):
        """Password with 'abcd' should fail."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        with pytest.raises(ValidationError):
            validator.validate("Xabcd789!")

    def test_invalid_password_qwerty_sequence(self):
        """Password with 'qwer' should fail."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        with pytest.raises(ValidationError):
            validator.validate("Xqwer789!")

    def test_case_insensitive(self):
        """Sequences should be detected regardless of case."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        with pytest.raises(ValidationError):
            validator.validate("XABCD789!")

    def test_reverse_sequence(self):
        """Reverse sequences should be detected."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        with pytest.raises(ValidationError):
            validator.validate("X4321abc!")  # 4321 is reverse

    def test_get_help_text(self):
        """Help text should be returned."""
        validator = NoSequentialCharactersValidator(max_sequential=4)
        help_text = validator.get_help_text()
        assert "4" in help_text
        assert "sequential" in help_text.lower()


NCSC_LIST_PATH = (
    Path(__file__).resolve().parent.parent / "checktick_app/core/ncsc-passwords.txt"
)


class TestNCSCCommonPasswordList:
    """Tests that the NCSC 100k deny list is present and wired into CommonPasswordValidator."""

    def test_ncsc_password_list_file_exists(self):
        """The NCSC password list file must be present in the repository."""
        assert NCSC_LIST_PATH.exists(), (
            f"NCSC password list not found at {NCSC_LIST_PATH}. "
            "Run: curl -fsSL https://raw.githubusercontent.com/danielmiessler/SecLists/"
            "master/Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt "
            "-o checktick_app/core/ncsc-passwords.txt"
        )

    def test_ncsc_password_list_has_sufficient_entries(self):
        """The NCSC list should contain at least 99,000 entries."""
        lines = [
            line
            for line in NCSC_LIST_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) >= 99_000, f"Expected ≥99,000 entries, got {len(lines)}"

    def test_common_password_validator_uses_ncsc_list(self):
        """CommonPasswordValidator must be configured with the NCSC list path."""
        from django.conf import settings

        validators = settings.AUTH_PASSWORD_VALIDATORS
        common = next(
            (v for v in validators if "CommonPasswordValidator" in v["NAME"]),
            None,
        )
        assert (
            common is not None
        ), "CommonPasswordValidator not found in AUTH_PASSWORD_VALIDATORS"
        assert (
            "OPTIONS" in common
        ), "CommonPasswordValidator has no OPTIONS (password_list_path not set)"
        assert (
            "password_list_path" in common["OPTIONS"]
        ), "password_list_path not configured on CommonPasswordValidator"
        configured_path = Path(common["OPTIONS"]["password_list_path"])
        assert (
            configured_path.resolve() == NCSC_LIST_PATH
        ), f"password_list_path points to {configured_path}, expected {NCSC_LIST_PATH}"

    def test_common_passwords_rejected(self):
        """Well-known passwords from the NCSC list should be rejected."""
        validator = CommonPasswordValidator(password_list_path=str(NCSC_LIST_PATH))
        # These are the first few entries in the NCSC list
        for bad_password in ("123456", "password", "qwerty", "iloveyou", "abc123"):
            with pytest.raises(ValidationError, match="too common"):
                validator.validate(bad_password)

    def test_strong_password_not_rejected(self):
        """A strong, unique password should not be on the deny list."""
        validator = CommonPasswordValidator(password_list_path=str(NCSC_LIST_PATH))
        # Validate raises nothing for a strong password
        validator.validate("xK9#mP2$vL7@nQ4!")
