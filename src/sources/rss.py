from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import feedparser
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.cleaning.text import clean_description
from src.sources.base import BaseSource, RawRecord, SourceError

LOGGER = logging.getLogger("source.rss")


@dataclass(frozen=True)
class FeedConfig:
    name: str
    url: str


class RSSSource(BaseSource):
    def __init__(
        self,
        feeds: Iterable[dict[str, str] | FeedConfig] | None = None,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.feeds = [_coerce_feed(feed) for feed in feeds or []]
        self.timeout = timeout
        self._client = client

    @property
    def source_name(self) -> str:
        return "rss"

    def discover(self) -> list[RawRecord]:
        records: list[RawRecord] = []
        seen_urls: set[str] = set()
        try:
            with self._managed_client() as client:
                for feed in self.feeds:
                    parsed = self._fetch_and_parse(client, feed)
                    entries = getattr(parsed, "entries", [])
                    if not isinstance(entries, list):
                        LOGGER.warning("unexpected_entries_shape feed=%s", feed.name)
                        continue
                    for entry in entries:
                        record = self._record_from_entry(entry, feed)
                        if record is None:
                            continue
                        dedupe_key = record.source_url or record.payload["title"]
                        if dedupe_key in seen_urls:
                            continue
                        seen_urls.add(dedupe_key)
                        records.append(record)
        except SourceError:
            LOGGER.exception("rss_discovery_failed")
            return []

        LOGGER.info("discovered=%s", len(records))
        return records

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate

    def _managed_client(self) -> _ClientContext:
        if self._client is not None:
            return _ClientContext(self._client, should_close=False)
        return _ClientContext(httpx.Client(timeout=self.timeout), should_close=True)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _fetch_and_parse(self, client: httpx.Client, feed: FeedConfig) -> Any:
        try:
            response = client.get(feed.url)
        except (httpx.TimeoutException, httpx.TransportError):
            raise

        if response.status_code >= 500:
            raise SourceError(f"rss_server_error feed={feed.name} status={response.status_code}")
        if response.status_code >= 400:
            raise SourceError(f"rss_client_error feed={feed.name} status={response.status_code}")

        parsed = feedparser.parse(response.content)
        if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", []):
            LOGGER.warning("malformed_feed feed=%s", feed.name)
            return parsed
        return parsed

    def _record_from_entry(self, entry: Any, feed: FeedConfig) -> RawRecord | None:
        title = _entry_value(entry, "title")
        link = _entry_value(entry, "link")
        if not title or not link:
            LOGGER.warning("missing_required_rss_fields feed=%s", feed.name)
            return None

        summary = (
            _entry_value(entry, "summary")
            or _entry_value(entry, "description")
            or _entry_value(entry, "subtitle")
        )
        published_at = (
            _entry_value(entry, "published")
            or _entry_value(entry, "updated")
            or _entry_value(entry, "created")
        )
        publisher = _entry_value(entry, "publisher") or feed.name

        return RawRecord(
            source_name=self.source_name,
            source_url=link,
            record_type="news",
            payload={
                "title": clean_description(title),
                "description": clean_description(summary),
                "article_url": link,
                "published_at": published_at,
                "publisher": publisher,
                "feed_name": feed.name,
                "feed_url": feed.url,
            },
        )


def _coerce_feed(feed: dict[str, str] | FeedConfig) -> FeedConfig:
    if isinstance(feed, FeedConfig):
        return feed
    name = str(feed.get("name", "")).strip()
    url = str(feed.get("url", "")).strip()
    if not name or not url:
        raise ValueError("RSS feeds require name and url")
    return FeedConfig(name=name, url=url)


def _entry_value(entry: Any, key: str) -> str | None:
    if isinstance(entry, dict):
        value = entry.get(key)
    else:
        value = getattr(entry, key, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class _ClientContext:
    def __init__(self, client: httpx.Client, should_close: bool) -> None:
        self.client = client
        self.should_close = should_close

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, *args: object) -> None:
        if self.should_close:
            self.client.close()
