from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def normalize_url(url: str | None) -> str:
    if url is None:
        return ""

    raw_url = str(url).strip()
    if not raw_url:
        return ""
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"

    parts = urlsplit(raw_url)
    scheme = "https"
    hostname = (parts.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    netloc = hostname
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    path = _normalize_path(parts.path)
    query = _normalize_query(parts.query)
    return urlunsplit((scheme, netloc, path, query, ""))


def canonical_domain(url: str | None) -> str:
    normalized = normalize_url(url)
    if not normalized:
        return ""
    return urlsplit(normalized).hostname or ""


def _normalize_path(path: str) -> str:
    if not path or path == "/":
        return ""
    return path.rstrip("/")


def _normalize_query(query: str) -> str:
    if not query:
        return ""

    meaningful_params = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    return urlencode(meaningful_params, doseq=True)
