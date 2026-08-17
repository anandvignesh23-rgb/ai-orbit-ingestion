from __future__ import annotations

import re
import string

from src.cleaning.text import normalize_unicode, normalize_whitespace

COMPANY_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
}

PUNCTUATION_TRANSLATION = str.maketrans(
    {char: " " for char in string.punctuation}
)


def normalize_name(name: str, entity_type: str | None = None) -> str:
    normalized = normalize_unicode(name).casefold()
    normalized = normalized.translate(PUNCTUATION_TRANSLATION)
    normalized = normalize_whitespace(normalized)

    if entity_type and entity_type.strip().lower() == "company":
        tokens = [
            token
            for token in normalized.split()
            if token not in COMPANY_SUFFIXES
        ]
        normalized = " ".join(tokens)

    return _compact_canonical_spaces(normalized)


def _compact_canonical_spaces(name: str) -> str:
    """Remove token-boundary spaces for stable canonical comparison.

    Important product qualifiers remain part of the key, so "Claude" and
    "Claude Desktop" normalize to different values.
    """

    return re.sub(r"\s+", "", name)
