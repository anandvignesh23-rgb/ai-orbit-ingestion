from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([.,;:!?])")


def normalize_unicode(text: str | None) -> str:
    if text is None:
        return ""
    return unicodedata.normalize("NFKC", str(text))


def normalize_whitespace(text: str | None) -> str:
    if text is None:
        return ""
    return WHITESPACE_RE.sub(" ", str(text)).strip()


def strip_html(text: str | None) -> str:
    if text is None:
        return ""

    decoded = html.unescape(str(text))
    try:
        soup = BeautifulSoup(decoded, "html.parser")
        stripped = soup.get_text(" ")
    except Exception:
        stripped = decoded
    return normalize_whitespace(stripped)


def clean_description(text: str | None) -> str:
    cleaned = strip_html(text)
    cleaned = html.unescape(cleaned)
    cleaned = normalize_unicode(cleaned)
    cleaned = normalize_whitespace(cleaned)
    return SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", cleaned)
