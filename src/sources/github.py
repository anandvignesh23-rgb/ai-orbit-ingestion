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

LOGGER = logging.getLogger("source.github")

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
DEFAULT_QUERIES = [
    "topic:llm",
    "topic:generative-ai",
    "topic:mcp",
    "topic:agents",
    "topic:rag",
    "topic:machine-learning",
    "topic:computer-vision",
]


class GitHubSource(BaseSource):
    def __init__(
        self,
        queries: Iterable[str] | None = None,
        token: str | None = None,
        per_page: int = 10,
        max_pages: int = 1,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.queries = list(queries or DEFAULT_QUERIES)
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.per_page = per_page
        self.max_pages = max_pages
        self.timeout = timeout
        self._client = client

    @property
    def source_name(self) -> str:
        return "github"

    def discover(self) -> list[RawRecord]:
        records: list[RawRecord] = []
        try:
            with self._managed_client() as client:
                for query in self.queries:
                    for page in range(1, self.max_pages + 1):
                        payload = self._search_repositories(client, query, page)
                        items = payload.get("items", [])
                        if not isinstance(items, list):
                            LOGGER.warning(
                                "unexpected_items_shape query=%s page=%s",
                                query,
                                page,
                            )
                            continue
                        for item in items:
                            record = self._record_from_item(item)
                            if record is not None:
                                records.append(record)
        except SourceError:
            LOGGER.exception("github_discovery_failed")
            return []

        LOGGER.info("discovered=%s", len(records))
        return records

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate

    def _managed_client(self) -> _ClientContext:
        if self._client is not None:
            return _ClientContext(self._client, should_close=False)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return _ClientContext(
            httpx.Client(headers=headers, timeout=self.timeout),
            should_close=True,
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _search_repositories(
        self,
        client: httpx.Client,
        query: str,
        page: int,
    ) -> dict[str, Any]:
        try:
            response = client.get(
                GITHUB_SEARCH_URL,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": self.per_page,
                    "page": page,
                },
            )
        except (httpx.TimeoutException, httpx.TransportError):
            raise

        if response.status_code in {403, 429}:
            remaining = response.headers.get("X-RateLimit-Remaining")
            message = "github_rate_limited"
            if remaining == "0":
                reset = response.headers.get("X-RateLimit-Reset", "unknown")
                message = f"github_rate_limited reset={reset}"
            raise SourceError(message)
        if response.status_code >= 500:
            raise SourceError(f"github_server_error status={response.status_code}")
        if response.status_code >= 400:
            raise SourceError(f"github_client_error status={response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError("github_malformed_json") from exc
        if not isinstance(data, dict):
            raise SourceError("github_unexpected_json_shape")
        return data

    def _record_from_item(self, item: Any) -> RawRecord | None:
        if not isinstance(item, dict):
            LOGGER.warning("malformed_repository_record")
            return None

        full_name = item.get("full_name") or item.get("name")
        html_url = item.get("html_url")
        if not full_name or not html_url:
            LOGGER.warning("missing_required_repository_fields")
            return None

        owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
        payload = {
            "name": item.get("name") or full_name,
            "full_name": full_name,
            "owner": owner.get("login"),
            "description": item.get("description"),
            "html_url": html_url,
            "stars": item.get("stargazers_count"),
            "primary_language": item.get("language"),
            "last_updated": item.get("updated_at"),
            "topics": item.get("topics") or [],
        }
        return RawRecord(
            source_name=self.source_name,
            source_url=html_url,
            record_type="repository",
            payload=payload,
        )


class _ClientContext:
    def __init__(self, client: httpx.Client, should_close: bool) -> None:
        self.client = client
        self.should_close = should_close

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, *args: object) -> None:
        if self.should_close:
            self.client.close()
