"""
Custom password validators for enhanced security.

These validators enforce stronger password complexity requirements
suitable for healthcare applications handling sensitive data.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexityValidator:
    """
    Validate that the password contains a mix of character types.

    Requires at least 3 of the following 4 character types:
    - Uppercase letters (A-Z)
    - Lowercase letters (a-z)
    - Digits (0-9)
    - Special characters (!@#$%^&*()_+-=[]{}|;':\",./<>?)

    This follows NIST SP 800-63B guidance which recommends complexity
    checks while avoiding overly prescriptive rules that encourage
    predictable patterns.
    """

    def __init__(self, min_character_types: int = 3):
        self.min_character_types = min_character_types

    def validate(self, password: str, user=None) -> None:
        character_types = 0

        if re.search(r"[A-Z]", password):
            character_types += 1
        if re.search(r"[a-z]", password):
            character_types += 1
        if re.search(r"[0-9]", password):
            character_types += 1
        if re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:'\",.<>/?`~\\]", password):
            character_types += 1

        if character_types < self.min_character_types:
            raise ValidationError(
                _(
                    "Password must contain at least %(min_types)d of the following: "
                    "uppercase letters, lowercase letters, numbers, and special characters."
                ),
                code="password_too_simple",
                params={"min_types": self.min_character_types},
            )

    def get_help_text(self) -> str:
        return _(
            "Your password must contain at least %(min_types)d of the following: "
            "uppercase letters (A-Z), lowercase letters (a-z), numbers (0-9), "
            "and special characters (!@#$%% etc.)."
        ) % {"min_types": self.min_character_types}


class NoRepeatingCharactersValidator:
    """
    Validate that the password does not contain excessive repeating characters.

    Prevents passwords like 'aaaaaaaaaa' or '1111111111' that may pass
    length requirements but provide weak security.
    """

    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive

    def validate(self, password: str, user=None) -> None:
        # Check for repeating characters
        pattern = rf"(.)\1{{{self.max_consecutive},}}"
        if re.search(pattern, password):
            raise ValidationError(
                _(
                    "Password cannot contain more than %(max)d consecutive "
                    "identical characters."
                ),
                code="password_too_repetitive",
                params={"max": self.max_consecutive},
            )

    def get_help_text(self) -> str:
        return _(
            "Your password cannot contain more than %(max)d consecutive "
            "identical characters."
        ) % {"max": self.max_consecutive}


class NoSequentialCharactersValidator:
    """
    Validate that the password does not contain obvious sequences.

    Prevents passwords containing sequences like '123456', 'abcdef',
    'qwerty', etc.
    """

    SEQUENCES = [
        "0123456789",
        "9876543210",
        "abcdefghijklmnopqrstuvwxyz",
        "zyxwvutsrqponmlkjihgfedcba",
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
    ]

    def __init__(self, max_sequential: int = 4):
        self.max_sequential = max_sequential

    def validate(self, password: str, user=None) -> None:
        password_lower = password.lower()

        for sequence in self.SEQUENCES:
            for i in range(len(sequence) - self.max_sequential + 1):
                if sequence[i : i + self.max_sequential] in password_lower:
                    raise ValidationError(
                        _(
                            "Password cannot contain %(length)d or more "
                            "sequential characters (e.g., '1234', 'abcd')."
                        ),
                        code="password_too_sequential",
                        params={"length": self.max_sequential},
                    )

    def get_help_text(self) -> str:
        return _(
            "Your password cannot contain %(length)d or more sequential "
            "characters (e.g., '1234', 'abcd', 'qwerty')."
        ) % {"length": self.max_sequential}
