from __future__ import annotations

import logging
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "key",
    "token",
}


def configure_logging(level: str | int | None = None) -> None:
    selected_level = level or os.getenv("LOG_LEVEL", "INFO")
    if isinstance(selected_level, str):
        selected_level = selected_level.upper()

    logging.basicConfig(
        level=selected_level,
        format="%(levelname)-5s %(name)s %(message)s",
        force=False,
    )


def sanitize_url(url: str) -> str:
    parts = urlsplit(str(url))
    sanitized_query = [
        (key, "[REDACTED]" if key.lower() in SECRET_KEYS else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(sanitized_query, doseq=True),
            parts.fragment,
        )
    )
