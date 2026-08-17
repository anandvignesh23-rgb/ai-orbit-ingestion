from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.sources.base import BaseSource, RawRecord, SourceError
from src.utils.logging import sanitize_url

LOGGER = logging.getLogger("source.youtube")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_BASE_URL = "https://www.youtube.com/watch"
DEFAULT_QUERIES = [
    "AI agents",
    "large language models",
    "retrieval augmented generation",
    "generative AI tools",
    "AI robotics",
]


class YouTubeSource(BaseSource):
    def __init__(
        self,
        queries: Iterable[str] | None = None,
        api_key: str | None = None,
        max_results: int = 5,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.queries = list(queries or DEFAULT_QUERIES)
        self.api_key = api_key if api_key is not None else os.getenv("YOUTUBE_API_KEY")
        self.max_results = max_results
        self.timeout = timeout
        self._client = client

    @property
    def source_name(self) -> str:
        return "youtube"

    def discover(self) -> list[RawRecord]:
        if not self.api_key:
            LOGGER.warning("youtube_skipped_missing_api_key")
            return []

        records: list[RawRecord] = []
        seen_video_ids: set[str] = set()
        try:
            with self._managed_client() as client:
                for query in self.queries:
                    payload = self._search_videos(client, query)
                    items = payload.get("items", [])
                    if not isinstance(items, list):
                        LOGGER.warning("unexpected_video_items_shape query=%s", query)
                        continue
                    for item in items:
                        record = self._record_from_item(item, query=query)
                        if record is None:
                            continue
                        video_id = record.payload["video_id"]
                        if video_id in seen_video_ids:
                            continue
                        seen_video_ids.add(video_id)
                        records.append(record)
        except SourceError:
            LOGGER.exception("youtube_discovery_failed")
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
    def _search_videos(self, client: httpx.Client, query: str) -> dict[str, Any]:
        try:
            response = client.get(
                YOUTUBE_SEARCH_URL,
                params={
                    "part": "snippet",
                    "type": "video",
                    "q": query,
                    "maxResults": self.max_results,
                    "order": "relevance",
                    "key": self.api_key,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError):
            raise

        if response.status_code in {403, 429}:
            raise SourceError(f"youtube_rate_limited_or_forbidden status={response.status_code}")
        if response.status_code >= 500:
            raise SourceError(f"youtube_server_error status={response.status_code}")
        if response.status_code >= 400:
            raise SourceError(f"youtube_client_error status={response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            safe_url = sanitize_url(str(response.request.url)) if response.request else YOUTUBE_SEARCH_URL
            raise SourceError(f"youtube_malformed_json url={safe_url}") from exc
        if not isinstance(data, dict):
            raise SourceError("youtube_unexpected_json_shape")
        return data

    def _record_from_item(self, item: Any, *, query: str | None = None) -> RawRecord | None:
        if not isinstance(item, dict):
            LOGGER.warning("malformed_video_record")
            return None

        video_id = _video_id_from_item(item)
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        title = snippet.get("title")
        if not video_id or not title:
            LOGGER.warning("missing_required_video_fields")
            return None

        video_url = f"{YOUTUBE_VIDEO_BASE_URL}?v={video_id}"
        payload = {
            "video_id": video_id,
            "title": title,
            "description": snippet.get("description"),
            "channel": snippet.get("channelTitle"),
            "channel_id": snippet.get("channelId"),
            "published_at": snippet.get("publishedAt"),
            "video_url": video_url,
            "query": query,
        }
        return RawRecord(
            source_name=self.source_name,
            source_url=video_url,
            record_type="video",
            payload=payload,
        )


def _video_id_from_item(item: dict[str, Any]) -> str | None:
    raw_id = item.get("id")
    if isinstance(raw_id, dict):
        value = raw_id.get("videoId")
    else:
        value = raw_id
    if value is None:
        return None
    video_id = str(value).strip()
    return video_id or None


class _ClientContext:
    def __init__(self, client: httpx.Client, should_close: bool) -> None:
        self.client = client
        self.should_close = should_close

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, *args: object) -> None:
        if self.should_close:
            self.client.close()
